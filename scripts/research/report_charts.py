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


GRADE_IT = {"PASS": ("ok", "Regge"), "MARGINAL": ("warn", "Al limite"), "FAIL": ("crit", "Non regge")}
_GRADE = re.compile(r"\b(PASS|MARGINAL|FAIL)\b")


def _plain(t: str) -> str:
    """Markdown cell -> plain words: no **, no `file.cs` references, no [FATTO]/[STIMA] labels, no '(vedi ...)'."""
    t = re.sub(r"\(([^()]*`[^()]*)\)", "", t or "")            # parentheses that only cite files
    t = re.sub(r"`[^`]*`", "", t)
    t = re.sub(r"\[(FATTO|STIMA|OPINIONE|DA VERIFICARE)\]", "", t, flags=re.I)
    t = re.sub(r"[*_]", "", t)
    return re.sub(r"\s+([,.;:])", r"\1", re.sub(r"\s+", " ", t)).strip(" .;,")


def _first_sentence(t: str, n: int = 170) -> str:
    t = _plain(t)
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m and len(m.group(1)) >= 25 else t
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _hours(cell: str):
    """(low, high, what to do) from a cell such as '14-20 (perk iniziale; verifica)'. Hours only when the cell STARTS with a number
    or a range, the range is plausible (0 < h <= 300) and the column is about hours; otherwise (None, None, words)."""
    raw = re.sub(r"[*_`]", "", cell or "").strip()
    m = re.match(r"~?\s*(\d+(?:[.,]\d+)?)(?:\s*[-–]\s*(\d+(?:[.,]\d+)?))?\s*(?:h\b|ore\b)?\s*(.*)$", raw, re.S)
    if not m:
        return None, None, _plain(raw)
    lo = float(m.group(1).replace(",", "."))
    hi = float(m.group(2).replace(",", ".")) if m.group(2) else lo
    rest = m.group(3).strip()
    what = _plain(rest[1:-1] if rest.startswith("(") and rest.endswith(")") else rest)
    if not (0 < lo <= hi <= 300):
        return None, None, _plain(raw)
    return lo, hi, what


def pillar_rows(root: str) -> list[dict]:
    """Pillars of 01-dev.md: the table whose header names the pillar ("Pilastro"/"Pillar") and whose rows carry PASS / MARGINAL / FAIL.
    Each row: name, grade, qualifier ("con riserva", "provvisorio"...), reason (one line from the evidence), todo (words), hours (lo, hi) or None."""
    p = os.path.join(root, "01-dev.md")
    if not os.path.exists(p):
        return []
    lines = open(p, encoding="utf-8").read().splitlines()
    tables, cur = [], []
    for ln in lines + [""]:
        if ln.lstrip().startswith("|"):
            cur.append([c.strip() for c in ln.strip().strip("|").split("|")])
        elif cur:
            tables.append(cur)
            cur = []
    best = []
    for t in tables:
        if len(t) < 3:
            continue
        head = [h.lower() for h in t[0]]
        body = [r for r in t[2:] if any(_GRADE.search(c.upper()) for c in r[1:])]
        if not body:
            continue
        find = lambda rx: next((k for k, h in enumerate(head) if re.search(rx, h)), None)
        c_name = find(r"pilastr|pillar|nome|area")
        c_grade = find(r"voto|esito|stato|grade|giudizio")
        c_why = find(r"evidenz|perch|motiv|nota|why|evidence")
        c_hours = find(r"\bore\b|hours|costo")
        c_todo = find(r"cosa fare|azione|intervento|fix")
        if c_name is None:
            c_name = next((k for k, h in enumerate(head) if h.strip() not in ("#", "n", "n.")), 0)
        rows = []
        for r in body:
            r = r + [""] * (len(head) - len(r))
            gi = c_grade if c_grade is not None else next(k for k, c in enumerate(r) if _GRADE.search(c.upper()))
            m = _GRADE.search(r[gi].upper())
            if not m:
                continue
            qual = _plain(re.sub(r"\[?\b(PASS|MARGINAL|FAIL)\b\]?", "", re.sub(r"\(era [^)]*\)", "", r[gi]), flags=re.I))
            lo = hi = None
            todo = _plain(r[c_todo]) if c_todo is not None else ""
            if c_hours is not None:
                lo, hi, what = _hours(r[c_hours])
                todo = todo or what
            rows.append(dict(name=_plain(r[c_name]) or "?", grade=m.group(1), qualifier=qual, reason=_first_sentence(r[c_why]) if c_why is not None else "",
                             todo=todo if len(todo) <= 220 else todo[:219].rstrip() + "…", hours=(lo, hi) if lo is not None else None))
        if len(rows) > len(best) and (c_name is not None):
            best = rows
            if re.search(r"pilastr|pillar", " ".join(head)):
                break
    return best


