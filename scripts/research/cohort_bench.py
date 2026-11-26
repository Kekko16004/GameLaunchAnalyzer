#!/usr/bin/env python3
"""Base rate of the REAL competition: of the games Steam releases every day, how many are at least at your
level once the junk is set aside, and how many of those actually sell.

Subcommands (outputs in --dir, default launch/_raw/cohort/):
  volume   games released per day over the last N days (store search sorted by release date, games only)
  fetch    every game released in a date window (e.g. 7 days ~3 months ago) with store data (appdetails) and
           review counts (appreviews) and the public review histogram, so that only reviews written from the
           release date on are counted (a 1.0 launch of an old Early Access game carries years of reviews and is
           marked "not new"); optional SteamSpy owners. Resumable: one cached file per app.
  filter   automatic rules for "clearly junk / not comparable", with the reason of every exclusion
  sheets   header capsules of the survivors as contact sheets (~30 per sheet, numbered and labelled) plus a
           grades.csv to fill with A / B / C by looking at them (the agent reads the sheets, or the user does)
  report   tiers x outcomes: copies [STIMA] with the Boxleiter range, share >= 100 / 1,000 / 10,000 copies,
           share >= ~$800 gross, "became popular", what separates B-tier winners from losers; optional
           --price-min/--price-max and --genres subsets
  update   rolling dataset in ~/.game-launch-strategist/cohorts/ (one CSV per release week): fills gaps in the
           last --new-weeks completed weeks, imports grades and checks older games at 30 / 90 / 180 days.
           The adjacent .quality.json records window/store/review coverage, including failed attempts. Missing
           manifest means unverified, not complete. Partial data remain in _work and can be resumed. A regional
           store block can leave a week partial indefinitely; it is never promoted by substituting zero.
  calibrate  base rates per tier / price band / genre, B-tier winners vs losers, real control capsules for the waves,
           marketing patterns (from market_tracker.py) -> ~/.game-launch-strategist/calibration.json

Grades: A = clearly above your game, B = about your level, C = below. Grade STRICTLY and assume your own
game is B unless the evidence says otherwise ("pretty good, not top" means B, not A).

HONEST LIMITS, quote them every time:
  - copies are reviews x 20..60 (Boxleiter): an order of magnitude, not a sales figure [STIMA]
  - the visual grading is one rater looking at one capsule: it measures presentation, not the game
  - the store search hides some content to logged-out visitors (adult-only titles) and delisted games are
    gone: the junk share is a lower bound
  - a 7-day cohort gives a few hundred games but only tens per tier: read the sample sizes

Examples:
  python cohort_bench.py volume --days 14
  python cohort_bench.py fetch --from 2026-07-15 --to 2026-07-21
  python cohort_bench.py filter
  python cohort_bench.py sheets --reference path/to/our_header.png
  python cohort_bench.py report --mine-price 7.99 --md launch/cohort.md
  python cohort_bench.py report --price-min 5 --price-max 15 --genres casual,simulation,rogue-lite,physics,comedy,party
  python cohort_bench.py update --new-weeks 4 --max-requests 500 --no-volume
  python cohort_bench.py update --new-weeks 0 --no-volume   # only grades and due review checks
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import html as htmlmod
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

import common
from common import Throttle, log, write_csv, write_json

SEARCH = ("https://store.steampowered.com/search/results/?sort_by=Released_DESC&category1=998&infinite=1"
          "&start={start}&count={count}&cc={cc}&l=english")
APPDETAILS = "https://store.steampowered.com/api/appdetails?appids={appid}&l=english&cc={cc}"
APPREVIEWS = "https://store.steampowered.com/appreviews/{appid}?json=1&num_per_page=0&language=all&purchase_type=all"
HISTOGRAM = "https://store.steampowered.com/appreviewhistogram/{appid}?l=english&review_score_preference=0"
STEAMSPY = "https://steamspy.com/api.php?request=appdetails&appid={appid}"
TAGS_URL = "https://store.steampowered.com/tagdata/populartags/english"
HEADER_CDN = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"

BOX_LOW, BOX_HIGH = 20, 60            # Boxleiter: copies per review, as a range
POPULAR_REVIEWS = 500                 # definition: >= 500 reviews or >= 10,000 estimated copies
POPULAR_COPIES = 10000
ADULT_DESCIDS = {3}                   # 3 = Adult Only Sexual Content
ADULT_TAGS = {"hentai", "nsfw"}
SEXUAL_TAGS = {"sexual content", "nudity"}
SHOVEL_TAGS = {"hentai", "nsfw"}      # tags that on their own mark shovelware; extend with --shovel-tag
GENERIC_NAME = re.compile(r"\b(hentai|waifu|sexy|nsfw|lewd|jigsaw|puzzle\s+pack|anime\s+girls?|hot\s+girls?|simulator\s+20\d\d)\b", re.I)
GRADES = ("A", "B", "C")


# ---------------------------------------------------------------- helpers
def parse_date(s: str | None) -> datetime.date | None:
    s = (s or "").strip().replace("  ", " ")
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def strip_tags(s: str | None) -> str:
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def quantile(v: list[float], q: float) -> float | None:
    v = sorted(v)
    if not v:
        return None
    i = (len(v) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval of a proportion, in %: honest error bars for small samples."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0.0, c - h), 1), round(100 * min(1.0, c + h), 1))


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 5:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 2) if den else None


def read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def p(dirp: str, *names: str) -> str:
    return os.path.join(dirp, *names)


# ---------------------------------------------------------------- store search
def parse_search_html(html: str) -> list[dict]:
    """Rows of the search results HTML: games only (rows with a single data-ds-appid)."""
    out = []
    for m in re.finditer(r'<a href="[^"]*"\s+data-ds-appid="(\d+)"(.*?)</a>', html, re.S):
        appid, body = int(m.group(1)), m.group(2)
        g = lambda rx: (re.search(rx, body, re.S) or [None, None])[1]  # noqa: E731
        name = htmlmod.unescape(g(r'<span class="title">(.*?)</span>') or "").strip()
        released = strip_tags(g(r'search_released[^>]*>(.*?)</div>'))
        d = parse_date(released)
        final = g(r'data-price-final="(\d+)"')
        disc = g(r'data-discount="(\d+)"')
        ids = lambda key: [int(x) for x in (g(r'data-ds-' + key + r'="\[([\d,]*)\]"') or "").split(",") if x]  # noqa: E731
        out.append(dict(appid=appid, name=name, released=released, date=d.isoformat() if d else None,
                        price_final_cents=int(final) if final else None, discount=int(disc) if disc else 0,
                        tagids=ids("tagids"), descids=ids("descids"), crtrids=ids("crtrids"),
                        review_tooltip=strip_tags(g(r'data-tooltip-html="([^"]*)"'))))
    return out


def search_page(start: int, count: int, cc: str) -> tuple[list[dict], int | None]:
    d = common.safe_json(SEARCH.format(start=start, count=count, cc=cc), default={})
    if not d or not d.get("results_html"):
        return [], d.get("total_count") if isinstance(d, dict) else None
    return parse_search_html(d["results_html"]), d.get("total_count")


def first_date(rows: list[dict]) -> datetime.date | None:
    for r in rows:
        if r.get("date"):
            return datetime.date.fromisoformat(r["date"])
    return None


def find_offset(newest: datetime.date, cc: str, page: int) -> int:
    """Binary search on the search offset: roughly the first result released on or before `newest`."""
    rows, total = search_page(0, 10, cc)
    for wait in (20, 60, 120):   # the store search rate-limits bursts (429): wait and retry before giving up
        if rows:
            break
        log(f"store search not answering (rate limit?): retry in {wait}s")
        time.sleep(wait)
        rows, total = search_page(0, 10, cc)
    if not rows:
        raise SystemExit("store search not reachable: no data, nothing written")
    lo, hi = 0, total or 200000
    while hi - lo > page:
        mid = (lo + hi) // 2
        rows, _ = search_page(mid, 10, cc)
        d = first_date(rows)
        if d is None:          # past the end, or a failed probe: look lower
            hi = mid
        elif d > newest:
            lo = mid
        else:
            hi = mid
    return max(0, lo - page // 2)


def collect_window(start_date: datetime.date, end_date: datetime.date, cc: str, page: int = 100, start: int | None = None,
                   backoff_tries: int = 4, incomplete: list | None = None) -> list[dict]:
    """Every game whose search release date is in [start_date, end_date]. Offsets where the search kept failing
    are appended to `incomplete` (empty list = the window is complete)."""
    incomplete = incomplete if incomplete is not None else []
    off = start if start is not None else find_offset(end_date, cc, page)
    seen, out, empty = set(), [], 0
    while True:
        rows, total = search_page(off, page, cc)
        if not rows and total is not None and off >= total:
            break          # past the last result: a normal end, not a failure
        if not rows:
            empty += 1
            if empty > backoff_tries:
                log(f"WARN search returned nothing {empty} times at offset {off}: stopping, the window may be INCOMPLETE")
                incomplete.append(off)
                break
            wait = 15 * 2 ** (empty - 1)
            log(f"search empty or rate limited at offset {off}: waiting {wait}s")
            time.sleep(wait)
            continue
        empty = 0
        for r in rows:
            if r["date"] and start_date.isoformat() <= r["date"] <= end_date.isoformat() and r["appid"] not in seen:
                seen.add(r["appid"])
                out.append(r)
        dated = [r["date"] for r in rows if r["date"]]
        log(f"search offset {off}: {dated[0] if dated else '?'} .. {dated[-1] if dated else '?'} ({len(out)} in window)")
        # stop once a whole page is older than the window (a few rows can be out of order)
        if dated and max(dated) < start_date.isoformat():
            break
        off += page
    return out


def tag_names() -> dict[int, str]:
    data = common.safe_json(TAGS_URL, default=[])
    return {int(t["tagid"]): t["name"] for t in data if isinstance(t, dict) and "tagid" in t} if isinstance(data, list) else {}


# ---------------------------------------------------------------- volume
def cmd_volume(a):
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    newest = today if a.include_today else today - datetime.timedelta(days=1)
    oldest = today - datetime.timedelta(days=a.days)
    bad: list[int] = []
    rows = collect_window(oldest, newest, a.cc, page=a.page, start=0, incomplete=bad)
    days = {}
    d = oldest
    while d <= newest:
        days[d.isoformat()] = dict(date=d.isoformat(), weekday=d.strftime("%a"), games=0, free=0, adult_flag=0, under_2usd=0)
        d += datetime.timedelta(days=1)
    for r in rows:
        x = days.get(r["date"])
        if not x:
            continue
        x["games"] += 1
        x["free"] += 1 if r["price_final_cents"] in (0, None) else 0
        x["adult_flag"] += 1 if set(r["descids"]) & ADULT_DESCIDS else 0
        x["under_2usd"] += 1 if (r["price_final_cents"] or 0) < 200 else 0
    counts = [x["games"] for x in days.values()]
    summary = dict(days=len(counts), total=sum(counts), min=min(counts) if counts else 0, median=statistics.median(counts) if counts else 0,
                   mean=round(statistics.mean(counts), 1) if counts else 0, max=max(counts) if counts else 0)
    res = dict(source=SEARCH.split("&start")[0], read_on=today.isoformat(), window=[oldest.isoformat(), newest.isoformat()],
               note="store search, games only (category1=998), logged-out view: adult-only titles may be hidden",
               summary=summary, incomplete_offsets=bad, per_day=list(days.values()), games=rows)
    write_json(res, p(a.dir, "volume.json"))
    print(f"{summary['days']} giorni, {summary['total']} giochi: min {summary['min']}, mediana {summary['median']}, max {summary['max']} al giorno")


# ---------------------------------------------------------------- fetch
def apply_histogram(r: dict, hist: dict | None) -> None:
    """Count only the reviews written from the release date on. A 1.0 launch of a game that was in Early Access for
    years carries its old reviews: without this it looks like a new hit. Marks such games `graduate`."""
    if not hist or not r.get("reviews_total") or not r.get("release_date"):
        return
    rel = datetime.date.fromisoformat(r["release_date"])
    roll = hist.get("rollups") or []
    if hist.get("rollup_type") == "month":
        cutoff = rel.replace(day=1)
    else:
        cutoff = rel - datetime.timedelta(days=7)
    day = lambda x: datetime.datetime.fromtimestamp(int(x["date"]), datetime.timezone.utc).date()  # noqa: E731
    tot = sum(x.get("recommendations_up", 0) + x.get("recommendations_down", 0) for x in roll)
    since = sum(x.get("recommendations_up", 0) + x.get("recommendations_down", 0) for x in roll if day(x) >= cutoff)
    if not tot:
        return
    first = datetime.datetime.fromtimestamp(int(hist.get("start_date") or roll[0]["date"]), datetime.timezone.utc).date()
    r["first_review"] = first.isoformat()
    r["reviews_total_raw"] = r["reviews_total"]
    r["pre_release_share"] = round(1 - since / tot, 3)
    r["reviews_total"] = round(r["reviews_total"] * since / tot)
    r["graduate"] = (rel - first).days > 30 and r["pre_release_share"] >= 0.10


def flatten(s: dict, details: dict | None, reviews: dict | None, spy: dict | None, tagmap: dict[int, str], today: datetime.date, hist: dict | None = None) -> dict:
    tags = [tagmap.get(t, str(t)) for t in s.get("tagids", [])]
    r = dict(appid=s["appid"], name=s.get("name"), search_date=s.get("date"), tags=tags, descids=s.get("descids", []),
             crtrids=s.get("crtrids", []), has_details=bool(details))
    if details:
        po = details.get("price_overview") or {}
        rel = parse_date((details.get("release_date") or {}).get("date"))
        genres = [g.get("description") for g in details.get("genres") or []]
        langs = [x for x in re.split(r",", re.sub(r"<br>.*$", "", details.get("supported_languages") or "", flags=re.S)) if strip_tags(x)]
        r.update(name=details.get("name") or r["name"], type=details.get("type"),
                 release_date=rel.isoformat() if rel else s.get("date"),
                 price=0.0 if details.get("is_free") else (po["initial"] / 100 if po.get("initial") is not None else None),
                 is_free=bool(details.get("is_free")), discount_now=po.get("discount_percent", 0),
                 genres=genres, categories=[c.get("description") for c in details.get("categories") or []],
                 early_access="Early Access" in genres or "70" in [str(g.get("id")) for g in details.get("genres") or []],
                 n_screenshots=len(details.get("screenshots") or []), n_movies=len(details.get("movies") or []),
                 short_desc_len=len(strip_tags(details.get("short_description"))), about_len=len(strip_tags(details.get("about_the_game") or details.get("detailed_description"))),
                 developers=details.get("developers") or [], publishers=details.get("publishers") or [],
                 has_demo=bool(details.get("demos")), n_languages=len(langs), required_age=str(details.get("required_age") or "0"),
                 content_descriptors=(details.get("content_descriptors") or {}).get("ids") or [],
                 header_image=details.get("header_image"), website=bool(details.get("website")))
        r["descids"] = sorted(set(r["descids"]) | set(r["content_descriptors"]))
    else:
        r.update(release_date=s.get("date"), price=(s["price_final_cents"] / 100) if s.get("price_final_cents") is not None else None)
    qs = (reviews or {}).get("query_summary") or {}
    if measured_reviews(reviews):
        r.update(reviews_total=qs["total_reviews"], reviews_positive=qs.get("total_positive"),
                 pct_positive=round(100 * qs["total_positive"] / qs["total_reviews"], 1) if qs["total_reviews"] and qs.get("total_positive") is not None else None,
                 review_desc=qs.get("review_score_desc"))
    else:
        r.update(reviews_total=None, reviews_positive=None, pct_positive=None, review_desc=None)
    r["graduate"] = False
    apply_histogram(r, hist)
    if spy:
        r["steamspy_owners"] = spy.get("owners")
    rel = r.get("release_date")
    r["days_out"] = (today - datetime.date.fromisoformat(rel)).days if rel else None
    if r["reviews_total"] is not None:
        r["copies_low"], r["copies_high"] = r["reviews_total"] * BOX_LOW, r["reviews_total"] * BOX_HIGH
    return r


def measured_reviews(rv):
    n = ((rv or {}).get("query_summary") or {}).get("total_reviews") if isinstance(rv, dict) else None
    return type(n) is int and n >= 0 and rv.get("success") == 1


def cmd_fetch(a):
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    d0, d1 = datetime.date.fromisoformat(a.date_from), datetime.date.fromisoformat(a.date_to)
    os.makedirs(p(a.dir, "apps"), exist_ok=True)
    wpath = p(a.dir, f"window_{d0}_{d1}.json")
    bad: list[int] = []
    if os.path.exists(wpath) and not a.refresh_window:
        window = common.load_json(wpath)["games"]
        log(f"window from cache: {len(window)} games ({wpath}); --refresh-window to search again")
    else:
        window = collect_window(d0, d1, a.cc, page=a.page, incomplete=bad)
        if bad:   # never cache a partial list as if it were the whole window
            log(f"WARN window incomplete (search failed at offsets {bad}): list not cached, run fetch again later")
        else:
            _write_quiet(dict(read_on=today.isoformat(), window=[d0.isoformat(), d1.isoformat()], games=window), wpath)
    limited = bool(a.limit and len(window) > a.limit)
    if a.limit:
        window = window[:a.limit]
    tpath = p(a.dir, "tags.json")
    tagmap = {int(k): v for k, v in common.load_json(tpath).items()} if os.path.exists(tpath) else ({} if bad else tag_names())
    if tagmap and not os.path.exists(tpath):
        write_json({str(k): v for k, v in tagmap.items()}, tpath)
    th_d, th_r, th_s = getattr(a, "throttles", None) or (Throttle(a.rate), Throttle(a.rate_reviews), Throttle(1.1))
    budget = getattr(a, "review_budget", None)
    fails = consecutive = 0
    for i, s in enumerate(window, 1):
        if bad:
            break   # do not start another batch of requests when search has already backed off and failed
        cp = p(a.dir, "apps", f"{s['appid']}.json")
        if os.path.exists(cp):
            cached = common.load_json(cp)
            cached["reviews_ok"] = measured_reviews(cached.get("reviews"))
            cached["hist_ok"] = bool((cached.get("hist") or {}).get("rollups"))
            if getattr(a, "retry_missing_store", False) and not cached.get("details"):
                cached["details_ok"] = False
            need_hist = a.histogram and not cached.get("hist_ok") and cached["reviews_ok"] and cached["reviews"]["query_summary"]["total_reviews"] > 0
            if cached.get("details_ok") and cached.get("reviews_ok") and (cached.get("spy") or not a.steamspy) and not need_hist:
                continue
        else:
            cached = {}
        if budget is not None and budget[0] <= 0:
            break
        details = cached.get("details")
        if not cached.get("details_ok"):
            dj = common.safe_json(APPDETAILS.format(appid=s["appid"], cc=a.cc), default={}, throttle=th_d)
            entry = dj.get(str(s["appid"])) if isinstance(dj, dict) else None
            details = entry.get("data") if isinstance(entry, dict) and entry.get("success") else None
            # success:false is a real answer (delisted / region locked); an empty body is a failure to retry later
            cached["details_ok"] = bool(entry is not None)
            if details:
                cached["store_observed_on"] = today.isoformat()
        reviews = cached.get("reviews")
        if not cached.get("reviews_ok"):
            reviews = common.safe_json(APPREVIEWS.format(appid=s["appid"]), default={}, throttle=th_r)
            if budget is not None:
                budget[0] -= 1
            cached["reviews_ok"] = measured_reviews(reviews)
            if cached["reviews_ok"]:
                cached["reviews_observed_on"] = today.isoformat()
        hist = cached.get("hist")
        if a.histogram and not cached.get("hist_ok") and measured_reviews(reviews) and reviews["query_summary"]["total_reviews"] > 0 and (budget is None or budget[0] > 0):
            h = common.safe_json(HISTOGRAM.format(appid=s["appid"]), default={}, throttle=th_r)
            if budget is not None:
                budget[0] -= 1
            cached["hist_ok"] = bool(h and h.get("success") == 1 and (h.get("results") or {}).get("rollups"))
            hist = h.get("results") if cached["hist_ok"] else None
            if hist:
                cached["hist_observed_on"] = today.isoformat()
        spy = cached.get("spy")
        if a.steamspy and not spy:
            spy = common.safe_json(STEAMSPY.format(appid=s["appid"]), default={}, throttle=th_s) or None
        if (not cached["details_ok"] or not cached["reviews_ok"] or
                (a.histogram and reviews["query_summary"]["total_reviews"] > 0 and not cached.get("hist_ok"))):
            fails += 1
            consecutive += 1
        else:
            consecutive = 0
        cached.update(search=s, details=details, reviews=reviews, hist=hist, spy=spy, fetched_on=today.isoformat())
        _write_quiet(cached, cp)
        if consecutive >= 3:
            log("WARN repeated source failures: pausing requests; retry this window later")
            break
        if i % 25 == 0:
            log(f"fetched {i}/{len(window)} (incomplete so far: {fails})")
    rows = []
    for s in window:
        cp = p(a.dir, "apps", f"{s['appid']}.json")
        c = common.load_json(cp) if os.path.exists(cp) else {}
        row = flatten(s, c.get("details"), c.get("reviews"), c.get("spy"), tagmap, today, c.get("hist"))
        row.update(store_observed_on=c.get("store_observed_on"),
                   reviews_observed_on=c.get("reviews_observed_on"), hist_observed_on=c.get("hist_observed_on"))
        rows.append(row)
    out = dict(read_on=today.isoformat(), window=[d0.isoformat(), d1.isoformat()],
               sources=dict(search=SEARCH.split("&start")[0], appdetails=APPDETAILS.split("?")[0], appreviews=APPREVIEWS.split("?")[0]),
               window_complete=not bad and not limited, incomplete_offsets=bad, limited=limited, source_paused=consecutive >= 3,
               n_no_histogram=sum(1 for r in rows if r.get("reviews_total_raw", r.get("reviews_total")) and not r.get("first_review")),
               n=len(rows), n_no_details=sum(1 for r in rows if not r["has_details"]), n_no_reviews=sum(1 for r in rows if r["reviews_total"] is None),
               n_graduates=sum(1 for r in rows if r.get("graduate")), games=rows)
    _write_quiet(out, p(a.dir, "cohort.json"))
    write_csv(rows, p(a.dir, "cohort.csv"))
    print(f"coorte {d0}..{d1}: {len(rows)} giochi, senza dati store {out['n_no_details']}, senza recensioni {out['n_no_reviews']}"
          + (" (rilancia fetch per riprovare: riprende da dove si era fermato)" if fails else ""))
    return out


def _write_quiet(obj, path):
    import json
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---------------------------------------------------------------- filter
def junk_reasons(r: dict, dev_counts: dict[str, int], a) -> list[str]:
    if not r.get("has_details"):
        return ["no_details"]
    why = []
    tags = {t.lower() for t in r.get("tags") or []}
    if set(r.get("descids") or []) & ADULT_DESCIDS or tags & ADULT_TAGS or (len(tags & SEXUAL_TAGS) == 2 and 4 in (r.get("descids") or [])):
        why.append("adult")
    if r.get("is_free") and (r.get("n_movies", 0) == 0 or r.get("n_screenshots", 0) < 5 or r.get("about_len", 0) < 300):
        why.append("free_thin")
    if r.get("n_movies", 0) == 0 and r.get("n_screenshots", 0) < a.min_screenshots:
        why.append("thin_page")
    devs = [d.strip().lower() for d in r.get("developers") or [] if d.strip()]
    if any(dev_counts.get(d, 0) >= a.flip_titles for d in devs):
        why.append("flip_dev")
    if GENERIC_NAME.search(r.get("name") or ""):
        why.append("generic_name")
    if r.get("short_desc_len", 0) < a.min_short_desc or r.get("about_len", 0) < a.min_about:
        why.append("short_desc")
    if tags & (SHOVEL_TAGS | {t.lower() for t in a.shovel_tag or []}):
        why.append("shovel_tags")
    return why


REASON_IT = dict(graduate="non è una nuova uscita: 1.0 di un gioco con recensioni di anni prima (Early Access)", no_details="dati store non disponibili (rimosso o bloccato per regione): escluso dal conteggio",
                 adult="solo contenuti per adulti", free_thin="gratis senza contenuto reale", thin_page="niente trailer e meno di 5 screenshot",
                 flip_dev="stesso sviluppatore con troppe uscite nella finestra (asset flip)", generic_name="nome generico da shovelware",
                 short_desc="descrizione troppo corta", shovel_tags="tag da shovelware")


def cmd_filter(a):
    c = common.load_json(p(a.dir, "cohort.json"))
    rows = c["games"]
    dev_counts: dict[str, int] = {}
    for r in rows:
        for d in {x.strip().lower() for x in r.get("developers") or [] if x.strip()}:
            dev_counts[d] = dev_counts.get(d, 0) + 1
    out = []
    for r in rows:
        why = junk_reasons(r, dev_counts, a)
        status = "missing" if why == ["no_details"] else ("junk" if why else "keep")
        if r.get("graduate") and status != "missing":
            status, why = "not_new", ["graduate"] + why
        out.append(dict(appid=r["appid"], name=r["name"], status=status, reasons=";".join(why),
                        price=r.get("price"), n_movies=r.get("n_movies"), n_screenshots=r.get("n_screenshots"),
                        short_desc_len=r.get("short_desc_len"), developers="; ".join(r.get("developers") or []), reviews_total=r.get("reviews_total")))
    write_csv(out, p(a.dir, "filtered.csv"))
    n = {s: sum(1 for x in out if x["status"] == s) for s in ("keep", "junk", "missing", "not_new")}
    counts: dict[str, int] = {}
    for x in out:
        for w in filter(None, x["reasons"].split(";")):
            counts[w] = counts.get(w, 0) + 1
    print(f"{len(out)} giochi: {n['keep']} restano, {n['junk']} esclusi come junk, {n['not_new']} non nuovi (1.0 di vecchi Early Access), {n['missing']} senza dati store")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {v:4d}  {k}: {REASON_IT.get(k, k)}")


# ---------------------------------------------------------------- sheets
def have_pil():
    try:
        from PIL import Image, ImageDraw  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def download_headers(rows: list[dict], hdir: str, rate: float) -> dict[int, str]:
    os.makedirs(hdir, exist_ok=True)
    th, got = Throttle(rate), {}
    for r in rows:
        fp = os.path.join(hdir, f"{r['appid']}.jpg")
        if os.path.exists(fp) and os.path.getsize(fp) > 0:
            got[r["appid"]] = fp
            continue
        for url in [u for u in (r.get("header_image"), HEADER_CDN.format(appid=r["appid"])) if u]:
            try:
                data = common.http_get(url, throttle=th, retries=1)
                if data and len(data) > 500:
                    with open(fp, "wb") as f:
                        f.write(data)
                    got[r["appid"]] = fp
                    break
            except Exception as e:  # noqa: BLE001
                log(f"WARN header {r['appid']}: {e}")
    return got


def sheet_pil(tiles: list[tuple[str, str | None]], out: str, cols: int, tw: int, th_: int):
    from PIL import Image, ImageDraw
    lab = 20
    rows_n = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * tw, rows_n * (th_ + lab)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, (label, fp) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th_ + lab)
        if fp:
            try:
                im = Image.open(fp).convert("RGB").resize((tw, th_))
                sheet.paste(im, (x, y))
            except Exception as e:  # noqa: BLE001
                log(f"WARN {fp}: {e}")
        dr.text((x + 4, y + th_ + 4), label[:44], fill=(255, 255, 255))
    sheet.save(out, quality=88)


def sheet_ffmpeg(tiles: list[tuple[str, str | None]], out: str, cols: int, tw: int, th_: int) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    font = next((f for f in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf") if os.path.exists(f)), None)
    lab = 22
    tmp = tempfile.mkdtemp(prefix="cohort_sheet_")
    try:
        rows_n = math.ceil(len(tiles) / cols)
        for i in range(rows_n * cols):
            label, fp = tiles[i] if i < len(tiles) else ("", None)
            lf = os.path.join(tmp, f"l{i:03d}.txt")
            with open(lf, "w", encoding="utf-8") as f:
                f.write(label[:44] or " ")
            src = ["-f", "lavfi", "-i", f"color=c=0x141414:s={tw}x{th_}"] if not fp else ["-i", os.path.abspath(fp)]
            vf = f"scale={tw}:{th_},format=rgb24,pad={tw}:{th_ + lab}:0:0:color=0x141414"
            if font:
                ff = font.replace(":", "\\:")
                vf += f",drawtext=fontfile='{ff}':textfile='l{i:03d}.txt':x=4:y={th_ + 4}:fontsize=14:fontcolor=white,format=rgb24"
            r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y"] + src + ["-frames:v", "1", "-vf", vf, f"t{i:03d}.png"],
                               cwd=tmp, capture_output=True, text=True)
            if r.returncode:
                log(f"WARN ffmpeg tile {i}: {r.stderr.strip()[:200]}")
                return False
        r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", "t%03d.png", "-vf", f"tile={cols}x{rows_n}", "-frames:v", "1", "-q:v", "3", os.path.abspath(out)],
                           cwd=tmp, capture_output=True, text=True)
        if r.returncode:
            log(f"WARN ffmpeg tile: {r.stderr.strip()[:200]}")
            return False
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sheet_html(tiles: list[tuple[str, str | None]], out: str, cols: int, tw: int):
    cells = "".join(f'<figure><img src="{("file:///" + os.path.abspath(fp).replace(os.sep, "/")) if fp else ""}" width="{tw}"><figcaption>{htmlmod.escape(lab)}</figcaption></figure>' for lab, fp in tiles)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f'<!doctype html><meta charset="utf-8"><style>body{{background:#141414;color:#fff;font:13px sans-serif;display:grid;grid-template-columns:repeat({cols},{tw}px);gap:6px}}figure{{margin:0}}</style>{cells}')


def cmd_sheets(a):
    c = common.load_json(p(a.dir, "cohort.json"))
    status = {int(r["appid"]): r["status"] for r in read_csv(p(a.dir, "filtered.csv"))}
    if not status:
        raise SystemExit("run `filter` first: filtered.csv not found")
    rows = [r for r in c["games"] if status.get(int(r["appid"])) in (("keep", "junk") if a.include_junk else ("keep",))]
    rows.sort(key=lambda r: r["appid"])
    got = download_headers(rows, p(a.dir, "headers"), a.rate)
    backend = "pil" if have_pil() else ("ffmpeg" if shutil.which("ffmpeg") else "html")
    if backend != "pil":
        log(f"Pillow non disponibile: uso {backend} per i fogli" + ("" if backend == "ffmpeg" else " (pagine HTML da aprire o fotografare; nessuna immagine generata)"))
    gpath = p(a.dir, "grades.csv")
    old = {int(g["appid"]): g for g in read_csv(gpath)}
    grades, per = [], a.per_sheet
    sdir = p(a.dir, "sheets")
    os.makedirs(sdir, exist_ok=True)
    nsheets = math.ceil(len(rows) / per) if rows else 0
    for si in range(nsheets):
        chunk = rows[si * per:(si + 1) * per]
        tiles = []
        if a.reference and os.path.exists(a.reference):
            tiles.append(("RIFERIMENTO (il tuo gioco)", a.reference))
        for j, r in enumerate(chunk, 1):
            tiles.append((f"{si + 1}.{j} {r['appid']} {r['name'] or ''}", got.get(r["appid"])))
            g = old.get(r["appid"], {})
            grades.append(dict(appid=r["appid"], name=r["name"], sheet=si + 1, idx=j, grade=g.get("grade", ""), note=g.get("note", ""),
                               header=os.path.relpath(got[r["appid"]], a.dir) if r["appid"] in got else ""))
        out = p(sdir, f"sheet_{si + 1:02d}." + ("html" if backend == "html" else "jpg"))
        if backend == "pil":
            sheet_pil(tiles, out, a.cols, a.tile_w, a.tile_h)
        elif backend == "ffmpeg":
            if not sheet_ffmpeg(tiles, out, a.cols, a.tile_w, a.tile_h):
                out = out[:-4] + ".html"
                sheet_html(tiles, out, a.cols, a.tile_w)
        else:
            sheet_html(tiles, out, a.cols, a.tile_w)
        log(f"wrote {out}")
    write_csv(grades, gpath, ["appid", "name", "sheet", "idx", "grade", "note", "header"])
    print(f"{len(rows)} capsule in {nsheets} fogli ({backend}); {len(got)} header scaricati. Compila la colonna grade di {gpath} con A / B / C:"
          " A = chiaramente sopra il tuo gioco, B = al tuo livello, C = sotto. Severità: il tuo gioco è B finché i dati non dicono altro.")


# ---------------------------------------------------------------- report
def shares(g: list[dict]) -> dict:
    """Outcome shares with the Boxleiter range: 'low' uses x20 (strict), 'high' uses x60 (generous)."""
    n = len(g)
    rv = [r["reviews_total"] for r in g]

    def both(fn):
        lo = sum(1 for r in g if fn(r, BOX_LOW))
        hi = sum(1 for r in g if fn(r, BOX_HIGH))
        return dict(k_low=lo, k_high=hi, pct_low=round(100 * lo / n, 1) if n else 0, pct_high=round(100 * hi / n, 1) if n else 0, ci_low=wilson(lo, n), ci_high=wilson(hi, n))
    res = dict(n=n, reviews_median=quantile(rv, .5), reviews_p75=quantile(rv, .75), reviews_p90=quantile(rv, .9), reviews_max=max(rv) if rv else None,
               zero_reviews=sum(1 for x in rv if x == 0),
               copies100=both(lambda r, m: r["reviews_total"] * m >= 100), copies1000=both(lambda r, m: r["reviews_total"] * m >= 1000),
               copies10000=both(lambda r, m: r["reviews_total"] * m >= 10000),
               gross800=both(lambda r, m: (r.get("price") or 0) * r["reviews_total"] * m >= 800),
               popular=both(lambda r, m: r["reviews_total"] >= POPULAR_REVIEWS or r["reviews_total"] * m >= POPULAR_COPIES))
    if rv:
        med = quantile(rv, .5)
        res["copies_median"] = (round(med * BOX_LOW), round(med * BOX_HIGH))
        res["copies_p75"] = (round(quantile(rv, .75) * BOX_LOW), round(quantile(rv, .75) * BOX_HIGH))
        res["copies_p90"] = (round(quantile(rv, .9) * BOX_LOW), round(quantile(rv, .9) * BOX_HIGH))
    return res


FEATURES = [("has_trailer", "ha un trailer"), ("n_movies", "video"), ("n_screenshots", "screenshot"), ("price", "prezzo $"), ("has_demo", "demo"),
            ("n_languages", "lingue"), ("early_access", "Early Access"), ("short_desc_len", "caratteri descrizione breve"), ("about_len", "caratteri descrizione"),
            ("has_publisher", "publisher diverso dallo sviluppatore"), ("discount_now", "sconto oggi %"), ("pct_positive", "% recensioni positive")]


def feat(r: dict, k: str):
    if k == "has_trailer":
        return 1 if r.get("n_movies", 0) > 0 else 0
    if k == "has_publisher":
        d = {x.lower() for x in r.get("developers") or []}
        pb = {x.lower() for x in r.get("publishers") or [] if x}
        return 1 if pb and not pb <= d else 0
    v = r.get(k)
    if isinstance(v, bool):
        return 1 if v else 0
    return v


def compare(win: list[dict], lose: list[dict]) -> list[dict]:
    out = []
    for k, label in FEATURES:
        w = [feat(r, k) for r in win if feat(r, k) is not None]
        l_ = [feat(r, k) for r in lose if feat(r, k) is not None]
        binary = k in ("has_trailer", "has_demo", "early_access", "has_publisher")
        f = (lambda v: round(100 * sum(v) / len(v), 1) if v else None) if binary else (lambda v: round(statistics.median(v), 2) if v else None)
        out.append(dict(feature=k, label=label, kind="% sì" if binary else "mediana", winners=f(w), losers=f(l_), n_w=len(w), n_l=len(l_)))
    return out


def correlations(g: list[dict]) -> list[dict]:
    out = []
    for k, label in FEATURES:
        if k == "pct_positive":
            continue
        pairs = [(feat(r, k), r["reviews_total"]) for r in g if feat(r, k) is not None]
        rho = spearman([float(x) for x, _ in pairs], [float(y) for _, y in pairs])
        out.append(dict(feature=k, label=label, rho=rho, n=len(pairs)))
    return out


def subset(rows: list[dict], a) -> list[dict]:
    out = rows
    if a.price_min is not None:
        out = [r for r in out if r.get("price") is not None and r["price"] >= a.price_min]
    if a.price_max is not None:
        out = [r for r in out if r.get("price") is not None and r["price"] <= a.price_max]
    if a.genres:
        want = [g.strip().lower().replace("-", "").replace(" ", "") for g in a.genres.split(",") if g.strip()]
        def match(r):
            have = [x.lower().replace("-", "").replace(" ", "") for x in (r.get("genres") or []) + (r.get("tags") or [])]
            return any(w in h for w in want for h in have)
        out = [r for r in out if match(r)]
    return out


def build_report(a) -> dict:
    c = common.load_json(p(a.dir, "cohort.json"))
    status = {int(r["appid"]): (r["status"], r["reasons"]) for r in read_csv(p(a.dir, "filtered.csv"))}
    grades = {int(g["appid"]): (g.get("grade") or "").strip().upper() for g in read_csv(p(a.dir, "grades.csv"))}
    vol = common.load_json(p(a.dir, "volume.json")) if os.path.exists(p(a.dir, "volume.json")) else None
    rows = []
    for r in c["games"]:
        st, why = status.get(int(r["appid"]), ("keep", ""))
        if st in ("missing", "not_new") or r.get("reviews_total") is None:
            continue
        r = dict(r, status=st, reasons=why, grade=grades.get(int(r["appid"]), "") if st == "keep" else "")
        rows.append(r)
    all_rows = rows
    rows = subset(rows, a)
    groups = {"tutti": rows, "junk": [r for r in rows if r["status"] == "junk"], "non junk": [r for r in rows if r["status"] == "keep"]}
    for gname in GRADES:
        groups[gname] = [r for r in rows if r["status"] == "keep" and r["grade"] == gname]
    groups["A+B"] = groups["A"] + groups["B"]
    groups["non giudicati"] = [r for r in rows if r["status"] == "keep" and r["grade"] not in GRADES]
    reasons: dict[str, int] = {}
    for r in groups["junk"]:
        for w in filter(None, r["reasons"].split(";")):
            reasons[w] = reasons.get(w, 0) + 1
    b = groups["B"]
    winners = [r for r in b if r["reviews_total"] >= a.win_reviews]
    losers = [r for r in b if r["reviews_total"] < a.lose_reviews]
    n_not_new = sum(1 for v in status.values() if v[0] == "not_new")
    res = dict(read_on=c["read_on"], window=c["window"], sources=c.get("sources"), n_cohort=c["n"], n_not_new=n_not_new,
               n_missing=c["n"] - len(all_rows) - n_not_new,
               subset=dict(price_min=a.price_min, price_max=a.price_max, genres=a.genres, n=len(rows)),
               junk_reasons=reasons, tiers={k: shares(v) for k, v in groups.items()},
               days_out_median=quantile([r["days_out"] for r in rows if r.get("days_out") is not None], .5),
               b_split=dict(win_reviews=a.win_reviews, lose_reviews=a.lose_reviews, n_win=len(winners), n_lose=len(losers), table=compare(winners, losers)),
               ab_correlations=correlations(groups["A+B"]), winners=[dict(appid=r["appid"], name=r["name"], reviews=r["reviews_total"], price=r.get("price")) for r in sorted(winners, key=lambda r: -r["reviews_total"])])
    if vol:
        s = vol["summary"]
        n = len(rows) or 1
        frac = {k: len(groups[k]) / n for k in ("junk", "non junk", "A", "B", "C", "A+B", "non giudicati")}
        res["volume"] = dict(read_on=vol["read_on"], window=vol["window"], summary=s, per_day=vol["per_day"],
                             per_day_est={k: (round(s["min"] * f, 1), round(s["median"] * f, 1), round(s["max"] * f, 1)) for k, f in frac.items()},
                             cohort_per_day=round(len(all_rows) / 7, 1) if c["window"] else None)
    ab = res["tiers"]["A+B"]
    if ab["n"]:
        per20 = lambda key, side: round(20 * ab[key][f"pct_{side}"] / 100, 1)  # noqa: E731
        res["of20_ab"] = {k: (per20(k, "low"), per20(k, "high")) for k in ("copies100", "copies1000", "copies10000", "gross800", "popular")}
    if a.mine_price is not None:
        mg = groups.get(a.mine_grade, [])
        res["mine"] = dict(grade=a.mine_grade, price=a.mine_price, n=len(mg), outcome=shares(mg) if mg else None,
                           gross_median=(round(res["tiers"][a.mine_grade].get("copies_median", (0, 0))[0] * a.mine_price), round(res["tiers"][a.mine_grade].get("copies_median", (0, 0))[1] * a.mine_price)) if mg else None)
    return res


def fmt_pct(x: dict) -> str:
    if x["pct_low"] == x["pct_high"]:
        return f"{x['pct_low']}% ({x['k_low']})"
    return f"{x['pct_low']}-{x['pct_high']}% ({x['k_low']}-{x['k_high']})"


def md_report(res: dict, a) -> str:
    sub = res["subset"]
    label = "tutta la coorte" if not (sub["price_min"] or sub["price_max"] or sub["genres"]) else f"sottoinsieme: prezzo {sub['price_min']}-{sub['price_max']} $, generi {sub['genres'] or 'tutti'}"
    L = [f"# Coorte di uscite Steam {res['window'][0]} .. {res['window'][1]} (calcolato da `cohort_bench.py`)", "",
         f"Letti il {res['read_on']} da {res['sources']['search']}, {res['sources']['appdetails']} e {res['sources']['appreviews']} **[FATTO]**. "
         f"{res['n_cohort']} giochi nella finestra, {res['n_missing']} senza dati store o recensioni e {res['n_not_new']} non nuovi (1.0 di vecchi Early Access con recensioni di anni prima), esclusi. "
         f"Le recensioni contano solo da quella di uscita in poi (istogramma pubblico delle recensioni). {label}: {sub['n']} giochi, "
         f"usciti da circa {res['days_out_median']:.0f} giorni (mediana).", ""]
    if res.get("volume"):
        v = res["volume"]; s = v["summary"]
        L += ["## Quanti giochi escono al giorno", "", f"Ultimi {s['days']} giorni ({v['window'][0]} .. {v['window'][1]}), letto il {v['read_on']} **[FATTO]**: "
              f"min **{s['min']}**, mediana **{s['median']}**, max **{s['max']}** giochi al giorno (totale {s['total']}).", "",
              "| Gruppo | al giorno (giorno calmo / mediano / pieno) |", "|---|---|"]
        L += [f"| {k} | {lo} / {md} / {hi} |" for k, (lo, md, hi) in v["per_day_est"].items()]
        L += ["", "_Le quote per gruppo vengono dalla coorte e sono applicate al volume di oggi **[STIMA]**._", ""]
    L += ["## Junk escluso automaticamente", "", "| Motivo | Giochi |", "|---|---|"] + [f"| {REASON_IT.get(k, k)} | {v} |" for k, v in sorted(res["junk_reasons"].items(), key=lambda kv: -kv[1])]
    L += ["", "_Un gioco può avere più motivi._", "",
          f"## Risultati per fascia (copie = recensioni × {BOX_LOW}..{BOX_HIGH} **[STIMA]**)", "",
          "A = chiaramente sopra il nostro gioco, B = al nostro livello, C = sotto (giudizio visivo della capsula, un solo valutatore).", "",
          "| Gruppo | n | recensioni mediana / p75 / p90 | 0 recensioni | ≥100 copie | ≥1.000 | ≥10.000 | ≥~800 $ lordi | popolare* |", "|---|---|---|---|---|---|---|---|---|"]
    for k, t in res["tiers"].items():
        if not t["n"]:
            L.append(f"| {k} | 0 | – | – | – | – | – | – | – |")
            continue
        L.append(f"| {k} | {t['n']} | {t['reviews_median']:.0f} / {t['reviews_p75']:.0f} / {t['reviews_p90']:.0f} | {t['zero_reviews']} | {fmt_pct(t['copies100'])} | {fmt_pct(t['copies1000'])} | "
                 f"{fmt_pct(t['copies10000'])} | {fmt_pct(t['gross800'])} | {fmt_pct(t['popular'])} |")
    L += ["", f"*Definizione di \"popolare\": ≥{POPULAR_REVIEWS} recensioni oppure ≥{POPULAR_COPIES:,} copie stimate. Ogni cella dà l'intervallo tra la stima prudente (×{BOX_LOW}) e quella generosa (×{BOX_HIGH}), e tra parentesi quanti giochi.",
          "Con meno di 30 giochi in un gruppo le percentuali sono indicative: l'errore è di ± 10-20 punti."]
    if res.get("of20_ab"):
        o = res["of20_ab"]
        L += ["", "## \"Su 20 giochi al nostro livello o sopra (A+B)…\"", "",
              f"- vendono almeno 100 copie: **{o['copies100'][0]}-{o['copies100'][1]}** **[STIMA]**",
              f"- vendono almeno 1.000 copie: **{o['copies1000'][0]}-{o['copies1000'][1]}**",
              f"- vendono almeno 10.000 copie: **{o['copies10000'][0]}-{o['copies10000'][1]}**",
              f"- diventano \"popolari\": **{o['popular'][0]}-{o['popular'][1]}**"]
    bs = res["b_split"]
    L += ["", f"## Cosa separa i B che vanno bene dai B che non vanno", "",
          f"Vincenti = B con ≥{bs['win_reviews']} recensioni (n = {bs['n_win']}); perdenti = B con <{bs['lose_reviews']} recensioni (n = {bs['n_lose']})."
          + (" **Campione troppo piccolo per conclusioni**: leggere solo come indizio." if min(bs["n_win"], bs["n_lose"]) < 8 else ""), "",
          "| Caratteristica | misura | vincenti | perdenti |", "|---|---|---|---|"]
    L += [f"| {t['label']} | {t['kind']} | {t['winners']} | {t['losers']} |" for t in bs["table"]]
    L += ["", "Correlazione di rango con le recensioni dentro A+B (Spearman, correlazione non è causalità):", "", "| Caratteristica | ρ | n |", "|---|---|---|"]
    L += [f"| {c['label']} | {c['rho']} | {c['n']} |" for c in res["ab_correlations"]]
    if res.get("mine") and res["mine"]["outcome"]:
        m = res["mine"]; o = m["outcome"]
        L += ["", f"## Se il nostro gioco è un {m['grade']} a {m['price']} $", "",
              f"Copie a ~3 mesi di un {m['grade']} tipico **[STIMA]**: mediana {o['copies_median'][0]:,}-{o['copies_median'][1]:,}, p75 {o['copies_p75'][0]:,}-{o['copies_p75'][1]:,}, p90 {o['copies_p90'][0]:,}-{o['copies_p90'][1]:,} (n = {m['n']}). "
              f"Lordo mediano a {m['price']} $: {m['gross_median'][0]:,}-{m['gross_median'][1]:,} $ (prima di IVA, sconti, resi e quota Steam)."]
    L += ["", "## Limiti", "", f"- Copie = recensioni × {BOX_LOW}..{BOX_HIGH} (metodo Boxleiter): ordine di grandezza, non vendite.",
          "- Le recensioni dopo l'uscita vengono dall'istogramma pubblico (settimanale), riproporzionato sul totale: piccolo errore ai bordi.",
          "- Il giudizio A/B/C è di un solo valutatore e guarda la capsula, non il gioco.",
          "- La ricerca dello store da non loggati nasconde i titoli solo per adulti e i giochi rimossi spariscono: il junk è sottostimato.",
          "- Una settimana di uscite: poche decine di giochi per fascia. Gli intervalli contano più dei decimali."]
    return "\n".join(L) + "\n"


def cmd_report(a):
    res = build_report(a)
    text = md_report(res, a)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    write_json(res, a.out or p(a.dir, "report.json"))


# ---------------------------------------------------------------- Steam news per app (pre-launch signals)
NEWS = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=100&maxlength=200"
NEWS_KINDS = {"demo": ["demo"], "next_fest": ["next fest", "nextfest", "steam next"], "playtest": ["playtest"], "trailer": ["trailer"],
              "festival": ["festival", "showcase"], "update": ["update", "patch", "hotfix"], "launch": ["out now", "launch", "release date", "available now"]}


def news_items(appid, th: Throttle) -> list[dict] | None:
    d = common.safe_json(NEWS.format(appid=appid), default={}, throttle=th)
    if not isinstance(d, dict) or "appnews" not in d:
        return None
    out = []
    for n in (d["appnews"].get("newsitems") or []):
        low = ((n.get("title") or "") + " " + (n.get("contents") or "")[:200]).lower()
        out.append(dict(date=datetime.datetime.fromtimestamp(n.get("date", 0), datetime.timezone.utc).date().isoformat(), title=(n.get("title") or "")[:120],
                        official=n.get("feedname") == "steam_community_announcements", kinds=[k for k, ws in NEWS_KINDS.items() if any(w in low for w in ws)]))
    return out


def cmd_news(a):
    """Official Steam news of every game of a cohort folder, cached in apps/<appid>.json (resumable)."""
    c = common.load_json(p(a.dir, "cohort.json"))
    budget = getattr(a, "max_requests", None)
    if budget is not None and budget < 0:
        raise SystemExit("--max-requests non può essere negativo")
    paid = getattr(a, "paid_only", False)
    kept = None
    if paid and os.path.isfile(p(a.dir, "filtered.csv")):
        kept = {str(r["appid"]) for r in read_csv(p(a.dir, "filtered.csv")) if r.get("status") == "keep"}
    th, done, attempts, remaining, failures = Throttle(a.rate), 0, 0, 0, 0
    for r in c["games"]:
        if paid and (r.get("is_free") or (_num(r.get("price")) or 0) <= 0
                     or kept is not None and str(r["appid"]) not in kept):
            continue
        cp = p(a.dir, "apps", f"{r['appid']}.json")
        cached = common.load_json(cp) if os.path.exists(cp) else {}
        if isinstance(cached.get("news"), list):
            continue
        if failures >= 3 or budget is not None and attempts >= budget:
            remaining += 1
            continue
        attempts += 1
        items = news_items(r["appid"], th)
        if items is None:
            failures += 1
            remaining += 1
            continue
        failures = 0
        cached["news"] = items
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(cp))
        os.close(fd)
        try:
            _write_quiet(cached, tmp)
            os.replace(tmp, cp)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        done += 1
        if done % 50 == 0:
            log(f"news {done}")
    print(f"news: {done} giochi aggiornati in {p(a.dir, 'apps')}")
    if remaining:
        log(f"WARN news parziali: {remaining} giochi senza risposta; {attempts} richieste. Riprendi dalla cache.")
        raise SystemExit(2)


# ---------------------------------------------------------------- rolling dataset (update) and calibration
MILESTONES = (30, 90, 180)
DATA_FIELDS = ["appid", "name", "release_date", "price", "is_free", "genres", "tags", "n_movies", "n_screenshots", "n_languages", "has_demo",
               "early_access", "has_publisher", "developers", "publishers", "status", "reasons", "grade", "store_prior", "first_review",
               "pre_release_share", "reviews_total_now", "pct_positive", "reviews_d30", "reviews_d90", "reviews_d180",
               "checked_d30", "checked_d90", "checked_d180", "header_image", "week", "store_observed_on",
               "global_tier", "grade_scope", "anchor_pack", "visual_batch", "header_sha256"]
PRICE_BANDS = [("0", 0, 0.01), ("<5", 0.01, 5), ("5-10", 5, 10.0001), ("10-15", 10.0001, 15.0001), ("15-20", 15.0001, 20.0001), ("20+", 20.0001, 10 ** 6)]
GENRE_BUCKETS = {"casual": ["casual"], "simulation": ["simulation"], "roguelite": ["roguelite", "roguelike", "rogue-lite", "rogue-like"],
                 "physics": ["physics"], "comedy/party": ["comedy", "funny", "party"], "action": ["action"], "adventure": ["adventure"],
                 "puzzle": ["puzzle"], "horror": ["horror"], "strategy": ["strategy"], "rpg": ["rpg"], "cozy": ["cozy", "relaxing", "wholesome"]}


def dataset_dir(a=None) -> str:
    return getattr(a, "dataset", None) or common.user_dir("cohorts")


def store_prior(r: dict) -> int:
    """Anti-junk prior 0-100 from the store page only (adapted from GamesTracker's quality_score store component).
    It never uses reviews or sales (those are the outcome): it orders capsules and flags thin pages; the A/B/C grade stays a judgment."""
    parts = [1.0 if (r.get("n_movies") or 0) > 0 else 0.0, min(1.0, (r.get("n_screenshots") or 0) / 8), min(1.0, (r.get("short_desc_len") or 0) / 150),
             min(1.0, (r.get("about_len") or 0) / 1500), min(1.0, (r.get("n_languages") or 0) / 5), min(1.0, len(r.get("tags") or []) / 5),
             1.0 if r.get("website") else 0.0, 1.0 if r.get("header_image") else 0.0]
    return round(100 * sum(parts) / len(parts))


def reviews_within(hist: dict | None, release: str, days: int, total_now: int | None) -> int | None:
    """Reviews written from the release date to release + `days`, from the public weekly histogram, scaled to the total
    (the histogram misses a few reviews). Works retroactively: a late check still gives the count at that milestone."""
    if not total_now:
        return 0 if total_now == 0 else None
    if not hist or not release:
        return None
    rel = datetime.date.fromisoformat(release)
    roll = hist.get("rollups") or []
    day = lambda x: datetime.datetime.fromtimestamp(int(x["date"]), datetime.timezone.utc).date()  # noqa: E731
    cnt = lambda x: x.get("recommendations_up", 0) + x.get("recommendations_down", 0)  # noqa: E731
    tot = sum(cnt(x) for x in roll)
    if not tot:
        return None
    lo = rel.replace(day=1) if hist.get("rollup_type") == "month" else rel - datetime.timedelta(days=7)
    hi = rel + datetime.timedelta(days=days)
    inside = sum(cnt(x) for x in roll if lo <= day(x) < hi)
    return round(total_now * inside / tot)


def dataset_row(r: dict, status: str, reasons: str, grade: str, week: str) -> dict:
    # The raw observation is not a signed visual assessment or a dated milestone.
    excluded = {"global_tier", "grade_scope", "anchor_pack", "visual_batch", "header_sha256"}
    d = {k: r[k] for k in DATA_FIELDS if k in r and k not in excluded and not k.startswith(("checked_d", "reviews_d"))}
    d.update(status=status, reasons=reasons, grade=grade, week=week, store_prior=store_prior(r),
             genres="; ".join(r.get("genres") or []), tags="; ".join(r.get("tags") or []),
             developers="; ".join(r.get("developers") or []), publishers="; ".join(r.get("publishers") or []),
             has_publisher=feat(r, "has_publisher"), reviews_total_now=r.get("reviews_total_raw", r.get("reviews_total")))
    for k in ("has_demo", "early_access", "is_free"):
        d[k] = 1 if r.get(k) else 0
    return d


def read_week(path: str) -> list[dict]:
    return read_csv(path)


def write_week(rows: list[dict], path: str):
    import contextlib
    import io
    if not rows:
        return
    fields = list(dict.fromkeys(DATA_FIELDS + [k for r in rows for k in r]))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    os.close(fd)
    try:
        with contextlib.redirect_stderr(io.StringIO()):   # the dataset is rewritten often: keep the console quiet
            write_csv(rows, tmp, fields)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def week_name(d0: datetime.date, d1: datetime.date) -> str:
    return f"cohort_{d0.isoformat()}_{d1.isoformat()}"


def cohort_quality(c, today):
    games = c["games"]
    n = len(games)
    nr = sum(type(r.get("reviews_total")) is int and r["reviews_total"] >= 0 for r in games)
    ns = sum(r.get("has_details") is True for r in games)
    window_ok = c.get("window_complete") is True and not c.get("incomplete_offsets") and not c.get("limited")
    nh = c.get("n_no_histogram", 0)
    complete = (window_ok and n > 0 and nr == ns == n and nh == 0 and c.get("n", n) == n
                and len({r["appid"] for r in games}) == n)
    return dict(complete=complete, window_complete=window_ok, n_games=n, n_reviews=nr, n_store=ns,
                n_no_histogram=nh, generated_on=today.isoformat(), observed_on=c.get("read_on"),
                window=c["window"], incomplete_offsets=c.get("incomplete_offsets", []))


def quality_path(path):
    return os.path.splitext(path)[0] + ".quality.json"


def verified_week(path):
    try:
        q = common.load_json(quality_path(path))
        return (q["complete"] is True and q["window_complete"] is True and q["n_games"] > 0
                and q["n_reviews"] == q["n_store"] == q["n_games"] and os.path.isfile(path))
    except (OSError, TypeError, ValueError, KeyError):
        return False


def milestone_ok(row, days, today):
    date = parse_date(row.get(f"checked_d{days}"))
    rel = parse_date(row.get("release_date"))
    return (row.get(f"reviews_d{days}") not in (None, "") and date and rel
            and rel + datetime.timedelta(days=days) <= date <= today)


def image_hash(path):
    if not os.path.isfile(path) or not os.path.getsize(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def import_cohort_dir(src: str, dsdir: str, today: datetime.date) -> str:
    """Seed the dataset from a folder made by fetch/filter/sheets (cohort.json, filtered.csv, grades.csv, apps/)."""
    c = common.load_json(os.path.join(src, "cohort.json"))
    status = {int(x["appid"]): (x["status"], x["reasons"]) for x in read_csv(os.path.join(src, "filtered.csv"))}
    grades = {int(g["appid"]): (g.get("grade") or "").strip().upper() for g in read_csv(os.path.join(src, "grades.csv"))}
    d0, d1 = (datetime.date.fromisoformat(x) for x in c["window"])
    name = week_name(d0, d1)
    os.makedirs(dsdir, exist_ok=True)
    path = os.path.join(dsdir, name + ".csv")
    quality = cohort_quality(c, today)
    if not c["games"] or any(int(r["appid"]) not in status for r in c["games"]):
        quality["complete"] = False
        quality["filter_incomplete"] = True
    if not quality["complete"]:
        # Keep a verified publication and any legacy CSV intact. No partial CSV is published.
        if not verified_week(path):
            _write_quiet(quality, quality_path(path))
        log(f"WARN {name}: window/store/reviews/filter incomplete or unverified; retry, no CSV published")
        return quality_path(path)
    rows = []
    for r in c["games"]:
        st, why = status.get(int(r["appid"]), ("keep", ""))
        row = dataset_row(r, st, why, grades.get(int(r["appid"]), "") if st == "keep" else "", name)
        cp = os.path.join(src, "apps", f"{r['appid']}.json")
        cache = common.load_json(cp) if os.path.exists(cp) else {}
        hist = cache.get("hist")
        row["header_sha256"] = image_hash(os.path.join(src, "headers", f"{r['appid']}.jpg"))
        # Old multi-source caches updated fetched_on on every retry, even when the
        # review response was older. Never reconstruct a milestone from that timestamp.
        fallback = c.get("read_on") if "fetched_on" not in cache and "reviews_observed_on" not in r else None
        reviewed = parse_date(r.get("reviews_observed_on") or cache.get("reviews_observed_on") or fallback)
        histogrammed = parse_date(r.get("hist_observed_on") or cache.get("hist_observed_on") or fallback)
        rel = parse_date(row.get("release_date"))
        for m in MILESTONES:
            cutoff = rel + datetime.timedelta(days=m) if rel else None
            if cutoff and reviewed and cutoff <= reviewed <= today and (
                    row["reviews_total_now"] == 0 or reviewed == histogrammed):
                v = reviews_within(hist, row["release_date"], m, row["reviews_total_now"])
                if v is not None:
                    row[f"reviews_d{m}"], row[f"checked_d{m}"] = v, reviewed.isoformat()
        rows.append(row)
    old = {int(x["appid"]): x for x in read_week(path)} if os.path.exists(path) else {}
    for row in rows:   # never lose grades or checks already in the dataset
        o = old.get(int(row["appid"]))
        if o:
            row["grade"] = row.get("grade") or o.get("grade", "")
            if row["header_sha256"] and row["header_sha256"] == o.get("header_sha256"):
                for k in ("global_tier", "grade_scope", "anchor_pack", "visual_batch"):
                    row[k] = o.get(k, "")
            for m in MILESTONES:
                if o.get("release_date") == row.get("release_date") and milestone_ok(o, m, today):
                    row[f"reviews_d{m}"], row[f"checked_d{m}"] = o[f"reviews_d{m}"], o[f"checked_d{m}"]
    write_week(rows, path)
    with open(os.path.join(dsdir, name + ".source"), "w", encoding="utf-8") as f:
        f.write(os.path.abspath(src))
    _write_quiet(quality, quality_path(path))
    return path


def last_full_week(today: datetime.date, lag_days: int = 2) -> tuple[datetime.date, datetime.date]:
    """The latest Monday-Sunday week that ended at least `lag_days` ago."""
    end = today - datetime.timedelta(days=lag_days)
    sunday = end - datetime.timedelta(days=(end.weekday() + 1) % 7)
    return sunday - datetime.timedelta(days=6), sunday


def recheck_week(path: str, today: datetime.date, a, budget: list[int]) -> int:
    rows = read_week(path)
    th = getattr(a, "review_throttle", None) or Throttle(a.rate_reviews)
    done = fails = 0
    for row in rows:
        if budget[0] <= 0:
            break
        if row.get("status") == "missing" or not row.get("release_date"):
            continue
        rel = datetime.date.fromisoformat(row["release_date"])
        due = [m for m in MILESTONES if today >= rel + datetime.timedelta(days=m) and not milestone_ok(row, m, today)]
        if not due:
            continue
        rv = common.safe_json(APPREVIEWS.format(appid=row["appid"]), default={}, throttle=th)
        qs = rv.get("query_summary") if isinstance(rv, dict) and rv.get("success") == 1 else None
        budget[0] -= 1
        if not measured_reviews(rv):
            fails += 1
            if fails >= 3:
                a.recheck_paused = True
                break
            continue
        total = qs["total_reviews"]
        hist = None
        if total and budget[0] > 0:
            h = common.safe_json(HISTOGRAM.format(appid=row["appid"]), default={}, throttle=th)
            hist = h.get("results") if isinstance(h, dict) and h.get("success") == 1 else None
            budget[0] -= 1
        row["reviews_total_now"] = total
        row["pct_positive"] = round(100 * qs["total_positive"] / total, 1) if total and qs.get("total_positive") is not None else ""
        for m in due:
            v = reviews_within(hist, row["release_date"], m, total)
            if v is not None:
                row[f"reviews_d{m}"], row[f"checked_d{m}"] = v, today.isoformat()
        checked = any(milestone_ok(row, m, today) for m in due)
        done += checked
        fails = 0 if checked else fails + 1
        if fails >= 3:
            a.recheck_paused = True
            break
        if checked and done % 25 == 0:
            write_week(rows, path)
    if done:
        write_week(rows, path)
    return done


def merge_work_grades(path: str, work: str) -> int:
    gp = os.path.join(work, "grades.csv")
    if not os.path.exists(gp) or not os.path.exists(path):
        return 0
    grades = {int(g["appid"]): (g.get("grade") or "").strip().upper() for g in read_csv(gp)}
    rows, n = read_week(path), 0
    for row in rows:
        g = grades.get(int(row["appid"]), "")
        if g in GRADES and not row.get("grade") and row.get("status") == "keep":
            row["grade"], n = g, n + 1
    if n:
        write_week(rows, path)
    return n


def cmd_update(a):
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    ds = dataset_dir(a)
    os.makedirs(ds, exist_ok=True)
    if a.new_weeks < 0 or a.max_requests < 0 or (a.limit is not None and a.limit <= 0):
        raise SystemExit("--new-weeks/--max-requests must be non-negative and --limit positive")
    if a.import_dir:
        p_ = import_cohort_dir(a.import_dir, ds, today)
        print(f"esito importazione {a.import_dir}: {p_}")
    work_root = os.path.join(ds, "_work")
    budget = [a.max_requests]
    throttles = Throttle(a.rate), Throttle(a.rate_reviews), Throttle(1.1)
    recent = last_full_week(today)
    paused = False
    for i in range(a.new_weeks):
        d0, d1 = (d - datetime.timedelta(weeks=i) for d in recent)
        name = week_name(d0, d1)
        path = os.path.join(ds, name + ".csv")
        if verified_week(path):
            continue
        if budget[0] <= 0:
            break
        work = os.path.join(work_root, name)
        os.makedirs(work, exist_ok=True)
        log(f"new release week {d0} .. {d1}: fetching into {work} (resumable)")
        ns = argparse.Namespace(**vars(a))
        ns.dir, ns.date_from, ns.date_to = work, d0.isoformat(), d1.isoformat()
        ns.refresh_window, ns.steamspy, ns.histogram, ns.page = False, False, True, 100
        ns.review_budget, ns.throttles, ns.retry_missing_store = budget, throttles, True
        try:
            c = cmd_fetch(ns)
        except SystemExit as exc:
            c = dict(games=[], window=[ns.date_from, ns.date_to], read_on=today.isoformat(), window_complete=False)
            log(f"WARN {name}: {exc}")
        quality = cohort_quality(c, today)
        if not quality["complete"]:
            _write_quiet(quality, quality_path(path))
            log(f"WARN {name} parziale: store {quality['n_store']}/{quality['n_games']}, recensioni {quality['n_reviews']}/{quality['n_games']}; "
                "nessuna nuova settimana pubblicata. Riprendi con update.")
            if c.get("limited") or (c.get("window_complete") and not c.get("source_paused") and budget[0] > 0):
                continue
            paused = True
            break
        cmd_filter(argparse.Namespace(dir=work, min_screenshots=5, flip_titles=3, min_short_desc=40, min_about=200, shovel_tag=None))
        cmd_sheets(argparse.Namespace(dir=work, include_junk=False, rate=0.25, per_sheet=30, cols=6, tile_w=320, tile_h=150, reference=a.reference))
        import_cohort_dir(work, ds, today)
        print(f"NUOVA SETTIMANA {name}: giudica le capsule in {os.path.join(work, 'sheets')} e compila {os.path.join(work, 'grades.csv')} "
              "(A/B/C, severo: il tuo gioco è B salvo prove), poi rilancia update")
    merged = 0
    for f in sorted(os.listdir(ds)):
        if f.endswith(".source"):
            with open(os.path.join(ds, f), encoding="utf-8") as fh:
                src = fh.read().strip()
            merged += merge_work_grades(os.path.join(ds, f[:-7] + ".csv"), src)
    if a.volume and not paused:   # the daily volume of the last two weeks, for the status page
        try:
            cmd_volume(argparse.Namespace(today=a.today, include_today=False, days=14, cc=a.cc, page=100, dir=common.user_dir()))
        except SystemExit as e:
            log(f"WARN volume not refreshed: {e}")
    checked = 0
    a.review_throttle = throttles[1]
    for f in sorted(os.listdir(ds)):
        if getattr(a, "recheck_paused", False):
            log("WARN review source unavailable; leaving due checks for the next run")
            break
        if not paused and budget[0] > 0 and f.startswith("cohort_") and f.endswith(".csv"):
            checked += recheck_week(os.path.join(ds, f), today, a, budget)
    weeks = [f for f in os.listdir(ds) if f.startswith("cohort_") and f.endswith(".csv")]
    ungraded = sum(1 for f in weeks for r in read_week(os.path.join(ds, f)) if r.get("status") == "keep" and r.get("grade") not in GRADES)
    print(f"dataset {ds}: {len(weeks)} settimane, {merged} voti importati, {checked} giochi ricontrollati (30/90/180 giorni), {ungraded} capsule ancora da giudicare"
          + ("; budget di richieste esaurito: rilancia per continuare" if budget[0] <= 0 else ""))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def group_stats(rows: list[dict], key: str) -> dict:
    vals = [int(float(r[key])) for r in rows if _num(r.get(key)) is not None]
    n = len(vals)
    if not n:
        return dict(n=0)

    def share(fn):
        lo, hi = sum(1 for v in vals if fn(v, BOX_LOW)), sum(1 for v in vals if fn(v, BOX_HIGH))
        return dict(pct_low=round(100 * lo / n, 1), pct_high=round(100 * hi / n, 1), ci_low=wilson(lo, n), ci_high=wilson(hi, n))
    q = {k: quantile(vals, p) for k, p in (("p25", .25), ("median", .5), ("p75", .75), ("p90", .9))}
    return dict(n=n, reviews={k: round(v, 1) for k, v in q.items()},
                copies={k: [round(v * BOX_LOW), round(v * BOX_HIGH)] for k, v in q.items()},
                copies100=share(lambda v, m: v * m >= 100), copies1000=share(lambda v, m: v * m >= 1000), copies10000=share(lambda v, m: v * m >= 10000),
                popular=share(lambda v, m: v >= POPULAR_REVIEWS or v * m >= POPULAR_COPIES), small_sample=n < 30)


def price_band(p) -> str | None:
    p = _num(p)
    if p is None:
        return None
    for label, lo, hi in PRICE_BANDS:
        if lo <= p < hi or (label == "0" and p == 0):
            return label
    return None


def in_bucket(r: dict, words: list[str]) -> bool:
    have = (r.get("genres") or "").lower().replace("-", "") + ";" + (r.get("tags") or "").lower().replace("-", "")
    return any(w.replace("-", "") in have for w in words)


def as_feature_row(r: dict) -> dict:
    return dict(n_movies=_num(r.get("n_movies")) or 0, n_screenshots=_num(r.get("n_screenshots")), price=_num(r.get("price")),
                has_demo=int(_num(r.get("has_demo")) or 0), n_languages=_num(r.get("n_languages")), early_access=int(_num(r.get("early_access")) or 0),
                short_desc_len=None, about_len=None, discount_now=None, pct_positive=_num(r.get("pct_positive")),
                developers=[x for x in (r.get("developers") or "").split("; ") if x], publishers=[x for x in (r.get("publishers") or "").split("; ") if x])


METRO_PROTOCOL = "asof-v1"


def _day(value) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _quality(path, n, today):
    manifest = os.path.splitext(path)[0] + ".quality.json"
    if not os.path.isfile(manifest):
        return "legacy"
    try:
        q = common.load_json(manifest)
    except (OSError, ValueError):
        return "incomplete"
    if (isinstance(q, dict) and q.get("complete") is True and q.get("window_complete") is True
            and n > 0 and all(type(q.get(k)) is int and q[k] == n for k in ("n_games", "n_reviews", "n_store"))
            and _day(q.get("generated_on")) and _day(q["generated_on"]) <= today):
        return "verified"
    return "incomplete"


def _global_grade(row):
    if (row.get("global_tier") in GRADES and row.get("grade_scope") == "global_verified"
            and (row.get("anchor_pack") or "").strip() and (row.get("visual_batch") or "").strip()):
        return row["global_tier"]
    return None


def _observed_outcome(row, days, today):
    rel, checked = _day(row.get("release_date")), _day(row.get(f"checked_d{days}"))
    v = _num(row.get(f"reviews_d{days}"))
    if rel and checked and rel + datetime.timedelta(days=days) <= checked <= today and v is not None and math.isfinite(v) and v >= 0:
        return v
    return None


def build_calibration(ds: str, today: datetime.date, market_dir: str | None = None) -> dict:
    rows = []
    legacy = []
    quality = dict(verified_weeks=0, legacy_weeks=0, incomplete_weeks=0, legacy_grades=0)
    for f in sorted(os.listdir(ds)) if os.path.isdir(ds) else []:
        if f.startswith("cohort_") and f.endswith(".csv"):
            path = os.path.join(ds, f)
            week = read_week(path)
            state = _quality(path, len(week), today)
            quality[state + "_weeks"] += 1
            if state != "verified":
                if state == "legacy":
                    quality["legacy_grades"] += sum(r.get("grade") in GRADES for r in week)
                    legacy.extend(r for r in week if r.get("status") == "keep")
                continue
            for r in week:
                grade = _global_grade(r)
                quality["legacy_grades"] += int(not grade and r.get("grade") in GRADES)
                rows.append(dict(r, grade=grade, **{f"reviews_d{m}": _observed_outcome(r, m, today) for m in MILESTONES}))
    new = [r for r in rows if r.get("status") == "keep"]
    graded = [r for r in new if r.get("grade") in GRADES]
    rel = sorted(r["release_date"] for r in rows if r.get("release_date"))
    cal = dict(generated_on=today.isoformat(), quality=quality, data_from=rel[0] if rel else None, data_to=rel[-1] if rel else None,
               weeks=sorted({r.get("week") for r in rows if r.get("week")}), n_games=len(rows), n_new=len(new), n_graded=len(graded),
               definitions=dict(copies=f"reviews x {BOX_LOW}..{BOX_HIGH} (Boxleiter) [STIMA]", popular=f">= {POPULAR_REVIEWS} reviews or >= {POPULAR_COPIES} estimated copies",
                                 tiers="global verified visual tier against the fixed genre anchor pack, not relative to the user's game",
                                reviews_dN="reviews written from release to release+N days (public weekly histogram)"),
               sources=dict(search=SEARCH.split("&start")[0], appdetails=APPDETAILS.split("?")[0], appreviews=APPREVIEWS.split("?")[0], histogram=HISTOGRAM.split("?")[0]),
               milestones={}, b_factors=None, controls=None, junk_share=round(sum(1 for r in rows if r.get("status") == "junk") / len(rows), 3) if rows else None,
               tier_share={g: round(sum(1 for r in graded if r["grade"] == g) / len(graded), 3) for g in GRADES} if graded else {})
    if legacy:
        # Keep historical descriptives accessible without feeding them to forecasts or to the global tiers.
        cal["legacy_descriptive"] = dict(n=len(legacy), scope="unverified_history", milestones={
            f"d{m}": group_stats([{f"reviews_d{m}": _observed_outcome(r, m, today)} for r in legacy], f"reviews_d{m}")
            for m in MILESTONES})
    for m in MILESTONES:
        key = f"reviews_d{m}"
        have = [r for r in graded if _num(r.get(key)) is not None]
        if not any(_num(r.get(key)) is not None for r in new):
            continue
        ms = dict(n=len(have), tiers={}, by_price={}, by_genre={})
        for t in ("A", "B", "C", "A+B"):
            g = [r for r in have if (r["grade"] in ("A", "B") if t == "A+B" else r["grade"] == t)]
            ms["tiers"][t] = group_stats(g, key)
            ms["by_price"][t] = {lab: group_stats([r for r in g if price_band(r.get("price")) == lab], key) for lab, _, _ in PRICE_BANDS}
            ms["by_genre"][t] = {b: group_stats([r for r in g if in_bucket(r, w)], key) for b, w in GENRE_BUCKETS.items()}
        ms["tiers"]["all_new"] = group_stats([r for r in new if _num(r.get(key)) is not None], key)
        cal["milestones"][f"d{m}"] = ms
    # d90 is the reference; until it covers at least half of the d30 sample (and 30 games), d30 is used and labelled
    n30 = cal["milestones"].get("d30", {}).get("n", 0)
    n90 = cal["milestones"].get("d90", {}).get("n", 0)
    prim = "d90" if n90 >= max(30, n30 // 2) else ("d30" if n30 else next(iter(cal["milestones"]), None))
    cal["primary"] = prim
    if prim:
        key = "reviews_" + prim
        b = [r for r in graded if r["grade"] == "B" and _num(r.get(key)) is not None]
        win = [r for r in b if float(r[key]) >= 50]
        lose = [r for r in b if float(r[key]) < 10]
        table = compare([as_feature_row(r) for r in win], [as_feature_row(r) for r in lose])
        cal["b_factors"] = dict(milestone=prim, n_win=len(win), n_lose=len(lose), small_sample=min(len(win), len(lose)) < 8,
                                table=[t for t in table if t["feature"] not in ("short_desc_len", "about_len", "discount_now")])
        recent = sorted(b, key=lambda r: r.get("release_date") or "", reverse=True)

        def pick(xs):
            return [dict(appid=int(r["appid"]), name=r["name"], release_date=r["release_date"], price=_num(r.get("price")), reviews=int(float(r[key])),
                         header_image=r.get("header_image") or HEADER_CDN.format(appid=r["appid"])) for r in xs[:12]]
        cal["controls"] = dict(milestone=prim, b_winners=pick([r for r in recent if float(r[key]) >= 50]), b_losers=pick([r for r in recent if float(r[key]) < 10]),
                               note="real recent B-tier releases: show them as control capsules in the waves, next to the game")
    if prim:
        key = "reviews_" + prim
        buckets = [("0", 0, 1), ("1-9", 1, 10), ("10-49", 10, 50), ("50-499", 50, 500), ("500-4.999", 500, 5000), ("5.000+", 5000, 10 ** 9)]
        cal["distribution"] = dict(milestone=prim, buckets=[dict(label=lab, **{t: sum(1 for r in graded if r["grade"] == t and _num(r.get(key)) is not None and lo <= float(r[key]) < hi) for t in GRADES})
                                                            for lab, lo, hi in buckets])
        vals = sorted((float(r[key]) for r in new if _num(r.get(key)) is not None), reverse=True)
        tot = sum(vals) or 1
        cal["concentration"] = dict(n=len(vals), top1=round(100 * sum(vals[:max(1, len(vals) // 100)]) / tot, 1), top10=round(100 * sum(vals[:max(1, len(vals) // 10)]) / tot, 1),
                                    bottom50=round(100 * sum(vals[len(vals) // 2:]) / tot, 1), zero=sum(1 for v in vals if v == 0))
    if market_dir and os.path.isdir(os.path.join(market_dir)):
        tp = os.path.join(market_dir, "tracked.json")
        if os.path.exists(tp):
            tr = common.load_json(tp)
            last = {}
            for r in read_csv(os.path.join(market_dir, "snapshots.csv")) if os.path.exists(os.path.join(market_dir, "snapshots.csv")) else []:
                last[str(r["appid"])] = r
            cal["head"] = [dict(appid=e["appid"], name=e.get("name"), roles=e["roles"], reviews=int(float(last[k]["reviews_total"])) if k in last and last[k].get("reviews_total") not in ("", None) else None,
                                peak_in_game=e.get("peak_in_game")) for k, e in tr.items() if {"most_played", "top_seller"} & set(e["roles"])]
            cal["breakouts"] = [dict(appid=e["appid"], name=e.get("name"), release_date=e.get("release_date"), reviews_per_day=e.get("breakout_reviews_per_day"),
                                     curve=e.get("curve") or {}) for e in tr.values() if "breakout" in e["roles"]]
    if market_dir and os.path.isdir(market_dir):
        try:
            import market_tracker
            cal["marketing"] = market_tracker.marketing_patterns(market_dir, {int(r["appid"]): r for r in graded}, prim)
        except Exception as e:  # noqa: BLE001
            log(f"WARN marketing patterns skipped: {e}")
    return cal


def base_rate(cal: dict, tier: str = "B", price: float | None = None, genre: str | None = None, milestone: str | None = None, min_n: int = 30) -> tuple[dict, str]:
    """The most specific group with at least `min_n` games: tier x price band, tier x genre, else the whole tier."""
    if not (cal.get("quality") or {}).get("verified_weeks"):
        return {}, "storico senza verifica di completezza e ambito dei voti"
    m = cal.get("milestones", {}).get(milestone or cal.get("primary") or "", {})
    if not m:
        return {}, "nessun dato"
    if price is not None:
        g = m["by_price"].get(tier, {}).get(price_band(price) or "", {})
        if g.get("n", 0) >= min_n:
            return g, f"fascia {tier}, prezzo {price_band(price)} $"
    if genre:
        g = m["by_genre"].get(tier, {}).get(genre, {})
        if g.get("n", 0) >= min_n:
            return g, f"fascia {tier}, genere {genre}"
    return m["tiers"].get(tier, {}), f"fascia {tier} (tutti i prezzi e generi)"


def cmd_calibrate(a):
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    cal = build_calibration(dataset_dir(a), today, a.market_dir or common.user_dir("market"))
    write_json(cal, a.out or common.user_dir("calibration.json"))
    if not cal.get("primary"):
        print("nessun dato con esito ancora: lancia `update` (e giudica le capsule) prima di `calibrate`")
        return
    t = cal["milestones"][cal["primary"]]["tiers"]
    L = [f"# Calibrazione dal mercato reale ({cal['generated_on']})", "",
         f"Dati: uscite dal {cal['data_from']} al {cal['data_to']}, {cal['n_new']} giochi nuovi, {cal['n_graded']} giudicati A/B/C; esito a {cal['primary'][1:]} giorni. "
         f"Copie = recensioni × {BOX_LOW}..{BOX_HIGH} **[STIMA]**.", "", "| Fascia | n | copie mediana | ≥1.000 copie | popolare |", "|---|---|---|---|---|"]
    for k in ("A", "B", "C", "A+B", "all_new"):
        g = t.get(k, {})
        if g.get("n"):
            L.append(f"| {k} | {g['n']} | {g['copies']['median'][0]:,}-{g['copies']['median'][1]:,} | {g['copies1000']['pct_low']}-{g['copies1000']['pct_high']}% | "
                     f"{g['popular']['pct_low']}-{g['popular']['pct_high']}% |")
    text = "\n".join(L) + "\n"
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(text)


# ---------------------------------------------------------------- the objective "metro": pre-launch features -> outcome bands
# Only what can be seen BEFORE release; target = estimated copies at 30 or 90 days, as bands. Transparent logistic models
# fitted with plain gradient descent, validated out-of-time (older release weeks -> newer ones) against "base rate only".
METRO_MULT = 35          # copies per review for the bands: the geometric middle of Boxleiter 20..60
METRO_BANDS = [("<100", 0, 100), ("100-1k", 100, 1000), ("1k-10k", 1000, 10000), (">10k", 10000, 10 ** 12)]
METRO_FEATS = [   # key, plain-Italian label, kind (bin = yes/no, num = number)
    ("tier_A", "capsule di fascia A (sopra di noi)", "bin"), ("tier_C", "capsule di fascia C (sotto di noi)", "bin"),
    ("price_log", "prezzo più alto", "num"), ("free", "gratis", "bin"), ("trailer", "ha un trailer", "bin"), ("movies", "numero di video", "num"),
    ("screens", "numero di screenshot", "num"), ("gif", "GIF nella descrizione", "bin"), ("desc_log", "descrizione più lunga", "num"),
    ("langs_log", "più lingue", "num"), ("publisher", "ha un publisher", "bin"), ("early_access", "Early Access", "bin"),
    ("demo_pre", "demo documentata prima dell'uscita", "bin"), ("nextfest_pre", "Next Fest documentato prima dell'uscita", "bin"), ("playtest_pre", "playtest documentato prima dell'uscita", "bin"),
    ("news_pre_log", "più notizie ufficiali prima dell'uscita", "num"), ("comingsoon_log", "pagina/notizie attive da più tempo (Coming Soon)", "num"),
    ("crowd_log", "giorno di uscita più affollato", "num"),
    ("g_casual", "genere casual", "bin"), ("g_action", "genere azione", "bin"), ("g_sim", "genere simulazione", "bin"), ("g_strategy", "genere strategia", "bin"),
    ("g_rpg", "genere GDR", "bin"), ("g_adventure", "genere avventura", "bin")]
# a lever changes the features that go together (a trailer is also a video; a demo is announced in the news...)
METRO_LEVERS = [("trailer", {"trailer": 1, "movies": 1}, "Trailer sulla pagina"),
                ("demo_pre", {"demo_pre": 1}, "Demo documentata prima dell'uscita"),
                ("nextfest_pre", {"nextfest_pre": 1}, "Steam Next Fest documentato prima dell'uscita"),
                ("playtest_pre", {"playtest_pre": 1}, "Playtest su Steam"), ("langs_log", {"langs_log": math.log1p(8)}, "8 lingue"),
                ("comingsoon_log", {"comingsoon_log": math.log1p(180)}, "Pagina e notizie visibili da 6 mesi"),
                ("news_pre_log", {"news_pre_log": math.log1p(8)}, "8 notizie ufficiali prima dell'uscita"), ("screens", {"screens": 1.2}, "12 screenshot")]


def prelaunch_features(r: dict, details: dict | None, news: list | None, crowd: int | None, grade: str | None) -> dict:
    """Unknown != absent. Never backdate today's store page, grade or release-day volume."""
    rel = _day(r.get("release_date"))
    store = _day(r.get("store_observed_on"))
    # Steam's last-100 feed is censored by later activity. Absence/counts in a
    # saturated retrospective feed cannot be interpreted as pre-launch observations.
    complete_news = isinstance(news, list) and len(news) < 100 and all(isinstance(n, dict) and _day(n.get("date")) for n in news)
    pre = [n for n in news if rel and _day(n["date"]) < rel] if complete_news else []
    off = [n for n in pre if n.get("official")]
    x = {}
    if complete_news and rel:
        first = min((_day(n["date"]) for n in pre), default=None)
        x.update(demo_pre=int(any("demo" in n.get("kinds", []) for n in pre)),
                 nextfest_pre=int(any("next_fest" in n.get("kinds", []) for n in pre)),
                 playtest_pre=int(any("playtest" in n.get("kinds", []) for n in pre)),
                 news_pre_log=math.log1p(len(off)), comingsoon_log=math.log1p((rel-first).days) if first else 0.0)
    if rel and store and store < rel and details:
        about = details.get("about_the_game") or details.get("detailed_description") or ""
        inputs = dict(r, gif=".gif" in about.lower(), publisher=bool(feat(r, "has_publisher")), tier=None)
        page = features_from_json(inputs)
        x.update({k: page[k] for k in page if k not in ("tier_A", "tier_C", "demo_pre", "nextfest_pre", "playtest_pre",
                                                        "news_pre_log", "comingsoon_log", "crowd_log")})
        if r.get("has_demo"):
            x["demo_pre"] = 1
    if rel and grade in GRADES and _day(r.get("grade_observed_on")) and _day(r["grade_observed_on"]) < rel:
        x.update(tier_A=int(grade == "A"), tier_C=int(grade == "C"))
    return x


def metro_rows(ds: str, today: datetime.date | None = None) -> list[dict]:
    """Paid releases from complete weeks only. Paid status defines the sample, not a predictor."""
    today = today or datetime.date.today()
    out = {}
    duplicates = set()
    for f in sorted(os.listdir(ds)) if os.path.isdir(ds) else []:
        if not f.endswith(".source"):
            continue
        with open(os.path.join(ds, f), encoding="utf-8") as fh:
            work = fh.read().strip()
        path = os.path.join(ds, f[:-7] + ".csv")
        week = read_week(path)
        if not week or _quality(path, len(week), today) != "verified" or not os.path.exists(os.path.join(work, "cohort.json")):
            continue
        cj = {g["appid"]: g for g in common.load_json(os.path.join(work, "cohort.json"))["games"]}
        for w in week:
            if w.get("status") != "keep":
                continue
            r = cj.get(int(w["appid"]))
            ap = os.path.join(work, "apps", f"{w['appid']}.json")
            if not r or r.get("is_free") or (_num(r.get("price")) or 0) <= 0 or not os.path.exists(ap):
                continue
            cache = common.load_json(ap)
            r = dict(r, store_observed_on=w.get("store_observed_on") or r.get("store_observed_on"),
                     grade_observed_on=w.get("grade_observed_on"), release_date=w["release_date"])
            x = prelaunch_features(r, cache.get("details"), cache.get("news"), None, _global_grade(w))
            if not x:
                continue
            if w["appid"] in out:
                duplicates.add(w["appid"])
                continue
            out[w["appid"]] = dict(appid=int(w["appid"]), name=w["name"], week=f[:-7], release_date=w["release_date"], x=x,
                            checked_d30=w.get("checked_d30"), checked_d90=w.get("checked_d90"),
                            y30=_observed_outcome(w, 30, today), y90=_observed_outcome(w, 90, today))
    return [r for appid, r in out.items() if appid not in duplicates]


def _sig(z: float) -> float:
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def fit_logit(X: list[list[float]], y: list[int], l2: float = 1.0, iters: int = 1500, lr: float = 0.2) -> dict:
    """Standardized logistic regression with L2, plain gradient descent. Returns {mean, std, w, b}."""
    n, k = len(X), len(X[0])
    mean = [sum(r[j] for r in X) / n for j in range(k)]
    std = [max(1e-9, math.sqrt(sum((r[j] - mean[j]) ** 2 for r in X) / n)) for j in range(k)]
    Z = [[(r[j] - mean[j]) / std[j] for j in range(k)] for r in X]
    w, b = [0.0] * k, math.log((sum(y) + 0.5) / (n - sum(y) + 0.5))
    for _ in range(iters):
        gw, gb = [0.0] * k, 0.0
        for zr, yy in zip(Z, y):
            e = _sig(b + sum(wj * zj for wj, zj in zip(w, zr))) - yy
            gb += e
            for j in range(k):
                gw[j] += e * zr[j]
        gradients = [(gw[j] + l2 * wj) / n for j, wj in enumerate(w)]
        if abs(gb / n) < 1e-6 and all(abs(v) < 1e-6 for v in gradients):
            break
        b -= lr * gb / n
        w = [wj - lr * gj for wj, gj in zip(w, gradients)]
    return dict(mean=mean, std=std, w=w, b=b)


def predict(m: dict, x: list[float]) -> float:
    """Inputs are clipped to +-3 standard deviations of the training data: no wild extrapolation outside what was seen."""
    return _sig(m["b"] + sum(wj * max(-3.0, min(3.0, (xj - mu) / sd)) for wj, xj, mu, sd in zip(m["w"], x, m["mean"], m["std"])))


def auc(p: list[float], y: list[int]) -> float | None:
    pos = [a for a, t in zip(p, y) if t]
    neg = [a for a, t in zip(p, y) if not t]
    if not pos or not neg:
        return None
    import bisect
    neg.sort()
    wins = sum((bisect.bisect_left(neg, a) + bisect.bisect_right(neg, a)) / 2 for a in pos)
    return round(wins / (len(pos) * len(neg)), 3)


def brier(p: list[float], y: list[int]) -> float:
    return sum((a - t) ** 2 for a, t in zip(p, y)) / len(y)


def band_of(reviews: float) -> int:
    c = reviews * METRO_MULT
    return next(i for i, (_, lo, hi) in enumerate(METRO_BANDS) if lo <= c < hi)


THRESH = {"p100": 100, "p1k": 1000, "p10k": 10000}


def bands_from(ps: dict) -> list[float]:
    p100, p1k, p10k = ps["p100"], min(ps["p1k"], ps["p100"]), min(ps["p10k"], ps["p1k"], ps["p100"])
    return [round(1 - p100, 3), round(p100 - p1k, 3), round(p1k - p10k, 3), round(p10k, 3)]


def fit_metro(rows: list[dict], key: str) -> dict:
    keys = [k for k, _, _ in METRO_FEATS if all(r["x"].get(k) is not None for r in rows)
            and len({r["x"][k] for r in rows}) > 1]
    X = [[r["x"][k] for k in keys] for r in rows]
    models = {}
    for name, thr in THRESH.items():
        y = [int(r[key] * METRO_MULT >= thr) for r in rows]
        models[name] = fit_logit(X, y) if keys and 0 < sum(y) < len(y) else dict(const=sum(y) / len(y))
    return dict(keys=keys, models=models, n=len(rows), target=key,
                ranges={k: [min(r["x"][k] for r in rows), max(r["x"][k] for r in rows)] for k in keys})


def metro_predict(model: dict, x: dict) -> dict:
    """P(>=100), P(>=1k), P(>=10k), made monotonic (three separate models can cross slightly)."""
    v = [x[k] for k in model["keys"]]
    p = {n: (m["const"] if "const" in m else predict(m, v)) for n, m in model["models"].items()}
    p["p1k"] = min(p["p1k"], p["p100"])
    p["p10k"] = min(p["p10k"], p["p1k"])
    return p


def backtest(rows: list[dict], key: str) -> dict:
    """Expanding release-week folds; a training outcome must be mature AND recorded before cutoff."""
    days = int(key[1:])
    observed = "checked_d" + str(days)
    rows = [r for r in rows if r.get(key) is not None and _day(r.get("release_date")) and _day(r.get(observed))
            and _day(r["release_date"]) + datetime.timedelta(days=days) <= _day(r[observed])]
    weeks = sorted({r["week"] for r in rows})
    preds, baselines, recent_baselines, test, base_bands, folds = [], [], [], [], [], []
    for week in weeks:
        block = [r for r in rows if r["week"] == week]
        first = min(_day(r["release_date"]) for r in block)
        cutoff = first - datetime.timedelta(days=first.weekday())
        train = [r for r in rows if r["week"] != week and _day(r[observed]) < cutoff]
        if len(train) < 30:
            continue
        model = fit_metro(train, key)
        base = {k: sum(r[key] * METRO_MULT >= thr for r in train) / len(train) for k, thr in THRESH.items()}
        recent_weeks = sorted({r["week"] for r in train})[-4:]
        recent = [r for r in train if r["week"] in recent_weeks]
        recent_base = {k: sum(r[key] * METRO_MULT >= thr for r in recent) / len(recent) for k, thr in THRESH.items()}
        mode = statistics.mode([band_of(r[key]) for r in train])
        pp = [metro_predict(model, r["x"]) if all(k in r["x"] for k in model["keys"]) else base for r in block]
        y = [int(r[key] * METRO_MULT >= 1000) for r in block]
        folds.append(dict(test_week=week, cutoff=cutoff.isoformat(), train_weeks=sorted({r["week"] for r in train}),
                          n_train=len(train), n_test=len(block), last_check=max(r[observed] for r in train), features=model["keys"],
                          positive_factors=[e["feature"] for e in effects(model, train) if e["delta_pp"] > 0],
                          brier_p1k=brier([p["p1k"] for p in pp], y), brier_base_p1k=brier([base["p1k"]] * len(y), y)))
        preds.extend(pp)
        baselines.extend([base] * len(block))
        recent_baselines.extend([recent_base] * len(block))
        base_bands.extend([mode] * len(block))
        test.extend(block)
    res = dict(possible=False, validated=False, protocol=METRO_PROTOCOL, embargo_days=days, folds=folds,
               test_weeks=[f["test_week"] for f in folds], n_test=len(test), target=key, per_threshold={})
    if len(folds) < 2 or len(test) < 30:
        return dict(res, why="servono due settimane distinte di test (almeno 30 giochi in tutto); per ogni fold almeno 30 esiti maturi e già rilevati prima della settimana")
    res.update(possible=True, train_weeks=folds[-1]["train_weeks"], test_week=folds[-1]["test_week"], n_train=folds[-1]["n_train"])
    for name, thr in THRESH.items():
        y = [int(r[key] * METRO_MULT >= thr) for r in test]
        p = [q[name] for q in preds]
        bases = [q[name] for q in baselines]
        bs, bb = brier(p, y), brier(bases, y)
        br = brier([q[name] for q in recent_baselines], y)
        order = sorted(range(len(p)), key=lambda i: p[i])
        bins = [order[i * len(order) // 4:(i + 1) * len(order) // 4] for i in range(4)]
        res["per_threshold"][name] = dict(auc=auc(p, y), brier=round(bs, 4), brier_base=round(bb, 4), brier_recent_base=round(br, 4), skill=round(1 - bs / bb, 3) if bb else None,
                                          actual_rate=round(sum(y) / len(y), 3), actual_ci95=wilson(sum(y), len(y)), base_rate=round(statistics.mean(bases), 3),
                                          calibration=[dict(pred=round(sum(p[i] for i in b) / len(b), 3), actual=round(sum(y[i] for i in b) / len(b), 3), n=len(b)) for b in bins if b])
    actual_band = [band_of(r[key]) for r in test]
    pred_band = [max(range(4), key=lambda i: bands_from(q)[i]) for q in preds]
    hits = sum(a == b for a, b in zip(actual_band, pred_band))
    res["band_accuracy"] = round(hits / len(test), 3)
    res["band_accuracy_ci95"] = wilson(hits, len(test))
    res["band_accuracy_base"] = round(sum(a == b for a, b in zip(actual_band, base_bands)) / len(test), 3)
    res["per_band"] = []
    for i, (label, _, _) in enumerate(METRO_BANDS):
        n = actual_band.count(i)
        hits = sum(a == b == i for a, b in zip(actual_band, pred_band))
        res["per_band"].append(dict(band=label, n=n, hit=round(hits / n, 3) if n else None, ci95=wilson(hits, n) if n else None))
    a1k = res["per_threshold"]["p1k"]
    res["strength"] = ("utile" if (a1k["auc"] or 0) >= 0.75 and (a1k["skill"] or 0) >= 0.10 else
                       "debole" if (a1k["auc"] or 0) >= 0.62 and (a1k["skill"] or 0) > 0 else "non migliore del base rate")
    positives = sum(r[key] * METRO_MULT >= THRESH["p1k"] for r in test)
    res["validated"] = (min(positives, len(test) - positives) >= 5 and res["strength"] in ("utile", "debole") and a1k["brier"] < a1k["brier_recent_base"]
                        and sum(f["brier_p1k"] < f["brier_base_p1k"] for f in folds) > len(folds) / 2)
    if not res["validated"]:
        res["why"] = "vantaggio non stabile contro le due baseline o troppo pochi casi dei due esiti a 1.000 copie"
    return res


def effects(model: dict, rows: list[dict]) -> list[dict]:
    """Plain-words weight of every factor: the change of P(>= 1k copies) for a typical B game when the factor goes
    from 'no' to 'yes' (or from the 25th to the 75th percentile)."""
    bs = [r for r in rows if r["x"].get("tier_A") == 0 and r["x"].get("tier_C") == 0] or rows
    typical = {k: statistics.median(r["x"][k] for r in bs) for k in model["keys"]}
    out = []
    for k, label, kind in METRO_FEATS:
        if k not in typical:
            continue
        if kind == "bin":
            lo, hi = 0, 1
        else:
            vals = sorted(r["x"][k] for r in rows)
            lo, hi = quantile(vals, .25), quantile(vals, .75)
            if lo == hi:
                continue
        p0 = metro_predict(model, dict(typical, **{k: lo}))["p1k"]
        p1 = metro_predict(model, dict(typical, **{k: hi}))["p1k"]
        out.append(dict(feature=k, label=label, kind=kind, delta_pp=round(100 * (p1 - p0), 1)))
    return sorted(out, key=lambda e: -abs(e["delta_pp"]))


def build_metro(ds: str, today: datetime.date) -> dict:
    # free games are left out: reviews x 20..60 does not measure sales for them (many players review a game they did not buy)
    rows = metro_rows(ds, today)
    key = "y90" if sum(1 for r in rows if r["y90"] is not None) >= max(200, len(rows) * 0.8) else "y30"
    rows = [r for r in rows if r[key] is not None]
    if len(rows) < 60:
        return dict(available=False, protocol=METRO_PROTOCOL, n=len(rows), why="servono almeno 60 giochi a pagamento di settimane verificate con segnali documentati ed esito maturo")
    bt = backtest(rows, key)
    model = fit_metro(rows, key)
    if bt["validated"] and any(f["features"] != model["keys"] for f in bt["folds"]):
        bt.update(validated=False, why="i segnali del modello finale differiscono da quelli provati nelle settimane di test")
    bandrate = [round(sum(1 for r in rows if band_of(r[key]) == i) / len(rows), 3) for i in range(4)]
    return dict(available=True, protocol=METRO_PROTOCOL, validated=bt["validated"], fitted_on=today.isoformat(), n=len(rows), weeks=sorted({r["week"] for r in rows}), target=key, copies_per_review=METRO_MULT,
                bands=[b for b, _, _ in METRO_BANDS], base_rate_bands=bandrate, backtest=bt, model=model, effects=effects(model, rows) if bt["validated"] else [],
                not_used=["giochi gratis (Boxleiter non misura vendite per loro: esclusi)", "durata del trailer (Steam non la espone in appdetails)", "storico dello sviluppatore (nessun endpoint pubblico pulito)",
                          "copertura YouTube e Reddit prima dell'uscita (raccolta solo per una parte dei giochi: la ricetta dei vincenti la mostra a parte)",
                          "mese di uscita (servono uscite di più mesi)"])


def score_features(met: dict, x: dict) -> dict:
    if met.get("protocol") != METRO_PROTOCOL:
        raise ValueError("protocollo metro obsoleto: rigenerare con cohort_bench.py metro")
    if x.get("free") != 0:
        return dict(mode="not_applicable", why="Prezzo a pagamento non documentato: Boxleiter non applicabile.", levers=[])
    m = met["model"]
    if not met.get("validated") or not (met.get("backtest") or {}).get("validated") or any(k not in x for k in m["keys"]):
        b = met["base_rate_bands"]
        total = sum(b)
        return dict(mode="base_rate", why="Verifica temporale insufficiente o segnali richiesti mancanti; solo frequenze del campione.",
                    bands=b, band=met["bands"][b.index(max(b))], p100=round(sum(b[1:]) / total, 3), p1k=round(sum(b[2:]) / total, 3), p10k=round(b[3] / total, 3), levers=[])
    ps = metro_predict(m, x)
    out = dict(mode="model", p100=round(ps["p100"], 3), p1k=round(ps["p1k"], 3), p10k=round(ps["p10k"], 3), bands=bands_from(ps))
    out["band"] = met["bands"][max(range(4), key=lambda i: out["bands"][i])]
    lev = []
    for k, change, label in METRO_LEVERS:
        if k not in m["keys"] or x[k] >= change[k]:
            continue
        folds = met["backtest"].get("folds") or []
        supported = sum(k in f.get("positive_factors", []) for f in folds)
        if supported < 2 or supported <= len(folds) / 2:
            continue
        updates = {f: max(x[f], v) for f, v in change.items() if f in m["keys"]}
        if any(not (m["ranges"][f][0] <= v <= m["ranges"][f][1]) for f, v in updates.items()):
            continue
        q = metro_predict(m, dict(x, **updates))
        if q["p1k"] <= ps["p1k"]:
            continue
        lev.append(dict(feature=k, label=label, supported=True, positive_folds=supported, total_folds=len(folds), p1k_after=round(q["p1k"], 3), delta_p1k_pp=round(100 * (q["p1k"] - ps["p1k"]), 1),
                        delta_p10k_pp=round(100 * (q["p10k"] - ps["p10k"]), 1)))
    out["levers"] = sorted(lev, key=lambda e: -e["delta_p1k_pp"])
    return out


def features_from_json(fj: dict) -> dict:
    """launch/prelaunch.json -> features. Keys: tier (A/B/C), price, is_free, n_movies, n_screenshots, gif, about_len, n_languages,
    publisher, early_access, demo_before, next_fest_before, playtest_before, news_before, coming_soon_days, release_day_crowd, genres."""
    g = " ".join(fj.get("genres") or []).lower()
    tier = _global_grade(fj)
    result = dict(tier_A=int(tier == "A"), tier_C=int(tier == "C"), price_log=math.log1p(fj.get("price") or 0), free=int(bool(fj.get("is_free")) or fj.get("price") == 0),
                trailer=int((fj.get("n_movies") or 0) > 0), movies=min(fj.get("n_movies") or 0, 4), screens=min(fj.get("n_screenshots") or 0, 20) / 10,
                gif=int(bool(fj.get("gif"))), desc_log=math.log1p(fj.get("about_len") or 0) / 7, langs_log=math.log1p(fj.get("n_languages") or 0),
                publisher=int(bool(fj.get("publisher"))), early_access=int(bool(fj.get("early_access"))), demo_pre=int(bool(fj.get("demo_before"))),
                nextfest_pre=int(bool(fj.get("next_fest_before"))), playtest_pre=int(bool(fj.get("playtest_before"))), news_pre_log=math.log1p(fj.get("news_before") or 0),
                comingsoon_log=math.log1p(fj.get("coming_soon_days") or 0), crowd_log=math.log1p(fj.get("release_day_crowd") or 0),
                g_casual=int("casual" in g), g_action=int("action" in g), g_sim=int("simulation" in g), g_strategy=int("strategy" in g), g_rpg=int("rpg" in g), g_adventure=int("adventure" in g))
    source = dict(price_log="price", trailer="n_movies", movies="n_movies", screens="n_screenshots", desc_log="about_len",
                  langs_log="n_languages", demo_pre="demo_before", nextfest_pre="next_fest_before", playtest_pre="playtest_before",
                  news_pre_log="news_before", comingsoon_log="coming_soon_days", crowd_log="release_day_crowd")
    known = {k for k in result if fj.get("genres" if k.startswith("g_") else source.get(k, k)) is not None}
    known -= {"tier_A", "tier_C", "free"}
    if tier:
        known.update(("tier_A", "tier_C"))
    if fj.get("price") is not None or fj.get("is_free") is not None:
        known.add("free")
    return {k: v for k, v in result.items() if k in known}


def score_heading(name: str, scored_on: str | None = None, data_date: str | None = None) -> str:
    """'Buffet Panic! (oggi, 2026-10-13)' scored on 2026-10-18 -> 'Buffet Panic! · punteggio del 2026-10-18 (dati del gioco del 2026-10-13)'.
    The date written in the features file is when the pre-launch features were described, not when the metro scored them."""
    m = re.search(r"\s*\((?:oggi|today|al|del)?,?\s*(\d{4}-\d{2}-\d{2})\)\s*$", name or "")
    base = (name[:m.start()] if m else name or "il gioco").strip()
    data_date = data_date or (m.group(1) if m else None)
    out = base + (f" · punteggio del {scored_on}" if scored_on else "")
    if data_date and data_date != scored_on:
        out += f" (dati del gioco del {data_date})"
    return out


def metro_md(met: dict, sc: dict | None = None, name: str = "il gioco", scored_on: str | None = None, data_date: str | None = None) -> str:
    if not met.get("available"):
        return f"# Metro oggettivo\n\nNon ancora disponibile: {met.get('why')} (ora {met.get('n')}).\n"
    if met.get("protocol") != METRO_PROTOCOL:
        return "# Metro oggettivo\n\nModello storico non verificato con il protocollo attuale: rigenerare il metro.\n"
    bt = met["backtest"]
    L = [f"# Metro oggettivo (dati veri, {met['fitted_on']})", "",
         f"Protocollo {METRO_PROTOCOL}, {met['n']} giochi nuovi a pagamento, settimane {', '.join(w.replace('cohort_', '') for w in met['weeks'])}; esito a {met['target'][1:]} giorni; "
         f"copie = recensioni × {METRO_MULT} (metà geometrica di Boxleiter 20..60) **[STIMA]**. Usa solo ciò che si vede prima dell'uscita.", ""]
    if bt.get("possible"):
        a = bt["per_threshold"]
        L += [f"## Verifica onesta (walk-forward, embargo di {bt['embargo_days']} giorni, settimane di test: {', '.join(bt['test_weeks'])}, n = {bt['n_test']})", "",
              f"**Giudizio: {bt['strength']}.**", "", "| Soglia | AUC | Brier | Brier del solo base rate | miglioramento | quota reale | base rate |", "|---|---|---|---|---|---|---|"]
        for k, v in a.items():
            skill = f"{100*v['skill']:.0f} %" if v["skill"] is not None else "n.c."
            L.append(f"| {k} | {v['auc'] if v['auc'] is not None else 'n.c.'} | {v['brier']} | {v['brier_base']} | {skill} | {round(100 * v['actual_rate'])} % | {round(100 * v['base_rate'])} % |")
        L += ["", f"Fascia indovinata: {round(100 * bt['band_accuracy'])} % (solo base rate: {round(100 * bt['band_accuracy_base'])} %). AUC 0,5 = a caso, 1 = perfetto."]
    else:
        L += [f"**Verifica fuori dal tempo non ancora possibile**: {bt.get('why')}. Il metro va letto come indicativo, con fiducia bassa."]
    if not bt.get("validated"):
        L += ["", "**Solo base rate, nessuna leva:** " + bt.get("why", "verifica insufficiente") + "."]
    L += ["", "## Cosa pesa (in parole)", "", "Variazione associata della probabilità di superare 1.000 copie per il profilo mediano quando il fattore passa da no a sì (o dal quartile basso a quello alto):", "",
          "| Fattore | effetto |", "|---|---|"] + [f"| {e['label']} | {e['delta_pp'] + 0:+.1f} punti |" for e in met["effects"][:12]]
    L += ["", "Non usati (ancora): " + "; ".join(met["not_used"]) + "."]
    if sc and sc.get("mode") != "model":
        L += ["", f"## {score_heading(name, scored_on, data_date)}", "", sc["why"]]
        if sc.get("band"):
            L.append(f"Fascia più frequente nel campione: {sc['band']} (non è una previsione personalizzata).")
    elif sc:
        L += ["", f"## {score_heading(name, scored_on, data_date)}", "", f"Fascia più probabile: **{sc['band']}** copie a {met['target'][1:]} giorni **[STIMA]**. "
              f"P(≥100) {round(100 * sc['p100'])} %, P(≥1.000) {round(100 * sc['p1k'])} %, P(≥10.000) {round(100 * sc['p10k'])} %.", "",
              "| Se aggiungiamo… | P(≥1.000) dopo | variazione | P(≥10.000) variazione |", "|---|---|---|---|"]
        L += [f"| {lv['label']} | {round(100 * lv['p1k_after'])} % | {lv['delta_p1k_pp'] + 0:+.1f} punti | {lv['delta_p10k_pp'] + 0:+.1f} punti |" for lv in sc["levers"]]
        L += ["", "_Correlazioni dal mercato reale, non garanzie: i giochi che fanno queste cose sono spesso anche fatti meglio._"]
    return "\n".join(L) + "\n"


def cmd_dossier(a):
    import market_tracker
    a.threshold = market_tracker.em.THRESHOLD
    market_tracker.cmd_dossier(a)


def cmd_metro(a):
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    met = build_metro(dataset_dir(a), today)
    cp = a.calibration or common.user_dir("calibration.json")
    cal = common.load_json(cp) if os.path.exists(cp) else {}
    cal["metro"] = met
    write_json(cal, cp)
    print(metro_md(met))


def cmd_score(a):
    cp = a.calibration or common.user_dir("calibration.json")
    met = (common.load_json(cp) if os.path.exists(cp) else {}).get("metro") or {}
    if not met.get("available") or met.get("protocol") != METRO_PROTOCOL:
        raise SystemExit("metro non disponibile: lancia prima `cohort_bench.py metro` (servono update + news + voti)")
    today = _day(getattr(a, "today", None)) or datetime.date.today()
    if not _day(met.get("fitted_on")) or _day(met["fitted_on"]) > today:
        raise SystemExit("data di addestramento assente o futura rispetto al punteggio")
    if a.features:
        fj = common.load_json(a.features)
        as_of = fj.get("as_of") or fj.get("date") or today.isoformat()
        release = fj.get("release_date")
        if not _day(as_of) or _day(as_of) > today or release and (not _day(release) or _day(release) <= today):
            raise SystemExit("la previsione richiede segnali già osservati e una data di punteggio prima dell'uscita")
        x, name = features_from_json(fj), fj.get("name") or "il gioco"
    else:
        if today != datetime.date.today():
            raise SystemExit("impossibile retrodatare una pagina Steam live; usare --features")
        dj = common.safe_json(APPDETAILS.format(appid=a.appid, cc=a.cc), default={})
        det = ((dj.get(str(a.appid)) or {}).get("data")) if isinstance(dj, dict) else None
        if not det:
            raise SystemExit(f"appdetails non disponibile per {a.appid}")
        r = flatten(dict(appid=a.appid, name=det.get("name"), date=None), det, None, None, {}, datetime.date.today())
        now = datetime.date.today()
        if not (det.get("release_date") or {}).get("coming_soon"):
            raise SystemExit("gioco già uscito o data incerta: fornire --features con segnali pre-lancio documentati")
        r["store_observed_on"] = now.isoformat()
        # No future event in the evidence: today's page and news only, even for a distant release.
        r["release_date"] = (now + datetime.timedelta(days=1)).isoformat()
        x, name = prelaunch_features(r, det, news_items(a.appid, Throttle(1.0)), None, None), det.get("name")
    sc = score_features(met, x)
    res = dict(name=name, scored_on=today.isoformat(), features=x, metro=dict(protocol=METRO_PROTOCOL, validated=sc["mode"] == "model", fitted_on=met["fitted_on"], n=met["n"], target=met["target"],
               strength=(met.get("backtest") or {}).get("strength", "non verificato")), score=sc)
    if a.out:
        write_json(res, a.out)
    text = metro_md(met, sc, name, res["scored_on"], (fj.get("as_of") or fj.get("date")) if a.features else None)
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(text)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=os.path.join("launch", "_raw", "cohort"), help="output folder (default launch/_raw/cohort)")
    ap.add_argument("--cc", default="us")
    ap.add_argument("--today", help="YYYY-MM-DD, for reproducible runs (default: today)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    v = sp.add_parser("volume", help="games released per day over the last N days")
    v.add_argument("--days", type=int, default=14); v.add_argument("--include-today", action="store_true"); v.add_argument("--page", type=int, default=100)
    v.add_argument("--rate", type=float, default=1.5)
    f = sp.add_parser("fetch", help="cohort data for a date window (resumable)")
    f.add_argument("--from", dest="date_from", required=True); f.add_argument("--to", dest="date_to", required=True)
    f.add_argument("--steamspy", action="store_true", help="also SteamSpy owners (1 req/s, often a useless 0-20k bucket for new games)")
    f.add_argument("--no-histogram", dest="histogram", action="store_false",
                   help="skip the review histogram (then 1.0 launches of old Early Access games keep their old reviews)")
    f.add_argument("--limit", type=int, help="only the first N games of the window (tests, dry runs)")
    f.add_argument("--refresh-window", action="store_true", help="search the window again instead of using the cached list")
    f.add_argument("--page", type=int, default=100)
    f.add_argument("--rate", type=float, default=1.6, help="seconds between appdetails calls (Steam allows ~200 per 5 minutes)")
    f.add_argument("--rate-reviews", type=float, default=1.0)
    fl = sp.add_parser("filter", help="automatic junk rules, with reasons")
    fl.add_argument("--min-screenshots", type=int, default=5); fl.add_argument("--flip-titles", type=int, default=3, help="titles by the same developer in the window that mark an asset flip")
    fl.add_argument("--min-short-desc", type=int, default=40); fl.add_argument("--min-about", type=int, default=200)
    fl.add_argument("--shovel-tag", action="append", help="extra tag that marks shovelware (repeatable)")
    s = sp.add_parser("sheets", help="contact sheets of the survivors + grades.csv")
    s.add_argument("--per-sheet", type=int, default=30); s.add_argument("--cols", type=int, default=6)
    s.add_argument("--tile-w", type=int, default=320); s.add_argument("--tile-h", type=int, default=150)
    s.add_argument("--reference", help="your own header capsule, shown first on every sheet for calibration")
    s.add_argument("--include-junk", action="store_true"); s.add_argument("--rate", type=float, default=0.25)
    r = sp.add_parser("report", help="tiers x outcomes")
    r.add_argument("--price-min", type=float); r.add_argument("--price-max", type=float)
    r.add_argument("--genres", help="comma list matched on Steam genres and tags, e.g. casual,simulation,rogue-lite,physics,comedy,party")
    r.add_argument("--win-reviews", type=int, default=50, help="B-tier 'winner' threshold (default 50 reviews, ~1,000-3,000 copies)")
    r.add_argument("--lose-reviews", type=int, default=10)
    r.add_argument("--mine-grade", default="B", choices=GRADES); r.add_argument("--mine-price", type=float)
    r.add_argument("--md"); r.add_argument("-o", "--out")
    u = sp.add_parser("update", help="rolling dataset in ~/.game-launch-strategist/cohorts: new week + re-checks at 30/90/180 days")
    u.add_argument("--dataset", help="dataset folder (default ~/.game-launch-strategist/cohorts)")
    u.add_argument("--import-dir", help="seed the dataset from a folder made by fetch/filter/sheets (e.g. launch/_raw/cohort)")
    u.add_argument("--new-weeks", type=int, default=1, help="inspect the latest N full release weeks, retry missing/partial weeks (0 = no discovery)")
    u.add_argument("--reference", help="your header capsule for the new contact sheets")
    u.add_argument("--no-volume", dest="volume", action="store_false", help="do not refresh ~/.game-launch-strategist/volume.json (daily releases, 14 days)")
    u.add_argument("--max-requests", type=int, default=3000, help="shared budget for appreviews + histogram queries, discovery and milestone checks (excluding HTTP retries)")
    u.add_argument("--limit", type=int); u.add_argument("--rate", type=float, default=1.6); u.add_argument("--rate-reviews", type=float, default=1.0)
    nw = sp.add_parser("news", help="official Steam news of every game of a cohort folder (demo, Next Fest, playtest, Coming Soon length)")
    nw.add_argument("--rate", type=float, default=1.0)
    nw.add_argument("--max-requests", type=int, help="massimo di giochi da interrogare; codice 2 se ne restano")
    nw.add_argument("--paid-only", action="store_true", help="solo giochi a pagamento, non esclusi dal filtro")
    mt_ = sp.add_parser("metro", help="fit and backtest the objective pre-launch metric on the dataset -> calibration.json['metro']")
    mt_.add_argument("--dataset"); mt_.add_argument("--calibration")
    sc_ = sp.add_parser("score", help="score a game with the metro: --appid X (released or with a store page) or --features launch/prelaunch.json")
    sc_.add_argument("--appid", type=int); sc_.add_argument("--features"); sc_.add_argument("--tier", default="B", choices=GRADES)
    sc_.add_argument("--calibration"); sc_.add_argument("--md"); sc_.add_argument("-o", "--out")
    do = sp.add_parser("dossier", help="marketing dossier of any game X (same as market_tracker.py dossier)")
    do.add_argument("--appid", action="append", required=True); do.add_argument("--name"); do.add_argument("--out-dir", default=os.path.join("launch", "_raw", "dossier"))
    do.add_argument("--yt-quota", type=int, default=2000); do.add_argument("--no-reddit", action="store_true"); do.add_argument("--market-dir")
    cb = sp.add_parser("calibrate", help="base rates per tier / price / genre, B-tier factors, control capsules -> calibration.json")
    cb.add_argument("--dataset"); cb.add_argument("--market-dir", help="market_tracker data folder (default ~/.game-launch-strategist/market)")
    cb.add_argument("-o", "--out", help="default ~/.game-launch-strategist/calibration.json"); cb.add_argument("--md")
    ap.add_argument("--env-file", help="private .env with API keys (default ~/.game-launch-strategist/.env, or $GLS_ENV_FILE)")
    a = ap.parse_args(argv)
    common.load_env(a.env_file)
    if a.cmd == "volume":
        common.set_rate(a.rate)
    elif a.cmd == "fetch":
        common.set_rate(1.2)
    elif a.cmd in ("update", "calibrate", "metro", "score", "dossier"):
        common.set_rate(1.2)
    if a.cmd not in ("update", "calibrate", "metro", "score", "dossier"):
        os.makedirs(a.dir, exist_ok=True)
    dict(volume=cmd_volume, fetch=cmd_fetch, filter=cmd_filter, sheets=cmd_sheets, report=cmd_report, update=cmd_update, calibrate=cmd_calibrate,
         news=cmd_news, metro=cmd_metro, score=cmd_score, dossier=cmd_dossier)[a.cmd](a)


if __name__ == "__main__":
    main()
