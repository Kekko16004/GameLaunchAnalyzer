#!/usr/bin/env python3
"""Honest odds: one card per decision with the chance, what it rests on (data, n, date), its label, what moves it, and a
CROSS-CHECK when two sources disagree (simulated vs real, verdict vs objective metro, our plan vs real cases).

It reads only files already in launch/ and writes nothing but its JSON (`-o`), so status_page.py can show the cards:
  _raw/metro.json            objective metro (cohort_bench.py score): P(>= 100 / 1,000 / 10,000 copies) at its horizon
  status.json -> verdict      the probability sentence written in the verdict
  _raw/publisher_scout.json  publisher_scout.py: chance of at least one offer pitching the realistic top list
  _raw/nextfest_expect.json  case_studies.py tripwires -o: expected Next Fest gain by wishlists at entry
  wishlists.csv / _raw/wl_plan.json   wishlists recorded now (wl_track.py) to pick the Next Fest row
  _raw/social_learn.json     social_content.py learn: our posts against the small-account benchmark
  predictions.json           predictions.py: simulated predictions that already have a real value

  honest_odds.py [--launch-dir launch] -o launch/_raw/honest_odds.json [--md]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re

import common  # noqa: F401
from common import load_json, write_json


def j(root: str, *p):
    path = os.path.join(root, *p)
    try:
        return load_json(path) if os.path.exists(path) else None
    except Exception:  # noqa: BLE001
        return None


def pct(x: float) -> str:
    return f"{round(100 * x)} %"


def _pcts(text: str, key: str) -> tuple[float, float] | None:
    """'1.000 copie: 25-30%' -> (0.25, 0.30)."""
    m = re.search(re.escape(key) + r"[^:]*:\s*(\d+)(?:\s*-\s*(\d+))?\s*%", text or "")
    if not m:
        return None
    lo = int(m.group(1)) / 100
    return lo, (int(m.group(2)) / 100 if m.group(2) else lo)


def current_wishlists(root: str) -> int | None:
    p = os.path.join(root, "wishlists.csv")
    if not os.path.exists(p):
        return None
    last = None
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            for k in ("wishlists", "total", "wl"):
                if str(r.get(k, "")).strip().isdigit():
                    last = int(r[k])
    return last


def cards(root: str, today: dt.date) -> list[dict]:
    out = []
    st = j(root, "status.json") or {}
    met = j(root, "_raw", "metro.json")
    vtext = str((st.get("verdict") or {}).get("probability") or "")
    if met and (met.get("score") or {}).get("p1k") is not None:
        sc, mm = met["score"], met.get("metro") or {}
        t = str(mm.get("target") or "")
        hz = f"a {t[1:]} giorni dall'uscita" if t[1:].isdigit() else "dopo l'uscita"
        c = dict(key="copies_1k", decision="Arrivare a 1.000 copie", odds=pct(sc["p1k"]), odds_low=sc["p1k"], odds_high=sc["p1k"], label="[STIMA]",
                 basis=f"metro oggettivo su {mm.get('n', '?')} giochi veri usciti di recente, {hz} (affidabilità: {mm.get('strength', '?')}, calcolato il {met.get('scored_on') or mm.get('fitted_on')})",
                 moves="le leve del metro (demo, Next Fest, video di creator prima dell'uscita, lingue, pagina visibile da mesi): `cohort_bench.py score`",
                 also=[f"≥ 100 copie: {pct(sc['p100'])}" if sc.get("p100") is not None else "", f"≥ 10.000 copie: {pct(sc['p10k'])}" if sc.get("p10k") is not None else ""])
        v = _pcts(vtext, "1.000 copie")
        if v:
            mid = (v[0] + v[1]) / 2
            ratio = mid / sc["p1k"] if sc["p1k"] else None
            c["cross_check"] = dict(other=f"il verdetto scritto dice {round(100 * v[0])}-{round(100 * v[1])} % (anno 1)",
                                    agree=bool(ratio and 0.5 <= ratio <= 2),
                                    note=("le due stime concordano" if ratio and 0.5 <= ratio <= 2 else
                                          f"le due stime NON concordano ({round(100 * mid)} % contro {pct(sc['p1k'])}): l'orizzonte è diverso ({hz} contro anno 1), "
                                          "ma la differenza è più grande di quanto l'orizzonte spieghi. Vale la più prudente finché il metro non viene ricalcolato con il piano rispettato."))
        out.append(c)
    pub = j(root, "_raw", "publisher_scout.json")
    if pub and pub.get("pitch_top"):
        pt = pub["pitch_top"]
        rn = (pub.get("counts") or {}).get("realistic_now", 0)
        out.append(dict(key="publisher", decision="Avere almeno un'offerta da un publisher", odds=f"≤ {pct(pt['p_any'])}", odds_low=0, odds_high=pt["p_any"], label="[STIMA]",
                        basis=f"proponendo il gioco ai primi {pt['n']} publisher realistici ({rn} realistici adesso); probabilità per invio da base rate citati (Raw Fury < 1 % dei pitch, Outersloth ~1,4 %) × aderenza; risposte trattate come indipendenti, quindi è un tetto",
                        moves="demo pubblica, wishlist, una run che si capisce in 10 secondi di video; vedi `publisher-scout.md`"))
    nf = j(root, "_raw", "nextfest_expect.json")
    if nf and nf.get("rows"):
        wl = current_wishlists(root)
        rows = nf["rows"]
        row = min(rows, key=lambda r: abs(r["entering"] - wl)) if wl is not None else rows[len(rows) // 2]
        e = row.get("expected") or {}
        sv = row.get("survey") or {}
        if e:
            c = dict(key="nextfest", decision=f"Wishlist guadagnate al {nf.get('fest') or 'Next Fest'} entrando con ~{row['entering']:,}".replace(",", "."),
                     odds=f"+{e['low']:,} … +{e['high']:,} (mediana +{e['mid']:,})".replace(",", "."), label="[STIMA]",
                     basis=(f"sondaggio con n = {sv.get('n')} ({sv.get('date')})" if sv else "casi reali") + (f" e {row['n']} casi simili auto-dichiarati" if row.get("n") else "")
                     + (f"; wishlist registrate oggi: {wl}" if wl is not None else "; nessuna wishlist registrata: riga centrale"),
                     moves="entrare con più wishlist (la correlazione più forte), demo pubblica settimane prima, trailer forte nei primi 5 secondi")
            if row.get("n") and row.get("gain_median") is not None and sv.get("median_gain"):
                r_ = row["gain_median"] / sv["median_gain"] if sv["median_gain"] else None
                c["cross_check"] = dict(other=f"casi auto-dichiarati: mediana +{row['gain_median']}", agree=bool(r_ and r_ <= 1.6),
                                        note="i casi postati sono più ottimisti del sondaggio: normale, chi va bene lo racconta" if r_ and r_ > 1.6 else "casi e sondaggio concordano")
            out.append(c)
    sl = j(root, "_raw", "social_learn.json")
    if sl and sl.get("platforms"):
        for p in sl["platforms"]:
            out.append(dict(key=f"social_{p['platform']}", decision=f"I nostri post su {p['platform']}", odds=f"mediana {p['median_views']} visual. ({p['vs_typical']}× il tipico)",
                            label="[FATTO]" if p["n"] >= 5 else "[FATTO, pochi post]", basis=f"{p['n']} post registrati; tipico per un account piccolo ~{p['typical_small']} (fonti in data/social_patterns.json)",
                            moves="i momenti e i ganci 'da rifare' di social_content.py learn"))
    pr = j(root, "predictions.json")
    if pr and pr.get("items"):
        sim = [x for x in pr["items"] if x.get("label") == "SIMULATO"]
        try:
            import predictions as pdm
            act = pdm.actuals(root)
        except Exception:  # noqa: BLE001
            act = {}
        real = [x for x in sim if act.get(x.get("actual_metric") or "")]
        out.append(dict(key="sim_vs_real", decision="Il focus group simulato contro la realtà", odds=f"{len(real)} previsioni su {len(sim)} hanno già un dato vero",
                        label="[FATTO]", basis="predictions.py: ogni ondata è una previsione; il confronto si fa solo quando arrivano i numeri dei tester veri e di Steam",
                        moves="registrare wishlist, giocatori della demo e risultati del test reale (wl_track.py, metrics_track.py)",
                        cross_check=dict(other="nessun dato vero ancora" if not real else "", agree=None,
                                         note="finché non c'è un dato vero il punteggio simulato ordina i problemi ma non dice quanto venderemo" if not real else "")))
    return [dict(c, also=[a for a in c.get("also", []) if a]) for c in out]


def to_md(cs: list[dict]) -> str:
    L = ["# Probabilità oneste, decisione per decisione", "", "| Decisione | Probabilità | Su cosa si basa | Cosa la sposta | Controllo incrociato |", "|---|---|---|---|---|"]
    for c in cs:
        cc = c.get("cross_check") or {}
        L.append(f"| {c['decision']} | **{c['odds']}** {c['label']} | {c['basis']} | {c['moves']} | {('✅ ' if cc.get('agree') else '⚠️ ' if cc.get('agree') is False else '') + (cc.get('note') or '')} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("-o", "--out"); ap.add_argument("--md")
    a = ap.parse_args(argv)
    cs = cards(a.launch_dir, dt.date.today())
    write_json(dict(generated_on=dt.date.today().isoformat(), cards=cs), a.out)
    if a.md:
        open(a.md, "w", encoding="utf-8", newline="\n").write(to_md(cs))


if __name__ == "__main__":
    main()
