#!/usr/bin/env python3
"""Agent-Reach adapter: the social platforms (X, TikTok, Instagram, Reddit, XiaoHongShu, Bilibili, Facebook...), YouTube with
transcripts, GitHub, V2EX, Xueqiu, LinkedIn, BOSS, Xiaoyuzhou, web pages and RSS, all through Agent Reach
(https://github.com/Panniantong/agent-reach, MIT). Stdlib only: Agent Reach runs as a separate program (`agent-reach`,
installed with uv) and answers one JSON object per command; this module calls it, caches, throttles and degrades.

What Agent Reach is: a read-only CLI. Public content goes through its "public-web" route (web search scoped to the site, page
reading); logged-in platforms go through its own dedicated browser (CloakBrowser or Chrome, headless) where the OWNER logged
in himself. It never posts, never logs in for you, never asks for passwords. Cookies stay inside ~/.agent-reach/: this module
never reads, prints or copies them.

TikTok: Agent Reach 1.6.1 has no TikTok channel. The OpenCLI tool it installs does have read-only TikTok commands (search,
profile, user videos), so `tiktok` here runs those inside Agent Reach's dedicated browser, read commands only (allowlist).
Experimental: it needs the owner logged in to tiktok.com in that browser, otherwise it answers NEED_LOGIN / empty.

  reach.py doctor [--live] [--md FILE] [-o FILE] [--json]     which channels are ready (pronto) / need a login / are off
  reach.py setup                                              the commands the OWNER runs himself (`! agent-reach login x`)
  reach.py channels                                           every channel, action and parameter Agent Reach declares
  reach.py search <platform> <query...> [--limit 10] [--game game.json]   search (game.json -> entity_match filter)
  reach.py read <url> [--platform P]                          read a post, video, page (channel picked from the URL)
  reach.py profile <platform> <handle>                        followers, bio... (x, instagram, tiktok, facebook, v2ex)
  reach.py posts <platform> <handle> [--limit 10]             recent posts with their numbers (x, instagram, tiktok) or subreddit
  reach.py comments <url>                                     post with comments (reddit, x thread, xiaohongshu)
  reach.py transcript <url> [--lang it,en] [--whisper]        subtitles (YouTube, Bilibili) or speech-to-text (needs a key)
  reach.py rss <feed-url> [--limit 30]                        RSS/Atom feed (stdlib first, Agent Reach web reader if blocked)
  reach.py run <channel> <action> [args...]                   anything else Agent Reach supports, passed through
  common: --cache-dir launch/_raw/reach --max-age 24 --no-cache --rate 3 --retries 1 --timeout 90
          --manual launch/ricerche-manuali.md --mode auto|on|off -o out.json

Platforms: x (twitter), tiktok, instagram, reddit, youtube, bilibili, xiaohongshu (xhs), facebook, github, web, v2ex, linkedin,
boss, xueqiu, xiaoyuzhou.

Every result says ok, label ([FATTO] with url and consultation date, or [DA VERIFICARE]), access (public / site), backend and
the normalised numbers (views, likes, comments, shares, followers, score). A channel that is not ready returns ok=false with
the reason and, with --manual, a dated manual step in ricerche-manuali.md, like the other tools. Never retried around a block:
RATE_LIMITED, PLATFORM_BLOCKED, NEED_LOGIN, BUSY stop the channel for this run.

Python API (used by social_verify, market_tracker, social_content, reddit_trends, reddit_rules, yt_research, case_studies):
  import reach
  reach.enabled()                      Agent Reach installed and not disabled (GLS_REACH=off)
  reach.search("x", "game title", 20)  reach.read(url)  reach.profile("tiktok", "studio")  reach.posts(...)
  reach.comments(url)  reach.transcript(url)  reach.rss(url)  reach.call(channel, action, params)
  reach.metrics(item)                  {views, likes, comments, shares, followers, score...} from any item
Tests: reach.set_runner(fn) or env GLS_REACH_FAKE=fixtures.json (no network, no Agent Reach needed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import common
from common import Throttle, log, parse_count, user_dir, write_json

REPO = "https://github.com/Panniantong/agent-reach"
INSTALL_CMD = "uv tool install https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip"
ALIASES = {"x": "twitter", "twitter": "twitter", "tw": "twitter", "tiktok": "tiktok", "tt": "tiktok", "instagram": "instagram", "ig": "instagram",
           "reels": "instagram", "reddit": "reddit", "youtube": "youtube", "yt": "youtube", "shorts": "youtube", "youtube_shorts": "youtube",
           "bilibili": "bilibili", "bili": "bilibili", "xiaohongshu": "xiaohongshu", "xhs": "xiaohongshu", "rednote": "xiaohongshu",
           "facebook": "facebook", "fb": "facebook", "github": "github", "gh": "github", "web": "web", "rss": "web", "v2ex": "v2ex",
           "linkedin": "linkedin", "boss": "boss", "xueqiu": "xueqiu", "xiaoyuzhou": "xiaoyuzhou"}
# channels whose own data needs the owner's login in the dedicated browser (public-web routes may still answer search/read)
LOGIN_CHANNELS = {"twitter", "instagram", "facebook", "xiaohongshu", "tiktok", "boss"}
# channels that work right after install (no login): an unverified status is still worth one try
OPEN_CHANNELS = {"github", "youtube", "bilibili", "v2ex", "web", "reddit", "linkedin", "xueqiu"}
FINAL = {"NOT_FOUND", "BAD_INPUT", "PLATFORM_BLOCKED", "RATE_LIMITED", "NEED_LOGIN", "BUSY", "NEED_SETUP", "NOT_INSTALLED", "NOT_READY"}
TIKTOK_READ = {"search", "profile", "user", "explore"}     # OpenCLI TikTok commands with access 'read'; nothing else is ever run
OK_STATUS = {"ready", "search_ready"}
STATUS_IT = {"ready": "pronto", "search_ready": "pronto (solo ricerca verificata)", "unverified": "installato, non verificato",
             "needs_login": "serve il login del proprietario", "not_added": "non attivo", "needs_setup": "manca un pezzo",
             "cooldown": "in pausa (troppe richieste)", "broken": "rotto all'ultimo controllo", "needs_user_action": "verifica della piattaforma da fare a mano",
             "not_installed": "Agent Reach non installato"}
MANUAL_SEARCH = {"tiktok": "https://www.tiktok.com/search?q={q}", "twitter": "https://x.com/search?q={q}&f=live",
                 "instagram": "https://www.instagram.com/explore/search/keyword/?q={q}", "reddit": "https://www.reddit.com/search/?q={q}",
                 "youtube": "https://www.youtube.com/results?search_query={q}", "bilibili": "https://search.bilibili.com/all?keyword={q}",
                 "xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword={q}", "facebook": "https://www.facebook.com/search/top?q={q}",
                 "github": "https://github.com/search?q={q}", "web": "https://duckduckgo.com/?q={q}"}
HINT_IT = {"NEED_LOGIN": "il proprietario lancia `! agent-reach login {ch}` e fa il login da sé nella finestra (account secondario consigliato), poi `reach.py doctor --live`",
           "NOT_READY": "canale non pronto: `! agent-reach login {ch}` (o `! agent-reach add {ch}`), poi `reach.py doctor --live`",
           "NEED_SETUP": "manca uno strumento: `! agent-reach add {ch}`, poi `reach.py doctor --live`",
           "NOT_INSTALLED": "Agent Reach non è installato: `! " + INSTALL_CMD + "` e `! agent-reach setup` (oppure `node installer/install.mjs update`)",
           "RATE_LIMITED": "la piattaforma ha rallentato le richieste: aspetta (Agent Reach mette in pausa il canale), non cambiare account",
           "PLATFORM_BLOCKED": "la piattaforma chiede una verifica (captcha): la fa il proprietario sulla pagina ufficiale; non si aggira",
           "BUSY": "il browser dedicato è occupato o c'è una finestra di login aperta: riprova tra un minuto",
           "TIMEOUT": "nessuna risposta in tempo: riprova più tardi o con --timeout più alto",
           "UPSTREAM_BROKEN": "il canale non funziona adesso: riprova più tardi; se dura, `! agent-reach update`",
           "NOT_FOUND": "il contenuto non esiste: controlla il link o il nome"}

_RUNNER = None           # tests: fn(argv: list[str], stdin: str | None, timeout: float) -> stdout str
_THROTTLES: dict = {}
_BLOCKED: dict = {}      # channel -> error code, for the rest of this process
_DOCTOR: dict | None = None
_CHANNELS: dict | None = None
OPTS = dict(cache_dir=None, max_age=24.0, cache=True, rate=3.0, retries=1, timeout=90.0, manual=None, mode="auto")


# ---------------------------------------------------------------- finding and running Agent Reach
def set_runner(fn):
    """Tests: replace the subprocess with fn(argv, stdin, timeout) -> stdout. Resets the per-process state."""
    global _RUNNER, _DOCTOR, _CHANNELS
    _RUNNER, _DOCTOR, _CHANNELS = fn, None, None
    _BLOCKED.clear()
    _THROTTLES.clear()


def configure(**kw):
    for k, v in kw.items():
        if k in OPTS and v is not None:
            OPTS[k] = v


def _fake_runner():
    p = os.environ.get("GLS_REACH_FAKE")
    if not p:
        return None
    fx = common.load_json(p)

    def run(argv, stdin=None, timeout=60):
        key = " ".join(argv)
        if key in fx:
            return json.dumps(fx[key])
        for k in sorted(fx, key=len, reverse=True):     # longest prefix wins
            if key.startswith(k):
                return json.dumps(fx[k])
        return json.dumps(dict(ok=False, items=[], error=dict(code="NOT_FOUND", message=f"no fixture for: {key}", hint="")))
    return run


def find_bin() -> str | None:
    b = os.environ.get("GLS_REACH_BIN")
    if b:
        return b if os.path.exists(b) or shutil.which(b) else None
    w = shutil.which("agent-reach")
    if w:
        return w
    for c in (os.path.join(os.path.expanduser("~"), ".local", "bin", "agent-reach" + (".exe" if os.name == "nt" else "")),):
        if os.path.exists(c):
            return c
    return None


def tool_python() -> str | None:
    """The Python inside Agent Reach's uv tool environment (needed only for the TikTok bridge)."""
    p = os.environ.get("GLS_REACH_PYTHON")
    if p:
        return p if os.path.exists(p) else None
    roots = [os.environ.get("UV_TOOL_DIR")]
    if os.name == "nt":
        roots.append(os.path.join(os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming"), "uv", "tools"))
    roots.append(os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share"), "uv", "tools"))
    for r in filter(None, roots):
        for c in (os.path.join(r, "agent-reach", "Scripts", "python.exe"), os.path.join(r, "agent-reach", "bin", "python")):
            if os.path.exists(c):
                return c
    return None


def enabled() -> bool:
    """True when Agent Reach can be called: a fake runner (tests), or the program installed and GLS_REACH not 'off'."""
    if _RUNNER or os.environ.get("GLS_REACH_FAKE"):
        return True
    if os.environ.get("GLS_REACH", "").lower() in ("off", "0", "no", "false") or OPTS["mode"] == "off":
        return False
    return find_bin() is not None


def _err(code: str, message: str, hint: str = "") -> dict:
    return dict(schema_version=1, ok=False, items=[], meta={}, error=dict(code=code, message=message[:500], hint=hint))


def _exec(argv: list[str], stdin: str | None = None, timeout: float | None = None) -> dict:
    """One Agent Reach command -> its JSON object (or a local error envelope). Never raises."""
    timeout = float(timeout or OPTS["timeout"])
    runner = _RUNNER or _fake_runner()
    try:
        if runner:
            out = runner(argv, stdin, timeout)
        elif argv and argv[0] == "__tiktok__":
            py = tool_python()
            if not py:
                return _err("NOT_INSTALLED", "Agent Reach's Python environment was not found (TikTok bridge)", HINT_IT["NOT_INSTALLED"])
            r = subprocess.run([py, "-I", "-c", _TIKTOK_BRIDGE], input=json.dumps(dict(args=argv[1:], timeout=timeout)), capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout + 150, cwd=os.path.expanduser("~"),
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            out = r.stdout
        else:
            b = find_bin()
            if not b:
                return _err("NOT_INSTALLED", "agent-reach is not on PATH", HINT_IT["NOT_INSTALLED"])
            # neutral working directory: never a cloned or downloaded folder
            r = subprocess.run([b, *argv], input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout + 150, cwd=os.path.expanduser("~"), env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            out = r.stdout
    except subprocess.TimeoutExpired:
        return _err("TIMEOUT", f"agent-reach did not answer in {int(timeout)} s")
    except OSError as e:
        return _err("NOT_INSTALLED", f"cannot run agent-reach: {e.__class__.__name__}", HINT_IT["NOT_INSTALLED"])
    for line in reversed((out or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return _err("BAD_OUTPUT", "agent-reach printed no JSON")


# TikTok through OpenCLI in Agent Reach's dedicated browser (read commands only). Runs inside Agent Reach's own Python.
_TIKTOK_BRIDGE = r'''
import json, sys
req = json.load(sys.stdin)
args = req["args"]
if not args or args[0] not in ("search", "profile", "user", "explore"):
    print(json.dumps({"ok": False, "items": [], "error": {"code": "BAD_INPUT", "message": "only TikTok read commands are allowed", "hint": ""}})); sys.exit(0)
try:
    from agent_reach.runtime import browser, bridge, tools
    from agent_reach.runtime.browser_binding import query_slot
    from agent_reach.runtime.run import CommandFailed, run_cmd
    from agent_reach.backends.opencli import _opencli_error, opencli_items
    from agent_reach.runtime.result import ReachError
except Exception as e:
    print(json.dumps({"ok": False, "items": [], "error": {"code": "NEED_SETUP", "message": "Agent Reach internals changed: " + type(e).__name__, "hint": ""}})); sys.exit(0)
try:
    tools.extend_path()
    if not tools.present("opencli"):
        raise ReachError("NEED_SETUP", "OpenCLI is not installed: run agent-reach add twitter (or instagram)")
    browser.ensure_running()
    prof = browser.bound_context()
    if not prof or not bridge.require_compatible():
        raise ReachError("NEED_SETUP", "OpenCLI has not connected to the dedicated browser")
    browser.touch()
    env = {"OPENCLI_PROFILE": prof, "OPENCLI_WINDOW": "background", "OPENCLI_CDP_ENDPOINT": "", "OPENCLI_CDP_TARGET": ""}
    with query_slot("tiktok"):
        try:
            out = run_cmd(["opencli", "tiktok", *args, "-f", "json"], timeout=float(req.get("timeout", 60)), env=env)
        except CommandFailed as exc:
            raise _opencli_error(exc.stdout or exc.stderr, "tiktok.com") from None
    data = json.loads(out)
    if isinstance(data, dict) and data.get("ok") is False:
        raise _opencli_error(out, "tiktok.com")
    browser.save_session()
    items = opencli_items(data)
    if not items:
        raise ReachError("NEED_LOGIN", "TikTok returned no data (usually: not logged in to tiktok.com in the Agent Reach browser)")
    print(json.dumps({"schema_version": 1, "ok": True, "channel": "tiktok", "action": args[0], "backend": "opencli-tiktok", "items": items, "meta": {}, "error": None}))
except ReachError as e:
    code = e.code
    if code == "UPSTREAM_BROKEN" and any(w in (e.message or "").lower() for w in ("not found", "no data", "unexpected end of json", "could not parse")):
        code = "NEED_LOGIN"
    print(json.dumps({"ok": False, "items": [], "error": {"code": code, "message": (e.message or "")[:400], "hint": e.hint or ""}}))
except Exception as e:
    print(json.dumps({"ok": False, "items": [], "error": {"code": "UPSTREAM_BROKEN", "message": type(e).__name__ + ": " + str(e)[:300], "hint": ""}}))
'''


# ---------------------------------------------------------------- state: doctor, channels, cooldowns
def _state_path() -> str:
    return user_dir("reach_state.json")


def _state() -> dict:
    try:
        return common.load_json(_state_path())
    except (OSError, ValueError):
        return {}


def _save_state(s: dict):
    try:
        os.makedirs(os.path.dirname(_state_path()), exist_ok=True)
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def _note_tiktok(ok: bool, code: str | None = None):
    s = _state()
    s["tiktok"] = dict(status="ready" if ok else ("needs_login" if code == "NEED_LOGIN" else "broken"), at=dt.datetime.now().isoformat(timespec="seconds"), code=code)
    _save_state(s)


def _cooldown(channel: str) -> bool:
    until = (_state().get("cooldown") or {}).get(channel)
    return bool(until and until > time.time())


def _set_cooldown(channel: str, seconds: float):
    s = _state()
    s.setdefault("cooldown", {})[channel] = time.time() + seconds
    _save_state(s)


def channels_info() -> dict:
    """{channel: {level, actions: {name: {params, public_web, backends}}}} from `agent-reach channels` (once per process)."""
    global _CHANNELS
    if _CHANNELS is not None:
        return _CHANNELS
    env = _exec(["channels"], timeout=60)
    _CHANNELS = {}
    for c in env.get("channels") or []:
        _CHANNELS[c["name"]] = dict(level=c.get("level"), description=c.get("description"), login=c.get("login"),
                                    actions={a["name"]: dict(params=[p["name"] for p in a.get("params") or []], required=[p["name"] for p in a.get("params") or [] if p.get("required")],
                                                             public_web=a.get("public_web") or [], backends=a.get("backends") or [], usage=a.get("usage")) for a in c.get("actions") or []})
    return _CHANNELS


def doctor_raw() -> dict:
    global _DOCTOR
    if _DOCTOR is None:
        _DOCTOR = _exec(["doctor"], timeout=60)
    return _DOCTOR


def status(channel: str) -> str:
    """Agent Reach's offline status of a channel (ready, search_ready, unverified, needs_login, not_added, ...)."""
    if not enabled():
        return "not_installed"
    if channel == "tiktok":
        t = _state().get("tiktok") or {}
        if t.get("status"):
            return t["status"]
        tw = status("twitter")
        return "unverified" if tw not in ("not_added", "not_installed", "needs_setup") else "not_added"
    d = doctor_raw()
    if not d.get("ok"):
        return "not_installed" if (d.get("error") or {}).get("code") == "NOT_INSTALLED" else "broken"
    for c in (d.get("result") or {}).get("channels") or []:
        if c.get("channel") == channel:
            return c.get("status") or "unverified"
    return "not_added"


def version() -> str | None:
    d = doctor_raw()
    return (d.get("result") or {}).get("version") if d.get("ok") else None


def ready(channel: str) -> bool:
    """Ready for the channel's OWN data (logged-in reads): what the skill rules call 'pronto'."""
    return status(ALIASES.get(channel, channel)) in OK_STATUS


def route(channel: str, action: str, mode: str | None = None) -> str | None:
    """'site' (no --backend), 'public-web', or None (not usable now)."""
    mode = mode or OPTS["mode"]
    if not enabled() or channel in _BLOCKED or _cooldown(channel):
        return None
    st = status(channel)
    if st in OK_STATUS:
        return "site"
    pw = bool(((channels_info().get(channel) or {}).get("actions") or {}).get(action, {}).get("public_web")) or (channel == "tiktok" and action == "search")
    if st in ("unverified", "not_added") and channel in OPEN_CHANNELS and channel != "reddit":
        return "site"
    if pw:
        return "public-web"
    if mode == "on" and st not in ("not_installed",):
        return "site"
    return None


# ---------------------------------------------------------------- normalising results
NUM_KEYS = dict(views=("views", "view_count", "plays", "playCount", "play_count", "viewCount", "view"),
                likes=("likes", "like_count", "diggCount", "digg_count", "likeCount", "favorite_count", "like"),
                comments=("comments", "comment_count", "num_comments", "commentCount", "replies", "reply", "reply_count"),
                shares=("shares", "share_count", "shareCount", "retweets", "retweet_count", "share"),
                followers=("followers", "follower_count", "followers_count", "fans", "subscribers", "subscriber_count", "channel_follower_count"),
                following=("following", "following_count"), posts=("posts", "videos", "tweets", "media_count", "video_count"),
                score=("score", "upvotes", "ups"), saves=("saves", "collect_count", "collectCount", "favorite", "coin"))


def _flat(raw) -> dict:
    """raw upstream row -> one flat dict (public-web rows keep the original under 'source'; bilibili keeps counts under 'stat')."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k in ("source", "post", "stats", "stat", "statistics"):
        v = raw.get(k)
        if isinstance(v, dict):
            out.update({kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list))})
    out.update({k: v for k, v in raw.items() if not isinstance(v, (dict, list))})
    return out


def metrics(item: dict) -> dict:
    """Public numbers of one item (None when absent). Counts like '1.2K' or '3,456' are parsed."""
    f = _flat(item.get("raw"))
    out = {}
    for name, keys in NUM_KEYS.items():
        for k in keys:
            if k in f and f[k] not in (None, "", False) and not isinstance(f[k], bool):
                n = parse_count(f[k])
                if n is not None:
                    out[name] = n
                    break
    return out


def _date(item: dict) -> str | None:
    p = item.get("published_at") or ""
    if p:
        return str(p)[:10]
    f = _flat(item.get("raw"))
    for k in ("created_at", "createTime", "date", "created_utc", "upload_date", "pubdate"):
        v = f.get(k)
        if v in (None, ""):
            continue
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit() and len(v) >= 9):
            try:
                return common.ts_to_date(int(v))
            except (ValueError, OSError, OverflowError):
                continue
        s = str(v)
        if re.match(r"^\d{8}$", s):
            return f"{s[:4]}-{s[4:6]}-{s[6:]}"
        m = re.search(r"\d{4}-\d{2}-\d{2}", s)
        if m:
            return m.group(0)
        try:   # "Wed Oct 08 12:00:00 +0000 2026" (X)
            return dt.datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").date().isoformat()
        except ValueError:
            continue
    return None


BLOCK_RX = re.compile(r"blocked by network security|just a moment\.\.\.|verify you are (a )?human|are you a robot|access denied|"
                      r"enable javascript and cookies|log in to continue|sign in to continue|performing security verification", re.I)


def is_block_page(it: dict) -> bool:
    """A login wall or anti-bot page returned as if it were content: never [FATTO]."""
    t = f"{it.get('title') or ''} {(it.get('text') or '')[:600]}"
    return bool(BLOCK_RX.search(t)) and len(it.get("text") or "") < 3000


def normalise(env: dict, channel: str, action: str, query: dict, cached: bool = False) -> dict:
    today = dt.date.today().isoformat()
    if env.get("ok") and env.get("items") and all(isinstance(x, dict) and is_block_page(x) for x in env["items"]):
        env = dict(env, ok=False, items=[], error=dict(code="PLATFORM_BLOCKED", message="the page returned is a block / login wall, not the content", hint=""))
    ok = bool(env.get("ok"))
    backend = env.get("backend")
    items = []
    for it in env.get("items") or []:
        if not isinstance(it, dict):
            continue
        raw = it.get("raw")
        access = "public" if (isinstance(raw, dict) and raw.get("access") == "public") or backend == "public-web" else "site"
        items.append(dict(title=it.get("title"), url=it.get("url"), author=it.get("author"), published=_date(it), text=(it.get("text") or "")[:4000] or None,
                          metrics=metrics(it), access=access, raw=raw))
    err = env.get("error") if not ok else None
    if err and err.get("code") in HINT_IT:
        err = dict(err, hint_it=HINT_IT[err["code"]].format(ch=channel))
    return dict(ok=ok and bool(items), channel=channel, action=action, query=query, backend=backend, access=("public" if backend == "public-web" else "site") if ok else None,
                label="[FATTO]" if ok and items else "[DA VERIFICARE]", consulted=today,
                source=f"agent-reach {version() or '?'} · {channel}/{backend or '-'}", cached=cached, items=items,
                error=err if err else (None if items else dict(code="EMPTY", message="no results", hint_it="nessun risultato: prova altre parole o a mano")))


# ---------------------------------------------------------------- calls: cache, throttle, backoff
def _cache_dir() -> str:
    return OPTS["cache_dir"] or os.environ.get("GLS_REACH_CACHE") or os.path.join("launch", "_raw", "reach")


def _cache_path(argv: list[str]) -> str:
    h = hashlib.sha1(json.dumps(argv, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    head = re.sub(r"[^a-z0-9_-]+", "-", "-".join(argv[:2]).lower().replace("__tiktok__", "tiktok"))[:40]
    return os.path.join(_cache_dir(), f"{head}-{h}.json")


def _cache_get(argv: list[str]) -> dict | None:
    if not OPTS["cache"]:
        return None
    p = _cache_path(argv)
    try:
        d = common.load_json(p)
    except (OSError, ValueError):
        return None
    if time.time() - float(d.get("at", 0)) > float(OPTS["max_age"]) * 3600:
        return None
    return d.get("envelope")


def _cache_put(argv: list[str], env: dict):
    if not OPTS["cache"]:
        return
    try:
        os.makedirs(_cache_dir(), exist_ok=True)
        with open(_cache_path(argv), "w", encoding="utf-8") as f:
            json.dump(dict(argv=argv, at=time.time(), date=dt.date.today().isoformat(), envelope=env), f, ensure_ascii=False, indent=1)
    except OSError as e:
        log(f"WARN reach cache: {e.__class__.__name__}")


def _throttle(channel: str) -> Throttle:
    if channel not in _THROTTLES:
        _THROTTLES[channel] = Throttle(OPTS["rate"])
    return _THROTTLES[channel]


def _run(channel: str, argv: list[str], timeout: float | None = None) -> tuple[dict, bool]:
    """Cached, throttled, retried run. Returns (envelope, from_cache)."""
    hit = _cache_get(argv)
    if hit is not None:
        return hit, True
    env = {}
    for attempt in range(int(OPTS["retries"]) + 1):
        _throttle(channel).wait()
        env = _exec(argv, timeout=timeout)
        code = (env.get("error") or {}).get("code") if not env.get("ok") else None
        if not code:
            break
        if code == "RATE_LIMITED":
            _set_cooldown(channel, 3600)
        if code in FINAL:
            if code in ("NEED_LOGIN", "RATE_LIMITED", "PLATFORM_BLOCKED", "BUSY", "NEED_SETUP", "NOT_INSTALLED"):
                _BLOCKED[channel] = code
            break
        if attempt < int(OPTS["retries"]):
            time.sleep(min(30.0, (2 ** attempt) * 2 + random.random()))
    if env.get("ok") and env.get("items") and not all(isinstance(x, dict) and is_block_page(x) for x in env["items"]):
        _cache_put(argv, env)
    return env, False


def manual_step(channel: str, what: str, err: dict | None, query: str = "", path: str | None = None):
    """Append a dated [DA VERIFICARE] block to ricerche-manuali.md (same channel + what + day = written once)."""
    path = path or OPTS["manual"]
    if not path:
        return
    today = dt.date.today().isoformat()
    code = (err or {}).get("code") or "NOT_READY"
    head = f"## agent-reach · {channel} · {what} ({today}) [DA VERIFICARE]"
    try:
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else "# Ricerche manuali\n"
    except OSError:
        old = ""
    if head in old:
        return
    url = MANUAL_SEARCH.get(channel, MANUAL_SEARCH["web"]).format(q=urllib.parse.quote(query)) if query else ""
    L = ["", head, "", f"- Motivo: {code}" + (f" ({(err or {}).get('message', '')[:160]})" if (err or {}).get("message") else ""),
         f"- Per sbloccarlo: {HINT_IT.get(code, HINT_IT['NOT_READY']).format(ch=channel)}"]
    if url:
        L.append(f"- Intanto a mano: {url} (annota URL, data, visualizzazioni e like; i numeri vanno poi in `social_content.py track add` o `market_tracker.py manual --import`)")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(L) + "\n")
    except OSError as e:
        log(f"WARN manual steps: {e.__class__.__name__}")


def _not_ready(channel: str, action: str, query: dict, what: str, q: str = "") -> dict:
    st = status(channel)
    code = "NOT_INSTALLED" if st == "not_installed" else _BLOCKED.get(channel) or ("RATE_LIMITED" if _cooldown(channel) else "NEED_LOGIN" if st == "needs_login" else "NOT_READY")
    err = dict(code=code, message=f"{channel}: {STATUS_IT.get(st, st)}", hint_it=HINT_IT.get(code, HINT_IT["NOT_READY"]).format(ch=channel))
    manual_step(channel, what, err, q)
    return dict(ok=False, channel=channel, action=action, query=query, backend=None, access=None, label="[DA VERIFICARE]", consulted=dt.date.today().isoformat(),
                source=f"agent-reach · {channel}", cached=False, items=[], error=err)


def call(channel: str, action: str, params: dict | None = None, *, what: str | None = None, timeout: float | None = None, backend: str | None = None) -> dict:
    """Run `agent-reach <channel> <action>` with params; route by readiness; degrade with a manual step."""
    channel = ALIASES.get(channel, channel)
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    what = what or f"{action} {' '.join(str(v) for v in params.values())}"[:80]
    q = str(params.get("query") or params.get("username") or params.get("target") or params.get("name") or "")
    if channel == "tiktok":
        return _tiktok(action, params, what)
    r = backend or route(channel, action)
    if r is None:
        return _not_ready(channel, action, params, what, q)
    info = (channels_info().get(channel) or {}).get("actions", {}).get(action) or {}
    req = info.get("required") or [k for k in ("query", "target", "username", "name", "symbol", "node_name") if k in params][:1]
    argv = [channel, action] + [str(params[k]) for k in req if k in params]
    for k, v in params.items():
        if k not in req:
            argv += [f"--{k}", str(v)]
    if r == "public-web":
        argv += ["--backend", "public-web"]
    elif r not in ("site", None):
        argv += ["--backend", r]
    if timeout:
        argv += ["--timeout", str(int(timeout))]
    env, cached = _run(channel, argv, timeout)
    res = normalise(env, channel, action, params, cached)
    if not res["ok"]:
        manual_step(channel, what, res["error"], q)
    return res


def _tiktok(action: str, params: dict, what: str) -> dict:
    q = str(params.get("query") or params.get("username") or "")
    st = status("tiktok")
    if action == "search" and st not in OK_STATUS and OPTS["mode"] != "on":
        # public route: web search scoped to tiktok.com (snippets and links, not TikTok's own ranking or numbers)
        res = call("web", "search", dict(query=f"({params.get('query')}) site:tiktok.com", limit=params.get("limit", 10)), what=what, backend=None)
        res["items"] = [x for x in res["items"] if "tiktok.com" in (x.get("url") or "")]
        for x in res["items"]:
            x["access"] = "public"
        res.update(channel="tiktok", action="search", backend="public-web", access="public", ok=bool(res["items"]), label="[FATTO]" if res["items"] else "[DA VERIFICARE]")
        if not res["items"]:
            manual_step("tiktok", what, res.get("error"), q)
        return res
    if st not in OK_STATUS and OPTS["mode"] != "on" and st != "unverified":
        return _not_ready("tiktok", action, params, what, q)
    if "tiktok" in _BLOCKED:
        return _not_ready("tiktok", action, params, what, q)
    sub = {"search": "search", "profile": "profile", "posts": "user", "user": "user", "explore": "explore"}.get(action)
    if sub not in TIKTOK_READ:
        return dict(_not_ready("tiktok", action, params, what, q), error=dict(code="BAD_INPUT", message=f"tiktok has no read action {action}"))
    argv = ["__tiktok__", sub]
    if sub == "search":
        argv += [str(params.get("query")), "--limit", str(params.get("limit", 10))]
    elif sub in ("profile", "user"):
        argv += [str(params.get("username", "")).lstrip("@")] + (["--limit", str(params.get("limit", 10))] if sub == "user" else [])
    else:
        argv += ["--limit", str(params.get("limit", 10))]
    env, cached = _run("tiktok", argv)
    if not cached:
        _note_tiktok(bool(env.get("ok")), (env.get("error") or {}).get("code"))
    res = normalise(env, "tiktok", action, params, cached)
    if not res["ok"]:
        manual_step("tiktok", what, res["error"], q)
    return res


# ---------------------------------------------------------------- high-level helpers
def platform_of(url: str) -> str | None:
    h = urllib.parse.urlparse(url if "://" in url else "https://" + url).netloc.lower()
    for key, p in (("tiktok.", "tiktok"), ("instagram.", "instagram"), ("instagr.am", "instagram"), ("twitter.", "twitter"), ("x.com", "twitter"),
                   ("youtube.", "youtube"), ("youtu.be", "youtube"), ("reddit.", "reddit"), ("redd.it", "reddit"), ("bilibili.", "bilibili"),
                   ("b23.tv", "bilibili"), ("xiaohongshu.", "xiaohongshu"), ("xhslink.", "xiaohongshu"), ("facebook.", "facebook"), ("github.", "github"),
                   ("v2ex.", "v2ex"), ("linkedin.", "linkedin"), ("xiaoyuzhoufm.", "xiaoyuzhou"), ("xueqiu.", "xueqiu"), ("zhipin.", "boss")):
        if key in h:
            return p
    return "web" if h else None


def handle_of(url: str) -> str | None:
    """@handle / username from a profile or post URL (tiktok, x, instagram)."""
    p = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return None
    if parts[0].startswith("@"):
        return parts[0][1:]
    if parts[0] in ("p", "reel", "reels", "tv", "explore", "i", "search", "hashtag", "status", "stories"):
        return None
    return parts[0]


SEARCH_ACTION = {"linkedin": "jobs", "boss": "search"}


SITE_OF = {"v2ex": "v2ex.com", "xiaoyuzhou": "xiaoyuzhoufm.com", "twitter": "x.com", "instagram": "instagram.com", "facebook": "facebook.com",
           "reddit": "reddit.com", "youtube": "youtube.com", "bilibili": "bilibili.com", "xiaohongshu": "xiaohongshu.com", "github": "github.com",
           "linkedin": "linkedin.com", "boss": "zhipin.com", "xueqiu": "xueqiu.com"}


def search(platform: str, query: str, limit: int = 10, **kw) -> dict:
    ch = ALIASES.get(platform, platform)
    act = SEARCH_ACTION.get(ch, "search")
    acts = (channels_info().get(ch) or {}).get("actions") or {}
    if ch != "tiktok" and acts and act not in acts and ch in SITE_OF:
        # the channel has no search of its own (v2ex, xiaoyuzhou): web search scoped to the site, links and snippets only
        res = call("web", "search", dict(query=f"({query}) site:{SITE_OF[ch]}", limit=limit), **kw)
        res["items"] = [x for x in res["items"] if SITE_OF[ch] in (x.get("url") or "")]
        for x in res["items"]:
            x["access"] = "public"
        res.update(channel=ch, action="search", access="public", ok=bool(res["items"]), label="[FATTO]" if res["items"] else "[DA VERIFICARE]")
        return res
    return call(ch, act, dict(query=query, limit=limit), **kw)


def read(target: str, platform: str | None = None, **kw) -> dict:
    ch = ALIASES.get(platform, platform) if platform else platform_of(target)
    if ch == "tiktok":
        m = re.search(r"/video/(\d+)", target)
        h = handle_of(target)
        if not (m and h):
            return _not_ready("tiktok", "read", dict(target=target), "read " + target[:60], target)
        res = _tiktok("posts", dict(username=h, limit=30), "read " + target[:60])
        hit = [x for x in res["items"] if m.group(1) in (x.get("url") or "") or str(_flat(x.get("raw")).get("id")) == m.group(1)]
        res.update(action="read", items=hit, ok=bool(hit), label="[FATTO]" if hit else "[DA VERIFICARE]")
        if not hit and res.get("error") is None:
            res["error"] = dict(code="NOT_FOUND", message="video not among the last 30 of the account")
        return res
    if ch == "twitter" and "/status/" in target:
        return call("twitter", "thread", dict(target=target), **kw)
    if ch in (None, "web"):
        return call("web", "read", dict(target=target), **kw)
    acts = (channels_info().get(ch) or {}).get("actions") or {}
    if "read" in acts or not acts:
        return call(ch, "read", dict(target=target), **kw)
    return call("web", "read", dict(target=target), **kw)


PROFILE_ACTION = {"twitter": "profile", "instagram": "profile", "tiktok": "profile", "facebook": "profile", "v2ex": "user"}
POSTS_ACTION = {"twitter": ("tweets", "username"), "instagram": ("posts", "username"), "tiktok": ("posts", "username"), "reddit": ("subreddit", "name"),
                "v2ex": ("node", "node_name")}


def profile(platform: str, handle: str, **kw) -> dict:
    ch = ALIASES.get(platform, platform)
    act = PROFILE_ACTION.get(ch)
    if not act:
        return dict(_not_ready(ch, "profile", dict(username=handle), f"profile {handle}"), error=dict(code="BAD_INPUT", message=f"{ch} has no profile action"))
    return call(ch, act, dict(username=str(handle).lstrip("@")), **kw)


def posts(platform: str, handle: str, limit: int = 10, **kw) -> dict:
    ch = ALIASES.get(platform, platform)
    if ch not in POSTS_ACTION:
        return dict(_not_ready(ch, "posts", dict(username=handle), f"posts {handle}"), error=dict(code="BAD_INPUT", message=f"{ch} has no posts action"))
    act, key = POSTS_ACTION[ch]
    return call(ch, act, {key: str(handle).lstrip("@").removeprefix("r/"), "limit": limit}, **kw)


def comments(target: str, limit: int = 20, **kw) -> dict:
    ch = platform_of(target)
    if ch == "reddit":
        # the whole Reddit chain (Agent Reach with login, OAuth, JSON, Arctic Shift archive, RSS, ThreadSnoop, public page)
        import reddit_backends as rb
        r = rb.thread(target)
        if not r["ok"]:
            res = _not_ready("reddit", "comments", dict(target=target), "comments " + target[:60], target)
            res["error"]["attempts"] = r["attempts"]
            return res
        p = r["post"]
        item = dict(title=p.get("title"), url=p.get("url") or target, author=p.get("author"), published=p.get("published"), text=(r.get("text") or "")[:20000],
                    metrics={k: v for k, v in dict(score=p.get("score"), comments=p.get("num_comments")).items() if v is not None}, access="public",
                    raw=dict(post=p, comments=r.get("comments")))
        return dict(ok=True, channel="reddit", action="comments", query=dict(target=target), backend=f"reddit-{r['backend']}", access="public", label="[FATTO]",
                    consulted=r["consulted"], source=f"reddit via {r['backend']} (punteggi: {r['scores']})", cached=False, items=[item], error=None, attempts=r["attempts"])
    if ch == "twitter":
        return call("twitter", "thread", dict(target=target), **kw)
    if ch == "xiaohongshu":
        return call("xiaohongshu", "comments", dict(target=target, limit=limit), **kw)
    return read(target, **kw)


def transcript(target: str, lang: str | None = None, whisper: bool = False, **kw) -> dict:
    ch = platform_of(target) if "://" in target or "." in target else ("youtube" if re.fullmatch(r"[\w-]{11}", target) else "bilibili")
    if ch == "xiaoyuzhou":
        return call("xiaoyuzhou", "transcribe", dict(target=target), timeout=1800, **kw)
    if ch not in ("youtube", "bilibili"):
        return dict(_not_ready(ch or "web", "transcript", dict(target=target), "transcript"), error=dict(code="BAD_INPUT", message="transcripts: YouTube, Bilibili, Xiaoyuzhou"))
    if whisper and ch == "youtube":
        return call("youtube", "transcribe", dict(target=target), timeout=1800, **kw)
    res = call(ch, "subtitle", dict(target=target, lang=lang) if ch == "youtube" else dict(target=target), **kw)
    if not res["ok"] and ch == "youtube" and whisper is None:
        return call("youtube", "transcribe", dict(target=target), timeout=1800, **kw)
    return res


def parse_feed(text: str, limit: int = 50) -> list[dict]:
    i = text.find("<")
    root = ET.fromstring(text[i:] if i > 0 else text)
    A = "{http://www.w3.org/2005/Atom}"
    out = []
    if root.tag.endswith("feed"):
        for e in root.findall(f"{A}entry")[:limit]:
            link = e.find(f"{A}link")
            out.append(dict(title=(e.findtext(f"{A}title") or "").strip(), url=link.get("href") if link is not None else None,
                            author=(e.findtext(f"{A}author/{A}name") or "").strip() or None, published=(e.findtext(f"{A}published") or e.findtext(f"{A}updated") or "")[:10] or None,
                            text=re.sub(r"<[^>]+>", " ", e.findtext(f"{A}content") or e.findtext(f"{A}summary") or "")[:1500].strip() or None, metrics={}, access="public", raw=None))
    else:
        for e in root.iter("item"):
            if len(out) >= limit:
                break
            pub = e.findtext("pubDate") or ""
            try:
                pub = dt.datetime.strptime(pub[:25].strip(), "%a, %d %b %Y %H:%M:%S").date().isoformat()
            except ValueError:
                pub = pub[:10]
            out.append(dict(title=(e.findtext("title") or "").strip(), url=(e.findtext("link") or "").strip() or None, author=e.findtext("author") or None,
                            published=pub or None, text=re.sub(r"<[^>]+>", " ", e.findtext("description") or "")[:1500].strip() or None, metrics={}, access="public", raw=None))
    return out


def rss(url: str, limit: int = 50, **kw) -> dict:
    """A feed: read directly (public, stdlib); if the site blocks scripts, through Agent Reach's web reader (page text)."""
    today = dt.date.today().isoformat()
    try:
        items = parse_feed(common.get_text(url, retries=1, timeout=30), limit)
        return dict(ok=bool(items), channel="web", action="rss", query=dict(target=url), backend="stdlib-rss", access="public", label="[FATTO]" if items else "[DA VERIFICARE]",
                    consulted=today, source="feed pubblico", cached=False, items=items, error=None if items else dict(code="EMPTY", message="feed with no entries"))
    except Exception as e:  # noqa: BLE001
        log(f"rss diretto non riuscito ({getattr(e, 'code', e.__class__.__name__)}): provo agent-reach web read")
    res = call("web", "read", dict(target=url), what="rss " + url[:60], **kw)
    res["action"] = "rss"
    return res


# ---------------------------------------------------------------- doctor and setup
SOCIAL = ["twitter", "tiktok", "instagram", "reddit", "youtube", "facebook", "xiaohongshu", "bilibili"]


def doctor(live: bool = False, tiktok_probe: str = "tiktok") -> dict:
    """Which channels are ready. live=True runs `agent-reach check` (network) and a TikTok probe first."""
    global _DOCTOR
    today = dt.date.today().isoformat()
    if not enabled():
        rows = [dict(channel=c, status="not_installed", ready=False, label=STATUS_IT["not_installed"], next="! " + INSTALL_CMD) for c in SOCIAL]
        return dict(installed=False, version=None, checked_on=today, install=INSTALL_CMD, repo=REPO, rows=rows,
                    ready=[], not_ready=[r["channel"] for r in rows])
    if live:
        chk = _exec(["check", "--timeout", "60"], timeout=900)
        if not chk.get("ok") and not chk.get("results"):
            log("check: " + str((chk.get("error") or {}).get("message", "")))
        _DOCTOR = None
        if status("twitter") not in ("not_added", "needs_setup"):
            env = _exec(["__tiktok__", "profile", tiktok_probe], timeout=90)
            _note_tiktok(bool(env.get("ok")), (env.get("error") or {}).get("code"))
    d = doctor_raw()
    rows = []
    info = channels_info()
    for c in (d.get("result") or {}).get("channels") or []:
        ch, st = c["channel"], c.get("status")
        pw = sorted({a for a, x in ((info.get(ch) or {}).get("actions") or {}).items() if x.get("public_web")})
        label = STATUS_IT.get(st, st)
        if st not in OK_STATUS and pw:
            label += f"; via web pubblico: {', '.join(pw)}"
        nxt = "" if st in OK_STATUS else (f"! agent-reach add {ch}  poi  ! agent-reach login {ch}" if st == "not_added" and (ch in LOGIN_CHANNELS or ch == "reddit") else
                                          f"! agent-reach login {ch}" if ch in LOGIN_CHANNELS or ch == "reddit" or st == "needs_login" else
                                          f"! agent-reach add {ch}" if st == "not_added" else f"agent-reach check {ch}" if st == "unverified" else
                                          "! agent-reach update" if st == "broken" else "")
        rows.append(dict(channel=ch, level=c.get("level"), status=st, ready=st in OK_STATUS, label=label, public_web=pw, problems=c.get("problems") or [],
                         checked_at=c.get("checked_at"), next=nxt, verified_actions=c.get("verified_actions") or []))
    tst = status("tiktok")
    t = _state().get("tiktok") or {}
    rows.append(dict(channel="tiktok", level="experimental (OpenCLI nel browser di Agent Reach)", status=tst, ready=tst in OK_STATUS,
                     label=STATUS_IT.get(tst, tst) + "; ricerca via web pubblico sempre possibile", public_web=["search"], problems=[],
                     checked_at=t.get("at"), next="" if tst in OK_STATUS else "! agent-reach login twitter  (poi apri tiktok.com nella stessa finestra e fai il login)",
                     verified_actions=["search", "profile", "user"] if tst in OK_STATUS else []))
    tools_ = [dict(tool=x.get("tool"), version=x.get("version")) for x in (d.get("result") or {}).get("tools") or []]
    return dict(installed=True, version=version(), checked_on=today, live=live, repo=REPO, rows=rows, tools=tools_,
                ready=[r["channel"] for r in rows if r["ready"]], not_ready=[r["channel"] for r in rows if not r["ready"]])


def doctor_md(d: dict) -> str:
    L = [f"# Agent Reach: canali pronti ({d['checked_on']})", ""]
    if not d["installed"]:
        return "\n".join(L + ["Agent Reach **non è installato**. Il proprietario lancia:", "", f"    ! {d['install']}", "    ! agent-reach setup", "",
                              "(oppure `node installer/install.mjs update`, che lo installa come dipendenza facoltativa)."]) + "\n"
    L += [f"Versione {d['version']} · controllo {'dal vivo' if d.get('live') else 'offline (stato dell’ultimo check)'}. "
          "**Pronto** = il canale ha passato il controllo dal vivo nelle ultime 24 ore: i numeri letti valgono **[FATTO]** con URL e data.", "",
          "| Canale | Stato | Pronto | Da fare |", "|---|---|---|---|"]
    for r in d["rows"]:
        L.append(f"| {r['channel']} | {r['label']} | {'sì' if r['ready'] else 'no'} | {('`' + r['next'] + '`') if r['next'] else ''} |")
    return "\n".join(L) + "\n"


def setup_text() -> str:
    return f"""# Agent Reach: comandi che lancia il proprietario (mai Claude al posto suo)

Login e cookie non passano mai dalla chat. Ogni comando si lancia nella chat con `!` davanti (gira nel tuo terminale).
Usa un **account secondario**: le piattaforme possono limitare gli account usati da programmi.

1. Installazione (se manca):  `! {INSTALL_CMD}`  poi  `! agent-reach setup`
2. Social con login, una volta sola (si apre una finestra del browser dedicato, il login lo fai tu):
   - X / Twitter:   `! agent-reach login twitter`
   - Instagram:     `! agent-reach login instagram`
   - Reddit (dati del sito, punteggi veri): `! agent-reach login reddit`
   - XiaoHongShu:   `! agent-reach add xiaohongshu`  poi  `! agent-reach login xiaohongshu`
   - Facebook:      `! agent-reach add facebook`  poi  `! agent-reach login facebook`
   - Bilibili (sottotitoli): `! agent-reach login bilibili` (QR)
   - TikTok: nella finestra aperta da `! agent-reach login twitter` apri https://www.tiktok.com/login e fai il login anche lì
     (stesso browser dedicato; TikTok passa da OpenCLI, è sperimentale)
3. Chiavi facoltative (testo nascosto, mai in chat): `! agent-reach configure groq-key` (trascrizione dei video senza sottotitoli)
4. Verifica: `! python <skill>/scripts/research/reach.py doctor --live`  → tabella pronto / non pronto
5. Se un login scade: rifai il punto 2 per quel canale. Per uscire: `! agent-reach logout <canale>`.
"""


# ---------------------------------------------------------------- CLI
def _filter_game(res: dict, game_path: str | None, threshold: int | None):
    if not game_path:
        return res
    import entity_match as em
    g = common.load_json(game_path)
    em.filter_reach(res, g, threshold or em.THRESHOLD)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-dir"); ap.add_argument("--max-age", type=float, default=24.0, help="hours a cached result stays valid (default 24)")
    ap.add_argument("--no-cache", action="store_true"); ap.add_argument("--rate", type=float, default=3.0, help="seconds between calls per channel (default 3)")
    ap.add_argument("--retries", type=int, default=1); ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--manual", help="ricerche-manuali.md: append a manual step when a channel is not ready")
    ap.add_argument("--mode", default="auto", choices=["auto", "on", "off"], help="on = try even channels not marked ready")
    ap.add_argument("-o", "--out", default="-")
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("doctor"); d.add_argument("--live", action="store_true"); d.add_argument("--md"); d.add_argument("--json", action="store_true")
    sp.add_parser("setup"); sp.add_parser("channels")
    s = sp.add_parser("search"); s.add_argument("platform"); s.add_argument("query", nargs="+"); s.add_argument("--limit", type=int, default=10)
    s.add_argument("--game", help="game JSON for entity_match (title, appid, developers, handles, words...)"); s.add_argument("--threshold", type=int)
    r = sp.add_parser("read"); r.add_argument("target"); r.add_argument("--platform")
    pr = sp.add_parser("profile"); pr.add_argument("platform"); pr.add_argument("handle")
    po = sp.add_parser("posts"); po.add_argument("platform"); po.add_argument("handle"); po.add_argument("--limit", type=int, default=10)
    po.add_argument("--game"); po.add_argument("--threshold", type=int)
    c = sp.add_parser("comments"); c.add_argument("target"); c.add_argument("--limit", type=int, default=20)
    t = sp.add_parser("transcript"); t.add_argument("target"); t.add_argument("--lang"); t.add_argument("--whisper", action="store_true")
    f = sp.add_parser("rss"); f.add_argument("url"); f.add_argument("--limit", type=int, default=50)
    ru = sp.add_parser("run"); ru.add_argument("channel"); ru.add_argument("action"); ru.add_argument("args", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    configure(cache_dir=a.cache_dir, max_age=a.max_age, cache=not a.no_cache, rate=a.rate, retries=a.retries, timeout=a.timeout, manual=a.manual, mode=a.mode)
    if a.cmd == "setup":
        print(setup_text())
        return 0
    if a.cmd == "doctor":
        res = doctor(a.live)
        if a.md:
            with open(a.md, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(doctor_md(res))
            log(f"wrote {a.md}")
        if a.json or a.out != "-":
            write_json(res, a.out)
        else:
            print(doctor_md(res))
        return 0
    if a.cmd == "channels":
        write_json(_exec(["channels"]), a.out)
        return 0
    if a.cmd == "search":
        res = _filter_game(search(a.platform, " ".join(a.query), a.limit), a.game, a.threshold)
    elif a.cmd == "read":
        res = read(a.target, a.platform)
    elif a.cmd == "profile":
        res = profile(a.platform, a.handle)
    elif a.cmd == "posts":
        res = _filter_game(posts(a.platform, a.handle, a.limit), a.game, a.threshold)
    elif a.cmd == "comments":
        res = comments(a.target, a.limit)
    elif a.cmd == "transcript":
        res = transcript(a.target, a.lang, a.whisper)
    elif a.cmd == "rss":
        res = rss(a.url, a.limit)
    else:
        argv2 = [a.channel, a.action] + list(a.args)
        if ALIASES.get(a.channel, a.channel) == "tiktok":
            argv2 = ["__tiktok__", a.action] + list(a.args)
        env, cached = _run(ALIASES.get(a.channel, a.channel), argv2)
        res = normalise(env, ALIASES.get(a.channel, a.channel), a.action, dict(args=a.args), cached)
    write_json(res, a.out)
    log(f"{res['channel']} {res['action']}: {'ok' if res['ok'] else (res.get('error') or {}).get('code')} · {len(res['items'])} risultati · {res['label']}"
        + (" (cache)" if res.get("cached") else ""))
    return 0 if res["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
