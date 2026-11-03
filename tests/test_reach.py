"""Offline tests for the Agent Reach adapter (reach.py) and its use in the other tools: fake runner, no network, no Agent Reach.
doctor and readiness, routing (site / public web / not ready), cache, throttle-free retries and backoff, blocks and cooldowns, manual
steps, block pages, TikTok bridge, transcripts, RSS, entity matching on social results, and the reach backends of social_verify,
social_content track fetch, reddit_trends, reddit_rules, yt_research, case_studies fetch and market_tracker."""
import os, sys, json, tempfile, subprocess, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
TMP = tempfile.mkdtemp()
os.environ["GLS_HOME"] = os.path.join(TMP, "home")     # never the user's real state, keys or cache
os.environ["GLS_REACH_CACHE"] = os.path.join(TMP, "cache")
os.environ.pop("GLS_REACH_FAKE", None)
import common
common.http_get = lambda url, **kw: (_ for _ in ()).throw(AssertionError("network: " + url))   # nothing may touch the network
import reach, entity_match as em
reach.time.sleep = lambda s: None                         # backoff without waiting

FX = json.load(open(os.path.join(HERE, "fixtures", "reach_fake.json"), encoding="utf-8"))
CALLS = []


def runner(argv, stdin=None, timeout=60):
    CALLS.append(list(argv))
    key = " ".join(argv)
    if key in DYN:
        v = DYN[key]
        v = v.pop(0) if isinstance(v, list) else v
        return json.dumps(v)
    for k in sorted(FX, key=len, reverse=True):
        if key.startswith(k):
            return json.dumps(FX[k])
    return json.dumps(dict(ok=False, items=[], error=dict(code="NOT_FOUND", message="no fixture " + key)))


DYN = {}


def reset(**opts):
    reach.set_runner(runner)
    reach.configure(cache_dir=os.path.join(TMP, "cache"), cache=True, max_age=24, retries=1, rate=0, mode="auto", manual=None)
    reach.configure(**opts)
    s = reach._state()                                    # cooldowns persist across runs by design: clear them between sections
    s.pop("cooldown", None)
    reach._save_state(s)
    CALLS.clear()


# ---- enabled / disabled
reach.set_runner(None)
os.environ["GLS_REACH"] = "off"
assert not reach.enabled()
os.environ.pop("GLS_REACH")
reset()
assert reach.enabled()
print("enabled ok: off by env, on with a runner")

# ---- doctor: ready / not ready per channel, TikTok row, markdown
d = reach.doctor()
st = {r["channel"]: r for r in d["rows"]}
assert d["installed"] and d["version"] == "1.6.1"
assert st["youtube"]["ready"] and st["web"]["ready"] and not st["twitter"]["ready"] and not st["instagram"]["ready"]
assert st["twitter"]["next"] == "! " + reach.login_cmd("twitter") and "reach.py login twitter" in st["twitter"]["next"] and "agent-reach login" not in st["twitter"]["next"] and "search" in st["twitter"]["public_web"]
assert st["tiktok"]["status"] == "unverified" and not st["tiktok"]["ready"] and "tiktok.com" in st["tiktok"]["next"]
md = reach.doctor_md(d)
assert "| youtube | pronto | sì |" in md and "reach.py login twitter" in md
assert "youtube" in d["ready"] and "twitter" in d["not_ready"]
print("doctor ok:", d["ready"])

# ---- routing: ready channel = site; login channel not ready = public web for search, not ready for profile
assert reach.route("youtube", "search") == "site"
assert reach.route("twitter", "search") == "public-web"
assert reach.route("twitter", "profile") is None
assert reach.route("reddit", "subreddit") is None and reach.route("reddit", "subreddit", mode="on") == "site"
man = os.path.join(TMP, "ricerche-manuali.md")
reset(manual=man)
r = reach.profile("x", "@studio")
assert not r["ok"] and r["label"] == "[DA VERIFICARE]" and r["error"]["code"] == "NEED_LOGIN" and not CALLS[2:], CALLS
txt = open(man, encoding="utf-8").read()
assert "agent-reach · twitter · profile studio" in txt and "reach.py login twitter" in txt and "! agent-reach login" not in txt and "x.com/search?q=studio" in txt
reach.profile("x", "studio")
assert open(man, encoding="utf-8").read().count("twitter · profile studio") == 1           # same day, same step: written once
print("routing ok: public web for search, manual step for profile (once)")

