#!/usr/bin/env python3
"""The whole market over time: the head (top sellers, most played, top of your tags), the new games taking off, and
the marketing behind each tracked game. Data lives in ~/.game-launch-strategist/market/ and feeds
`cohort_bench.py calibrate` (marketing patterns of B-tier winners vs losers).

Subcommands:
  discover   add games to the tracked set: --top-sellers N, --most-played N, --tag "Casual" --tag-top N, --breakouts
             (new releases of the last --days with the fastest review growth, read from the release-date search),
             --from-dataset TIER (B-tier games of the cohort dataset, for the marketing patterns)
  add        add app ids by hand (--role comp / competitor / own)
  snapshot   time series per game at +24h, +48h, +1 week, +1 month, +3 months after release (older games: one per week):
             reviews and % positive, current players, SteamSpy owners, price and discount. --players-only samples the
             current players of every tracked game (run it several times a day: the daily peak is the max sample)
  estimate   copies as ranges from several methods: Boxleiter (reviews x 20..60), SteamSpy owners range, peak players x 30..100
  social     what marketing happened and when, per game: Steam news and events (official ISteamNews), YouTube (Data API,
             YOUTUBE_API_KEY), Reddit (OAuth if REDDIT_CLIENT_ID/SECRET, else the public RSS search), Twitch (Helix if
             TWITCH_CLIENT_ID/SECRET, else skipped). Every result goes through entity_match.py: kept only above the threshold.
  manual     writes launch/ricerche-manuali.md: the SteamDB pages to open (followers, peak CCU, price history) and the exact
             TikTok / Instagram / X searches to do BY HAND; `--import file.csv` loads what you found (platform,url,date,views,likes,appid,note)
  timeline   per game: weekly reviews (public histogram), player samples, news, videos, posts; spikes and what came before them
  market     the shape of the market: how much of the reviews the top 1 % / 10 % of a cohort takes, the head (most played,
             top sellers) vs the long tail, breakouts over time

Data sources policy (do not "fix" this by scraping):
  - USE: official Steam store endpoints (search, appdetails, appreviews, appreviewhistogram), official Steam Web API
    (GetNumberOfCurrentPlayers, GetMostPlayedGames, GetNewsForApp; STEAM_WEB_API_KEY is passed when present), SteamSpy,
    YouTube Data API, Reddit (OAuth or public RSS), Twitch Helix, Gamalytic public API only with GAMALYTIC_API_KEY.
  - SteamDB: its terms do not allow automated scraping and it sits behind Cloudflare. NEVER scraped: `manual` writes the
    exact pages to check by hand.
  - TikTok, Instagram, X: no official access without login or paid API. NEVER scraped: manual searches + CSV import.
  - Followers and wishlists are not public: only proxies, always labelled as proxies.

Keys: loaded at run time from --env-file, $GLS_ENV_FILE or the private file ~/.game-launch-strategist/.env. Values are never
printed, logged or written to any output.

Adapted from GamesTracker (https://github.com/Kekko16004/GamesTracker, MIT, the owner's project): snapshot schedule,
Steam players and SteamSpy sources, growth and launch-health ideas, YouTube and Reddit RSS collectors, manual import.
The title-only social search was replaced by entity matching (entity_match.py).
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import math
import os
import re
import statistics
import urllib.parse
import xml.etree.ElementTree as ET

import common
from common import Throttle, log, user_dir, write_json
import entity_match as em

APPDETAILS = "https://store.steampowered.com/api/appdetails?appids={appid}&l=english&cc=us"
APPREVIEWS = "https://store.steampowered.com/appreviews/{appid}?json=1&num_per_page=0&language=all&purchase_type=all"
HISTOGRAM = "https://store.steampowered.com/appreviewhistogram/{appid}?l=english&review_score_preference=0"
PLAYERS = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}"
MOST_PLAYED = "https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/"
NEWS = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=100&maxlength=400"
STEAMSPY = "https://steamspy.com/api.php?request=appdetails&appid={appid}"
SEARCH = "https://store.steampowered.com/search/results/?{q}&category1=998&infinite=1&start={start}&count={count}&cc=us&l=english"
YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
REDDIT_RSS = "https://www.reddit.com/search.rss"
REDDIT_OAUTH = "https://oauth.reddit.com/search"
TWITCH_TOKEN = "https://id.twitch.tv/oauth2/token"
TWITCH_HELIX = "https://api.twitch.tv/helix"

SCHEDULE = [("h24", 1), ("h48", 2), ("w1", 7), ("m1", 30), ("m3", 90)]   # GamesTracker tracking schedule + 3 months
SNAP_FIELDS = ["ts", "appid", "label", "days_out", "reviews_total", "pct_positive", "players_now", "spy_owners", "price", "discount"]
EVENT_WORDS = {"demo": ["demo"], "next_fest": ["next fest", "nextfest", "steam next"], "launch": ["out now", "launch", "released", "release date", "available now"],
               "early_access": ["early access"], "update": ["update", "patch", "hotfix", "content"], "trailer": ["trailer"], "sale": ["sale", "discount", "% off"],
               "playtest": ["playtest"], "festival": ["festival", "showcase"]}
YT_COST_SEARCH, YT_COST_VIDEOS = 100, 1


def mdir(a=None, *parts) -> str:
    return os.path.join(getattr(a, "market_dir", None) or user_dir("market"), *parts)


def redact(url: str) -> str:
    return re.sub(r"(key|client_secret|access_token)=[^&]+", r"\1=***", url)


def api_json(url: str, *, headers: dict | None = None, throttle: Throttle | None = None, data: bytes | None = None, default=None):
    """GET/POST JSON that never leaks a key in the logs."""
    try:
        return json.loads(common.http_get(url, headers=headers, throttle=throttle, data=data).decode("utf-8", "ignore"))
    except Exception as e:  # noqa: BLE001
        log(f"WARN {redact(url)}: {e.__class__.__name__} {str(e)[:80]}")
        return {} if default is None else default


def with_steam_key(url: str) -> str:
    k = os.environ.get("STEAM_WEB_API_KEY", "").strip()
    return url + ("&" if "?" in url else "?") + "key=" + urllib.parse.quote(k) if k else url


# ---------------------------------------------------------------- tracked set
def load_tracked(a) -> dict:
    p = mdir(a, "tracked.json")
    return common.load_json(p) if os.path.exists(p) else {}


def save_tracked(a, t: dict):
    os.makedirs(mdir(a), exist_ok=True)
    with open(mdir(a, "tracked.json"), "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=1)


def track(t: dict, appid, name: str | None, role: str, today: str, release: str | None = None, extra: dict | None = None):
    k = str(appid)
    e = t.setdefault(k, dict(appid=int(appid), name=name, roles=[], first_seen=today, release_date=release))
    if role not in e["roles"]:
        e["roles"].append(role)
    e["name"] = e.get("name") or name
    e["release_date"] = e.get("release_date") or release
    if extra:
        e.update({kk: v for kk, v in extra.items() if v is not None})


def search_rows(q: str, start: int, count: int) -> list[dict]:
    from cohort_bench import parse_search_html
    d = api_json(SEARCH.format(q=q, start=start, count=count))
    return parse_search_html(d.get("results_html") or "") if isinstance(d, dict) else []


def review_count_from_tooltip(t: str) -> int | None:
    m = re.search(r"of the ([\d,]+) user reviews", t or "")
    return int(m.group(1).replace(",", "")) if m else None


def cmd_discover(a):
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    t = load_tracked(a)
    added = {}
    if a.top_sellers:
        for r in search_rows("filter=topsellers", 0, a.top_sellers)[:a.top_sellers]:
            track(t, r["appid"], r["name"], "top_seller", today.isoformat(), r.get("date")); added["top_seller"] = added.get("top_seller", 0) + 1
    if a.most_played:
        d = api_json(with_steam_key(MOST_PLAYED))
        for x in ((d.get("response") or {}).get("ranks") or [])[:a.most_played]:
            track(t, x["appid"], None, "most_played", today.isoformat(), extra=dict(peak_in_game=x.get("peak_in_game"))); added["most_played"] = added.get("most_played", 0) + 1
    if a.tag:
        tp = user_dir("tags.json")
        from cohort_bench import tag_names
        names = {v.lower(): k for k, v in tag_names().items()}
        for tag in a.tag:
            tid = names.get(tag.lower())
            if not tid:
                log(f"WARN unknown tag {tag}")
                continue
            for r in search_rows(f"filter=topsellers&tags={tid}", 0, a.tag_top)[:a.tag_top]:
                track(t, r["appid"], r["name"], f"tag_top:{tag}", today.isoformat(), r.get("date")); added["tag_top"] = added.get("tag_top", 0) + 1
    if a.breakouts:
        rows, off = [], 0
        oldest = (today - datetime.timedelta(days=a.days)).isoformat()
        while off < 5000:
            page = search_rows("sort_by=Released_DESC", off, 100)
            if not page:
                break
            rows += page
            if min((r["date"] for r in page if r.get("date")), default=today.isoformat()) < oldest:
                break
            off += 100
        cand = []
        for r in rows:
            n = review_count_from_tooltip(r.get("review_tooltip"))
            price = (r.get("price_final_cents") or 0) / 100 / max(0.01, 1 - (r.get("discount") or 0) / 100)
            if n and r.get("date") and r["date"] >= oldest and price <= a.max_price:
                days = max(1, (today - datetime.date.fromisoformat(r["date"])).days)
                cand.append((n / days, n, r))
        from cohort_bench import reviews_within
        for speed, n, r in sorted(cand, key=lambda x: -x[0])[:a.breakouts]:
            h = api_json(HISTOGRAM.format(appid=r["appid"]))
            hist = h.get("results") if isinstance(h, dict) and h.get("success") == 1 else None
            age = (today - datetime.date.fromisoformat(r["date"])).days
            curve = {f"d{d}": reviews_within(hist, r["date"], d, n) for d in (7, 30, 90) if age >= d} if hist else {}
            track(t, r["appid"], r["name"], "breakout", today.isoformat(), r["date"], dict(breakout_reviews_per_day=round(speed, 1), curve=curve, reviews_seen=n))
            added["breakout"] = added.get("breakout", 0) + 1
    if a.from_dataset:
        from cohort_bench import read_csv as rc
        ds = a.dataset or user_dir("cohorts")
        for f in sorted(os.listdir(ds)) if os.path.isdir(ds) else []:
            if f.startswith("cohort_") and f.endswith(".csv"):
                for r in rc(os.path.join(ds, f)):
                    if r.get("status") == "keep" and r.get("grade") in a.from_dataset.split(","):
                        track(t, r["appid"], r["name"], f"cohort_{r['grade']}", today.isoformat(), r.get("release_date"),
                              dict(developers=[x for x in (r.get("developers") or "").split("; ") if x], publishers=[x for x in (r.get("publishers") or "").split("; ") if x],
                                   words=[x for x in (r.get("tags") or "").split("; ") if x][:6]))
                        added["cohort"] = added.get("cohort", 0) + 1
    save_tracked(a, t)
    print(f"giochi seguiti: {len(t)} (aggiunti o aggiornati: {added or 'nessuno'}) in {mdir(a, 'tracked.json')}")


def cmd_add(a):
    today = (datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()).isoformat()
    t = load_tracked(a)
    for x in a.appids:
        track(t, int(x), None, a.role, today)
    save_tracked(a, t)
    print(f"giochi seguiti: {len(t)}")


# ---------------------------------------------------------------- snapshots
def append_rows(path: str, fields: list[str], rows: list[dict]):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def players_now(appid, th: Throttle) -> int | None:
    d = api_json(with_steam_key(PLAYERS.format(appid=appid)), throttle=th)
    r = d.get("response") if isinstance(d, dict) else None
    return int(r["player_count"]) if isinstance(r, dict) and r.get("result") == 1 and r.get("player_count") is not None else None


def due_labels(e: dict, now: datetime.datetime, done: set[str]) -> list[str]:
    rel = e.get("release_date")
    if rel:
        rd = datetime.date.fromisoformat(rel)
        age = (now.date() - rd).days
        if age <= 120:
            # the latest milestone reached and not yet captured (a missed one is not faked later)
            reached = [lab for lab, d in SCHEDULE if age >= d]
            return [reached[-1]] if reached and reached[-1] not in done else []
    week = f"wk{now.date().isocalendar()[0]}-{now.date().isocalendar()[1]:02d}"
    return [] if week in done else [week]


def fetch_meta(e: dict, th: dict) -> dict | None:
    """Store data of a tracked game; fills name, release date, developers, languages and genre words once."""
    appid = e["appid"]
    det = api_json(APPDETAILS.format(appid=appid), throttle=th["details"])
    data = (det.get(str(appid)) or {}).get("data") if isinstance(det, dict) else None
    if data and not e.get("name"):
        e["name"] = data.get("name")
    if data and not e.get("release_date"):
        from cohort_bench import parse_date
        d = parse_date((data.get("release_date") or {}).get("date"))
        e["release_date"] = d.isoformat() if d else None
    if data:
        e.setdefault("developers", data.get("developers") or [])
        e.setdefault("publishers", data.get("publishers") or [])
        e.setdefault("languages", [re.sub(r"<[^>]+>|\*", "", x).strip() for x in re.sub(r"<br>.*$", "", data.get("supported_languages") or "").split(",") if x.strip()])
        e.setdefault("words", [g.get("description") for g in data.get("genres") or []][:5])
    return data


def snapshot_one(e: dict, label: str, now: datetime.datetime, th: dict, data: dict | None = None) -> dict:
    appid = e["appid"]
    rv = api_json(APPREVIEWS.format(appid=appid), throttle=th["store"])
    qs = rv.get("query_summary") if isinstance(rv, dict) and rv.get("success") == 1 else {}
    data = data if data is not None else fetch_meta(e, th)
    po = (data or {}).get("price_overview") or {}
    spy = api_json(STEAMSPY.format(appid=appid), throttle=th["spy"]) if th.get("spy") else {}
    tot = qs.get("total_reviews")
    rel = e.get("release_date")
    return dict(ts=now.isoformat(timespec="minutes"), appid=appid, label=label,
                days_out=(now.date() - datetime.date.fromisoformat(rel)).days if rel else "",
                reviews_total=tot if tot is not None else "", pct_positive=round(100 * qs.get("total_positive", 0) / tot, 1) if tot else "",
                players_now=players_now(appid, th["api"]), spy_owners=(spy or {}).get("owners", ""),
                price=(0.0 if (data or {}).get("is_free") else (po.get("initial", 0) / 100 if po else "")), discount=po.get("discount_percent", "") if po else "")


def cmd_snapshot(a):
    now = datetime.datetime.fromisoformat(a.now) if a.now else datetime.datetime.now()
    t = load_tracked(a)
    th = dict(store=Throttle(a.rate), details=Throttle(1.6), api=Throttle(1.0), spy=Throttle(1.1) if a.steamspy else None)
    if a.players_only:
        rows = [dict(ts=now.isoformat(timespec="minutes"), appid=e["appid"], players=players_now(e["appid"], th["api"])) for e in t.values()]
        append_rows(mdir(a, "players.csv"), ["ts", "appid", "players"], rows)
        print(f"{len(rows)} conteggi di giocatori registrati in {mdir(a, 'players.csv')}")
        return
    prev = read_rows(mdir(a, "snapshots.csv"))
    done: dict[str, set] = {}
    for r in prev:
        done.setdefault(r["appid"], set()).add(r["label"])
    out = []
    for e in list(t.values())[: a.limit or None]:
        data = None
        if not e.get("release_date"):
            data = fetch_meta(e, th)     # the schedule depends on the release date
        for lab in due_labels(e, now, done.get(str(e["appid"]), set())):
            out.append(snapshot_one(e, lab, now, th, data))
    append_rows(mdir(a, "snapshots.csv"), SNAP_FIELDS, out)
    save_tracked(a, t)
    print(f"{len(out)} snapshot nuovi in {mdir(a, 'snapshots.csv')} ({len(t)} giochi seguiti)")


# ---------------------------------------------------------------- estimates
def spy_range(s: str) -> tuple[int, int] | None:
    m = re.match(r"\s*([\d,]+)\s*\.\.\s*([\d,]+)", s or "")
    return (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) if m else None


def daily_peaks(rows: list[dict]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        if r.get("players") in (None, "", "None"):
            continue
        d = out.setdefault(str(r["appid"]), {})
        day = r["ts"][:10]
        d[day] = max(d.get(day, 0), int(float(r["players"])))
    return out


def estimates(snaps: list[dict], players: list[dict]) -> list[dict]:
    last: dict[str, dict] = {}
    for r in snaps:
        last[str(r["appid"])] = r
    peaks = daily_peaks(players)
    for r in snaps:
        if r.get("players_now") not in (None, "", "None"):
            d = peaks.setdefault(str(r["appid"]), {})
            d[r["ts"][:10]] = max(d.get(r["ts"][:10], 0), int(float(r["players_now"])))
    out = []
    for k, r in last.items():
        rv = int(float(r["reviews_total"])) if r.get("reviews_total") not in ("", None) else None
        sp = spy_range(r.get("spy_owners"))
        pk = max(peaks.get(k, {}).values(), default=None)
        methods = {}
        if rv is not None:
            methods["boxleiter"] = (rv * 20, rv * 60)
        if sp and sp[0] > 0:            # the "0 .. 20,000" bucket of every new game says nothing: left out
            methods["steamspy"] = sp
        if pk:
            methods["peak_players"] = (pk * 30, pk * 100)
        lows, highs = [v[0] for v in methods.values()], [v[1] for v in methods.values()]
        out.append(dict(appid=int(k), reviews=rv, peak_players=pk, methods=methods,
                        combined=(round(statistics.median(lows)), round(statistics.median(highs))) if methods else None))
    return out


def cmd_estimate(a):
    est = estimates(read_rows(mdir(a, "snapshots.csv")), read_rows(mdir(a, "players.csv")))
    t = load_tracked(a)
    L = ["# Copie stimate con più metodi **[STIMA]**", "", "Boxleiter = recensioni × 20..60; SteamSpy = fascia di proprietari; picco giocatori × 30..100 (euristica, "
         "il rapporto vero cambia molto tra generi). Nessun metodo è un dato di vendita.", "",
         "| Gioco | Recensioni | Picco giocatori visto | Boxleiter | SteamSpy | Da picco | Intervallo combinato (mediane) |", "|---|---|---|---|---|---|---|"]
    fmt = lambda v: f"{v[0]:,}-{v[1]:,}" if v else "–"  # noqa: E731
    for e in sorted(est, key=lambda x: -(x["reviews"] or 0)):
        m = e["methods"]
        L.append(f"| {(t.get(str(e['appid'])) or {}).get('name') or e['appid']} | {e['reviews'] if e['reviews'] is not None else '–'} | {e['peak_players'] or '–'} | "
                 f"{fmt(m.get('boxleiter'))} | {fmt(m.get('steamspy'))} | {fmt(m.get('peak_players'))} | {fmt(e['combined'])} |")
    text = "\n".join(L) + "\n"
    write_json(est, mdir(a, "estimates.json"))
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(text)


# ---------------------------------------------------------------- social
def game_entity(e: dict) -> dict:
    rel = e.get("release_date")
    ann = e.get("announced") or ((datetime.date.fromisoformat(rel) - datetime.timedelta(days=730)).isoformat() if rel else None)
    return dict(title=e.get("name") or "", appid=e["appid"], developers=e.get("developers") or [], publishers=e.get("publishers") or [],
                handles=e.get("handles") or [], official_channels=e.get("official_channels") or [], words=e.get("words") or [],
                languages=e.get("languages") or ["English"], announced=ann)


class YouTube:
    def __init__(self, quota: int):
        self.key = os.environ.get("YOUTUBE_API_KEY", "").strip()
        self.left = quota
        self.th = Throttle(0.3)

    def ok(self) -> bool:
        return bool(self.key)

    def search(self, q: str, after: str | None = None, n: int = 10) -> list[dict]:
        if not self.key or self.left < YT_COST_SEARCH:
            return []
        p = dict(part="snippet", type="video", q=q, maxResults=n, key=self.key)
        if after:
            p["publishedAfter"] = after + "T00:00:00Z"
        self.left -= YT_COST_SEARCH
        d = api_json(YT_SEARCH + "?" + urllib.parse.urlencode(p), throttle=self.th)
        out = []
        for it in d.get("items") or []:
            sn = it.get("snippet") or {}
            vid = (it.get("id") or {}).get("videoId")
            if vid:
                out.append(dict(platform="youtube", id=vid, url=f"https://www.youtube.com/watch?v={vid}", title=sn.get("title"), text=sn.get("description"),
                                author=sn.get("channelTitle"), author_id=sn.get("channelId"), published=(sn.get("publishedAt") or "")[:10]))
        return out

    def views(self, items: list[dict]):
        ids = [x["id"] for x in items if x.get("platform") == "youtube"]
        for i in range(0, len(ids), 50):
            if self.left < YT_COST_VIDEOS:
                return
            self.left -= YT_COST_VIDEOS
            d = api_json(YT_VIDEOS + "?" + urllib.parse.urlencode(dict(part="statistics", id=",".join(ids[i:i + 50]), key=self.key)), throttle=self.th)
            stats = {x["id"]: x.get("statistics") or {} for x in d.get("items") or []}
            for x in items:
                if x.get("id") in stats:
                    x["views"] = int(stats[x["id"]].get("viewCount", 0) or 0)


def reddit_search(title: str, th: Throttle) -> list[dict]:
    ua = os.environ.get("REDDIT_USER_AGENT", "").strip() or "game-launch-strategist/1.0 (research script)"
    cid, sec = os.environ.get("REDDIT_CLIENT_ID", "").strip(), os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    q = f'"{title}"'
    if cid and sec:
        import base64
        tok = api_json("https://www.reddit.com/api/v1/access_token", data=b"grant_type=client_credentials", throttle=th,
                       headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{sec}".encode()).decode(), "User-Agent": ua})
        if tok.get("access_token"):
            d = api_json(REDDIT_OAUTH + "?" + urllib.parse.urlencode(dict(q=q, sort="new", limit=50, type="link")), throttle=th,
                         headers={"Authorization": "Bearer " + tok["access_token"], "User-Agent": ua})
            out = []
            for c in ((d.get("data") or {}).get("children") or []):
                x = c.get("data") or {}
                out.append(dict(platform="reddit", id=x.get("id"), url="https://www.reddit.com" + (x.get("permalink") or ""), title=x.get("title"),
                                text=(x.get("selftext") or "")[:600] + " " + (x.get("url") or ""), author=x.get("author"), subreddit=x.get("subreddit"),
                                score=x.get("score"), comments=x.get("num_comments"),
                                published=datetime.datetime.fromtimestamp(x.get("created_utc", 0), datetime.timezone.utc).date().isoformat()))
            return out
    try:
        raw = common.http_get(REDDIT_RSS + "?" + urllib.parse.urlencode(dict(q=q, sort="new", limit=50)), headers={"User-Agent": ua, "Accept": "application/atom+xml"}, throttle=th)
    except Exception as e:  # noqa: BLE001
        log(f"WARN reddit rss: {e.__class__.__name__} {getattr(e, 'code', '')} (anonymous RSS is often blocked: add REDDIT_CLIENT_ID/SECRET for OAuth)")
        return None
    return parse_reddit_atom(raw.decode("utf-8", "ignore"))


def parse_reddit_atom(xml: str) -> list[dict]:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for en in root.findall("a:entry", ns):
        link = en.find("a:link", ns)
        cat = en.find("a:category", ns)
        content = re.sub(r"<[^>]+>", " ", (en.findtext("a:content", default="", namespaces=ns) or ""))
        out.append(dict(platform="reddit", id=en.findtext("a:id", default="", namespaces=ns), url=link.get("href") if link is not None else "",
                        title=en.findtext("a:title", default="", namespaces=ns), text=content[:800],
                        author=(en.findtext("a:author/a:name", default="", namespaces=ns) or "").replace("/u/", ""),
                        subreddit=cat.get("term") if cat is not None else "", published=(en.findtext("a:updated", default="", namespaces=ns) or "")[:10]))
    return out


def twitch_streams(title: str, th: Throttle) -> list[dict] | None:
    cid, sec = os.environ.get("TWITCH_CLIENT_ID", "").strip(), os.environ.get("TWITCH_CLIENT_SECRET", "").strip()
    if not (cid and sec):
        return None
    tok = api_json(TWITCH_TOKEN, data=urllib.parse.urlencode(dict(client_id=cid, client_secret=sec, grant_type="client_credentials")).encode(), throttle=th)
    if not tok.get("access_token"):
        return None
    h = {"Client-Id": cid, "Authorization": "Bearer " + tok["access_token"]}
    g = api_json(TWITCH_HELIX + "/games?" + urllib.parse.urlencode(dict(name=title)), headers=h, throttle=th)
    gid = ((g.get("data") or [{}])[0]).get("id")
    if not gid:
        return []
    v = api_json(TWITCH_HELIX + "/videos?" + urllib.parse.urlencode(dict(game_id=gid, first=50, sort="views")), headers=h, throttle=th)
    return [dict(platform="twitch", id=x.get("id"), url=x.get("url"), title=x.get("title"), author=x.get("user_name"), views=x.get("view_count"),
                 published=(x.get("created_at") or "")[:10], matched_by="twitch game id") for x in v.get("data") or []]


def steam_news(appid, th: Throttle) -> list[dict]:
    d = api_json(with_steam_key(NEWS.format(appid=appid)), throttle=th)
    out = []
    for n in ((d.get("appnews") or {}).get("newsitems") or []):
        title = n.get("title") or ""
        low = (title + " " + (n.get("contents") or "")[:200]).lower()
        kinds = [k for k, ws in EVENT_WORDS.items() if any(w in low for w in ws)]
        official = n.get("feedname") == "steam_community_announcements"
        out.append(dict(platform="steam_news", id=n.get("gid"), url=n.get("url"), title=title, author=n.get("author"), official=official,
                        feed=n.get("feedlabel"), kinds=kinds, published=datetime.datetime.fromtimestamp(n.get("date", 0), datetime.timezone.utc).date().isoformat()))
    return out


def cmd_social(a):
    t = load_tracked(a)
    yt = YouTube(a.yt_quota)
    th_r, th_s, th_t = Throttle(2.5), Throttle(1.0), Throttle(0.5)
    if not yt.ok():
        log("YOUTUBE_API_KEY assente: YouTube saltato (aggiungilo al file privato delle chiavi)")
    if not (os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET")):
        log("Reddit: niente OAuth (REDDIT_CLIENT_ID/SECRET), uso la ricerca RSS pubblica (più lenta, meno campi)")
    if not (os.environ.get("TWITCH_CLIENT_ID") and os.environ.get("TWITCH_CLIENT_SECRET")):
        log("Twitch: niente chiavi Helix (TWITCH_CLIENT_ID/SECRET), saltato")
    ids = [str(x) for x in a.appid] if a.appid else [k for k, e in t.items() if not a.role or any(r.startswith(a.role) for r in e["roles"])]
    os.makedirs(mdir(a, "social"), exist_ok=True)
    done = 0
    for k in ids[: a.limit or None]:
        e = t.get(k) or dict(appid=int(k), name=None, roles=[])
        out_p = mdir(a, "social", f"{k}.json")
        if os.path.exists(out_p) and not a.refresh:
            if not (a.fill_youtube and yt.ok() and not (common.load_json(out_p).get("sources") or {}).get("youtube")):
                continue
        if not e.get("name") or not e.get("developers"):
            fetch_meta(e, dict(store=th_s, details=Throttle(1.6), api=th_s))
            t[k] = e
        g = game_entity(e)
        cands = steam_news(e["appid"], th_s)
        for n in cands:
            n["score"], n["why"], n["kept"] = 100, ["official Steam news feed of the app"], True
        found = []
        yt_done = False
        if yt.ok():
            if yt.left < YT_COST_SEARCH:
                log("YouTube: quota del giorno finita, riprendo al prossimo giro")
            else:
                found += yt.search(f'"{g["title"]}"', after=g["announced"], n=25)
                yt_done = True
        rd = None if a.no_reddit else reddit_search(g["title"], th_r)
        found += rd or []
        tw = twitch_streams(g["title"], th_t)
        for plat in {c["platform"] for c in found}:
            em.score_batch([c for c in found if c["platform"] == plat], g, a.threshold)
        kept = [c for c in found if c["kept"]]
        if yt.ok():
            yt.views(kept)
        res = dict(appid=e["appid"], name=g["title"], collected_on=datetime.date.today().isoformat(), threshold=a.threshold,
                   sources=dict(steam_news=True, youtube=yt_done, reddit=(("oauth" if os.environ.get("REDDIT_CLIENT_ID") else "rss") if rd is not None else False), twitch=tw is not None),
                   news=cands, kept=kept + (tw or []), rejected=[dict(platform=c["platform"], title=c.get("title"), score=c["score"], why=c["why"]) for c in found if not c["kept"]])
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        done += 1
    save_tracked(a, t)
    print(f"social: {done} giochi raccolti in {mdir(a, 'social')}; quota YouTube rimasta in questo giro: {yt.left}")


# ---------------------------------------------------------------- manual checks (SteamDB, TikTok, Instagram, X)
MANUAL_START, MANUAL_END = "<!-- market_tracker:manual:start -->", "<!-- market_tracker:manual:end -->"


def manual_md(t: dict, today: str) -> str:
    L = [MANUAL_START, f"## Controlli a mano generati da `market_tracker.py manual` ({today})", "",
         "Queste fonti **non si leggono con gli script**: SteamDB vieta lo scraping automatico (ed è dietro Cloudflare), TikTok, Instagram e X "
         "non hanno un accesso ufficiale senza login. Si aprono a mano; quello che trovi va in un CSV e si importa con "
         "`market_tracker.py manual --import file.csv` (colonne: platform,url,date,views,likes,appid,note).", ""]
    for e in sorted(t.values(), key=lambda x: (x.get("name") or "")):
        n, k = e.get("name") or str(e["appid"]), e["appid"]
        tag = re.sub(r"[^A-Za-z0-9]", "", n)
        devs = ", ".join(e.get("developers") or []) or "sviluppatore da verificare"
        L += [f"### {n} (appid {k})", "",
              f"- SteamDB, follower e posizione tra i più desiderati: https://steamdb.info/app/{k}/charts/ (sezione Followers)",
              f"- SteamDB, picco di giocatori: https://steamdb.info/app/{k}/charts/",
              f"- SteamDB, storia dei prezzi: https://steamdb.info/app/{k}/ (scheda Price History)",
              f"- TikTok: cerca `\"{n}\"` e `#{tag}`; scarta i video che non mostrano il gioco o lo studio ({devs})",
              f"- Instagram: cerca `#{tag}` e l'account dello studio ({devs})",
              f"- X: cerca `\"{n}\" (steam OR game OR demo)` e l'account dello studio", ""]
    L.append(MANUAL_END)
    return "\n".join(L) + "\n"


def cmd_manual(a):
    t = load_tracked(a)
    today = datetime.date.today().isoformat()
    if a.import_csv:
        with open(a.import_csv, encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("url")]
        allowed = {"tiktok", "instagram", "x", "twitter", "youtube", "reddit", "twitch", "discord", "other"}
        bad = [r["url"] for r in rows if (r.get("platform") or "").lower() not in allowed]
        rows = [r for r in rows if (r.get("platform") or "").lower() in allowed]
        p = mdir(a, "manual_posts.csv")
        have = {r["url"] for r in read_rows(p)}
        new = [dict(r, imported_on=today) for r in rows if r["url"] not in have]
        append_rows(p, ["platform", "url", "date", "views", "likes", "appid", "note", "imported_on"], new)
        print(f"importati {len(new)} post a mano ({len(rows) - len(new)} già presenti" + (f", {len(bad)} con piattaforma sconosciuta scartati" if bad else "") + ")")
        return
    out = a.out or os.path.join("launch", "ricerche-manuali.md")
    body = manual_md({k: v for k, v in t.items() if not a.role or any(r.startswith(a.role) for r in v["roles"])}, today)
    old = open(out, encoding="utf-8").read() if os.path.exists(out) else "# Ricerche manuali\n\n"
    if MANUAL_START in old and MANUAL_END in old:
        new = old.split(MANUAL_START)[0] + body + old.split(MANUAL_END, 1)[1].lstrip("\n")
    else:
        new = old.rstrip("\n") + "\n\n" + body
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print(f"scritto {out} (sezione generata, il resto del file non è toccato)")


# ---------------------------------------------------------------- timeline and patterns
def weekly_reviews(appid, th: Throttle) -> list[tuple[str, int]]:
    d = api_json(HISTOGRAM.format(appid=appid), throttle=th)
    r = d.get("results") if isinstance(d, dict) and d.get("success") == 1 else None
    if not r:
        return []
    return [(datetime.datetime.fromtimestamp(int(x["date"]), datetime.timezone.utc).date().isoformat(),
             x.get("recommendations_up", 0) + x.get("recommendations_down", 0)) for x in r.get("rollups") or []]


def spikes(series: list[tuple[str, int]], factor: float = 2.0, min_n: int = 10) -> list[str]:
    """Weeks with at least `factor` x the median of the previous 4 weeks (and at least min_n reviews)."""
    out = []
    for i, (d, n) in enumerate(series):
        prev = [x for _, x in series[max(0, i - 4):i]]
        base = statistics.median(prev) if prev else 0
        if n >= min_n and (not prev or n >= factor * max(base, 1)):
            out.append(d)
    return out


def load_social(a, appid) -> dict:
    p = mdir(a, "social", f"{appid}.json")
    return common.load_json(p) if os.path.exists(p) else {}


def events_of(soc: dict, manual: list[dict], appid) -> list[dict]:
    ev = [dict(date=n["published"], kind="+".join(n.get("kinds") or []) or "news", src="steam", title=n.get("title")) for n in soc.get("news") or [] if n.get("official")]
    ev += [dict(date=x["published"], kind=x["platform"], src=x.get("author"), title=x.get("title"), views=x.get("views")) for x in soc.get("kept") or [] if x.get("published")]
    ev += [dict(date=m.get("date"), kind=m.get("platform"), src="manuale", title=m.get("note"), views=m.get("views")) for m in manual if str(m.get("appid")) == str(appid) and m.get("date")]
    return sorted(ev, key=lambda x: x["date"])


def cmd_timeline(a):
    t = load_tracked(a)
    th = Throttle(1.0)
    manual = read_rows(mdir(a, "manual_posts.csv"))
    L = ["# Timeline marketing → risultati", "", "Recensioni per settimana dall'istogramma pubblico di Steam **[FATTO]**; eventi da Steam news, YouTube, Reddit "
         "(solo risultati che passano il controllo di pertinenza) e import manuali. Un evento prima di un picco **non prova** che lo abbia causato.", ""]
    for k in [str(x) for x in a.appid] if a.appid else list(t)[: a.limit or None]:
        e = t.get(k, {"name": k})
        series = weekly_reviews(k, th)
        ev = events_of(load_social(a, k), manual, k)
        sp = spikes(series)
        L += [f"## {e.get('name') or k} (appid {k})", ""]
        if not series:
            L += ["Nessuna recensione ancora.", ""]
            continue
        L += ["| Settimana | Recensioni | Picco | Eventi nei 10 giorni prima |", "|---|---|---|---|"]
        for d, n in series[-26:]:
            dd = datetime.date.fromisoformat(d)
            near = [x for x in ev if dd - datetime.timedelta(days=10) <= datetime.date.fromisoformat(x["date"]) <= dd + datetime.timedelta(days=6)]
            L.append(f"| {d} | {n} | {'▲' if d in sp else ''} | {'; '.join((x['kind'] + ': ' + (x.get('title') or '')[:50]) for x in near[:3])} |")
        L.append("")
    text = "\n".join(L) + "\n"
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(text[:4000])


def marketing_features(soc: dict, release: str | None) -> dict:
    """What happened before (and right after) launch, from one game's social file."""
    rel = datetime.date.fromisoformat(release) if release else None
    def before(x, days=None):
        if not rel or not x.get("published"):
            return False
        d = datetime.date.fromisoformat(x["published"][:10])
        return d < rel and (days is None or (rel - d).days <= days)
    src = soc.get("sources") or {}
    news = [n for n in soc.get("news") or [] if n.get("official")]
    vids = [x for x in soc.get("kept") or [] if x.get("platform") == "youtube"]
    posts = [x for x in soc.get("kept") or [] if x.get("platform") == "reddit"]
    yt_ok, rd_ok = src.get("youtube", True), bool(src.get("reddit", True))
    official = {x.get("author_id") for x in vids if "official channel" in " ".join(x.get("why") or [])}
    creator_v = [x for x in vids if x.get("author_id") not in official and not any("developer" in w for w in x.get("why") or [])]
    trailers = [x for x in vids if "trailer" in (x.get("title") or "").lower()]
    first_trailer = min((x["published"] for x in trailers if x.get("published")), default=None)
    after = [n for n in news if rel and n.get("published") and 0 <= (datetime.date.fromisoformat(n["published"]) - rel).days <= 90]
    first = lambda xs: min((x["published"][:10] for x in xs if x.get("published") and before(x)), default=None)  # noqa: E731
    days = lambda d: (rel - datetime.date.fromisoformat(d)).days if rel and d else None  # noqa: E731
    trailer_news = [n for n in news if "trailer" in n["kinds"]]
    return dict(news_before=sum(1 for n in news if before(n)), demo_before=int(any(before(n) and "demo" in n["kinds"] for n in news)),
                next_fest=int(any(before(n) and "next_fest" in n["kinds"] for n in news)), playtest_before=int(any(before(n) and "playtest" in n["kinds"] for n in news)),
                festival_before=int(any(before(n) and "festival" in n["kinds"] for n in news)),
                trailer_days_before=days(first(trailers + trailer_news)) if (yt_ok or trailer_news) else None,
                demo_days_before=days(first([n for n in news if "demo" in n["kinds"]])), playtest_days_before=days(first([n for n in news if "playtest" in n["kinds"]])),
                next_fest_days_before=days(first([n for n in news if "next_fest" in n["kinds"]])),
                creators_days_before=days(first(creator_v)) if yt_ok else None,
                videos_before=sum(1 for x in vids if before(x)) if yt_ok else None, creator_videos=len(creator_v) if yt_ok else None,
                creator_views=sum(x.get("views") or 0 for x in creator_v) if yt_ok else None, creators_before=int(any(before(x) for x in creator_v)) if yt_ok else None,
                reddit_posts_before=sum(1 for x in posts if before(x)) if rd_ok else None, reddit_posts=len(posts) if rd_ok else None,
                updates_90d=sum(1 for n in after if "update" in n["kinds"]), updates_after=int(any("update" in n["kinds"] for n in after)))


