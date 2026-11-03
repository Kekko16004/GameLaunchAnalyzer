#!/usr/bin/env python3
"""The skill's INTERNAL copy of Agent Reach (https://github.com/Panniantong/agent-reach, MIT): where it lives, how it is built,
patched, checked and migrated. Stdlib only. The owner never runs `agent-reach` himself: reach.py and the installer use this module.

Layout (one folder, owned by the skill, outside the skill copy so updates of the skill never touch logins):
  ~/.game-launch-strategist/reach/            R (GLS_HOME changes the base)
    venv/                                     private Python with Agent Reach <PIN version> and its dependencies
    home/                                     Agent Reach state (AGENT_REACH_HOME): browser profile, logins, sessions, config.yaml,
                                              its tools (OpenCLI, CloakBrowser, bili-cli) and the CloakBrowser Chromium
    runtime.json                              pinned version, wheel sha256, patches applied, migration record
  <skill>/tools/agent-reach  ->  R           link created by the installer (like designer's styles link), so it is "inside" the skill

Where R is looked up (first hit wins, never a global `agent-reach` on PATH):
  env GLS_REACH_HOME -> ~/.game-launch-strategist/config.json {"reach": {"path": ...}} -> <skill>/tools/agent-reach -> the default above.
The real path (links resolved) is always used: Agent Reach refuses state paths that pass through a link.

Local patches (applied after every install/update, idempotent, checked by `check`): see PATCHES. All marked `GLS-PATCH:<id>`.

  python reach_runtime.py install [--update] [--no-migrate] [--json]   build or refresh the private copy (wheel pinned by sha256)
  python reach_runtime.py check [--json]                                installed? version? every patch in place?
  python reach_runtime.py patch                                         re-apply the patches
  python reach_runtime.py migrate [--from ~/.agent-reach]              COPY an old global setup (profile, logins, state) into home/
  python reach_runtime.py where                                         the folder in use
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(os.path.dirname(HERE))

PIN = dict(version="1.6.1", repo="https://github.com/Panniantong/agent-reach", license="MIT",
           wheel="https://github.com/Panniantong/Agent-Reach/releases/download/v1.6.1/agent_reach-1.6.1-py3-none-any.whl",
           sha256="6a1085cae53118c5f1271ab24041e55ec17c509932612b919208f04d10183acb")
PY_WANT = "3.12"            # uv downloads it if missing; the fallback venv needs a local Python >= 3.10
MARK = "GLS-PATCH"
_LANG_RX = r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$"
_RUN = None                 # tests: fn(argv, env, timeout, log) -> (code, output)
_FETCH = None               # tests: fn(url) -> bytes


def _gls_home() -> str:
    return os.environ.get("GLS_HOME") or os.path.join(os.path.expanduser("~"), ".game-launch-strategist")


def default_root() -> str:
    return os.path.join(_gls_home(), "reach")


def skill_link() -> str:
    return os.path.join(SKILL_DIR, "tools", "agent-reach")


def _config_path() -> str | None:
    try:
        with open(os.path.join(_gls_home(), "config.json"), encoding="utf-8") as fh:
            p = ((json.load(fh) or {}).get("reach") or {}).get("path")
        return os.path.expanduser(p) if p else None
    except (OSError, ValueError, AttributeError):
        return None


def root() -> str:
    """The runtime folder in use (real path, links resolved). See the module docstring for the search order."""
    for cand, must_exist in ((os.environ.get("GLS_REACH_HOME"), False), (_config_path(), False), (skill_link(), True)):
        if cand and (not must_exist or os.path.exists(cand)):
            return os.path.realpath(cand)
    return os.path.realpath(default_root())


def source() -> str:
    """Which rule picked root(): env | config | skill | default."""
    if os.environ.get("GLS_REACH_HOME"):
        return "env"
    if _config_path():
        return "config"
    return "skill" if os.path.exists(skill_link()) else "default"


def state_home(r: str | None = None) -> str:
    return os.path.join(r or root(), "home")


def venv_dir(r: str | None = None) -> str:
    return os.path.join(r or root(), "venv")


def python(r: str | None = None) -> str:
    v = venv_dir(r)
    return os.path.join(v, "Scripts", "python.exe") if os.name == "nt" else os.path.join(v, "bin", "python")


def info_path(r: str | None = None) -> str:
    return os.path.join(r or root(), "runtime.json")


def read_info(r: str | None = None) -> dict:
    try:
        with open(info_path(r), encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


def _write_info(d: dict, r: str | None = None):
    os.makedirs(r or root(), exist_ok=True)
    tmp = info_path(r) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, info_path(r))


def installed(r: str | None = None) -> bool:
    """The private Python exists and runtime.json says which version is in it."""
    return os.path.isfile(python(r)) and bool(read_info(r).get("version"))


def system_locale() -> str:
    """This machine's language as a BCP 47 tag (it-IT); en-US when it cannot be read."""
    v = ""
    try:
        if os.name == "nt":
            import ctypes
            buf = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
                v = buf.value
        else:
            v = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").split(".")[0].replace("_", "-")
    except Exception:  # noqa: BLE001
        v = ""
    return v if re.match(_LANG_RX, v or "") else "en-US"


