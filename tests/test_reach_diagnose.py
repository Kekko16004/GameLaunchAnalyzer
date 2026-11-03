"""Offline tests: WHY a channel is not ready (reach.py diagnose / doctor `why` / import check). Fake runner only: no network, no Agent Reach, no browser.
Covers: a login import that copied cookies but NOT the login cookie is reported as such (and no wasted live check), Agent Reach's own
1-hour rate-limit pause is shown with the minutes left, the error text of the last live check (Reddit's 403 block page, Instagram's 401) becomes a
plain Italian cause, the doctor table and the manual steps carry it, TikTok 'ready' without a login is flagged, and no cookie value is ever printed."""
import os, sys, json, tempfile, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
TMP = tempfile.mkdtemp()
os.environ["GLS_HOME"] = os.path.join(TMP, "home")
os.environ["GLS_REACH_CACHE"] = os.path.join(TMP, "cache")
os.environ.pop("GLS_REACH_FAKE", None)
import common
common.http_get = lambda url, **kw: (_ for _ in ()).throw(AssertionError("network: " + url))
import reach
reach.time.sleep = lambda s: None
reach.PROFILE_WAIT = 0

FX = json.load(open(os.path.join(HERE, "fixtures", "reach_fake.json"), encoding="utf-8"))
CALLS, DYN = [], {}
SECRET = "SECRET-COOKIE-VALUE-123"


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


def ok(result=None):
    return {"schema_version": 1, "ok": True, "action": "x", "result": result, "error": None}


def cookies(**present):
    """What the cookie-name look inside the dedicated browser answers: booleans per channel."""
    return ok({"running": True, "present": present})


