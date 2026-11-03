#!/usr/bin/env python3
"""Reddit, read-only, through a chain of backends: the first one that answers wins and the result says which one it was.

Why a chain: Reddit answers 403 / a login page to anonymous scripts more and more often (JSON endpoints), rate limits the RSS
feeds (429), and Agent Reach's Reddit channel needs the owner's login in its browser. No single route is reliable, so every
Reddit tool of the skill (reddit_trends, reddit_rules, case_studies fetch, market_tracker) asks this module and reports the
backend used. Nothing here ever posts, votes, comments or logs in. Blocks are never bypassed: a 401/403/429 takes that backend
out for the rest of the run and the next one is tried.

Backends, in order (override with --backends or env GLS_REDDIT_BACKENDS="arctic,rss"; for "new" listings rss comes before arctic,
because the archive can lag a few hours):
  reach        Agent Reach's Reddit channel with the owner's login (`! agent-reach login reddit`): real upvotes, comments.
               Used only when `reach.py doctor` says reddit is ready.
  oauth        official API, app-only OAuth (REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in the private keys file): real numbers.
  json         public JSON (www.reddit.com, then old.reddit.com) with a descriptive User-Agent. Often 403 / login redirect now.
  rss          public Atom feeds (subreddit top/new, thread with its comments, search): no scores, rank is the signal.
  arctic       Arctic Shift (https://arctic-shift.photon-reddit.com), public archive of Reddit, no key: posts, comment trees,
               subreddit info. Scores are the archive's (taken some hours after posting, may be lower than today's).
  threadsnoop  ThreadSnoop read API (https://threadsnoop.com), only with THREADSNOOP_API_KEY in the private keys file
               (1 credit per request, 1,000 free). Same data as an archive; from the owner's suggestion threadsnoop/reddit-skills,
               which is only a SKILL.md (no code) describing this API.
  reach_public Agent Reach's public web route: the page text as visitors see it (rules, post text). No numbers.

  reddit_backends.py thread <url-or-id> [--limit 200]                         post + comments
  reddit_backends.py rules <sub>                                              subreddit rules (+ subscribers)
  reddit_backends.py listing <sub> [--kind top|new] [--t week|month|year] [--limit 100]
  reddit_backends.py search <query> [--sub IndieDev] [--limit 25]
  reddit_backends.py doctor                                                   which backends answer now (one light call each)
  common: --backends reach,oauth,json,rss,arctic,threadsnoop,reach_public  --rate 3  --env-file  -o out.json

Every result: ok, backend, label ([FATTO] with URL and date, or [DA VERIFICARE]), consulted, scores ("real" / "archive" /
"none"), attempts [[backend, outcome], ...].
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html as htmlmod
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET

import common
from common import Throttle, log, write_json

ORDER = ["reach", "oauth", "json", "arctic", "rss", "threadsnoop", "reach_public"]
ARCTIC = "https://arctic-shift.photon-reddit.com/api"
THREADSNOOP = "https://api.threadsnoop.com/v1"
UA = "game-launch-strategist/1.0 (indie launch research; read-only; low volume)"
ATOM = "{http://www.w3.org/2005/Atom}"
SCORES = dict(reach="real", oauth="real", json="real", rss="none", arctic="archive", threadsnoop="archive", reach_public="none")
_DOWN: dict = {}           # backend -> reason, for the rest of this process
_TH: dict = {}
OPTS = dict(rate=3.0, backends=None)


def configure(**kw):
    for k, v in kw.items():
        if k in OPTS and v is not None:
            OPTS[k] = v


def reset():
    """Tests: forget blocked backends and throttles."""
    _DOWN.clear()
    _TH.clear()


def ua() -> str:
    return os.environ.get("REDDIT_USER_AGENT") or UA


def order(only: list[str] | None = None) -> list[str]:
    o = only or OPTS["backends"] or [x.strip() for x in os.environ.get("GLS_REDDIT_BACKENDS", "").split(",") if x.strip()] or ORDER
    return [b for b in o if b in ORDER]


def _reach():
    import reach
    return reach


def available(b: str) -> bool:
    if b in _DOWN:
        return False
    if b == "reach":
        r = _reach()
        return r.enabled() and r.ready("reddit")
    if b == "reach_public":
        return _reach().enabled()
    if b == "oauth":
        return common.has_key("REDDIT_CLIENT_ID") and common.has_key("REDDIT_CLIENT_SECRET")
    if b == "threadsnoop":
        return common.has_key("THREADSNOOP_API_KEY")
    if b == "arctic":
        return os.environ.get("GLS_ARCTIC", "").lower() not in ("off", "0", "no")
    return True


def _get(b: str, url: str, headers: dict | None = None, raw: bool = False):
    """One polite request for backend b (own throttle, 2 retries with backoff inside common.http_get)."""
    if b not in _TH:
        _TH[b] = Throttle(float(OPTS["rate"]))
    h = {"User-Agent": ua(), "Accept": "application/json" if not raw else "application/atom+xml, text/xml;q=0.9, */*;q=0.5"}
    h.update(headers or {})
    data = common.http_get(url, headers=h, throttle=_TH[b], retries=2, timeout=40)
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
    if raw:
        if text.lstrip()[:200].lower().startswith(("<!doctype html", "<html", "<body")):
            raise BlockPage("HTML page instead of a feed")
        return text
    if text.lstrip()[:1] not in ("{", "["):
        raise BlockPage("HTML page instead of JSON (block or login wall)")
    d = json.loads(text)
    if isinstance(d, dict) and d.get("error") and d.get("data") is None:
        raise BlockPage(str(d.get("error"))[:120])
    return d


class BlockPage(Exception):
    pass


class Empty(Exception):
    pass


def _fail(b: str, e: Exception) -> str:
    code = getattr(e, "code", None)
    out = f"HTTP {code}" if code else f"{type(e).__name__}: {str(e)[:120]}"
    if code in (401, 403, 429) or isinstance(e, BlockPage) or (code is None and "Too many requests" in str(e)):
        _DOWN[b] = out          # never retried around a block in this run
    return out


def _chain(what: str, fns: dict, only: list[str] | None = None) -> dict:
    attempts = []
    for b in order(only):
        if b not in fns:
            continue
        if not available(b):
            attempts.append([b, "non disponibile" + (f" ({_DOWN[b]})" if b in _DOWN else "")])
            continue
        try:
            res = fns[b]()
        except Empty as e:
            attempts.append([b, f"vuoto: {e}"])
            continue
        except Exception as e:  # noqa: BLE001
            attempts.append([b, _fail(b, e)])
            continue
        attempts.append([b, "ok"])
        return dict(res, ok=True, backend=b, scores=SCORES[b], label="[FATTO]", consulted=dt.date.today().isoformat(), attempts=attempts, what=what)
    return dict(ok=False, backend=None, scores="none", label="[DA VERIFICARE]", consulted=dt.date.today().isoformat(), attempts=attempts, what=what)


# ---------------------------------------------------------------- shapes
def _date(ts) -> str | None:
    try:
        return common.ts_to_date(int(float(ts))) if ts not in (None, "") else None
    except (ValueError, OSError, OverflowError):
        return None


def post_of(x: dict) -> dict:
    """A Reddit-shaped post (API, JSON, Arctic Shift, ThreadSnoop) -> the skill's post."""
    pid = str(x.get("id") or "").removeprefix("t3_")
    perma = x.get("permalink") or (f"/r/{x.get('subreddit')}/comments/{pid}/" if pid and x.get("subreddit") else "")
    hidden = bool(x.get("hide_score"))
    return dict(id=pid, title=htmlmod.unescape(x.get("title") or ""), author=x.get("author"), subreddit=x.get("subreddit"),
                score=None if hidden else x.get("score"), score_hidden=hidden, num_comments=x.get("num_comments"),
                published=_date(x.get("created_utc")), url=("https://www.reddit.com" + perma) if perma.startswith("/") else perma or None,
                link=x.get("url_overridden_by_dest") or x.get("url"), text=htmlmod.unescape(x.get("selftext") or "")[:6000] or None,
                removed=bool(x.get("removed_by_category")) or (x.get("selftext") in ("[removed]", "[deleted]")),
                raw={k: x.get(k) for k in ("post_hint", "is_video", "is_gallery", "is_self", "domain", "url", "url_overridden_by_dest", "link_flair_text") if k in x})


