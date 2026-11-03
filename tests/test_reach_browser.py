"""Offline tests: login copied from the owner's normal browser (reach.py `login <canale|tutti> --dal-mio-browser`, `browser profiles|use`,
`collega-browser`). Fake runner only: no network, no Agent Reach, no browser. Checks the argument mapping to Agent Reach's own commands
(`login <ch> --import-existing`, `browser profiles`, `browser use ID`), that nothing is copied without an explicit profile choice,
the per-channel Italian report, TikTok, the doctor alternatives and that no cookie value can reach the output."""
import os, sys, json, tempfile, io, contextlib
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


def reset():
    reach.set_runner(runner)
    reach.configure(cache_dir=os.path.join(TMP, "cache"), cache=True, max_age=24, retries=1, rate=0, mode="auto", manual=None)
    s = reach._state()
    s.pop("source_profile", None); s.pop("cooldown", None)
    reach._save_state(s)
    reach._CHANNELS = None; reach._DOCTOR = None
    CALLS.clear(); DYN.clear()
    DYN["browser status"] = {"ok": True, "result": {"running": True, "headless": True}}


def ok(result=None):
    return {"schema_version": 1, "ok": True, "action": "x", "result": result, "error": None}


def err(code, msg, hint=""):
    return {"schema_version": 1, "ok": False, "action": "x", "result": None, "error": {"code": code, "message": msg, "hint": hint}}


PROFILES = ok({"profiles": [{"id": "ded0", "dedicated": True}, {"id": "abc1", "dedicated": False}]})
CH = {"schema_version": 1, "ok": True, "channels": [
    {"name": n, "level": "x", "login": {"via": "browser"}, "actions": []} for n in ("twitter", "instagram", "reddit")] + [
    {"name": "bilibili", "level": "x", "login": {"via": "session"}, "actions": []}, {"name": "github", "level": "x", "login": None, "actions": []}]}

# ---- which channels can be copied: browser-login channels + tiktok, never session/no-login ones
reset()
DYN["channels"] = CH
assert reach.import_channels() == ["twitter", "instagram", "reddit", "tiktok"], reach.import_channels()
reset()
DYN["channels"] = {"ok": False, "error": {"code": "X", "message": "no"}}
assert "xueqiu" in reach.import_channels() and reach.import_channels()[-1] == "tiktok"
print("import_channels ok")

# ---- REFUSES without an explicit profile choice, even with exactly one profile connected: nothing is copied, nothing is even started
reset()
DYN["browser profiles"] = PROFILES
lines = []
rc = reach.login_from_browser("twitter", out=lines.append)
flat = "\n".join(lines)
assert rc == 5 and "QUALE profilo" in flat and "browser use ID" in flat and "--profilo ID" in flat, flat
assert not any(c[:1] in (["login"], ["browser"]) for c in CALLS) and not any("import" in " ".join(c) for c in CALLS), CALLS
print("refuses without a chosen profile ok")

# ---- browser profiles: Italian list, dedicated one is not offered, chosen one is marked, hint when none chosen / none connected
reset()
DYN["browser profiles"] = PROFILES
lines = []
assert reach.browser_profiles(out=lines.append) == 0
flat = "\n".join(lines)
assert "ded0: browser dedicato" in flat and "abc1: un TUO profilo" in flat and "SCELTO" not in flat and "Non hai ancora scelto" in flat and "Profile" in flat, flat
reach._save_chosen("abc1"); lines.clear()
reach.browser_profiles(out=lines.append)
assert "abc1: un TUO profilo di Chrome/Edge con l'estensione OpenCLI   <== SCELTO" in "\n".join(lines)
reset()
DYN["browser profiles"] = ok({"profiles": [{"id": "ded0", "dedicated": True}]})
lines = []
assert reach.browser_profiles(out=lines.append) == 1 and "collega-browser" in "\n".join(lines)
print("browser profiles ok")

