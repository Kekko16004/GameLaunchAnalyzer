#!/usr/bin/env python3
"""The real-market parts of STATUS.html: the "Mercato reale" tab, the header summary, and the cards that link the other
tabs to the real market (used by status_page.py; no network, everything read from files).

Reads (anything missing is left out, and the page says so):
  ~/.game-launch-strategist/calibration.json (or launch/_raw/calibration.json)   cohort_bench.py calibrate + metro
  ~/.game-launch-strategist/volume.json (or launch/_raw/cohort/volume.json)       games released per day
  launch/_raw/metro.json            cohort_bench.py score --features launch/prelaunch.json -o launch/_raw/metro.json
  launch/_raw/top_moves.json        top_moves.py apply
  launch/predictions.json           predictions.py (prediction vs reality)
  launch/_raw/comps_calibrated.json market_tracker.py comps (comparables measured at 30/90 days like the cohort)
  launch/_raw/dossier/*.json        market_tracker.py dossier (marketing dossier of comparables and competitors)
  launch/ricerche-manuali.md        manual checks (SteamDB, TikTok, Instagram, X) as a checklist
  launch/metrics.csv, wishlists.csv, _raw/contingencies.json   weekly KPI board against the thresholds
Labels: [FATTO] read from a public source, [STIMA] computed with a stated method, SIMULATO from the simulated panel.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import os
import re

import charts as ch
import common

esc = ch.esc
STALE_DAYS = 30
UPDATE_CMD = "python cohort_bench.py update && python cohort_bench.py calibrate && python cohort_bench.py metro"


def _j(p: str):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load(root: str, today: dt.date) -> dict:
    cal = _j(os.path.join(root, "_raw", "calibration.json")) or _j(common.user_dir("calibration.json"))
    vol = _j(common.user_dir("volume.json")) or _j(os.path.join(root, "_raw", "cohort", "volume.json"))
    d = dict(cal=cal, vol=vol, metro=_j(os.path.join(root, "_raw", "metro.json")), metro_plan=_j(os.path.join(root, "_raw", "metro-piano.json")), moves=_j(os.path.join(root, "_raw", "top_moves.json")),
             comps=_j(os.path.join(root, "_raw", "comps_calibrated.json")), dossiers=[x for x in (_j(p) for p in sorted(glob.glob(os.path.join(root, "_raw", "dossier", "dossier-*.json")))) if x],
             today=today, root=root)
    try:
        import predictions as pr
        d["pred"] = pr.evaluate(root, today) if os.path.exists(pr.path_of(root)) else None
    except Exception:  # noqa: BLE001
        d["pred"] = None
    d["age"] = (today - dt.date.fromisoformat(cal["generated_on"])).days if cal and cal.get("generated_on") else None
    d["stale"] = d["age"] is None or d["age"] > STALE_DAYS
    return d


def pct(x, nd=0) -> str:
    return "n/d" if x is None else f"{x:.{nd}f} %".replace(".", ",")


def rng(g: dict, key: str) -> str:
    s = (g or {}).get(key) or {}
    return "n/d" if not s else (f"{s['pct_low']:.0f} %" if s["pct_low"] == s["pct_high"] else f"{s['pct_low']:.0f}-{s['pct_high']:.0f} %")


def nfmt(n) -> str:
    return "n/d" if n is None else f"{int(round(n)):,}".replace(",", ".")


def badge(kind: str, text: str) -> str:
    return f'<span class="mbadge {kind}">{esc(text)}</span>'


def freshness(d: dict) -> str:
    cal = d["cal"]
    if not cal:
        return (f'<div class="card mfresh crit"><strong>Nessuna calibrazione dal mercato reale.</strong> Le affermazioni su vendite e successo qui sotto non hanno ancora un '
                f'ancoraggio reale. Per crearla: <code>{esc(UPDATE_CMD)}</code></div>')
    when = f"dati del {cal['generated_on']} (uscite dal {cal.get('data_from')} al {cal.get('data_to')}, {cal.get('n_graded')} giochi giudicati)"
    if d["stale"]:
        age_txt = f"vecchi di {d['age']} giorni"
        return (f'<div class="card mfresh warn">{badge("warn", age_txt)} <strong>I dati del mercato reale vanno aggiornati</strong>: {esc(when)}. '
                f'Aggiorna con <code>{esc(UPDATE_CMD)}</code> (poi giudica le capsule nuove).</div>')
    return f'<div class="card mfresh ok">{badge("ok", "dati freschi")} Mercato reale: {esc(when)}.</div>'


# ---------------------------------------------------------------- base rates for our game
def our_base(d: dict, price: float | None, tier: str = "B"):
    cal = d["cal"]
    if not cal or not cal.get("primary"):
        return None, None
    from cohort_bench import base_rate
    g, label = base_rate(cal, tier, price)
    return g, label


def game_price(root: str) -> float | None:
    kit = _j(os.path.join(root, "store_kit.json")) or {}
    econ = _j(os.path.join(root, "_raw", "econ.json")) or {}
    p = ((econ.get("inputs") or {}).get("ea_price") or (econ.get("inputs") or {}).get("price"))
    if p:
        return float(p)
    m = re.search(r"(\d+[.,]\d{2})\s*\$", json.dumps(kit, ensure_ascii=False))
    return float(m.group(1).replace(",", ".")) if m else None


# ---------------------------------------------------------------- header summary (replaces the big traffic light)
def hero(d: dict, st: dict, fg_rows: list, crit: dict | None, plan: dict | None, light: tuple[str, str], gate: float | None) -> str:
    today, root = d["today"], d["root"]
    S, chips = [], []
    level = 0   # 0 good, 1 attention, 2 risk
    need = {1: [], 2: []}   # what keeps the verdict at "attention" (1) or "risk" (2): the same rules, read backwards
    cal = d["cal"]
    if not cal:
        S.append("Non c'è ancora una calibrazione dal mercato reale: ogni frase su vendite e successo qui sotto è un'ipotesi, non un dato.")
        level = max(level, 1)
        need[1].append(f"Crea la calibrazione dal mercato reale: {UPDATE_CMD}.")
    elif d["stale"]:
        S.append(f"Prima di tutto: i dati del mercato reale sono vecchi di {d['age']} giorni (del {cal['generated_on']}); aggiornali prima di decidere.")
        level = max(level, 1)
        need[1].append(f"Aggiorna i dati del mercato reale (sono vecchi di {d['age']} giorni, il limite è {STALE_DAYS}).")
    beta = [r for r in (fg_rows or []) if (r.get("_stage") or r.get("stage") or "beta") != "full"]
    if beta:
        last = beta[-1]
        prev = beta[-2] if len(beta) > 1 else None
        sc, ps = _f(last.get("score")), _f(prev.get("score")) if prev else None
        trend = "" if ps is None else (f", in salita di {sc - ps:.1f} punti" if sc - ps >= 3 else f", in calo di {ps - sc:.1f} punti" if ps - sc >= 3 else ", stabile")
        S.append((f"L'ultima ondata del focus group (n. {last.get('wave')}, {last.get('date')}) dà {sc:.1f} su 100 alla beta{trend}"
                  + (f"; la soglia è {gate:.1f}" if gate else "")).replace(".", ",").replace(f"n, {last.get('wave')}", f"n. {last.get('wave')}") + " (SIMULATO: ordina i problemi, non prevede le vendite).")
        if gate and sc < gate:
            level = max(level, 2)
            c_ = lambda v: f"{v:.1f}".replace(".", ",")
            need[2].append(f"Porta il punteggio della prossima ondata da {c_(sc)} ad almeno {c_(gate)} (mancano {c_(gate - sc)} punti): lavora sui problemi gravi.")
    price = game_price(root)
    g, label = our_base(d, price)
    met = d.get("metro")
    if g and g.get("n"):
        S.append(f"Nel mercato reale un gioco di {label} vende almeno 1.000 copie a {cal['primary'][1:]} giorni nel {rng(g, 'copies1000')} dei casi; "
                 f"la mediana è {nfmt(g['copies']['median'][0])}-{nfmt(g['copies']['median'][1])} copie (n = {g['n']}) [STIMA].")
    if met and met.get("score"):
        sc_ = met["score"]
        strength = (met.get("metro") or {}).get("strength", "non verificato")
        pl = (d.get("metro_plan") or {}).get("score")
        S.append(f"Il metro oggettivo (dati veri, affidabilità: {strength}) dà oggi il {round(100 * sc_['p1k'])} % di probabilità di superare 1.000 copie {_horizon(met)}" + (f" (punteggio del {met['scored_on']})" if met.get("scored_on") else "")
                 + (f"; con il piano attuale rispettato (trailer, demo, Next Fest, 8 lingue, pagina visibile da mesi) sale al {round(100 * pl['p1k'])} %" if pl else "") + " [STIMA].")
        if sc_["p1k"] < 0.25:
            level = max(level, 1)
            lev = [lv for lv in sc_.get("levers") or [] if lv.get("delta_p1k_pp", 0) > 0][:3]
            need[1].append(f"Metro oggettivo: P(≥1.000 copie) è al {round(100 * sc_['p1k'])} %, la soglia è 25 %."
                           + (" Le leve che lo spostano di più: " + "; ".join(f"{lv['label']} (+{str(round(lv['delta_p1k_pp'], 1)).replace('.', ',')} punti)" for lv in lev) + "." if lev else "")
                           + (f" Il piano completo lo porta al {round(100 * pl['p1k'])} %: si sale facendo davvero quei passi, poi rilanciando cohort_bench.py score." if pl else ""))
    issues = [x for x in (crit or {}).get("issues", []) if x.get("now")]
    high = [x for x in issues if x.get("severity") == "alta"]
    moves = (d.get("moves") or {}).get("moves") or []
    if high:
        S.append(("Resta aperto 1 problema grave:" if len(high) == 1 else f"Restano aperti {len(high)} problemi gravi; il primo è") + f" «{high[0].get('label')}».")
        level = max(level, 1 if len(high) < 3 else 2)
        names = "; ".join(f"«{x.get('label')}»" for x in high[:3])
        if len(high) >= 3:
            need[2].append(f"Chiudi almeno {len(high) - 2} {'problema grave' if len(high) - 2 == 1 else 'problemi gravi'} su {len(high)} (sotto i 3 il verdetto non è più «a rischio»): {names}.")
        need[1].append(f"Chiudi tutti e {len(high)} i problemi gravi, non solo quelli che bastano per uscire da «a rischio» (lista nella scheda Gioco e test)." if len(high) >= 3
                       else f"Chiudi {'il problema grave ancora aperto' if len(high) == 1 else f'i {len(high)} problemi gravi ancora aperti'}: {names}.")
    if moves:
        S.append("Le mosse a più impatto adesso: " + "; ".join(f"{i}. {m['title']}" for i, m in enumerate(moves[:3], 1)) + ".")
    nxt = None
    if plan and plan.get("phases"):
        import plan_steps as ps_
        ns = ps_.next_steps(plan, None, 1, today)
        if ns:
            nxt = ns[0]
            late = nxt["due"] and nxt["due"] < today.isoformat()
            bold = re.search(r"\*\*(.+?)\*\*", nxt["text"])
            what = re.sub(r"[*`]", "", bold.group(1) if bold else nxt["text"]).replace("⭐ mossa top · ", "").strip()
            S.append(f"Prossima scadenza: {what if len(what) <= 110 else what[:107].rsplit(' ', 1)[0] + '…'}" + (f" ({'in ritardo, era il ' if late else 'entro il '}{nxt['due']})" if nxt["due"] else "") + ".")
            if late:
                level = max(level, 1)
            n_late = ps_.summary(plan, today)["overdue"]
            if n_late:
                need[1].append(f"Chiudi o ripianifica {'il passo in ritardo' if n_late == 1 else f'i {n_late} passi in ritardo'} (scheda Calendario, riquadro «In ritardo»).")
    pr = d.get("pred")
    if pr and pr.get("evaluated"):
        S.append(f"Previsioni verificate con dati veri: {pr['hits']} giuste su {pr['evaluated']} ({pct(pr['accuracy'])})"
                 + (f", {pr['optimistic']} erano troppo ottimiste" if pr.get("optimistic") else "") + ".")
        if pr["accuracy"] is not None and pr["accuracy"] < 50:
            level = max(level, 1)
            need[1].append(f"Le previsioni verificate sono giuste solo nel {pct(pr['accuracy'])} dei casi: ricalibra le stime prima di fidarti dei numeri.")
    kind = ["ok", "warn", "crit"][level]
    title = ["In linea con i dati", "Da sistemare prima di spingere", "A rischio: servono correzioni"][level]
    icon = ['<path d="M5 12l4 4 10-10"/>', '<path d="M12 7v6M12 17h.01"/>', '<path d="M12 7v6M12 17h.01M4 20h16L12 4z"/>'][level]
    lk, lw = light
    chips.append(badge(lk, f"semaforo: {lw}"))
    if cal:
        chips.append(badge("warn" if d["stale"] else "ok", f"mercato reale del {cal['generated_on']}"))
    if pr and pr.get("evaluated"):
        chips.append(badge("info", f"previsioni giuste {pct(pr['accuracy'])}"))
    steps_html = ""
    if level:
        names = ["In linea con i dati", "Da sistemare prima di spingere", "A rischio: servono correzioni"]
        blocks = []
        if level == 2 and need[2]:
            blocks.append((f"Per passare a «{names[1]}»", need[2]))
        if need[1] or level == 2:
            blocks.append((f"Per arrivare a «{names[0]}»", [x for x in need[1] if x not in need[2]] or ["Nient'altro oltre al passo sopra."]))
        steps_html = ('<div class="hero-next"><div class="hn-h">Cosa manca per passare al livello successivo</div>' + "".join(
            f'<div class="hn-b"><div class="hn-t">{esc(t)}</div><ol>' + "".join(f"<li>{esc(x)}</li>" for x in xs) + "</ol></div>" for t, xs in blocks)
            + '<p class="note">Calcolato con le stesse regole del verdetto: chiusa una voce, alla prossima rigenerazione della pagina il livello si aggiorna da solo.</p></div>')
    return (f'<section class="card hero {kind}"><div class="hero-ic"><svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="2.2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{icon}</svg></div><div><div class="big">{esc(title)}</div>'
            + "".join(f"<p>{esc(s)}</p>" for s in S[:7]) + steps_html + f'<div class="chips">{"".join(chips)}</div>'
            f'<p class="note">Riassunto ricalcolato a ogni aggiornamento della pagina dai dati di <code>launch/</code> e dalla calibrazione; non è mai più ottimista dei dati.</p></div></section>')


def _horizon(met: dict) -> str:
    """'a 90 giorni dall'uscita' from the metro target (d30, d90...): never 'nel primo mese' when the model measures 90 days."""
    t = str(((met or {}).get("metro") or {}).get("target") or "")
    return f"a {t[1:]} giorni dall'uscita" if t[1:].isdigit() else "dopo l'uscita"


