"""Offline tests of the INTERNAL Agent Reach copy (reach_runtime.py) and of how reach.py runs it: folder lookup order, the private
Python (never a global `agent-reach` on PATH), environment (state folder, embedded mode, browser language), the local patches
(idempotent, LF and CRLF sources, an unknown upstream file left alone), install with a pinned sha256, migration of an old
~/.agent-reach (copy, never move; paths rewritten; global skill links dropped; pip venvs reinstalled). No network, nothing real."""
import hashlib, json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
TMP = tempfile.mkdtemp()
os.environ["GLS_HOME"] = os.path.join(TMP, "gls")
for k in ("GLS_REACH_HOME", "GLS_REACH_FAKE", "GLS_REACH", "REACH_BROWSER_LOCALE"):
    os.environ.pop(k, None)
import reach_runtime as rt
import reach

# ---- lookup order: env -> config.json -> <skill>/tools/agent-reach -> default; real path always
rt.skill_link = lambda: os.path.join(TMP, "skill", "tools", "agent-reach")
assert rt.root() == os.path.realpath(os.path.join(TMP, "gls", "reach")) and rt.source() == "default"
os.makedirs(os.path.join(TMP, "linked"))
os.makedirs(os.path.join(TMP, "skill", "tools"))
try:
    os.symlink(os.path.join(TMP, "linked"), rt.skill_link(), target_is_directory=True)
except OSError:                                  # no symlink right on this Windows account: a junction does the same
    subprocess.run(["cmd", "/c", "mklink", "/J", rt.skill_link(), os.path.join(TMP, "linked")], capture_output=True)
assert rt.source() == "skill" and rt.root() == os.path.realpath(os.path.join(TMP, "linked")), rt.root()
os.makedirs(os.environ["GLS_HOME"], exist_ok=True)
json.dump({"reach": {"path": os.path.join(TMP, "fromconfig")}}, open(os.path.join(os.environ["GLS_HOME"], "config.json"), "w"))
assert rt.source() == "config" and rt.root() == os.path.realpath(os.path.join(TMP, "fromconfig"))
os.environ["GLS_REACH_HOME"] = os.path.join(TMP, "fromenv")
assert rt.source() == "env" and rt.root() == os.path.realpath(os.path.join(TMP, "fromenv"))
print("lookup ok: env > config.json > skill link (resolved) > default")

# ---- never a global agent-reach: a fake one on PATH is ignored, the private Python is used with the private environment
os.environ["GLS_REACH_HOME"] = RT = os.path.join(TMP, "rt")
fakebin = os.path.join(TMP, "bin")
os.makedirs(fakebin)
for name in ("agent-reach", "agent-reach.cmd", "agent-reach.exe"):
    open(os.path.join(fakebin, name), "w").write("echo GLOBAL-CALLED > " + os.path.join(TMP, "global_called.txt") + "\n")
os.environ["PATH"] = fakebin + os.pathsep + os.environ.get("PATH", "")
reach.set_runner(None)
assert not rt.installed() and not reach.enabled()                     # a global agent-reach on PATH does not count
e = reach._exec(["doctor"])
assert e["error"]["code"] == "NOT_INSTALLED" and "reach.py install" in e["error"]["hint"] and not os.path.exists(os.path.join(TMP, "global_called.txt"))
assert not hasattr(reach, "find_bin") and "INSTALL_CMD" not in dir(reach)
os.makedirs(os.path.dirname(rt.python()))
open(rt.python(), "w").write("")
rt._write_info({"version": rt.PIN["version"]})
assert rt.installed() and reach.enabled() and reach.tool_python() == rt.python()
seen = []
real_run = subprocess.run
def fake_run(cmd, *a, **kw):
    seen.append((list(cmd), kw.get("env") or {}))
    return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true, "result": {"version": "1.6.1", "channels": []}}', stderr="")
reach.subprocess.run = fake_run
reach._DOCTOR = None
reach.doctor_raw()
cmd, env = seen[-1]
assert cmd[:5] == [rt.python(), "-X", "utf8", "-m", "agent_reach.cli"] and cmd[5:] == ["doctor"], cmd
assert not any(os.path.basename(str(x)).lower().startswith("agent-reach") for x in cmd)
assert env["AGENT_REACH_HOME"] == os.path.join(rt.root(), "home") and env["AGENT_REACH_EMBEDDED"] and env["PYTHONIOENCODING"] == "utf-8"
assert rt.re.match(rt._LANG_RX, env["REACH_BROWSER_LOCALE"]) and env["REACH_BROWSER_LOCALE"] != "zh-CN" or rt.system_locale().startswith("zh")
reach._exec(["__tiktok__", "profile", "x"])
assert seen[-1][0][0] == rt.python() and seen[-1][1]["AGENT_REACH_HOME"].endswith("home")
reach._login_call("twitter", "it-IT")
assert seen[-1][0][-2:] == ["login", "twitter"] and seen[-1][1]["REACH_BROWSER_LOCALE"] == "it-IT" and seen[-1][0][0] == rt.python()
reach.subprocess.run = real_run
assert not os.path.exists(os.path.join(TMP, "global_called.txt"))
print("private runtime ok: never the global agent-reach, private Python + AGENT_REACH_HOME + embedded + browser language")