# ---- a real call: metrics parsed, label, cache
reset()
r = reach.search("x", "Test Game", 5)
assert r["ok"] and r["label"] == "[FATTO]" and r["backend"] == "public-web" and r["access"] == "public"
assert ["twitter", "search", "Test Game", "--limit", "5", "--backend", "public-web"] in CALLS
n = len(CALLS)
r2 = reach.search("x", "Test Game", 5)
assert r2["cached"] and len(CALLS) == n
y = reach.read("https://www.youtube.com/watch?v=abcdefghijk")
it = y["items"][0]
assert it["metrics"] == {"views": 12345, "likes": 678} and it["published"] == "2026-10-01" and y["source"].startswith("agent-reach 1.6.1")
print("call ok: [FATTO], public-web backend, metrics, cache hit without a second run")

# ---- logged-in channel ready: X profile and tweets with 1.2K-style counts and X dates
reset()
DYN["doctor"] = json.loads(json.dumps(FX["doctor"]))
for c in DYN["doctor"]["result"]["channels"]:
    if c["channel"] in ("twitter", "instagram", "reddit"):
        c["status"] = "ready"
reach.set_runner(runner)
p = reach.profile("x", "studio")
assert p["ok"] and p["items"][0]["metrics"]["followers"] == 1200 and p["access"] == "site", p
tw = reach.posts("x", "studio", 2)
assert tw["items"][0]["metrics"]["views"] == 3400 and tw["items"][0]["published"] == "2026-10-08"
print("logged-in ok: followers 1.2K -> 1200, tweet date from X format")

# ---- final errors stop the channel; RATE_LIMITED sets a cooldown; TIMEOUT is retried once
reset()
DYN["doctor"] = FX["doctor_all_ready"]
reach.set_runner(runner)
DYN["instagram profile nasa"] = dict(ok=False, items=[], error=dict(code="NEED_LOGIN", message="HTTP 401"))
r = reach.profile("instagram", "nasa")
assert r["error"]["code"] == "NEED_LOGIN" and "instagram" in reach._BLOCKED
k = len(CALLS)
r = reach.posts("instagram", "nasa", 3)
assert not r["ok"] and len(CALLS) == k                       # blocked for the rest of the run: no new call
DYN["reddit subreddit IndieDev --limit 3"] = dict(ok=False, items=[], error=dict(code="RATE_LIMITED", message="HTTP 429"))
r = reach.posts("reddit", "IndieDev", 3)
assert r["error"]["code"] == "RATE_LIMITED" and reach._cooldown("reddit")
DYN["youtube search slow --limit 2"] = [dict(ok=False, items=[], error=dict(code="TIMEOUT", message="slow")), FX["youtube search"]]
r = reach.search("youtube", "slow", 2)
assert r["ok"] and [c for c in CALLS if c[:3] == ["youtube", "search", "slow"]].__len__() == 2
print("errors ok: NEED_LOGIN blocks, RATE_LIMITED cools down, TIMEOUT retried")

# ---- a block page is never content
reset()
r = reach.read("https://www.reddit.com/r/IndieDev/about/rules")
assert not r["ok"] and r["error"]["code"] == "PLATFORM_BLOCKED" and r["label"] == "[DA VERIFICARE]"
assert not [f for f in os.listdir(os.path.join(TMP, "cache")) if f.startswith("reddit-read")]
print("block page ok: PLATFORM_BLOCKED, not cached")

# ---- TikTok: public search when not ready; bridge when ready; a video read from the account listing
reset()
r = reach.search("tiktok", "Test Game", 3)
assert r["ok"] and r["backend"] == "public-web" and all("tiktok.com" in x["url"] for x in r["items"]) and r["channel"] == "tiktok"
assert any(c[:2] == ["web", "search"] and "site:tiktok.com" in c[2] for c in CALLS)
reach._note_tiktok(True)
reset()
assert reach.status("tiktok") == "ready"
pr = reach.profile("tiktok", "teststudio")
assert pr["ok"] and pr["items"][0]["metrics"]["followers"] == 5300 and ["__tiktok__", "profile", "teststudio"] in CALLS
v = reach.read("https://www.tiktok.com/@teststudio/video/7550000000000000001")
assert v["ok"] and v["items"][0]["metrics"]["views"] == 15000 and v["items"][0]["metrics"]["shares"] == 12
print("tiktok ok: public search, bridge profile, video numbers by id")