def pillars(root: str) -> list[str]:
    """Pillars of 01-dev.md: how many hold (one bar) and, below, every pillar by NAME with its grade, why, and what to do."""
    rows = pillar_rows(root)
    if not rows:
        return []
    cnt = {g: sum(1 for r in rows if r["grade"] == g) for g in STATUS}
    svg, _ = C.stacked([dict(label=f"{len(rows)} pilastri", values=cnt)], [("PASS", "Regge", STATUS["PASS"]), ("MARGINAL", "Al limite", STATUS["MARGINAL"]), ("FAIL", "Non regge", STATUS["FAIL"])], aria="Pilastri del genere per esito", percent=False)
    order = {"FAIL": 0, "MARGINAL": 1, "PASS": 2}
    any_hours = any(r["hours"] for r in rows)
    body = []
    for r in sorted(rows, key=lambda r: order[r["grade"]]):
        kind, word = GRADE_IT[r["grade"]]
        h = r["hours"]
        hours = "" if not h else (f"{h[0]:g}" if h[0] == h[1] else f"{h[0]:g}-{h[1]:g}").replace(".", ",") + " h"
        todo = r["todo"] or ("—" if r["grade"] != "PASS" else "niente di urgente")
        body.append(f'<tr><td><strong>{C.esc(r["name"])}</strong></td><td class="nw"><span class="pill {kind}">{C.esc(word)}</span>'
                    + (f'<br><span class="note">{C.esc(r["qualifier"])}</span>' if r["qualifier"] else "") + f'</td><td>{C.esc(r["reason"])}</td><td>{C.esc(todo)}</td>'
                    + (f'<td class="n nw">{C.esc(hours) or "—"}</td>' if any_hours else "") + "</tr>")
    head = "<th>Pilastro</th><th>Esito</th><th>Perché, in una riga</th><th>Cosa fare</th>" + ('<th class="n nw">Ore stimate</th>' if any_hours else "")
    table = f'<div class="wrap"><table class="ptab"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    leg = C.legend([("Regge (PASS)", STATUS["PASS"]), ("Al limite (MARGINAL)", STATUS["MARGINAL"]), ("Non regge (FAIL)", STATUS["FAIL"])])
    note = ("Le ore sono la stima dell'audit per arrivare a «regge», scritte accanto a ogni pilastro in 01-dev.md: non sono misure." if any_hours
            else "L'audit non dà una stima di ore per pilastro: conta cosa fare, non un numero inventato.")
    return [f'<div class="chartbox"><h3>Pilastri del genere</h3><p class="why">I punti su cui un gioco di questo genere vive o muore. Prima quelli che non reggono, poi quelli al limite.</p>{leg}'
            f'<div class="chart">{svg}<div class="tip" role="status"></div></div>{table}<p class="note">{C.esc(note)}</p></div>']


_WAVES_CACHE: dict = {}


def wave_files(root: str) -> list[dict]:
    """Every wave file (validated by fg_waves, with "stage" inferred from the name or the label), ordered by wave number."""
    import glob
    key = os.path.abspath(root)
    files = sorted(glob.glob(os.path.join(root, "fg", "waves", "w[0-9]*.json")))
    sig = tuple((f, os.path.getmtime(f)) for f in files)
    if _WAVES_CACHE.get(key, (None,))[0] == sig:
        return _WAVES_CACHE[key][1]
    out = []
    try:
        import fg_waves
        rp = os.path.join(root, "fg", "roster.json")
        roster = _json(rp) if os.path.exists(rp) else None
        for f in files:
            try:
                out.append(fg_waves.load_wave(f, roster))
            except (SystemExit, Exception):
                continue
    except ImportError:
        pass
    out.sort(key=lambda w: (int(w["wave"]), w.get("stage") == "full"))
    _WAVES_CACHE[key] = (sig, out)
    return out


