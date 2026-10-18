"""promo_events.py: curated file format (the real fallback too), occurrences from dated editions and usual months (no
invented days), stage / requirement / genre checks, value score and tiers, at most N applications with at most 3 long
shots, fetch with deadline parsing and graceful failure, window.csv export (own rows replaced, hand rows and Steam's
events never duplicated), deadlines into calendar.md / TODO.md once (stable ids), the generic TODO line superseded,
the Markdown report, top_moves 'promo' move, cp1252 console. No network."""
import os, sys, csv, json, shutil, tempfile, subprocess, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import common
FX = os.path.join(HERE, "fixtures", "promo_events_sample.json")
PAGES = {"https://example.org/funcozy/form": "<html><body><h1>Fun Cozy Fest 2027</h1><p>Submissions close: <b>November 20, 2026</b> at midnight.</p></body></html>",
         "https://example.org/biw/form": "<p>Deadline: October 23, 2026. Trailer due November 17, 2026.</p>"}
calls = []
def fake_get(url, **k):
    calls.append(url)
    if url in PAGES:
        return PAGES[url].encode("utf-8")
    raise OSError("offline test: " + url)
common.http_get = fake_get
import promo_events as pe, plan_steps as ps, todo_track as tt, top_moves as tm, launch_window as lw
D = dt.date
TODAY = D(2026, 10, 17)

# ---- the curated files are well formed: dated items have a source and a read date, undated ones a pattern
real = pe.load_fallback()
assert pe.validate(real) == [], pe.validate(real)[:5]
assert real["read_on"] and len([e for e in real["events"] if e.get("online", True)]) >= 15 and any(not e.get("online", True) for e in real["events"])
assert {e["kind"] for e in real["events"]} >= {"showcase", "steam_fest_3rd", "itch", "reddit_recurring", "newsletter", "italian"}
for e in real["events"]:
    assert e.get("reach_tier") in ("alta", "media", "piccola") and e.get("odds") in ("bassa", "media", "alta") and e.get("odds_why"), e["key"]
assert sum(1 for e in real["events"] if e.get("online", True) and e["odds"] in ("media", "alta")) >= 5         # feasible ones, not only long shots
data = pe.load_fallback(FX)
assert pe.validate(data) == []
it = dict(ev0 := data["events"][0], key="ita", name="Italian Sale", team_country="IT")
assert not pe.check(pe.occurrences(it, TODAY, D(2027, 12, 31))[0], pe.Timeline(page=D(2026, 10, 31)), ["Funny"], TODAY)["ok"]
assert pe.check(pe.occurrences(it, TODAY, D(2027, 12, 31))[0], pe.Timeline(page=D(2026, 10, 31), country="it"), ["Funny"], TODAY)["ok"]
only = dict(ev0, key="wl", name="Women Led", team_only="studi guidati da donne")
assert "riservato" in pe.check(pe.occurrences(only, TODAY, D(2027, 12, 31))[0], pe.Timeline(page=D(2026, 10, 31)), ["Funny"], TODAY)["reasons"][0]
assert pe.check(pe.occurrences(only, TODAY, D(2027, 12, 31))[0], pe.Timeline(page=D(2026, 10, 31), eligible=["wl"]), ["Funny"], TODAY)["ok"]
assert pe.validate(dict(events=[dict(key="x", kind="party", url="u", recurrence="annual", editions=[dict(start="2027-01-01", status="DA VERIFICARE")])]))   # no source -> flagged

# ---- occurrences
ev = {e["key"]: e for e in data["events"]}
to = D(2027, 12, 31)
wd = pe.occurrences(ev["wd"], TODAY, to)
assert [(o["key"], o["deadline"], o["opens"], o["estimated"]) for o in wd] == [("wd:2027-06", D(2027, 3, 31), D(2027, 3, 1), True)], wd   # 2026 window passed, never a day
fgs = pe.occurrences(ev["fgs"], TODAY, to)
assert [(o["key"], o["deadline"], o["opens"]) for o in fgs] == [("fgs:2027-03", D(2027, 1, 31), D(2026, 12, 1)), ("fgs:2027-06", D(2027, 4, 30), D(2027, 3, 1))], fgs
fc = pe.occurrences(ev["fun_cozy"], TODAY, to)
assert len(fc) == 1 and fc[0]["deadline"] == D(2026, 11, 15) and not fc[0]["estimated"]                   # the dated edition replaces the pattern for that year
assert pe.occurrences(ev["ss"], TODAY, to)[0]["rolling"]