def comments_of(children, depth: int = 0, out: list | None = None, limit: int = 500) -> list[dict]:
    """Reddit comment listing (t1 with nested replies) -> flat list with depth."""
    out = [] if out is None else out
    for c in children or []:
        if len(out) >= limit:
            break
        if not isinstance(c, dict) or c.get("kind") not in (None, "t1"):
            continue
        d = c.get("data", c)
        if not d.get("body"):
            continue
        hidden = bool(d.get("score_hidden"))
        out.append(dict(id=d.get("id"), author=d.get("author"), score=None if hidden else d.get("score"), body=htmlmod.unescape(d["body"])[:3000],
                        depth=depth, published=_date(d.get("created_utc"))))
        r = d.get("replies")
        kids = r.get("data", {}).get("children") if isinstance(r, dict) else r if isinstance(r, list) else None
        if kids:
            comments_of(kids, depth + 1, out, limit)
    return out


def thread_text(post: dict, comments: list[dict]) -> str:
    return ((post.get("text") or "") + "".join(f"\n@{c.get('author') or ''}: {c.get('body') or ''}" for c in comments)).strip()


def thread_id(target: str) -> str | None:
    m = re.search(r"/comments/([a-z0-9]{2,10})", target) or re.search(r"redd\.it/([a-z0-9]{2,10})", target)
    if m:
        return m.group(1)
    t = target.strip().removeprefix("t3_")
    return t if re.fullmatch(r"[a-z0-9]{2,10}", t) else None