RECIPE = [("playtest", "Playtest su Steam", "playtest_before", "playtest_days_before"), ("trailer", "Trailer pubblicato", None, "trailer_days_before"),
          ("demo", "Demo gratuita", "demo_before", "demo_days_before"), ("festival", "Festival o vetrina", "festival_before", None),
          ("next_fest", "Steam Next Fest", "next_fest", "next_fest_days_before"), ("creators", "Video di creator prima dell'uscita", "creators_before", "creators_days_before"),
          ("updates", "Aggiornamenti nei primi 90 giorni", "updates_after", None)]


def recipe(groups: dict) -> list[dict]:
    """How often each step appears in B winners vs losers, and when (median days before release), in time order."""
    out = []
    for key, label, flag, when in RECIPE:
        row = dict(step=key, label=label)
        for g, xs in groups.items():
            if flag:
                v = [x[flag] for x in xs if x.get(flag) is not None]
            else:   # a timing field: present if known
                v = [1 if x.get(when) is not None else 0 for x in xs if not (key == "trailer" and x.get(when) is None and x.get("videos_before") is None)]
            row[g] = round(100 * sum(v) / len(v), 1) if v else None
            row["n_" + g] = len(v)
        d = [x[when] for x in groups.get("winners", []) if when and x.get(when) is not None]
        row["median_days_before"] = statistics.median(d) if d else (-45 if key == "updates" else None)
        out.append(row)
    return sorted(out, key=lambda r: -(r["median_days_before"] if r["median_days_before"] is not None else -999))