# ---- transcripts and RSS
reset()
t = reach.transcript("https://www.youtube.com/watch?v=abcdefghijk", "en")
assert t["ok"] and "hello" in t["items"][0]["text"] and ["youtube", "subtitle", "https://www.youtube.com/watch?v=abcdefghijk", "--lang", "en"] in CALLS
atom = open(os.path.join(HERE, "fixtures", "reach_feed.xml"), encoding="utf-8").read()
items = reach.parse_feed(atom)
assert len(items) == 2 and items[0]["title"] == "Devlog 12: the physics bug" and items[0]["published"] == "2026-10-20"
print("transcript and rss ok")

# ---- entity matching on social results
reset()
res = reach.search("x", "Test Game", 5)
g = dict(title="Wobble Kitchen", appid=4242, developers=["Tiny Pan Studio"], words=["co-op", "physics", "cooking"], languages=["English"])
em.filter_reach(res, g)
kept = [x["url"] for x in res["kept_items"]]
assert any("1001" in u for u in kept) and not any("1002" in u for u in kept) and res["rejected_count"] >= 1, [(x["url"], x["score"], x["why"]) for x in res["items"]]
print("entity_match ok: game post kept, unrelated one rejected")

# ---- social_verify: real followers for TikTok / X with source and date
reset()
import social_verify as sv
row = sv.with_reach("https://www.tiktok.com/@teststudio/video/7550000000000000001", "tiktok", dict(url="u", handle="teststudio", followers="manual (requires login)"))
assert row["followers"] == 5300 and row["followers_label"] == "[FATTO]" and "agent-reach" in row["followers_source"] and row["views"] == 15000
DYN["doctor"] = FX["doctor_all_ready"]; reach.set_runner(runner)
row = sv.with_reach("https://x.com/studio", "x", dict(url="u"))
assert row["followers"] == 1200
print("social_verify ok: TikTok and X followers [FATTO]")

# ---- social_content track fetch: fills empty numbers, never wishlists
reset()
import social_content as sc
DYN["doctor"] = FX["doctor_all_ready"]; reach.set_runner(runner); reach._note_tiktok(True)
rows = [dict(date="2026-10-05", platform="tiktok", url="https://www.tiktok.com/@teststudio/video/7550000000000000001", views="", likes="", wishlists_delta=""),
        dict(date="2026-10-01", platform="youtube_shorts", url="https://www.youtube.com/shorts/abcdefghijk", views="99", likes=""),
        dict(date="2026-10-02", platform="instagram", url="https://www.instagram.com/p/XYZ/", views="", likes=""),
        dict(date="2026-10-03", platform="reddit", url="", views="")]
stt = sc.fetch_numbers(rows, handles=dict(instagram="teststudio"))
assert rows[0]["views"] == "15000" and rows[0]["shares"] == "12" and rows[0]["wishlists_delta"] == "" and "agent-reach" in rows[0]["fetched"]
assert rows[1]["views"] == "99" and rows[1]["likes"] == "678"                       # existing number kept, empty one filled
assert rows[2]["likes"] == "321" and "abbinato per data" in rows[2]["fetched"]
assert stt["updated"] == 3 and stt["skipped"] == 1, stt
print("social_content fetch ok:", stt)

# ---- reddit_trends via Agent Reach: real upvotes, top = best quarter
reset()
import reddit_trends as rt
DYN["doctor"] = FX["doctor_all_ready"]; reach.set_runner(runner)
top, new = rt.fetch_reach("IndieDev", 100)
assert len(new) == 8 and top[0]["score"] == 900 and top[0]["format"] == "video" and new[0]["rank"] == 1
an = rt.analyse(top, new)
assert an["n_top"] == 5 and any(r["key"] == "video" for r in an["format"])
assert rt.reach_format(dict(post_hint="image", url_overridden_by_dest="https://i.redd.it/a.gif")) == "gif"
print("reddit_trends ok: reach mode with real upvotes")