def parse_atom(text: str) -> list[dict]:
    i = text.find("<")
    root = ET.fromstring(text[i:] if i > 0 else text)
    out = []
    for e in root.findall(f"{ATOM}entry"):
        link = e.find(f"{ATOM}link")
        body = re.sub(r"<[^>]+>", " ", htmlmod.unescape(e.findtext(f"{ATOM}content") or ""))
        body = re.sub(r"\s+", " ", body).replace("submitted by", "").strip()
        out.append(dict(id=(e.findtext(f"{ATOM}id") or "").removeprefix("t3_").removeprefix("t1_"), title=(e.findtext(f"{ATOM}title") or "").strip(),
                        author=(e.findtext(f"{ATOM}author/{ATOM}name") or "").removeprefix("/u/") or None,
                        url=link.get("href") if link is not None else None, published=(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated") or "")[:10] or None,
                        text=body[:3000] or None, html=e.findtext(f"{ATOM}content") or "", score=None))
    return out


# ---------------------------------------------------------------- oauth
_TOKEN: dict = {}


def oauth_headers() -> dict:
    if _TOKEN.get("exp", 0) > time.time():
        return _TOKEN["h"]
    cid, sec = os.environ.get("REDDIT_CLIENT_ID", "").strip(), os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    tok = json.loads(common.http_get("https://www.reddit.com/api/v1/access_token", data=body, method="POST",
                                     headers={"Authorization": f"Basic {auth}", "User-Agent": ua()}))["access_token"]
    _TOKEN.update(h={"Authorization": f"Bearer {tok}"}, exp=time.time() + 3000)
    return _TOKEN["h"]


def _threadsnoop_h() -> dict:
    return {"x-api-key": os.environ.get("THREADSNOOP_API_KEY", "").strip()}


# ---------------------------------------------------------------- thread: post + comments
def thread(target: str, limit: int = 200, only: list[str] | None = None) -> dict:
    tid = thread_id(target)
    url = target if "://" in target else (f"https://www.reddit.com/comments/{tid}/" if tid else target)
    if not tid:
        return dict(ok=False, backend=None, label="[DA VERIFICARE]", attempts=[["-", "non è il link di un post Reddit"]], what="thread", scores="none",
                    consulted=dt.date.today().isoformat())

    def listing_pair(d):
        post = post_of(d[0]["data"]["children"][0]["data"])
        com = comments_of(d[1]["data"]["children"], limit=limit)
        return dict(post=post, comments=com, text=thread_text(post, com), url=post["url"] or url)

    def f_reach():
        r = _reach().call("reddit", "read", dict(target=url), backend="site")
        if not r["ok"]:
            raise Empty((r.get("error") or {}).get("code"))
        it = r["items"][0]
        raw = it.get("raw") if isinstance(it.get("raw"), dict) else {}
        post = dict(post_of(raw.get("post") if isinstance(raw.get("post"), dict) else raw), title=it.get("title"), url=it.get("url") or url)
        post.update(score=it["metrics"].get("score", post.get("score")), num_comments=it["metrics"].get("comments", post.get("num_comments")))
        com = [dict(author=c.get("author"), score=c.get("score"), body=(c.get("text") or c.get("body") or "")[:3000], depth=0, published=None)
               for c in raw.get("comments") or [] if isinstance(c, dict)]
        return dict(post=post, comments=com, text=it.get("text") or thread_text(post, com), url=post["url"])

    def f_oauth():
        return listing_pair(_get("oauth", f"https://oauth.reddit.com/comments/{tid}?limit={limit}&raw_json=1", oauth_headers()))

    def f_json():
        last = None
        for host in ("www", "old"):
            try:
                return listing_pair(_get("json", f"https://{host}.reddit.com/comments/{tid}/.json?limit={limit}&raw_json=1"))
            except Exception as e:  # noqa: BLE001
                last = e
                _DOWN.pop("json", None)
        raise last  # type: ignore[misc]

    def f_rss():
        ents = parse_atom(_get("rss", f"https://www.reddit.com/comments/{tid}/.rss?limit={limit}", raw=True))
        if not ents:
            raise Empty("feed vuoto")
        p = ents[0]
        post = dict(id=tid, title=p["title"], author=p["author"], subreddit=None, score=None, score_hidden=False, num_comments=len(ents) - 1,
                    published=p["published"], url=p["url"] or url, link=None, text=p["text"], removed=False, raw={})
        com = [dict(id=c["id"], author=c["author"], score=None, body=c["text"] or "", depth=0, published=c["published"]) for c in ents[1:]]
        return dict(post=post, comments=com, text=thread_text(post, com), url=post["url"])

    def f_arctic():
        d = _get("arctic", f"{ARCTIC}/posts/ids?ids={tid}")
        rows = d.get("data") or []
        if not rows:
            raise Empty("post non nell'archivio")
        post = post_of(rows[0])
        t = _get("arctic", f"{ARCTIC}/comments/tree?link_id={tid}&limit={min(limit, 9999)}")
        com = comments_of(t.get("data") or [], limit=limit)
        return dict(post=post, comments=com, text=thread_text(post, com), url=post["url"] or url)

    def f_threadsnoop():
        d = _get("threadsnoop", f"{THREADSNOOP}/posts?ids={tid}", _threadsnoop_h())
        rows = d.get("data") or d.get("posts") or []
        if not rows:
            raise Empty("post non trovato")
        post = post_of(rows[0])
        t = _get("threadsnoop", f"{THREADSNOOP}/comments/tree?post_id={tid}&limit={limit}", _threadsnoop_h())
        com = comments_of(t.get("data") or t.get("comments") or [], limit=limit)
        return dict(post=post, comments=com, text=thread_text(post, com), url=post["url"] or url)

    def f_public():
        r = _reach().call("reddit", "read", dict(target=url), backend="public-web")
        if not r["ok"]:
            raise Empty((r.get("error") or {}).get("code"))
        it = r["items"][0]
        post = dict(id=tid, title=it.get("title"), author=it.get("author"), subreddit=None, score=None, score_hidden=False, num_comments=None,
                    published=it.get("published"), url=it.get("url") or url, link=None, text=it.get("text"), removed=False, raw={})
        return dict(post=post, comments=[], text=it.get("text") or "", url=post["url"], note="testo pubblico della pagina: i commenti possono mancare")

    return _chain("thread", dict(reach=f_reach, oauth=f_oauth, json=f_json, rss=f_rss, arctic=f_arctic, threadsnoop=f_threadsnoop, reach_public=f_public), only)


# ---------------------------------------------------------------- rules
def sidebar_rules(md: str) -> list[dict]:
    """Old-Reddit sidebar markdown -> rule-like sections: numbered items, or headings with the paragraph under them."""
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md or "")
    out, cur = [], None
    for line in md.splitlines():
        l = line.strip().strip(">").strip()
        if not l or re.fullmatch(r"[-=_*~\s|:]{2,}", l):
            continue
        m = re.match(r"^\**(\d{1,2})[.)]\s+(.{3,160})$", l)
        h = re.match(r"^#{1,6}\s*(.+)$", l)
        if m or h:
            title = (m.group(2) if m else h.group(1)).strip(" *#_")
            cur = dict(title=title, text="", numbered=bool(m))
            out.append(cur)
        elif cur is not None and len(cur["text"]) < 1200:
            cur["text"] = (cur["text"] + " " + l.strip("*_ ")).strip()[:1200]
    rs = [x for x in out if (x["numbered"] or x["text"]) and len(re.sub(r"[^A-Za-z]", "", x["title"])) >= 3 and not x["title"].lower().startswith(("/r/", "r/"))]
    return [dict(n=i + 1, title=x["title"][:160], text=x["text"], kind="sidebar") for i, x in enumerate(rs[:25])]