def marketing_patterns(market_dir: str, graded: dict, milestone: str | None) -> dict | None:
    """B-tier winners vs losers: what marketing came before launch. Used by cohort_bench.py calibrate."""
    sdir = os.path.join(market_dir, "social")
    if not milestone or not os.path.isdir(sdir):
        return None
    key = "reviews_" + milestone
    groups = {"winners": [], "losers": []}
    for f in os.listdir(sdir):
        if not f.endswith(".json"):
            continue
        r = graded.get(int(f[:-5]))
        if not r or r.get("grade") != "B" or r.get(key) in (None, ""):
            continue
        with open(os.path.join(sdir, f), encoding="utf-8") as fh:
            soc = json.load(fh)
        feats = marketing_features(soc, r.get("release_date"))
        n = float(r[key])
        if n >= 50:
            groups["winners"].append(feats)
        elif n < 10:
            groups["losers"].append(feats)
    if not groups["winners"] and not groups["losers"]:
        return None
    out = dict(milestone=milestone, n_win=len(groups["winners"]), n_lose=len(groups["losers"]),
               small_sample=min(len(groups["winners"]), len(groups["losers"])) < 8, table=[])
    out["recipe"] = recipe(groups)
    for k in ("news_before", "demo_before", "next_fest", "trailer_days_before", "videos_before", "creator_videos", "creator_views", "reddit_posts_before", "updates_90d"):
        row = dict(feature=k)
        for g, xs in groups.items():
            v = [x[k] for x in xs if x.get(k) is not None]
            row[g] = (round(100 * sum(v) / len(v), 1) if k in ("demo_before", "next_fest") else statistics.median(v)) if v else None
            row["n_" + g] = len(v)
        row["kind"] = "% sì" if k in ("demo_before", "next_fest") else "mediana"
        out["table"].append(row)
    return out