# ---- reddit_rules from the public page text
import reddit_rules as rr
rules = rr.rules_from_text("Rules\n1. No spam or self-promotion outside Saturday\nOne link per week.\n2. Be kind\nNo insults.")
assert [x["title"] for x in rules] == ["No spam or self-promotion outside Saturday", "Be kind"] and rules[0]["text"] == "One link per week."
reset()
o = rr.via_reach(dict(subreddit="IndieDev", url="https://www.reddit.com/r/IndieDev/", error="HTTPError 403"))
assert o["label"] == "[FATTO]" and o["rules"] and 1 in o["promo_related_rules"] and o["anonymous_error"] == "HTTPError 403" and "error" not in o
print("reddit_rules ok: rules from the page through Agent Reach")

# ---- yt_research reach backend and transcript
reset()
import yt_research as yr
vids = yr.reach_search("Test Game", "year", 5)
assert vids and vids[0]["vid"] == "abcdefghijk" and vids[0]["views"] == 12345 and vids[0]["channel_id"] == "UC123" and vids[0]["when"] == "2026-10-01"
print("yt_research ok: reach search with dates")

# ---- case_studies fetch: draft with numbers from the post and its comments
reset()
import case_studies as cs
dr = cs.fetch_drafts(["https://www.reddit.com/r/gamedev/comments/abc/my_next_fest_results/"])[0]
assert dr["ok"] and dr["has_comments"] and {"next fest"} <= set(dr["events"]) and any(x["value"] == 2100 and x["what"] == "wishlists" for x in dr["numbers"])
assert dr["draft"]["confidence"] == "self_reported" and dr["draft"]["source_url"].startswith("https://www.reddit.com")
print("case_studies fetch ok:", [(x["value"], x["what"]) for x in dr["numbers"]])

# ---- market_tracker: accounts from links, social through Agent Reach
reset()
import market_tracker as mt
acc = mt.accounts_from_links(["https://x.com/studio", "https://www.tiktok.com/@teststudio", "https://twitter.com/intent/tweet?x", "https://store.steampowered.com/app/1"])
assert acc == {"x": "studio", "tiktok": "teststudio"}, acc
DYN["doctor"] = FX["doctor_all_ready"]; reach.set_runner(runner); reach._note_tiktok(True)
found, official, src = mt.reach_social(dict(title="Wobble Kitchen"), acc, 5)
assert any(x["platform"] == "x" for x in found) and all(x["official"] for x in official) and src["x_followers"]["followers"] == 1200
assert src["tiktok_followers"]["followers"] == 5300 and "instagram" in src
print("market_tracker ok:", sorted(k for k in src))

# ---- CLI with GLS_REACH_FAKE (subprocess, the way the agent runs it)
env = dict(os.environ, GLS_REACH_FAKE=os.path.join(HERE, "fixtures", "reach_fake.json"), PYTHONIOENCODING="utf-8", GLS_HOME=os.path.join(TMP, "home2"))
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "--cache-dir", os.path.join(TMP, "c2"), "doctor", "--json"], capture_output=True, text=True, encoding="utf-8", env=env)
dj = json.loads(out.stdout)
assert out.returncode == 0 and "youtube" in dj["ready"], out.stderr
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "--cache-dir", os.path.join(TMP, "c2"), "search", "x", "Test", "Game", "--limit", "5"], capture_output=True, text=True, encoding="utf-8", env=env)
assert out.returncode == 0 and json.loads(out.stdout)["label"] == "[FATTO]", out.stderr
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "setup"], capture_output=True, text=True, encoding="utf-8", env=env)
assert "reach.py login twitter" in out.stdout and "reach.py fix-lang" in out.stdout and "! agent-reach login" not in out.stdout and "cookie" not in out.stdout.lower().replace("login e cookie", "")
print("cli ok: doctor --json, search, setup")

