#!/usr/bin/env python3
"""Agent-Reach adapter: the social platforms (X, TikTok, Instagram, Reddit, XiaoHongShu, Bilibili, Facebook...), YouTube with
transcripts, GitHub, V2EX, Xueqiu, LinkedIn, BOSS, Xiaoyuzhou, web pages and RSS, all through Agent Reach
(https://github.com/Panniantong/agent-reach, MIT). Stdlib only. Agent Reach is an INTERNAL component of the skill: a private copy
(pinned version, own Python, own state folder) built by the skill installer, see reach_runtime.py. This module runs that copy, never
a global `agent-reach` found on PATH, and answers one JSON object per command; it caches, throttles, degrades and translates.

What Agent Reach is: a read-only CLI. Public content goes through its "public-web" route (web search scoped to the site, page
reading); logged-in platforms go through its own dedicated browser (CloakBrowser, headless) where the OWNER logged in himself. It
never posts, never logs in for you, never asks for passwords. Cookies stay inside the private state folder
(~/.game-launch-strategist/reach/home): this module never reads, prints or copies them (it only asks Agent Reach's own Python whether a login cookie exists BY NAME: a yes/no answer).

TikTok: Agent Reach 1.6.1 has no TikTok channel. The OpenCLI tool it installs does have read-only TikTok commands (search,
profile, user videos), so `tiktok` here runs those inside Agent Reach's dedicated browser, read commands only (allowlist).
Experimental: it needs the owner logged in to tiktok.com in that browser, otherwise it answers NEED_LOGIN / empty.

  reach.py install                                            build or repair the internal copy (same as the installer does)
  reach.py doctor [--live] [--md FILE] [-o FILE] [--json]     which channels are ready (pronto) / need a login / are off
  reach.py setup                                              the commands the OWNER runs himself (`! python reach.py login x`)
  reach.py login <channel> [--lang it-IT] [--check] [--no-wait]   opens the login window of the dedicated browser (in your language),
                                                              then checks the channel (tiktok = twitter window + tiktok.com/login)
  reach.py login <canale|tutti> --dal-mio-browser             copies the login of the OWNER'S normal Chrome/Edge (never shows it); tiktok included
  reach.py collega-browser                                    step by step: connect the owner's normal browser (OpenCLI extension)
  reach.py logout <channel> | add <channel> | configure <key> | browser status|stop|profiles|use ID     owner maintenance, all through the skill
  reach.py fix-lang [--lang it-IT] [--stop]                   check the language fix and set the browser profile languages
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
RATE_LIMITED, PLATFORM_BLOCKED, NEED_LOGIN, BUSY stop the channel for this run. Messages Agent Reach writes in Chinese are
replaced by Italian ones (error code + hint) before they reach the owner.

Python API (used by social_verify, market_tracker, social_content, reddit_trends, reddit_rules, yt_research, case_studies):
  import reach
  reach.enabled()                      the internal copy is installed and not disabled (GLS_REACH=off)
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
import reach_runtime as rt
from common import Throttle, log, parse_count, user_dir, write_json

REPO = "https://github.com/Panniantong/agent-reach"
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
             "not_installed": "Agent Reach interno non installato"}
MANUAL_SEARCH = {"tiktok": "https://www.tiktok.com/search?q={q}", "twitter": "https://x.com/search?q={q}&f=live",
                 "instagram": "https://www.instagram.com/explore/search/keyword/?q={q}", "reddit": "https://www.reddit.com/search/?q={q}",
                 "youtube": "https://www.youtube.com/results?search_query={q}", "bilibili": "https://search.bilibili.com/all?keyword={q}",
                 "xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword={q}", "facebook": "https://www.facebook.com/search/top?q={q}",
                 "github": "https://github.com/search?q={q}", "web": "https://duckduckgo.com/?q={q}"}
HINT_IT = {"NEED_LOGIN": "il proprietario lancia `! {login}` e fa il login da sé nella finestra (account secondario consigliato), poi `reach.py doctor --live`; se la piattaforma blocca quel login, copia quello del tuo browser normale: `! {login} --dal-mio-browser` (prima `! {me} collega-browser`)",
           "NOT_READY": "canale non pronto: `! {login}` (o `! {me} add {ch}`), poi `reach.py doctor --live`; alternativa: `! {login} --dal-mio-browser` (login copiato dal tuo browser normale, vedi `! {me} collega-browser`)",
           "NEED_SETUP": "manca uno strumento: `! {me} add {ch}`, poi `reach.py doctor --live`",
           "NOT_INSTALLED": "Agent Reach interno non installato: `! {me} install` (lo fa anche l'aggiornamento della skill)",
           "RATE_LIMITED": "la piattaforma ha rallentato le richieste: aspetta (Agent Reach mette in pausa il canale), non cambiare account",
           "PLATFORM_BLOCKED": "la piattaforma chiede una verifica (captcha): la fa il proprietario sulla pagina ufficiale; non si aggira",
           "BUSY": "il browser dedicato è occupato o c'è una finestra di login aperta: riprova tra un minuto",
           "TIMEOUT": "nessuna risposta in tempo: riprova più tardi o con --timeout più alto",
           "UPSTREAM_BROKEN": "il canale non funziona adesso: riprova più tardi; se dura, `! {me} install` (ripara la copia interna)",
           "NOT_FOUND": "il contenuto non esiste: controlla il link o il nome",
           "BAD_INPUT": "richiesta non valida: controlla canale, azione e parametri"}
# Agent Reach writes many messages in Chinese: the owner sees these instead (by error code), never the raw text
MSG_IT = {"NEED_LOGIN": "serve il login nel browser dedicato", "NOT_READY": "canale non pronto", "NEED_SETUP": "manca uno strumento del canale",
          "NOT_INSTALLED": "Agent Reach interno non installato", "RATE_LIMITED": "troppe richieste, la piattaforma ha rallentato",
          "PLATFORM_BLOCKED": "la piattaforma ha chiesto una verifica", "BUSY": "browser dedicato occupato", "TIMEOUT": "nessuna risposta in tempo",
          "UPSTREAM_BROKEN": "il canale non ha risposto come previsto", "NOT_FOUND": "contenuto non trovato", "BAD_INPUT": "richiesta non valida",
          "BAD_OUTPUT": "risposta non leggibile"}
_CJK = re.compile(r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")


def me() -> str:
    """`python <installed reach.py>`: how the owner calls this file after `!`."""
    p = skill_script()
    return f"python {chr(34) + p + chr(34) if ' ' in p else p}"


def hint_it(code: str, channel: str) -> str:
    """The Italian hint of an error code, with the login command the owner can really type."""
    return HINT_IT.get(code, HINT_IT["NOT_READY"]).format(ch=channel, login=login_cmd(channel), me=me())


def it_text(text, code: str | None = None) -> str:
    """Owner-facing text: a message in Chinese becomes the Italian one of its error code (English is kept as it is)."""
    t = str(text or "")
    if not _CJK.search(t):
        return t
    return MSG_IT.get(code or "", "messaggio di Agent Reach non tradotto") + (f" [{code}]" if code else "")


def it_error(err: dict | None) -> dict | None:
    """The error envelope with message/hint safe to show (Chinese replaced); the original stays under message_raw."""
    if not err:
        return err
    code = err.get("code")
    out = dict(err)
    for k in ("message", "hint"):
        if out.get(k) and _CJK.search(str(out[k])):
            out[k + "_raw"] = out[k]
            out[k] = it_text(out[k], code) if k == "message" else (hint_it(code, "") if code in HINT_IT else "")
    return out


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


def tool_python() -> str | None:
    """The private Python of the internal Agent Reach copy (reach_runtime.py), or None. Never a global install."""
    p = rt.python()
    return p if os.path.isfile(p) else None


def enabled() -> bool:
    """True when Agent Reach can be called: a fake runner (tests), or the internal copy installed and GLS_REACH not 'off'."""
    if _RUNNER or os.environ.get("GLS_REACH_FAKE"):
        return True
    if os.environ.get("GLS_REACH", "").lower() in ("off", "0", "no", "false") or OPTS["mode"] == "off":
        return False
    return rt.installed()


def _err(code: str, message: str, hint: str = "") -> dict:
    return dict(schema_version=1, ok=False, items=[], meta={}, error=dict(code=code, message=message[:500], hint=hint))


def _exec(argv: list[str], stdin: str | None = None, timeout: float | None = None) -> dict:
    """One Agent Reach command -> its JSON object (or a local error envelope). Never raises."""
    timeout = float(timeout or OPTS["timeout"])
    runner = _RUNNER or _fake_runner()
    try:
        if runner:
            out = runner(argv, stdin, timeout)
        elif not tool_python():
            return _err("NOT_INSTALLED", "the internal Agent Reach copy is not installed", hint_it("NOT_INSTALLED", ""))
        elif argv and argv[0] in ("__tiktok__", "__tiktok_import__", "__logincookies__"):
            r = subprocess.run([tool_python(), "-I", "-X", "utf8", "-c", {"__tiktok__": _TIKTOK_BRIDGE, "__tiktok_import__": _TIKTOK_IMPORT}.get(argv[0], _LOGINCK)],
                               input=stdin if argv[0] == "__logincookies__" else json.dumps(dict(args=argv[1:], timeout=timeout)),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout + 150,
                               cwd=os.path.expanduser("~"), env=rt.env())
            out = r.stdout
        else:
            # the private copy (never a program found on PATH); neutral working directory, never a cloned or downloaded folder
            r = subprocess.run(rt.argv(argv), input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout + 150, cwd=os.path.expanduser("~"), env=rt.env())
            out = r.stdout
    except subprocess.TimeoutExpired:
        return _err("TIMEOUT", f"agent-reach did not answer in {int(timeout)} s")
    except OSError as e:
        return _err("NOT_INSTALLED", f"cannot run the internal agent-reach: {e.__class__.__name__}", hint_it("NOT_INSTALLED", ""))
    return _parse(out)


def _parse(out: str) -> dict:
    """The last JSON line of Agent Reach's output; its error message is made readable for the owner (no Chinese)."""
    for line in reversed((out or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                env = json.loads(line)
            except ValueError:
                break
            if isinstance(env, dict) and isinstance(env.get("error"), dict):
                env["error"] = it_error(env["error"])
            return env
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
        raise ReachError("NEED_SETUP", "OpenCLI is not installed: reach.py add twitter (or instagram)")
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


# Copies the owner's tiktok.com login from his normal browser into the dedicated one. Agent Reach has no TikTok channel, so this runs
# its own session_reuse.prepare (the code behind `login <ch> --import-existing`) with a stand-in channel. It prints counts only.
_TIKTOK_IMPORT = r'''
import json, sys
def out(ok, result=None, code="", message="", hint=""):
    print(json.dumps({"schema_version": 1, "ok": ok, "action": "reuse login", "result": result,
                      "error": None if ok else {"code": code, "message": message[:300], "hint": hint}}))
try:
    from types import SimpleNamespace
    from agent_reach.runtime import manage, session_reuse, tools
    from agent_reach.runtime.result import ReachError
except Exception as e:
    out(False, code="NEED_SETUP", message="Agent Reach internals changed: " + type(e).__name__); sys.exit(0)
try:
    tools.extend_path()
    ch = SimpleNamespace(name="tiktok", login_url="https://www.tiktok.com/login", domains=("tiktok.com",))
    orig = manage._channel
    manage._channel = lambda name: ch if name == "tiktok" else orig(name)
    r = session_reuse.prepare("tiktok", force=True)
    out(True, {"source": r.get("source"), "copied_cookies": r.get("copied_cookies", 0)})
except ReachError as e:
    out(False, code=e.code, message=e.message or "", hint=e.hint or "")
except Exception as e:
    out(False, code="UPSTREAM_BROKEN", message=type(e).__name__)
'''


# Does the dedicated browser hold the cookie only a LOGGED-IN user has on that site? Runs inside Agent Reach's own Python, never starts the
# browser, looks cookies up BY NAME and prints booleans only: values are never printed, returned or stored.
_LOGINCK = r'''
import json, sys
req = json.load(sys.stdin)
def out(ok, result=None, code="", message=""):
    print(json.dumps({"schema_version": 1, "ok": ok, "result": result, "error": None if ok else {"code": code, "message": message[:200], "hint": ""}}))
try:
    from agent_reach.runtime import browser, cdp
except Exception as e:
    out(False, code="NEED_SETUP", message="Agent Reach internals changed: " + type(e).__name__); sys.exit(0)
try:
    res = cdp.call("Storage.getCookies") if browser.is_running() else None
    if res is None:
        out(True, {"running": False, "present": {}}); sys.exit(0)
    rows = res.get("cookies", [])
    present = {}
    for ch, (dom, names) in (req.get("channels") or {}).items():
        present[ch] = any(c.get("name") in names and bool(c.get("value")) and cdp.domain_matches(str(c.get("domain", "")), dom) for c in rows)
    out(True, {"running": True, "present": present})
except Exception as e:
    out(False, code="UPSTREAM_BROKEN", message=type(e).__name__)
'''
# channel -> (site domain, names of the cookie only a logged-in user has). Names are public knowledge, not secrets.
LOGIN_COOKIE = {"twitter": ("x.com", ("auth_token",)), "reddit": ("reddit.com", ("reddit_session",)),
                "instagram": ("instagram.com", ("sessionid",)), "linkedin": ("linkedin.com", ("li_at",)),
                "tiktok": ("tiktok.com", ("sessionid", "sessionid_ss", "sid_tt"))}
SITE_NAME = dict(twitter="X", reddit="Reddit", instagram="Instagram", linkedin="LinkedIn", tiktok="TikTok")


def login_cookie_state(channels) -> dict:
    """{channel: True|False|None}: is the login cookie of each channel in the dedicated browser? None = unknown (browser off, no answer)."""
    want = {c: LOGIN_COOKIE[c] for c in channels if c in LOGIN_COOKIE}
    if not want:
        return {}
    env = _exec(["__logincookies__"], stdin=json.dumps(dict(channels={c: [d, list(n)] for c, (d, n) in want.items()})), timeout=30)
    res = env.get("result") if isinstance(env.get("result"), dict) else {}
    if not env.get("ok") or not res.get("running"):
        return {c: None for c in want}
    return {c: (bool(res["present"][c]) if c in (res.get("present") or {}) else None) for c in want}


def _agent_state() -> dict:
    """Agent Reach's own state.json (counts, codes and times only are read from it), or {}."""
    try:
        with open(os.path.join(rt.state_home(), "state.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def agent_cooldown_left(channel: str) -> int:
    """Seconds Agent Reach still keeps the channel in its 1-hour pause after a confirmed rate limit (0 = no pause)."""
    at = ((_agent_state().get("cooldowns") or {}).get(channel) or {}).get("at")
    try:
        t = dt.datetime.strptime(str(at), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return 0
    return max(0, int(t + 3600 - time.time()))


def _short(msg, code=None) -> str:
    line = (str(msg or "").strip().splitlines() or [""])[0]
    return it_text(line, code)[:160]


def _note_diag(channel: str, env: dict):
    """After a live check: per failed action keep the error code and the first line of the message (no cookies, no results)."""
    acts = {}
    for r in env.get("results") or []:
        if r.get("channel") == channel and not r.get("passed") and isinstance(r.get("error"), dict):
            e = r["error"]
            acts.setdefault(r.get("action") or "?", dict(code=e.get("code"), msg=_short(e.get("message"), e.get("code"))))
    s = _state()
    s.setdefault("diag", {})[channel] = dict(at=dt.datetime.now().isoformat(timespec="seconds"), actions=acts)
    _save_state(s)


def diagnose(channel: str, cookie: bool | None = None) -> dict:
    """Why a channel is not ready, in plain Italian, from facts only: Agent Reach's pause, the login cookie in the dedicated browser and
    the error text of the last live check. Returns {why, next}; `next` is empty when the right answer is the public web or waiting."""
    site = SITE_NAME.get(channel, channel)
    left = agent_cooldown_left(channel)
    acts = ((_state().get("diag") or {}).get(channel) or {}).get("actions") or {}
    msgs = " ".join(str(a.get("msg") or "") for a in acts.values()).lower()
    codes = {a.get("code") for a in acts.values()}
    if left:
        mins = max(1, left // 60)
        return dict(why=f"{site} ha rallentato le richieste: Agent Reach non riprova per altri {mins} minuti (non insistere e non cambiare account); "
                        "passato il tempo controlla UNA sola volta",
                    next=f"! {me()} login {channel} --check")
    if cookie is False and channel in LOGIN_COOKIE:
        name = LOGIN_COOKIE[channel][1][0]
        return dict(why=f"nel browser dedicato manca il cookie di login `{name}`: il login di {site} non c'è (non è stato copiato, oppure {site} l'ha cancellato): entra in {site} nel tuo Chrome (profilo scelto) e ripeti la copia",
                    next=f"! {alt_cmd(channel)}")
    if "unexpected token '<'" in msgs or "not valid json" in msgs or "network security" in msgs:
        return dict(why=f"{site} blocca le richieste dati del browser dedicato (risposta 403 \"blocked by network security\"): è un blocco della piattaforma, "
                        "non dipende dal tuo login; ricerca e lettura passano dal web pubblico", next="")
    if "NEED_LOGIN" in codes and cookie:
        return dict(why=f"{site} rifiuta la sessione copiata (risposta 401) anche se il cookie di login c'è: di solito è un limite temporaneo o la sessione è stata invalidata: aspetta almeno un'ora e controlla UNA sola volta",
                    next=f"! {me()} login {channel} --check")
    return dict(why="", next="")


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
        err = dict(err, hint_it=hint_it(err["code"], channel))
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
         f"- Per sbloccarlo: {hint_it(code, channel)}"]
    if (err or {}).get("why"):
        L.insert(4, f"- Perché: {err['why']}")
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
    err = dict(code=code, message=f"{channel}: {STATUS_IT.get(st, st)}", hint_it=hint_it(code, channel))
    if st not in OK_STATUS:
        err["why"] = diagnose(channel)["why"]          # the real cause, when known (pause, missing login cookie, platform block)
        if not err["why"]:
            del err["why"]
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


def runtime_info() -> dict:
    """Where the internal copy lives, its version and whether every local patch is in place (no Agent Reach process started)."""
    if _RUNNER or os.environ.get("GLS_REACH_FAKE"):
        return dict(root="(test)", installed=True, version=None, patches_ok=True, patches={}, source="test")
    try:
        return rt.check()
    except Exception as e:  # noqa: BLE001
        return dict(root=None, installed=False, error=e.__class__.__name__, patches_ok=False, patches={})


def doctor(live: bool = False, tiktok_probe: str = "tiktok") -> dict:
    """Which channels are ready. live=True runs Agent Reach's `check` (network) and a TikTok probe first."""
    global _DOCTOR
    today = dt.date.today().isoformat()
    run_info = runtime_info()
    if not enabled():
        nxt = f"! {me()} install"
        rows = [dict(channel=c, status="not_installed", ready=False, label=STATUS_IT["not_installed"], next=nxt) for c in SOCIAL]
        return dict(installed=False, version=None, checked_on=today, install=nxt, repo=REPO, runtime=run_info, rows=rows,
                    ready=[], not_ready=[r["channel"] for r in rows])
    if live:
        chk = _exec(["check", "--timeout", "60"], timeout=900)
        if not chk.get("ok") and not chk.get("results"):
            log("check: " + it_text((chk.get("error") or {}).get("message", ""), (chk.get("error") or {}).get("code")))
        for c in sorted({r.get("channel") for r in chk.get("results") or [] if r.get("channel")}):
            _note_diag(c, chk)
        _DOCTOR = None
        if status("twitter") not in ("not_added", "needs_setup"):
            env = _exec(["__tiktok__", "profile", tiktok_probe], timeout=90)
            _note_tiktok(bool(env.get("ok")), (env.get("error") or {}).get("code"))
    d = doctor_raw()
    rows = []
    info = channels_info()
    importable = set(import_channels())
    chans = (d.get("result") or {}).get("channels") or []
    # is the login cookie of a not-ready channel (and of TikTok) in the dedicated browser? one local look, names only, no network
    cookie = login_cookie_state([c["channel"] for c in chans if c.get("status") not in OK_STATUS and c["channel"] in LOGIN_COOKIE] + ["tiktok"])
    for c in chans:
        ch, st = c["channel"], c.get("status")
        pw = sorted({a for a, x in ((info.get(ch) or {}).get("actions") or {}).items() if x.get("public_web")})
        label = STATUS_IT.get(st, st)
        if st not in OK_STATUS and pw:
            label += f"; via web pubblico: {', '.join(pw)}"
        nxt = "" if st in OK_STATUS else (f"! {login_cmd(ch)}" if ch in LOGIN_CHANNELS or ch == "reddit" or st == "needs_login" else
                                          f"! {me()} add {ch}" if st == "not_added" else f"{me()} doctor --live" if st == "unverified" else
                                          f"! {me()} install" if st == "broken" else "")
        dg = diagnose(ch, cookie.get(ch)) if st not in OK_STATUS else {}
        if dg.get("why"):                       # a real cause is known: do not send the owner to reinstall or to log in again for nothing
            nxt = dg.get("next", "")
        rows.append(dict(channel=ch, level=c.get("level"), status=st, ready=st in OK_STATUS, label=label, public_web=pw, why=dg.get("why", ""),
                         problems=[it_text(p) for p in c.get("problems") or []],
                         checked_at=c.get("checked_at"), next=nxt, verified_actions=c.get("verified_actions") or [],
                         alt=f"! {alt_cmd(ch)}" if st not in OK_STATUS and ch in importable and nxt != f"! {alt_cmd(ch)}" else ""))
    tst = status("tiktok")
    t = _state().get("tiktok") or {}
    tlabel = STATUS_IT.get(tst, tst) + "; ricerca via web pubblico sempre possibile"
    twhy = diagnose("tiktok", cookie.get("tiktok"))["why"] if tst not in OK_STATUS else ""
    if tst in OK_STATUS and cookie.get("tiktok") is False:     # the probe also passes on public data: say that no login is behind it
        twhy = "nel browser dedicato non c'è il login di TikTok (cookie `sessionid` assente): vale solo per i dati pubblici"
        tlabel += "; ATTENZIONE: senza login, solo dati pubblici"
    rows.append(dict(channel="tiktok", level="experimental (OpenCLI nel browser di Agent Reach)", status=tst, ready=tst in OK_STATUS,
                     label=tlabel, why=twhy, public_web=["search"], problems=[],
                     checked_at=t.get("at"), next="" if tst in OK_STATUS else f"! {login_cmd('tiktok')}  (si apre la finestra di X: poi apri tiktok.com/login nella stessa finestra e fai il login)",
                     alt="" if tst in OK_STATUS else f"! {alt_cmd('tiktok')}",
                     verified_actions=["search", "profile", "user"] if tst in OK_STATUS else []))
    tools_ = [dict(tool=x.get("tool"), version=x.get("version")) for x in (d.get("result") or {}).get("tools") or []]
    return dict(installed=True, version=version(), checked_on=today, live=live, repo=REPO, runtime=run_info, rows=rows, tools=tools_,
                ready=[r["channel"] for r in rows if r["ready"]], not_ready=[r["channel"] for r in rows if not r["ready"]])


def doctor_md(d: dict) -> str:
    L = [f"# Agent Reach: canali pronti ({d['checked_on']})", ""]
    ri = d.get("runtime") or {}
    if not d["installed"]:
        return "\n".join(L + ["Agent Reach (componente interno della skill) **non è installato**. Il proprietario lancia:", "",
                              f"    {d['install']}", "", "(lo fa anche l'aggiornamento della skill: `update.bat` / `node installer/install.mjs update`)."]) + "\n"
    L += [f"Versione {d['version']} (copia interna della skill{(' in ' + ri['root']) if ri.get('root') else ''}) · controllo "
          f"{'dal vivo' if d.get('live') else 'offline (stato dell’ultimo check)'}. "
          "**Pronto** = il canale ha passato il controllo dal vivo nelle ultime 24 ore: i numeri letti valgono **[FATTO]** con URL e data.", ""]
    if ri.get("patches") and not ri.get("patches_ok"):
        L += [f"Attenzione: correzioni locali mancanti ({', '.join(k for k, v in ri['patches'].items() if v != 'ok')}): `! {me()} install`", ""]
    L += ["| Canale | Stato | Pronto | Da fare |", "|---|---|---|---|"]
    for r in d["rows"]:
        L.append(f"| {r['channel']} | {r['label']}{(' — Perché: ' + r['why']) if r.get('why') else ''} | {'sì' if r['ready'] else 'no'} | {('`' + r['next'] + '`') if r['next'] else ''}{(' · oppure, se il login nel browser dedicato è bloccato: `' + r['alt'] + '`') if r.get('alt') else ''} |")
    if any(r.get("alt") for r in d["rows"]):
        L += ["", f"Login copiato dal tuo browser normale (da un profilo che scegli tu): guida con `{me()} collega-browser`."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- login through the skill + browser language
# The internal copy is patched at install time (reach_runtime.py, patch "locale"): the dedicated browser takes its language from
# REACH_BROWSER_LOCALE, which this module always sets (default: this machine's language). `fix-lang` only checks that patch and sets
# the same language in the browser profile (pages already saved keep their language otherwise).
_LANG_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,2}$")


def skill_script() -> str:
    """Absolute path of reach.py as the owner must type it: the installed copy if there is one. Forward slashes (work in bash and cmd)."""
    inst = os.path.join(os.path.expanduser("~"), ".agents", "skills", "game-launch-strategist", "scripts", "research", "reach.py")
    return (inst if os.path.isfile(inst) else os.path.abspath(__file__)).replace("\\", "/")


def login_cmd(channel: str) -> str:
    """The command the owner types after `!` to log in to a channel through the skill."""
    return f"{me()} login {ALIASES.get(channel, channel)}"


def system_locale() -> str:
    """This machine's language as a BCP 47 tag (it-IT), or en-US when it cannot be read."""
    return rt.system_locale()


def wanted_lang(arg: str | None = None) -> str:
    """--lang, else the env REACH_BROWSER_LOCALE, else the system language, else en-US. Invalid values are ignored."""
    for v in (arg, os.environ.get("REACH_BROWSER_LOCALE")):
        if v and _LANG_RE.match(v.strip()):
            return v.strip()
    return system_locale()


def accept_languages(lang: str) -> str:
    out = []
    for x in (lang, lang.split("-")[0], "en-US", "en"):
        if x not in out:
            out.append(x)
    return ",".join(out)


def browser_status() -> dict:
    """Agent Reach's own `browser status`: {running, headless, profile_dir...} or {} when it cannot be read."""
    env = _exec(["browser", "status"], timeout=30)
    return (env.get("result") or {}) if env.get("ok") else {}


def profile_prefs_path(profile_dir: str | None) -> str:
    d = os.environ.get("GLS_REACH_PROFILE") or profile_dir or os.path.join(rt.state_home(), "browser", "profile")
    return os.path.join(d, "Default", "Preferences")


def patch_prefs(path: str, lang: str) -> dict:
    """Set the browser profile's accepted/selected languages. Call it only when the browser is NOT running (it rewrites the file on exit).
    One backup, Preferences.gls-backup. status: set | unchanged | missing (no profile yet) | error."""
    if not os.path.isfile(path):
        return dict(status="missing", path=path)
    want = accept_languages(lang)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        intl = data.setdefault("intl", {})
        before = {k: intl.get(k) for k in ("accept_languages", "selected_languages")}
        if before["accept_languages"] == want and before["selected_languages"] == want:
            return dict(status="unchanged", path=path, languages=want)
        backup = path + ".gls-backup"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        intl["accept_languages"] = intl["selected_languages"] = want
        tmp = path + ".gls-tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            json.dump(data, fh, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp, path)
    except (OSError, ValueError) as e:
        return dict(status="error", path=path, message=e.__class__.__name__)
    return dict(status="set", path=path, languages=want, was=before, backup=backup)


def stop_browser() -> bool:
    """Close the dedicated browser with Agent Reach's own command (`browser stop`); nothing else is ever killed."""
    env = _exec(["browser", "stop"], timeout=60)
    return bool(env.get("ok")) and not browser_status().get("running")


def locale_patch_status() -> str:
    """ok | missing | not_installed | test: is the language fix inside the internal copy?"""
    if _RUNNER or os.environ.get("GLS_REACH_FAKE"):
        return os.environ.get("GLS_REACH_LOCALE_PATCH", "ok")
    pkg = rt.package_dir()
    return rt.patch_status(pkg).get("locale", "missing") if pkg else "not_installed"


def fix_lang(lang: str | None = None, stop: bool = False, out=print) -> dict:
    """Check the language fix of the internal copy and set the browser profile languages. Returns the report; `out` prints Italian lines."""
    lang = wanted_lang(lang)
    ps = locale_patch_status()
    rep = dict(lang=lang, patch=ps, prefs=None, running=None)
    out({"ok": f"Lingua del browser: la copia interna di Agent Reach apre il browser in {lang} (correzione presente).",
         "missing": f"Lingua del browser: correzione MANCANTE nella copia interna. Rimettila con `! {me()} install`.",
         "not_installed": f"Lingua del browser: Agent Reach interno non installato. `! {me()} install`."}.get(ps, f"Lingua del browser: {ps}"))
    st = browser_status()
    running = rep["running"] = st.get("running")
    if running and stop:
        out("Il browser dedicato è acceso: lo chiudo con il suo comando (`browser stop`).")
        running = rep["running"] = not stop_browser()
    if running is None:
        out("Profilo del browser: non riesco a sapere se il browser è acceso, non lo tocco.")
    elif running:
        out(f"Profilo del browser: il browser dedicato è ACCESO, non tocco le sue impostazioni. Chiudilo con `! {me()} browser stop` "
            f"(oppure rilancia con --stop) e rifai `fix-lang`: così anche le pagine già salvate passano a {lang}.")
    else:
        r = rep["prefs"] = patch_prefs(profile_prefs_path(st.get("profile_dir")), lang)
        out("Profilo del browser: " + {"set": f"lingue impostate a {r.get('languages')} (prima: {(r.get('was') or {}).get('selected_languages')}); copia in {r.get('backup')}",
                                       "unchanged": f"già a posto ({r.get('languages')})", "missing": "nessun profilo ancora (si crea al primo login, con la lingua giusta)",
                                       "error": "non modificabile: " + str(r.get("message"))}[r["status"]])
    return rep


def _owner_call(args: list[str], lang: str | None = None, stdin: str | None = None, timeout: float = 900) -> dict:
    """One Agent Reach management command run for the owner (login, logout, add, configure): its stderr (QR codes, prompts) stays on
    screen, stdout is parsed. Always the internal copy, with REACH_BROWSER_LOCALE set."""
    if _RUNNER or os.environ.get("GLS_REACH_FAKE"):
        return _exec(args, stdin=stdin, timeout=timeout)
    if not tool_python():
        return _err("NOT_INSTALLED", "the internal Agent Reach copy is not installed", hint_it("NOT_INSTALLED", ""))
    try:
        r = subprocess.run(rt.argv(args), input=stdin, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           cwd=os.path.expanduser("~"), env=rt.env(lang))
    except subprocess.TimeoutExpired:
        return _err("TIMEOUT", f"agent-reach {args[0]} did not finish in {int(timeout // 60)} minutes")
    except OSError as e:
        return _err("NOT_INSTALLED", f"cannot run the internal agent-reach: {e.__class__.__name__}", hint_it("NOT_INSTALLED", ""))
    return _parse(r.stdout)


def _login_call(channel: str, lang: str) -> dict:
    return _owner_call(["login", channel], lang=lang, timeout=900)


def check_channel(channel: str) -> dict:
    """Live check of ONE channel (Agent Reach's check <ch>; TikTok through its probe) and its row of the doctor table."""
    global _DOCTOR
    if channel == "tiktok":
        env = _exec(["__tiktok__", "profile", "tiktok"], timeout=90)
        _note_tiktok(bool(env.get("ok")), (env.get("error") or {}).get("code"))
    else:
        env = _exec(["check", channel, "--timeout", "60"], timeout=300)     # always live; only Agent Reach's own 1-hour rate-limit pause skips it
        if env.get("results"):
            _note_diag(channel, env)
    _DOCTOR = None
    return next((r for r in doctor(False)["rows"] if r["channel"] == channel), dict(channel=channel, ready=False, label="sconosciuto", next=""))


def _print_row(row: dict, out=print):
    out(f"Canale {row['channel']}: {row['label']}." + ("" if row.get("ready") else f" Non ancora pronto{(' - ' + row['next']) if row.get('next') else ''}"))
    if row.get("why") and not row.get("ready"):
        out(f"  Perché: {row['why']}.")


def login(channel: str, lang: str | None = None, wait: bool = True, check_only: bool = False, out=print) -> int:
    """The login flow run by the OWNER: browser language, Agent Reach's login window (internal copy), then the channel check.
    It never types credentials and never reads cookies: the login itself is done by the owner in the window."""
    ch = ALIASES.get(channel, channel)
    target = "twitter" if ch == "tiktok" else ch
    if not enabled():
        out("Agent Reach interno non installato. " + hint_it("NOT_INSTALLED", ch))
        return 2
    if check_only:
        row = check_channel(ch)
        _print_row(row, out)
        return 0 if row.get("ready") else 1
    lang = wanted_lang(lang)
    st = browser_status()
    # a background (headless) browser is closed with Agent Reach's own command so its language can change; a visible window is never closed
    fix_lang(lang, stop=bool(st.get("running") and st.get("headless")), out=out)
    out(f"Apro la finestra di login di {target}... (utente e password li scrivi tu, non passano da qui)")
    env = _login_call(target, lang)
    if not env.get("ok"):
        e = env.get("error") or {}
        out(f"Login non partito [{e.get('code', '?')}]: {it_text(e.get('message', ''), e.get('code'))[:200]} {it_text(e.get('hint', ''), e.get('code'))}".strip())
        return 3
    item = (env.get("items") or [{}])[0]
    out(f"Finestra aperta{(': ' + str(item.get('opened'))) if item.get('opened') else ''}. Fai il login da solo (account secondario consigliato).")
    if item.get("next") and not _CJK.search(str(item["next"])):
        out("Indicazione di Agent Reach: " + str(item["next"])[:300])
    if ch == "tiktok":
        out("TikTok: nella STESSA finestra apri https://www.tiktok.com/login e fai il login anche lì.")
    if wait and sys.stdin and sys.stdin.isatty():
        try:
            input("Quando hai finito il login premi Invio per controllare... ")
        except EOFError:
            pass
        else:
            row = check_channel(ch)
            _print_row(row, out)
            return 0 if row.get("ready") else 1
    out(f"Quando hai finito il login, controlla con:  ! {me()} login {ch} --check")
    return 0


# ---------------------------------------------------------------- login copied from the owner's normal browser
# Agent Reach reads a site's login from the owner's normal Chrome/Edge through the OpenCLI "Browser Bridge" extension and copies ONLY
# that site into the dedicated browser (`login <ch> --import-existing`, runtime/session_reuse.py). The owner's browser is never changed.
# The bridge daemon runs only while the dedicated browser is open: `_ensure_bridge` turns it on (invisible window) when it is not.
# The SOURCE browser profile is always chosen by the owner (`browser use ID` or `--profilo ID`), never guessed, even with one profile.
# The bridge only knows a profile by its OpenCLI id (no name, no e-mail): the id is shown in the extension popup of that profile.
# Nothing here reads or prints cookie values: Agent Reach answers with counts, and error texts never carry cookies.
IMPORT_FALLBACK = ("twitter", "instagram", "reddit", "facebook", "xiaohongshu", "linkedin", "boss", "xueqiu")
EXTENSION_STORE = "https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk"
PROFILE_WAIT = 30.0          # seconds to wait for the owner's extension to connect to the bridge (it retries every few seconds)
_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_ALL = ("tutti", "all", "tutto")


def import_channels() -> list[str]:
    """Channels whose login can be copied from the owner's browser: every Agent Reach channel with a browser login, plus tiktok."""
    names = [n for n, c in channels_info().items() if isinstance(c.get("login"), dict) and c["login"].get("via") == "browser"]
    names = names or list(IMPORT_FALLBACK)
    return [n for n in names if n != "tiktok"] + ["tiktok"]


def alt_cmd(channel: str) -> str:
    """The alternative the owner can type when the dedicated browser's login is blocked."""
    return f"{login_cmd(channel)} --dal-mio-browser"


def extension_dir() -> str:
    """Where Agent Reach keeps the OpenCLI extension (unpacked). Stable: it is only replaced by an explicit extension upgrade."""
    return os.path.normpath(os.path.join(rt.state_home(), "browser", "extension"))


def chosen_profile() -> str | None:
    """The source profile the owner chose with `browser use` / `--profilo` (kept in the skill's own state), or None."""
    v = _state().get("source_profile")
    return v if isinstance(v, str) and _ID_RE.match(v) else None


def _save_chosen(profile: str):
    s = _state()
    s["source_profile"] = profile
    _save_state(s)


def _ensure_bridge(out=print) -> bool:
    """The bridge daemon lives with the dedicated browser: turn that on (invisible) when it is off. A visible login window is never touched."""
    if browser_status().get("running"):
        return True
    out("Accendo il browser dedicato (invisibile) per collegare il tuo browser normale...")
    env = _owner_call(["browser", "setup"], timeout=240)
    if not env.get("ok"):
        e = env.get("error") or {}
        out(f"Non riuscito [{e.get('code', '?')}]: {it_text(e.get('message', ''), e.get('code'))[:200]} {it_text(e.get('hint', ''), e.get('code'))}".strip())
        return False
    return True


def source_profiles(wait: float | None = None) -> tuple[list[str], list[str], dict]:
    """(your browsers connected to the bridge, the dedicated one, raw answer). Waits for the owner's extension while there is none."""
    end = time.time() + (PROFILE_WAIT if wait is None else wait)
    while True:
        env = _exec(["browser", "profiles"], timeout=30)
        rows = (env.get("result") or {}).get("profiles") or [] if env.get("ok") else []
        mine = [str(r.get("id")) for r in rows if not r.get("dedicated")]
        if mine or not env.get("ok") or time.time() >= end:
            return mine, [str(r.get("id")) for r in rows if r.get("dedicated")], env
        time.sleep(3)


def _fail_line(env: dict) -> str:
    e = env.get("error") or {}
    msg = it_text(e.get("message", ""), e.get("code"))[:200]
    if "choose a connected local browser profile" in str(e.get("message", "")).lower():
        msg = "quell'ID non è un tuo browser collegato (o è il browser dedicato)"
    return f"Non riuscito [{e.get('code', '?')}]: {msg}"


def browser_profiles(out=print) -> int:
    """`browser profiles`: which browsers the bridge sees. Yours = the Chrome profile where the OpenCLI extension is loaded."""
    if not enabled():
        out("Agent Reach interno non installato. " + hint_it("NOT_INSTALLED", ""))
        return 2
    if not _ensure_bridge(out):
        return 3
    mine, ded, env = source_profiles()
    if not env.get("ok"):
        out(_fail_line(env))
        return 3
    pick = chosen_profile()
    for i in ded:
        out(f"- {i}: browser dedicato di Agent Reach (non è il tuo, non va scelto)")
    for i in mine:
        out(f"- {i}: un TUO profilo di Chrome/Edge con l'estensione OpenCLI" + ("   <== SCELTO come sorgente dei login" if i == pick else ""))
    if mine:
        out("Il ponte non conosce nome o e-mail del profilo, solo questo ID. Per riconoscerlo: nel profilo giusto clicca l'icona OpenCLI "
            "(puzzle in alto a destra, poi OpenCLI): la riga \"Profile\" mostra lo stesso ID.")
    if not mine:
        out(f"Nessun tuo profilo è collegato (l'estensione manca o non ha ancora trovato il ponte). Guida: `! {me()} collega-browser`")
        return 1
    if pick and pick not in mine:
        out(f"Attenzione: il profilo scelto ({pick}) adesso non è collegato: apri quel profilo di Chrome (o scegline un altro con `browser use ID`).")
    elif not pick:
        out(f"Non hai ancora scelto la sorgente. Anche se ne vedi uno solo, scegli tu: `! {me()} browser use ID`")
    return 0


def browser_use(profile: str, out=print) -> int:
    """`browser use ID`: choose the Chrome profile the logins are copied from. Always explicit: copying refuses to run without it."""
    if not enabled():
        out("Agent Reach interno non installato. " + hint_it("NOT_INSTALLED", ""))
        return 2
    if not profile or not _ID_RE.match(profile):
        out(f"Serve l'ID di un tuo profilo, come lo mostra `! {me()} browser profiles`.")
        return 2
    if not _ensure_bridge(out):
        return 3
    env = _owner_call(["browser", "use", profile], timeout=60)
    if not env.get("ok"):
        out(_fail_line(env) + f" (controlla l'ID con `! {me()} browser profiles`)")
        return 3
    _save_chosen(profile)
    out(f"Profilo sorgente scelto: {profile}. Da lì si leggono solo i login dei siti che chiedi; il tuo browser non viene modificato.")
    return 0


def import_one(channel: str) -> dict:
    """Copy one site's login from the owner's browser: {channel, state: copied|none|choose|bridge|error, n, code, message}. No cookie values."""
    env = _exec(["__tiktok_import__"], timeout=120) if channel == "tiktok" else _owner_call(["login", channel, "--import-existing"], timeout=180)
    if env.get("ok"):
        n = int((env.get("result") or {}).get("copied_cookies") or 0)
        # "copied N cookies" is not "logged in": look (by name) whether the cookie only a logged-in user has is really in the dedicated browser
        has = login_cookie_state([channel]).get(channel)
        return dict(channel=channel, state="nologin" if has is False else "copied", n=n, cookie=LOGIN_COOKIE.get(channel, ("", ("",)))[1][0])
    e = env.get("error") or {}
    low = str(e.get("message", "")).lower()
    state = ("none" if "no local browser login" in low else "choose" if "several local browsers" in low else
             "bridge" if "bridge" in low or e.get("code") == "NOT_INSTALLED" else "error")
    return dict(channel=channel, state=state, n=0, code=e.get("code"), message=it_text(e.get("message", ""), e.get("code"))[:160])


def import_line(r: dict) -> str:
    ch = r["channel"]
    site = SITE_NAME.get(ch, ch)
    return {"copied": f"{ch}: login copiato ({r.get('n')} voci)",
            "nologin": f"{ch}: copiate {r.get('n')} voci ma NON il login (manca il cookie `{r.get('cookie')}`): in quel profilo di Chrome non risulti dentro a {site}, "
                       f"o la sessione è scaduta. Entra in {site} in QUEL profilo, poi ripeti. Non controllo il canale: sarebbe una richiesta sprecata",
            "none": f"{ch}: nessun login trovato in quel profilo (fai il login su quel sito in quel profilo di Chrome, poi riprova)",
            "choose": f"{ch}: più browser hanno un login di questo sito: scegli con `! {me()} browser use ID`",
            "bridge": f"{ch}: il ponte non è attivo (browser dedicato spento o estensione scollegata): riprova, oppure `! {me()} collega-browser`",
            }.get(r["state"], f"{ch}: errore [{r.get('code') or '?'}] {r.get('message') or ''}".strip())


def login_from_browser(channel: str, profile: str | None = None, out=print) -> int:
    """`login <canale|tutti> --dal-mio-browser [--profilo ID]`: copy the login(s) from the owner's CHOSEN Chrome profile, then check each one.
    Refuses to run when no source profile was chosen by the owner (`browser use ID` or `--profilo ID`), even if only one is connected."""
    global _DOCTOR
    ch = "tutti" if channel.lower() in _ALL else ALIASES.get(channel, channel)
    if not enabled():
        out("Agent Reach interno non installato. " + hint_it("NOT_INSTALLED", ch))
        return 2
    can = import_channels()
    if ch == "bilibili":
        out("bilibili: non si copia con un comando. Prende da solo il login dal profilo collegato (se sei dentro a bilibili.com) quando serve; "
            f"altrimenti `! {login_cmd('bilibili')}` (QR).")
        return 2
    if ch != "tutti" and ch not in can:
        out(f"{ch}: non ha un login da copiare dal browser (canali possibili: {', '.join(can)}, oppure `tutti`).")
        return 2
    if profile is not None and not _ID_RE.match(profile):
        out(f"--profilo vuole l'ID di un tuo profilo, come lo mostra `! {me()} browser profiles`.")
        return 2
    pick = profile or chosen_profile()
    if not pick:
        out("Mi fermo: non hai ancora scelto da QUALE profilo di Chrome copiare i login (non lo scelgo io, nemmeno se ne vedo uno solo).\n"
            f"  1. `! {me()} browser profiles`  (elenca i tuoi profili collegati)\n"
            f"  2. `! {me()} browser use ID`    (oppure aggiungi `--profilo ID` a questo comando)\n"
            f"  Se non hai ancora collegato il browser: `! {me()} collega-browser`")
        return 5
    todo = can if ch == "tutti" else [ch]
    if not _ensure_bridge(out):
        return 3
    mine, _, env = source_profiles()
    if not mine:
        out("Non vedo il tuo browser normale: l'estensione OpenCLI non è collegata al ponte. "
            f"Guida passo per passo: `! {me()} collega-browser`")
        return 4
    if pick not in mine:
        out(f"Il profilo scelto ({pick}) adesso non è collegato. Collegati ora: {', '.join(mine)}. "
            f"Apri il profilo di Chrome giusto e riprova, oppure scegline un altro: `! {me()} browser use ID`")
        return 4
    use_env = _owner_call(["browser", "use", pick], timeout=60)          # makes Agent Reach read ONLY this profile
    if not use_env.get("ok"):
        out(_fail_line(use_env))
        return 3
    _save_chosen(pick)
    out(f"Copio i login dal profilo scelto: {pick} (il Chrome dove hai caricato l'estensione). Siti: {', '.join(todo)}. Il tuo browser non cambia.")
    results = [import_one(c) for c in todo]
    for r in results:
        out("- " + import_line(r))
    copied = [r["channel"] for r in results if r["state"] == "copied"]
    ok = True
    for c in copied:
        _DOCTOR = None
        if c != "tiktok" and status(c) == "not_added":
            out(f"Attivo il canale {c} (installa quello che serve)...")
            _owner_call(["add", c], timeout=900)
        row = check_channel(c)
        _print_row(row, out)
        ok = ok and bool(row.get("ready"))
    if not copied:
        out("Nessun login copiato." + ("" if ch != "tutti" else " Fai il login nel profilo scelto sui siti che vuoi, poi ripeti."))
        return 1
    return 0 if ok else 1


def connect_browser_text() -> str:
    """The owner steps to connect his normal browser (shown by `collega-browser`)."""
    ext = extension_dir()
    ext_ok = os.path.isfile(os.path.join(ext, "manifest.json"))
    where = (f"""scegli la cartella:
         {ext}
      Non spostarla e non cancellarla. Se un giorno Agent Reach la aggiorna, il percorso resta lo stesso ma devi premere
      "Ricarica" sulla scheda OpenCLI in chrome://extensions.""" if ext_ok else
             f"""scegli la cartella dell'estensione: non c'è ancora, la prepara `! {me()} browser profiles` (poi ripeti qui, la cartella è
      {ext}).""")
    manual = f"""   B) Senza negozio: apri chrome://extensions (Edge: edge://extensions), attiva "Modalità sviluppatore", poi
      "Carica estensione non pacchettizzata" (Edge: "Carica estensione decompressa") e {where}"""
    return f"""# Collega UN profilo del tuo browser normale (copia del login, per quando X o altri bloccano il browser dedicato)

Serve una volta sola. Il login lo fai tu, nel tuo Chrome/Edge di tutti i giorni; la skill copia nel browser dedicato solo il sito che
chiedi, e SOLO dal profilo che scegli tu (mai uno scelto da me). Il tuo browser non viene modificato. Account secondario consigliato.

1. Apri il profilo di Chrome che vuoi usare (icona del profilo in alto a destra, poi scegli il profilo: ogni profilo ha la sua finestra).
   Installa l'estensione "OpenCLI" (il ponte ufficiale di Agent Reach) SOLO in quel profilo:
   A) Dal negozio (più semplice): apri {EXTENSION_STORE}  e premi "Aggiungi a Chrome"
      (in Edge: prima edge://extensions, attiva "Consenti estensioni da altri negozi", poi lo stesso link).
{manual}
   Attenzione: l'estensione ha permessi larghi (cookie, debugger, tutti i siti). Quando hai finito puoi toglierla o disattivarla.
   Se la metti in due profili, il ponte li vede entrambi e devi scegliere (punto 3).
2. In quello stesso profilo fai il login normale sui siti che vuoi: x.com, instagram.com, tiktok.com, reddit.com...
3. Elenca i profili collegati e scegli (accende da solo il browser dedicato invisibile, aspetta fino a {int(PROFILE_WAIT)} secondi):
   `! {me()} browser profiles`
   Il ponte conosce solo un ID (niente nome o e-mail). Per riconoscerlo: nel profilo giusto clicca l'icona OpenCLI (puzzle in alto a
   destra, poi OpenCLI): la riga "Profile" mostra lo stesso ID.
   `! {me()} browser use ID`        <- OBBLIGATORIO, anche se ne vedi uno solo: senza questa scelta la copia non parte.
4. Copia il login (mostra da quale profilo copia, prima di copiare):
   `! {me()} login twitter --dal-mio-browser`        (un sito: twitter, instagram, tiktok, reddit, facebook, xiaohongshu, linkedin, boss, xueqiu)
   `! {me()} login tutti --dal-mio-browser`          (tutti quelli che trovi in quel profilo; per gli altri scrive "nessun login trovato")
   Puoi anche passare il profilo al volo: `... --dal-mio-browser --profilo ID`. Alla fine controlla da solo ogni canale copiato;
   per rifarlo: `! {me()} login twitter --check`
5. Se il login scade o cambi account: ripeti il punto 4 (rilegge il profilo e sostituisce la copia).

Nota: il ponte c'è solo mentre il browser dedicato è acceso (lo accendono questi comandi). Bilibili prende il login da solo dal profilo
collegato quando serve. Se l'estensione è in un solo profilo, Agent Reach può anche riusare i suoi login da solo durante le ricerche:
per questo va caricata solo nel profilo che vuoi usare.
"""


def owner_cmd(cmd: str, arg: str | None = None, out=print) -> int:
    """add <channel> | logout <channel> | configure <key> | browser status|stop, through the internal copy, with Italian output."""
    if not enabled():
        out("Agent Reach interno non installato. " + hint_it("NOT_INSTALLED", ""))
        return 2
    if cmd == "configure":
        import getpass
        try:
            value = getpass.getpass(f"Valore per {arg} (non si vede mentre scrivi, non passa dalla chat): ")
        except (EOFError, KeyboardInterrupt):
            value = ""
        if not value:
            out("Nessun valore: niente di cambiato.")
            return 1
        env = _owner_call(["configure", arg, "--stdin"], stdin=value, timeout=60)
        value = ""
    elif cmd == "browser":
        env = _exec(["browser", arg], timeout=60)
    else:
        env = _owner_call([cmd, ALIASES.get(arg, arg)], timeout=900)
    if not env.get("ok"):
        e = env.get("error") or {}
        out(f"Non riuscito [{e.get('code', '?')}]: {it_text(e.get('message', ''), e.get('code'))[:200]}")
        return 3
    done = {"add": f"canale {arg} aggiunto: controlla con `{me()} doctor --live`", "logout": f"uscito da {arg} (login rimosso dal browser dedicato)",
            "configure": f"{arg} salvato nella cartella privata di Agent Reach (non viene mai mostrato)"}
    if cmd == "browser":
        res = env.get("result") or {}
        out("Browser dedicato: " + ("acceso" if res.get("running") else "spento") + (f" ({'invisibile' if res.get('headless') else 'finestra visibile'})" if res.get("running") else ""))
    else:
        out(done.get(cmd, "fatto"))
    return 0


def install_runtime(out=print) -> int:
    """`reach.py install`: build or repair the internal copy (same step the skill installer runs)."""
    try:
        rep = rt.install(update=True, log=out)
    except RuntimeError as e:
        out("Installazione di Agent Reach interno non riuscita: " + str(e))
        return 1
    bad = [k for k, v in (rep.get("patches") or {}).items() if v not in ("ok", "patched")]
    out(f"Agent Reach interno {rep['version']} pronto in {rep['root']}" + (f" (correzioni non applicate: {', '.join(bad)})" if bad else ""))
    return 0 if rep.get("installed") and not bad else 1


def setup_text() -> str:
    L = lambda ch: login_cmd(ch)
    return f"""# Agent Reach: comandi che lancia il proprietario (mai Claude al posto suo)

Agent Reach è un componente interno della skill: non c'è nessun programma `agent-reach` da installare o lanciare a parte.
Si usa SOLO questo file: `{me()}`. Login e cookie non passano mai dalla chat. Ogni comando si lancia nella chat con `!` davanti
(gira nel tuo terminale). Usa un **account secondario**: le piattaforme possono limitare gli account usati da programmi.
Il browser dedicato si apre nella tua lingua (di serie {wanted_lang()}).

1. Installazione o riparazione (se manca; lo fa anche l'aggiornamento della skill):  `! {me()} install`
2. Social con login, una volta sola (si apre una finestra del browser dedicato, il login lo fai tu):
   - X / Twitter:   `! {L("twitter")}`
   - Instagram:     `! {L("instagram")}`
   - Reddit (dati del sito, punteggi veri): `! {L("reddit")}`
   - XiaoHongShu:   `! {L("xiaohongshu")}`
   - Facebook:      `! {L("facebook")}`
   - Bilibili (sottotitoli): `! {L("bilibili")}` (QR)
   - TikTok: `! {L("tiktok")}`  (si apre la finestra di X: nella stessa finestra apri https://www.tiktok.com/login e fai il login anche lì;
     stesso browser dedicato; TikTok passa da OpenCLI, è sperimentale)
   Finito il login, se il comando non ha aspettato: `! {me()} login <canale> --check`
   Se la piattaforma blocca il login nel browser dedicato (succede con X): copia il login dal TUO Chrome/Edge, da un profilo che scegli tu:
   `! {me()} collega-browser` (guida), poi `! {me()} browser profiles`, `! {me()} browser use ID`, `! {me()} login twitter --dal-mio-browser`
   (o `login tutti --dal-mio-browser` per ogni sito in cui sei già dentro).
3. Aggiungere un canale senza login (es. linkedin, xueqiu): `! {me()} add <canale>`
4. Chiavi facoltative (testo nascosto, mai in chat): `! {me()} configure groq-key` (trascrizione dei video senza sottotitoli)
5. Verifica: `! {me()} doctor --live`  → tabella pronto / non pronto
6. Se un login scade: rifai il punto 2 per quel canale. Per uscire: `! {me()} logout <canale>`.
7. Browser dedicato: `! {me()} browser status` / `! {me()} browser stop` / `! {me()} browser profiles`; lingua del profilo: `! {me()} fix-lang` (`--lang it-IT`).
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
    sp.add_parser("setup"); sp.add_parser("channels"); sp.add_parser("install"); sp.add_parser("collega-browser")
    lg = sp.add_parser("login"); lg.add_argument("channel", help="canale, oppure 'tutti' con --dal-mio-browser"); lg.add_argument("--lang"); lg.add_argument("--check", action="store_true"); lg.add_argument("--no-wait", action="store_true")
    lg.add_argument("--dal-mio-browser", dest="from_browser", action="store_true", help="copia il login dal profilo di Chrome/Edge scelto con `browser use ID`")
    lg.add_argument("--profilo", help="ID del profilo sorgente (come `browser profiles`), alternativa a `browser use ID`")
    fl = sp.add_parser("fix-lang"); fl.add_argument("--lang"); fl.add_argument("--stop", action="store_true")
    for name in ("add", "logout"):
        x = sp.add_parser(name); x.add_argument("channel")
    cf = sp.add_parser("configure"); cf.add_argument("key", help="groq-key | openai-key | proxy | github-token | browser-port")
    br = sp.add_parser("browser"); br.add_argument("op", choices=["status", "stop", "profiles", "use"]); br.add_argument("profile", nargs="?", help="ID del profilo (solo per `use`)")
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
    if a.cmd == "install":
        return install_runtime()
    if a.cmd == "collega-browser":
        print(connect_browser_text())
        return 0
    if a.cmd == "login":
        if a.profilo and not a.from_browser:
            print("--profilo si usa con --dal-mio-browser.")
            return 2
        if a.from_browser:
            return login_from_browser(a.channel, a.profilo)
        if a.channel.lower() in _ALL:
            print("`tutti` si usa solo con --dal-mio-browser (ogni sito ha il suo login: uno alla volta senza).")
            return 2
        return login(a.channel, a.lang, wait=not a.no_wait, check_only=a.check)
    if a.cmd in ("add", "logout"):
        return owner_cmd(a.cmd, a.channel)
    if a.cmd == "configure":
        return owner_cmd("configure", a.key)
    if a.cmd == "browser":
        if a.profile and a.op != "use":
            print("L'ID del profilo serve solo a `browser use ID`.")
            return 2
        if a.op == "profiles":
            return browser_profiles()
        if a.op == "use":
            return browser_use(a.profile or "")
        return owner_cmd("browser", a.op)
    if a.cmd == "fix-lang":
        rep = fix_lang(a.lang, a.stop)
        return 0 if rep["patch"] == "ok" else 1
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