def cmd_market(a):
    from cohort_bench import read_csv as rc
    ds = a.dataset or user_dir("cohorts")
    rows = []
    for f in sorted(os.listdir(ds)) if os.path.isdir(ds) else []:
        if f.startswith("cohort_") and f.endswith(".csv"):
            rows += [r for r in rc(os.path.join(ds, f)) if r.get("status") == "keep"]
    vals = sorted((int(float(r.get("reviews_total_now") or 0)) for r in rows), reverse=True)
    tot = sum(vals) or 1
    share = lambda q: round(100 * sum(vals[:max(1, math.ceil(len(vals) * q))]) / tot, 1)  # noqa: E731
    t = load_tracked(a)
    head = [e for e in t.values() if "most_played" in e["roles"] or "top_seller" in e["roles"]]
    L = ["# Forma del mercato", "", f"Coorti del dataset: {len(rows)} giochi nuovi (junk e 1.0 di vecchi Early Access esclusi). **[FATTO]** sulle recensioni lette.", "",
         f"- Il **top 1 %** dei giochi nuovi prende il **{share(.01)} %** di tutte le recensioni della coorte; il top 10 % il **{share(.10)} %**; la metà bassa il "
         f"**{round(100 * sum(vals[len(vals) // 2:]) / tot, 1)} %**.",
         f"- Giochi con 0 recensioni: {sum(1 for v in vals if v == 0)} su {len(vals)}.",
         f"- La testa del mercato seguita (più giocati e più venduti): {len(head)} giochi; i nuovi che decollano (breakout): "
         f"{sum(1 for e in t.values() if 'breakout' in e['roles'])}.", "",
         "_La coda lunga è la regola: la mediana di un gioco nuovo è poche recensioni, e pochi titoli prendono quasi tutto._"]
    text = "\n".join(L) + "\n"
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    print(text)