def rules_from_api(rules: list) -> list[dict]:
    return [dict(n=i + 1, title=r.get("short_name") or r.get("title"), text=r.get("description") or r.get("text"), kind=r.get("kind"))
            for i, r in enumerate(rules or []) if isinstance(r, dict)]


def rules(sub: str, only: list[str] | None = None) -> dict:
    sub = sub.removeprefix("r/").strip("/")
    page = f"https://www.reddit.com/r/{sub}/"

    def about(base, b, h=None):
        try:
            a = _get(b, f"{base}/r/{sub}/about.json?raw_json=1" if "oauth" not in base else f"{base}/r/{sub}/about?raw_json=1", h).get("data") or {}
            return dict(subscribers=a.get("subscribers"), public_description=a.get("public_description"))
        except Exception:  # noqa: BLE001
            return {}

    def f_oauth():
        h = oauth_headers()
        rs = rules_from_api(_get("oauth", f"https://oauth.reddit.com/r/{sub}/about/rules?raw_json=1", h).get("rules"))
        if not rs:
            raise Empty("nessuna regola")
        return dict(rules=rs, url=page, completeness="API ufficiale", **about("https://oauth.reddit.com", "oauth", h))

    def f_json():
        last = None
        for host in ("www", "old"):
            try:
                rs = rules_from_api(_get("json", f"https://{host}.reddit.com/r/{sub}/about/rules.json?raw_json=1").get("rules"))
                if rs:
                    return dict(rules=rs, url=page, completeness="JSON pubblico", **about(f"https://{host}.reddit.com", "json"))
            except Exception as e:  # noqa: BLE001
                last = e
                _DOWN.pop("json", None)
        if last:
            raise last
        raise Empty("nessuna regola")

    def f_arctic():
        d = _get("arctic", f"{ARCTIC}/subreddits/rules?subreddits={sub}")
        rows = d.get("data") or []
        rs = rules_from_api((rows[0].get("rules") if rows and isinstance(rows[0], dict) else None) or [])
        s = {}
        try:
            s = (_get("arctic", f"{ARCTIC}/subreddits/search?subreddit={sub}").get("data") or [{}])[0]
        except Exception:  # noqa: BLE001
            if not rs:
                raise
        info = dict(subscribers=s.get("subscribers"), public_description=s.get("public_description"))
        if rs:
            return dict(rules=rs, url=page, completeness="regole dall'archivio Arctic Shift", **info)
        # no rules in the archive: the subreddit's sidebar and submit text (old Reddit), where most subs write their guidelines
        side = "\n".join(x for x in (s.get("description"), s.get("submit_text")) if x)
        if not side.strip():
            raise Empty("l'archivio non ha regole né sidebar per questo subreddit")
        rs = sidebar_rules(side) or [dict(n=1, title="Linee guida della sidebar", text=side[:1500], kind="sidebar")]
        copy = _date(s.get("retrieved_on"))
        return dict(rules=rs, url=page, sidebar=side[:4000], **info,
                    completeness=f"sidebar e testo di invio dall'archivio Arctic Shift (copia del {copy or '?'}): le regole ufficiali possono differire")

    def f_threadsnoop():
        d = _get("threadsnoop", f"{THREADSNOOP}/subreddits/{sub}/rules", _threadsnoop_h())
        rs = rules_from_api(d.get("rules") or d.get("data") or [])
        if not rs:
            raise Empty("nessuna regola")
        return dict(rules=rs, url=page, completeness="ThreadSnoop")

    def f_text(backend):
        def run():
            r = _reach().call("reddit", "read", dict(target=page), backend=backend)
            if not r["ok"]:
                raise Empty((r.get("error") or {}).get("code"))
            import reddit_rules as rr
            text = r["items"][0].get("text") or ""
            rs = rr.rules_from_text(text)
            if not rs:
                raise Empty("nessuna regola riconosciuta nel testo")
            return dict(rules=rs, url=page, completeness="testo pubblico della pagina, completezza non verificata", page_text=text[:4000])
        return run

    return _chain("rules", dict(reach=f_text("site"), oauth=f_oauth, json=f_json, arctic=f_arctic, threadsnoop=f_threadsnoop, reach_public=f_text("public-web")), only)