def env(lang: str | None = None, r: str | None = None) -> dict:
    """Environment of every Agent Reach process: private state folder, embedded mode, browser language, UTF-8."""
    e = dict(os.environ)
    for k in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        e.pop(k, None)
    lang = lang if lang and re.match(_LANG_RX, lang) else (os.environ.get("REACH_BROWSER_LOCALE") or "")
    e.update(AGENT_REACH_HOME=state_home(r), AGENT_REACH_EMBEDDED="game-launch-strategist", AGENT_REACH_LANG="en",
             REACH_BROWSER_LOCALE=lang if re.match(_LANG_RX, lang) else system_locale(), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return e


def argv(args: list[str], r: str | None = None) -> list[str]:
    """Command line of one Agent Reach command: the private Python, never a program found on PATH."""
    return [python(r), "-X", "utf8", "-m", "agent_reach.cli", *[str(a) for a in args]]


# ---------------------------------------------------------------- patches (applied to the installed package, idempotent)
_HOME_EXPR = 'home_dir() / ".agent-reach"'
_HOME_IMPORT = "from agent_reach.utils import paths as _gls_paths  # GLS-PATCH:home\n"
_HOME_FUNC = '''

# GLS-PATCH:home  (game-launch-strategist: the state folder can be moved with AGENT_REACH_HOME)
def reach_home() -> Path:
    """Agent Reach's state folder: AGENT_REACH_HOME when set (embedded copy), else ~/.agent-reach."""
    explicit = os.environ.get("AGENT_REACH_HOME")
    if explicit:
        return Path(os.path.abspath(explicit))
    return home_dir() / ".agent-reach"
'''
_LOCALE_FUNC = '''

# GLS-PATCH:locale  (game-launch-strategist: the browser opens in the owner's language, never a fixed one)
def _gls_locale() -> str:
    import re as _re
    rx = r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$"
    v = (os.environ.get("REACH_BROWSER_LOCALE") or "").strip()
    if not _re.match(rx, v):
        v = ""
        try:
            if sys.platform == "win32":
                import ctypes
                buf = ctypes.create_unicode_buffer(85)
                if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
                    v = buf.value
            else:
                v = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").split(".")[0].replace("_", "-")
        except Exception:
            v = ""
    return v if _re.match(rx, v or "") else "en-US"
'''
_EMBED_SKILL = ('    if os.environ.get("AGENT_REACH_EMBEDDED"):  # GLS-PATCH:embedded (no global skill, no links in other AIs)\n'
                '        return {"path": "", "installed": False, "agents": [], "links": [], "copies": [], "not_linked": [],\n'
                '                "removed_old_copies": [], "embedded": True}\n')
_EMBED_UPDATE = ('    if os.environ.get("AGENT_REACH_EMBEDDED") and not check_only:  # GLS-PATCH:embedded\n'
                 '        raise ReachError(BAD_INPUT, "this copy belongs to game-launch-strategist: its installer updates it",\n'
                 '                         hint="node installer/install.mjs update")\n')
_EMBED_UNINSTALL = ('    if os.environ.get("AGENT_REACH_EMBEDDED"):  # GLS-PATCH:embedded\n'
                    '        raise ReachError(BAD_INPUT, "this copy belongs to game-launch-strategist: remove it with the skill",\n'
                    '                         hint="node installer/install.mjs uninstall")\n')


def _p_home(pkg: str) -> list[tuple[str, str, str]]:
    """[(relative file, old text, new text)] ; computed per file because the import goes before an existing line."""
    out = []
    p = os.path.join(pkg, "utils", "paths.py")
    t = _read(p)
    if t is not None and "def home_dir() -> Path:" in t:
        out.append(("utils/paths.py", t, t.rstrip("\r\n") + _nl(t, "\n" + _HOME_FUNC)))
    for rel in ("config.py", "runtime/browser.py", "runtime/sessions.py", "runtime/state.py"):
        t = _read(os.path.join(pkg, *rel.split("/")))
        anchor = "from agent_reach.utils.paths import"
        if t is None or _HOME_EXPR not in t or anchor not in t:
            out.append((rel, None, None))
            continue
        i = t.index(anchor)
        new = t[:i] + _nl(t, _HOME_IMPORT) + t[i:]
        out.append((rel, t, new.replace(_HOME_EXPR, "_gls_paths.reach_home()")))
    return out


def _nl(t: str | None, s: str) -> str:
    """s with the file's own line endings (a source checked out on Windows may use CRLF)."""
    return s.replace("\n", "\r\n") if t and "\r\n" in t else s


def _sub_once(t: str | None, old: str, new: str) -> str | None:
    old, new = _nl(t, old), _nl(t, new)
    return t.replace(old, new, 1) if t is not None and t.count(old) == 1 else None


def _p_locale(pkg: str):
    t = _read(os.path.join(pkg, "runtime", "browser_watcher.py"))
    anchor = "from . import bridge, browser\n"
    n = _sub_once(t, 'locale="zh-CN"', "locale=_gls_locale()")
    n = _sub_once(n, anchor, anchor + _LOCALE_FUNC) if n else None
    return [("runtime/browser_watcher.py", t, n)]


def _p_subs(pkg: str):
    t = _read(os.path.join(pkg, "channels", "youtube.py"))
    return [("channels/youtube.py", t, _sub_once(t, 'default="zh-Hans,zh,en,en-orig"', 'default="en,en-orig,it"'))]


def _p_embedded(pkg: str):
    t = _read(os.path.join(pkg, "runtime", "manage.py"))
    n = _sub_once(t, '    """Write the real copy, link every detected AI, refresh recorded links/copies."""\n',
                  '    """Write the real copy, link every detected AI, refresh recorded links/copies."""\n' + _EMBED_SKILL)
    n = _sub_once(n, '    """Upgrade Agent Reach when a release is newer, then upgrade every added channel\'s tools."""\n',
                  '    """Upgrade Agent Reach when a release is newer, then upgrade every added channel\'s tools."""\n' + _EMBED_UPDATE) if n else None
    n = _sub_once(n, "def uninstall(dry_run: bool = False) -> dict:\n", "def uninstall(dry_run: bool = False) -> dict:\n" + _EMBED_UNINSTALL) if n else None
    return [("runtime/manage.py", t, n)]


# id -> (what it does, builder). The subs patch sits inside a call's arguments, so its "mark" is the new default value itself.
PATCHES = {
    "home": ("state folder from AGENT_REACH_HOME (the skill's private folder, not ~/.agent-reach)", _p_home),
    "locale": ("dedicated browser language from REACH_BROWSER_LOCALE or the system language (upstream: fixed zh-CN)", _p_locale),
    "subs": ("YouTube subtitles: English first, then Italian (upstream: Chinese first)", _p_subs),
    "embedded": ("no global skill/links, no self-update or self-uninstall: the skill installer owns this copy", _p_embedded),
}
_DONE = {"home": ("utils/paths.py", "GLS-PATCH:home"), "locale": ("runtime/browser_watcher.py", "GLS-PATCH:locale"),
         "subs": ("channels/youtube.py", 'default="en,en-orig,it"'), "embedded": ("runtime/manage.py", "GLS-PATCH:embedded")}


def _read(p: str) -> str | None:
    try:
        with open(p, encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError:
        return None


def _write(p: str, t: str):
    tmp = p + ".gls-tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(t)
    os.replace(tmp, p)


def patch_status(pkg: str) -> dict:
    """{id: 'ok' | 'missing'} : a patch is ok when its mark is in the installed file."""
    out = {}
    for pid, (rel, mark) in _DONE.items():
        t = _read(os.path.join(pkg, *rel.split("/")))
        ok = t is not None and mark in t
        if pid == "home":       # every file must use the moved folder
            ok = ok and all(_HOME_EXPR not in (_read(os.path.join(pkg, *f.split("/"))) or _HOME_EXPR)
                            for f in ("config.py", "runtime/browser.py", "runtime/sessions.py", "runtime/state.py"))
        if pid == "locale":
            ok = ok and 'locale="zh-CN"' not in (t or "")
        out[pid] = "ok" if ok else "missing"
    return out


def apply_patches(pkg: str) -> dict:
    """Apply every patch not yet in place. {id: patched | ok | unrecognized}. Nothing is written for an unrecognized patch."""
    before = patch_status(pkg)
    res = {}
    for pid, (_, build) in PATCHES.items():
        if before.get(pid) == "ok":
            res[pid] = "ok"
            continue
        edits = build(pkg)
        if not edits or any(new is None for _, _, new in edits):
            res[pid] = "unrecognized"
            continue
        for rel, _, new in edits:
            _write(os.path.join(pkg, *rel.split("/")), new)
        res[pid] = "patched"
    after = patch_status(pkg)
    for pid in res:
        if res[pid] == "patched" and after.get(pid) != "ok":
            res[pid] = "unrecognized"
    return res


def package_dir(r: str | None = None) -> str | None:
    """agent_reach folder inside the private venv (found on disk, nothing imported)."""
    v = venv_dir(r)
    cands = [os.path.join(v, "Lib", "site-packages", "agent_reach")]
    lib = os.path.join(v, "lib")
    if os.path.isdir(lib):
        cands += [os.path.join(lib, d, "site-packages", "agent_reach") for d in sorted(os.listdir(lib)) if d.startswith("python")]
    return next((c for c in cands if os.path.isfile(os.path.join(c, "__init__.py"))), None)


def package_version(pkg: str | None) -> str | None:
    t = _read(os.path.join(pkg, "__init__.py")) if pkg else None
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)', t or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- building the private copy
def _run(cmd: list[str], log, timeout: float = 1800, environ: dict | None = None) -> tuple[int, str]:
    if _RUN:
        return _RUN(cmd, environ, timeout, log)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           cwd=os.path.expanduser("~"), env=environ)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"{e.__class__.__name__}: {e}"
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def find_uv() -> str | None:
    w = shutil.which("uv")
    if w:
        return w
    c = os.path.join(os.path.expanduser("~"), ".local", "bin", "uv.exe" if os.name == "nt" else "uv")
    return c if os.path.isfile(c) else None