# ---- login / fix-lang: patch the installed browser_watcher.py (on a temp copy), the profile language, the new subcommands
WATCHER = "import os\n\n\ndef _launch_cloak(url, *, headless=True):\n    ctx = launch_persistent_context(\n        str(browser.profile_dir()), headless=headless, locale=\"zh-CN\",\n        args=[\"--x\"],\n    )\n    return ctx\n"
wp = os.path.join(TMP, "browser_watcher.py")
open(wp, "w", encoding="utf-8", newline="").write(WATCHER)
r = reach.patch_watcher(wp, "it-IT")
t = open(wp, encoding="utf-8").read()
assert r["status"] == "patched" and r["was"] == "zh-CN" and "zh-CN" not in t and 'os.environ.get("REACH_BROWSER_LOCALE") or "it-IT"' in t and t.count("GLS-LOCALE-PATCH") == 1
assert open(wp + ".orig", encoding="utf-8").read() == WATCHER                          # backup = the untouched original
r = reach.patch_watcher(wp, "it-IT")
assert r["status"] == "unchanged" and open(wp, encoding="utf-8").read() == t           # idempotent: the second run changes nothing
r = reach.patch_watcher(wp, "en-GB")
t2 = open(wp, encoding="utf-8").read()
assert r["status"] == "updated" and '"en-GB"' in t2 and "it-IT" not in t2 and t2.count("locale=") == 1
assert open(wp + ".orig", encoding="utf-8").read() == WATCHER                          # the backup is never overwritten by a patched file
compile(t2, wp, "exec")
open(wp, "w", encoding="utf-8", newline="").write("def nothing():\n    pass\n")
assert reach.patch_watcher(wp, "it-IT")["status"] == "unrecognized"                      # a changed upstream file is left alone
assert reach.patch_watcher(os.path.join(TMP, "nope.py"), "it-IT")["status"] == "error"
print("patch_watcher ok: patched, backup, idempotent, language change, unrecognized")

assert reach.accept_languages("it-IT") == "it-IT,it,en-US,en" and reach.accept_languages("en-US") == "en-US,en" and reach.accept_languages("it") == "it,en-US,en"
os.environ.pop("REACH_BROWSER_LOCALE", None)
assert reach.wanted_lang("fr-FR") == "fr-FR" and reach.wanted_lang("xx; rm -rf") == reach.system_locale()
os.environ["REACH_BROWSER_LOCALE"] = "de-DE"
assert reach.wanted_lang() == "de-DE" and reach.wanted_lang("it-IT") == "it-IT"
os.environ.pop("REACH_BROWSER_LOCALE")
assert reach._LANG_RE.match(reach.system_locale())
pd = os.path.join(TMP, "profile", "Default")
os.makedirs(pd)
pp = os.path.join(pd, "Preferences")
open(pp, "w", encoding="utf-8").write(json.dumps({"intl": {"selected_languages": "zh-CN,zh"}, "other": {"k": [1, 2]}}, separators=(",", ":")))
r = reach.patch_prefs(pp, "it-IT")
d2 = json.load(open(pp, encoding="utf-8"))
assert r["status"] == "set" and d2["intl"] == {"selected_languages": "it-IT,it,en-US,en", "accept_languages": "it-IT,it,en-US,en"} and d2["other"] == {"k": [1, 2]}
assert json.load(open(pp + ".gls-backup", encoding="utf-8"))["intl"] == {"selected_languages": "zh-CN,zh"}
assert reach.patch_prefs(pp, "it-IT")["status"] == "unchanged" and reach.patch_prefs(os.path.join(pd, "x"), "it-IT")["status"] == "missing"
print("patch_prefs ok")

# fix_lang end to end with the fake runner: running browser -> profile untouched; stopped -> profile set
os.environ["GLS_REACH_WATCHER"] = os.path.join(TMP, "w2.py"); os.environ["GLS_REACH_PROFILE"] = os.path.join(TMP, "profile")
open(os.environ["GLS_REACH_WATCHER"], "w", encoding="utf-8").write(WATCHER)
open(pp, "w", encoding="utf-8").write(json.dumps({"intl": {"selected_languages": "ja"}}))
reset()
DYN["browser status"] = {"ok": True, "result": {"running": True, "headless": True, "profile_dir": os.environ["GLS_REACH_PROFILE"]}}
lines = []
rep = reach.fix_lang("it-IT", out=lines.append)
assert rep["watcher"]["status"] == "patched" and rep["running"] and rep["prefs"] is None and json.load(open(pp, encoding="utf-8"))["intl"] == {"selected_languages": "ja"}
assert any("ACCESO" in x for x in lines) and ["browser", "stop"] not in CALLS                  # never closed without --stop
CALLS.clear()
DYN["browser status"] = [{"ok": True, "result": {"running": True, "headless": True}}, {"ok": True, "result": {"running": False}}, {"ok": True, "result": {"running": False, "profile_dir": os.environ["GLS_REACH_PROFILE"]}}]
DYN["browser stop"] = {"ok": True, "result": {}}
rep = reach.fix_lang("it-IT", stop=True, out=lines.append)
assert ["browser", "stop"] in CALLS and rep["watcher"]["status"] == "unchanged" and rep["running"] is False, rep
assert rep["prefs"]["status"] == "set" and json.load(open(pp, encoding="utf-8"))["intl"]["selected_languages"] == "it-IT,it,en-US,en"
print("fix_lang ok: running browser untouched, --stop uses agent-reach's own command, then the profile is set")