# ---------------------------------------------------------------- listings
PERIOD_DAYS = dict(hour=1, day=1, week=7, month=31, year=366, all=36500)


def listing(sub: str, kind: str = "top", t: str = "week", limit: int = 100, only: list[str] | None = None) -> dict:
    """top (by score over the period) or new posts of a subreddit. scores tells if the numbers are real, archived or absent."""
    sub = sub.removeprefix("r/").strip("/")
    limit = max(1, min(int(limit), 100))
    q = f"?t={t}&limit={limit}&raw_json=1" if kind == "top" else f"?limit={limit}&raw_json=1"

    def from_children(d):
        rows = [post_of(c.get("data") or {}) for c in (d.get("data") or {}).get("children") or []]
        if not rows:
            raise Empty("nessun post")
        return dict(posts=rows)

    def f_reach():
        r = _reach().posts("reddit", sub, limit)
        if not r["ok"]:
            raise Empty((r.get("error") or {}).get("code"))
        rows = []
        for it in r["items"]:
            raw = it.get("raw") if isinstance(it.get("raw"), dict) else {}
            p = post_of(raw)
            p.update(title=it.get("title") or p["title"], url=it.get("url") or p["url"], score=it["metrics"].get("score", p["score"]),
                     num_comments=it["metrics"].get("comments", p["num_comments"]), published=it.get("published") or p["published"])
            rows.append(p)
        if kind == "top":
            rows = sorted(rows, key=lambda p: -(p.get("score") or 0))
        return dict(posts=rows, note="Agent Reach: gli ultimi post del subreddit (non il periodo --t); top = ordinati per upvote")

    def f_oauth():
        return from_children(_get("oauth", f"https://oauth.reddit.com/r/{sub}/{kind}{q}", oauth_headers()))

    def f_json():
        last = None
        for host in ("www", "old"):
            try:
                return from_children(_get("json", f"https://{host}.reddit.com/r/{sub}/{kind}/.json{q}"))
            except Exception as e:  # noqa: BLE001
                last = e
                _DOWN.pop("json", None)
        raise last  # type: ignore[misc]

    def f_rss():
        ents = parse_atom(_get("rss", f"https://www.reddit.com/r/{sub}/{kind}/.rss" + (f"?t={t}&limit={limit}" if kind == "top" else f"?limit={limit}"), raw=True))
        if not ents:
            raise Empty("feed vuoto")
        return dict(posts=[dict(id=e["id"], title=e["title"], author=e["author"], subreddit=sub, score=None, score_hidden=False, num_comments=None,
                                published=e["published"], url=e["url"], link=None, text=e["text"], removed=False, raw=dict(html=e["html"][:3000]), rank=k)
                           for k, e in enumerate(ents, 1)], note="RSS: niente punteggi, conta la posizione")

    def f_arctic():
        after = (dt.date.today() - dt.timedelta(days=PERIOD_DAYS.get(t, 7) if kind == "top" else 14)).isoformat()
        d = _get("arctic", f"{ARCTIC}/posts/search?subreddit={sub}&after={after}&limit=" + ("auto" if kind == "top" else str(limit)) + "&sort=desc")
        rows = [post_of(x) for x in d.get("data") or []]
        if not rows:
            raise Empty("nessun post nell'archivio per il periodo")
        if kind == "top":
            rows = sorted(rows, key=lambda p: -(p.get("score") or 0))[:limit]
        return dict(posts=rows[:limit], note="Arctic Shift: punteggi dell'archivio, presi alcune ore dopo la pubblicazione (possono essere più bassi di oggi); "
                                             + ("top = ordinati per punteggio tra i post del periodo letti (fino a 1000)" if kind == "top" else "nuovi = più recenti"))

    def f_threadsnoop():
        after = int(time.time() - 86400 * (PERIOD_DAYS.get(t, 7) if kind == "top" else 14))
        d = _get("threadsnoop", f"{THREADSNOOP}/posts?subreddit={sub}&after={after}&limit=100&sort=desc", _threadsnoop_h())
        rows = [post_of(x) for x in d.get("data") or d.get("posts") or []]
        if not rows:
            raise Empty("nessun post")
        if kind == "top":
            rows = sorted(rows, key=lambda p: -(p.get("score") or 0))
        return dict(posts=rows[:limit])

    seq = order(only)
    if kind == "new" and "rss" in seq and "arctic" in seq and seq.index("arctic") < seq.index("rss"):
        seq.remove("rss")
        seq.insert(seq.index("arctic"), "rss")
    return _chain(f"listing {kind}", dict(reach=f_reach, oauth=f_oauth, json=f_json, rss=f_rss, arctic=f_arctic, threadsnoop=f_threadsnoop), seq)


