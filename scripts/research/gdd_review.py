#!/usr/bin/env python3
"""Idea and GDD review (mode "Revisione GDD", references/10-revisione-gdd.md; contract dev-link.md §10).

One JSON is the source, launch/_raw/gdd_review.json; the page to read, launch/gdd-review.md, is rendered from it.
The script never judges the idea: Claude fills the JSON with the research (comparables, genre benchmark, real reviews,
calibration, flop cases). The script keeps the review honest and usable:

  - the owner's dial: how much the GDD may change (1 ritocchi · 2 struttura · 3 tutto in discussione) and what is untouchable
    (the engine always). No proposal above the dial, none on an untouchable.
  - a scorecard of the idea on 10 fixed areas, each with a 1-5 score, a label ([FATTO] needs a source) and the reason.
  - proposals P-GDD-n with the GDD section, current and proposed text (ready to paste), evidence, impact, hours, risk,
    what is lost, and the owner's answer (da_decidere / accettata / rifiutata, with date).
  - enough ambition for the dial: >= 3 proposals; dial 2 -> >= 2 structural ones; dial 3 -> >= 2 concept alternatives.

  gdd_review.py init    --launch-dir launch --gdd GDD.md [--date AAAA-MM-GG]   skeleton (never overwrites)
  gdd_review.py check   --launch-dir launch [--json]                           errors exit 1, warnings only print
  gdd_review.py render  --launch-dir launch [--md launch/gdd-review.md]
  gdd_review.py decide  --launch-dir launch P-GDD-1 [P-GDD-2 ...] accettata|rifiutata|da_decidere [--date D] [--note T]
  gdd_review.py pending --launch-dir launch --decisions DECISIONI.md [--json]  accepted, not yet applied to the GDD (read only;
                                                                               applied = DECISIONI.md cites the P-GDD-n)
  gdd_review.py self-test
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile

try:
    import common  # noqa: F401  (side effect: UTF-8 stdout on a Windows console)
except ImportError:  # pragma: no cover
    pass

RAW = os.path.join("_raw", "gdd_review.json")
LEVELS = {1: "Ritocchi", 2: "Struttura", 3: "Tutto in discussione"}
LEVEL_HELP = {1: "il concept resta; si rinforzano gancio, chiarezza, prima ora, scope",
              2: "stessa idea e stesso tema; possono cambiare loop, progressione, modalità, durata, scope, pitch",
              3: "si può cambiare anche genere, verbo centrale, ambientazione o pubblico; con versioni alternative del concept"}
LEVEL_GROUP = {1: "Ritocchi", 2: "Cambi di struttura", 3: "Cambi di concept (versioni alternative)"}
TOUCH = {"engine": "motore", "genere": "genere", "tema": "tema e ambientazione", "stile": "stile grafico", "verbo": "verbo centrale",
         "loop": "loop centrale", "progressione": "progressione", "modalita": "modalità", "contenuti": "contenuti e durata",
         "onboarding": "prima ora e onboarding", "pitch": "pitch e gancio", "scope": "scope e tempi", "piattaforma": "piattaforma",
         "prezzo": "prezzo e modello", "pubblico": "pubblico", "multiplayer": "multiplayer e co-op", "ui": "interfaccia"}
AREAS = [("gancio", "Gancio e pitch: si capisce in 5 secondi?"),
         ("differenza", "Differenza dai giochi simili"),
         ("mercato", "Domanda del genere e affollamento"),
         ("loop", "Loop centrale: cosa premiano e puniscono le recensioni del genere"),
         ("progressione", "Progressione, rigiocabilità e durata"),
         ("prima_ora", "Prima ora e onboarding"),
         ("clip", "Si mostra bene: clip, streamer, capsule"),
         ("scope", "Scope contro tempo e squadra"),
         ("prezzo", "Prezzo e valore percepito"),
         ("rischio_flop", "Rischi da flop (casi reali)")]
LABELS = ("[FATTO]", "[STIMA]", "[OPINIONE]", "[DA VERIFICARE]")
STATUS = ("da_decidere", "accettata", "rifiutata")
STATUS_WORD = {"da_decidere": "○ da decidere", "accettata": "✓ accettata", "rifiutata": "✗ rifiutata"}
VERDICTS = ("forte", "promettente", "fragile", "da ripensare")
PID = re.compile(r"^P-GDD-\d+$")


# ---------------------------------------------------------------------------------------------------- io
def raw_path(launch_dir: str) -> str:
    return os.path.join(launch_dir, RAW)


def load(launch_dir: str) -> dict:
    p = raw_path(launch_dir)
    if not os.path.exists(p):
        raise SystemExit(f"{p} non c'è: prima `gdd_review.py init`")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(launch_dir: str, data: dict) -> None:
    p = raw_path(launch_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def gdd_outline(path: str) -> dict:
    """Front-matter keys and ## sections of the GDD, so proposals can name a section that exists."""
    if not path or not os.path.exists(path):
        return {"keys": [], "sections": [], "status": ""}
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    keys, status = [], ""
    fm = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if fm:
        for line in fm.group(1).splitlines():
            m = re.match(r"^([A-Za-z][\w-]*)\s*:\s*(.*)$", line)
            if m:
                keys.append(m.group(1))
                if m.group(1) == "status":
                    status = m.group(2).strip()
    if not status:
        m = re.search(r"^\**status\**\s*:\s*(\w+)", text, re.M | re.I)
        status = m.group(1) if m else ""
    sections = [m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", text, re.M)]
    return {"keys": keys, "sections": sections, "status": status}


# ---------------------------------------------------------------------------------------------------- init
def skeleton(gdd: str, date: str) -> dict:
    o = gdd_outline(gdd)
    return {
        "date": date, "gdd": gdd.replace("\\", "/"), "gdd_status": o["status"], "gdd_sections": o["sections"], "gdd_keys": o["keys"],
        "dial": {"level": None, "untouchable": ["engine"], "owner_words": "", "asked": ""},
        "product": "",                                  # slice / beta / gioco completo, as the owner said
        "verdict": {"idea": "", "one_line": "", "best_move": "", "strengths": [], "weak_spots": []},
        "scorecard": [{"area": k, "score": None, "label": "", "why": "", "source": ""} for k, _ in AREAS],
        "comps": [],                                    # {"name", "appid", "why_close", "result", "source"}
        "proposals": [],
        "panel": {},                                    # optional, SIMULATO: {"size", "method", "results": [{"version", ...}]}
        "sources": [],
    }


def cmd_init(a) -> int:
    p = raw_path(a.launch_dir)
    if os.path.exists(p):
        print(f"{p} esiste già: non lo tocco")
        return 0
    save(a.launch_dir, skeleton(a.gdd, a.date or dt.date.today().isoformat()))
    print(f"scritto {p}")
    return 0


# ---------------------------------------------------------------------------------------------------- check
def _hours_ok(v) -> bool:
    if isinstance(v, (int, float)) and v >= 0:
        return True
    return isinstance(v, str) and bool(re.fullmatch(r"\s*\d+(\.\d+)?\s*(-\s*\d+(\.\d+)?)?\s*h?\s*", v))


def check(data: dict, today: str | None = None) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    dial = data.get("dial") or {}
    level = dial.get("level")
    untouch = set(dial.get("untouchable") or []) | {"engine"}
    if level not in LEVELS:
        errs.append("dial.level mancante: chiedi al proprietario quanto è disposto a cambiare il GDD (1, 2 o 3)")
        level = 3
    bad = [u for u in untouch if u not in TOUCH]
    if bad:
        warns.append(f"intoccabili fuori vocabolario (non controllabili): {', '.join(bad)}")

    v = data.get("verdict") or {}
    if v.get("idea") not in VERDICTS:
        errs.append(f"verdict.idea deve essere uno di: {', '.join(VERDICTS)}")
    for k in ("one_line", "best_move"):
        if not str(v.get(k) or "").strip():
            errs.append(f"verdict.{k} vuoto")

    areas = {s.get("area"): s for s in data.get("scorecard") or [] if isinstance(s, dict)}
    for key, name in AREAS:
        s = areas.get(key)
        if not s:
            errs.append(f"pagella: manca l'area '{key}'")
            continue
        if s.get("score") not in (1, 2, 3, 4, 5):
            errs.append(f"pagella {key}: voto 1-5 mancante")
        if s.get("label") not in LABELS:
            errs.append(f"pagella {key}: etichetta mancante ({' '.join(LABELS)})")
        if not str(s.get("why") or "").strip():
            errs.append(f"pagella {key}: manca il perché")
        if s.get("label") == "[FATTO]" and not str(s.get("source") or "").strip():
            errs.append(f"pagella {key}: [FATTO] senza fonte")
    if sum(1 for s in areas.values() if s.get("label") == "[OPINIONE]") > 5:
        warns.append("più di metà della pagella è [OPINIONE]: servono i dati (comparabili, recensioni, calibrazione)")

    comps = [c for c in data.get("comps") or [] if isinstance(c, dict)]
    if len(comps) < 5:
        warns.append(f"solo {len(comps)} comparabili: il metro regge meglio con 5-15 giochi veri")
    for c in comps:
        if not c.get("source") and not c.get("appid"):
            warns.append(f"comparabile '{c.get('name', '?')}' senza appid né fonte")

    props = [p for p in data.get("proposals") or [] if isinstance(p, dict)]
    ids = [p.get("id") for p in props]
    for dup in sorted({i for i in ids if ids.count(i) > 1 and i}):
        errs.append(f"ID ripetuto: {dup}")
    if len(props) < 3:
        errs.append(f"solo {len(props)} proposte: ne servono almeno 3")
    sections = data.get("gdd_sections") or []
    for p in props:
        pid = p.get("id") or "?"
        if not PID.match(str(pid)):
            errs.append(f"{pid}: l'ID deve essere P-GDD-n")
        lv = p.get("level")
        if lv not in LEVELS:
            errs.append(f"{pid}: livello 1-3 mancante")
        elif lv > level:
            errs.append(f"{pid}: livello {lv} sopra quello scelto dal proprietario ({level})")
        touched = set(p.get("touches") or [])
        if not touched:
            errs.append(f"{pid}: `touches` vuoto (cosa del gioco cambia: {', '.join(TOUCH)})")
        hit = sorted(touched & untouch)
        if hit:
            errs.append(f"{pid}: tocca un intoccabile ({', '.join(TOUCH.get(h, h) for h in hit)})")
        for k in ("title", "gdd_section", "proposed", "why", "impact", "risk", "loses"):
            if not str(p.get(k) or "").strip():
                errs.append(f"{pid}: campo `{k}` vuoto")
        if "now" not in p:
            errs.append(f"{pid}: manca `now` (testo attuale del GDD, o \"assente\")")
        if not _hours_ok(p.get("cost_hours")):
            errs.append(f"{pid}: `cost_hours` deve essere ore (numero o \"a-b\")")
        sec = str(p.get("gdd_section") or "")
        if sections and sec and not any(sec.lower() in s.lower() or s.lower() in sec.lower() for s in sections) \
                and sec.lower() not in ("nuova sezione", "front matter") and not sec.lower().startswith("nuova"):
            warns.append(f"{pid}: la sezione '{sec}' non è tra le sezioni del GDD")
        ev = [e for e in p.get("evidence") or [] if isinstance(e, dict)]
        if not ev:
            errs.append(f"{pid}: nessuna prova in `evidence`")
        for e in ev:
            if e.get("label") not in LABELS:
                errs.append(f"{pid}: prova senza etichetta valida")
            elif e.get("label") == "[FATTO]" and not str(e.get("source") or "").strip():
                errs.append(f"{pid}: prova [FATTO] senza fonte")
        if lv in (2, 3) and ev and all(e.get("label") == "[OPINIONE]" for e in ev):
            warns.append(f"{pid}: cambio di livello {lv} sostenuto solo da opinioni")
        st = p.get("status", "da_decidere")
        if st not in STATUS:
            errs.append(f"{pid}: stato '{st}' non valido ({', '.join(STATUS)})")
        elif st != "da_decidere" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p.get("decided") or "")):
            errs.append(f"{pid}: {st} senza data (`decided`)")
        if p.get("reopens") and not re.search(r"D-\d+|\w", str(p["reopens"])):
            warns.append(f"{pid}: `reopens` non dice quale decisione")

    by_level = {n: sum(1 for p in props if p.get("level") == n) for n in LEVELS}
    if level >= 2 and by_level[2] < 2 and not data.get("no_structural_reason"):
        errs.append("livello 2+: servono almeno 2 proposte di struttura (o `no_structural_reason` con il perché)")
    if level == 3 and by_level[3] < 2 and not data.get("no_concept_reason"):
        errs.append("livello 3: servono almeno 2 versioni alternative del concept (o `no_concept_reason` con il perché)")
    if level >= 2 and by_level[1] == 0:
        warns.append("nessun ritocco: anche con cambi grandi servono le correzioni piccole e sicure")

    panel = data.get("panel") or {}
    if panel and not panel.get("results"):
        warns.append("panel senza risultati: toglilo o compilalo")
    return errs, warns