def _f(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- the tab
def tab(d: dict, root: str) -> list[str]:
    cal, out = d["cal"], [f"<h2>Mercato reale: freschezza dei dati</h2>{freshness(d)}"]
    met = d.get("metro")
    calm = (cal or {}).get("metro")
    if calm:
        out.append(metro_section(calm, met, d.get("metro_plan")))
    if d["vol"]:
        out.append(volume_section(d))
    if cal and cal.get("primary"):
        out.append(outcomes_section(d))
        out.append(head_tail_section(d))
        if cal.get("breakouts"):
            out.append(breakouts_section(d))
        if (cal.get("marketing") or {}).get("recipe"):
            out.append(recipe_section(cal))
    comp = competitors_section(d)
    if comp:
        out.append(comp)
    kpi = kpi_section(root, d["today"])
    if kpi:
        out.append(kpi)
    pr = predictions_section(d)
    if pr:
        out.append(pr)
    man = manual_section(root)
    if man:
        out.append(man)
    return out


def metro_section(calm: dict, met: dict | None, plan: dict | None = None) -> str:
    if not calm.get("available"):
        return f'<h2>Metro oggettivo (dati veri)</h2><div class="card"><p>Non ancora disponibile: {esc(calm.get("why"))} (ora {calm.get("n")}).</p></div>'
    bt = calm.get("backtest") or {}
    a1k = (bt.get("per_threshold") or {}).get("p1k") or {}
    parts = [f'<h2>Metro oggettivo (dati veri)</h2><p class="sub">Una misura del mercato reale per giochi non ancora usciti: usa solo ciò che si vede prima dell\'uscita '
             f'(capsule, prezzo, trailer, demo, Next Fest, lingue, notizie, durata del Coming Soon…). Allenato su {calm["n"]} giochi il {calm["fitted_on"]}; esito a {calm["target"][1:]} giorni [STIMA]. '
             'Affianca il focus group simulato, non lo sostituisce.</p><div class="cgrid">']
    if met and met.get("score"):
        sc = met["score"]
        rows = [dict(label="Oggi", values={b: v * 100 for b, v in zip(calm["bands"], sc["bands"])})]
        if plan and plan.get("score"):
            rows.append(dict(label="Con il piano", values={b: v * 100 for b, v in zip(calm["bands"], plan["score"]["bands"])}))
        rows.append(dict(label="Base rate", values={b: v * 100 for b, v in zip(calm["bands"], calm["base_rate_bands"])}))
        svg, table = ch.stacked(rows, [(b, f"{b} copie", c) for b, c in zip(calm["bands"], ["var(--crit)", "var(--s4)", "var(--s1)", "var(--good)"])], aria="Probabilità per fascia di copie")
        parts.append('<div class="card">' + ch.wrap(svg, title="In che fascia di copie cadiamo", why=f"Oggi: fascia più probabile {sc['band']} copie, P(≥1.000) {round(100 * sc['p1k'])} %, P(≥10.000) {round(100 * sc['p10k'])} % [STIMA]."
                                                    + (f" Con il piano ({esc((plan or {}).get('name') or '')}): P(≥1.000) {round(100 * plan['score']['p1k'])} %, P(≥10.000) {round(100 * plan['score']['p10k'])} %." if plan and plan.get("score") else ""),
                                                    leg=ch.legend([(f"{b} copie", c) for b, c in zip(calm["bands"], ["var(--crit)", "var(--s4)", "var(--s1)", "var(--good)"])]), table=table) + "</div>")
        if sc.get("levers"):
            items = [dict(label=lv["label"], value=lv["delta_p1k_pp"], tip=f"{lv['label']}: P(≥1.000) da {round(100 * sc['p1k'])} % a {round(100 * lv['p1k_after'])} %",
                          color="var(--good)" if lv["delta_p1k_pp"] >= 0 else "var(--crit)") for lv in sc["levers"]]
            svg, table = ch.hbar(items, aria="Cosa sposta l'ago", fmt=lambda v: f"{v:+.1f}", unit=" punti", label_w=170)
            parts.append('<div class="card">' + ch.wrap(svg, title="Cosa sposta l'ago", why="Punti in più (o in meno) di probabilità di superare 1.000 copie se aggiungiamo ciascun fattore. Correlazione dal mercato, non garanzia.", table=table) + "</div>")
    eff = calm.get("effects") or []
    if eff:
        items = [dict(label=e["label"], value=e["delta_pp"], color="var(--s1)" if e["delta_pp"] >= 0 else "var(--s2)") for e in eff[:10]]
        svg, table = ch.hbar(items, aria="Peso dei fattori", fmt=lambda v: f"{v:+.1f}", unit=" punti", label_w=190)
        parts.append('<div class="card">' + ch.wrap(svg, title="Cosa pesa, in parole", why="Per un gioco B tipico: quanto cambia la probabilità di superare 1.000 copie quando il fattore c'è (o è alto). Niente scatola nera: è tutto qui.", table=table) + "</div>")
    if bt.get("possible"):
        verdict = {"utile": ("ok", "utile"), "debole": ("warn", "debole: leggilo come un intervallo, fiducia bassa"), "non migliore del base rate": ("crit", "non migliore del base rate: non usarlo per decidere")}[bt["strength"]]
        rowsv = "".join(f"<tr><td>{esc(k.replace('p', '≥ ').replace('1k', '1.000').replace('10k', '10.000'))}</td><td class=n>{v['auc']}</td><td class=n>{round(100 * (v['skill'] or 0))} %</td>"
                        f"<td class=n>{round(100 * v['actual_rate'])} %</td><td class=n>{round(100 * v['base_rate'])} %</td></tr>" for k, v in bt["per_threshold"].items())
        parts.append(f'<div class="card"><h3>Verifica onesta (fuori dal tempo)</h3><p>{badge(*verdict)}</p><p class="why">Allenato sulle uscite di {esc(", ".join(w.replace("cohort_", "") for w in bt["train_weeks"]))}, '
                     f'provato su quelle di {esc(bt["test_week"].replace("cohort_", ""))} (n = {bt["n_test"]}). AUC 0,5 = a caso, 1 = perfetto; "meglio del base rate" = quanto riduce l\'errore rispetto a usare solo la media.</p>'
                     f'<div class="wrap"><table><thead><tr><th>Soglia di copie</th><th class=n>AUC</th><th class=n>meglio del base rate</th><th class=n>quota reale</th><th class=n>base rate</th></tr></thead><tbody>{rowsv}</tbody></table></div>'
                     f'<p class="note">Fascia indovinata: {round(100 * bt["band_accuracy"])} % (solo base rate {round(100 * bt["band_accuracy_base"])} %). Non usati ancora: {esc("; ".join(calm.get("not_used") or []))}.</p></div>')
    else:
        parts.append(f'<div class="card"><h3>Verifica onesta</h3><p>{badge("warn", "non ancora verificabile")} {esc(bt.get("why", ""))}. Fiducia bassa.</p></div>')
    return "".join(parts) + "</div>"


def volume_section(d: dict) -> str:
    vol, cal = d["vol"], d["cal"] or {}
    sh = cal.get("tier_share") or {}
    junk = cal.get("junk_share") or 0
    weeks: dict = {}
    for x in vol.get("per_day", []):
        day = dt.date.fromisoformat(x["date"])
        k = f"{day.isocalendar()[0]}-S{day.isocalendar()[1]:02d}"
        weeks[k] = weeks.get(k, 0) + x["games"]
    rows = []
    for k, n in weeks.items():
        ok = n * (1 - junk)
        rows.append(dict(label=k, values=dict(junk=round(n * junk), A=round(ok * sh.get("A", 0)), B=round(ok * sh.get("B", 0)), C=round(ok * sh.get("C", 0)))))
    svg, table = ch.stacked(rows, [("C", "C, sotto di noi", "var(--muted)"), ("B", "B, al nostro livello", "var(--s1)"), ("A", "A, sopra di noi", "var(--good)"), ("junk", "junk", "var(--crit)")],
                            aria="Uscite per settimana per fascia", percent=False, label_w=90)
    s = vol["summary"]
    ab = (sh.get("A", 0) + sh.get("B", 0)) * (1 - junk)
    g_ab = ((cal.get("milestones") or {}).get(cal.get("primary") or "", {}).get("tiers") or {}).get("A+B") or {}
    of20 = ""
    if g_ab.get("n"):
        pop = g_ab["popular"]
        of20 = (f" Su 20 giochi al nostro livello o sopra, a {cal['primary'][1:]} giorni ne diventano popolari {20 * pop['pct_low'] / 100:.1f}-{20 * pop['pct_high'] / 100:.1f} "
                f"e vendono almeno 1.000 copie {20 * g_ab['copies1000']['pct_low'] / 100:.1f}-{20 * g_ab['copies1000']['pct_high'] / 100:.1f} [STIMA].")
    return (f'<h2>Quanti giochi escono, e quanti sono al nostro livello</h2><div class="card">'
            + ch.wrap(svg, title="Uscite per settimana, divise per fascia", why=f"Ogni giorno escono {s['min']}-{s['max']} giochi (mediana {s['median']}) [FATTO, ricerca dello store, {vol.get('read_on')}]; "
                      f"al nostro livello o sopra circa {s['median'] * ab:.0f} al giorno [STIMA: quote della coorte giudicata].{of20}",
                      leg=ch.legend([("C, sotto di noi", "var(--muted)"), ("B, al nostro livello", "var(--s1)"), ("A, sopra di noi", "var(--good)"), ("junk", "var(--crit)")]), table=table,
                      note="Le quote A/B/C vengono dal giudizio visivo severo di un solo valutatore sulle capsule; il junk visibile da non loggati è un minimo.") + "</div>")


def outcomes_section(d: dict) -> str:
    cal = d["cal"]
    m = cal["milestones"][cal["primary"]]
    T = m["tiers"]
    out = [f'<h2>Cosa succede davvero dopo l\'uscita, per fascia</h2><p class="sub">Esito a {cal["primary"][1:]} giorni dall\'uscita; copie = recensioni × 20..60 [STIMA]; '
           '"popolare" = almeno 500 recensioni o 10.000 copie stimate (nostra definizione). Le barre mostrano il valore medio dell\'intervallo; nel suggerimento e nella tabella c\'è l\'intervallo intero.</p><div class="cgrid">']
    for key, title in (("copies100", "Almeno 100 copie"), ("copies1000", "Almeno 1.000 copie"), ("copies10000", "Almeno 10.000 copie"), ("popular", "Diventa popolare")):
        items = []
        for t, lab in (("A", "A sopra di noi"), ("B", "B come noi"), ("C", "C sotto"), ("all_new", "tutti i nuovi")):
            g = T.get(t) or {}
            if g.get("n"):
                s = g[key]
                items.append(dict(label=f"{lab} (n={g['n']})", value=(s["pct_low"] + s["pct_high"]) / 2, tip=f"{lab}: {s['pct_low']:.0f}-{s['pct_high']:.0f} % (n = {g['n']})",
                                  color="var(--s1)" if t == "B" else "var(--muted)"))
        svg, table = ch.hbar(items, aria=title, fmt=lambda v: f"{v:.0f}", unit=" %", vmax=100, label_w=150)
        out.append(f'<div class="card">{ch.wrap(svg, title=title, table=table)}</div>')
    bp = m["by_price"].get("B") or {}
    items = [dict(label=f"{band} $ (n={g['n']})", value=(g["copies1000"]["pct_low"] + g["copies1000"]["pct_high"]) / 2, tip=f"B a {band} $: {g['copies1000']['pct_low']:.0f}-{g['copies1000']['pct_high']:.0f} %",
                  color="var(--s1)" if g["n"] >= 30 else "var(--muted)") for band, g in bp.items() if g.get("n")]
    if items:
        svg, table = ch.hbar(items, aria="B per prezzo", fmt=lambda v: f"{v:.0f}", unit=" %", vmax=100, label_w=130)
        out.append(f'<div class="card">{ch.wrap(svg, title="Fascia B: almeno 1.000 copie, per prezzo", why="Grigio = meno di 30 giochi: solo indicativo.", table=table)}</div>')
    bg = m["by_genre"].get("B") or {}
    items = [dict(label=f"{k} (n={g['n']})", value=(g["copies1000"]["pct_low"] + g["copies1000"]["pct_high"]) / 2, color="var(--s1)" if g["n"] >= 30 else "var(--muted)")
             for k, g in sorted(bg.items(), key=lambda kv: -(kv[1].get("n") or 0)) if g.get("n", 0) >= 5]
    if items:
        svg, table = ch.hbar(items, aria="B per genere", fmt=lambda v: f"{v:.0f}", unit=" %", vmax=100, label_w=140)
        out.append(f'<div class="card">{ch.wrap(svg, title="Fascia B: almeno 1.000 copie, per genere", why="Un gioco può stare in più generi. Grigio = meno di 30 giochi.", table=table)}</div>')
    return "".join(out) + "</div>"


def head_tail_section(d: dict) -> str:
    cal = d["cal"]
    dist, conc = cal.get("distribution"), cal.get("concentration") or {}
    out = ['<h2>La testa del mercato e la coda lunga</h2><div class="cgrid">']
    if dist:
        rows = [dict(label=b["label"], values={t: b.get(t, 0) for t in ("A", "B", "C")}) for b in dist["buckets"]]
        svg, table = ch.stacked(rows, [("C", "C", "var(--muted)"), ("B", "B (noi)", "var(--s1)"), ("A", "A", "var(--good)")], aria="Distribuzione delle recensioni", percent=False, label_w=90)
        out.append('<div class="card">' + ch.wrap(svg, title=f"Quante recensioni a {dist['milestone'][1:]} giorni (giochi nuovi)", why=(
            f"Il top 1 % prende il {conc.get('top1')} % delle recensioni, il top 10 % il {conc.get('top10')} %, la metà bassa lo {conc.get('bottom50')} % [FATTO]. Dove cadono i B: la barra blu." if conc else ""),
            leg=ch.legend([("C", "var(--muted)"), ("B (noi)", "var(--s1)"), ("A", "var(--good)")]), table=table) + "</div>")
    head = [h for h in cal.get("head") or [] if h.get("reviews")]
    if head:
        head.sort(key=lambda h: -h["reviews"])
        items = [dict(label=h.get("name") or str(h["appid"]), value=h["reviews"], tip=f"{h.get('name')}: {h['reviews']:,} recensioni in tutto · {', '.join(h['roles'])}") for h in head[:12]]
        svg, table = ch.hbar(items, aria="La testa del mercato", label_w=170)
        out.append('<div class="card">' + ch.wrap(svg, title="La testa: più venduti e più giocati oggi", why="Recensioni totali (anni di vita, non 30 giorni): è un altro pianeta rispetto ai giochi nuovi.", table=table) + "</div>")
    return "".join(out) + "</div>"


def breakouts_section(d: dict) -> str:
    cal = d["cal"]
    tb = (cal["milestones"].get("d30", {}).get("tiers") or {}).get("B") or {}
    rows = []
    for b in cal["breakouts"]:
        c = b.get("curve") or {}
        rows.append([b.get("name"), b.get("release_date"), b.get("reviews_per_day"), c.get("d7", "–"), c.get("d30", "–"), c.get("d90", "–")])
    items = [dict(label=b.get("name") or "", value=b.get("reviews_per_day") or 0) for b in sorted(cal["breakouts"], key=lambda b: -(b.get("reviews_per_day") or 0))[:10]]
    svg, table = ch.hbar(items, aria="Nuovi che decollano", fmt=lambda v: f"{v:.0f}", unit="/giorno", label_w=170,
                         ref=((tb.get("reviews") or {}).get("median", 0) / 30, "B tipico") if tb.get("n") else None)
    head = "".join(f"<th{' class=n' if i > 1 else ''}>{esc(h)}</th>" for i, h in enumerate(["Gioco", "Uscita", "Recensioni/giorno", "a 1 settimana", "a 1 mese", "a 3 mesi"]))
    body = "".join("<tr>" + "".join(f"<td{' class=n' if i > 1 else ''}>{esc(c)}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    return ('<h2>I nuovi che decollano</h2><div class="cgrid"><div class="card">' + ch.wrap(svg, title="Recensioni al giorno dall'uscita", why="Uscite degli ultimi 30 giorni sotto i 25 $ con la crescita più veloce, contro il ritmo di un B tipico (linea tratteggiata). Possono comparire anche giochi gratis o 1.0 di vecchi Early Access.") + "</div>"
            + f'<div class="card"><h3>La curva: recensioni a +1 settimana, +1 mese, +3 mesi</h3><div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
            f'<p class="note">B tipico: mediana {nfmt((tb.get("reviews") or {}).get("median"))} recensioni a 1 mese (n = {tb.get("n")}). Dati: istogramma pubblico delle recensioni di Steam [FATTO].</p></div></div>')


def recipe_section(cal: dict) -> str:
    mk = cal["marketing"]
    rec = mk["recipe"]
    items = []
    for r in rec:
        if r.get("winners") is None:
            continue
        items.append(dict(label=f"{r['label']} · vincenti", value=r["winners"], color="var(--good)", tip=f"{r['label']}: vincenti {r['winners']:.0f} % (n = {r['n_winners']})"))
        items.append(dict(label="perdenti", value=r["losers"] or 0, color="var(--muted)", tip=f"{r['label']}: perdenti {r['losers'] or 0:.0f} % (n = {r['n_losers']})"))
    svg, table = ch.hbar(items, aria="Ricetta dei B vincenti", fmt=lambda v: f"{v:.0f}", unit=" %", vmax=100, label_w=220)
    order = " → ".join(f"{r['label']}" + (f" (~{int(r['median_days_before'])} g prima)" if r.get("median_days_before") and r["median_days_before"] > 0 else " (dopo l'uscita)" if (r.get("median_days_before") or 0) < 0 else "")
                       for r in rec if r.get("winners") is not None)
    return (f'<h2>Cosa hanno fatto i B vincenti, in ordine</h2><div class="card">' + ch.wrap(svg, title="Quanto spesso c\'è ogni passo: vincenti contro perdenti",
            why=f"B vincenti = almeno 50 recensioni a {mk['milestone'][1:]} giorni (n = {mk['n_win']}); perdenti = meno di 10 (n = {mk['n_lose']}). Fonte: notizie ufficiali Steam e video YouTube abbinati al gioco [FATTO sul campione]. "
                f"Correlazione, non garanzia: chi fa tutto spesso ha anche più mezzi.",
            leg=ch.legend([("B vincenti", "var(--good)"), ("B perdenti", "var(--muted)")]), table=table) + f'<p><strong>In ordine di tempo:</strong> {esc(order)}.</p></div>')


def competitors_section(d: dict) -> str | None:
    comps, doss = d.get("comps"), d.get("dossiers") or []
    if not comps and not doss:
        return None
    out = ['<h2>Concorrenti sul metro del mercato reale</h2>']
    if comps and comps.get("games"):
        body = "".join(
            f"<tr><td>{esc(g['name'])}</td><td>{esc(g.get('role') or '')}</td><td class=n>{esc(g.get('price') or '')}</td><td class=n>{nfmt(g.get('reviews_d30'))}</td><td class=n>{nfmt(g.get('reviews_d90'))}</td>"
            f"<td class=n>{nfmt(g.get('reviews_total'))}</td><td>{esc(g.get('looks_like') or 'n/d')}</td></tr>" for g in comps["games"])
        out.append(f'<div class="card"><p class="why">Recensioni dei primi 30 e 90 giorni dopo l\'uscita (istogramma pubblico, {esc(comps.get("built_on"))}) confrontate con i giochi nuovi giudicati: '
                   f'"esito da B vincente" = sopra il 90° percentile della fascia B al primo mese, "da fascia A" = sopra la mediana degli A. I giochi più vecchi sono usciti in un mercato meno affollato. [FATTO] sulle recensioni, [STIMA] sul confronto.</p>'
                   '<div class="wrap"><table><thead><tr><th>Gioco</th><th>Ruolo</th><th class=n>Prezzo $</th><th class=n>Recensioni a 30 g</th><th class=n>a 90 g</th><th class=n>Totali</th><th>Somiglia a</th></tr></thead>'
                   f'<tbody>{body}</tbody></table></div></div>')
    for x in doss:
        pat = x.get("pattern") or {}
        f = pat.get("features") or {}
        out.append(f'<details class="card"><summary><strong>Dossier marketing: {esc(x["name"])}</strong> <span class="note">{len(x.get("timeline") or [])} eventi · primo segnale {esc(pat.get("first_event") or "n/d")}'
                   + (f" ({pat['lead_days']} giorni prima dell'uscita)" if pat.get("lead_days") is not None else "") + '</span></summary>'
                   f'<p>Prima dell\'uscita: {esc(", ".join(f"{k} {v}" for k, v in (pat.get("before") or {}).items()) or "n/d")}; dopo: {esc(", ".join(f"{k} {v}" for k, v in (pat.get("after") or {}).items()) or "n/d")}. '
                   f'Demo prima: {"sì" if f.get("demo_before") else "no"}; Next Fest: {"sì" if f.get("next_fest") else "no"}; video di creator: {f.get("creator_videos") if f.get("creator_videos") is not None else "n/d"}.</p>'
                   + "".join(f'<p class="note">Picco {esc(s["week"])} ({s["reviews"]} recensioni): ' + esc("; ".join(f"{e['platform']} {e['kind']}: {(e.get('title') or '')[:50]}" for e in s["events"][:4])) + "</p>" for s in (x.get("spikes") or [])[:3])
                   + f'<p class="note">Il dossier completo è in <code>launch/_raw/dossier/dossier-{x["appid"]}.md</code>.</p></details>')
    return "".join(out)


def kpi_section(root: str, today: dt.date) -> str | None:
    """Weekly KPI board: the metrics you record, week by week, against the thresholds of the 'if... then' plans."""
    cpath = os.path.join(root, "_raw", "contingencies.json")
    import metrics_track as mt
    rows = mt.read_metrics(os.path.join(root, "metrics.csv"), os.path.join(root, "wishlists.csv"))
    if not rows:
        return None
    thr = {}
    for s in (_j(cpath) or {}).get("scenarios", []):
        for g in s.get("signals") or []:
            if g.get("metric") and g.get("value") is not None and g.get("op") in ("<", "<=", ">", ">="):
                thr.setdefault(g["metric"], (g["op"], g["value"], g.get("label") or g["metric"], s.get("title")))
    by: dict = {}
    for r in rows:
        m, d_, v = r.get("metric"), r.get("date"), r.get("value")
        if m is None or d_ is None or v is None or m.startswith("fg_"):
            continue
        dd = d_ if isinstance(d_, dt.date) else dt.date.fromisoformat(str(d_)[:10])
        wk = f"{dd.isocalendar()[0]}-S{dd.isocalendar()[1]:02d}"
        by.setdefault(m, {})[wk] = v
    if not by:
        return None
    weeks = sorted({w for v in by.values() for w in v})[-8:]
    body = []
    for m, vals in sorted(by.items()):
        t = thr.get(m)
        cells = []
        for w in weeks:
            v = vals.get(w)
            if v is None:
                cells.append("<td class=n>–</td>")
                continue
            if t:
                op, lim = t[0], float(t[1])
                bad = (v < lim) if op in ("<", "<=") else (v > lim)
                cells.append(f'<td class=n>{badge("crit" if bad else "ok", ("⚠ " if bad else "") + f"{v:g}")}</td>')
            else:
                cells.append(f"<td class=n>{v:g}</td>")
        body.append(f"<tr><td>{esc(m)}</td><td>{esc(f'allarme se {t[0]} {t[1]}' if t else 'nessuna soglia')}</td>{''.join(cells)}</tr>")
    head = "".join(f"<th class=n>{esc(w)}</th>" for w in weeks)
    return (f'<h2>KPI settimana per settimana</h2><div class="card"><p class="why">I numeri che registri (wishlist, scarichi itch, visualizzazioni, membri Discord, ore del team) contro le soglie dei piani se… allora. '
            f'Verde = sopra la soglia, rosso con ⚠ = scattata. Si registrano con <code>metrics_track.py add</code> e <code>wl_track.py add</code>.</p>'
            f'<div class="wrap"><table><thead><tr><th>Metrica</th><th>Soglia</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div></div>')


def predictions_section(d: dict) -> str | None:
    pr = d.get("pred")
    if not pr or not pr.get("n"):
        return None
    def row(x):
        pred = f"{x['low']:g}-{x['high']:g}" if x.get("low") is not None else f"{x['value']:g}"
        real = "" if x.get("actual") is None else f"{x['actual']:g}"
        res = badge("ok", "giusta") if x.get("hit") else badge("crit", x.get("direction", "")) if x.get("hit") is False else ""
        return (f"<tr><td>{esc(x['date'])}</td><td>{esc(x['source'])}</td><td>{esc(x['metric'])}</td><td class=n>{esc(pred)} {esc(x.get('unit') or '')}</td>"
                f"<td>{esc(x['label'])}</td><td>{esc(x['status'])}</td><td class=n>{esc(real)}</td><td>{res}</td></tr>")
    rows = "".join(row(x) for x in pr["rows"])
    acc = (f"{pr['hits']} giuste su {pr['evaluated']} verificate ({pct(pr['accuracy'])})." if pr["evaluated"] else
           "Nessuna previsione è ancora verificabile: arriveranno con i tester veri di novembre, le wishlist e le vendite.")
    return (f'<h2>Previsioni contro realtà</h2><div class="card"><p class="why">Ogni ondata e ogni stima registra la sua previsione (<code>predictions.py</code>); quando arrivano i dati veri '
            f'(<code>metrics_track.py</code>, <code>wl_track.py</code>, i tester veri) qui si vede chi aveva ragione. {esc(acc)}</p>'
            '<div class="wrap"><table><thead><tr><th>Data</th><th>Fonte</th><th>Metrica</th><th class=n>Previsto</th><th>Tipo</th><th>Stato</th><th class=n>Reale</th><th>Esito</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></div>')


def manual_section(root: str) -> str | None:
    p = os.path.join(root, "ricerche-manuali.md")
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8").read()
    items = []
    for ln in txt.splitlines():
        m = re.match(r"^\s*[-*]\s*(\[( |x|X)\]\s*)?(.*(?:steamdb|tiktok|instagram|\bX:|twitter|SteamDB|TikTok|Instagram).*)$", ln)
        if m:
            done = (m.group(2) or " ").lower() == "x"
            items.append((done, re.sub(r"[*`]", "", m.group(3)).strip()))
    if not items:
        return None
    lis = "".join(f'<li><input type="checkbox" disabled{" checked" if d else ""} aria-label="{"fatto" if d else "da fare"}"> {esc(t[:220])}</li>' for d, t in items[:60])
    return (f'<h2>Controlli a mano (SteamDB, TikTok, Instagram, X)</h2><details class="card"><summary>{len(items)} controlli da fare a mano · '
            f'non si leggono con script (termini d\'uso, login)</summary><ul class="checks">{lis}</ul><p class="note">Elenco da <code>launch/ricerche-manuali.md</code>; '
            'segna [x] nel file quando un controllo è fatto, e importa i risultati con <code>market_tracker.py manual --import</code>.</p></details>')


# ---------------------------------------------------------------- cards for the other tabs
def riepilogo_card(d: dict, fg_rows: list) -> str | None:
    cal = d["cal"]
    price = game_price(d["root"])
    g, label = our_base(d, price)
    met = d.get("metro")
    beta = [r for r in (fg_rows or []) if (r.get("_stage") or r.get("stage") or "beta") != "full"]
    lines = ["<li>Fascia ipotizzata: <strong>B</strong> (al livello dei giochi indie curati; nessuna prova che sia A) [giudizio, regola della skill].</li>"]
    if g and g.get("n"):
        lines.append(f"<li>Base rate reale per {esc(label)}: almeno 1.000 copie nel {rng(g, 'copies1000')} dei casi, popolare nel {rng(g, 'popular')}; mediana {nfmt(g['copies']['median'][0])}-{nfmt(g['copies']['median'][1])} copie a {cal['primary'][1:]} giorni (n = {g['n']}) [STIMA].</li>")
    else:
        lines.append("<li>Base rate reale: non disponibile (manca la calibrazione).</li>")
    if met and met.get("score"):
        sc = met["score"]
        lines.append(f"<li>Metro oggettivo oggi: fascia <strong>{esc(sc['band'])}</strong> copie, P(≥1.000) {round(100 * sc['p1k'])} % ({esc((met.get('metro') or {}).get('strength', ''))}) [STIMA].</li>")
    if beta:
        lines.append(f"<li>Ultima ondata: {esc(str(beta[-1].get('score') or 'n/d').replace('.', ','))} su 100, wishlist {esc(str(beta[-1].get('wishlist_pct') or 'n/d').replace('.', ','))} % dei tester (SIMULATO): non si confronta direttamente con le vendite reali.</li>")
    return (f'<h2>Dove siamo rispetto al mercato reale</h2><div class="card"><ul>{"".join(lines)}</ul><p class="note">Il dettaglio è nella scheda <a href="#p-mercato">Mercato reale</a>. '
            "Il focus group simulato e il mercato reale si affiancano: il primo dice cosa correggere, il secondo cosa aspettarsi.</p></div>")


def gioco_card(d: dict) -> str | None:
    cal = d["cal"]
    c = (cal or {}).get("controls")
    if not c:
        return None
    li = lambda xs: "".join(f'<li><a href="https://store.steampowered.com/app/{x["appid"]}/" rel="noopener">{esc(x["name"])}</a> · {esc(x.get("price"))} $ · uscito il {esc(x["release_date"])} · '  # noqa: E731
                             f'{x["reviews"]} recensioni a {c["milestone"][1:]} giorni ({nfmt(x["reviews"] * 20)}-{nfmt(x["reviews"] * 60)} copie [STIMA])</li>' for x in xs[:5])
    return (f'<h2>Il controllo con la realtà del focus group</h2><div class="card"><p class="why">Capsule di controllo per le ondate: giochi B <strong>reali e recenti</strong>, con il loro esito vero. '
            f'Se il panel dà al nostro gioco un punteggio da vincente ma le capsule di controllo reali dicono B, vale la fascia B.</p><div class="grid g2"><div><h3>B che hanno venduto</h3><ul>{li(c["b_winners"])}</ul></div>'
            f'<div><h3>B che non hanno venduto</h3><ul>{li(c["b_losers"])}</ul></div></div><p class="note">Dati del {esc(cal["generated_on"])}. Le ondate restano identiche (54 tester): questo le affianca.</p></div>')


def marketing_card(d: dict) -> str | None:
    cal = d["cal"]
    rec = ((cal or {}).get("marketing") or {}).get("recipe")
    if not rec:
        return None
    import top_moves as tm
    mine = tm.our_status(d["root"])
    st_badge = {"fatto": ("ok", "fatto"), "pianificato": ("warn", "pianificato"), "manca": ("crit", "manca")}
    lis = "".join(f'<li>{badge(*st_badge[mine.get(r["step"], "manca")])} <strong>{esc(r["label"])}</strong> · vincenti {r["winners"]:.0f} %, perdenti {r["losers"] or 0:.0f} %'
                  + (f" · ~{int(r['median_days_before'])} giorni prima dell'uscita" if r.get("median_days_before") and r["median_days_before"] > 0 else "") + "</li>"
                  for r in rec if r.get("winners") is not None)
    return (f'<h2>La ricetta dei B vincenti, e a che punto siamo</h2><div class="card"><ul class="clean">{lis}</ul><p class="note">Il nostro stato viene da <code>TODO.md</code> e <code>calendar.md</code> '
            f'(fatto = voce spuntata, pianificato = voce aperta, manca = nessuna voce). Dati reali del {esc(cal["generated_on"])} [FATTO sul campione]; dettaglio in <a href="#p-mercato">Mercato reale</a>.</p></div>')


def piano_card(d: dict, econ: dict | None) -> str | None:
    cb = (econ or {}).get("calibrated")
    if not cb:
        cal = d["cal"]
        price = game_price(d["root"])
        g, label = our_base(d, price)
        if not (g and g.get("n")) or not econ:
            return None
        net = econ["net_per_copy"]
        rows = [(n_, g["copies"][q][0], g["copies"][q][1]) for n_, q in (("pessimistico (p25)", "p25"), ("base (mediana)", "median"), ("ottimistico (p75)", "p75"), ("raro (p90)", "p90"))]
        cb = dict(group=label, n=g["n"], generated_on=cal["generated_on"], data_from=cal.get("data_from"), data_to=cal.get("data_to"), milestone=cal["primary"],
                  scenarios=[dict(name=a, copies_low=lo, copies_high=hi, net_low=lo * net, net_high=hi * net) for a, lo, hi in rows])
    body = "".join(f"<tr><td>{esc(s['name'])}</td><td class=n>{nfmt(s['copies_low'])}-{nfmt(s['copies_high'])}</td><td class=n>{nfmt(s['net_low'])}-{nfmt(s['net_high'])}</td></tr>" for s in cb["scenarios"])
    return (f'<h2>Scenari di vendita dal mercato reale</h2><div class="card"><p class="why">Copie vendute a {cb["milestone"][1:]} giorni dai giochi reali di {esc(cb["group"])} (n = {cb["n"]}, uscite {esc(cb.get("data_from"))}..{esc(cb.get("data_to"))}, '
            f'calibrazione del {esc(cb["generated_on"])}) [STIMA]. Stanno accanto agli scenari da wishlist di <code>calc_econ.py</code>, non li sostituiscono.</p>'
            f'<div class="wrap"><table><thead><tr><th>Scenario</th><th class=n>Copie</th><th class=n>Netto</th></tr></thead><tbody>{body}</tbody></table></div></div>')


CSS = """#p-mercato li,#p-mercato p,#p-mercato a,.toc a{overflow-wrap:anywhere}
.hero{display:grid;grid-template-columns:auto 1fr;gap:14px;border-left:6px solid var(--muted)}.hero.ok{border-left-color:var(--good)}.hero.warn{border-left-color:var(--warn)}.hero.crit{border-left-color:var(--crit)}
.hero .big{font-size:1.25rem;font-weight:700;margin-bottom:4px}.hero p{margin:4px 0}.hero-ic{width:46px;height:46px;border-radius:50%;display:grid;place-items:center;background:var(--surface2,rgba(127,127,127,.12))}
.hero.ok .hero-ic{color:var(--good)}.hero.warn .hero-ic{color:var(--warn)}.hero.crit .hero-ic{color:var(--crit)}.chips{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 2px}
.mbadge{display:inline-block;border-radius:999px;padding:1px 9px;font-size:.8rem;border:1px solid var(--grid);white-space:nowrap}.mbadge.ok{border-color:var(--good)}.mbadge.warn{border-color:var(--warn)}.mbadge.crit{border-color:var(--crit)}.mbadge.info{border-color:var(--s1)}
.mfresh.warn{border-left:4px solid var(--warn)}.mfresh.crit{border-left:4px solid var(--crit)}.mfresh.ok{border-left:4px solid var(--good)}
ul.checks{list-style:none;padding-left:0}ul.checks li{margin:4px 0}
.hero-next{margin:12px 0 6px;padding:12px 14px;border-radius:12px;background:var(--surface2,rgba(127,127,127,.08));border:1px solid var(--grid)}
.hn-h{font-weight:700;margin-bottom:6px}.hn-b{margin:6px 0}.hn-t{font-weight:600;font-size:.9rem;color:var(--ink2)}.hn-b ol{margin:4px 0 0;padding-left:1.3em}.hn-b li{margin:3px 0}.hero-next .note{margin:6px 0 0}
@media (max-width:600px){.hero{grid-template-columns:1fr}.hero-ic{display:none}}
"""
