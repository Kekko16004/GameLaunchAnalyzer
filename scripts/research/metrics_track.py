#!/usr/bin/env python3
"""Metrics and "if... then" contingency plans: the game goes badly after one week on itch.io? the demo is
abandoned in two minutes? the Next Fest brings nothing? Decide BEFORE it happens what you will look at, when
it counts as a problem, what you check first and what you do.

Two files:
  launch/metrics.csv                  date,metric,value,note   (you type numbers from itch.io, Steamworks, Discord, TikTok...)
  launch/_raw/contingencies.json      the scenarios (written by the skill from benchmarks and your answers)
Wishlists are read automatically from launch/wishlists.csv (metrics `wishlists` and `followers`).

Scenario shape:
  {"scenarios": [{
     "id": "itch-week1-low", "area": "itch beta", "title": "First week on itch far below expectations",
     "start": "2026-11-10",                       # not evaluated before this date
     "when": "any",                               # any | all signals must hold
     "severity": "ATTENZIONE",                    # or ALARM (exit code 2)
     "signals": [{"metric": "itch_views", "kind": "gain", "days": 7, "op": "<", "value": 150, "label": "views in 7 days"},
                 {"metric": "itch_downloads", "kind": "ratio", "of": "itch_views", "op": "<", "value": 0.05, "label": "downloads / views"}],
     "diagnosis": ["traffic problem (nobody arrives) or page problem (they arrive and leave)?"],
     "actions": [{"text": "rewrite the cover and the first lines of the page", "owner": "both", "cost": "basso"}],
     "decision": "if after the actions the next 7 days are still below X, then...",
     "evidence": "where the threshold comes from (benchmark or opinion, with the reason)"}]}
Signal kinds: level (latest value), gain (latest minus the value `days` ago, for cumulative counters), avg (mean of the
last `days` days, for daily numbers), drop (% fall over `days`), ratio (latest metric / latest `of`). ops: < <= > >= ==.

  metrics_track.py add --metric itch_views --value 412 [--date D] [--note "..."]
  metrics_track.py status [--md launch/metrics-status.md] [--json out.json] [--today D]
  metrics_track.py check            validates contingencies.json against the metrics you record
  metrics_track.py catalog          the usual metric names and where each number comes from

Exit code 2 when a scenario with severity ALARM has triggered. Thresholds are OPINIONS unless `evidence` cites a benchmark.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import operator
import os
import statistics
import sys
from common import load_json, log, write_json

D = dt.date.fromisoformat
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge, "==": operator.eq}
CATALOG = {
    "wishlists": "Steamworks > Wishlist (total outstanding); also tracked by wl_track.py",
    "followers": "Steam page followers",
    "steam_page_visits": "Steamworks > Marketing & Visibility > visits (cumulative or per period: say which in the note)",
    "steam_impressions": "Steamworks > store traffic: impressions (use with visits for the capsule click rate)",
    "itch_views": "itch.io dashboard > Views (cumulative)", "itch_downloads": "itch.io dashboard > Downloads (cumulative)",
    "itch_browser_plays": "itch.io dashboard > Browser plays", "itch_ratings": "itch.io ratings count", "itch_comments": "itch.io comments count",
    "discord_members": "Discord server member count", "tiktok_followers": "TikTok followers", "youtube_subscribers": "YouTube subscribers",
    "demo_players": "Steamworks demo: unique players", "demo_median_playtime_min": "Steamworks demo: median playtime in minutes",
    "demo_to_wishlist_pct": "wishlists gained from demo players, percent", "reviews_total": "Steam reviews", "reviews_pct_positive": "Steam % positive",
    "refund_rate_pct": "Steamworks sales report: refund rate", "units_sold": "Steamworks sales report: units", "players_now": "Steamworks or SteamDB: concurrent players",
    "tester_count": "real test (Gate B): testers who completed a session", "second_session_pct": "real test: share that started a second session by themselves",
    "avg_session_min": "real test: average session length in minutes",
}


def read_metrics(path: str, wishlists_csv: str | None) -> list[dict]:
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    rows.append(dict(date=r["date"], metric=r["metric"].strip(), value=float(r["value"]), note=r.get("note", "")))
                except (KeyError, ValueError):
                    continue
    if wishlists_csv and os.path.exists(wishlists_csv):
        with open(wishlists_csv, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("wishlists") or "").strip().lstrip("-").isdigit():
                    rows.append(dict(date=r["date"], metric="wishlists", value=float(r["wishlists"]), note=r.get("note", "")))
                if (r.get("followers") or "").strip().isdigit():
                    rows.append(dict(date=r["date"], metric="followers", value=float(r["followers"]), note=""))
    return sorted(rows, key=lambda r: (r["metric"], r["date"]))


def series(rows: list[dict], metric: str, today: dt.date) -> list[tuple[dt.date, float]]:
    by = {}
    for r in rows:
        if r["metric"] == metric and D(r["date"]) <= today:
            by[r["date"]] = r["value"]  # last row of the day wins
    return [(D(k), v) for k, v in sorted(by.items())]


def value_ago(s: list[tuple[dt.date, float]], today: dt.date, days: int):
    """Value at the record on or before today-days; if none, the first record when it is at least 60% of the window old."""
    cutoff = today - dt.timedelta(days=days)
    before = [p for p in s if p[0] <= cutoff]
    if before:
        return before[-1]
    return s[0] if s and (s[-1][0] - s[0][0]).days >= 0.6 * days and s[0][0] < s[-1][0] else None


def measure(sig: dict, rows: list[dict], today: dt.date):
    """(value or None, explanation)"""
    kind, m = sig.get("kind", "level"), sig["metric"]
    s = series(rows, m, today)
    if not s:
        return None, f"nessun dato per `{m}`"
    last = s[-1]
    if kind == "level":
        return last[1], f"{m} = {last[1]:g} ({last[0]})"
    if kind == "ratio":
        o = series(rows, sig["of"], today)
        if not o or not o[-1][1]:
            return None, f"nessun dato per `{sig['of']}`"
        return last[1] / o[-1][1], f"{m} / {sig['of']} = {last[1]:g} / {o[-1][1]:g}"
    days = int(sig.get("days", 7))
    if kind == "avg":
        w = [v for d, v in s if d > today - dt.timedelta(days=days)]
        return (statistics.mean(w), f"media di {m} negli ultimi {days} giorni ({len(w)} rilevazioni)") if w else (None, f"nessuna rilevazione di `{m}` negli ultimi {days} giorni")
    old = value_ago(s, today, days)
    if not old:
        return None, f"dati di `{m}` insufficienti per una finestra di {days} giorni"
    if kind == "gain":
        return last[1] - old[1], f"{m}: {old[1]:g} ({old[0]}) -> {last[1]:g} ({last[0]}), +{last[1] - old[1]:g}"
    if kind == "drop":
        return (100 * (old[1] - last[1]) / old[1], f"{m}: {old[1]:g} -> {last[1]:g}") if old[1] else (None, f"`{m}` era zero")
    return None, f"kind sconosciuto: {kind}"


def evaluate(cont: dict, rows: list[dict], today: dt.date) -> list[dict]:
    out = []
    for sc in cont.get("scenarios", []):
        r = dict(sc, status="", signals_eval=[])
        if sc.get("start") and today < D(sc["start"]):
            r["status"] = "NON ANCORA"
            out.append(r)
            continue
        results = []
        for sig in sc.get("signals", []):
            v, why = measure(sig, rows, today)
            ok = None if v is None else OPS[sig["op"]](v, sig["value"])
            results.append(ok)
            r["signals_eval"].append(dict(label=sig.get("label") or sig["metric"], op=sig["op"], threshold=sig["value"], value=None if v is None else round(v, 3), holds=ok, detail=why))
        if sc.get("when", "any") == "all":
            r["status"] = "SCATTATO" if results and all(x is True for x in results) else "SENZA DATI" if any(x is None for x in results) and not any(x is False for x in results) else "OK"
        else:
            r["status"] = "SCATTATO" if any(x is True for x in results) else "SENZA DATI" if results and all(x is None for x in results) else "OK"
        out.append(r)
    return out


def to_md(res: list[dict], today: dt.date) -> str:
    L = [f"# Stato delle contingenze al {today.isoformat()}", ""]
    trig = [r for r in res if r["status"] == "SCATTATO"]
    L += [f"**{len(trig)} scenari scattati**, {sum(r['status'] == 'OK' for r in res)} ok, {sum(r['status'] == 'SENZA DATI' for r in res)} senza dati, {sum(r['status'] == 'NON ANCORA' for r in res)} non ancora attivi.", ""]
    for r in sorted(res, key=lambda r: (["SCATTATO", "SENZA DATI", "OK", "NON ANCORA"].index(r["status"]), r.get("area", ""))):
        L += [f"## {r['status']} · {r.get('area', '')} · {r['title']} ({r.get('severity', 'ATTENZIONE')})", ""]
        for s in r["signals_eval"]:
            L.append(f"- {'SÌ' if s['holds'] else 'no' if s['holds'] is False else '?'} {s['label']} {s['op']} {s['threshold']}: {s['detail']}")
        if r["status"] == "SCATTATO":
            if r.get("diagnosis"):
                L += ["", "Prima controlla:"] + [f"{i}. {d}" for i, d in enumerate(r["diagnosis"], 1)]
            if r.get("actions"):
                L += ["", "Azioni, dalla più economica:"] + [f"- {a['text']} ({a.get('owner', '')}, costo {a.get('cost', '?')})" for a in r["actions"]]
            if r.get("decision"):
                L += ["", f"Decisione: {r['decision']}"]
        if r.get("evidence"):
            L += ["", f"_Origine della soglia: {r['evidence']}_"]
        L.append("")
    return "\n".join(L)


def check(cont: dict, rows: list[dict]) -> list[str]:
    p, have = [], {r["metric"] for r in rows}
    ids = [s.get("id") for s in cont.get("scenarios", [])]
    if not ids:
        return ["no scenarios"]
    if len(set(ids)) != len(ids):
        p.append("duplicated scenario ids")
    for sc in cont["scenarios"]:
        for k in ("id", "title", "signals", "actions"):
            if not sc.get(k):
                p.append(f"{sc.get('id', '?')}: missing '{k}'")
        if not sc.get("evidence"):
            p.append(f"{sc.get('id')}: no 'evidence' (say whether the threshold comes from a benchmark or is an opinion, and why)")
        for s in sc.get("signals", []):
            if s.get("op") not in OPS:
                p.append(f"{sc.get('id')}: bad op {s.get('op')!r}")
            if s.get("kind", "level") in ("gain", "avg", "drop") and not s.get("days"):
                p.append(f"{sc.get('id')}: signal on {s.get('metric')} needs 'days'")
            if s.get("kind") == "ratio" and not s.get("of"):
                p.append(f"{sc.get('id')}: ratio signal needs 'of'")
            if s.get("metric") not in CATALOG and s.get("metric") not in have:
                p.append(f"{sc.get('id')}: metric '{s.get('metric')}' is not in the catalog nor recorded (typo?)")
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="launch/metrics.csv"); ap.add_argument("--wishlists-csv", default="launch/wishlists.csv")
    ap.add_argument("--contingencies", default="launch/_raw/contingencies.json"); ap.add_argument("--today")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("--metric", required=True); s.add_argument("--value", type=float, required=True); s.add_argument("--date"); s.add_argument("--note", default="")
    s = sub.add_parser("status"); s.add_argument("--md"); s.add_argument("--json")
    sub.add_parser("check"); sub.add_parser("catalog")
    a = ap.parse_args()
    today = D(a.today) if a.today else dt.date.today()
    if a.cmd == "catalog":
        print("\n".join(f"{k:26} {v}" for k, v in CATALOG.items()))
        return
    if a.cmd == "add":
        day = a.date or today.isoformat()
        D(day)
        rows = []
        if os.path.exists(a.csv):
            with open(a.csv, encoding="utf-8-sig", newline="") as f:
                rows = [r for r in csv.DictReader(f) if not (r["date"] == day and r["metric"] == a.metric)]
        rows.append(dict(date=day, metric=a.metric, value=f"{a.value:g}", note=a.note))
        os.makedirs(os.path.dirname(os.path.abspath(a.csv)), exist_ok=True)
        with open(a.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "metric", "value", "note"])
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: (r["date"], r["metric"])))
        if a.metric not in CATALOG:
            log(f"note: '{a.metric}' is not in the catalog (fine for custom metrics; `catalog` lists the usual ones)")
        log(f"recorded {day} {a.metric} = {a.value:g}")
        return
    rows = read_metrics(a.csv, a.wishlists_csv)
    if not os.path.exists(a.contingencies):
        raise SystemExit(f"{a.contingencies} not found: the skill writes it in phase 7C")
    cont = load_json(a.contingencies)
    if a.cmd == "check":
        pr = check(cont, rows)
        print("\n".join(pr) if pr else f"OK: {len(cont['scenarios'])} scenarios")
        sys.exit(1 if pr else 0)
    res = evaluate(cont, rows, today)
    text = to_md(res, today)
    if a.md:
        open(a.md, "w", encoding="utf-8", newline="\n").write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if a.json:
        write_json(dict(today=today.isoformat(), scenarios=res), a.json)
    if any(r["status"] == "SCATTATO" and r.get("severity") == "ALARM" for r in res):
        sys.exit(2)


if __name__ == "__main__":
    main()