# ---- patches on a minimal copy of the upstream files (LF and CRLF), idempotent, unknown file left alone
SRC = {
    "__init__.py": '__version__ = "1.6.1"\n',
    "utils/paths.py": "import os\nfrom pathlib import Path\n\n\ndef home_dir() -> Path:\n    return Path(os.path.expanduser('~'))\n",
    "config.py": 'import os\nfrom pathlib import Path\nfrom agent_reach.utils.paths import (\n    home_dir,\n)\n\n\nclass Config:\n    CONFIG_DIR = home_dir() / ".agent-reach"\n\n    def save(self):\n        if self.config_path == home_dir() / ".agent-reach" / "config.yaml":\n            pass\n',
    "runtime/browser.py": 'from __future__ import annotations\nfrom pathlib import Path\nfrom agent_reach.utils.paths import (\n    home_dir,\n)\n\n\ndef browser_root() -> Path:\n    return home_dir() / ".agent-reach" / "browser"\n',
    "runtime/sessions.py": 'from __future__ import annotations\nfrom agent_reach.utils.paths import ensure_no_symlink_path, home_dir, make_private_dir\n\n\ndef sessions_root():\n    return home_dir() / ".agent-reach" / "sessions"\n',
    "runtime/state.py": 'from __future__ import annotations\nfrom agent_reach.utils.paths import (\n    home_dir,\n)\n\n\ndef root():\n    return home_dir() / ".agent-reach"\n',
    "runtime/browser_watcher.py": 'import os\nimport sys\n\nfrom . import bridge, browser\n\n\ndef _launch_cloak(url, *, headless=True):\n    ctx = launch_persistent_context(\n        str(browser.profile_dir()), headless=headless, locale="zh-CN",\n        args=[],\n    )\n    return ctx\n',
    "channels/youtube.py": 'X = Param("lang", "preferred languages, comma separated", required=False, default="zh-Hans,zh,en,en-orig")\n',
    "runtime/manage.py": 'import os\n\n\ndef place_skill() -> dict:\n    """Write the real copy, link every detected AI, refresh recorded links/copies."""\n    return {}\n\n\ndef update(check_only: bool = False) -> dict:\n    """Upgrade Agent Reach when a release is newer, then upgrade every added channel\'s tools."""\n    return {}\n\n\ndef uninstall(dry_run: bool = False) -> dict:\n    return {}\n',
}


