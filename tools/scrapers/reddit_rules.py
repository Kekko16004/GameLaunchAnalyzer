#!/usr/bin/env python3
"""Fetch subreddit rules (+ subscribers, self-promo hints) via Reddit's official JSON endpoints.

Auth modes:
  - If env REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET are set: official OAuth "application-only"
    (client_credentials) against https://oauth.reddit.com  -> reliable, recommended.
    Create a "script" app at https://www.reddit.com/prefs/apps (free).
  - Otherwise: unauthenticated https://www.reddit.com/r/<sub>/about/rules.json. Reddit often answers
    403/429 or HTML to anonymous clients; in that case the subreddit is reported as error and you
    should use OAuth or read the sidebar manually. No login/CAPTCHA bypass is attempted.

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
from common import get_json, http_get, log, read_list, set_rate, write_json

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
    return o


def to_md(rows: list[dict]) -> str:
    out = []
    for r in rows:
        out.append(f"## r/{r['subreddit']}  ({r.get('subscribers') or '?'} iscritti)\n{r['url']}\n")
        if r.get("error"):
            out.append(f"ERRORE: {r['error']} -> controllare a mano la sidebar\n")
            continue
        for x in r["rules"]:
            flag = " **[promo]**" if x["n"] in r["promo_related_rules"] else ""
            out.append(f"{x['n']}. **{x['title']}**{flag}\n   {(x['text'] or '').strip()}\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subs", nargs="*", help="subreddit names (with or without r/)")
    ap.add_argument("--subs-file")
    ap.add_argument("--rate", type=float, default=2.0, help="min seconds between requests (default 2)")
    ap.add_argument("-o", "--out", default="-", help=".json or .md (default stdout JSON)")
    a = ap.parse_args()
    set_rate(a.rate)
    subs = read_list(a.subs, a.subs_file)
    if not subs:
        ap.error("no subreddits given")
    h = oauth_headers()
    log("mode:", "oauth app-only" if h else "anonymous (may be blocked)")
    rows = []
    for s in subs:
        r = fetch(s, h)
        rows.append(r)
        log(f"r/{r['subreddit']}: {r.get('error') or str(len(r['rules'])) + ' rules'}")
    if a.out.lower().endswith(".md"):
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(to_md(rows))
        log(f"wrote {a.out}")
    else:
        write_json(rows, a.out)


if __name__ == "__main__":
    main()