# ---- browser use ID: maps to Agent Reach's `browser use ID`, saves the choice, rejects bad ids and unknown profiles; starts the bridge if off
reset()
DYN["browser use abc1"] = ok({"source_profile": "abc1", "scope": "requested site only", "source_changed": False})
lines = []
assert reach.browser_use("abc1", out=lines.append) == 0 and ["browser", "use", "abc1"] in CALLS and reach.chosen_profile() == "abc1", lines
assert "abc1" in lines[-1] and "non viene modificato" in lines[-1]
lines.clear(); CALLS.clear()
assert reach.browser_use("a b; rm", out=lines.append) == 2 and reach.browser_use("", out=lines.append) == 2 and not CALLS
DYN["browser use nope"] = err("NEED_SETUP", "Choose a connected local browser profile from browser profiles")
assert reach.browser_use("nope", out=lines.append) == 3 and "non è un tuo browser collegato" in lines[-1] and reach.chosen_profile() == "abc1"
reset()
DYN["browser status"] = {"ok": True, "result": {"running": False}}
DYN["browser setup"] = ok({"running": True}); DYN["browser use abc1"] = ok({})
lines = []
reach.browser_use("abc1", out=lines.append)
assert CALLS.index(["browser", "setup"]) < CALLS.index(["browser", "use", "abc1"]) and "Accendo il browser dedicato" in lines[0]
print("browser use ok")

# ---- login <canale> --dal-mio-browser with a chosen profile: use ID first, then `login <ch> --import-existing`, then the check; says the profile
reset()
reach._save_chosen("abc1")
DYN["browser profiles"] = PROFILES
DYN["browser use abc1"] = ok({"source_profile": "abc1"})
DYN["login twitter --import-existing"] = ok({"source": "abc1", "copied_cookies": 7, "at": "t", "verified": False, "secret": SECRET})
DYN["doctor"] = FX["doctor_all_ready"]
lines = []
rc = reach.login_from_browser("x", out=lines.append)
flat = "\n".join(lines)
assert rc == 0 and "profilo scelto: abc1" in flat and "twitter: login copiato (7 voci)" in flat and "Canale twitter" in flat, flat
assert CALLS.index(["browser", "use", "abc1"]) < CALLS.index(["login", "twitter", "--import-existing"]) < CALLS.index(["check", "twitter", "--timeout", "60"]), CALLS
assert flat.index("profilo scelto") < flat.index("login copiato")
assert SECRET not in flat
print("login --dal-mio-browser ok:", [l for l in lines if "copiato" in l][0])

# ---- --profilo ID: the explicit choice on the command line (no saved choice needed), saved afterwards
reset()
DYN["browser profiles"] = PROFILES
DYN["browser use abc1"] = ok({}); DYN["login reddit --import-existing"] = err("NEED_SETUP", "No local browser login was found for this site; nothing was copied")
lines = []
rc = reach.login_from_browser("reddit", profile="abc1", out=lines.append)
assert rc == 1 and reach.chosen_profile() == "abc1" and "nessun login trovato in quel profilo" in "\n".join(lines), lines
assert reach.login_from_browser("reddit", profile="a;b", out=lines.append) == 2
print("--profilo ok")

# ---- chosen profile not connected now: no copy, tells which ones are connected; no extension at all: points at collega-browser
reset()
reach._save_chosen("old9")
DYN["browser profiles"] = PROFILES
lines = []
assert reach.login_from_browser("twitter", out=lines.append) == 4 and "old9" in "\n".join(lines) and "abc1" in "\n".join(lines)
assert not any(c[:1] == ["login"] or c[:2] == ["browser", "use"] for c in CALLS), CALLS
reset()
reach._save_chosen("abc1")
DYN["browser profiles"] = ok({"profiles": [{"id": "ded0", "dedicated": True}]})
lines = []
assert reach.login_from_browser("twitter", out=lines.append) == 4 and "collega-browser" in "\n".join(lines)
print("not connected ok")