def agent_state(cooldowns=None):
    home = reach.rt.state_home()
    os.makedirs(home, exist_ok=True)
    with open(os.path.join(home, "state.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "cooldowns": cooldowns or {}}, f)


def at(minutes_ago):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def reset():
    reach.set_runner(runner)
    reach.configure(cache_dir=os.path.join(TMP, "cache"), cache=True, max_age=24, retries=1, rate=0, mode="auto", manual=None)
    s = reach._state()
    for k in ("source_profile", "cooldown", "diag", "tiktok"):
        s.pop(k, None)
    reach._save_state(s)
    reach._CHANNELS = None; reach._DOCTOR = None
    CALLS.clear(); DYN.clear()
    DYN["browser status"] = {"ok": True, "result": {"running": True, "headless": True}}
    DYN["channels"] = json.loads(json.dumps(FX["channels"]))
    DYN["channels"]["channels"] += [{"name": "linkedin", "level": "optional", "login": {"via": "browser"}, "actions": [
        {"name": "jobs", "params": [{"name": "query", "required": True}], "backends": ["opencli"], "public_web": ["linkedin.com/jobs/view/"]}]}]
    agent_state()


PROFILES = ok({"profiles": [{"id": "ded0", "dedicated": True}, {"id": "abc1", "dedicated": False}]})


def prep_import(**kw):
    reach._save_chosen("abc1")
    DYN["browser profiles"] = PROFILES
    DYN["browser use abc1"] = ok({})
    DYN.update(kw)


# ---- import copied cookies but NOT the login cookie: said plainly, no live check (it would only waste a request)
reset()
prep_import(**{"login linkedin --import-existing": ok({"copied_cookies": 2, "secret": SECRET}), "__logincookies__": cookies(linkedin=False)})
lines = []
rc = reach.login_from_browser("linkedin", out=lines.append)
flat = "\n".join(lines)
assert rc == 1 and "linkedin: copiate 2 voci ma NON il login (manca il cookie `li_at`)" in flat and "LinkedIn" in flat, flat
assert not any(c[:1] == ["check"] for c in CALLS), CALLS
assert SECRET not in flat
print("import without login cookie ok")

# ---- the same import with the login cookie present: copied and checked live, like before
reset()
prep_import(**{"login instagram --import-existing": ok({"copied_cookies": 8}), "__logincookies__": cookies(instagram=True), "doctor": FX["doctor_all_ready"]})
lines = []
reach.login_from_browser("instagram", out=lines.append)
assert "instagram: login copiato (8 voci)" in "\n".join(lines) and ["check", "instagram", "--timeout", "60"] in CALLS
# unknown (browser off / no answer): behaves as before, the live check decides
reset()
prep_import(**{"login instagram --import-existing": ok({"copied_cookies": 8}), "__logincookies__": ok({"running": False, "present": {}}), "doctor": FX["doctor_all_ready"]})
lines = []
reach.login_from_browser("instagram", out=lines.append)
assert "login copiato (8 voci)" in "\n".join(lines) and ["check", "instagram", "--timeout", "60"] in CALLS
# tutti: one channel without login does not stop the others
reset()
prep_import(**{"login twitter --import-existing": ok({"copied_cookies": 5}), "login linkedin --import-existing": ok({"copied_cookies": 2}),
               "__logincookies__": cookies(twitter=True, linkedin=False), "doctor": FX["doctor_all_ready"]})
DYN["channels"] = {"schema_version": 1, "ok": True, "channels": [{"name": n, "level": "x", "login": {"via": "browser"}, "actions": []} for n in ("twitter", "linkedin")]}
lines = []
rc = reach.login_from_browser("tutti", out=lines.append)
flat = "\n".join(lines)
assert "twitter: login copiato (5 voci)" in flat and "linkedin: copiate 2 voci ma NON il login" in flat, flat
assert ["check", "twitter", "--timeout", "60"] in CALLS and ["check", "linkedin", "--timeout", "60"] not in CALLS
print("import with login cookie / unknown / tutti ok")

# ---- login_cookie_state: booleans, unknown when the browser is off, only known channels
reset()
DYN["__logincookies__"] = cookies(instagram=False, reddit=True)
st = reach.login_cookie_state(["instagram", "reddit", "github"])
assert st == {"instagram": False, "reddit": True}, st
DYN["__logincookies__"] = ok({"running": False, "present": {}})
assert reach.login_cookie_state(["instagram"]) == {"instagram": None}
assert reach.login_cookie_state(["github"]) == {}
print("login_cookie_state ok")

# ---- Agent Reach's 1-hour pause: minutes left, nothing after it ends
reset()
agent_state({"instagram": {"code": "RATE_LIMITED", "message": "Platform reported a rate limit", "at": at(10)}})
left = reach.agent_cooldown_left("instagram")
assert 49 * 60 <= left <= 50 * 60 + 5, left
dg = reach.diagnose("instagram", None)
assert "ha rallentato le richieste" in dg["why"] and "49 minuti" in dg["why"] and dg["next"].endswith("login instagram --check"), dg
agent_state({"instagram": {"code": "RATE_LIMITED", "message": "x", "at": at(120)}})
assert reach.agent_cooldown_left("instagram") == 0 and reach.diagnose("instagram", None)["why"] == ""
agent_state({"instagram": {"code": "RATE_LIMITED", "message": "x", "at": "garbage"}})
assert reach.agent_cooldown_left("instagram") == 0
print("cooldown ok")

# ---- the error text of a live check becomes the cause: Reddit's 403 block page (not a login problem), Instagram's 401 with / without the cookie
reset()
reach._note_diag("reddit", {"results": [
    {"channel": "reddit", "action": "search", "passed": False, "error": {"code": "UPSTREAM_BROKEN", "message": "SyntaxError: Unexpected token '<', \"<body clas\"... is not valid JSON"}},
    {"channel": "reddit", "action": "subreddit", "passed": True, "error": None}]})
dg = reach.diagnose("reddit", True)
assert "blocca le richieste" in dg["why"] and "403" in dg["why"] and "web pubblico" in dg["why"] and dg["next"] == "", dg
reach._note_diag("instagram", {"results": [
    {"channel": "instagram", "action": "profile", "passed": False, "error": {"code": "NEED_LOGIN", "message": "Error: HTTP 401 - make sure you are logged in to Instagram\n    at x"}}]})
assert "rifiuta la sessione copiata (risposta 401)" in reach.diagnose("instagram", True)["why"]
assert "manca il cookie di login `sessionid`" in reach.diagnose("instagram", False)["why"]
assert reach.diagnose("instagram", None)["why"] == "" and reach.diagnose("github", None)["why"] == ""
assert "\n" not in json.dumps(reach._state()["diag"]["instagram"]["actions"]["profile"]["msg"].replace("\\n", ""))   # first line only
print("diagnose ok")

# ---- doctor: the table says why, and does not send the owner to reinstall for a block he cannot fix
reset()
DYN["doctor"] = json.loads(json.dumps(FX["doctor"]))
DYN["__logincookies__"] = cookies(twitter=True, reddit=True, instagram=False, tiktok=False)
reach._note_diag("reddit", {"results": [{"channel": "reddit", "action": "search", "passed": False, "error": {"code": "UPSTREAM_BROKEN", "message": "SyntaxError: Unexpected token '<'"}}]})
d = reach.doctor()
rows = {r["channel"]: r for r in d["rows"]}
assert "blocca le richieste" in rows["reddit"]["why"] and rows["reddit"]["next"] == "" and "install" not in rows["reddit"]["next"], rows["reddit"]
assert "`sessionid`" in rows["instagram"]["why"] and rows["instagram"]["next"].endswith("login instagram --dal-mio-browser") and rows["instagram"]["alt"] == "", rows["instagram"]
assert rows["github"]["why"] == "" and rows["github"]["ready"]
md = reach.doctor_md(d)
assert "Perché: Reddit blocca" in md and "Perché: nel browser dedicato manca il cookie" in md
print("doctor why ok")

# ---- TikTok 'ready' (the probe passes on public data) but no login behind it: flagged, still ready
reset()
DYN["doctor"] = FX["doctor"]
reach._note_tiktok(True)
DYN["__logincookies__"] = cookies(tiktok=False, instagram=False, reddit=False)
row = next(r for r in reach.doctor()["rows"] if r["channel"] == "tiktok")
assert row["ready"] and "ATTENZIONE" in row["label"] and "`sessionid`" in row["why"], row
DYN["__logincookies__"] = cookies(tiktok=True)
row = next(r for r in reach.doctor()["rows"] if r["channel"] == "tiktok")
assert "ATTENZIONE" not in row["label"] and row["why"] == ""
print("tiktok flag ok")

# ---- a live check always runs (no stale 'broken'), keeps the reason, and `login --check` prints it
reset()
DYN["doctor"] = FX["doctor"]
DYN["__logincookies__"] = cookies(reddit=True)
DYN["check reddit --timeout 60"] = {"schema_version": 1, "ok": False, "results": [
    {"channel": "reddit", "action": "search", "passed": False, "error": {"code": "UPSTREAM_BROKEN", "message": "SyntaxError: Unexpected token '<', \"<body clas\"... is not valid JSON"}}]}
lines = []
rc = reach.login("reddit", check_only=True, out=lines.append)
flat = "\n".join(lines)
assert rc == 1 and ["check", "reddit", "--timeout", "60"] in CALLS and "Perché: Reddit blocca" in flat, flat
assert reach._state()["diag"]["reddit"]["actions"]["search"]["code"] == "UPSTREAM_BROKEN"
# doctor --live keeps the reason of every channel it checked
reset()
DYN["doctor"] = FX["doctor"]
DYN["check --timeout 60"] = {"schema_version": 1, "ok": False, "results": [
    {"channel": "linkedin", "action": "jobs", "passed": False, "error": {"code": "NEED_LOGIN", "message": "Not logged in to linkedin.com"}}]}
reach.doctor(live=True)
assert reach._state()["diag"]["linkedin"]["actions"]["jobs"] == {"code": "NEED_LOGIN", "msg": "Not logged in to linkedin.com"}
print("live check keeps the reason ok")

# ---- manual steps and not-ready answers carry the cause
reset()
manual = os.path.join(TMP, "manual.md")
reach.configure(manual=manual)
agent_state({"instagram": {"code": "RATE_LIMITED", "message": "x", "at": at(5)}})
DYN["doctor"] = FX["doctor"]
res = reach.search("instagram", "my game")
assert not res["ok"] and "ha rallentato le richieste" in res["error"]["why"], res
txt = open(manual, encoding="utf-8").read()
assert "- Perché: Instagram ha rallentato le richieste" in txt and "instagram.com/explore" in txt, txt
print("manual step why ok")
print("test_reach_diagnose: all ok")