# ---- checks and plan
tl = pe.Timeline(page=D(2026, 10, 31), itch=D(2026, 11, 10), demo=D(2026, 12, 20), launch=D(2027, 5, 13), ea=True)
tags = ["Roguelite", "Physics", "Comedy", "Funny", "Food", "Cute", "Singleplayer"]
assert pe.check(fc[0], tl, tags, TODAY)["ok"]
late = pe.Timeline(page=D(2026, 11, 20), demo=D(2026, 12, 20), launch=D(2027, 5, 13))
assert any("pagina Steam" in r for r in pe.check(fc[0], late, tags, TODAY)["reasons"])
res = pe.plan(data, TODAY, tl, tags, to)
keys = {r["key"]: r for r in res["matches"]}
rej = {r["event_key"]: r for r in res["rejected"]}
assert "spooky" in rej and "tema" in rej["spooky"]["reasons"][0]                                            # horror-only show: no fit
assert "discount_fest" in rej and any("già usciti" in x for x in rej["discount_fest"]["reasons"])
assert not any(r["event_key"] == "pax" for r in res["matches"] + res["rejected"]) and res["physical"][0]["key"] == "pax"
assert keys["fun_cozy:2027"]["score"] == 2 * 3 * 2 and keys["fun_cozy:2027"]["priority"] == "alta" and keys["fun_cozy:2027"]["tier"] == "fattibile"
assert keys["wd:2027-06"]["score"] == 3 * 1 * 2 and keys["wd:2027-06"]["tier"] == "tentativo" and keys["wd:2027-06"]["priority"] == "alta"
assert keys["fgs:2027-03"]["score"] == 3 and keys["fgs:2027-03"]["priority"] == "bassa"
assert keys["big_winter:2026"]["score"] == 8 and not keys["big_winter:2026"]["estimated"]
assert keys["shopk:2027"]["estimated"]                                                                        # a dated event without a published deadline: estimate
assert keys["ss"]["rolling"] and keys["ss"]["trigger"] == "2026-10-31"
coop = pe.plan(data, TODAY, pe.Timeline(page=D(2026, 10, 31), launch=D(2026, 11, 30)), tags, to)
assert any(r["event_key"] == "discount_fest" for r in coop["matches"])                                       # released by then

# ---- steps: value first, at most N, at most 3 long shots, stable ids
st = pe.steps(res, TODAY, max_apps=12)
apps = [s for s in st if s["kind"] == "candidatura"]
assert [s["key"] for s in apps][:2] == ["big_winter:2026", "fun_cozy:2027"], [s["key"] for s in apps]
assert any(s["key"] == "wd:2027-06" for s in apps) and sum(1 for s in apps if s["tier"] == "tentativo") <= 2                  # long shots capped
assert not any(s["key"].startswith("spooky") for s in apps)
assert all("[id promo:" in s["note"] for s in st) and any(s["kind"] == "abitudine" and "sabato" in s["text"] for s in st)
fc_step = next(s for s in apps if s["key"] == "fun_cozy:2027"); assert fc_step["due"] == "2026-11-10" and "FATTO" in fc_step["note"] and "compila il modulo" in fc_step["note"]
wd_step = next(s for s in apps if s["key"] == "wd:2027-06"); assert wd_step["due"] == "2027-03-01" and "DA VERIFICARE" in wd_step["text"] and "STIMA" in wd_step["note"]
many = dict(data, events=[dict(ev["wd"], key=f"wd{i}", name=f"Long Shot {i}") for i in range(6)] + [dict(ev["tiny"], key=f"t{i}", name=f"Tiny {i}") for i in range(12)])
st2 = pe.steps(pe.plan(many, TODAY, tl, tags, to), TODAY, max_apps=10)
assert len([s for s in st2 if s["kind"] == "candidatura"]) == 10 and sum(1 for s in st2 if s.get("tier") == "tentativo") == 2