# ---------------------------------------------------------------- marketing dossier of any game
URL_RX = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)
TIKTOK_OEMBED = "https://www.tiktok.com/oembed?url={url}"
PLATFORM_OF = [("tiktok", r"tiktok\.com"), ("instagram", r"instagram\.com"), ("x", r"(?:twitter|x)\.com"), ("youtube", r"youtube\.com|youtu\.be"),
               ("reddit", r"reddit\.com"), ("discord", r"discord\.(?:gg|com)"), ("twitch", r"twitch\.tv"), ("linktree", r"linktr\.ee"), ("bluesky", r"bsky\.app"),
               ("steam", r"steampowered\.com|steamcommunity\.com")]


def platform_of(url: str) -> str:
    for name, rx in PLATFORM_OF:
        if re.search(rx, url, re.I):
            return name
    return "web"


def links_in(text: str) -> list[str]:
    seen, out = set(), []
    for u in URL_RX.findall(html_unescape(text or "")):
        u = u.rstrip(".,;")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def html_unescape(s: str) -> str:
    import html as _h
    return _h.unescape(s)


def tiktok_date(url: str) -> str | None:
    """A TikTok video id carries its creation time in the top 32 bits (public, documented by many; no request needed)."""
    m = re.search(r"/video/(\d{15,})", url)
    if not m:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(m.group(1)) >> 32, datetime.timezone.utc).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def tiktok_oembed(url: str, th: Throttle) -> dict:
    """Official oEmbed (public, no login): title and author of a video URL found elsewhere. Views are not exposed."""
    d = api_json(TIKTOK_OEMBED.format(url=urllib.parse.quote(url, safe="")), throttle=th)
    return dict(platform="tiktok", url=url, title=d.get("title"), author=d.get("author_name"), published=tiktok_date(url), source="oEmbed") if d.get("title") is not None or d.get("author_name") else \
        dict(platform="tiktok", url=url, title=None, author=None, published=tiktok_date(url), source="link")


