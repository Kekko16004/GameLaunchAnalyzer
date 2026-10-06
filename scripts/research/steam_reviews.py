#!/usr/bin/env python3
"""Real Steam reviews for the "real critiques" section: negative (or positive) reviews of comparables,
with date, playtime, helpful votes, URL and keyword themes, plus a per-game theme tally.

Endpoint (public, no login): https://store.steampowered.com/appreviews/<appid>?json=1 (cursor pagination,
100 reviews per page). Only reviews already public on Steam are read; reviewer names are NOT collected.

Sampling honesty:
  --sort helpful  (default) = Steam's "most helpful" order: over-represents the most discussed problems.
  --sort recent             = newest first: closer to a random slice of current complaints.
The theme tally is a keyword heuristic over English text (complaint themes for negative reviews, praise themes
for positive ones, see --taxonomy). It is a starting point for the human/LLM
reader, NOT an analysis: read a sample of the reviews and correct the themes by hand.

Examples:
  python steam_reviews.py 1599600 728880 --type negative --within-days 365 --limit 150 -o reviews_neg.json
  python steam_reviews.py 1599600 --type negative --sort recent --max-playtime-h 2 -o refund_like.json
  python steam_reviews.py 1599600 --type positive --limit 100 -o praised.json     # "what the audience rewards"
  python steam_reviews.py --ids-file ids.txt --language all --themes-json my_themes.json -o reviews.csv
"""
from __future__ import annotations

import argparse
import re
import statistics
import time
import urllib.parse
from common import load_json, log, read_list, safe_json, set_rate, ts_to_date, write_csv, write_json

# theme -> regex (English, case-insensitive). Override/extend with --themes-json {"theme": "regex"}.
THEMES = {
    "onboarding_tutorial": r"tutorial|confus|no explanation|doesn'?t explain|hard to understand|learning curve|unclear|don'?t know what (?:to do|i'?m doing)",
    "repetitive_shallow": r"repetitiv|\brepeat|grind|boring|tedious|monoton|same thing|samey|shallow|get(?:s|ting)? old",
    "difficulty_balance": r"unbalanc|balanc|too hard|too easy|unfair|overpowered|(?<![\w-])op(?![\w-])|\brng\b|cheap death|difficulty spike|pay[- ]to[- ]win",
    "bugs_crashes": r"\bbugs?\b|bugg|crash|glitch|broken|freez|soft ?lock|game[- ]breaking|save(?:s|file)? (?:lost|corrupt|wiped)",
    "performance": r"perform|\bfps\b|frame ?rate|stutter|\blag\b|optimi[sz]|memory leak|loading (?:time|screen)",
    "price_value_length": r"overpriced|not worth|too short|too expensive|wait for (?:a )?sale|for the price|hours? of content|money",
    "content_depth": r"not enough content|lack of content|little content|empty|unfinished|feels? (?:incomplete|unfinished)|more content|barebones|bare bones|early access",
    "ui_ux_controls": r"\bui\b|\bux\b|interface|menu|controls?\b|controller|key ?bind|rebind|camera|clunky|unintuitive|\bmouse\b",
    "multiplayer_netcode": r"multiplayer|netcode|servers?\b|matchmak|desync|dead game|no players|empty lobb|co-?op|\bonline\b",
    "story_writing_audio": r"\bstory\b|writing|dialog|voice|translation|localiz|\bmusic\b|\bsound\b|\baudio\b",
    "art_visuals": r"graphics|visuals?|art ?style|ugly|asset[- ]?flip|low[ -]effort|unpolished|animation",
    "ai_generated_assets": r"ai[- ]generated|generative ai|\bai art\b|\bai voice|ai slop",
    "ai_behavior": r"enemy ai|\bai (?:is|are|was)|dumb ai|stupid ai|pathfinding",
    "monetization_dlc": r"\bdlc\b|microtransaction|paywall|cash[- ]grab|\bmtx\b",
    "dev_support": r"abandon|no updates?|no patch|dev(?:eloper)?s? (?:don'?t|doesn'?t|never)|dead dev|developer (?:support|communication)",
    "steam_deck": r"steam ?deck",
    "refund_mentions": r"refund",
}