# ---- fetch: a deadline next to "submissions close" is read; a missing page keeps the curated data; offline
f = pe.fetch(rate=0, fallback_path=FX, today=TODAY)
fcz = next(e for e in f["events"] if e["key"] == "fun_cozy")
auto = [x for x in fcz["editions"] if x["status"] == "LETTURA_AUTO"]
assert f["parser"] == "live" and auto and auto[0]["submission_deadline"] == "2026-11-20" and f["pages_read"] == 2, f
assert pe.find_deadline(PAGES["https://example.org/biw/form"], TODAY) == D(2026, 10, 23)
assert pe.find_deadline("<p>Deadline: March 1, 2027</p><p>Applications close April 2, 2027</p>", TODAY) is None   # two competing dates: nothing
assert pe.find_deadline("<p>Deadline: March 1, 2025</p>", TODAY) is None                                          # past
PAGES.clear()
f2 = pe.fetch(rate=0, fallback_path=FX, today=TODAY)
assert f2["parser"] == "fallback" and f2["pages_failed"] == 2 and len(f2["events"]) == len(data["events"])
assert pe.fetch(offline=True, fallback_path=FX)["parser"] == "fallback"
assert pe.diff(dict(events=[]), f) and pe.diff(None, f) == []

# ---- window.csv: own rows replaced, hand rows kept, Steam's events never twice
d = tempfile.mkdtemp(); evp = os.path.join(d, "promo.json"); common.write_json(data, evp)
win = os.path.join(d, "window.csv")
with open(win, "w", encoding="utf-8", newline="") as fh:
    fh.write("date,name,kind,weight,source,note\n2027-03-09,Big Co,big_release,5,steamdb upcoming,\n"
             "2026-12-01,Winter Indie Show 2026,festival,3,my note,\n2027-02-22,Steam Next Fest febbraio 2027,festival,4,\"steam_events.py, x, letto 2026-10-17\",\n")
steam_ev = os.path.join(d, "steam_events.json"); common.write_json(dict(read_on="2026-10-17", events=[dict(key="shop_keep_2027", name="Shop Keeper Fest", kind="themed_fest", start="2027-01-25", end="2027-02-01")]), steam_ev)
r1 = pe.export_window(pe.load(evp), win, steam_events_path=steam_ev); r2 = pe.export_window(pe.load(evp), win, steam_events_path=steam_ev)
rows = list(csv.DictReader(open(win, encoding="utf-8-sig")))
assert r1["written"] == r2["written"] and len(rows) == 3 + r2["written"], (r1, r2, rows)
assert sum(1 for r in rows if r["name"].startswith("Winter Indie Show")) == 1 and not any("Shop Keeper" in r["name"] for r in rows)   # hand row wins; Steam's fest skipped
assert all(r["kind"] in lw.KINDS for r in rows) and any(r["name"].startswith("Discount Fest") and r["source"].startswith("promo_events.py") for r in rows)
assert not any("Screenshot" in r["name"] or "PAX" in r["name"] for r in rows)
pe.export_window(pe.load(evp), win, include_estimated=True, steam_events_path=steam_ev)
est = [r for r in csv.DictReader(open(win, encoding="utf-8-sig")) if "(stima)" in r["name"]]
assert est and all("DA VERIFICARE" in r["note"] and float(r["weight"]) >= 0.5 for r in est)
assert lw.read_window(win)[1] == []