# ---------------------------------------------------------------- search
def search(query: str, sub: str | None = None, limit: int = 25, only: list[str] | None = None) -> dict:
    limit = max(1, min(int(limit), 100))
    qs = urllib.parse.quote(query)
    path = f"/r/{sub}/search" if sub else "/search"
    restrict = "&restrict_sr=1" if sub else ""

    def f_reach(backend):
        def run():
            r = _reach().call("reddit", "search", dict(query=query + (f" subreddit:{sub}" if sub else ""), limit=limit), backend=backend)
            if not r["ok"]:
                raise Empty((r.get("error") or {}).get("code"))
            rows = []
            for it in r["items"]:
                raw = it.get("raw") if isinstance(it.get("raw"), dict) else {}
                p = post_of(raw)
                p.update(title=it.get("title") or p["title"], url=it.get("url") or p["url"], text=it.get("text") or p["text"],
                         score=it["metrics"].get("score", p["score"]), num_comments=it["metrics"].get("comments", p["num_comments"]),
                         published=it.get("published") or p["published"])
                rows.append(p)
            return dict(posts=rows)
        return run

    def f_oauth():
        d = _get("oauth", f"https://oauth.reddit.com{path}?q={qs}&sort=new&limit={limit}&raw_json=1{restrict}", oauth_headers())
        return dict(posts=[post_of(c.get("data") or {}) for c in (d.get("data") or {}).get("children") or []] or _empty())

    def f_json():
        d = _get("json", f"https://www.reddit.com{path}.json?q={qs}&sort=new&limit={limit}&raw_json=1{restrict}")
        return dict(posts=[post_of(c.get("data") or {}) for c in (d.get("data") or {}).get("children") or []] or _empty())

    def f_rss():
        ents = parse_atom(_get("rss", f"https://www.reddit.com{path}.rss?q={qs}&sort=new&limit={limit}{restrict}", raw=True))
        return dict(posts=[dict(id=e["id"], title=e["title"], author=e["author"], subreddit=sub, score=None, score_hidden=False, num_comments=None,
                                published=e["published"], url=e["url"], link=None, text=e["text"], removed=False, raw={}) for e in ents] or _empty())

    def f_arctic():
        if not sub:
            raise Empty("l'archivio cerca solo dentro un subreddit (--sub)")
        d = _get("arctic", f"{ARCTIC}/posts/search?subreddit={sub}&query={qs}&limit={limit}&sort=desc")
        return dict(posts=[post_of(x) for x in d.get("data") or []] or _empty())

    def f_threadsnoop():
        if not sub:
            raise Empty("ThreadSnoop filtra dentro un subreddit (--sub)")
        d = _get("threadsnoop", f"{THREADSNOOP}/posts?subreddit={sub}&q={qs}&limit={limit}", _threadsnoop_h())
        return dict(posts=[post_of(x) for x in d.get("data") or d.get("posts") or []] or _empty())

    return _chain("search", dict(reach=f_reach("site"), oauth=f_oauth, json=f_json, rss=f_rss, arctic=f_arctic, threadsnoop=f_threadsnoop,
                                 reach_public=f_reach("public-web")), only)