# what players PRAISE (used for positive reviews: "what the audience rewards")
PRAISE_THEMES = {
    "fun_addictive": r"\bfun\b|addict|one more (?:run|turn|game|level)|hooked|can'?t stop|so good|a blast",
    "art_style": r"art ?style|beautiful|gorgeous|graphics|visuals?|pixel art|aesthetic|stunning|charming",
    "music_sound": r"\bmusic\b|soundtrack|\bost\b|sound design|\bsfx\b|\baudio\b",
    "depth_variety": r"depth|variety|diverse|\bbuilds?\b|synerg|so many (?:options|ways)|strateg",
    "replayability": r"replay|run after run|hundreds of hours|endless|every run|different every",
    "value_for_money": r"worth (?:it|the|every)|great value|bargain|cheap|price",
    "story_characters": r"\bstory\b|character|writing|dialog|\blore\b|world.?building|narrative",
    "polish_feel": r"polish|smooth|responsive|tight controls|satisfying|juicy|game ?feel|feels? (?:great|good)",
    "coop_friends": r"co-?op|with (?:my )?friends|multiplayer|\bparty\b",
    "content_amount": r"lots? of content|so much content|plenty of|content-?rich|hours of content",
    "dev_support_positive": r"devs? (?:are|is)|active dev|developers? (?:are|is)|listens?|regular updates|patches",
    "easy_to_learn": r"easy to (?:learn|pick up)|intuitive|accessible|beginner|newcomer",
    "relaxing_cozy": r"relax|cozy|cosy|\bchill\b|comfort|wholesome|\bcalm\b|stress.?free",
    "challenge_rewarding": r"challeng|rewarding|skill|mastery",
}


def compile_themes(path: str | None, review_type: str = "negative", taxonomy: str = "auto") -> dict:
    """taxonomy auto: complaints for negative reviews, praise for positive, both for 'all'."""
    kind = taxonomy if taxonomy != "auto" else {"negative": "complaints", "positive": "praise"}.get(review_type, "both")
    src = {}
    if kind in ("complaints", "both"):
        src.update(THEMES)
    if kind in ("praise", "both"):
        src.update(PRAISE_THEMES)
    if path:
        src.update(load_json(path))
    return {k: re.compile(v, re.I) for k, v in src.items()}


def default_opts(**kw):
    """Options object for fetch_reviews when used as a library (same defaults as the command line)."""
    import types
    o = dict(type="negative", sort="helpful", language="english", within_days=None, limit=100, max_pages=30, min_votes_up=0,
             max_playtime_h=None, min_playtime_h=None, purchase="all", include_offtopic=False, max_chars=1500)
    o.update(kw)
    return types.SimpleNamespace(**o)


def game_name(appid: int) -> str | None:
    d = safe_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=basic")
    return ((d.get(str(appid)) or {}).get("data") or {}).get("name")


def fetch_reviews(appid: int, a, themes: dict) -> dict:
    flt = {"helpful": "all", "recent": "recent", "updated": "updated"}[a.sort]
    purchase = {"all": "all", "steam": "steam", "other": "non_steam_purchase"}[a.purchase]
    cutoff = time.time() - a.within_days * 86400 if a.within_days else None
    cursor, pages, seen, out, summary, stop = "*", 0, set(), [], None, False
    while len(out) < a.limit and pages < a.max_pages and not stop:
        params = dict(json=1, filter=flt, language=a.language, review_type=a.type, purchase_type=purchase,
                      num_per_page=100, cursor=cursor)
        if a.sort == "helpful" and a.within_days:
            params["day_range"] = min(a.within_days, 365)  # Steam caps day_range at 365 and only honours it with filter=all
        if a.include_offtopic:
            params["filter_offtopic_activity"] = 0  # default hides Steam-flagged review-bomb periods
        d = safe_json(f"https://store.steampowered.com/appreviews/{appid}?" + urllib.parse.urlencode(params))
        if not d.get("success"):
            log(f"WARN {appid}: no reviews returned (blocked, delisted or no data)")
            break
        summary = summary or d.get("query_summary")
        revs = d.get("reviews") or []
        if not revs:
            break
        for r in revs:
            rid, au = r.get("recommendationid"), r.get("author") or {}
            if rid in seen:
                continue
            seen.add(rid)
            created = r.get("timestamp_created") or 0
            if cutoff and created < cutoff:
                if a.sort == "recent":
                    stop = True  # newest first: everything after is older
                continue
            mins = au.get("playtime_at_review")
            mins = au.get("playtime_forever") if mins is None else mins
            hours = round(mins / 60, 1) if mins is not None else None
            if (a.max_playtime_h is not None and (hours is None or hours > a.max_playtime_h)) or \
               (a.min_playtime_h is not None and (hours is None or hours < a.min_playtime_h)) or \
               (r.get("votes_up") or 0) < a.min_votes_up:
                continue
            text = (r.get("review") or "").replace("\r", " ").strip()
            found = [k for k, rx in themes.items() if rx.search(text)]
            out.append(dict(
                appid=appid, recommendation_id=rid,
                url=f"https://steamcommunity.com/profiles/{au.get('steamid')}/recommended/{appid}/" if au.get("steamid") else None,
                voted_up=r.get("voted_up"), date=ts_to_date(created) if created else None,
                language=r.get("language"), playtime_at_review_h=hours,
                playtime_forever_h=round(au["playtime_forever"] / 60, 1) if au.get("playtime_forever") is not None else None,
                votes_up=r.get("votes_up"), votes_funny=r.get("votes_funny"),
                helpful_score=float(r["weighted_vote_score"]) if r.get("weighted_vote_score") else None,
                steam_purchase=r.get("steam_purchase"), received_for_free=r.get("received_for_free"),
                early_access=r.get("written_during_early_access"),
                chars=len(text), text=text[:a.max_chars], themes=found))
            if len(out) >= a.limit:
                break
        new = d.get("cursor")
        if not new or new == cursor:
            break
        cursor, pages = new, pages + 1
    return dict(appid=appid, query_summary=summary, sampled=len(out), reviews=out)