def make_pkg(base, crlf=False):
    pkg = os.path.join(base, "agent_reach")
    for rel, text in SRC.items():
        p = os.path.join(pkg, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
    return pkg


for crlf in (False, True):
    pkg = make_pkg(os.path.join(TMP, "pkg_crlf" if crlf else "pkg_lf"), crlf)
    assert set(rt.patch_status(pkg).values()) == {"missing"}
    res = rt.apply_patches(pkg)
    assert res == {"home": "patched", "locale": "patched", "subs": "patched", "embedded": "patched"}, (crlf, res)
    assert set(rt.patch_status(pkg).values()) == {"ok"}
    snap = {f: open(os.path.join(pkg, *f.split("/")), "rb").read() for f in SRC}
    assert rt.apply_patches(pkg) == {k: "ok" for k in rt.PATCHES}                     # idempotent: nothing rewritten
    assert snap == {f: open(os.path.join(pkg, *f.split("/")), "rb").read() for f in SRC}
    w = open(os.path.join(pkg, "runtime", "browser_watcher.py"), encoding="utf-8", newline="").read()
    assert 'locale="zh-CN"' not in w and "locale=_gls_locale()" in w and ("\r\n" in w) == crlf and ("\n" not in w.replace("\r\n", "")) or not crlf
    for f in SRC:
        if f.endswith(".py"):
            compile(open(os.path.join(pkg, *f.split("/")), encoding="utf-8").read(), f, "exec")
    assert '".agent-reach"' not in open(os.path.join(pkg, "runtime", "state.py"), encoding="utf-8").read()
    assert 'default="en,en-orig,it"' in open(os.path.join(pkg, "channels", "youtube.py"), encoding="utf-8").read()
# the patched helpers really work: state folder from AGENT_REACH_HOME, browser language from REACH_BROWSER_LOCALE / system, never zh-CN
pkg = os.path.join(TMP, "pkg_lf", "agent_reach")
ns = {}
exec(compile(open(os.path.join(pkg, "utils", "paths.py"), encoding="utf-8").read(), "paths", "exec"), ns)
os.environ["AGENT_REACH_HOME"] = os.path.join(TMP, "somewhere")
assert str(ns["reach_home"]()) == os.path.abspath(os.path.join(TMP, "somewhere"))
os.environ.pop("AGENT_REACH_HOME")
assert str(ns["reach_home"]()).endswith(".agent-reach")
wsrc = open(os.path.join(pkg, "runtime", "browser_watcher.py"), encoding="utf-8").read().replace("from . import bridge, browser", "")
ns = {}
exec(compile(wsrc, "watcher", "exec"), ns)
os.environ["REACH_BROWSER_LOCALE"] = "it-IT"
assert ns["_gls_locale"]() == "it-IT"
os.environ["REACH_BROWSER_LOCALE"] = "x; rm -rf /"
assert ns["_gls_locale"]() == rt.system_locale()
os.environ.pop("REACH_BROWSER_LOCALE")
m = open(os.path.join(pkg, "runtime", "manage.py"), encoding="utf-8").read()
assert m.count("GLS-PATCH:embedded") == 3
# an upstream file that changed: the patch is reported, nothing is written
odd = make_pkg(os.path.join(TMP, "pkg_odd"))
open(os.path.join(odd, "runtime", "browser_watcher.py"), "w").write("def nothing():\n    pass\n")
before = open(os.path.join(odd, "runtime", "browser_watcher.py")).read()
res = rt.apply_patches(odd)
assert res["locale"] == "unrecognized" and res["home"] == "patched" and open(os.path.join(odd, "runtime", "browser_watcher.py")).read() == before
print("patches ok: LF and CRLF, idempotent, helpers work, unknown upstream file untouched")

# ---- install: pinned wheel (sha256 checked), uv venv + pip install into the private venv, patches, info file; never PATH
calls = []
WHEEL = b"fake wheel bytes"


def fake_cmd(cmd, environ, timeout, log):
    calls.append(list(cmd))
    if "venv" in cmd:
        os.makedirs(os.path.dirname(rt.python()), exist_ok=True)
        open(rt.python(), "w").write("")
    if "install" in cmd:
        site = os.path.join(rt.venv_dir(), "Lib", "site-packages")
        make_pkg(site)
    return 0, "ok"


os.environ["GLS_REACH_HOME"] = os.path.join(TMP, "rt2")
rt._RUN = fake_cmd
rt._FETCH = lambda url: WHEEL
rt.find_uv = lambda: "uv"
orig_pin = dict(rt.PIN)
rt.PIN["sha256"] = "0" * 64
try:
    rt.install(migrate_from=None, log=lambda s: None)
    raise AssertionError("a wheel with the wrong sha256 must not be installed")
except RuntimeError as e:
    assert "sha256" in str(e)
assert not [c for c in calls if "install" in c] and calls[0][:2] == ["uv", "venv"] and rt.venv_dir() in calls[0]
rt.PIN["sha256"] = hashlib.sha256(WHEEL).hexdigest()
calls.clear()
rep = rt.install(migrate_from=None, log=lambda s: None)
assert rep["installed"] and rep["patches"] == {k: "patched" for k in rt.PATCHES}, rep
assert calls[0][:3] == ["uv", "pip", "install"] and "--python" in calls[0] and rt.python() in calls[0] and calls[0][-1].endswith(".whl")
assert not any("tool" in c for c in calls)                                       # never `uv tool install` (global)
info = rt.read_info()
assert info["version"] == rt.PIN["version"] and info["sha256"] == rt.PIN["sha256"] and set(info["patches"]) == set(rt.PATCHES)
calls.clear()
rep = rt.install(update=True, migrate_from=None, log=lambda s: None)              # second run: nothing to download or install
assert not calls and rep["patches"] == {k: "ok" for k in rt.PATCHES}
c = rt.check()
assert c["installed"] and c["patches_ok"] and c["up_to_date"] and c["source"] == "env"
rt.PIN.update(orig_pin)
print("install ok: sha256 enforced, private venv, idempotent, check")

# ---- migration: COPY of an old ~/.agent-reach, paths rewritten, locks/caches skipped, global skill links dropped, pip venvs reinstalled
old = os.path.join(TMP, "old-agent-reach")
for rel, text in {"state.json": json.dumps({"tools": {"cloakbrowser": {"owner": "agent-reach"}, "bili-cli": {}, "opencli": {"prefix": os.path.join(old, "tools", "npm-global")}},
                                            "owned_paths": {"tools/cloakbrowser": "x", "browser/profile": "y"},
                                            "skill": {"links": [{"agent": "claude-code", "path": "C:/x/.claude/skills/agent-reach"}], "files": {"a": ["b"]}}}),
                  "browser/state.json": json.dumps({"backend": "cloakbrowser", "executable": os.path.join(old, "cloak-binaries", "chromium", "chrome.exe"),
                                                    "launcher_python": os.path.join(old, "tools", "cloakbrowser", "venv", "Scripts", "python.exe"),
                                                    "profile_backup": os.path.join(old, "browser", "profile-before-cloak-1"), "started_at": 1}),
                  "browser/profile/Default/Cookies": "secret-cookie-bytes", "browser/profile/Default/Cache/data_0": "cache",
                  "browser/profile-before-cloak-1/x": "old", "browser/watcher.lock": "", "browser/watcher.log": "log",
                  "browser-locks/a.lock": "", "cache/downloads/big.bin": "x" * 100, "sessions/bili-cli/s.json": "{}",
                  "cloak-binaries/chromium/chrome.exe": "exe", "tools/npm-global/opencli.cmd": "@node %~dp0\\x",
                  "tools/cloakbrowser/venv/Scripts/cloakbrowser.exe": "launcher-with-old-path", "tools/bili-cli/venv/Scripts/bili.exe": "x"}.items():
    p = os.path.join(old, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text)
snapshot = sorted(os.path.relpath(os.path.join(d, f), old) for d, _, fs in os.walk(old) for f in fs)
res = rt.migrate(old, log=lambda s: None)
H = rt.state_home()
assert res["status"] == "copied" and sorted(res["reinstall"]) == ["bili-cli", "cloakbrowser"]
assert sorted(os.path.relpath(os.path.join(d, f), old) for d, _, fs in os.walk(old) for f in fs) == snapshot      # the original is untouched
assert open(os.path.join(H, "browser", "profile", "Default", "Cookies"), encoding="utf-8").read() == "secret-cookie-bytes"
for gone in ("cache", "browser-locks", os.path.join("browser", "watcher.lock"), os.path.join("browser", "watcher.log"),
             os.path.join("browser", "profile", "Default", "Cache"), os.path.join("browser", "profile-before-cloak-1"),
             os.path.join("tools", "cloakbrowser"), os.path.join("tools", "bili-cli")):
    assert not os.path.exists(os.path.join(H, gone)), gone
assert os.path.isfile(os.path.join(H, "tools", "npm-global", "opencli.cmd")) and os.path.isfile(os.path.join(H, "cloak-binaries", "chromium", "chrome.exe"))
st = json.load(open(os.path.join(H, "state.json"), encoding="utf-8"))
assert st["skill"] == {"links": [], "files": {}} and "cloakbrowser" not in st["tools"] and "bili-cli" not in st["tools"] and "tools/cloakbrowser" not in st["owned_paths"]
assert st["tools"]["opencli"]["prefix"] == os.path.join(os.path.abspath(H), "tools", "npm-global")
bs = json.load(open(os.path.join(H, "browser", "state.json"), encoding="utf-8"))
assert bs["executable"] == os.path.join(os.path.abspath(H), "cloak-binaries", "chromium", "chrome.exe") and bs["launcher_python"] is None and "profile_backup" not in bs
assert old not in open(os.path.join(H, "state.json"), encoding="utf-8").read()
assert rt.read_info()["reinstall_tools"] == ["bili-cli", "cloakbrowser"] and rt.read_info()["migrated_from"]["path"] == os.path.abspath(old)
assert rt.migrate(old, log=lambda s: None)["status"] == "skip"                     # once only: a later run never overwrites new logins
# the reinstall runs inside the private Python with the private environment, and is retried until it succeeds
calls.clear()
envs = []
rt._RUN = lambda cmd, environ, timeout, log: (calls.append(list(cmd)) or envs.append(environ) or (0, '{"bili-cli": "ok", "cloakbrowser": "NEED_SETUP: x"}'))
out = rt.repair_tools(["bili-cli", "cloakbrowser"], log=lambda s: None)
assert calls[0][0] == rt.python() and envs[0]["AGENT_REACH_HOME"] == H and rt.read_info()["reinstall_tools"] == ["cloakbrowser"]
rt._RUN = None
print("migration ok: copy only, cookies kept as files, paths rewritten, no global skill links, pip venvs reinstalled privately")

print("ALL REACH RUNTIME TESTS PASSED")