def dossier(a, appid: int, name: str | None = None) -> dict:
    """One dated timeline of everything public about a game's marketing, matched to the game."""
    t = load_tracked(a)
    e = t.get(str(appid)) or dict(appid=appid, name=name, roles=["dossier"], first_seen=datetime.date.today().isoformat())
    th = dict(store=Throttle(1.0), details=Throttle(1.6), api=Throttle(1.0))
    data = fetch_meta(e, th)
    if name and not e.get("name"):
        e["name"] = name
    g = game_entity(e)
    about = ((data or {}).get("about_the_game") or "") + " " + ((data or {}).get("detailed_description") or "")
    page_links = links_in(about) + ([data["website"]] if (data or {}).get("website") else [])
    # social (reuse the cached collection when present; collect when missing)
    soc = load_social(a, appid)
    if not soc:
        ns = argparse.Namespace(**vars(a)); ns.appid = [appid]; ns.role = None; ns.limit = None; ns.refresh = False; ns.threshold = getattr(a, "threshold", em.THRESHOLD)
        ns.no_reddit = getattr(a, "no_reddit", False); ns.fill_youtube = False; ns.yt_quota = getattr(a, "yt_quota", 2000)
        t[str(appid)] = e; save_tracked(a, t)
        cmd_social(ns)
        soc = load_social(a, appid)
    kept = soc.get("kept") or []
    official_ids = {x.get("author_id") for x in kept if x.get("platform") == "youtube" and (any("official" in w or "developer" in w for w in x.get("why") or [])
                                                                                          or em.fold(x.get("author")).strip() in {em.fold(d).strip() for d in g["developers"] + g["publishers"] + [g["title"]]})}
    for x in kept:
        if x.get("platform") == "youtube":
            x["official"] = x.get("author_id") in official_ids
            x["short"] = "#shorts" in ((x.get("title") or "") + " " + (x.get("text") or "")).lower()
    found_links = page_links + [u for x in kept for u in links_in((x.get("text") or "") + " " + (x.get("url") or ""))]
    th_o = Throttle(1.0)
    tiktok = [tiktok_oembed(u, th_o) for u in dict.fromkeys(u for u in found_links if platform_of(u) == "tiktok" and "/video/" in u)][:20]
    # the game's own accounts come only from its store page and website (links in creators' descriptions are THEIR accounts)
    accounts = sorted({u for u in page_links if platform_of(u) in ("tiktok", "instagram", "x", "youtube", "discord", "twitch", "bluesky", "linktree", "reddit")
                       and "/video/" not in u and "watch?v=" not in u})
    press = sorted({u for u in page_links if platform_of(u) == "web" and not re.search(r"steamstatic|akamaihd|steamcdn|\.(?:webm|avif|png|jpe?g|gif|mp4)(?:\?|$)", u, re.I)})
    manual = [m for m in read_rows(mdir(a, "manual_posts.csv")) if str(m.get("appid")) == str(appid)]
    series = weekly_reviews(appid, th["store"])
    snaps = [r for r in read_rows(mdir(a, "snapshots.csv")) if str(r["appid"]) == str(appid)]
    rel = e.get("release_date")
    ev = []
    for n in soc.get("news") or []:
        ev.append(dict(date=n["published"], platform="steam", kind="+".join(n.get("kinds") or []) or "news", title=n.get("title"), official=n.get("official"), url=n.get("url")))
    for x in kept:
        ev.append(dict(date=(x.get("published") or "")[:10], platform=x["platform"], kind=("short" if x.get("short") else "official" if x.get("official") else "creator" if x["platform"] == "youtube" else "post"),
                       title=x.get("title"), author=x.get("author"), views=x.get("views"), score=x.get("score"), url=x.get("url")))
    for x in tiktok:
        ev.append(dict(date=x.get("published") or "", platform="tiktok", kind="video", title=x.get("title"), author=x.get("author"), url=x["url"], views=None))
    for m in manual:
        ev.append(dict(date=m.get("date") or "", platform=(m.get("platform") or "").lower(), kind="manuale", title=m.get("note"), views=_int(m.get("views")), url=m.get("url")))
    ev = sorted([x for x in ev if x["date"]], key=lambda x: x["date"])
    sp = spikes(series)
    moved = []
    for d in sp:
        dd = datetime.date.fromisoformat(d)
        near = [x for x in ev if dd - datetime.timedelta(days=7) <= datetime.date.fromisoformat(x["date"]) <= dd + datetime.timedelta(days=3)]
        moved.append(dict(week=d, reviews=dict(series).get(d), events=near[:6]))
    before = [x for x in ev if rel and x["date"] < rel]
    after = [x for x in ev if rel and x["date"] >= rel]
    offs = sorted(x["date"] for x in ev if x["platform"] == "steam" and x.get("official"))
    gaps = [(datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a_)).days for a_, b in zip(offs, offs[1:])]
    pattern = dict(before={p: sum(1 for x in before if x["platform"] == p) for p in sorted({x["platform"] for x in before})},
                   after={p: sum(1 for x in after if x["platform"] == p) for p in sorted({x["platform"] for x in after})},
                   official_news_cadence_days=statistics.median(gaps) if gaps else None, first_event=ev[0]["date"] if ev else None,
                   lead_days=(datetime.date.fromisoformat(rel) - datetime.date.fromisoformat(ev[0]["date"])).days if ev and rel else None,
                   features=marketing_features(soc, rel))
    prices = [(r["ts"][:10], r.get("price"), r.get("discount")) for r in snaps]
    out = dict(appid=appid, name=g["title"], release_date=rel, built_on=datetime.date.today().isoformat(), developers=g["developers"], publishers=g["publishers"],
               sources=dict(soc.get("sources") or {}, tiktok="oEmbed dei link trovati (niente ricerca: non esiste un accesso pubblico)",
                            instagram="solo link trovati (oEmbed di Instagram richiede un token Meta; la Graph API Business Discovery richiede un tuo account Business: opzione futura)",
                            x="solo link trovati e import manuale (l'API di X è a pagamento)"),
               accounts=accounts, press=press, timeline=ev, weekly_reviews=series, spikes=moved, prices=prices, pattern=pattern,
               rejected_count=len(soc.get("rejected") or []), threshold=soc.get("threshold"))
    os.makedirs(mdir(a, "dossier"), exist_ok=True)
    with open(mdir(a, "dossier", f"{appid}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    t[str(appid)] = e
    save_tracked(a, t)
    return out


def _int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def dossier_md(d: dict) -> str:
    pat = d["pattern"]
    L = [f"# Dossier marketing: {d['name']} (appid {d['appid']})", "",
         f"Costruito il {d['built_on']} da fonti pubbliche e ufficiali; uscita {d.get('release_date') or 'n/d'}; sviluppatore {', '.join(d['developers']) or 'n/d'}"
         + (f", publisher {', '.join(d['publishers'])}" if d["publishers"] else "") + ". Video e post contano solo se passano il controllo di pertinenza "
         f"(soglia {d.get('threshold')}; scartati {d['rejected_count']}). **[FATTO]** su date e conteggi; nessun legame causa-effetto è dimostrato.", "",
         "## Fonti", ""] + [f"- **{k}**: {v}" for k, v in d["sources"].items()]
    if d["accounts"]:
        L += ["", "## Account e canali trovati", ""] + [f"- {platform_of(u)}: {u}" for u in d["accounts"][:15]]
    if d["press"]:
        L += ["", "## Link dalla pagina Steam (stampa, sito)", ""] + [f"- {u}" for u in d["press"][:15]]
    L += ["", "## Il percorso", "", f"Primo segnale pubblico: {pat['first_event'] or 'n/d'}" + (f" ({pat['lead_days']} giorni prima dell'uscita)" if pat.get("lead_days") is not None else "")
          + (f"; notizie ufficiali su Steam in media ogni {pat['official_news_cadence_days']:.0f} giorni" if pat.get("official_news_cadence_days") else "") + ".", "",
          "| Piattaforma | prima dell'uscita | dopo |", "|---|---|---|"]
    for p_ in sorted(set(pat["before"]) | set(pat["after"])):
        L.append(f"| {p_} | {pat['before'].get(p_, 0)} | {pat['after'].get(p_, 0)} |")
    if d["spikes"]:
        L += ["", "## Cosa ha mosso l'ago (correlazione, non causa)", "", "Settimane con almeno il doppio delle recensioni delle 4 precedenti, e gli eventi dei 7 giorni prima:", ""]
        for s in d["spikes"]:
            L.append(f"- **{s['week']}** ({s['reviews']} recensioni): " + ("; ".join(f"{x['platform']} {x['kind']}: {(x.get('title') or '')[:60]}" + (f" ({x['views']:,} visualizzazioni)" if x.get("views") else "") for x in s["events"]) or "nessun evento trovato"))
    L += ["", "## Cronologia", "", "| Data | Piattaforma | Tipo | Cosa | Visualizzazioni |", "|---|---|---|---|---|"]
    L += [f"| {x['date']} | {x['platform']} | {x['kind']} | {(x.get('title') or '').replace('|', '/')[:80]} | {x.get('views') or ''} |" for x in d["timeline"][-80:]]
    L += ["", "_TikTok, Instagram e X non si cercano con script (login e termini d'uso): le ricerche da fare a mano sono in `launch/ricerche-manuali.md`; "
          "i risultati si importano con `market_tracker.py manual --import` e compaiono qui._"]
    return "\n".join(L) + "\n"


def cmd_dossier(a):
    os.makedirs(a.out_dir, exist_ok=True)
    for x in a.appid:
        d = dossier(a, int(x), a.name)
        p_ = os.path.join(a.out_dir, f"dossier-{x}.md")
        with open(p_, "w", encoding="utf-8", newline="\n") as f:
            f.write(dossier_md(d))
        with open(os.path.join(a.out_dir, f"dossier-{x}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        print(f"dossier di {d['name']}: {len(d['timeline'])} eventi, {len(d['spikes'])} picchi -> {p_}")


# ---------------------------------------------------------------- comparables measured like the cohort
def looks_like(d30: float | None, cal: dict | None) -> str:
    t = (((cal or {}).get("milestones") or {}).get("d30") or {}).get("tiers") or {}
    a, b = (t.get("A") or {}).get("reviews") or {}, (t.get("B") or {}).get("reviews") or {}
    if d30 is None or not b:
        return "n/d"
    if a and d30 >= a.get("median", 1e9):
        return "esito da fascia A (sopra la mediana degli A)"
    if d30 >= b.get("p90", 1e9):
        return "esito da B vincente (top 10 % dei B)"
    if d30 >= b.get("p75", 1e9):
        return "esito da B sopra la media"
    return "esito da B nella media o sotto"


def cmd_comps(a):
    from cohort_bench import reviews_within, read_csv as rc
    rows = [dict(appid=int(r["appid"]), name=r.get("gioco") or r.get("name"), role=r.get("ruolo") or r.get("role") or "") for r in rc(a.csv) if (r.get("appid") or "").strip().isdigit()] if os.path.exists(a.csv) else []
    for x in a.appid or []:
        if not any(r["appid"] == int(x) for r in rows):
            rows.append(dict(appid=int(x), name=None, role="aggiunto"))
    cp = a.calibration or user_dir("calibration.json")
    cal = common.load_json(cp) if os.path.exists(cp) else None
    th = dict(store=Throttle(1.0), details=Throttle(1.6), api=Throttle(1.0))
    out = []
    for r in rows:
        e = dict(appid=r["appid"], name=r["name"])
        data = fetch_meta(e, th)
        rv = api_json(APPREVIEWS.format(appid=r["appid"]), throttle=th["store"])
        tot = ((rv.get("query_summary") or {}).get("total_reviews")) if isinstance(rv, dict) else None
        h = api_json(HISTOGRAM.format(appid=r["appid"]), throttle=th["store"])
        hist = h.get("results") if isinstance(h, dict) and h.get("success") == 1 else None
        rel = e.get("release_date")
        d30 = reviews_within(hist, rel, 30, tot) if rel else None
        d90 = reviews_within(hist, rel, 90, tot) if rel else None
        po = (data or {}).get("price_overview") or {}
        out.append(dict(appid=r["appid"], name=e.get("name") or r["name"], role=r["role"], release_date=rel, price=(po.get("initial", 0) / 100) if po else (0.0 if (data or {}).get("is_free") else None),
                        reviews_total=tot, reviews_d30=d30, reviews_d90=d90, looks_like=looks_like(d30, cal)))
    res = dict(built_on=datetime.date.today().isoformat(), calibration=(cal or {}).get("generated_on"), games=out)
    write_json(res, a.out)
    for g in out:
        print(f"{(g['name'] or '')[:34]:34s} 30g {g['reviews_d30']!s:>6} 90g {g['reviews_d90']!s:>6}  -> {g['looks_like']}")


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market-dir", help="data folder (default ~/.game-launch-strategist/market)")
    ap.add_argument("--env-file", help="private .env with keys (default ~/.game-launch-strategist/.env or $GLS_ENV_FILE)")
    ap.add_argument("--today")
    sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("discover")
    d.add_argument("--top-sellers", type=int, default=0); d.add_argument("--most-played", type=int, default=0)
    d.add_argument("--tag", action="append"); d.add_argument("--tag-top", type=int, default=25)
    d.add_argument("--breakouts", type=int, default=0, help="how many fast-growing new releases to add"); d.add_argument("--days", type=int, default=30)
    d.add_argument("--max-price", type=float, default=25.0, help="breakouts: ignore games above this list price (big-studio launches)")
    d.add_argument("--from-dataset", help="grades of the cohort dataset to track, e.g. B or A,B"); d.add_argument("--dataset")
    ad = sp.add_parser("add"); ad.add_argument("appids", nargs="+"); ad.add_argument("--role", default="comp")
    s = sp.add_parser("snapshot"); s.add_argument("--players-only", action="store_true"); s.add_argument("--steamspy", action="store_true")
    s.add_argument("--now", help="ISO datetime, for tests"); s.add_argument("--limit", type=int); s.add_argument("--rate", type=float, default=1.0)
    e = sp.add_parser("estimate"); e.add_argument("--md")
    so = sp.add_parser("social"); so.add_argument("--appid", action="append"); so.add_argument("--role", help="only tracked games with this role prefix")
    so.add_argument("--limit", type=int); so.add_argument("--refresh", action="store_true"); so.add_argument("--threshold", type=int, default=em.THRESHOLD)
    so.add_argument("--no-reddit", action="store_true", help="skip Reddit (anonymous RSS is often rate limited)")
    so.add_argument("--fill-youtube", action="store_true", help="re-collect the games whose file has no YouTube part (quota ran out last time)")
    so.add_argument("--yt-quota", type=int, default=8000, help="YouTube units this run may spend (daily quota is 10,000; a search costs 100)")
    m = sp.add_parser("manual"); m.add_argument("--import", dest="import_csv"); m.add_argument("-o", "--out"); m.add_argument("--role")
    tl = sp.add_parser("timeline"); tl.add_argument("--appid", action="append"); tl.add_argument("--limit", type=int, default=10); tl.add_argument("--md")
    mk = sp.add_parser("market"); mk.add_argument("--dataset"); mk.add_argument("--md")
    cp_ = sp.add_parser("comps", help="comparables measured like the cohort: reviews at 30 / 90 days and which tier they look like")
    cp_.add_argument("--csv", default=os.path.join("launch", "comps.csv")); cp_.add_argument("--appid", action="append"); cp_.add_argument("--calibration")
    cp_.add_argument("-o", "--out", default=os.path.join("launch", "_raw", "comps_calibrated.json"))
    do = sp.add_parser("dossier", help="marketing dossier of any game: one dated timeline across Steam, YouTube, Reddit, Twitch, TikTok links, manual imports")
    do.add_argument("--appid", action="append", required=True); do.add_argument("--name"); do.add_argument("--out-dir", default=os.path.join("launch", "_raw", "dossier"))
    do.add_argument("--yt-quota", type=int, default=2000); do.add_argument("--no-reddit", action="store_true"); do.add_argument("--threshold", type=int, default=em.THRESHOLD)
    a = ap.parse_args(argv)
    names = common.load_env(a.env_file)
    if names:
        log("chiavi caricate: " + ", ".join(sorted(names)))   # names only, never values
    common.set_rate(1.0)
    dict(discover=cmd_discover, add=cmd_add, snapshot=cmd_snapshot, estimate=cmd_estimate, social=cmd_social, manual=cmd_manual,
         timeline=cmd_timeline, market=cmd_market, dossier=cmd_dossier, comps=cmd_comps)[a.cmd](a)


if __name__ == "__main__":
    main()
