#!/usr/bin/env python3
"""Charts for the reports, built from files already in launch/ (nothing is fetched, nothing is invented).

`groups(root, today)` returns the available chart groups as [{key, title, intro, charts:[html]}], in reading order:
product (pillars, issues), focus group, market (comparables, genre, trailers), real reviews, economics, plan (steps by
phase), creators, full game. A group whose source file is missing is simply absent. Used by status_page.py (section
"Quadro d'insieme"), report_html.py (REPORT.html) and charts_export.py (one .svg per chart, for the Markdown reports).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re

import charts as C
import criticita as cr
import plan_steps as ps

STATUS = {"PASS": "var(--good)", "MARGINAL": "var(--warn)", "FAIL": "var(--crit)"}
SEV = {"alta": "var(--crit)", "media": "var(--warn)", "bassa": "var(--muted)"}


def _json(path: str):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _csv(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _num(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _chart(svg_table, **kw) -> str:
    svg, table = svg_table
    return C.wrap(svg, table=table, **kw)


def pillars(root: str) -> list[str]:
    """Pillar matrix of 01-dev.md: any table row carrying PASS / MARGINAL / FAIL."""
    p = os.path.join(root, "01-dev.md")
    if not os.path.exists(p):
        return []
    rows = []
    for ln in open(p, encoding="utf-8").read().splitlines():
        if not ln.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        m = next((re.search(r"\b(PASS|MARGINAL|FAIL)\b", c.upper()) for c in cells[1:] if re.search(r"\b(PASS|MARGINAL|FAIL)\b", c.upper())), None)
        if not m or len(cells) < 3:
            continue
        hours = _num(re.sub(r"[^\d.,]", "", cells[-1])) if re.search(r"\d", cells[-1]) else None
        rows.append(dict(name=re.sub(r"[*_`]", "", cells[0]), grade=m.group(1), hours=hours))
    if not rows:
        return []
    cnt = {g: sum(1 for r in rows if r["grade"] == g) for g in STATUS}
    out = [_chart(C.stacked([dict(label=f"{len(rows)} pilastri", values=cnt)], [("PASS", "PASS", STATUS["PASS"]), ("MARGINAL", "MARGINAL", STATUS["MARGINAL"]), ("FAIL", "FAIL", STATUS["FAIL"])], aria="Pilastri del genere per esito"),
                  title="Pilastri del genere", why="Quanti pilastri la build regge già. Verde = PASS, giallo = MARGINAL, rosso = FAIL.", leg=C.legend([("PASS", STATUS["PASS"]), ("MARGINAL", STATUS["MARGINAL"]), ("FAIL", STATUS["FAIL"])]))]
    todo = sorted((r for r in rows if r["grade"] != "PASS" and r["hours"]), key=lambda r: -r["hours"])
    if todo:
        out.append(_chart(C.hbar([dict(label=r["name"], value=r["hours"], color=STATUS[r["grade"]], tip=f"{r['name']}: {r['grade']}, {r['hours']:.0f} ore per arrivare a PASS") for r in todo[:10]], aria="Ore per portare i pilastri a PASS", unit=" h"),
                          title="Quanto costa arrivare a PASS", why="Ore stimate per ogni pilastro non ancora PASS: da dove partire per rendimento.",
                          leg=C.legend([("MARGINAL", STATUS["MARGINAL"]), ("FAIL", STATUS["FAIL"])]), note="Stime dell'audit, non misure."))
    return out


def focus_group(root: str) -> list[str]:
    rows = _csv(os.path.join(root, "fg", "timeline.csv"))
    if not rows:
        return []
    out = []
    ser = [("w", "Wishlist subito", "var(--s1)"), ("s", "Aspetta i saldi", "var(--s3)"), ("i", "Scorre oltre", "var(--muted)"), ("r", "Compra e rimborsa", "var(--crit)")]
    data = [dict(label=f"Ondata {r['wave']}", values=dict(w=_num(r["wishlist_pct"]) or 0, s=_num(r["saldi_pct"]) or 0, i=_num(r["ignoro_pct"]) or 0, r=_num(r["refund_pct"]) or 0),
                 tip=f"Ondata {r['wave']} ({r['date']}): wishlist {r['wishlist_pct']}%, saldi {r['saldi_pct']}%, ignora {r['ignoro_pct']}%, rimborso {r['refund_pct']}%") for r in rows]
    out.append(_chart(C.stacked(data, ser, aria="Verdetti dei tester per ondata"), title="Cosa farebbero i tester", why="Come si distribuiscono i verdetti a ogni ondata: più blu e meno grigio e rosso = meglio.",
                      leg=C.legend([(l, c) for _, l, c in ser]), note="Panel simulato: ordina i problemi, non prevede le vendite."))
    last = rows[-1]
    b = [dict(label="Punteggio wishlist", value=_num(last["score"]), target=_num(last.get("gate")), max=100, tip=f"Punteggio {last['score']} contro soglia {last.get('gate')}"),
         dict(label="Click al primo sguardo", value=_num(last["click_pct"]), unit="%"), dict(label="Pitch capito", value=_num(last["pitch_pct"]), unit="%")]
    if _num(last.get("buy_pct")) is not None:
        b.append(dict(label="Pagherebbe il prezzo", value=_num(last["buy_pct"]), unit="%", tip=f"Pagherebbe il prezzo previsto all'uscita: {last['buy_pct']}% dei tester"))
    out.append(_chart(C.bullets(b, aria="Indicatori dell'ultima ondata"), title=f"Ultima ondata (n. {last['wave']})", why="Il segno nero è la soglia: la barra deve arrivarci. Click, pitch e acquisto sono percentuali di tester."))
    issues = _top_issues(root)
    if issues:
        out.append(issues)
    return out


def _top_issues(root: str) -> str | None:
    try:
        import fg_waves
        rp = os.path.join(root, "fg", "roster.json")
        ws = fg_waves.load_dir(os.path.join(root, "fg", "waves"), _json(rp) if os.path.exists(rp) else None)
        m = fg_waves.metrics(ws[-1])
    except (SystemExit, Exception):   # no waves, invalid wave file: the group is simply not drawn
        return None
    its = m["issues"][:8]
    if not its:
        return None
    return _chart(C.hbar([dict(label=i["label"], value=i["pct"], color=SEV.get(i["severity"], "var(--muted)"), tip=f"{i['label']}: {i['freq']} tester su {m['n']} ({i['severity']})") for i in its], aria="Critiche più frequenti", unit="%"),
                  title="Critiche più frequenti", why="Quota di tester che le solleva nell'ultima ondata. Il colore è la gravità.",
                  leg=C.legend([("alta", SEV["alta"]), ("media", SEV["media"]), ("bassa", SEV["bassa"])]))


def market(root: str) -> list[str]:
    out = []
    gb = _json(os.path.join(root, "_raw", "genre_bench.json"))
    an = (gb or {}).get("analysis") or {}
    if an.get("cohorts"):
        out.append(_chart(C.columns([dict(label=str(c["year"]), value=c["median_reviews_per_year"], tip=f"{c['year']}: {c['n']} giochi, mediana {c['median_reviews_per_year']} recensioni l'anno") for c in an["cohorts"]], aria="Recensioni l'anno per anno di uscita"),
                          title="Il genere per anno di uscita", why="Mediana delle recensioni l'anno dei giochi più recensiti: un proxy della domanda, non le vendite.",
                          note="Sono la coda alta del genere, non il gioco mediano."))
    if an.get("price_bands"):
        out.append(_chart(C.columns([dict(label=b["band"], value=b["median_reviews_per_year"], tip=f"{b['band']}: {b['n']} giochi") for b in an["price_bands"]], aria="Recensioni l'anno per fascia di prezzo", color="var(--s2)"),
                          title="Per fascia di prezzo", why="Dove si concentrano i giochi che si fanno vedere. Numero di giochi nella tabella."))
    if an.get("demo"):
        out.append(_chart(C.hbar([dict(label=d["group"], value=d["median_reviews_per_year"], tip=f"{d['group']}: {d['n']} giochi", color="var(--s3)") for d in an["demo"]], aria="Con e senza demo"),
                          title="Demo o no", why="Recensioni l'anno mediane dei giochi con e senza demo."))
    if an.get("mine"):
        out.append(_chart(C.hbar([dict(label=m["feature"], value=m["percentile"], tip=f"{m['feature']}: il tuo {m['value']} è al {m['percentile']}° percentile (mediana {m['median']})") for m in an["mine"]], aria="Il tuo gioco contro il genere", unit="°", ref=(50, "mediana"), vmax=100),
                          title="Il tuo gioco contro il genere", why="Percentile dei tuoi numeri nel genere. A destra della linea sei sopra la mediana."))
    comps = _csv(os.path.join(root, "comps.csv"))
    rows = [(r.get("name") or r.get("nome"), _num(r.get("reviews_total") or r.get("recensioni")), _num(r.get("pct_positive") or r.get("positive_pct")), r.get("role") or "") for r in comps]
    rows = sorted((r for r in rows if r[0] and r[1]), key=lambda r: -r[1])[:10]
    if rows:
        out.append(_chart(C.hbar([dict(label=n, value=v, tip=f"{n}: {v:.0f} recensioni" + (f", {p:.0f}% positive" if p else "")) for n, v, p, _ in rows], aria="Comparabili per recensioni"),
                          title="I comparabili più recensiti", why="Quanto pubblico hanno raccolto i giochi che ti somigliano di più."))
    sp = _json(os.path.join(root, "_raw", "store_pages.json"))
    tr = sorted(((o.get("name"), o.get("trailer_s")) for o in (sp if isinstance(sp, list) else []) if o.get("name") and o.get("trailer_s")), key=lambda t: -t[1])[:10]
    if tr:
        out.append(_chart(C.hbar([dict(label=n, value=s, tip=f"{n}: trailer di {s:.0f} s", color="var(--s4)") for n, s in tr], aria="Durata dei trailer dei comparabili", unit=" s"),
                          title="Quanto durano i trailer dei comparabili", why="Durata del trailer principale: confrontala con il tuo."))
    return out


def window(root: str) -> list[str]:
    w = _json(os.path.join(root, "_raw", "window.json"))
    if not w or not w.get("weeks"):
        return []
    ch = w["chosen"]
    items = []
    for k in w["weeks"]:
        d = dt.date.fromisoformat(k["week"])
        near = "; ".join(f"{n['name']} ({n['date']})" for n in k["items"][:4]) or "niente in lista"
        items.append(dict(label=f"{d.day}/{d.month}", value=k["score"], color="var(--s2)" if k["chosen"] else "var(--s3)" if k.get("best") else "var(--s1)", stub=True,
                          tip=f"Settimana dal {k['week']}{' (la tua)' if k['chosen'] else ''}: punteggio {k['score']}. {near}"))
    out = [_chart(C.columns(items, aria="Affollamento per settimana di lancio", fmt=lambda v: f"{v:g}"), title="Quanto è affollata ogni settimana",
                  why=f"Più alta la colonna, più concorrenza vicino a quella settimana. La tua (arancione) è {ch['verdict']}: il {ch['quieter_weeks_pct']}% delle settimane è più tranquillo.",
                  leg=C.legend([("la tua settimana", "var(--s2)"), ("le 3 più tranquille", "var(--s3)"), ("le altre", "var(--s1)")]),
                  note=f"Conta solo le {w.get('counted', 0)} voci in lista (watchlist e window.csv): una settimana libera qui non è libera nel mondo. Punteggio = euristica [OPINIONE].")]
    mine = next((k for k in w["weeks"] if k["chosen"]), None)
    if mine and mine["items"]:
        out.append(_chart(C.hbar([dict(label=n["name"], value=n["points"], tip=f"{n['name']}: {n['kind']}, {n['date']}, peso {n['weight']:g} x {n['factor']}", color="var(--s2)") for n in mine["items"][:8]], aria="Cosa pesa sulla tua settimana"),
                          title="Cosa pesa sulla tua settimana", why="Le voci vicine alla data scelta, con i punti che aggiungono (peso × vicinanza)."))
    return out


def _explain(headers: list[str], rows: list[list], summary: str) -> str:
    """Like charts.table_view but with a clear summary line: the table explains what each bar means."""
    head = "".join(f"<th>{C.esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{C.esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<details><summary>{C.esc(summary)}</summary><div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>'


def reviews(root: str) -> list[str]:
    import theme_labels as TL
    res = _json(os.path.join(root, "_raw", "corpus.json"))
    g = (res or {}).get("groups") or {}
    out = []
    for key, title, why in (("punished", "Di cosa si lamentano i giocatori",
                             "Su 100 recensioni negative dei giochi simili, quante parlano di ciascun problema. Barra lunga = lamentela frequente."),
                            ("rewarded", "Cosa piace ai giocatori",
                             "Su 100 recensioni positive dei giochi simili, quante lodano ciascuna cosa. Barra lunga = motivo di gradimento frequente.")):
        c, n = {r["theme"]: r for r in (g.get("comps") or {}).get(key, [])}, {r["theme"]: r for r in (g.get("genre") or {}).get(key, [])}
        themes = sorted(set(c) | set(n), key=lambda t: -max((c.get(t) or {}).get("macro_pct", 0), (n.get(t) or {}).get("macro_pct", 0)))[:7]
        if not themes:
            continue
        items, rows = [], []
        for t in themes:
            lb = TL.label(t)
            cv, nv = (c.get(t) or {}).get("macro_pct"), (n.get(t) or {}).get("macro_pct")
            items.append(dict(label=lb, value=cv, color="var(--s1)", tip=f"{lb} — giochi più simili al tuo: {cv if cv is not None else 'n/d'}% (in {(c.get(t) or {}).get('breadth', '-')} giochi)"))
            if n:
                items.append(dict(label="", value=nv, color="var(--s2)", tip=f"{lb} — giochi dello stesso genere: {nv if nv is not None else 'n/d'}%"))
            rows.append([lb, TL.means(t), f"{cv}%" if cv is not None else "n/d", f"{nv}%" if nv is not None else "n/d"])
        leg = C.legend([("Giochi più simili al tuo", "var(--s1)")] + ([("Giochi dello stesso genere", "var(--s2)")] if n else []))
        svg, _ = C.hbar(items, aria=title, unit="%", label_w=230)
        table = _explain(["Voce", "Cosa conta (parole cercate nelle recensioni)", "Simili", "Genere"], rows, "Cosa vuol dire ogni voce")
        out.append(_chart((svg, table), title=title, why=why, leg=leg,
                          note="Conteggio automatico per parole chiave nelle recensioni in inglese: indica la tendenza, non è una lettura recensione per recensione."))
    feats = ((res or {}).get("features") or {}).get("all") or []
    feats = [f for f in feats if f.get("neg_share") is not None and f.get("pos_share") is not None]
    if feats:
        fl = TL.feature_labels(root)
        items, rows = [], []
        for f in feats:
            lb, mn = TL.feature_label(f["feature"], fl)
            diff = round(f["pos_share"] - f["neg_share"], 1)
            items.append(dict(label=lb, value=diff, color="var(--s1)" if diff >= 0 else "var(--s2)",
                              tip=f"{lb}: nelle positive {f['pos_share']}%, nelle negative {f['neg_share']}% — {TL.verdict_it(f.get('verdict'))}"))
            rows.append([lb, mn, f"{f['pos_share']}%", f"{f['neg_share']}%", TL.verdict_it(f.get("verdict"))])
        svg, _ = C.hbar(items, aria="Le caratteristiche del tuo gioco: piacciono o no?", unit=" punti", label_w=230)
        table = _explain(["Caratteristica", "Cosa vuol dire", "Citata nelle positive", "Citata nelle negative", "In parole semplici"], rows, "Leggi i numeri e cosa vuol dire")
        out.append(_chart((svg, table), title="Le caratteristiche del tuo gioco: ai giocatori piacciono o no?",
                          why="Nelle recensioni dei giochi simili, quanto se ne parla bene meno quanto se ne parla male. Barra verde a destra = piace; barra rossa a sinistra = dà fastidio; vicino a zero = divide o se ne parla poco.",
                          leg=C.legend([("Piace", "var(--s1)"), ("Dà fastidio", "var(--s2)")])))
    return out


def economics(root: str) -> list[str]:
    e = _json(os.path.join(root, "_raw", "econ.json"))
    if not e:
        return []
    out = []
    steps = e.get("per_copy") or []
    if steps:
        out.append(_chart(C.hbar([dict(label=s["step"], value=s["value"], tip=f"{s['step']}: {s['value']:.2f}", color="var(--s1)" if k in (0, len(steps) - 1) else "var(--axis)") for k, s in enumerate(steps)], aria="Dal prezzo al netto per copia", fmt=lambda v: f"{v:.2f}"),
                          title="Dal prezzo a quanto resta per copia", why=f"Ogni passaggio toglie una parte. Netto per copia: {e.get('net_per_copy', 0):.2f}."))
    sc = e.get("scenarios") or []
    be = (e.get("breakeven") or {}).get("copies_with_time")
    if sc:
        out.append(_chart(C.hbar([dict(label=s["name"], value=s["copies"], color="var(--s1)" if (not be or s["copies"] >= be) else "var(--s2)",
                                       tip=f"{s['name']}: {C.fmt_n(s['copies'])} copie da {C.fmt_n(s['wishlists'])} wishlist ({s['conversion']:.0%})") for s in sc],
                                 aria="Copie per scenario contro il break-even", ref=(be, "break-even") if be else None),
                          title="Copie per scenario contro il break-even", why="La linea tratteggiata è il numero di copie che copre i costi (tempo compreso). Blu = la supera, arancione = no.",
                          leg=C.legend([("sopra il break-even", "var(--s1)"), ("sotto", "var(--s2)")]), note="Conversioni e aliquote sono ipotesi dichiarate nel piano."))
        out.append(_chart(C.hbar([dict(label=s["name"], value=s["profit_cash"], color="var(--s1)" if s["profit_cash"] >= 0 else "var(--crit)", tip=f"{s['name']}: utile di cassa {C.fmt_n(s['profit_cash'])}") for s in sc], aria="Utile di cassa per scenario"),
                          title="Utile di cassa per scenario", why="Netto incassato meno i costi vivi. A sinistra dello zero si perde.", leg=C.legend([("utile", "var(--s1)"), ("perdita", "var(--crit)")])))
    sens = e.get("sensitivity") or []
    if sens and be:
        items = [dict(label="Piano base", value=be, tip=f"Piano base: {C.fmt_n(be)} copie")] + [dict(label=s["case"], value=s["breakeven_copies"], color="var(--s2)", tip=f"{s['case']}: {C.fmt_n(s['breakeven_copies'])} copie") for s in sens]
        out.append(_chart(C.hbar(items, aria="Break-even in copie e sensibilità"), title="Quanto è fragile il break-even", why="Copie necessarie se il prezzo cala, sale o i rimborsi raddoppiano."))
    return out


def plan(root: str, today: dt.date) -> list[str]:
    p = os.path.join(root, "calendar.md")
    if not os.path.exists(p):
        return []
    pl = ps.parse(open(p, encoding="utf-8").read())
    if not pl["phases"]:
        return []
    rows = []
    for ph in pl["phases"]:
        st = [ps.status_of(s, today) for s in ph["steps"]]
        rows.append(dict(label=re.sub(r"^FASE\s*\d+\s*[—-]\s*", "", ph["title"]), values=dict(done=st.count("done"), open=st.count("open"), overdue=st.count("overdue"))))
    ser = [("done", "Fatti", "var(--s1)"), ("open", "Da fare", "var(--axis)"), ("overdue", "In ritardo", "var(--crit)")]
    return [_chart(C.stacked(rows, ser, aria="Avanzamento dei passi per fase", percent=False), title="Avanzamento per fase", why="Quanti passi sono fatti, aperti o in ritardo in ogni fase del calendario.", leg=C.legend([(l, c) for _, l, c in ser]))]


def creators(root: str) -> list[str]:
    rows = _csv(os.path.join(root, "creators.csv"))
    if not rows:
        return []
    by: dict[str, dict] = {}
    for r in rows:
        k = (r.get("piattaforma") or "altro").strip() or "altro"
        pr = ((r.get("priorita") or "C").strip()[:1] or "C").upper()
        d = by.setdefault(k, dict(A=0, B=0, C=0))
        d[pr if pr in d else "C"] += 1
    data = [dict(label=k, values=v) for k, v in sorted(by.items(), key=lambda kv: -sum(kv[1].values()))]
    ser = [("A", "Priorità A", "var(--s1)"), ("B", "Priorità B", "var(--s3)"), ("C", "Priorità C", "var(--axis)")]
    return [_chart(C.stacked(data, ser, aria="Creator per piattaforma e priorità", percent=False), title=f"{len(rows)} creator per piattaforma", why="Dove sono i creator trovati e quanti sono da contattare per primi (priorità A).", leg=C.legend([(l, c) for _, l, c in ser]))]


def full_game(root: str) -> list[str]:
    st = _json(os.path.join(root, "status.json")) or {}
    gaps = [g for g in (st.get("full_game") or {}).get("gaps", []) if _num(g.get("hours")) is not None]
    if not gaps:
        return []
    items = [dict(label=g.get("area", ""), value=_num(g["hours"]), tip=f"{g.get('area')}: oggi {g.get('today')}, previsto {g.get('target')}. {g.get('action', '')}") for g in sorted(gaps, key=lambda g: -_num(g["hours"]))]
    tot = sum(i["value"] for i in items)
    return [_chart(C.hbar(items, aria="Ore per colmare i gap verso il gioco completo", unit=" h"), title="Dalla beta al gioco completo", why=f"Ore stimate per colmare ogni gap: in tutto circa {tot:.0f} ore.", note="Stime dal piano del gioco completo.")]


def criticita_charts(root: str) -> list[str]:
    """The whole criticalities card (one panel per wave, per gate, evolution) as a single wide block."""
    card, _ = cr.build(root, _json(os.path.join(root, "status.json")) or {}, bare=True)
    return [card] if card else []


def groups(root: str, today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    spec = [("product", "Prodotto", "Dove regge il gioco e cosa costa sistemarlo.", lambda: pillars(root)),
            ("criticita", "Criticità", "I problemi trovati, ondata per ondata e per cancello.", lambda: criticita_charts(root)),
            ("fg", "Focus group", "Come reagiscono i tester simulati, ondata dopo ondata.", lambda: focus_group(root)),
            ("market", "Mercato e comparabili", "Il genere in numeri, da dati pubblici.", lambda: market(root)),
            ("window", "Finestra di lancio", "Concorrenti, festival e saldi attorno alla tua data.", lambda: window(root)),
            ("reviews", "Recensioni reali", "Cosa dicono i giocatori dei giochi come il tuo.", lambda: reviews(root)),
            ("econ", "Economia", "Quanto resta, quanto serve, quanto è fragile.", lambda: economics(root)),
            ("plan", "Piano", "Avanzamento del calendario a passi.", lambda: plan(root, today)),
            ("creators", "Creator", "Chi contattare e dove.", lambda: creators(root)),
            ("fullgame", "Gioco completo", "Cosa manca alla beta per diventare il gioco finale.", lambda: full_game(root))]
    out = []
    for key, title, intro, fn in spec:
        try:
            ch = fn()
        except Exception as e:   # a malformed source file must not break the report: say so in the group instead
            ch = [f'<p class="note">Grafici di «{C.esc(title)}» non disponibili: {C.esc(type(e).__name__)}: {C.esc(e)}</p>']
        if ch:
            out.append(dict(key=key, title=title, intro=intro, charts=ch, wide=key == "criticita"))
    return out


def render(gs: list[dict], hide: set[str] = frozenset()) -> str:
    """HTML of the groups: a heading per group and a responsive grid of chart cards."""
    wide = ' style="grid-column:1/-1"'
    return "".join(f'<h3 class="gh">{C.esc(g["title"])}</h3><p class="sub">{C.esc(g["intro"])}</p><div class="cgrid">' + "".join(f'<div class="card"{wide if g.get("wide") else ""}>{c}</div>' for c in g["charts"]) + "</div>"
                   for g in gs if g["key"] not in hide)
