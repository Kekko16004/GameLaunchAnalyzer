#!/usr/bin/env python3
"""Find comparable games: keyword/name -> Steam app ids, or Steam tag -> most reviewed games.

Subcommands:
  search  TERM...  Steam store search (public endpoint store.steampowered.com/api/storesearch).
                   Use it to resolve names you already know to app ids, or to explore a keyword.
  tag     TAG...   SteamSpy "tag" listing (steamspy.com/api.php?request=tag): the ~100 most reviewed games
                   per tag. Several tags are merged; rows matching more tags rank first (--require-all keeps
                   only games present in every list). --enrich N adds release date, price, genres, demo and
                   coming-soon from the Steam store for the top N rows (1 request each).

Limits: SteamSpy lists only the top ~100 games per tag and is a third-party service; owners are ranges.
Tag names are matched loosely and case-sensitively by SteamSpy ("Roguelite" returns another tag's list, the right
spelling is "Rogue-lite"): tags are resolved first, with spelling variants, typo correction and a check of each list
(steam_tags.py explains how; `python steam_tags.py Roguelite` shows what a name resolves to). The result is a CANDIDATE
list: the final comparable set (successes, mid performers, instructive flops) is chosen by a human.

Examples:
  python steam_discover.py search "cooking roguelite" "overcooked" --limit 8 -o search.json
  python steam_discover.py tag Roguelike Cooking --enrich 40 --released-after 2021 --max-reviews 20000 -o tags.csv
"""
from __future__ import annotations

import argparse
import re
from common import log, q, safe_json, set_rate, write_output
import steam_tags


def cmd_search(a):
    rows = []
    for term in a.terms:
        d = safe_json(f"https://store.steampowered.com/api/storesearch/?term={q(term)}&cc={a.cc}&l={a.lang}")
        for it in (d.get("items") or [])[:a.limit]:
            if it.get("type") not in (None, "app"):
                continue
            p = it.get("price") or {}
            rows.append(dict(term=term, appid=it.get("id"), name=it.get("name"), price_final_cents=p.get("final"),
                             currency=p.get("currency"), metascore=it.get("metascore") or None,
                             url=f"https://store.steampowered.com/app/{it.get('id')}/"))
        log(f"{term!r}: {sum(1 for r in rows if r['term'] == term)} results")
    write_output(rows, a.out)


def release_year(s: str | None) -> int | None:
    m = re.search(r"(19|20)\d{2}", s or "")
    return int(m.group(0)) if m else None


def enrich(row: dict, cc: str, lang: str):
    d = safe_json(f"https://store.steampowered.com/api/appdetails?appids={row['appid']}&cc={cc}&l={lang}")
    d = (d.get(str(row["appid"])) or {}).get("data") or {}
    po, rd = d.get("price_overview") or {}, d.get("release_date") or {}
    row.update(release_date=rd.get("date"), coming_soon=rd.get("coming_soon"), type=d.get("type"),
               is_free=d.get("is_free"), price_base_cents=po.get("initial"), price_now_cents=po.get("final"),
               genres=[g["description"] for g in d.get("genres") or []],
               has_demo=bool(d.get("demos")), developers=d.get("developers"))


def candidates(tags: list[str], require_all: bool = False, min_reviews: int | None = None,
               max_reviews: int | None = None, top: int = 100, variants: bool = True, validate: bool = True) -> list[dict]:
    """Games listed under the given tags (SteamSpy), ranked by tags matched then review count.

    Each tag is resolved first (steam_tags.py): spelling variants ("Roguelite" -> "Rogue-lite"), typos, and a check that the
    list SteamSpy returns really carries the tag. variants=False / validate=False restore the literal, unchecked behaviour.
    """
    games: dict[str, dict] = {}
    for tag in tags:
        d, rep = steam_tags.collect(tag, variants=variants, validate=validate)
        for aid, g in d.items():
            r = games.setdefault(str(aid), dict(
                appid=int(aid), name=g.get("name"), developer=g.get("developer"), matched_tags=[],
                positive=g.get("positive"), negative=g.get("negative"), owners_steamspy=g.get("owners"),
                avg_playtime_forever_min=g.get("average_forever"), price_cents=g.get("price"),
                url=f"https://store.steampowered.com/app/{aid}/"))
            r["matched_tags"].append(tag)
        log(f"tag {tag!r}: {len(d)} games from {rep['accepted'] or rep['unverified'] or 'no usable spelling'}")
    rows = list(games.values())
    for r in rows:
        pos, neg = r.get("positive") or 0, r.get("negative") or 0
        r["reviews_total"] = pos + neg
        r["pct_positive"] = round(100 * pos / (pos + neg), 1) if pos + neg else None
        r["n_tags"] = len(r["matched_tags"])
    if require_all:
        rows = [r for r in rows if r["n_tags"] == len(tags)]
    rows = [r for r in rows if (min_reviews is None or r["reviews_total"] >= min_reviews)
            and (max_reviews is None or r["reviews_total"] <= max_reviews)]
    rows.sort(key=lambda r: (-r["n_tags"], -r["reviews_total"]))
    return rows[:top]


def cmd_tag(a):
    rows = candidates(a.tags, a.require_all, a.min_reviews, a.max_reviews, a.top, variants=not a.exact_tags, validate=not a.no_validate_tags)
    if a.enrich:
        for r in rows[:a.enrich]:
            enrich(r, a.cc, a.lang)
        if a.released_after:
            rows = [r for r in rows if not r.get("release_date") or (release_year(r["release_date"]) or 9999) >= a.released_after]
    for r in rows:
        r["matched_tags"] = "; ".join(r["matched_tags"])
    log(f"{len(rows)} candidates")
    write_output(rows, a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=float, default=1.2, help="min seconds between requests (default 1.2)")
    ap.add_argument("--cc", default="us", help="store country code for prices (default us)")
    ap.add_argument("--lang", default="english", help="store language (default english)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="store search by keyword or game name")
    s.add_argument("terms", nargs="+")
    s.add_argument("--limit", type=int, default=10, help="results per term (default 10)")
    s.add_argument("-o", "--out", default="-")
    s.set_defaults(fn=cmd_search)

    t = sub.add_parser("tag", help="most reviewed games per Steam tag (SteamSpy)")
    t.add_argument("tags", nargs="+", help='tag names, e.g. Roguelike "City Builder"')
    t.add_argument("--require-all", action="store_true", help="keep only games listed under every tag")
    t.add_argument("--min-reviews", type=int, help="drop games with fewer reviews")
    t.add_argument("--max-reviews", type=int, help="drop games with more reviews (skip the mega-hits)")
    t.add_argument("--exact-tags", action="store_true", help="use the tag names exactly as typed (no spelling variants or typo correction)")
    t.add_argument("--no-validate-tags", action="store_true", help="skip the check that each SteamSpy list really carries the tag (saves 3 requests per spelling)")
    t.add_argument("--top", type=int, default=100, help="keep the top N rows after filters (default 100)")
    t.add_argument("--enrich", type=int, default=0, help="add store data (release date, price, demo) to the top N rows")
    t.add_argument("--released-after", type=int, help="with --enrich: drop games released before this year")
    t.add_argument("-o", "--out", default="-", help=".json or .csv")
    t.set_defaults(fn=cmd_tag)

    a = ap.parse_args()
    set_rate(a.rate)
    a.fn(a)


if __name__ == "__main__":
    main()
