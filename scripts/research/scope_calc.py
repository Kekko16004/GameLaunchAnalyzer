#!/usr/bin/env python3
"""Scope calculator for the idea review (references/10-revisione-gdd.md): how many hours the content of the GDD needs against the hours
the team really has, plus how long the comparables are played (real reviews already cached by review_corpus.py) and price per hour.

Input JSON (counts from the GDD, capacity from the owner):
  {"content": {"levels": 0, "enemies": 12, "bosses": 3, "items": 60, "characters": 2, "biomes": 3, "mechanics": 6, ...},
   "capacity": {"people": 1, "hours_per_week": 15, "weeks": 52},
   "target_hours": 6, "price_usd": 9.99,                       optional: hours of play promised, launch price
   "comps": [{"appid": 123, "name": "X", "price_usd": 14.99}]}  optional: playtime read from launch/_raw/corpus/<appid>_*.json

Rates (hours per unit, overhead %) are [OPINIONE] defaults in data/scope_rates.json; --rates mine.json overrides them (same names).
Every number of the output is [STIMA] except the comparables' playtime, which is [FATTO] (median playtime of the reviewers, Steam).

  scope_calc.py calc --input scope.json [--corpus-dir launch/_raw/corpus] [--rates r.json] [--json] [--md out.md]
  scope_calc.py rates            the default rates
  scope_calc.py self-test

Verdict on needed/available: < 1 ci sta · 1-1.5 stretto · >= 1.5 troppo (warning) · >= 3 fuori scala (strong warning).
The suggested `scope` score for the scorecard of gdd_review.py: 5 / 4 / 3 / 2 / 1 on the same bands.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile

try:
    import common  # noqa: F401  (side effect: UTF-8 stdout on a Windows console)
except ImportError:  # pragma: no cover
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
RATES = os.path.join(HERE, "data", "scope_rates.json")
WARN, STRONG = 1.5, 3.0


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_rates(path: str | None = None) -> dict:
    rates = read_json(RATES)
    if path:
        mine = read_json(path)
        for k, v in (mine.get("units") or {}).items():
            rates["units"][k] = v if isinstance(v, dict) else {"hours": float(v), "what": "(tuo)"}
        for k, v in (mine.get("overhead") or {}).items():
            rates["overhead"][k] = v if isinstance(v, dict) else {"pct": float(v), "what": "(tuo)"}
        for k in ("base_hours", "productive_share"):
            if k in mine:
                rates[k] = mine[k]
    return rates


def comp_playtime(appid, corpus_dir: str) -> dict | None:
    """Median total playtime of the reviewers of one game, from the review caches (negative and positive)."""
    hrs, n = [], 0
    for kind in ("negative", "positive"):
        p = os.path.join(corpus_dir, f"{appid}_{kind}.json")
        if not os.path.exists(p):
            continue
        try:
            revs = read_json(p)
        except (OSError, ValueError):
            continue
        for r in revs if isinstance(revs, list) else []:
            h = r.get("playtime_forever_h")
            if h is None:
                h = r.get("playtime_at_review_h")
            if isinstance(h, (int, float)):
                hrs.append(float(h))
        n += 1
    if not hrs:
        return None
    return dict(median_h=round(statistics.median(hrs), 1), reviews=len(hrs), files=n)


def verdict(ratio: float) -> tuple[str, int]:
    if ratio < 1:
        return "ci sta", 5
    if ratio < 1.25:
        return "stretto", 4
    if ratio < WARN:
        return "stretto", 3
    if ratio < STRONG:
        return "troppo", 2
    return "fuori scala", 1


def calc(inp: dict, rates: dict, corpus_dir: str = os.path.join("launch", "_raw", "corpus")) -> dict:
    units = rates["units"]
    rows, unknown = [], []
    for k, n in (inp.get("content") or {}).items():
        if not isinstance(n, (int, float)) or n <= 0:
            continue
        if k not in units:
            unknown.append(k)
            continue
        h = float(units[k]["hours"])
        rows.append(dict(item=k, count=n, hours_each=h, hours=round(n * h, 1), what=units[k].get("what", "")))
    content_h = sum(r["hours"] for r in rows) + float(rates.get("base_hours", {}).get("hours", 0))
    over = {k: round(content_h * float(v["pct"]) / 100, 1) for k, v in rates["overhead"].items()}
    needed = round(content_h + sum(over.values()), 1)
    cap = inp.get("capacity") or {}
    people, hpw, weeks = (float(cap[k]) if cap.get(k) is not None else None for k in ("people", "hours_per_week", "weeks"))
    share = float(rates.get("productive_share", 0.75))
    available = None if None in (people, hpw, weeks) else round(people * hpw * weeks * share, 1)
    ratio = round(needed / available, 2) if available else None
    word, score = verdict(ratio) if ratio is not None else ("nessuna ora disponibile" if available == 0 else "capacità non nota", None)
    weeks_needed = round(needed / (people * hpw * share), 1) if people and hpw and share else None

    comps = []
    for c in inp.get("comps") or []:
        c = c if isinstance(c, dict) else {"appid": c}
        pt = comp_playtime(c.get("appid"), corpus_dir)
        row = dict(appid=c.get("appid"), name=c.get("name") or str(c.get("appid")), price_usd=c.get("price_usd"),
                   median_h=pt["median_h"] if pt else None, reviews=pt["reviews"] if pt else 0)
        if row["median_h"] and isinstance(row["price_usd"], (int, float)):
            row["usd_per_hour"] = round(row["price_usd"] / row["median_h"], 2) if row["median_h"] else None
        comps.append(row)
    med = [c["median_h"] for c in comps if c["median_h"]]
    comps_median = round(statistics.median(med), 1) if med else None
    target, price = inp.get("target_hours"), inp.get("price_usd")
    notes = []
    if ratio is not None and ratio >= STRONG:
        notes.append(f"servono {ratio}x le ore disponibili: il GDD descrive un altro gioco rispetto a quello che la squadra può fare; taglia contenuti o allunga i tempi")
    elif ratio is not None and ratio >= WARN:
        notes.append(f"servono {ratio}x le ore disponibili: taglia prima i contenuti più cari (vedi la tabella) o riduci le quantità")
    if comps_median and isinstance(target, (int, float)):
        if target < comps_median * 0.5:
            notes.append(f"il gioco promette {target} h, i comparabili sono giocati {comps_median} h (mediana): rischio 'troppo corto' nelle recensioni")
        elif target > comps_median * 2:
            notes.append(f"il gioco promette {target} h, i comparabili {comps_median} h: forse puoi tagliare contenuti senza perdere valore")
    upr = round(price / target, 2) if isinstance(price, (int, float)) and isinstance(target, (int, float)) and target else None
    comp_upr = [c["usd_per_hour"] for c in comps if c.get("usd_per_hour")]
    if upr and comp_upr and upr > 2 * statistics.median(comp_upr):
        notes.append(f"{upr} $/ora contro {statistics.median(comp_upr)} dei comparabili: il prezzo pesa sulla durata (tema 'price_value_length')")
    return dict(rows=sorted(rows, key=lambda r: -r["hours"]), unknown=unknown, base_hours=rates.get("base_hours", {}).get("hours", 0),
                overhead=over, needed_h=needed, available_h=available, productive_share=share, ratio=ratio, verdict=word, scope_score=score,
                weeks_needed=weeks_needed, capacity=dict(people=people, hours_per_week=hpw, weeks=weeks),
                comps=comps, comps_median_h=comps_median, target_hours=target, price_usd=price, usd_per_hour=upr,
                usd_per_hour_comps=round(statistics.median(comp_upr), 2) if comp_upr else None, notes=notes,
                labels={"ore e rapporto": "[STIMA] da tariffe [OPINIONE] (data/scope_rates.json)", "durata comparabili": "[FATTO] recensioni Steam in cache"})


def to_md(r: dict) -> str:
    def value(x):
        return "n/d" if x is None else f"{x:g}"

    L = ["# Scope: ore necessarie contro ore disponibili", "",
         f"**{r['needed_h']} h necessarie contro {value(r['available_h'])} h disponibili: rapporto {value(r['ratio'])} → {r['verdict']}** [STIMA] "
         f"(tariffe [OPINIONE] di `data/scope_rates.json`; voto suggerito per l'area scope della pagella: {r['scope_score'] or '—'}/5).", "",
         f"Capacità: {value(r['capacity']['people'])} persone × {value(r['capacity']['hours_per_week'])} h/settimana × {value(r['capacity']['weeks'])} settimane × "
         f"{r['productive_share']:g} di ore produttive." + (f" Al ritmo attuale servirebbero {r['weeks_needed']} settimane." if r["weeks_needed"] else ""), "",
         "| Contenuto | Quantità | Ore l'una | Ore | Cosa comprende |", "|---|---|---|---|---|"]
    for x in r["rows"]:
        L.append(f"| {x['item']} | {x['count']:g} | {x['hours_each']:g} | {x['hours']:g} | {x['what']} |")
    L.append(f"| fondamenta | 1 | {r['base_hours']:g} | {r['base_hours']:g} | progetto, input, salvataggi, build |")
    for k, h in r["overhead"].items():
        L.append(f"| {k} | — | — | {h:g} | percentuale sul contenuto |")
    if r["unknown"]:
        L += ["", f"Voci senza tariffa (non contate): {', '.join(r['unknown'])}. Aggiungile con `--rates`."]
    if r["comps"]:
        L += ["", "## Quanto si giocano i comparabili [FATTO]", "", "| Gioco | Ore (mediana di chi recensisce) | Recensioni lette | Prezzo | $ per ora |", "|---|---|---|---|---|"]
        for c in r["comps"]:
            L.append(f"| {c['name']} | {c['median_h'] if c['median_h'] is not None else 'nessuna cache'} | {c['reviews']} | {c['price_usd'] or '—'} | {c.get('usd_per_hour') or '—'} |")
        L.append("")
        L.append(f"Mediana dei comparabili: {r['comps_median_h'] or '—'} h. Il gioco promette: {r['target_hours'] or '—'} h"
                 + (f", {r['usd_per_hour']} $ per ora." if r["usd_per_hour"] else "."))
    if r["notes"]:
        L += ["", "## Cosa dice"] + [""] + [f"- {n}" for n in r["notes"]]
    return "\n".join(L) + "\n"


def cmd_calc(a) -> int:
    r = calc(read_json(a.input), load_rates(a.rates), a.corpus_dir)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(to_md(r))
        print(f"scritto {a.md}: {r['verdict']}" + (f" (rapporto {r['ratio']})" if r["ratio"] is not None else ""))
    else:
        print(to_md(r))
    if r["ratio"] is not None and r["ratio"] >= WARN:
        print(("⚠⚠ " if r["ratio"] >= STRONG else "⚠ ") + f"servono {r['ratio']}x le ore disponibili", file=sys.stderr)
    return 0


def self_test() -> int:
    rates = load_rates()
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "7_positive.json"), "w", encoding="utf-8") as f:
        json.dump([{"playtime_forever_h": h} for h in (4, 6, 8)], f)
    inp = {"content": {"enemies": 10, "bosses": 2, "items": 40, "astronavi": 3}, "capacity": {"people": 1, "hours_per_week": 10, "weeks": 40},
           "target_hours": 2, "price_usd": 9.99, "comps": [{"appid": 7, "name": "Sette", "price_usd": 12}]}
    r = calc(inp, rates, tmp)
    content = 10 * 14 + 2 * 45 + 40 * 2.5 + 150
    assert r["needed_h"] == round(content * 1.55, 1), r["needed_h"]
    assert r["available_h"] == 300.0 and r["unknown"] == ["astronavi"]
    assert r["ratio"] == round(r["needed_h"] / 300, 2) and r["verdict"] == "troppo" and r["scope_score"] == 2
    assert r["comps_median_h"] == 6.0 and r["comps"][0]["usd_per_hour"] == 2.0
    assert any("troppo corto" in n for n in r["notes"]) and any("taglia" in n for n in r["notes"])
    assert verdict(0.8) == ("ci sta", 5) and verdict(3.2) == ("fuori scala", 1)
    md = to_md(r)
    assert "rapporto" in md and "| enemies | 10 |" in md and "Sette" in md
    print("self-test OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scope calculator: hours the GDD needs vs hours available.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calc")
    c.add_argument("--input", required=True)
    c.add_argument("--corpus-dir", default=os.path.join("launch", "_raw", "corpus"))
    c.add_argument("--rates")
    c.add_argument("--json", action="store_true")
    c.add_argument("--md")
    sub.add_parser("rates")
    sub.add_parser("self-test")
    a = ap.parse_args(argv)
    if a.cmd == "rates":
        r = load_rates()
        for k, v in r["units"].items():
            print(f"{k:15} {v['hours']:>6g} h  {v['what']}")
        print(f"fondamenta {r['base_hours']['hours']} h; sovraccarichi " + ", ".join(f"{k} {v['pct']}%" for k, v in r["overhead"].items())
              + f"; ore produttive {r['productive_share']}  [OPINIONE]")
        return 0
    return cmd_calc(a) if a.cmd == "calc" else self_test()


if __name__ == "__main__":
    sys.exit(main())
