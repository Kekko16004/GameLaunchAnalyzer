#!/usr/bin/env python3
"""Competitor calendar for your launch window: which weeks are crowded, which are free, and how your date compares.

Reads, never fetches:
  launch/watchlist.csv   competitors you follow with watchlist.py (role `competitor`, release date from the store; coming soon)
  launch/window.csv      what you add by hand: big releases, festivals, sales, holidays, rivals seen on SteamDB "upcoming" or in the press
                         columns: date,name,kind,weight,source,note   (kind: competitor | big_release | festival | sale | holiday)
  Steam's own calendar   seasonal sales, Next Fest and themed fests from steam_events.py (user file, else its built-in fallback),
                         one row per week of each event, added automatically (--no-steam-events to leave them out); the same
                         rows written into window.csv by `steam_events.py export-window` are counted once
Public Steam data does not list every upcoming game, so a free week in this list is NOT a free week in the world: the tool
says what it counted and how many items had no usable date.

Crowding score of a week = sum of the weights of the items near it, discounted by distance (the week itself 1.0, one week away
0.5, two weeks away 0.25). Default weights (1-5): competitor 3, big_release 4, festival 3, sale 2, holiday 2 [OPINIONE: a
heuristic to compare weeks with each other, not a forecast of wishlists or sales]. It ranks the candidate weeks and tells where
your chosen date stands.

  launch_window.py add --date 2027-03-02 --name "Big Co. shooter" --kind big_release --weight 5 --source "steamdb upcoming, read 2026-10-07"
  launch_window.py plan --launch 2027-03-01 [--from 2027-01-15 --to 2027-05-31] [--md launch/window.md] [-o launch/_raw/window.json]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os

from common import log, write_json

D = dt.date.fromisoformat
FIELDS = ["date", "name", "kind", "weight", "source", "note"]
KINDS = {"competitor": 3, "big_release": 4, "festival": 3, "sale": 2, "holiday": 2}
LABEL = {"competitor": "rivale", "big_release": "grande uscita", "festival": "festival", "sale": "saldi", "holiday": "festività"}
DECAY = [(3, 1.0), (10, 0.5), (17, 0.25)]   # days from the week's midday (Thursday) -> factor


def read_window(path: str) -> tuple[list[dict], list[str]]:
    items, bad = [], []
    if not os.path.exists(path):
        return items, bad
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name, kind = (r.get("name") or "").strip(), (r.get("kind") or "competitor").strip().lower()
            try:
                day = D((r.get("date") or "").strip())
            except ValueError:
                bad.append(f"{name or '?'} (date '{r.get('date', '')}')")
                continue
            if kind not in KINDS:
                bad.append(f"{name} (kind '{kind}' unknown: {', '.join(KINDS)})")
                continue
            try:
                w = float(r.get("weight") or KINDS[kind])
            except ValueError:
                w = KINDS[kind]
            items.append(dict(date=day, name=name, kind=kind, weight=min(max(w, 0.5), 5.0), source=(r.get("source") or "").strip(), origin="window.csv"))
    return items, bad


def read_watchlist(path: str) -> tuple[list[dict], list[str]]:
    items, bad, last = [], [], {}
    if not os.path.exists(path):
        return items, bad
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("role") == "competitor" and (r.get("date") or "") >= (last.get(r.get("appid"), {}).get("date") or ""):
                last[r.get("appid")] = r
    for aid, r in last.items():
        try:
            day = D((r.get("release_date") or "").strip())
        except ValueError:
            bad.append(f"{r.get('name') or aid} (release date '{r.get('release_date', '')}')")
            continue
        items.append(dict(date=day, name=r.get("name") or str(aid), kind="competitor", weight=float(KINDS["competitor"]), source=f"watchlist.csv, app {aid}", origin="watchlist.csv"))
    return items, bad


def dedupe(items: list[dict]) -> list[dict]:
    """The same rival can be in watchlist.csv and in window.csv: count it once (same name and date), keeping the higher weight."""
    best: dict = {}
    for it in items:
        k = (it["name"].strip().lower(), it["date"])
        if k not in best or it["weight"] > best[k]["weight"]:
            best[k] = it
    return list(best.values())


def week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def factor(days: int) -> float:
    return next((f for lim, f in DECAY if days <= lim), 0.0)


def score_week(monday: dt.date, items: list[dict]) -> tuple[float, list[dict]]:
    mid = monday + dt.timedelta(days=3)
    near, total = [], 0.0
    for it in items:
        f = factor(abs((it["date"] - mid).days))
        if f:
            near.append(dict(name=it["name"], kind=it["kind"], date=it["date"].isoformat(), weight=it["weight"], factor=f, points=round(it["weight"] * f, 2)))
            total += it["weight"] * f
    near.sort(key=lambda n: (-n["points"], n["date"]))
    return round(total, 2), near


def analyse(items: list[dict], launch: dt.date, start: dt.date, end: dt.date) -> dict:
    weeks, m = [], week_start(start)
    while m <= end:
        s, near = score_week(m, items)
        weeks.append(dict(week=m.isoformat(), score=s, items=near, chosen=m == week_start(launch)))
        m += dt.timedelta(days=7)
    if not any(w["chosen"] for w in weeks):   # chosen week outside the range: score it anyway
        s, near = score_week(week_start(launch), items)
        weeks.append(dict(week=week_start(launch).isoformat(), score=s, items=near, chosen=True))
        weeks.sort(key=lambda w: w["week"])
    scores = sorted(w["score"] for w in weeks)
    ch = next(w for w in weeks if w["chosen"])
    below = sum(1 for s in scores if s < ch["score"])
    pct = round(100 * below / len(scores))     # share of candidate weeks that are quieter than yours
    verdict = "libera" if ch["score"] == 0 or pct <= 25 else "affollata" if pct >= 75 else "nella media"
    best = sorted(weeks, key=lambda w: (w["score"], w["week"]))[:5]
    for w in weeks:
        w["best"] = w in best[:3]
    return dict(launch=launch.isoformat(), range=[start.isoformat(), end.isoformat()], weeks=weeks, chosen=dict(week=ch["week"], score=ch["score"], quieter_weeks_pct=pct, verdict=verdict),
                best=[dict(week=w["week"], score=w["score"]) for w in best], counted=len(items))


def md(res: dict, bad: list[str], today: dt.date) -> str:
    ch = res["chosen"]
    L = ["# Calendario dei concorrenti per la finestra di lancio", "",
         f"Data scelta: **{res['launch']}** (settimana del {ch['week']}), valutata il {today.isoformat()}. Conteggiate **{res['counted']}** voci (rivali, grandi uscite, festival, saldi, festività) dalle liste `watchlist.csv` e `window.csv`"
         + (f", compresi i saldi e i fest ufficiali di Steam (`steam_events.py`, {res['steam_events']} righe settimanali; le stesse righe in `window.csv` contano una volta sola)." if res.get("steam_events") else "."), "",
         f"**Esito: settimana {ch['verdict']}** (punteggio {ch['score']}; il {ch['quieter_weeks_pct']}% delle settimane candidate è più tranquillo). "
         "Il punteggio confronta le settimane tra loro [OPINIONE]: non prevede wishlist o vendite, e vale solo per ciò che è in lista: una settimana libera qui non è libera nel mondo.", "",
         "## Le 5 settimane più tranquille", "", "| Settimana dal | Punteggio | Cosa c'è vicino |", "|---|---|---|"]
    byweek = {w["week"]: w for w in res["weeks"]}
    for b in res["best"]:
        near = ", ".join(f"{n['name']} ({LABEL[n['kind']]}, {n['date']})" for n in byweek[b["week"]]["items"][:3]) or "niente in lista"
        L.append(f"| {b['week']} | {b['score']} | {near} |")
    L += ["", "## Tutte le settimane", "", "| Settimana dal | Punteggio | Voci vicine |", "|---|---|---|"]
    for w in res["weeks"]:
        mark = " ◀ la tua" if w["chosen"] else (" ★" if w["best"] else "")
        L.append(f"| {w['week']}{mark} | {w['score']} | {', '.join(n['name'] for n in w['items'][:4]) or '-'} |")
    if byweek[ch["week"]]["items"]:
        L += ["", f"## Cosa pesa sulla tua settimana ({ch['week']})", ""] + [f"- {n['name']}: {LABEL[n['kind']]}, {n['date']}, peso {n['weight']:g} × {n['factor']} = {n['points']}" for n in byweek[ch["week"]]["items"]]
    L += ["", "## Come usarlo", "- Se la tua settimana è affollata, guarda le 5 più tranquille e controlla che non cadano nei giorni che ti servono (fine Next Fest, scadenze, ferie); poi riapri la decisione con `00-intenzioni.md`.",
          "- Un rivale diretto (stesso genere e pubblico) pesa più di un grande titolo di un altro genere: alza o abbassa il peso a mano in `window.csv` e motivalo nella colonna `note`.",
          "- Aggiorna la lista ogni due-tre settimane (`steamdb_assist.py links` indica dove guardare le uscite in arrivo)."]
    if bad:
        L += ["", "## Voci non conteggiate", ""] + [f"- {b}" for b in bad]
    return "\n".join(L) + "\n"


def cmd_add(a):
    try:
        D(a.date)
    except ValueError:
        raise SystemExit(f"--date '{a.date}' is not YYYY-MM-DD")
    rows = []
    if os.path.exists(a.csv):
        with open(a.csv, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    if any((r.get("date"), (r.get("name") or "").lower()) == (a.date, a.name.lower()) for r in rows):
        log(f"already listed: {a.name} on {a.date}")
        return
    new = not os.path.exists(a.csv)
    os.makedirs(os.path.dirname(os.path.abspath(a.csv)), exist_ok=True)
    with open(a.csv, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(dict(date=a.date, name=a.name, kind=a.kind, weight=a.weight if a.weight is not None else KINDS[a.kind], source=a.source, note=a.note))
    log(f"added {a.name} ({a.kind}) on {a.date} to {a.csv}")


def cmd_plan(a):
    today = D(a.today) if a.today else dt.date.today()
    launch = D(a.launch)
    start, end = D(a.start) if a.start else max(today, launch - dt.timedelta(days=56)), D(a.end) if a.end else launch + dt.timedelta(days=56)
    if end < start:
        raise SystemExit("--to is before --from")
    i1, b1 = read_watchlist(a.watchlist)
    i2, b2 = read_window(a.csv)
    i3 = []
    if not a.no_steam_events:      # Steam's own sales and fests (steam_events.py), always counted unless switched off
        try:
            import steam_events
            i3 = steam_events.window_items(a.steam_events)
        except Exception as e:  # noqa: BLE001
            log(f"WARN steam events not read: {e}")
    res = analyse(dedupe(i1 + i2 + i3), launch, start, end)
    res["steam_events"] = len(i3)
    res["not_counted"] = b1 + b2
    text = md(res, b1 + b2, today)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        open(a.md, "w", encoding="utf-8", newline="\n").write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if a.out:
        write_json(res, a.out)
    ch = res["chosen"]
    log(f"your week {ch['week']}: score {ch['score']} ({ch['verdict']}); quietest: {res['best'][0]['week']} ({res['best'][0]['score']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("--date", required=True); p.add_argument("--name", required=True); p.add_argument("--kind", choices=list(KINDS), default="competitor")
    p.add_argument("--weight", type=float); p.add_argument("--source", default=""); p.add_argument("--note", default=""); p.add_argument("--csv", default="launch/window.csv")
    p = sub.add_parser("plan"); p.add_argument("--launch", required=True); p.add_argument("--from", dest="start"); p.add_argument("--to", dest="end")
    p.add_argument("--watchlist", default="launch/watchlist.csv"); p.add_argument("--csv", default="launch/window.csv"); p.add_argument("--md"); p.add_argument("-o", "--out"); p.add_argument("--today")
    p.add_argument("--steam-events", help="steam_events.json (default: ~/.game-launch-strategist/steam_events.json, else the built-in fallback)")
    p.add_argument("--no-steam-events", action="store_true", help="do not add Steam's official sales and fests")
    a = ap.parse_args()
    (cmd_add if a.cmd == "add" else cmd_plan)(a)


if __name__ == "__main__":
    main()