def stage_of(root: str) -> dict:
    """{wave number (str): "beta" | "full" | ""}."""
    return {str(w["wave"]): w.get("stage") or "" for w in wave_files(root)}


def latest_waves(root: str) -> dict:
    """{"beta": wave, "full": wave}: the latest wave of each kind (unlabelled waves count as beta)."""
    out = {}
    for w in wave_files(root):
        out["full" if w.get("stage") == "full" else "beta"] = w
    return out


def share_raising(w: dict, keys) -> float | None:
    """% of the wave's testers who raised at least one of `keys` (None if no key is given)."""
    keys = set(keys or [])
    if not keys or not w or not w.get("testers"):
        return None
    n = sum(1 for t in w["testers"] if keys & set(t.get("issues") or []))
    return round(100 * n / len(w["testers"]), 1)


STAGE_SHORT = {"beta": "beta", "full": "completo", "": ""}


def focus_group(root: str) -> list[str]:
    rows = _csv(os.path.join(root, "fg", "timeline.csv"))
    if not rows:
        return []
    stg = stage_of(root)
    for r in rows:
        r["_stage"] = (r.get("stage") or stg.get(str(r.get("wave")), "")).strip()
        r["_lab"] = f"Ondata {r['wave']}" + (f" · {STAGE_SHORT.get(r['_stage'], r['_stage'])}" if r["_stage"] else "")
    out = []
    ser = [("w", "Wishlist subito", "var(--s1)"), ("s", "Aspetta i saldi", "var(--s3)"), ("i", "Scorre oltre", "var(--muted)"), ("r", "Compra e rimborsa", "var(--crit)")]
    data = [dict(label=r["_lab"], values=dict(w=_num(r["wishlist_pct"]) or 0, s=_num(r["saldi_pct"]) or 0, i=_num(r["ignoro_pct"]) or 0, r=_num(r["refund_pct"]) or 0),
                 tip=f"{r['_lab']} ({r['date']}): wishlist {r['wishlist_pct']}%, saldi {r['saldi_pct']}%, ignora {r['ignoro_pct']}%, rimborso {r['refund_pct']}%") for r in rows]
    out.append(_chart(C.stacked(data, ser, aria="Verdetti dei tester per ondata"), title="Cosa farebbero i tester", why="Come si distribuiscono i verdetti a ogni ondata: più blu e meno grigio e rosso = meglio.",
                      leg=C.legend([(l, c) for _, l, c in ser]), note="Panel simulato: ordina i problemi, non prevede le vendite."))
    betas = [r for r in rows if r["_stage"] != "full"]
    last = betas[-1] if betas else rows[-1]
    b = [dict(label="Punteggio wishlist", value=_num(last["score"]), target=_num(last.get("gate")), max=100, tip=f"Punteggio {last['score']} contro soglia {last.get('gate')}"),
         dict(label="Click al primo sguardo", value=_num(last["click_pct"]), unit="%"), dict(label="Pitch capito", value=_num(last["pitch_pct"]), unit="%")]
    if _num(last.get("buy_pct")) is not None:
        b.append(dict(label="Pagherebbe il prezzo", value=_num(last["buy_pct"]), unit="%", tip=f"Pagherebbe il prezzo previsto all'uscita: {last['buy_pct']}% dei tester"))
    if _num(last.get("ceiling")) is not None:
        b.insert(1, dict(label="Tetto di questa versione", value=_num(last["ceiling"]), max=100, tip=f"Tetto di questa versione {str(last['ceiling']).replace('.', ',')}: il punteggio con le sole correzioni possibili adesso. Margine ancora da prendere: {last.get('headroom')} punti"))
    if _num(last.get("ceiling_full")) is not None:
        b.insert(2 if _num(last.get("ceiling")) is not None else 1, dict(label="Tetto gioco completo", value=_num(last["ceiling_full"]), max=100, tip=f"Tetto del gioco completo {str(last['ceiling_full']).replace('.', ',')}: con i contenuti pianificati, non è margine di oggi"))
    out.append(_chart(C.bullets(b, aria="Indicatori dell'ultima ondata"), title=f"Ultima {last['_lab'].lower()}", why="Il segno nero è la soglia: la barra deve arrivarci. Il tetto di questa versione è il massimo con le sole correzioni possibili adesso; quello del gioco completo conta i contenuti pianificati. Click, pitch e acquisto sono percentuali di tester."))
    issues = _top_issues(root)
    if issues:
        out.append(issues)
    return out