def tally(reviews: list[dict], themes: dict) -> dict:
    n = len(reviews)
    if not n:
        return dict(sampled=0)
    counts = {k: sum(1 for r in reviews if k in r["themes"]) for k in themes}
    hrs = [r["playtime_at_review_h"] for r in reviews if r["playtime_at_review_h"] is not None]
    dates = sorted(r["date"] for r in reviews if r["date"])
    return dict(
        sampled=n,
        themes={k: dict(count=c, pct=round(100 * c / n, 1)) for k, c in sorted(counts.items(), key=lambda x: -x[1]) if c},
        median_playtime_at_review_h=round(statistics.median(hrs), 1) if hrs else None,
        pct_under_2h=round(100 * sum(1 for h in hrs if h < 2) / len(hrs), 1) if hrs else None,
        median_votes_up=statistics.median([r["votes_up"] or 0 for r in reviews]),
        date_range=[dates[0], dates[-1]] if dates else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("appids", nargs="*", help="Steam app ids")
    ap.add_argument("--ids-file", help="text file, one app id per line (# comments ok)")
    ap.add_argument("--type", default="negative", choices=["negative", "positive", "all"], help="review type (default negative)")
    ap.add_argument("--sort", default="helpful", choices=["helpful", "recent", "updated"], help="sampling order (default helpful)")
    ap.add_argument("--language", default="english", help="Steam language name or 'all' (default english; themes are English keywords)")
    ap.add_argument("--within-days", type=int, help="only reviews created in the last N days")
    ap.add_argument("--limit", type=int, default=100, help="max reviews kept per game after filters (default 100)")
    ap.add_argument("--max-pages", type=int, default=30, help="safety cap on pages of 100 per game (default 30)")
    ap.add_argument("--min-votes-up", type=int, default=0, help="keep reviews with at least N helpful votes")
    ap.add_argument("--max-playtime-h", type=float, help="keep reviews written at <= H hours (refund-like: 2)")
    ap.add_argument("--min-playtime-h", type=float, help="keep reviews written at >= H hours")
    ap.add_argument("--purchase", default="all", choices=["all", "steam", "other"], help="purchase type (other = key/non-Steam)")
    ap.add_argument("--include-offtopic", action="store_true", help="include Steam-flagged off-topic/review-bomb activity")
    ap.add_argument("--max-chars", type=int, default=1500, help="truncate stored review text (default 1500)")
    ap.add_argument("--taxonomy", default="auto", choices=["auto", "complaints", "praise", "both"],
                    help="theme list: auto = complaints for negative, praise for positive, both for all")
    ap.add_argument("--themes-json", help='JSON {"theme": "regex"} added to / overriding the built-in themes')
    ap.add_argument("--rate", type=float, default=1.2, help="min seconds between requests (default 1.2)")
    ap.add_argument("-o", "--out", default="-", help="output .json or .csv (default stdout JSON)")
    a = ap.parse_args()
    set_rate(a.rate)
    ids = [int(x) for x in read_list(a.appids, a.ids_file)]
    if not ids:
        ap.error("no app ids given")
    themes = compile_themes(a.themes_json, a.type, a.taxonomy)
    games = []
    for i in ids:
        g = fetch_reviews(i, a, themes)
        g["name"] = game_name(i)
        g["summary"] = tally(g["reviews"], themes)
        games.append(g)
        top = ", ".join(f"{k} {v['pct']}%" for k, v in list(g["summary"].get("themes", {}).items())[:3])
        log(f"{i} | {g['name']} | sampled {g['sampled']} | {top or 'no themes'}")
    if a.out.lower().endswith(".csv"):
        rows = [dict(name=g["name"], **{k: (r[k] if k != "themes" else "; ".join(r[k])) for k in r}) for g in games for r in g["reviews"]]
        write_csv(rows, a.out)
    else:
        write_json(dict(
            note="Samples are not random (see --sort). Theme counts are a keyword heuristic over English text: verify by reading. "
                 "In deliverables paraphrase, quote < 15 words, one per source, never name reviewers.",
            params={k: v for k, v in vars(a).items() if k not in ("appids", "ids_file", "out")}, games=games), a.out)


if __name__ == "__main__":
    main()