def cmd_check(a) -> int:
    errs, warns = check(load(a.launch_dir))
    if a.json:
        print(json.dumps({"ok": not errs, "errors": errs, "warnings": warns}, ensure_ascii=False))
    else:
        for e in errs:
            print("❌ " + e)
        for w in warns:
            print("⚠ " + w)
        print("✅ revisione completa" if not errs else f"{len(errs)} errori")
    return 1 if errs else 0


# ---------------------------------------------------------------------------------------------------- render
def _cell(t) -> str:
    return str(t if t is not None else "").replace("|", "/").replace("\n", " ").strip()


def _bar(score) -> str:
    return ("■" * score + "□" * (5 - score)) if score in (1, 2, 3, 4, 5) else "—"


def _quote(text: str) -> list[str]:
    return ["> " + l if l.strip() else ">" for l in str(text).strip().splitlines()] or ["> (vuoto)"]


def render(data: dict) -> str:
    dial = data.get("dial") or {}
    level = dial.get("level")
    v = data.get("verdict") or {}
    props = [p for p in data.get("proposals") or [] if isinstance(p, dict)]
    L = [f"# Revisione dell'idea e del GDD — {data.get('date', '')}", "",
         "> Come leggerla: una **pagella** dell'idea confrontata con giochi veri, poi le **proposte** per migliorarla, divise per quanto "
         "cambiano il gioco. Ogni affermazione ha un'etichetta: **[FATTO]** dato con fonte · **[STIMA]** calcolo · **[OPINIONE]** giudizio "
         "con le sue ragioni · **[DA VERIFICARE]**. Il GDD lo cambia solo il proprietario: ogni proposta si accetta o si rifiuta.", ""]
    L += ["## In breve", "",
          f"- **L'idea oggi:** {v.get('idea', '—')}. {v.get('one_line', '')}",
          f"- **La mossa che conta di più:** {v.get('best_move', '—')}"]
    if v.get("strengths"):
        L.append("- **Punti forti:** " + "; ".join(map(str, v["strengths"])))
    if v.get("weak_spots"):
        L.append("- **Punti deboli:** " + "; ".join(map(str, v["weak_spots"])))
    if data.get("product"):
        L.append(f"- **Cosa descrive il GDD:** {data['product']}")
    L.append("")

    L += ["## Quanto si può cambiare (scelta del proprietario)", ""]
    if level in LEVELS:
        L.append(f"- **Livello {level}: {LEVELS[level]}** — {LEVEL_HELP[level]}.")
    else:
        L.append("- Livello non ancora scelto.")
    unt = [TOUCH.get(u, u) for u in (dial.get("untouchable") or [])]
    L.append("- **Intoccabili:** " + (", ".join(unt) if unt else "motore"))
    if dial.get("owner_words"):
        L.append(f"- **Parole del proprietario:** {dial['owner_words']}")
    L.append("")

    L += ["## Pagella dell'idea", "", "| Area | Voto | Perché | Etichetta e fonte |", "|---|---|---|---|"]
    areas = {s.get("area"): s for s in data.get("scorecard") or [] if isinstance(s, dict)}
    scores = []
    for key, name in AREAS:
        s = areas.get(key, {})
        if s.get("score") in (1, 2, 3, 4, 5):
            scores.append(s["score"])
        L.append(f"| {name} | {_bar(s.get('score'))} {s.get('score') or ''} | {_cell(s.get('why'))} | {_cell(s.get('label'))} {_cell(s.get('source'))} |")
    if scores:
        L += ["", f"Media {sum(scores) / len(scores):.1f} su 5 ({len(scores)} aree). Un 2 o meno è un punto da sistemare prima di costruire."]
    L.append("")

    comps = [c for c in data.get("comps") or [] if isinstance(c, dict)]
    if comps:
        L += ["## Giochi simili usati come metro", "", "| Gioco | Perché è vicino | Com'è andato | Fonte |", "|---|---|---|---|"]
        for c in comps:
            name = _cell(c.get("name"))
            if c.get("appid"):
                name = f"[{name}](https://store.steampowered.com/app/{_cell(c['appid'])}/)"
            L.append(f"| {name} | {_cell(c.get('why_close'))} | {_cell(c.get('result'))} | {_cell(c.get('source'))} |")
        L.append("")

    L += ["## Proposte", ""]
    for lv in (1, 2, 3):
        group = [p for p in props if p.get("level") == lv]
        if not group:
            continue
        L += [f"### {LEVEL_GROUP[lv]}", ""]
        for p in group:
            st = STATUS_WORD.get(p.get("status", "da_decidere"), p.get("status"))
            when = f" il {p['decided']}" if p.get("decided") and p.get("status") != "da_decidere" else ""
            L += [f"#### {p.get('id')} · {p.get('title', '')} — {st}{when}", "",
                  f"- **Sezione del GDD:** {p.get('gdd_section', '')} · **cosa tocca:** {', '.join(TOUCH.get(t, t) for t in p.get('touches') or [])}",
                  f"- **Perché:** {p.get('why', '')}",
                  f"- **Effetto atteso:** {p.get('impact', '')}",
                  f"- **Costo:** {p.get('cost_hours', '')} h [STIMA] · **rischio:** {p.get('risk', '')} · **cosa si perde:** {p.get('loses', '')}"]
            if p.get("reopens"):
                L.append(f"- **Riapre la decisione:** {p['reopens']}")
            for e in p.get("evidence") or []:
                if isinstance(e, dict):
                    src = f" ({e['source']})" if e.get("source") else ""
                    L.append(f"- {e.get('label', '')} {e.get('text', '')}{src}")
            if p.get("note"):
                L.append(f"- **Nota del proprietario:** {p['note']}")
            L += ["", "Oggi nel GDD:", ""] + _quote(p.get("now") or "assente") + ["", "Proposto (da incollare):", ""] + _quote(p.get("proposed", "")) + [""]

    panel = data.get("panel") or {}
    if panel.get("results"):
        L += ["## Panel rapido — SIMULATO", "",
              f"> SIMULATO: {panel.get('size', '?')} tester del genere, {panel.get('method', 'solo pitch e loop')}. Ordina le versioni, non prevede vendite.", "",
              "| Versione | Capiscono il pitch | Lo metterebbero in wishlist | Note |", "|---|---|---|---|"]
        for r in panel["results"]:
            if isinstance(r, dict):
                L.append(f"| {_cell(r.get('version'))} | {_cell(r.get('pitch_ok_pct'))}% | {_cell(r.get('wishlist_pct'))}% | {_cell(r.get('notes'))} |")
        L.append("")

    L += ["## Le tue scelte", "", "| Proposta | Livello | Stato | Data |", "|---|---|---|---|"]
    for p in props:
        L.append(f"| {_cell(p.get('id'))} {_cell(p.get('title'))} | {p.get('level', '')} | {STATUS_WORD.get(p.get('status', 'da_decidere'), '')} | {_cell(p.get('decided'))} |")
    acc = [p for p in props if p.get("status") == "accettata"]
    L += ["", "## Per lo sviluppo", ""]
    if acc:
        L += [f"Accettate: {', '.join(str(p.get('id')) for p in acc)}. Con `game-developer` le applica il parent a `GDD.md` (bozza → recap delle modifiche → "
              "di nuovo locked), una riga in `DECISIONI.md` per proposta con `fonte: launch/gdd-review.md P-GDD-n` "
              "(contratto `dev-link.md` §10). Senza: incolla il testo \"Proposto\" nella sezione indicata."]
    else:
        L.append("Nessuna proposta accettata per ora: il GDD resta com'è.")
    if data.get("sources"):
        L += ["", "## Fonti", ""] + [f"- {s}" for s in data["sources"]]
    return "\n".join(L).rstrip() + "\n"