def _top_issues(root: str) -> str | None:
    lw = latest_waves(root)
    w = lw.get("beta") or lw.get("full")
    if not w:
        return None
    try:
        import fg_waves
        m = fg_waves.metrics(w)
    except (SystemExit, Exception):   # invalid wave file: the chart is simply not drawn
        return None
    owner = cr.load_owner(root)
    now = [i for i in m["issues"] if cr.is_now(i["key"], owner)]
    its = now[:8]
    if not its:
        return None
    hidden = len(m["issues"]) - len(now)
    lab = f"ondata {m['wave']}" + (f" ({cr.STAGE_LABEL.get(w.get('stage'), '')})" if w.get("stage") else "")
    return _chart(C.hbar([dict(label=i["label"], value=i["pct"], color=SEV.get(i["severity"], "var(--muted)"), tip=f"{i['label']}: {i['freq']} tester su {m['n']} ({i['severity']}). Decisione: {cr.owner_text(i['key'], owner)}") for i in its], aria="Critiche più frequenti", unit="%"),
                  title="Critiche da affrontare adesso", why=f"Quota di tester che le solleva nell'ultima {lab}, solo quelle senza una decisione chiusa. Il colore è la gravità.",
                  leg=C.legend([("alta", SEV["alta"]), ("media", SEV["media"]), ("bassa", SEV["bassa"])]),
                  note=(f"Altre {hidden} critiche di questa ondata sono già decise (risolte, pianificate, accettate): sono nella sezione Criticità." if hidden else ""))


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


def _ours_cells(theme: str, kind: str, t05: dict, tmap: dict, lw: dict, owner: dict, TL) -> tuple[str, str, str, str]:
    """(il tuo gioco, tester beta, tester completo, decisione) for one review theme, in plain words."""
    row = TL.ours(theme, kind, t05)
    mine = " / ".join(row["tags"]) if row else "non valutato"
    keys = tmap.get(theme) or []
    sb, sf = share_raising(lw.get("beta"), keys), share_raising(lw.get("full"), keys)
    f = lambda v: "—" if v is None else f"{v:g}".replace(".", ",") + "%"
    decs = []
    for k in keys:
        if k in owner:
            t = cr.owner_text(k, owner).split(":")[0]
            if t not in decs:
                decs.append(t)
    return mine, f(sb), f(sf), ", ".join(decs) or ("da decidere" if keys and (sb or sf) else "—")


