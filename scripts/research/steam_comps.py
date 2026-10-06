#!/usr/bin/env python3
"""Steam comparables: store data + review summary + Boxleiter estimates (+ optional SteamSpy / Gamalytic).

Endpoints (public, no login):
  - https://store.steampowered.com/api/appdetails?appids=ID      (store page data)
  - https://store.steampowered.com/appreviews/ID?json=1           (review summary)
  - https://steamspy.com/api.php?request=appdetails&appid=ID       (--steamspy, owners range + tags)
  - https://gamalytic.com/api/game-details/ID                      (--gamalytic, third-party estimates)

Examples:
  python steam_comps.py 1599600 728880 -o comps.json
  python steam_comps.py --ids-file ids.txt --steamspy --gamalytic -o comps.csv --headers-dir hdr
"""
from __future__ import annotations

import argparse
import os
from common import http_get, log, read_list, safe_json, set_rate, ts_to_date, write_csv, write_json


def fetch_app(appid: int, cc: str, lang: str, use_spy: bool, use_gam: bool, multipliers: list[int]) -> dict:
    d = safe_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}&l={lang}")
    d = (d.get(str(appid)) or {}).get("data") or {}
    r = safe_json(f"https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all"
                  f"&num_per_page=0&filter=all").get("query_summary") or {}
    po = d.get("price_overview") or {}
    rd = d.get("release_date") or {}
    total, pos = r.get("total_reviews"), r.get("total_positive")
    o = dict(
        appid=appid, name=d.get("name"), steam_url=f"https://store.steampowered.com/app/{appid}/",
        release_date=rd.get("date"), coming_soon=rd.get("coming_soon"), is_free=d.get("is_free"),
        price_base_cents=po.get("initial"), price_now_cents=po.get("final"), discount_pct=po.get("discount_percent"),
        currency=po.get("currency"), developers=d.get("developers"), publishers=d.get("publishers"),
        genres=[g["description"] for g in d.get("genres") or []],
        categories=[c["description"] for c in d.get("categories") or []][:15],
        demos=[x.get("appid") for x in d.get("demos") or []], movies=len(d.get("movies") or []),
        screenshots=len(d.get("screenshots") or []), header_image=d.get("header_image"),
        reviews_total=total, reviews_positive=pos,
        pct_positive=round(100 * pos / total, 1) if total else None, review_score_desc=r.get("review_score_desc"),
    )
    # Boxleiter: copies ~= total reviews x multiplier (rule of thumb; 30 = conservative, 60 = optimistic)
    for m in multipliers:
        o[f"boxleiter_x{m}"] = total * m if total is not None else None
    if use_spy:
        s = safe_json(f"https://steamspy.com/api.php?request=appdetails&appid={appid}")
        o["steamspy_owners"] = s.get("owners")
        o["steamspy_tags"] = list((s.get("tags") or {}).keys())[:10] if isinstance(s.get("tags"), dict) else []
    if use_gam:
        g = safe_json(f"https://gamalytic.com/api/game-details/{appid}").get("data") or {}
        first = g.get("firstReleaseDate")
        o.update(
            gamalytic_copies=g.get("copiesSold"), gamalytic_revenue=g.get("revenue"),
            gamalytic_accuracy=round(g["accuracy"], 2) if g.get("accuracy") is not None else None,
            gamalytic_avg_playtime_h=round(g["avgPlaytime"], 1) if g.get("avgPlaytime") is not None else None,
            gamalytic_followers=g.get("followers"), gamalytic_tags=(g.get("tags") or [])[:10],
            gamalytic_early_access=g.get("earlyAccess"), gamalytic_price=g.get("price"),
            gamalytic_first_release=ts_to_date(first / 1000) if first else None,
            gamalytic_audience_overlap=[x.get("name") for x in (g.get("audienceOverlap") or [])[:8]],
        )
        if o["gamalytic_copies"] and total:
            o["copies_per_review"] = round(o["gamalytic_copies"] / total)
    return o


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("appids", nargs="*", help="Steam app ids")
    ap.add_argument("--ids-file", help="text file, one app id per line (# comments ok)")
    ap.add_argument("-o", "--out", default="-", help="output .json or .csv (default stdout JSON)")
    ap.add_argument("--cc", default="us", help="store country code for prices (default us)")
    ap.add_argument("--lang", default="en", help="store language (default en)")
    ap.add_argument("--steamspy", action="store_true", help="add SteamSpy owners range + tags")
    ap.add_argument("--gamalytic", action="store_true", help="add Gamalytic estimates (third-party, public API)")
    ap.add_argument("--boxleiter", default="30,60", help="review multipliers, comma separated (default 30,60)")
    ap.add_argument("--headers-dir", help="also download each header image to DIR/<appid>.jpg")
    ap.add_argument("--rate", type=float, default=1.2, help="min seconds between requests (default 1.2)")
    a = ap.parse_args()
    set_rate(a.rate)
    ids = [int(x) for x in read_list(a.appids, a.ids_file)]
    if not ids:
        ap.error("no app ids given")
    mult = [int(x) for x in a.boxleiter.split(",") if x.strip()]
    rows = []
    for i in ids:
        o = fetch_app(i, a.cc, a.lang, a.steamspy, a.gamalytic, mult)
        rows.append(o)
        log(f"{i} | {o['name']} | {o['release_date']} | reviews {o['reviews_total']} ({o['pct_positive']}%) | demo {o['demos']}")
        if a.headers_dir and o.get("header_image"):
            os.makedirs(a.headers_dir, exist_ok=True)
            try:
                with open(os.path.join(a.headers_dir, f"{i}.jpg"), "wb") as f:
                    f.write(http_get(o["header_image"]))
            except Exception as e:  # noqa: BLE001
                log(f"WARN header {i}: {e}")
    if a.out.lower().endswith(".csv"):
        write_csv(rows, a.out)
    else:
        write_json(rows, a.out)


if __name__ == "__main__":
    main()
