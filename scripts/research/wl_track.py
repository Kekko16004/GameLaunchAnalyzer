#!/usr/bin/env python3
"""Wishlist tracker: record the Steamworks wishlist total once a week, compare it with the plan and raise alarms.

Steam does not publish wishlists, so you type them: Steamworks > your app > Wishlist reports (total outstanding
wishlists). The tool keeps one row per date in a CSV, compares it with the scenario targets from calc_econ.py and
with the pre-mortem tripwires, and tells you when an alarm has fired.

  wl_track.py add --wishlists 1840 [--date 2026-10-06] [--followers 310] [--note "Reddit post"] [--csv launch/wishlists.csv]
  wl_track.py plan --launch 2027-03-01 --start 2026-10-01 --econ launch/_raw/econ.json \\
        --tripwire "2026-12-01:1500:8 weeks after the page:cut paid ads, rework capsule" \\
        --event "2026-11-17:Next Fest" -o launch/_raw/wl_plan.json
  wl_track.py status [--csv ...] [--plan ...] [--today D] [--md launch/wishlist-status.md] [--json out.json]

Exit code 2 when at least one ALARM is active (so a script or the skill can react). Targets are interpolated
linearly from the first record to the scenario value at launch: a simplification [OPINIONE], real curves are
spiky (festivals, press, launch week), so read "on pace" as a direction, not a forecast.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import statistics
import sys
from common import load_json, log, write_json

FIELDS = ["date", "wishlists", "followers", "note"]
D = dt.date.fromisoformat


def read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = {}
        for r in csv.DictReader(f):
            if r.get("date") and (r.get("wishlists") or "").strip().lstrip("-").isdigit():
                rows[r["date"]] = dict(date=r["date"], wishlists=int(r["wishlists"]),
                                       followers=int(r["followers"]) if (r.get("followers") or "").strip().isdigit() else None,
                                       note=(r.get("note") or "").strip())
    return [rows[k] for k in sorted(rows)]


def write_rows(path: str, rows: list[dict]):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows({k: ("" if r.get(k) is None else r[k]) for k in FIELDS} for r in rows)


def at(rows: list[dict], day: dt.date):
    """Wishlists on `day` by linear interpolation between records; None outside the recorded range."""
    pts = [(D(r["date"]), r["wishlists"]) for r in rows]
    if not pts or day < pts[0][0] or day > pts[-1][0]:
        return None
    for (d0, v0), (d1, v1) in zip(pts, pts[1:] + [pts[-1]]):
        if d0 <= day <= d1:
            return v0 if d1 == d0 else v0 + (v1 - v0) * (day - d0).days / (d1 - d0).days
    return None


def velocity(rows: list[dict], days: int):
    """Wishlists per week over the last `days`, from the first record inside that window (interpolated)."""
    if len(rows) < 2:
        return None
    end = D(rows[-1]["date"])
    start = max(end - dt.timedelta(days=days), D(rows[0]["date"]))
    v0, span = at(rows, start), (end - start).days
    return None if v0 is None or span <= 0 else (rows[-1]["wishlists"] - v0) / span * 7


def spark(vals):
    return "".join("▁▂▃▄▅▆▇█"[0 if max(vals) == min(vals) else int((v - min(vals)) / (max(vals) - min(vals)) * 7)] for v in vals) if vals else ""


def cmd_add(a):
    day = a.date or dt.date.today().isoformat()
    D(day)
    rows = read_rows(a.csv)
    old = next((r for r in rows if r["date"] == day), None)
    if old:
        log(f"WARN {day} already recorded ({old['wishlists']}): replaced with {a.wishlists}")
        rows.remove(old)
    prev = [r for r in rows if r["date"] < day]
    if prev and a.wishlists < 0.95 * prev[-1]["wishlists"]:
        log(f"WARN wishlists dropped {100 * (1 - a.wishlists / prev[-1]['wishlists']):.0f}% since {prev[-1]['date']}: check the number (deletions/purchases are normal, typos are not)")
    rows.append(dict(date=day, wishlists=a.wishlists, followers=a.followers, note=a.note or ""))
    rows.sort(key=lambda r: r["date"])
    write_rows(a.csv, rows)
    log(f"recorded {day}: {a.wishlists} wishlists ({len(rows)} records) -> {a.csv}")


def cmd_plan(a):
    plan = dict(start=a.start, launch=a.launch, targets={}, tripwires=[], events=[])
    if a.econ:
        for s in load_json(a.econ).get("scenarios", []):
            plan["targets"][s["name"]] = s["wishlists"]
    for t in a.target or []:
        name, _, v = t.partition("=")
        plan["targets"][name] = int(v)
    for t in a.tripwire or []:
        date, minimum, label, *emerg = t.split(":", 3)
        plan["tripwires"].append(dict(date=date, min_wishlists=int(minimum), label=label, emergency=(emerg[0] if emerg else "")))
    for e in a.event or []:
        date, _, label = e.partition(":")
        plan["events"].append(dict(date=date, label=label))
    if not plan["targets"]:
        log("WARN no scenario targets: give --econ (calc_econ.py output) or --target name=wishlists")
    write_json(plan, a.out)


def analyse(rows: list[dict], plan: dict | None, today: dt.date) -> dict:
    out = dict(today=today.isoformat(), records=len(rows), alerts=[], tripwires=[], scenarios=[], series=[dict(date=r["date"], wishlists=r["wishlists"]) for r in rows])
    if not rows:
        out["alerts"].append(dict(level="INFO", text="Nessun dato: registra il totale wishlist con `wl_track.py add`."))
        return out
    last, last_d = rows[-1], D(rows[-1]["date"])
    v1, v4 = velocity(rows, 7), velocity(rows, 28)
    out.update(current=last["wishlists"], last_record=last["date"], velocity_1w=v1 and round(v1, 1), velocity_4w=v4 and round(v4, 1),
               followers=last.get("followers"), spark=spark([r["wishlists"] for r in rows]))
    stale = (today - last_d).days
    if stale > 10:
        out["alerts"].append(dict(level="ATTENZIONE", text=f"Ultimo dato di {stale} giorni fa ({last['date']}): aggiorna prima di fidarti dei confronti."))
    if len(rows) >= 3 and rows[-1]["wishlists"] < rows[-2]["wishlists"] < rows[-3]["wishlists"]:
        out["alerts"].append(dict(level="ATTENZIONE", text="Le wishlist calano da due rilevazioni consecutive."))
    if v1 is not None and v4 and v4 > 0 and v1 < 0.25 * v4:
        out["alerts"].append(dict(level="ATTENZIONE", text=f"Rallentamento: {v1:.0f}/settimana nell'ultima settimana contro {v4:.0f}/settimana nelle ultime 4."))
    steps = [rows[i + 1]["wishlists"] - rows[i]["wishlists"] for i in range(len(rows) - 1)]
    if len(steps) >= 4:
        med = statistics.median(s for s in steps if s > 0) if any(s > 0 for s in steps) else 0
        for i, s in enumerate(steps):
            if med and s > 3 * med:
                out["alerts"].append(dict(level="INFO", text=f"Picco di +{s} wishlist fino al {rows[i + 1]['date']}" + (f" (nota: {rows[i + 1]['note']})" if rows[i + 1]["note"] else " (senza nota: annota cosa è successo)")))
    if not plan:
        return out
    launch = D(plan["launch"])
    weeks_left = max((launch - today).days, 0) / 7
    out.update(launch=plan["launch"], days_to_launch=(launch - today).days)
    start = D(plan.get("start") or rows[0]["date"])
    start_wl = (at(rows, start) if at(rows, start) is not None else rows[0]["wishlists"])
    for name, target in plan.get("targets", {}).items():
        span = max((launch - start).days, 1)
        expected = start_wl + (target - start_wl) * min(max((today - start).days, 0) / span, 1)
        need = (target - last["wishlists"]) / weeks_left if weeks_left > 0 else None
        out["scenarios"].append(dict(name=name, target=target, expected_today=round(expected), ratio=round(last["wishlists"] / expected, 2) if expected else None,
                                     needed_per_week=need and round(need), projected_at_launch=round(last["wishlists"] + v4 * weeks_left) if v4 is not None else None))
    if out["scenarios"]:
        ordered = sorted(out["scenarios"], key=lambda s: s["target"])
        below = [s for s in ordered if last["wishlists"] < s["expected_today"]]
        out["pace"] = ("sotto il percorso dello scenario più basso" if len(below) == len(ordered) else
                       "sopra il percorso dello scenario più alto" if not below else
                       f"tra '{ordered[len(below) - 1]['name']}' e '{ordered[len(below)]['name']}'" if below else "")
        if len(below) == len(ordered):
            out["alerts"].append(dict(level="ATTENZIONE", text=f"Sei {out['pace']} ({ordered[0]['name']}: attese {ordered[0]['expected_today']} oggi, hai {last['wishlists']})."))
    for t in plan.get("tripwires", []):
        d = D(t["date"])
        row = dict(t, status="", value=None)
        if d > today:
            row["status"] = "IN ATTESA"
            row["needed_per_week"] = round((t["min_wishlists"] - last["wishlists"]) / max((d - today).days / 7, 0.1))
        else:
            v = at(rows, d)
            if v is None:
                row["status"] = "SENZA DATI"
                out["alerts"].append(dict(level="ATTENZIONE", text=f"Tripwire '{t['label']}' del {t['date']}: nessun dato registrato in quella data, non valutabile."))
            else:
                row.update(value=round(v), status="ALLARME" if v < t["min_wishlists"] else "OK")
                if row["status"] == "ALLARME":
                    out["alerts"].append(dict(level="ALARM", text=f"TRIPWIRE '{t['label']}' ({t['date']}): {round(v)} wishlist, soglia {t['min_wishlists']}." + (f" Azione di emergenza: {t['emergency']}" if t.get("emergency") else "")))
        out["tripwires"].append(row)
    out["events"] = plan.get("events", [])
    return out


def to_md(o: dict) -> str:
    L = [f"# Stato wishlist al {o['today']}", ""]
    if "current" not in o:
        return "\n".join(L + [a["text"] for a in o["alerts"]]) + "\n"
    L += [f"**{o['current']} wishlist** (ultimo dato {o['last_record']}, {o['records']} rilevazioni) `{o['spark']}`",
          f"Velocità: ultima settimana {o['velocity_1w']}/sett., ultime 4 settimane {o['velocity_4w']}/sett." + (f" | follower {o['followers']}" if o.get("followers") else "")]
    if "launch" in o:
        L.append(f"Lancio: {o['launch']} (tra {o['days_to_launch']} giorni). Posizione: **{o.get('pace', 'n/d')}**.")
    L += ["", "## Alert", ""] + ([f"- **{a['level']}**: {a['text']}" for a in sorted(o["alerts"], key=lambda a: ["ALARM", "ATTENZIONE", "INFO"].index(a["level"]))] or ["- Nessun alert."])
    if o["scenarios"]:
        L += ["", "## Scenari", "", "| Scenario | Obiettivo al lancio | Atteso oggi | Tu / atteso | Servono a settimana | Proiezione a velocità attuale |", "|---|---|---|---|---|---|"]
        L += [f"| {s['name']} | {s['target']} | {s['expected_today']} | {s['ratio']} | {s['needed_per_week']} | {s['projected_at_launch']} |" for s in o["scenarios"]]
    if o["tripwires"]:
        L += ["", "## Tripwire del pre-mortem", "", "| Data | Segnale | Soglia | Valore | Stato |", "|---|---|---|---|---|"]
        L += [f"| {t['date']} | {t['label']} | {t['min_wishlists']} | {t['value'] if t['value'] is not None else '-'} | {t['status']}" + (f" (servono {t['needed_per_week']}/sett.)" if t.get("needed_per_week") else "") + " |" for t in o["tripwires"]]
    L += ["", "_Wishlist inserite a mano da Steamworks. Percorso lineare e proiezione sono semplificazioni [OPINIONE]; festival, stampa e lancio fanno picchi._"]
    return "\n".join(L) + "\n"


def cmd_status(a):
    o = analyse(read_rows(a.csv), load_json(a.plan) if a.plan and os.path.exists(a.plan) else None, D(a.today) if a.today else dt.date.today())
    text = to_md(o)
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if a.json:
        write_json(o, a.json)
    if any(x["level"] == "ALARM" for x in o["alerts"]):
        sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add", help="record today's (or a given date's) wishlist total")
    s.add_argument("--wishlists", type=int, required=True); s.add_argument("--date"); s.add_argument("--followers", type=int)
    s.add_argument("--note", help="what happened that week (post, festival, press)"); s.add_argument("--csv", default="launch/wishlists.csv")
    s.set_defaults(fn=cmd_add)
    p = sub.add_parser("plan", help="create the plan: launch date, scenario targets, tripwires, events")
    p.add_argument("--launch", required=True); p.add_argument("--start", help="date the Steam page went live (default: first record)")
    p.add_argument("--econ", help="calc_econ.py JSON: scenario wishlists become the targets"); p.add_argument("--target", action="append", help="name=wishlists (repeatable)")
    p.add_argument("--tripwire", action="append", help='"DATE:MIN_WISHLISTS:label[:emergency action]" (repeatable)')
    p.add_argument("--event", action="append", help='"DATE:label" (repeatable)'); p.add_argument("-o", "--out", default="launch/_raw/wl_plan.json")
    p.set_defaults(fn=cmd_plan)
    t = sub.add_parser("status", help="compare the records with the plan and print alerts")
    t.add_argument("--csv", default="launch/wishlists.csv"); t.add_argument("--plan", default="launch/_raw/wl_plan.json")
    t.add_argument("--today", help="override today (YYYY-MM-DD)"); t.add_argument("--md"); t.add_argument("--json")
    t.set_defaults(fn=cmd_status)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