def reviews(root: str) -> list[str]:
    import theme_labels as TL
    res = _json(os.path.join(root, "_raw", "corpus.json"))
    g = (res or {}).get("groups") or {}
    t05, tmap, lw, owner = TL.read_05b(root), TL.theme_issues(root), latest_waves(root), cr.load_owner(root)
    wb, wf = lw.get("beta"), lw.get("full")
    wlab = lambda w, word: f"ondata {w['wave']}, {word}" if w else word
    out = []
    for key, title, why, mine_head, raise_word in (
            ("punished", "Di cosa si lamentano i giocatori",
             "Su 100 recensioni negative dei giochi simili, quante parlano di ciascun problema. Barra lunga = lamentela frequente. Sotto: se il TUO gioco rischia lo stesso.", "Il tuo gioco ne soffre?", "lo pensano"),
            ("rewarded", "Cosa piace ai giocatori",
             "Su 100 recensioni positive dei giochi simili, quante lodano ciascuna cosa. Barra lunga = motivo di gradimento frequente. Sotto: se il TUO gioco ce l'ha.", "Ce l'hai?", "dicono che manca")):
        c, n = {r["theme"]: r for r in (g.get("comps") or {}).get(key, [])}, {r["theme"]: r for r in (g.get("genre") or {}).get(key, [])}
        themes = sorted(set(c) | set(n), key=lambda t: -max((c.get(t) or {}).get("macro_pct", 0), (n.get(t) or {}).get("macro_pct", 0)))[:7]
        if not themes:
            continue
        items, rows, ours_rows = [], [], []
        for t in themes:
            lb = TL.label(t)
            cv, nv = (c.get(t) or {}).get("macro_pct"), (n.get(t) or {}).get("macro_pct")
            mine, sb, sf, dec = _ours_cells(t, key, t05, tmap, lw, owner, TL)
            ours_txt = f"Il tuo gioco: {mine}" if key == "punished" else f"Ce l'hai? {mine}"
            if sb != "—" or sf != "—":
                ours_txt += f" · {raise_word} {sb} dei tester (beta)" + (f", {sf} (completo)" if sf != "—" else "")
            items.append(dict(label=lb, value=cv, color="var(--s1)", tip=f"{lb} — giochi più simili al tuo: {cv if cv is not None else 'n/d'}% (in {(c.get(t) or {}).get('breadth', '-')} giochi)\n{ours_txt}"))
            if n:
                items.append(dict(label="", value=nv, color="var(--s2)", tip=f"{lb} — giochi dello stesso genere: {nv if nv is not None else 'n/d'}%\n{ours_txt}"))
            rows.append([lb, TL.means(t), f"{cv}%" if cv is not None else "n/d", f"{nv}%" if nv is not None else "n/d", mine, sb, sf])
            row05 = TL.ours(t, key, t05)
            ours_rows.append((lb, mine, sb, sf, dec, row05["text"] if row05 else ""))
        leg = C.legend([("Giochi più simili al tuo", "var(--s1)")] + ([("Giochi dello stesso genere", "var(--s2)")] if n else []))
        svg, _ = C.hbar(items, aria=title, unit="%", label_w=230)
        kinds = {"sì": "crit", "a rischio": "warn", "no": "ok", "in parte": "warn", "non valutabile": "mute", "non valutato": "mute"} if key == "punished" else \
                {"sì": "ok", "in parte": "warn", "no": "crit", "non valutabile": "mute", "non valutato": "mute", "a rischio": "warn"}
        kind_of = lambda x: next((kinds[k] for k in sorted(kinds, key=len, reverse=True) if x.startswith(k)), "mute")
        pill = lambda m: " ".join(f'<span class="pill {kind_of(x)}">{C.esc(x)}</span>' for x in m.split(" / "))
        vis = ('<div class="wrap"><table class="ours"><thead><tr><th>Voce</th>' + f"<th>{C.esc(mine_head)}</th>"
               + f'<th class="n nw">Tester beta<br><span class="note">{C.esc(wlab(wb, "ultima"))}</span></th><th class="n nw">Tester completo<br><span class="note">{C.esc(wlab(wf, "ultima"))}</span></th><th>Cosa hai deciso</th></tr></thead><tbody>'
               + "".join(f'<tr><td><strong>{C.esc(lb)}</strong></td><td>{pill(mine)}' + (f'<br><span class="note">{C.esc(txt)}</span>' if txt else "") + f'</td><td class="n nw">{C.esc(sb)}</td><td class="n nw">{C.esc(sf)}</td><td>{C.esc(dec)}</td></tr>'
                         for lb, mine, sb, sf, dec, txt in ours_rows) + "</tbody></table></div>")
        table = _explain(["Voce", "Cosa conta (parole cercate nelle recensioni)", "Simili", "Genere", mine_head, "Tester beta", "Tester completo"], rows, "Cosa vuol dire ogni voce (tabella completa)")
        src = os.path.join(root, "05b-critiche-reali.md")
        when = dt.date.fromtimestamp(os.path.getmtime(src)).isoformat() if os.path.exists(src) else None
        explain = ("«Il tuo gioco» viene dalla tabella di 05b-critiche-reali.md" + (f" (aggiornata il {when}: va rivista dopo ogni fix importante)" if when else " (non ancora scritta)") + ". Le colonne «Tester» dicono quanti tester simulati, "
                   "nell'ultima ondata beta e in quella del gioco completo, hanno sollevato il problema collegato" + (" (cioè dicono che manca)" if key == "rewarded" else "") + ".")
        out.append(C.wrap(svg, title=title, why=why, leg=leg, table=vis + table, note="Conteggio automatico per parole chiave nelle recensioni in inglese: indica la tendenza, non è una lettura recensione per recensione. " + explain))
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
