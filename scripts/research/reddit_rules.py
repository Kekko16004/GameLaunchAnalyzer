#!/usr/bin/env python3
"""Fetch subreddit rules (+ subscribers, self-promo hints) via Reddit's official JSON endpoints.

Auth modes:
  - If env REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET are set: official OAuth "application-only"
    (client_credentials) against https://oauth.reddit.com  -> reliable, recommended.
    Create a "script" app at https://www.reddit.com/prefs/apps (free).
  - Otherwise: unauthenticated https://www.reddit.com/r/<sub>/about/rules.json. Reddit often answers
    403/429 or HTML to anonymous clients; in that case the subreddit is reported as error and you
    should use OAuth or read the sidebar manually. No login/CAPTCHA bypass is attempted.
  - Fallback chain (reddit_backends.py) when the anonymous JSON is blocked: Agent Reach with the owner's Reddit login, the
    Arctic Shift public archive (rules, or the sidebar + submit text where most subs write their guidelines), ThreadSnoop
    (only with THREADSNOOP_API_KEY), then the public page text through Agent Reach. The first that answers wins; the row says
    which one (`backend`) and how complete it is (`completeness`). A block page is never taken as rules.

Set REDDIT_USER_AGENT to something descriptive, e.g. "launch-research/1.0 by u/yourname" (Reddit rule).

Examples:
  python reddit_rules.py IndieDev indiegaming playmygame -o reddit_rules.json
  python reddit_rules.py --subs-file subs.txt -o reddit_rules.md
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.parse
from common import get_json, http_get, load_env, log, read_list, set_rate, write_json
import reach
import reddit_backends as rb

PROMO_RX = re.compile(r"self[- ]?promo|promot|advertis|spam|10%|ratio|saturday|feedback friday|screenshot saturday|"
                      r"flair|no (?:links|ads)|tag your|devlog", re.I)


def oauth_headers() -> dict | None:
    cid, sec = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not (cid and sec):
        return None
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    tok = json.loads(http_get("https://www.reddit.com/api/v1/access_token", data=body, method="POST",
                              headers={"Authorization": f"Basic {auth}", "User-Agent": ua()}))["access_token"]
    return {"Authorization": f"Bearer {tok}", "User-Agent": ua()}


def ua() -> str:
    return os.environ.get("REDDIT_USER_AGENT", "research-scrapers/1.0 (subreddit rules lookup)")


def fetch(sub: str, headers: dict | None) -> dict:
    base = "https://oauth.reddit.com" if headers else "https://www.reddit.com"
    h = headers or {"User-Agent": ua()}
    sub = sub.removeprefix("r/").strip("/")
    o = dict(subreddit=sub, url=f"https://www.reddit.com/r/{sub}/")
    try:
        rules = get_json(f"{base}/r/{sub}/about/rules.json?raw_json=1", headers=h)
        o["rules"] = [dict(n=i + 1, title=r.get("short_name"), text=r.get("description"), kind=r.get("kind"))
                      for i, r in enumerate(rules.get("rules") or [])]
        about = get_json(f"{base}/r/{sub}/about.json?raw_json=1", headers=h).get("data") or {}
        o.update(subscribers=about.get("subscribers"), active=about.get("accounts_active") or about.get("active_user_count"),
                 over18=about.get("over18"), submission_type=about.get("submission_type"),
                 public_description=about.get("public_description"))
        o["promo_related_rules"] = [r["n"] for r in o["rules"]
                                    if PROMO_RX.search(f"{r['title']} {r['text'] or ''}")]
    except Exception as e:  # noqa: BLE001
        o["error"] = f"{type(e).__name__}: {e}"
        if not headers:
            via_chain(o)
    return o


def via_chain(o: dict) -> dict:
    """Anonymous JSON blocked: the other Reddit backends, in order; the first that answers wins."""
    r = rb.rules(o["subreddit"], only=[b for b in rb.order() if b not in ("oauth", "json")])
    o["attempts"] = r["attempts"]
    if not r["ok"]:
        return o
    o["rules"] = r["rules"]
    o["promo_related_rules"] = [x["n"] for x in o["rules"] if PROMO_RX.search(f"{x['title']} {x['text'] or ''}")]
    text = r.get("page_text") or r.get("sidebar") or " ".join(f"{x['title']} {x['text'] or ''}" for x in o["rules"])
    o["promo_mentions"] = sorted({m.group(0).lower() for m in PROMO_RX.finditer(text)})
    o.update(backend=r["backend"], source=f"reddit via {r['backend']} · {r['consulted']}", completeness=r.get("completeness"), label="[FATTO]",
             **{k: r[k] for k in ("subscribers", "public_description") if r.get(k) is not None})
    o["anonymous_error"] = o.pop("error", None)
    return o


def rules_from_text(text: str) -> list[dict]:
    """Rules from the public page text: numbered lines ("1. No spam") or short title lines followed by their paragraph."""
    lines = [l.strip(" #*\t") for l in (text or "").splitlines()]
    lines = [l for l in lines if l]
    out = []
    for i, l in enumerate(lines):
        m = re.match(r"^(\d{1,2})[.)]\s+(.{3,120})$", l)
        if m:
            nxt = lines[i + 1] if i + 1 < len(lines) and not re.match(r"^\d{1,2}[.)]\s", lines[i + 1]) else ""
            out.append(dict(n=len(out) + 1, title=m.group(2).strip(), text=nxt[:500], kind="page"))
    if not out:   # no numbering: a short line (the rule title) followed by a longer paragraph
        for i, l in enumerate(lines[:-1]):
            nxt = lines[i + 1]
            if 3 <= len(l) <= 80 and not l.endswith((".", ":", "?")) and len(nxt) > len(l) and not l.lower().startswith(("r/", "http", "[")):
                out.append(dict(n=len(out) + 1, title=l, text=nxt[:500], kind="page"))
    return out[:25]


def via_reach(o: dict) -> dict:
    """Anonymous JSON blocked: the public subreddit page through Agent Reach (sidebar and rules as visitors see them)."""
    res = reach.read(o["url"], "reddit")
    if not res["ok"]:
        o["reach_error"] = (res.get("error") or {}).get("code")
        return o
    text = res["items"][0].get("text") or ""
    o["rules"] = rules_from_text(text)
    o["promo_related_rules"] = [r["n"] for r in o["rules"] if PROMO_RX.search(f"{r['title']} {r['text'] or ''}")]
    o["promo_mentions"] = sorted({m.group(0).lower() for m in PROMO_RX.finditer(text)})
    o.update(source=f"{res['source']} · {res['consulted']}", completeness="testo pubblico della pagina, completezza non verificata", label="[FATTO]")
    o["anonymous_error"] = o.pop("error", None)
    return o


def to_md(rows: list[dict]) -> str:
    out = []
    for r in rows:
        out.append(f"## r/{r['subreddit']}  ({r.get('subscribers') or '?'} iscritti)\n{r['url']}\n")
        if r.get("error"):
            out.append(f"ERRORE: {r['error']} -> controllare a mano la sidebar\n")
            continue
        if r.get("source"):
            out.append(f"_Fonte: {r['source']} ({r.get('completeness')}). Parole di autopromozione nella pagina: "
                       f"{', '.join(r.get('promo_mentions') or []) or 'nessuna'}._\n")
        for x in r["rules"]:
            flag = " **[promo]**" if x["n"] in r["promo_related_rules"] else ""
            out.append(f"{x['n']}. **{x['title']}**{flag}\n   {(x['text'] or '').strip()}\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subs", nargs="*", help="subreddit names (with or without r/)")
    ap.add_argument("--subs-file")
    ap.add_argument("--rate", type=float, default=2.0, help="min seconds between requests (default 2)")
    ap.add_argument("--reach", default="auto", choices=["auto", "on", "off"], help="Agent Reach fallback when Reddit blocks the anonymous JSON (default auto)")
    ap.add_argument("--manual", help="ricerche-manuali.md for the manual steps")
    ap.add_argument("-o", "--out", default="-", help=".json or .md (default stdout JSON)")
    a = ap.parse_args()
    set_rate(a.rate)
    load_env()                       # REDDIT_CLIENT_ID/SECRET, THREADSNOOP_API_KEY from the private keys file (names only, never printed)
    rb.configure(rate=max(a.rate, 2.0))
    reach.configure(mode=a.reach, manual=a.manual)
    subs = read_list(a.subs, a.subs_file)
    if not subs:
        ap.error("no subreddits given")
    h = oauth_headers()
    log("mode:", "oauth app-only" if h else "anonymous (may be blocked), then " + " → ".join(b for b in rb.order() if b not in ("oauth", "json")))
    rows = []
    for s in subs:
        r = fetch(s, h)
        rows.append(r)
        log(f"r/{r['subreddit']}: {r.get('error') or str(len(r['rules'])) + ' rules'}" + (f" (via {r.get('backend') or 'agent-reach'})" if r.get("source") else ""))
    if a.out.lower().endswith(".md"):
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(to_md(rows))
        log(f"wrote {a.out}")
    else:
        write_json(rows, a.out)


if __name__ == "__main__":
    main()
