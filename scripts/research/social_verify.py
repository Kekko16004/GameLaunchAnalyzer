#!/usr/bin/env python3
"""Verify social video/channel URLs using ONLY official public endpoints (no login, no scraping).

Platforms:
  tiktok     https://www.tiktok.com/oembed  (no key). Returns author + caption; publish date is decoded
             from the video id (id >> 32 = unix seconds). Follower counts are NOT available -> manual.
  youtube    https://www.youtube.com/oembed (no key). Works for watch, youtu.be and /shorts/ URLs.
             No publish date / subs: use yt_research.py (Data API) for those.
  instagram  Meta Graph API instagram_oembed. Needs env IG_OEMBED_TOKEN ("APP_ID|CLIENT_TOKEN" of a
             Meta app with oEmbed Read). Without it the platform is skipped.
  twitch     Helix API (clips / videos / users). Needs env TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET
             (app access token, client-credentials flow). Without them the platform is skipped.
  x          X / Twitter posts and profiles: only through Agent Reach (below).

Agent Reach backend (reach.py, --reach auto by default): when Agent Reach is installed and the channel is ready
(`reach.py doctor`), the REAL follower counts of TikTok, Instagram and X accounts and the numbers of the post (views,
likes, comments) are read from the platform through the owner's own login in Agent Reach's browser, labelled [FATTO]
with the source and the date. YouTube gets publish date and views. When a channel is not ready the old behaviour stays
(oEmbed, "manual (requires login)") and, with --manual, the manual step is written to ricerche-manuali.md.

Platform is auto-detected from each URL.

Examples:
  python social_verify.py https://www.tiktok.com/@user/video/7677411131643809031 -o tt_verified.json
  python social_verify.py --urls-file urls.txt -o verified.csv --since 2026-07-01
  python social_verify.py https://x.com/studio https://www.instagram.com/studio/ --manual launch/ricerche-manuali.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
from common import get_json, http_get, log, q, read_list, set_rate, ts_to_date, write_output
import reach


def platform_of(u: str) -> str | None:
    h = urllib.parse.urlparse(u).netloc.lower()
    for key, p in (("tiktok.", "tiktok"), ("youtube.", "youtube"), ("youtu.be", "youtube"),
                   ("instagram.", "instagram"), ("twitch.tv", "twitch"), ("twitter.", "x"), ("x.com", "x")):
        if key in h:
            return p
    return None


def tiktok(u: str) -> dict:
    o = {}
    m = re.search(r"/(?:video|photo)/(\d+)", u)
    if m:
        o["date"] = ts_to_date(int(m.group(1)) >> 32)
    e = get_json("https://www.tiktok.com/oembed?url=" + q(u))
    o.update(author=e.get("author_name"), author_url=e.get("author_url"), handle=e.get("author_unique_id"),
             title=(e.get("title") or "")[:200], followers="manual (requires login)")
    return o


def youtube(u: str) -> dict:
    m = re.search(r"(?:shorts/|youtu\.be/|v=)([\w-]{11})", u)
    watch = f"https://www.youtube.com/watch?v={m.group(1)}" if m else u
    e = get_json("https://www.youtube.com/oembed?format=json&url=" + q(watch))
    return dict(author=e.get("author_name"), author_url=e.get("author_url"), title=e.get("title"),
                is_short="/shorts/" in u)


def instagram(u: str) -> dict:
    tok = os.environ.get("IG_OEMBED_TOKEN")
    if not tok:
        return dict(skipped="set IG_OEMBED_TOKEN (Meta app oEmbed Read) to verify Instagram")
    e = get_json(f"https://graph.facebook.com/v19.0/instagram_oembed?url={q(u)}&omitscript=true&access_token={q(tok)}")
    return dict(author=e.get("author_name"), title=(e.get("title") or "")[:200], followers="manual (requires login)")


_TW_TOKEN: str | None = None


def _twitch_headers() -> dict | None:
    global _TW_TOKEN
    cid, sec = os.environ.get("TWITCH_CLIENT_ID"), os.environ.get("TWITCH_CLIENT_SECRET")
    if not (cid and sec):
        return None
    if not _TW_TOKEN:
        body = urllib.parse.urlencode(dict(client_id=cid, client_secret=sec, grant_type="client_credentials")).encode()
        _TW_TOKEN = json.loads(http_get("https://id.twitch.tv/oauth2/token", data=body, method="POST"))["access_token"]
    return {"Client-Id": cid, "Authorization": f"Bearer {_TW_TOKEN}"}


def twitch(u: str) -> dict:
    h = _twitch_headers()
    if not h:
        return dict(skipped="set TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET to verify Twitch")
    api = "https://api.twitch.tv/helix"
    p = urllib.parse.urlparse(u)
    path = [x for x in p.path.split("/") if x]
    if "clips.twitch.tv" in p.netloc or "clip" in path:
        cid = path[-1]
        d = (get_json(f"{api}/clips?id={q(cid)}", headers=h).get("data") or [{}])[0]
        return dict(kind="clip", author=d.get("broadcaster_name"), title=d.get("title"),
                    date=(d.get("created_at") or "")[:10], views=d.get("view_count"), game_id=d.get("game_id"))
    if "videos" in path:
        vid = path[path.index("videos") + 1]
        d = (get_json(f"{api}/videos?id={q(vid)}", headers=h).get("data") or [{}])[0]
        return dict(kind="video", author=d.get("user_name"), title=d.get("title"),
                    date=(d.get("created_at") or "")[:10], views=d.get("view_count"))
    login = path[0] if path else ""
    d = (get_json(f"{api}/users?login={q(login)}", headers=h).get("data") or [{}])[0]
    o = dict(kind="channel", author=d.get("display_name"), title=(d.get("description") or "")[:200],
             broadcaster_type=d.get("broadcaster_type"), followers="manual (Helix needs a user token)")
    if d.get("id"):
        vids = get_json(f"{api}/videos?user_id={d['id']}&first=5&sort=time", headers=h).get("data") or []
        o["recent_videos"] = [dict(date=v["created_at"][:10], title=v["title"], url=v["url"]) for v in vids]
        o["date"] = o["recent_videos"][0]["date"] if vids else None
    return o


def x_post(u: str) -> dict:
    return dict(followers="manual (requires login)")   # X has no free public endpoint: Agent Reach or by hand


HANDLERS = dict(tiktok=tiktok, youtube=youtube, instagram=instagram, twitch=twitch, x=x_post)


def _src(res: dict) -> str:
    return f"{res.get('source')} · {res.get('consulted')}"


def with_reach(u: str, p: str, row: dict) -> dict:
    """Real numbers through Agent Reach (followers of the account, numbers of the post), only when the channel answers."""
    if p not in ("tiktok", "instagram", "x", "youtube") or not reach.enabled():
        return row
    if p == "youtube":
        r = reach.read(u, "youtube")
        if r["ok"]:
            it = r["items"][0]
            row.update(date=row.get("date") or it.get("published"), **{k: v for k, v in it["metrics"].items() if k in ("views", "likes", "comments")},
                       numbers_source=_src(r), numbers_label="[FATTO]")
        return row
    is_post = bool(re.search(r"/(video|photo|status|p|reel|reels)/", u))
    handle = row.get("handle") or reach.handle_of(u)
    if not handle and p == "x" and is_post:
        handle = (urllib.parse.urlparse(u).path.split("/") + [""])[1] or None
    if is_post and p in ("tiktok", "x"):
        r = reach.read(u, p)
        if r["ok"]:
            it = r["items"][0]
            row.update(author=row.get("author") or it.get("author"), title=row.get("title") or (it.get("text") or "")[:200],
                       date=row.get("date") or it.get("published"), numbers_source=_src(r), numbers_label="[FATTO]",
                       **{k: v for k, v in it["metrics"].items() if k in ("views", "likes", "comments", "shares")})
    if handle:
        r = reach.profile(p, handle)
        if r["ok"] and r["items"][0]["metrics"].get("followers") is not None:
            m = r["items"][0]["metrics"]
            row.update(followers=m["followers"], followers_source=_src(r), followers_label="[FATTO]", handle=handle,
                       **{k: m[k] for k in ("following", "posts") if k in m})
            row.pop("skipped", None)
        else:
            row["followers_label"] = "[DA VERIFICARE]"
            row["reach_error"] = (r.get("error") or {}).get("code")
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--urls-file", help="text file, one URL per line")
    ap.add_argument("--since", help="flag rows with date before YYYY-MM-DD as recent=False")
    ap.add_argument("--rate", type=float, default=1.0, help="min seconds between requests (default 1.0)")
    ap.add_argument("--reach", default="auto", choices=["auto", "on", "off"], help="Agent Reach backend for real followers / post numbers (default auto)")
    ap.add_argument("--manual", help="ricerche-manuali.md: write the manual step when a channel is not ready")
    ap.add_argument("-o", "--out", default="-", help=".json or .csv (default stdout JSON)")
    a = ap.parse_args()
    set_rate(a.rate)
    reach.configure(mode=a.reach, manual=a.manual)
    urls = read_list(a.urls, a.urls_file)
    if not urls:
        ap.error("no URLs given")
    out = []
    for u in urls:
        p = platform_of(u)
        row = dict(url=u, platform=p)
        if not p:
            row["error"] = "unsupported platform"
        else:
            try:
                row.update(HANDLERS[p](u))
            except Exception as e:  # noqa: BLE001
                row.update(error=str(e))
            if a.reach != "off":
                with_reach(u, p, row)
            row["ok"] = "skipped" not in row and ("error" not in row or "followers_source" in row or "numbers_source" in row)
        if a.since and row.get("date"):
            row["recent"] = row["date"] >= a.since
        out.append(row)
        log(f"{p} | {row.get('date', '')} | {row.get('author')} | {(row.get('title') or row.get('error') or row.get('skipped') or '')[:80]}")
    write_output(out, a.out)


if __name__ == "__main__":
    main()