def _fetch(url: str) -> bytes:
    if _FETCH:
        return _FETCH(url)
    req = urllib.request.Request(url, headers={"User-Agent": "game-launch-strategist"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def _wheel(r: str, log) -> str:
    """The pinned wheel, downloaded once into R/cache and checked against its sha256 (a mismatch is never installed)."""
    d = os.path.join(r, "cache")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, PIN["wheel"].rsplit("/", 1)[-1])
    if os.path.isfile(p) and hashlib.sha256(open(p, "rb").read()).hexdigest() == PIN["sha256"]:
        return p
    log(f"scarico Agent Reach {PIN['version']} (release GitHub)...")
    data = _fetch(PIN["wheel"])
    got = hashlib.sha256(data).hexdigest()
    if got != PIN["sha256"]:
        raise RuntimeError(f"il file scaricato non corrisponde (sha256 {got[:12]}..., atteso {PIN['sha256'][:12]}...): non lo installo")
    with open(p, "wb") as fh:
        fh.write(data)
    return p


def _base_python() -> str | None:
    """A local Python >= 3.10 for the fallback venv (when uv is missing)."""
    for c in ([sys.executable] if sys.version_info >= (3, 10) else []) + [shutil.which(x) for x in ("python3", "python", "py")]:
        if not c:
            continue
        code, out = _run([c, "-c", "import sys; print(sys.version_info >= (3, 10))"], lambda *_: None, 60)
        if code == 0 and out.strip().endswith("True"):
            return c
    return None


def install(update: bool = False, migrate_from: str | None = "auto", log=print) -> dict:
    """Build (or refresh) the private copy: venv, pinned wheel, patches, migration of an old global setup. Never touches PATH."""
    r = root()
    os.makedirs(r, exist_ok=True)
    os.makedirs(state_home(r), exist_ok=True)
    rep = dict(root=r, version=PIN["version"], steps=[])
    info = read_info(r)
    py = python(r)
    pkg = package_dir(r)
    have = package_version(pkg)
    uv = find_uv()
    if not os.path.isfile(py):
        log(f"creo l'ambiente Python privato in {venv_dir(r)}")
        if uv:
            code, out = _run([uv, "venv", "--python", PY_WANT, venv_dir(r)], log, 900)
        else:
            base = _base_python()
            if not base:
                raise RuntimeError("serve Python 3.10+ oppure uv per creare l'ambiente di Agent Reach")
            code, out = _run([base, "-m", "venv", venv_dir(r)], log, 900)
        if code != 0 or not os.path.isfile(py):
            raise RuntimeError("ambiente Python non creato: " + out.strip()[-300:])
        rep["steps"].append("venv")
    if have != PIN["version"] or not info.get("version"):
        wheel = _wheel(r, log)
        log(f"installo Agent Reach {PIN['version']} nell'ambiente privato" + (f" (era {have})" if have else ""))
        cmd = ([uv, "pip", "install", "--python", py, wheel] if uv else [py, "-m", "pip", "install", "--disable-pip-version-check", wheel])
        code, out = _run(cmd, log, 1800)
        if code != 0:
            raise RuntimeError("installazione non riuscita: " + out.strip()[-400:])
        pkg = package_dir(r)
        have = package_version(pkg)
        if have != PIN["version"]:
            raise RuntimeError(f"dopo l'installazione trovo la versione {have}, attesa {PIN['version']}")
        rep["steps"].append("wheel")
    elif update:
        rep["steps"].append("già alla versione fissata")
    patches = apply_patches(pkg)
    rep["patches"] = patches
    bad = [k for k, v in patches.items() if v == "unrecognized"]
    if bad:
        log("ATTENZIONE: correzioni non applicate (file di Agent Reach diverso dal previsto): " + ", ".join(bad))
    info.update(version=PIN["version"], wheel=PIN["wheel"], sha256=PIN["sha256"], python=py, patches=patches,
                updated_at=dt.datetime.now().isoformat(timespec="seconds"), layout=1)
    info.setdefault("installed_at", info["updated_at"])
    _write_info(info, r)
    if migrate_from:
        src = os.path.join(os.path.expanduser("~"), ".agent-reach") if migrate_from == "auto" else migrate_from
        if os.path.isdir(src) and not os.path.isfile(os.path.join(state_home(r), "state.json")):
            rep["migration"] = migrate(src, r, log=log)
    pending = read_info(r).get("reinstall_tools") or []
    if pending:
        rep["repair"] = repair_tools(pending, r, log=log)
    rep["installed"] = installed(r)
    return rep


# Reinstall, with Agent Reach's own code and inside the private folder, the tools whose venvs were not copied by the migration.
_REPAIR = r'''
import json, sys
from agent_reach.runtime import browser, tools
out = {}
for name in json.loads(sys.argv[1]):
    try:
        if name == "cloakbrowser":
            browser.ensure_chrome(retry_cloak=True)       # private CloakBrowser venv + launcher; the Chromium copy is reused
        else:
            tools.ensure(name)
        out[name] = "ok"
    except Exception as e:
        out[name] = type(e).__name__ + ": " + str(getattr(e, "message", e))[:200]
print(json.dumps(out))
'''


def repair_tools(names: list[str], r: str | None = None, log=print) -> dict:
    r = r or root()
    log("reinstallo nella cartella privata: " + ", ".join(names))
    code, out = _run([python(r), "-X", "utf8", "-c", _REPAIR, json.dumps(names)], log, 1800, env(None, r))
    res = {}
    for line in reversed((out or "").strip().splitlines()):
        if line.strip().startswith("{"):
            try:
                res = json.loads(line)
            except ValueError:
                pass
            break
    left = [n for n in names if res.get(n) != "ok"]
    info = read_info(r)
    info["reinstall_tools"] = left
    _write_info(info, r)
    if left:
        log("da riprovare al prossimo aggiornamento: " + ", ".join(f"{n} ({res.get(n, 'nessuna risposta')})" for n in left))
    return res


# ---------------------------------------------------------------- migration of an old global setup (copy, never move)
_SKIP_TOP = {"cache", "browser-locks", "update-check.json"}
_SKIP_ANY = {"Cache", "Code Cache", "GPUCache", "GrShaderCache", "ShaderCache", "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
             "Crashpad", "__pycache__"}
_SKIP_FILE = re.compile(r"(\.lock|^watcher\.log|^SingletonLock|^SingletonCookie|^SingletonSocket|^lockfile)$", re.I)
PIP_TOOLS = {"cloakbrowser": "cloakbrowser", "bili-cli": "bilibili-cli"}    # private venvs: their launchers hold absolute paths


def _copy_tree(src: str, dst: str, skip_top: set) -> int:
    n = 0
    for cur, dirs, files in os.walk(src):
        rel = os.path.relpath(cur, src)
        top = rel.split(os.sep)[0] if rel != "." else ""
        dirs[:] = [d for d in dirs if d not in _SKIP_ANY and not (rel == "." and d in skip_top)
                   and not d.startswith("profile-before-cloak")]
        if rel != "." and top in skip_top:
            continue
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            if (rel == "." and f in skip_top) or _SKIP_FILE.search(f):
                continue
            try:
                shutil.copy2(os.path.join(cur, f), os.path.join(dst, rel, f))
                n += 1
            except OSError:
                pass
    return n


def _repath(text: str, old: str, new: str) -> str:
    """Rewrite absolute paths of the old folder inside a JSON text (plain, JSON-escaped and forward-slash forms)."""
    for o, nw in ((old, new), (json.dumps(old)[1:-1], json.dumps(new)[1:-1]), (old.replace("\\", "/"), new.replace("\\", "/"))):
        if o:
            text = text.replace(o, nw)
    return text


def migrate(src: str, r: str | None = None, log=print) -> dict:
    """Copy an old ~/.agent-reach into the private state folder: browser profile (logins), sessions, state, config, OpenCLI and the
    CloakBrowser Chromium. The old folder is left untouched (backup). Private pip venvs are not copied (their launchers point to the
    old folder): they are reinstalled by Agent Reach itself on first use or by `install`. Cookies are copied as files, never read."""
    r = r or root()
    dst = state_home(r)
    if os.path.isfile(os.path.join(dst, "state.json")):
        return dict(status="skip", reason="già migrato", src=src, dst=dst)
    if not os.path.isdir(src):
        return dict(status="skip", reason="nessuna installazione precedente", src=src, dst=dst)
    log(f"copio la configurazione esistente di Agent Reach da {src} (l'originale resta com'è)")
    skip_top = set(_SKIP_TOP) | {os.path.join("tools", t) for t in PIP_TOOLS}
    n = 0
    for e in sorted(os.listdir(src)):
        s = os.path.join(src, e)
        if e in _SKIP_TOP:
            continue
        if e == "tools" and os.path.isdir(s):
            os.makedirs(os.path.join(dst, "tools"), exist_ok=True)
            for t in sorted(os.listdir(s)):
                if t in PIP_TOOLS:
                    continue
                st = os.path.join(s, t)
                n += _copy_tree(st, os.path.join(dst, "tools", t), set()) if os.path.isdir(st) else int(bool(shutil.copy2(st, os.path.join(dst, "tools", t))))
        elif os.path.isdir(s):
            n += _copy_tree(s, os.path.join(dst, e), set())
        elif not _SKIP_FILE.search(e):
            shutil.copy2(s, os.path.join(dst, e))
            n += 1
    old, new = os.path.abspath(src), os.path.abspath(dst)
    fixed = []
    reinstall = []
    try:
        with open(os.path.join(src, "state.json"), encoding="utf-8") as fh:
            old_tools = (json.load(fh) or {}).get("tools") or {}
        reinstall = [t for t in PIP_TOOLS if t in old_tools]
    except (OSError, ValueError):
        pass
    for rel in ("state.json", os.path.join("browser", "state.json")):
        p = os.path.join(dst, rel)
        t = _read(p)
        if t is None:
            continue
        t2 = _repath(t, old, new)
        if rel == "state.json":
            try:
                d = json.loads(t2)
                d["skill"] = {"links": [], "files": {}}                     # the embedded copy never manages global skills
                for tname in PIP_TOOLS:
                    (d.get("tools") or {}).pop(tname, None)                  # reinstalled privately on first use
                    (d.get("owned_paths") or {}).pop(f"tools/{tname}", None)
                t2 = json.dumps(d, ensure_ascii=False, indent=1)
            except ValueError:
                pass
        if rel == os.path.join("browser", "state.json"):
            try:
                d = json.loads(t2)
                lp = d.get("launcher_python") or ""
                if any(f"tools{os.sep}{tname}" in lp or f"tools/{tname}" in lp for tname in PIP_TOOLS):
                    d["launcher_python"] = None                               # re-detected by `browser setup` on first use
                d.pop("profile_backup", None)
                for k in ("started_at", "running_backend", "headless"):
                    d.pop(k, None)
                t2 = json.dumps(d, ensure_ascii=False, indent=1)
            except ValueError:
                pass
        if t2 != t:
            _write(p, t2)
            fixed.append(rel.replace("\\", "/"))
    info = read_info(r)
    info["migrated_from"] = dict(path=old, at=dt.datetime.now().isoformat(timespec="seconds"), files=n)
    info["reinstall_tools"] = sorted(set(info.get("reinstall_tools") or []) | set(reinstall))
    _write_info(info, r)
    log(f"copiati {n} file; percorsi aggiornati in: {', '.join(fixed) or '-'}")
    return dict(status="copied", src=old, dst=new, files=n, rewritten=fixed, reinstall=reinstall)


# ---------------------------------------------------------------- check
def check() -> dict:
    r = root()
    pkg = package_dir(r)
    info = read_info(r)
    st = patch_status(pkg) if pkg else {k: "missing" for k in PATCHES}
    ver = package_version(pkg)
    return dict(root=r, source=source(), link=skill_link(), link_ok=os.path.exists(skill_link()) and os.path.realpath(skill_link()) == r,
                installed=installed(r), python=python(r) if os.path.isfile(python(r)) else None, version=ver, pinned=PIN["version"],
                up_to_date=ver == PIN["version"], patches=st, patches_ok=all(v == "ok" for v in st.values()),
                state_home=state_home(r), migrated_from=(info.get("migrated_from") or {}).get("path"))


def check_lines(c: dict) -> list[str]:
    if not c["installed"]:
        return [f"Agent Reach interno: NON installato (cartella {c['root']})."]
    L = [f"Agent Reach interno {c['version']} (fissata {c['pinned']}) in {c['root']} [{c['source']}]",
         "correzioni locali: " + ", ".join(f"{k} {'ok' if v == 'ok' else 'MANCA'}" for k, v in c["patches"].items())]
    if not c["link_ok"]:
        L.append(f"collegamento nella skill assente ({c['link']}): lo crea l'installatore")
    return L


def main(argv_=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("install"); i.add_argument("--update", action="store_true"); i.add_argument("--no-migrate", action="store_true"); i.add_argument("--json", action="store_true")
    c = sp.add_parser("check"); c.add_argument("--json", action="store_true")
    sp.add_parser("patch"); sp.add_parser("where")
    m = sp.add_parser("migrate"); m.add_argument("--from", dest="src", default=os.path.join(os.path.expanduser("~"), ".agent-reach"))
    a = ap.parse_args(argv_)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass
    if a.cmd == "where":
        print(root())
        return 0
    if a.cmd == "check":
        c = check()
        print(json.dumps(c, ensure_ascii=False, indent=1) if a.json else "\n".join(check_lines(c)))
        return 0 if c["installed"] and c["patches_ok"] and c["up_to_date"] else 1
    if a.cmd == "patch":
        pkg = package_dir()
        if not pkg:
            print("Agent Reach interno non installato.")
            return 1
        res = apply_patches(pkg)
        print(", ".join(f"{k}: {v}" for k, v in res.items()))
        return 0 if all(v in ("ok", "patched") for v in res.values()) else 1
    if a.cmd == "migrate":
        res = migrate(a.src)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    say = (lambda s: print(s, file=sys.stderr, flush=True)) if a.json else (lambda s: print(s, flush=True))
    try:
        rep = install(update=a.update, migrate_from=None if a.no_migrate else "auto", log=say)
    except RuntimeError as e:
        say("ERRORE: " + str(e))
        if a.json:
            print(json.dumps(dict(ok=False, error=str(e)), ensure_ascii=False))
        return 1
    ok = rep["installed"] and all(v in ("ok", "patched") for v in rep["patches"].values())
    if a.json:
        print(json.dumps(dict(rep, ok=ok), ensure_ascii=False))
    else:
        print(f"Agent Reach interno {rep['version']} pronto in {rep['root']}" if ok else "Agent Reach interno installato con avvisi")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