def _empty():
    raise Empty("nessun risultato")


# ---------------------------------------------------------------- doctor
def doctor(sub: str = "IndieDev") -> dict:
    """One light call per backend: which ones answer from this machine now."""
    rows = []
    for b in ORDER:
        if not available(b):
            why = _DOWN.get(b) or dict(reach="Reddit non pronto in Agent Reach (`! agent-reach login reddit`)",
                                       oauth="mancano REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET nel file privato delle chiavi",
                                       threadsnoop="manca THREADSNOOP_API_KEY nel file privato delle chiavi",
                                       reach_public="Agent Reach non installato", arctic="disattivato (GLS_ARCTIC=off)").get(b, "non disponibile")
            rows.append(dict(backend=b, works=False, why=why))
            continue
        r = listing(sub, "new", "week", 3, only=[b]) if b not in ("reach_public",) else rules(sub, only=[b])
        rows.append(dict(backend=b, works=r["ok"], why=r["attempts"][-1][1] if r["attempts"] else ""))
    return dict(checked_on=dt.date.today().isoformat(), sub=sub, rows=rows, first=next((r["backend"] for r in rows if r["works"]), None))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backends", help="comma list, in order (default: " + ",".join(ORDER) + ")")
    ap.add_argument("--rate", type=float, default=3.0, help="seconds between requests per backend (default 3)")
    ap.add_argument("--env-file"); ap.add_argument("-o", "--out", default="-")
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("thread"); t.add_argument("target"); t.add_argument("--limit", type=int, default=200)
    r = sp.add_parser("rules"); r.add_argument("sub")
    li = sp.add_parser("listing"); li.add_argument("sub"); li.add_argument("--kind", default="top", choices=["top", "new"])
    li.add_argument("--t", default="week", choices=list(PERIOD_DAYS)); li.add_argument("--limit", type=int, default=100)
    s = sp.add_parser("search"); s.add_argument("query", nargs="+"); s.add_argument("--sub"); s.add_argument("--limit", type=int, default=25)
    d = sp.add_parser("doctor"); d.add_argument("--sub", default="IndieDev")
    a = ap.parse_args(argv)
    common.load_env(a.env_file)
    configure(rate=a.rate, backends=[x.strip() for x in a.backends.split(",")] if a.backends else None)
    if a.cmd == "thread":
        res = thread(a.target, a.limit)
    elif a.cmd == "rules":
        res = rules(a.sub)
    elif a.cmd == "listing":
        res = listing(a.sub, a.kind, a.t, a.limit)
    elif a.cmd == "search":
        res = search(" ".join(a.query), a.sub, a.limit)
    else:
        res = doctor(a.sub)
        write_json(res, a.out)
        for row in res["rows"]:
            log(f"{row['backend']:<13} {'funziona' if row['works'] else 'no'}  {row['why']}")
        return 0
    write_json(res, a.out)
    log(f"reddit {a.cmd}: {'ok via ' + res['backend'] if res['ok'] else 'nessun backend ha risposto'} · "
        + " → ".join(f"{b}: {o}" for b, o in res["attempts"]))
    return 0 if res["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
