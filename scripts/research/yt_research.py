#!/usr/bin/env python3
"""YouTube creator research: search recent videos -> group by channel -> subscriber counts -> oEmbed verify.

Two backends:
  api  : official YouTube Data API v3 (needs env YOUTUBE_API_KEY; search costs 100 quota units/query,
         default daily quota 10,000 -> ~90 queries/day). Recommended / ToS-clean.
  html : parses the public results page (ytInitialData), no key, no login. Fragile (layout changes)
         and automated access is not encouraged by YouTube ToS: use sparingly, low volume, slow rate.
  reach: Agent Reach (reach.py, yt-dlp underneath): search with views, duration, channel id; dates read per video
         (cached in launch/_raw/reach). No key, no quota. Used by auto when the html page gives nothing.
  auto (default): api if YOUTUBE_API_KEY is set, else html, with reach as fallback.

Subcommands:
  search    queries -> videos JSON  (fields: vid,title,ch,url,when,days,views,topic,query)
  channels  videos JSON -> channels JSON (grouped, filtered by recency/min videos)
  subs      channels JSON -> + subs/country/desc, filtered by subscriber range
  verify    video URLs (incl. /shorts/) -> official oEmbed (author, title) to confirm they exist; + date, views, likes via reach
  transcript video URLs -> subtitles text (manual or auto captions) via Agent Reach; --whisper = speech-to-text (Groq/OpenAI
            key set by the owner with `reach.py configure groq-key`); one .txt per video + an index JSON

Examples:
  python yt_research.py search -q "PlateUp" -q "PlateUp ita" --within month -o yt_raw.json
  python yt_research.py search --topics-json topics.json --within month --within year -o yt_raw.json
  python yt_research.py channels yt_raw.json --max-days 90 -o yt_channels.json
  python yt_research.py subs yt_channels.json --max-subs 1000000 -o yt_shortlist.json
  python yt_research.py verify https://www.youtube.com/shorts/XXXXXXXXXXX -o yt_verified.json
  python yt_research.py transcript https://www.youtube.com/watch?v=XXXXXXXXXXX --lang en,it --out-dir launch/_raw/transcripts
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from common import (Throttle, get_json, get_text, load_json, log, parse_count, q, read_list, safe_json,
                    set_rate, write_output)
import reach

API = "https://www.googleapis.com/youtube/v3"
# YouTube results-page "upload date" filter tokens
SP = {"hour": "EgIIAQ%3D%3D", "today": "EgIIAg%3D%3D", "week": "EgIIAw%3D%3D",
      "month": "EgIIBA%3D%3D", "year": "EgIIBQ%3D%3D", "any": ""}
DAYS = {"hour": 0, "today": 1, "week": 7, "month": 31, "year": 366, "any": None}
HTML_HEADERS = {"Cookie": "CONSENT=YES+1"}  # only dismisses the EU cookie interstitial; not a login


def rel2days(when: str) -> int | None:
    """'2w ago' / '3 days ago' / 'Streamed 1 month ago' / ISO date -> days ago."""
    if not when:
        return None
    if re.match(r"\d{4}-\d{2}-\d{2}", when):
        d = datetime.date.fromisoformat(when[:10])
        return (datetime.date.today() - d).days
    m = re.search(r"(\d+)\s*([a-zA-Z]+)", when.replace("Streamed ", "").replace("Premiered ", ""))
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2).lower()
    if u.startswith(("sec", "min", "hour", "h", "s")) and not u.startswith("mo"):
        return 0
    if u.startswith("mo"):
        return 30 * n
    if u.startswith("d"):
        return n
    if u.startswith("w"):
        return 7 * n
    if u.startswith("y"):
        return 365 * n
    return None


# ---------------------------------------------------------------- search
def html_search(query: str, within: str) -> list[dict]:
    sp = SP[within]
    u = "https://www.youtube.com/results?search_query=" + q(query) + (f"&sp={sp}" if sp else "")
    h = get_text(u, headers=HTML_HEADERS, timeout=40)
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", h)
    if not m:
        log(f"WARN no ytInitialData for {query!r} (layout change or consent page)")
        return []
    data, out = json.loads(m.group(1)), []

    def walk(o):
        if isinstance(o, dict):
            v = o.get("videoRenderer")
            if v:
                try:
                    own = v["ownerText"]["runs"][0]
                    when = (v.get("publishedTimeText") or {}).get("simpleText", "")
                    out.append(dict(vid=v["videoId"], title="".join(r["text"] for r in v["title"]["runs"]),
                                    ch=own["text"], url=own["navigationEndpoint"]["browseEndpoint"].get("canonicalBaseUrl"),
                                    when=when, days=rel2days(when),
                                    views=parse_count((v.get("viewCountText") or {}).get("simpleText"))))
                except (KeyError, IndexError, TypeError):
                    pass
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(data)
    return out


def api_search(query: str, within: str, key: str, max_results: int, region: str | None, lang: str | None) -> list[dict]:
    params = f"part=snippet&type=video&maxResults={min(max_results, 50)}&q={q(query)}&key={key}"
    if DAYS[within] is not None:
        hours = 1 if within == "hour" else DAYS[within] * 24
        after = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
        params += "&publishedAfter=" + after.strftime("%Y-%m-%dT%H:%M:%SZ")
    if region:
        params += f"&regionCode={region}"
    if lang:
        params += f"&relevanceLanguage={lang}"
    items = get_json(f"{API}/search?{params}").get("items") or []
    vids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
    stats = {}
    if vids:  # videos.list = 1 unit, adds view counts
        for v in get_json(f"{API}/videos?part=statistics&id={','.join(vids)}&key={key}").get("items") or []:
            stats[v["id"]] = parse_count((v.get("statistics") or {}).get("viewCount"))
    out = []
    for i in items:
        s, vid = i["snippet"], i["id"].get("videoId")
        if not vid:
            continue
        out.append(dict(vid=vid, title=s.get("title"), ch=s.get("channelTitle"), url="/channel/" + s.get("channelId", ""),
                        channel_id=s.get("channelId"), when=s.get("publishedAt"), days=rel2days(s.get("publishedAt")),
                        views=stats.get(vid)))
    return out


def reach_search(query: str, within: str, max_results: int, dates: int = 15) -> list[dict]:
    """Search through Agent Reach (yt-dlp): views, duration, channel id; the date of the first `dates` videos is read one by one."""
    res = reach.search("youtube", query, min(max_results, 50))
    if not res["ok"]:
        log(f"reach {query!r}: {(res.get('error') or {}).get('code')}")
        return []
    out = []
    for k, it in enumerate(res["items"]):
        raw = it.get("raw") if isinstance(it.get("raw"), dict) else {}
        m = re.search(r"v=([\w-]{11})", it.get("url") or "")
        vid = raw.get("id") or (m.group(1) if m else None)
        if not vid:
            continue
        when = it.get("published")
        if not when and k < dates:
            r = reach.read(f"https://www.youtube.com/watch?v={vid}", "youtube")
            when = r["items"][0].get("published") if r["ok"] else None
        days = rel2days(when or "")
        if DAYS[within] is not None and days is not None and days > DAYS[within]:
            continue
        cid = raw.get("channel_id")
        out.append(dict(vid=vid, title=it.get("title"), ch=it.get("author"), url=("/channel/" + cid) if cid else None, channel_id=cid,
                        when=when, days=days, views=it["metrics"].get("views"), duration=raw.get("duration"), source="agent-reach"))
    return out


def pick_backend(name: str) -> str:
    if name == "auto":
        return "api" if os.environ.get("YOUTUBE_API_KEY") else "html"
    if name == "reach":
        if not reach.enabled():
            raise SystemExit("backend=reach requires Agent Reach (reach.py doctor)")
        return "reach"
    if name == "api" and not os.environ.get("YOUTUBE_API_KEY"):
        raise SystemExit("backend=api requires env var YOUTUBE_API_KEY")
    return name


def cmd_search(a):
    backend = pick_backend(a.backend)
    jobs = [(None, x) for x in read_list(a.query, a.queries_file)]
    if a.topics_json:  # {"Topic label": ["query 1", "query 2"], ...}
        for topic, qs in load_json(a.topics_json).items():
            jobs += [(topic, x) for x in qs]
    if not jobs:
        raise SystemExit("no queries given")
    windows = a.within or ["month"]
    res, seen = [], set()
    for topic, query in jobs:
        for w in windows:
            try:
                vids = (api_search(query, w, os.environ["YOUTUBE_API_KEY"], a.max_results, a.region, a.lang) if backend == "api"
                        else reach_search(query, w, a.max_results) if backend == "reach" else html_search(query, w))
            except Exception as e:  # noqa: BLE001
                log(f"ERR {query!r} [{w}]: {e}")
                vids = []
            if not vids and backend == "html" and a.backend == "auto" and reach.enabled():
                log(f"{query!r} [{w}]: pagina html vuota, provo agent-reach")
                vids = reach_search(query, w, a.max_results)
            if not vids:
                continue
            for v in vids:
                if a.dedupe and (v["vid"], topic) in seen:
                    continue
                seen.add((v["vid"], topic))
                v.update(topic=topic or query, query=query, window=w)
                res.append(v)
        log(f"{topic or query}: total {len(res)}")
    write_output(res, a.out)


# ---------------------------------------------------------------- channels
def cmd_channels(a):
    vids = load_json(a.videos)
    chans: dict[str, dict] = {}
    for v in vids:
        d = v.get("days") if v.get("days") is not None else rel2days(v.get("when", ""))
        if a.max_days is not None and (d is None or d > a.max_days):
            continue
        if a.exclude_title and re.search(a.exclude_title, v.get("title", ""), re.I):
            continue
        v["days"] = d
        c = chans.setdefault(v["url"], dict(ch=v["ch"], url=v["url"], channel_id=v.get("channel_id"), vids=[]))
        if v["vid"] not in {x["vid"] for x in c["vids"]}:
            c["vids"].append(v)
    out = [c for c in chans.values() if len(c["vids"]) >= a.min_videos]
    for c in out:
        c["vids"].sort(key=lambda x: (x["days"] if x["days"] is not None else 9999))
        c["topics"] = sorted({x.get("topic") for x in c["vids"] if x.get("topic")})
    out.sort(key=lambda c: (-len(c["vids"]), c["vids"][0]["days"] or 0))
    log(f"{len(out)} channels from {len(vids)} videos")
    write_output(out, a.out, [dict(ch=c["ch"], url="https://www.youtube.com" + c["url"], n_videos=len(c["vids"]),
                                   topics=c["topics"], latest_days=c["vids"][0]["days"]) for c in out])


# ---------------------------------------------------------------- subs
def html_channel_info(c: dict, th: Throttle) -> dict:
    try:
        h = get_text("https://www.youtube.com" + c["url"], headers=HTML_HEADERS, timeout=40, throttle=th)
        m = re.search(r'"content":"([\d.,]+[KMB]?) subscribers"', h) or re.search(r"([\d.,]+[KMB]?) subscribers", h)
        c["subs_txt"] = m.group(1) if m else None
        m2 = re.search(r'"country":"([^"]+)"', h)
        c["country"] = m2.group(1) if m2 else None
        m3 = re.search(r'<meta name="description" content="([^"]{0,300})', h)
        c["desc"] = m3.group(1) if m3 else ""
    except Exception as e:  # noqa: BLE001
        c["subs_txt"], c["err"] = None, str(e)
    c["subs"] = parse_count(c.get("subs_txt"))
    return c


def api_channel_info(chs: list[dict], key: str):
    by_id = {c.get("channel_id") or c["url"].split("/channel/")[-1]: c for c in chs}
    ids = [i for i in by_id if i and not i.startswith("/")]
    for k in range(0, len(ids), 50):
        batch = ",".join(ids[k:k + 50])
        for it in get_json(f"{API}/channels?part=statistics,snippet&id={batch}&key={key}").get("items") or []:
            c = by_id[it["id"]]
            st, sn = it.get("statistics") or {}, it.get("snippet") or {}
            c["subs"] = None if st.get("hiddenSubscriberCount") else parse_count(st.get("subscriberCount"))
            c["country"] = sn.get("country")
            c["desc"] = (sn.get("description") or "")[:300]
            c["handle"] = sn.get("customUrl")


def cmd_subs(a):
    chs = load_json(a.channels)
    backend = pick_backend(a.backend)
    if backend == "api" and all(c.get("channel_id") or "/channel/" in c["url"] for c in chs):
        api_channel_info(chs, os.environ["YOUTUBE_API_KEY"])
    else:
        th = Throttle(a.rate)
        with ThreadPoolExecutor(a.workers) as ex:
            chs = list(ex.map(lambda c: html_channel_info(c, th), chs))
    ok = sum(1 for c in chs if c.get("subs") is not None)
    log(f"subs found for {ok}/{len(chs)}")
    out = [c for c in chs if c.get("subs") is None and a.keep_unknown
           or c.get("subs") is not None and a.min_subs <= c["subs"] <= a.max_subs]
    out.sort(key=lambda c: c.get("subs") or 0)
    write_output(out, a.out, [dict(ch=c["ch"], url="https://www.youtube.com" + c["url"], subs=c.get("subs"),
                                   country=c.get("country"), n_videos=len(c.get("vids", [])),
                                   topics=c.get("topics"), desc=c.get("desc")) for c in out])


# ---------------------------------------------------------------- verify
def to_watch_url(u: str) -> str:
    m = re.search(r"(?:shorts/|youtu\.be/|v=)([\w-]{11})", u)
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else u


def cmd_verify(a):
    out = []
    for u in read_list(a.urls, a.urls_file):
        o = safe_json("https://www.youtube.com/oembed?format=json&url=" + q(to_watch_url(u)), default={})
        row = dict(url=u, ok=bool(o), author=o.get("author_name"), author_url=o.get("author_url"), title=o.get("title"), is_short="/shorts/" in u)
        if a.reach != "off" and reach.enabled():
            r = reach.read(to_watch_url(u), "youtube")
            if r["ok"]:
                it = r["items"][0]
                row.update(ok=True, date=it.get("published"), author=row["author"] or it.get("author"), title=row["title"] or it.get("title"),
                           numbers_source=f"{r['source']} · {r['consulted']}", **{k: v for k, v in it["metrics"].items() if k in ("views", "likes", "comments")})
        out.append(row)
        log(f"{'OK ' if o else 'ERR'} {u} | {o.get('author_name')} | {(o.get('title') or '')[:80]}")
    write_output(out, a.out)


def cmd_transcript(a):
    os.makedirs(a.out_dir, exist_ok=True)
    out = []
    for u in read_list(a.urls, a.urls_file):
        target = to_watch_url(u) if ("youtu" in u or re.fullmatch(r"[\w-]{11}", u)) else u
        r = reach.transcript(target, a.lang, True if a.whisper else None)
        row = dict(url=u, ok=r["ok"], label=r["label"], source=r.get("source"), consulted=r.get("consulted"), error=(r.get("error") or {}).get("code"))
        if r["ok"]:
            it = r["items"][0]
            m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", u) or re.search(r"(BV[0-9A-Za-z]{10})", u)
            vid = m.group(1) if m else re.sub(r"\W+", "_", u)[-40:]
            path = os.path.join(a.out_dir, f"{vid}.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(it.get("text") or "")
            raw = it.get("raw") if isinstance(it.get("raw"), dict) else {}
            row.update(file=path, title=it.get("title"), lang=raw.get("lang"), words=len((it.get("text") or "").split()))
        out.append(row)
        log(f"{'OK ' if r['ok'] else 'ERR'} {u} | {row.get('words') or row.get('error')}")
    write_output(out, a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=float, default=1.5, help="min seconds between requests (default 1.5)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search videos")
    s.add_argument("-q", "--query", action="append", help="search query (repeatable)")
    s.add_argument("--queries-file", help="text file, one query per line")
    s.add_argument("--topics-json", help='JSON {"Topic": ["query", ...]}; topic is stored on each video')
    s.add_argument("--within", action="append", choices=list(SP), help="upload-date window (repeatable; default month)")
    s.add_argument("--backend", default="auto", choices=["auto", "api", "html", "reach"])
    s.add_argument("--max-results", type=int, default=50, help="api backend only (max 50)")
    s.add_argument("--region", help="api: regionCode, e.g. IT")
    s.add_argument("--lang", help="api: relevanceLanguage, e.g. it")
    s.add_argument("--dedupe", action="store_true", help="drop duplicate video ids per topic")
    s.add_argument("-o", "--out", default="-")
    s.set_defaults(fn=cmd_search)

    c = sub.add_parser("channels", help="group videos by channel")
    c.add_argument("videos", help="JSON from `search`")
    c.add_argument("--max-days", type=int, help="keep only videos published within N days")
    c.add_argument("--min-videos", type=int, default=1)
    c.add_argument("--exclude-title", help="regex: drop videos whose title matches (e.g. 'trailer|soundtrack')")
    c.add_argument("-o", "--out", default="-")
    c.set_defaults(fn=cmd_channels)

    b = sub.add_parser("subs", help="add subscriber counts to channels")
    b.add_argument("channels", help="JSON from `channels`")
    b.add_argument("--backend", default="auto", choices=["auto", "api", "html", "reach"])
    b.add_argument("--min-subs", type=int, default=0)
    b.add_argument("--max-subs", type=int, default=10**12)
    b.add_argument("--keep-unknown", action="store_true", help="keep channels whose subs could not be read")
    b.add_argument("--workers", type=int, default=3, help="html: parallel workers (throttled globally)")
    b.add_argument("-o", "--out", default="-")
    b.set_defaults(fn=cmd_subs)

    v = sub.add_parser("verify", help="verify video URLs via official oEmbed")
    v.add_argument("urls", nargs="*")
    v.add_argument("--urls-file")
    v.add_argument("--reach", default="auto", choices=["auto", "on", "off"], help="add date, views, likes through Agent Reach")
    v.add_argument("-o", "--out", default="-")
    v.set_defaults(fn=cmd_verify)

    t = sub.add_parser("transcript", help="subtitles / speech-to-text of videos via Agent Reach")
    t.add_argument("urls", nargs="*")
    t.add_argument("--urls-file")
    t.add_argument("--lang", help="preferred subtitle languages, e.g. en,it (default: Agent Reach's list)")
    t.add_argument("--whisper", action="store_true", help="speech-to-text when there are no subtitles (needs the owner's Groq/OpenAI key)")
    t.add_argument("--out-dir", default=os.path.join("launch", "_raw", "transcripts"))
    t.add_argument("--manual", help="ricerche-manuali.md for the manual steps")
    t.add_argument("-o", "--out", default="-")
    t.set_defaults(fn=cmd_transcript)

    a = ap.parse_args()
    set_rate(a.rate)
    reach.configure(manual=getattr(a, "manual", None))
    a.fn(a)


if __name__ == "__main__":
    main()
