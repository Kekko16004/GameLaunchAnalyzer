#!/usr/bin/env python3
"""Watchlist: follow your comparables and your competitors over time, with append-only snapshots in one CSV.

Run `snap` whenever you like (weekly is plenty): it records, for every tracked game, the public numbers of that
day. `report` turns the history into growth, and alerts: a game going viral, a discount, a release, a drop in
% positive, a player spike, and a competitor releasing in YOUR launch window. Public Steam endpoints only
(store details, review summary, current players); nothing is installed, nothing runs in the background.

Roles: comp (comparable to learn from), competitor (releases that can hurt your window), self (your own game once
it has a Steam page).

  watchlist.py add 1599600 728880 --role comp [--csv launch/watchlist.csv]       # first snapshot
  watchlist.py snap [--csv launch/watchlist.csv]                                 # snapshot everything tracked
  watchlist.py report --launch 2027-03-01 --window-days 30 [--md launch/watchlist-report.md] [--json out.json]

Honest limit: it sees what Steam shows publicly. Wishlists and sales of other games are not public.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import statistics
from common import log, safe_json, set_rate, write_json
from store_bench import parse_release

FIELDS = ["date", "appid", "name", "role", "reviews_total", "reviews_positive", "pct_positive", "price_cents", "discount_pct", "players", "coming_soon", "release_date"]
D = dt.date.fromisoformat


def fetch(appid: int) -> dict:
    d = safe_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=english")
    d = (d.get(str(appid)) or {}).get("data") or {}
    r = safe_json(f"https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all&num_per_page=0&filter=all").get("query_summary") or {}
    p = safe_json(f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={appid}").get("response") or {}
    players = p.get("player_count") if p.get("result") == 1 else None   # result 1 = ok; anything else = Steam has no count for this app
    po, rd = d.get("price_overview") or {}, d.get("release_date") or {}
    total, pos = r.get("total_reviews"), r.get("total_positive")
    rel = parse_release(rd.get("date"))
    return dict(appid=appid, name=d.get("name"), reviews_total=total, reviews_positive=pos, pct_positive=round(100 * pos / total, 1) if total else None,
                price_cents=po.get("initial"), discount_pct=po.get("discount_percent", 0), players=players,
                coming_soon=1 if rd.get("coming_soon") else 0, release_date=rel.isoformat() if rel and (rel.month or rel.day) else (rd.get("date") or ""))


def read(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path: str, rows: list[dict]):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["date"], int(r["appid"]))))


def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def snapshot(csv_path: str, targets: list[tuple[int, str]], today: str):
    rows = read(csv_path)
    for appid, role in targets:
        s = fetch(appid)
        rows = [r for r in rows if not (r["date"] == today and int(r["appid"]) == appid)]  # one row per game per day
        rows.append(dict(s, date=today, role=role))
        log(f"{appid} | {s['name']} | reviews {s['reviews_total']} ({s['pct_positive']}%) | players {s['players']} | discount {s['discount_pct']}%")
    write(csv_path, rows)


def at_or_before(hist: list[dict], day: dt.date, tolerance: int):
    best = None
    for r in hist:
        d = D(r["date"])
        if d <= day and (day - d).days <= tolerance:
            best = r
    return best


def analyse(rows: list[dict], today: dt.date, launch: dt.date | None, window: int, viral_factor: float) -> dict:
    out = dict(today=today.isoformat(), games=[], alerts=[])
    for appid in sorted({int(r["appid"]) for r in rows}):
        hist = sorted((r for r in rows if int(r["appid"]) == appid), key=lambda r: r["date"])
        last = hist[-1]
        g = dict(appid=appid, name=last["name"], role=last["role"], last=last["date"], snapshots=len(hist), reviews=num(last["reviews_total"]), pct_positive=num(last["pct_positive"]),
                 price=(num(last["price_cents"]) or 0) / 100, discount=num(last["discount_pct"]) or 0, players=num(last["players"]), coming_soon=last["coming_soon"] == "1", release=last["release_date"])
        ld = D(last["date"])
        for days in (7, 30):
            old = at_or_before(hist[:-1], ld - dt.timedelta(days=days), tolerance=max(3, days // 3))
            g[f"gain_{days}d"] = (g["reviews"] - num(old["reviews_total"])) if old and g["reviews"] is not None and num(old["reviews_total"]) is not None else None
        label = f"{last['name']} ({last['role']})"
        weekly = []
        for a, b in zip(hist, hist[1:]):
            span = (D(b["date"]) - D(a["date"])).days
            if span >= 5 and num(a["reviews_total"]) is not None and num(b["reviews_total"]) is not None:
                weekly.append((num(b["reviews_total"]) - num(a["reviews_total"])) / span * 7)
        if g["gain_7d"] is not None and len(weekly) >= 3:
            med = statistics.median(weekly[:-1]) if len(weekly) > 1 else 0
            if g["gain_7d"] >= max(50, viral_factor * max(med, 1)):
                out["alerts"].append(dict(level="INFO", game=label, text=f"Impennata: +{g['gain_7d']:.0f} recensioni in 7 giorni contro una mediana di {med:.0f}/settimana. Cerca cosa è successo (creator, saldo, festival)."))
        if (num(last["discount_pct"]) or 0) > 0:
            since = last["date"]
            for r in reversed(hist):
                if (num(r["discount_pct"]) or 0) > 0:
                    since = r["date"]
                else:
                    break
            out["alerts"].append(dict(level="INFO", game=label, text=f"In saldo del {int(g['discount'])}% (rilevato dal {since})."))
        if len(hist) > 1 and hist[-2]["coming_soon"] == "1" and not g["coming_soon"]:
            out["alerts"].append(dict(level="ATTENZIONE" if last["role"] == "competitor" else "INFO", game=label, text="È uscito."))
        old30 = at_or_before(hist[:-1], ld - dt.timedelta(days=30), 12)
        if old30 and (g["reviews"] or 0) >= 200 and num(old30["pct_positive"]) is not None and g["pct_positive"] is not None and g["pct_positive"] <= num(old30["pct_positive"]) - 3:
            out["alerts"].append(dict(level="ATTENZIONE", game=label, text=f"% positive scese da {num(old30['pct_positive'])} a {g['pct_positive']} in un mese: guarda le recensioni recenti."))
        pl = [num(r["players"]) for r in hist[:-1] if num(r["players"]) is not None]
        if g["players"] is not None and len(pl) >= 4 and g["players"] >= 3 * max(statistics.median(pl), 10):
            out["alerts"].append(dict(level="INFO", game=label, text=f"Giocatori contemporanei {g['players']:.0f}, oltre 3 volte la mediana storica ({statistics.median(pl):.0f})."))
        if launch and last["role"] == "competitor" and last["release_date"]:
            try:
                rd = D(last["release_date"])
                if abs((rd - launch).days) <= window:
                    out["alerts"].append(dict(level="ALARM", game=label, text=f"COLLISIONE CON LA TUA FINESTRA: esce il {last['release_date']}, a {abs((rd - launch).days)} giorni dal tuo lancio ({launch}). Valuta di spostare la data."))
            except ValueError:
                pass
        out["games"].append(g)
    return out


def to_md(o: dict) -> str:
    L = [f"# Watchlist al {o['today']}", "", "| Gioco | Ruolo | Recensioni | +7 giorni | +30 giorni | % positive | Giocatori | Sconto | Uscita |", "|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: "-" if v is None else f"{v:,.0f}".replace(",", ".")
    L += [f"| {g['name']} | {g['role']} | {f(g['reviews'])} | {f(g['gain_7d'])} | {f(g['gain_30d'])} | {g['pct_positive'] or '-'} | {f(g['players'])} | {int(g['discount'])}% | {g['release'] or '-'}{' (prossimamente)' if g['coming_soon'] else ''} |" for g in o["games"]]
    L += ["", "## Alert", ""] + ([f"- **{a['level']}** {a['game']}: {a['text']}" for a in sorted(o["alerts"], key=lambda a: ["ALARM", "ATTENZIONE", "INFO"].index(a["level"]))] or ["- Nessun alert."])
    L += ["", "_Dati pubblici di Steam. Le wishlist e le vendite degli altri giochi non sono pubbliche._"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=float, default=1.2)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("appids", nargs="+", type=int); s.add_argument("--role", default="comp", choices=["comp", "competitor", "self"]); s.add_argument("--csv", default="launch/watchlist.csv")
    s = sub.add_parser("snap"); s.add_argument("--csv", default="launch/watchlist.csv")
    s = sub.add_parser("report"); s.add_argument("--csv", default="launch/watchlist.csv"); s.add_argument("--launch"); s.add_argument("--window-days", type=int, default=30)
    s.add_argument("--viral-factor", type=float, default=3.0); s.add_argument("--today"); s.add_argument("--md"); s.add_argument("--json")
    a = ap.parse_args()
    set_rate(a.rate)
    today = dt.date.today().isoformat()
    if a.cmd == "add":
        snapshot(a.csv, [(i, a.role) for i in a.appids], today)
    elif a.cmd == "snap":
        rows = read(a.csv)
        if not rows:
            raise SystemExit(f"{a.csv} is empty: add games first (watchlist.py add APPID --role comp)")
        latest = {}
        for r in rows:
            latest[int(r["appid"])] = r["role"]
        snapshot(a.csv, sorted(latest.items()), today)
    else:
        o = analyse(read(a.csv), D(a.today) if a.today else dt.date.today(), D(a.launch) if a.launch else None, a.window_days, a.viral_factor)
        text = to_md(o)
        if a.md:
            with open(a.md, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            log(f"wrote {a.md}")
        else:
            print(text)
        if a.json:
            write_json(o, a.json)


if __name__ == "__main__":
    main()