# login: fix-lang first, then Agent Reach's `login <canale>`, nothing else; tiktok = the twitter window; --check = that channel only
reset()
DYN["browser status"] = {"ok": True, "result": {"running": False, "profile_dir": os.environ["GLS_REACH_PROFILE"]}}
DYN["login twitter"] = {"ok": True, "items": [{"opened": "https://x.com/login", "next": "log in in the window"}]}
lines = []
rc = reach.login("x", "it-IT", wait=False, out=lines.append)
flat = "\n".join(lines)
assert rc == 0 and ["login", "twitter"] in CALLS and "x.com/login" in flat and "login twitter --check" in flat, flat
assert CALLS.index(["browser", "status"]) < CALLS.index(["login", "twitter"])
CALLS.clear(); lines.clear()
rc = reach.login("tiktok", "it-IT", wait=False, out=lines.append)
assert ["login", "twitter"] in CALLS and ["login", "tiktok"] not in CALLS and "tiktok.com/login" in "\n".join(lines)
CALLS.clear(); lines.clear()
DYN["login instagram"] = {"ok": False, "items": [], "error": {"code": "NEED_SETUP", "message": "no browser", "hint": "x"}}
assert reach.login("instagram", "it-IT", wait=False, out=lines.append) == 3 and "NEED_SETUP" in lines[-1]
CALLS.clear(); lines.clear()
DYN["doctor"] = FX["doctor_all_ready"]; DYN["check twitter --timeout 60"] = {"ok": True}
reach._DOCTOR = None
rc = reach.login("twitter", check_only=True, out=lines.append)
assert ["check", "twitter", "--timeout", "60"] in CALLS and ["login", "twitter"] not in CALLS and lines and lines[0].startswith("Canale twitter"), (CALLS, lines)
del DYN["doctor"]
os.environ.pop("GLS_REACH_WATCHER"); os.environ.pop("GLS_REACH_PROFILE")
print("login ok:", lines[0])

# CLI parsing of the new subcommands (subprocess, fake runner: nothing real is touched)
env = dict(os.environ, GLS_REACH_FAKE=os.path.join(HERE, "fixtures", "reach_fake.json"), PYTHONIOENCODING="utf-8", GLS_HOME=os.path.join(TMP, "home3"),
           GLS_REACH_WATCHER=os.path.join(TMP, "w3.py"), GLS_REACH_PROFILE=os.path.join(TMP, "noprofile"))
open(env["GLS_REACH_WATCHER"], "w", encoding="utf-8").write(WATCHER)
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "fix-lang", "--lang", "it-IT"], capture_output=True, text=True, encoding="utf-8", env=env)
assert out.returncode == 0 and "corretto browser_watcher.py" in out.stdout and "zh-CN" not in open(env["GLS_REACH_WATCHER"], encoding="utf-8").read(), out.stdout + out.stderr
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "fix-lang", "--lang", "it-IT"], capture_output=True, text=True, encoding="utf-8", env=env)
assert out.returncode == 0 and "già a posto" in out.stdout, out.stdout
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "login", "--help"], capture_output=True, text=True, encoding="utf-8", env=env)
assert out.returncode == 0 and "--check" in out.stdout and "--no-wait" in out.stdout and "--lang" in out.stdout
out = subprocess.run([sys.executable, os.path.join(R, "reach.py"), "login"], capture_output=True, text=True, encoding="utf-8", env=env)
assert out.returncode == 2                                                                       # argparse: the channel is required
print("cli ok: fix-lang (twice), login --help, login without channel")

print("ALL REACH TESTS PASSED")
