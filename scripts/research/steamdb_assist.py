#!/usr/bin/env python3
"""SteamDB as a manual lookup, never as a scraper.

SteamDB has no public API and its terms do not allow automated scraping (it sits behind a bot wall), so this tool
does NOT fetch anything from steamdb.info. It does the two useful things around it:

  links   which SteamDB pages to open for your comparables/competitors and what to read on each (a checklist,
          written to Markdown so it can go into launch/ricerche-manuali.md)
  add     record what you read there, one row per game and date, append-only, in launch/steamdb.csv
  show    latest values and change since the previous record, per game

What SteamDB shows that public Steam endpoints do not (or not conveniently): followers, the wishlist rank among
games, player peaks (24h, all-time) with history, price history and the lowest price, update/patch cadence.
Wishlists of other games stay unknown: only a rank. Everything you type is a [FATTO] with the date you read it.

  steamdb_assist.py links 1599600 728880 [--md launch/_raw/steamdb_links.md]
  steamdb_assist.py add 1599600 --followers 12,400 --wishlist-rank 850 --peak-24h 310 --peak-all 4,100 --lowest-price 8.99 [--date D] [--note "..."]
  steamdb_assist.py show [--csv launch/steamdb.csv] [--md out.md]

URL patterns are [DA VERIFICARE]: SteamDB changes its layout; if a link is dead, search the game on the site.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os

from common import log, parse_count

FIELDS = ["date", "appid", "followers", "wishlist_rank", "peak_24h", "peak_all_time", "lowest_price", "note"]
NUMERIC = ["followers", "wishlist_rank", "peak_24h", "peak_all_time"]
PAGES = [
    ("app/{id}/", "followers, wishlist rank, rating, tags, release date, price"),
    ("app/{id}/charts/", "players now, 24h peak, all-time peak, and the history (growth after launch, Next Fest, sales)"),
    ("app/{id}/", "price history and lowest price (section on the same page); patches and update cadence in the Patches tab"),
]
GLOBAL = [
    ("https://steamdb.info/stats/mostwished/", "most wishlisted games: the visibility bar for your window (read the rank at which games sit)"),
    ("https://steamdb.info/upcoming/", "upcoming releases: competitors in your launch window (compare with watchlist.py)"),
]


def links(appids: list[str]) -> str:
    L = ["# SteamDB: cosa aprire e cosa leggere", "",
         "Non automatizzato: SteamDB non ha API pubblica e vieta lo scraping. Leggi i numeri a mano e registrali con `steamdb_assist.py add`. URL [DA VERIFICARE].", ""]
    for a in appids:
        L += [f"## App {a}", ""]
        for path, what in PAGES[:2]:
            L.append(f"- https://steamdb.info/{path.format(id=a)}: {what}")
        L.append(f"- Prezzi e patch: stessa pagina https://steamdb.info/app/{a}/ ({PAGES[2][1]})")
        L.append(f"- Pagina store: https://store.steampowered.com/app/{a}/")
        L.append("")
    L += ["## Liste globali", ""] + [f"- {u}: {w}" for u, w in GLOBAL] + [""]
    L += ["## Da registrare per ogni gioco", "", "| Campo | Dove |", "|---|---|",
          "| followers | pagina app, riquadro informazioni |", "| wishlist_rank | pagina app, se compare la posizione tra i più desiderati |",
          "| peak_24h, peak_all_time | scheda Charts |", "| lowest_price | storico prezzi |", ""]
    return "\n".join(L)


def read(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append(path: str, row: dict):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: ("" if row.get(k) is None else row[k]) for k in FIELDS})


def show(rows: list[dict]) -> str:
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["appid"], []).append(r)
    L = ["| App | Data | Followers | Δ followers | Rank wishlist | Picco 24h | Picco assoluto | Prezzo minimo |", "|---|---|---|---|---|---|---|---|"]
    for a, rs in sorted(by.items()):
        rs.sort(key=lambda r: r["date"])
        last, prev = rs[-1], (rs[-2] if len(rs) > 1 else None)
        n = lambda r, k: parse_count(r.get(k)) if r.get(k) not in (None, "") else None
        d = "" if not prev or n(last, "followers") is None or n(prev, "followers") is None else f"{n(last, 'followers') - n(prev, 'followers'):+d}"
        f = lambda v: "" if v is None else f"{v:,}"
        L.append(f"| {a} | {last['date']} | {f(n(last, 'followers'))} | {d} | {f(n(last, 'wishlist_rank'))} | {f(n(last, 'peak_24h'))} | {f(n(last, 'peak_all_time'))} | {last.get('lowest_price') or ''} |")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("links"); p.add_argument("appids", nargs="+"); p.add_argument("--md")
    p = sub.add_parser("add"); p.add_argument("appid"); p.add_argument("--date", default=dt.date.today().isoformat())
    p.add_argument("--followers"); p.add_argument("--wishlist-rank"); p.add_argument("--peak-24h"); p.add_argument("--peak-all"); p.add_argument("--lowest-price")
    p.add_argument("--note", default=""); p.add_argument("--csv", default="launch/steamdb.csv")
    p = sub.add_parser("show"); p.add_argument("--csv", default="launch/steamdb.csv"); p.add_argument("--md")
    a = ap.parse_args()
    if a.cmd == "links":
        text = links(a.appids)
        if a.md:
            os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
            open(a.md, "w", encoding="utf-8", newline="\n").write(text)
            print("wrote", a.md)
        else:
            print(text)
    elif a.cmd == "add":
        vals = dict(followers=a.followers, wishlist_rank=a.wishlist_rank, peak_24h=a.peak_24h, peak_all_time=a.peak_all)
        row = dict(date=a.date, appid=a.appid, lowest_price=a.lowest_price, note=a.note)
        for k, v in vals.items():
            n = parse_count(v) if v else None
            if v and n is None:
                ap.error(f"--{k.replace('_', '-')}: '{v}' is not a number")
            row[k] = n
        if not any(row.get(k) is not None for k in NUMERIC) and not a.lowest_price:
            ap.error("nothing to record: give at least one value")
        append(a.csv, row)
        log(f"recorded {a.appid} on {a.date} in {a.csv}")
    else:
        rows = read(a.csv)
        text = show(rows) if rows else "Nessun dato in " + a.csv
        if a.md:
            open(a.md, "w", encoding="utf-8", newline="\n").write(text + "\n")
        print(text)


if __name__ == "__main__":
    main()