# ---- deadlines into calendar.md / TODO.md: once, valid formats, generic line superseded
L = os.path.join(d, "launch"); os.makedirs(L)
open(os.path.join(L, "calendar.md"), "w", encoding="utf-8").write("# Cal\n\n## ✅ Passi in ordine\n🤖 = io · 👤 = tu\n### FASE 1 — Adesso\n1. [ ] 👤 **Candidati al Winter Indie Show** con il trailer. · 📅 2026-10-23\n\n## Altro\ntesto\n")
open(os.path.join(L, "TODO.md"), "w", encoding="utf-8").write("# TODO\nAggiornato: 2026-10-01\n\n## Strategia\n- [ ] 👤+🤖 **10 festival di terzi in tema** (party, cozy) e candidature — 2026-11-30 — 3 h — pagina pubblica — ≥ 3 accettati\n")
def deadlines(*extra):
    return subprocess.run([sys.executable, os.path.join(R, "promo_events.py"), "deadlines", "--events", evp, "--launch-dir", L, "--page", "2026-10-31", "--itch", "2026-11-10",
                           "--demo", "2026-12-20", "--launch", "2027-05-13", "--tags", ",".join(tags), "--today", "2026-10-17", "--to", "2027-09-30"] + list(extra),
                          capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
r = deadlines("--dry-run"); assert r.returncode == 0 and "dry run" in r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
assert "Fun Cozy" not in open(os.path.join(L, "calendar.md"), encoding="utf-8").read()
r = deadlines("--replace-todo", "festival di terzi"); assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
cal1 = open(os.path.join(L, "calendar.md"), encoding="utf-8").read(); todo1 = open(os.path.join(L, "TODO.md"), encoding="utf-8").read()
plan_ = ps.parse(cal1)
assert "### 📣 Eventi online e showcase" in cal1 and cal1.index("### 📣 Eventi online") < cal1.index("## Altro")
assert "Candidati a Fun Cozy Fest 2027" in cal1 and cal1.count("Winter Indie Show") == 1                       # hand-written step not duplicated
nums = [s["n"] for s in ps.all_steps(plan_)]; assert len(nums) == len(set(nums)) and nums[0] == 1
assert all(s["due"] for s in ps.all_steps(plan_))
assert "## 📣 Eventi online e showcase (promo_events.py)" in todo1 and "[-] 👤+🤖 **10 festival di terzi" in todo1 and "superata il 2026-10-17" in todo1
t = tt.parse(os.path.join(L, "TODO.md")); assert t["items"] and any(x["dropped"] for x in t["items"])
assert any(x["due_date"] == D(2026, 11, 10) for x in t["items"])
r = deadlines("--replace-todo", "festival di terzi"); assert r.returncode == 0
assert open(os.path.join(L, "calendar.md"), encoding="utf-8").read() == cal1 and open(os.path.join(L, "TODO.md"), encoding="utf-8").read() == todo1   # idempotent
md = open(os.path.join(L, "promo-events.md"), encoding="utf-8").read()
assert "## 1. Fattibili" in md and "## 2. Vale un tentativo" in md and "## 6. Eventi fisici" in md and "PAX Big" in md and "[DA VERIFICARE]" in md
assert md.index("Fun Cozy Fest") < md.index("## 2. Vale un tentativo") < md.index("Wholesome Show")
raw = json.load(open(os.path.join(L, "_raw", "promo_events_deadlines.json"), encoding="utf-8")); assert raw["steps"] and raw["matches"]

# ---- top_moves: the nearest high-value application only
c = [x for x in tm.candidates(L, TODAY, None) if x["source"] == "promo"]
assert len(c) == 1 and c[0]["title"] == "Candidati a Winter Indie Show 2026 entro il 2026-10-23" and c[0]["score"] == 40, c
c2 = [x for x in tm.candidates(L, D(2026, 10, 30), None) if x["source"] == "promo"]
assert len(c2) == 1 and "Fun Cozy" in c2[0]["title"] and c2[0]["score"] == 40
assert not [x for x in tm.candidates(L, D(2027, 6, 1), None) if x["source"] == "promo"]

r = subprocess.run([sys.executable, os.path.join(R, "promo_events.py"), "deadlines", "--events", evp, "--launch-dir", L, "--page", "2026-10-31", "--demo", "2026-12-20",
                    "--launch", "2027-05-13", "--tags", ",".join(tags), "--today", "2026-11-03", "--to", "2027-09-30"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
assert r.returncode == 0 and open(os.path.join(L, "calendar.md"), encoding="utf-8").read().count("Fun Cozy Fest 2027") == 1     # a later run: same ids, nothing new
# ---- list
r = subprocess.run([sys.executable, os.path.join(R, "promo_events.py"), "list", "--events", evp, "--online-only"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
out = r.stdout.decode("utf-8", "replace"); assert r.returncode == 0 and "Fun Cozy" in out and "PAX" not in out
r = subprocess.run([sys.executable, os.path.join(R, "promo_events.py"), "match", "--events", evp, "--launch-dir", L, "--page", "2026-10-31", "--demo", "2026-12-20", "--launch", "2027-05-13",
                    "--tags", "Funny,Cute", "--today", "2026-10-17", "--to", "2027-12-31", "--all"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
assert r.returncode == 0 and "Spooky" in r.stdout.decode("utf-8", "replace") and os.path.exists(os.path.join(L, "_raw", "promo_events_match.json")), r.stderr.decode("utf-8", "replace")
shutil.rmtree(d, ignore_errors=True)
print("ALL PROMO_EVENTS TESTS PASSED")
