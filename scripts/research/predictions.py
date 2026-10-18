#!/usr/bin/env python3
"""Predictions log: what the skill predicted, and what really happened. The self-correcting loop of the skill.

Every wave of the focus group and every estimate records its prediction in launch/predictions.json (date, source, metric,
value or range, label SIMULATO / [STIMA], the real metric that will check it). When real data arrives (metrics.csv from
metrics_track.py, wishlists.csv from wl_track.py, the real testers' answers recorded as metrics), `eval` puts prediction
and reality side by side and computes the accuracy over time. STATUS.html shows it.

  predictions.py sync  [--launch-dir launch]     record predictions from the waves (fg/timeline.csv), the economic plan
                                                 (_raw/econ.json, wishlist scenarios) and the real-market calibration
  predictions.py add   --metric copies_90d --low 500 --high 1500 --source "stima manuale" [--label STIMA] [--due 2027-07-01]
                       [--actual-metric copies_90d] [--subject "Buffet Panic EA"]
  predictions.py eval  [--json out.json]          prediction vs reality, hits, accuracy

Real metrics that close predictions (record them with metrics_track.py add --metric NAME --value V):
  real_wishlist_pct   share of REAL testers who would wishlist (the test form), closes the waves' wishlist_pct (SIMULATO)
  real_buy_pct        share of real testers who would pay the price, closes the waves' buy share
  wishlists           Steamworks total (wishlists.csv), closes the wishlist scenarios at the launch date
  copies_30d / copies_90d / copies_year1   copies sold (Steamworks), close the sales ranges
A hit = the real value inside the predicted range (point predictions: within 10 % of the value, or 10 points for shares).
Recording never overwrites: a prediction keeps its id; `sync` only adds what is new.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os

from common import log, user_dir

LABELS = {"SIMULATO": "SIMULATO", "STIMA": "[STIMA]", "FATTO": "[FATTO]"}


def path_of(root: str) -> str:
    return os.path.join(root, "predictions.json")


def load(root: str) -> dict:
    p = path_of(root)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return dict(updated=None, items=[])


def save(root: str, d: dict, today: dt.date):
    d["updated"] = today.isoformat()
    with open(path_of(root), "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def put(d: dict, item: dict) -> bool:
    if any(x["id"] == item["id"] for x in d["items"]):
        return False
    d["items"].append(item)
    return True


def _f(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def sync(root: str, today: dt.date, cal_path: str | None = None) -> int:
    d, n = load(root), 0
    tl = os.path.join(root, "fg", "timeline.csv")
    if os.path.exists(tl):
        with open(tl, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                w, stage = r.get("wave"), (r.get("stage") or "beta").strip() or "beta"
                if stage == "full":
                    continue   # the full game is not what the real test measures
                for m, actual in (("wishlist_pct", "real_wishlist_pct"), ("buy_pct", "real_buy_pct")):
                    v = _f(r.get(m))
                    if v is not None:
                        n += put(d, dict(id=f"wave{w}-{m}", date=r.get("date"), source=f"Ondata {w} del focus group ({stage})", metric=m, value=v, low=None, high=None,
                                         unit="%", label="SIMULATO", subject="beta", actual_metric=actual, due=None))
    ep = os.path.join(root, "_raw", "econ.json")
    if os.path.exists(ep):
        with open(ep, encoding="utf-8") as f:
            e = json.load(f)
        sc = e.get("scenarios") or []
        wl_plan = os.path.join(root, "_raw", "wl_plan.json")
        due = None
        if os.path.exists(wl_plan):
            with open(wl_plan, encoding="utf-8") as f:
                due = json.load(f).get("launch")
        if len(sc) >= 2:
            n += put(d, dict(id=f"econ-wishlists-{today.isoformat()[:7]}", date=today.isoformat(), source="Piano economico (calc_econ.py), scenari", metric="wishlists",
                             value=None, low=min(s["wishlists"] for s in sc), high=max(s["wishlists"] for s in sc), unit="wishlist", label="STIMA", subject="al lancio",
                             actual_metric="wishlists", due=due))
            n += put(d, dict(id=f"econ-copies-{today.isoformat()[:7]}", date=today.isoformat(), source="Piano economico (calc_econ.py), scenari", metric="copies_year1",
                             value=None, low=min(s["copies"] for s in sc), high=max(s["copies"] for s in sc), unit="copie", label="STIMA", subject="anno 1",
                             actual_metric="copies_year1", due=None))
        cb = e.get("calibrated")
        if cb:
            med = next((x for x in cb["scenarios"] if x["name"].startswith("base")), None)
            if med:
                n += put(d, dict(id=f"calib-copies90-{cb.get('generated_on')}", date=today.isoformat(), source=f"Base rate reale ({cb['group']}, n = {cb['n']}, dati {cb.get('data_from')}..{cb.get('data_to')})",
                                 metric="copies_90d", value=None, low=med["copies_low"], high=med["copies_high"], unit="copie", label="STIMA", subject="mediana della fascia, 3 mesi",
                                 actual_metric="copies_90d", due=None))
    for fn, subject in (("metro.json", "pagina com'è oggi"), ("metro-piano.json", "con il piano rispettato")):
        mp = os.path.join(root, "_raw", fn)
        if os.path.exists(mp):
            with open(mp, encoding="utf-8") as f:
                m = json.load(f)
            sc, meta = m.get("score") or {}, m.get("metro") or {}
            band = sc.get("band")
            if band:
                lo, hi = {"<100": (0, 100), "100-1k": (100, 1000), "1k-10k": (1000, 10000), ">10k": (10000, 10 ** 7)}[band]
                n += put(d, dict(id=f"metro-{fn[:-5]}-{meta.get('fitted_on')}", date=today.isoformat(), source=f"Metro oggettivo ({meta.get('strength')}, n = {meta.get('n')}, {meta.get('fitted_on')})",
                                 metric=f"copies_{(meta.get('target') or 'y30')[1:]}d", value=None, low=lo, high=hi, unit="copie", label="STIMA", subject=f"fascia più probabile, {subject}",
                                 actual_metric=f"copies_{(meta.get('target') or 'y30')[1:]}d", due=None, p1k=sc.get("p1k")))
    if n:
        save(root, d, today)
    return n


def actuals(root: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    mp = os.path.join(root, "metrics.csv")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                v = _f(r.get("value"))
                if v is not None and r.get("metric"):
                    out.setdefault(r["metric"], []).append((r.get("date") or "", v))
    wp = os.path.join(root, "wishlists.csv")
    if os.path.exists(wp):
        with open(wp, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                v = _f(r.get("wishlists"))
                if v is not None:
                    out.setdefault("wishlists", []).append((r.get("date") or "", v))
    for k in out:
        out[k].sort()
    return out


def evaluate(root: str, today: dt.date) -> dict:
    d, act = load(root), actuals(root)
    rows = []
    for p in d["items"]:
        series = act.get(p.get("actual_metric") or "", [])
        pick = [x for x in series if not p.get("due") or x[0] >= p["due"]] if series else []
        if p.get("due") and not pick and p["due"] > today.isoformat():
            rows.append(dict(p, status="in attesa", actual=None, actual_date=None, hit=None))
            continue
        if not pick:
            rows.append(dict(p, status="manca il dato reale", actual=None, actual_date=None, hit=None))
            continue
        ad, av = pick[0] if p.get("due") else pick[-1]
        lo, hi = p.get("low"), p.get("high")
        if lo is None or hi is None:
            v = p["value"]
            tol = 10 if p.get("unit") == "%" else abs(v) * 0.10
            lo, hi = v - tol, v + tol
        mid = (lo + hi) / 2
        rows.append(dict(p, status="verificata", actual=av, actual_date=ad, hit=lo <= av <= hi, error=round(av - mid, 1),
                         direction="ottimista" if av < lo else ("pessimista" if av > hi else "giusta")))
    ev = [r for r in rows if r["status"] == "verificata"]
    by_date = []
    for i in range(len(ev)):
        part = sorted(ev, key=lambda r: r["actual_date"])[: i + 1]
        by_date.append(dict(date=part[-1]["actual_date"], accuracy=round(100 * sum(r["hit"] for r in part) / len(part), 1), n=len(part)))
    return dict(rows=rows, n=len(rows), evaluated=len(ev), hits=sum(1 for r in ev if r["hit"]),
                accuracy=round(100 * sum(1 for r in ev if r["hit"]) / len(ev), 1) if ev else None,
                optimistic=sum(1 for r in ev if r["direction"] == "ottimista"), over_time=by_date)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("--today")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("sync")
    a_ = sp.add_parser("add")
    for k in ("metric", "source", "subject", "due", "actual_metric", "unit", "note"):
        a_.add_argument("--" + k.replace("_", "-"), dest=k)
    a_.add_argument("--value", type=float); a_.add_argument("--low", type=float); a_.add_argument("--high", type=float)
    a_.add_argument("--label", default="STIMA", choices=list(LABELS)); a_.add_argument("--id")
    e = sp.add_parser("eval"); e.add_argument("--json")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    root = a.launch_dir
    if a.cmd == "sync":
        print(f"{sync(root, today)} previsioni nuove registrate in {path_of(root)}")
    elif a.cmd == "add":
        if a.value is None and (a.low is None or a.high is None):
            raise SystemExit("give --value or --low and --high")
        d = load(root)
        pid = a.id or f"{a.metric}-{today.isoformat()}-{len(d['items']) + 1}"
        ok = put(d, dict(id=pid, date=today.isoformat(), source=a.source or "manuale", metric=a.metric, value=a.value, low=a.low, high=a.high, unit=a.unit or "",
                         label=a.label, subject=a.subject or "", actual_metric=a.actual_metric or a.metric, due=a.due, note=a.note or ""))
        save(root, d, today)
        print(("registrata " if ok else "già presente ") + pid)
    else:
        r = evaluate(root, today)
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False, indent=1)
        print(f"{r['n']} previsioni, {r['evaluated']} verificate con dati reali, {r['hits']} giuste" + (f" ({r['accuracy']} %)" if r["accuracy"] is not None else ""))
        for x in r["rows"]:
            rng = f"{x['low']:g}-{x['high']:g}" if x.get("low") is not None else f"{x['value']:g}"
            print(f"  {x['date']}  {x['metric']:<16} {rng:>14} {x['unit']:<8} {x['label']:<9} -> {x['status']}" + (f": reale {x['actual']:g} ({'giusta' if x['hit'] else x['direction']})" if x.get("actual") is not None else ""))


if __name__ == "__main__":
    main()