# ---- tutti: every importable channel, one Italian line each (copiato / nessun login / errore), tiktok through its own import, only copied ones checked
reset()
reach._save_chosen("abc1")
DYN["channels"] = CH
DYN["browser profiles"] = PROFILES
DYN["browser use abc1"] = ok({})
DYN["login twitter --import-existing"] = ok({"copied_cookies": 5})
DYN["login instagram --import-existing"] = err("NEED_SETUP", "No local browser login was found for this site; nothing was copied", "Run agent-reach browser profiles")
DYN["login reddit --import-existing"] = err("UPSTREAM_BROKEN", "Could not apply the local site session; saved state retained")
DYN["__tiktok_import__"] = ok({"source": "abc1", "copied_cookies": 3})
DYN["doctor"] = FX["doctor_all_ready"]
lines = []
rc = reach.login_from_browser("tutti", out=lines.append)
flat = "\n".join(lines)
assert "twitter: login copiato (5 voci)" in flat and "instagram: nessun login trovato" in flat and "reddit: errore [UPSTREAM_BROKEN]" in flat and "tiktok: login copiato (3 voci)" in flat, flat
assert ["__tiktok_import__"] in CALLS and ["check", "twitter", "--timeout", "60"] in CALLS and ["check", "instagram", "--timeout", "60"] not in CALLS
assert not any(c[:2] == ["login", "bilibili"] for c in CALLS) and "profilo scelto: abc1" in flat
# several browsers have a login for the site: tells to choose
reset()
reach._save_chosen("abc1")
DYN["browser profiles"] = PROFILES; DYN["browser use abc1"] = ok({})
DYN["login twitter --import-existing"] = err("NEED_SETUP", "Several local browsers have cookies for this site; choose which account to reuse")
lines = []
reach.login_from_browser("twitter", out=lines.append)
assert "twitter: più browser hanno un login" in "\n".join(lines) and "browser use ID" in "\n".join(lines)
print("tutti ok")

# ---- channels without a copyable login are explained, not run
reset()
reach._save_chosen("abc1")
lines = []
assert reach.login_from_browser("bilibili", out=lines.append) == 2 and "QR" in lines[-1]
assert reach.login_from_browser("github", out=lines.append) == 2 and "non ha un login da copiare" in lines[-1]
assert not any(c[:1] == ["login"] for c in CALLS)
print("unsupported channels ok")

# ---- CLI argument rules
reset()
def cli(*argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = reach.main(list(argv))
    return rc, buf.getvalue()
rc, o = cli("login", "tutti"); assert rc == 2 and "--dal-mio-browser" in o
rc, o = cli("login", "twitter", "--profilo", "abc1"); assert rc == 2 and "--dal-mio-browser" in o
rc, o = cli("browser", "status", "abc1"); assert rc == 2
rc, o = cli("browser", "use"); assert rc == 2 and "ID" in o
rc, o = cli("login", "twitter", "--dal-mio-browser"); assert rc == 5 and "QUALE profilo" in o      # nothing chosen yet
rc, o = cli("collega-browser"); assert rc == 0 and "OBBLIGATORIO" in o and "browser use ID" in o and "--dal-mio-browser" in o
assert reach.EXTENSION_STORE in o and "chrome://extensions" in o
assert "SOLO in quel profilo" in o and "puzzle" in o
reset()
DYN["browser use abc1"] = ok({}); DYN["browser profiles"] = PROFILES
rc, o = cli("browser", "use", "abc1"); assert rc == 0 and reach.chosen_profile() == "abc1"
rc, o = cli("browser", "profiles"); assert rc == 0 and "SCELTO" in o
print("cli ok")

# ---- the extension folder text is built from the real path when the manifest exists
ext = os.path.join(TMP, "reachhome")
os.makedirs(os.path.join(ext, "browser", "extension"))
open(os.path.join(ext, "browser", "extension", "manifest.json"), "w").write("{}")
orig = reach.rt.state_home
reach.rt.state_home = lambda r=None: ext
t = reach.connect_browser_text()
assert os.path.join(ext, "browser", "extension") in t and "Non spostarla" in t
reach.rt.state_home = lambda r=None: os.path.join(TMP, "nothing")
assert "non c'è ancora" in reach.connect_browser_text()
reach.rt.state_home = orig
print("collega-browser text ok")

# ---- doctor and hints offer the alternative for every login channel that is not ready; ready ones and no-login ones do not
reset()
DYN["channels"] = CH
d = reach.doctor()
rows = {r["channel"]: r for r in d["rows"]}
assert "--dal-mio-browser" in rows["twitter"]["alt"] and "reach.py login twitter --dal-mio-browser" in rows["twitter"]["alt"], rows["twitter"]
assert "--dal-mio-browser" in rows["tiktok"]["alt"] and rows["twitter"]["next"] == "! " + reach.login_cmd("twitter")
assert rows["youtube"]["alt"] == "" and rows["youtube"]["ready"]
md = reach.doctor_md(d)
assert "--dal-mio-browser" in md and "collega-browser" in md
for code in ("NEED_LOGIN", "NOT_READY"):
    h = reach.hint_it(code, "instagram")
    assert "login instagram --dal-mio-browser" in h and "agent-reach login" not in h, h
print("doctor hints ok")
print("test_reach_browser: all ok")