def cmd_render(a) -> int:
    data = load(a.launch_dir)
    out = a.md or os.path.join(a.launch_dir, "gdd-review.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))
    errs, _ = check(data)
    print(f"scritto {out}" + (f" (attenzione: {len(errs)} errori in check)" if errs else ""))
    return 0


# ---------------------------------------------------------------------------------------------------- decide / pending
def cmd_decide(a) -> int:
    *ids, status = a.items
    if status not in STATUS or not ids:
        raise SystemExit(f"uso: decide P-GDD-1 [P-GDD-2 ...] {'|'.join(STATUS)}")
    data = load(a.launch_dir)
    props = {p.get("id"): p for p in data.get("proposals") or [] if isinstance(p, dict)}
    missing = [i for i in ids if i not in props]
    if missing:
        raise SystemExit("proposte inesistenti: " + ", ".join(missing))
    level = (data.get("dial") or {}).get("level")
    for i in ids:
        p = props[i]
        if status == "accettata" and level in LEVELS and p.get("level", 0) > level:
            raise SystemExit(f"{i} è di livello {p['level']}, sopra il livello scelto ({level}): alza prima il livello con il proprietario")
        p["status"] = status
        p["decided"] = "" if status == "da_decidere" else (a.date or dt.date.today().isoformat())
        if a.note:
            p["note"] = a.note
    save(a.launch_dir, data)
    print(", ".join(f"{i} {STATUS_WORD[status]}" for i in ids))
    return 0


def pending(data: dict, decisions_text: str) -> list[dict]:
    cited = set(re.findall(r"P-GDD-\d+", decisions_text or ""))
    return [p for p in data.get("proposals") or [] if isinstance(p, dict) and p.get("status") == "accettata" and p.get("id") not in cited]


def cmd_pending(a) -> int:
    data = load(a.launch_dir)
    text = ""
    if a.decisions and os.path.exists(a.decisions):
        with open(a.decisions, encoding="utf-8", errors="replace") as f:
            text = f.read()
    todo = pending(data, text)
    if a.json:
        print(json.dumps([{k: p.get(k) for k in ("id", "title", "level", "gdd_section", "now", "proposed", "decided", "reopens")} for p in todo],
                         ensure_ascii=False, indent=1))
    else:
        for p in todo:
            print(f"{p['id']}  [{p.get('gdd_section', '')}]  {p.get('title', '')}")
        print(f"{len(todo)} accettate da applicare al GDD" if todo else "nessuna proposta accettata da applicare")
    return 0


# ---------------------------------------------------------------------------------------------------- self-test
def _sample(level: int = 2) -> dict:
    d = skeleton("GDD.md", "2026-11-07")
    d["gdd_sections"] = ["Core loop", "Progressione", "Onboarding", "Pitch"]
    d["dial"] = {"level": level, "untouchable": ["engine", "stile"], "owner_words": "la grafica resta", "asked": "2026-11-07"}
    d["verdict"] = {"idea": "promettente", "one_line": "Il loop regge, il gancio no.", "best_move": "Un gancio visibile nei primi 10 secondi"}
    for s in d["scorecard"]:
        s.update(score=3, label="[STIMA]", why="metodo nel testo")
    d["scorecard"][0].update(label="[FATTO]", source="steam_comps 2026-11-07", score=2)
    d["comps"] = [{"name": f"Gioco {i}", "appid": 1000 + i, "why_close": "stesso loop", "result": "1-3k recensioni"} for i in range(5)]
    base = {"now": "assente", "why": "w", "impact": "i", "risk": "r", "loses": "l", "cost_hours": "4-8", "status": "da_decidere",
            "evidence": [{"label": "[FATTO]", "text": "le recensioni negative citano la noia dopo 2 h", "source": "review_corpus 2026-11-07"}]}
    d["proposals"] = [dict(base, id="P-GDD-1", level=1, title="Gancio nei primi 10 s", gdd_section="Pitch", touches=["pitch"], proposed="testo"),
                      dict(base, id="P-GDD-2", level=2, title="Run da 20 minuti", gdd_section="Core loop", touches=["loop"], proposed="testo"),
                      dict(base, id="P-GDD-3", level=2, title="Meta-progressione", gdd_section="Progressione", touches=["progressione"], proposed="testo")]
    return d


def self_test() -> int:
    d = _sample()
    errs, warns = check(d)
    assert not errs, errs
    bad = _sample()
    bad["proposals"][1]["level"] = 3
    bad["proposals"][2]["touches"] = ["stile"]
    bad["proposals"][0]["evidence"] = [{"label": "[FATTO]", "text": "x"}]
    errs, _ = check(bad)
    assert any("sopra quello scelto" in e for e in errs), errs
    assert any("intoccabile" in e for e in errs), errs
    assert any("[FATTO] senza fonte" in e for e in errs), errs
    assert any("almeno 2 proposte di struttura" in e for e in errs), errs
    eng = _sample()
    eng["dial"]["untouchable"] = []
    eng["proposals"][0]["touches"] = ["engine"]
    assert any("motore" in e for e in check(eng)[0])                    # the engine is untouchable even when not listed
    three = _sample(3)
    assert any("versioni alternative" in e for e in check(three)[0])
    nodial = _sample()
    nodial["dial"]["level"] = None
    assert any("dial.level" in e for e in check(nodial)[0])
    md = render(d)
    assert "## Pagella dell'idea" in md and "■■□□□ 2" in md and "### Cambi di struttura" in md and "> testo" in md
    assert "https://store.steampowered.com/app/1000/" in md
    tmp = tempfile.mkdtemp()
    save(tmp, d)
    ns = argparse.Namespace(launch_dir=tmp, items=["P-GDD-1", "P-GDD-2", "accettata"], date="2026-11-08", note="")
    cmd_decide(ns)
    data = load(tmp)
    assert [p["status"] for p in data["proposals"]] == ["accettata", "accettata", "da_decidere"] and data["proposals"][0]["decided"] == "2026-11-08"
    assert not check(data)[0]
    assert [p["id"] for p in pending(data, "- 2026-11-08 · GDD · run 20 min · fonte: launch/gdd-review.md P-GDD-2")] == ["P-GDD-1"]
    try:
        cmd_decide(argparse.Namespace(launch_dir=tmp, items=["P-GDD-9", "accettata"], date=None, note=""))
        raise AssertionError("unknown id accepted")
    except SystemExit:
        pass
    g = os.path.join(tmp, "GDD.md")
    with open(g, "w", encoding="utf-8") as f:
        f.write("---\nstatus: locked\ngenre: roguelite\n---\n# GDD\n## Core loop\nx\n## Progressione\ny\n")
    o = gdd_outline(g)
    assert o == {"keys": ["status", "genre"], "sections": ["Core loop", "Progressione"], "status": "locked"}, o
    print("self-test OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Idea and GDD review: dial, scorecard, proposals, owner's choices.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--launch-dir", default="launch")
    i.add_argument("--gdd", default="GDD.md")
    i.add_argument("--date")
    for name in ("check", "render"):
        s = sub.add_parser(name)
        s.add_argument("--launch-dir", default="launch")
        s.add_argument("--json", action="store_true")
        s.add_argument("--md")
    d = sub.add_parser("decide")
    d.add_argument("--launch-dir", default="launch")
    d.add_argument("items", nargs="+", help="P-GDD-n ... then accettata|rifiutata|da_decidere")
    d.add_argument("--date")
    d.add_argument("--note", default="")
    p = sub.add_parser("pending")
    p.add_argument("--launch-dir", default="launch")
    p.add_argument("--decisions", default="DECISIONI.md")
    p.add_argument("--json", action="store_true")
    sub.add_parser("self-test")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "check": cmd_check, "render": cmd_render, "decide": cmd_decide, "pending": cmd_pending,
            "self-test": lambda _a: self_test()}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
