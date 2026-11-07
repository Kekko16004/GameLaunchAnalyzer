#!/usr/bin/env python3
"""Idea and GDD review (mode "Revisione GDD", references/10-revisione-gdd.md; contract dev-link.md §10).

One JSON is the source, launch/_raw/gdd_review.json; the page to read, launch/gdd-review.md, is rendered from it.
The script never judges the idea: Claude fills the JSON with the research (comparables, genre benchmark, real reviews,
calibration, flop cases). The script keeps the review honest and usable:

  - the owner's dial: how much the GDD may change (1 ritocchi · 2 struttura · 3 tutto in discussione), what is untouchable
    (the engine always) and the HEART of the game in the owner's words ("cosa ti fa venire voglia di farlo"): no proposal
    above the dial, none on an untouchable, every concept change says how it keeps the heart (`keeps_heart`).
  - the stage: `idea` (judges the GDD's promises), `sviluppo` (mid-development: judges what the game really does, from the
    files in `basis`; proposals are cuts / reinforcements / changes, `kind`), `slice` (after the vertical slice: promises
    against reality, `promises`).
  - a scorecard of the idea on 10 fixed areas, each with a 1-5 score, a label ([FATTO] needs a source) and the reason;
    proposals may carry `score_delta` {area: +n} [STIMA]: the "after" scorecard counts the accepted ones (capped 1-5).
  - proposals P-GDD-n with the GDD section, current and proposed text (ready to paste), evidence, impact, hours, risk,
    what is lost, and the owner's answer (da_decidere / accettata / rifiutata, with date).
  - enough ambition for the dial: >= 3 proposals; dial 2 -> >= 2 structural ones; dial 3 -> >= 2 concept alternatives.

  gdd_review.py init    --launch-dir launch --gdd GDD.md [--stage idea|sviluppo|slice] [--date D]   skeleton (never overwrites)
  gdd_review.py check   --launch-dir launch [--json]                           errors exit 1, warnings only print
  gdd_review.py render  --launch-dir launch [--md launch/gdd-review.md]
  gdd_review.py decide  --launch-dir launch P-GDD-1 [P-GDD-2 ...] accettata|rifiutata|da_decidere [--date D] [--note T]
  gdd_review.py pending --launch-dir launch --decisions DECISIONI.md [--json]  accepted, not yet applied to the GDD (read only;
                                                                               applied = DECISIONI.md cites the P-GDD-n)
  gdd_review.py panel-score --launch-dir launch [--tol 8]   blind pitch panel with REAL anchors (2+ successes, 1 flop of the comps):
                        anchor drift vs their band from real reviews, raw and anchor-normalized score of every version
                        (same arithmetic as fg_waves.py); exit 3 when the anchors drift (re-judge before showing it)
  gdd_review.py flop-risk --launch-dir launch [--top 5] [--write]   the flop cases of data/case_studies.json (Reddit post-mortems,
                        references/09-reddit-casi.md) that share the most blamed factors (`risk_factors`) and genres with this game
  gdd_review.py compare --before OLD.json --after NEW.json [--md out.md]   second review after the slice: scorecard before/after,
                        accepted proposals kept or not, promises seen / partly / not seen in the game
  gdd_review.py predictions --launch-dir launch   every scorecard vote becomes a prediction in launch/predictions.json
                        (predictions.py; id gdd-<date>-<area>, idempotent), closed later by the same vote from real reviews
  gdd_review.py self-test
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import tempfile

try:
    import common  # noqa: F401  (side effect: UTF-8 stdout on a Windows console)
except ImportError:  # pragma: no cover
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join("_raw", "gdd_review.json")
CASES = os.path.join(HERE, "data", "case_studies.json")
PATTERNS = os.path.join(HERE, "data", "social_patterns.json")
LEVELS = {1: "Ritocchi", 2: "Struttura", 3: "Tutto in discussione"}
LEVEL_HELP = {1: "il concept resta; si rinforzano gancio, chiarezza, prima ora, scope",
              2: "stessa idea e stesso tema; possono cambiare loop, progressione, modalità, durata, scope, pitch",
              3: "si può cambiare anche genere, verbo centrale, ambientazione o pubblico; con versioni alternative del concept"}
LEVEL_GROUP = {1: "Ritocchi", 2: "Cambi di struttura", 3: "Cambi di concept (versioni alternative)"}
STAGES = {"idea": "idea scritta (si giudicano le promesse del GDD)",
          "sviluppo": "a metà sviluppo (si giudica quello che il gioco fa davvero oggi)",
          "slice": "dopo la vertical slice (promesse contro realtà)"}
KINDS = {"taglio": "Taglio", "rinforzo": "Rinforzo", "cambio": "Cambio"}
REALITY = {"si vede": "✓ si vede", "in parte": "◐ in parte", "non si vede": "✗ non si vede"}
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
AREA_KEYS = [k for k, _ in AREAS]
AREA_SHORT = {"gancio": "Gancio", "differenza": "Differenza", "mercato": "Mercato", "loop": "Loop", "progressione": "Progressione",
              "prima_ora": "Prima ora", "clip": "Clip", "scope": "Scope", "prezzo": "Prezzo", "rischio_flop": "Rischio flop"}
LABELS = ("[FATTO]", "[STIMA]", "[OPINIONE]", "[DA VERIFICARE]")
STATUS = ("da_decidere", "accettata", "rifiutata")
STATUS_WORD = {"da_decidere": "○ da decidere", "accettata": "✓ accettata", "rifiutata": "✗ rifiutata"}
VERDICTS = ("forte", "promettente", "fragile", "da ripensare")
PID = re.compile(r"^P-GDD-\d+$")
FLOP_SIM_WARN = 0.6        # a flop case sharing >= 60% of its blamed factors (and >= 2 of them) is a close look-alike
BASIS_CANDIDATES = ("docs/design-review/game-map.md", "docs/design-review/screen-map.md", "docs/design-review/runs.md", "GAME_TASKS.md",
                    "GAME_CONTEXT.md")


# ---------------------------------------------------------------------------------------------------- io
def raw_path(launch_dir: str) -> str:
    return os.path.join(launch_dir, RAW)


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(launch_dir: str) -> dict:
    p = raw_path(launch_dir)
    if not os.path.exists(p):
        raise SystemExit(f"{p} non c'è: prima `gdd_review.py init`")
    return read_json(p)


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


def project_root(launch_dir: str) -> str:
    return os.path.dirname(os.path.abspath(launch_dir))


def detect_basis(root: str) -> list[str]:
    """What the game really does today: design-review maps, task registry, gates with a header, the latest wave maps."""
    out = [p for p in BASIS_CANDIDATES if os.path.exists(os.path.join(root, *p.split("/")))]
    gates = sorted(glob.glob(os.path.join(root, "docs", "gates", "*.md")))
    if gates:
        out.append("docs/gates/ (%d gate)" % len(gates))
    maps = sorted(glob.glob(os.path.join(root, "launch", "fg", "waves", "w*-mappa-gioco.md")))
    if maps:
        out.append("launch/fg/waves/" + os.path.basename(maps[-1]))
    return out


# ---------------------------------------------------------------------------------------------------- init
def skeleton(gdd: str, date: str, stage: str = "idea", basis: list | None = None) -> dict:
    o = gdd_outline(gdd)
    return {
        "date": date, "stage": stage, "basis": basis or [],
        "gdd": gdd.replace("\\", "/"), "gdd_status": o["status"], "gdd_sections": o["sections"], "gdd_keys": o["keys"],
        "dial": {"level": None, "untouchable": ["engine"], "heart": "", "owner_words": "", "asked": ""},
        "product": "",                                  # slice / beta / gioco completo, as the owner said
        "genres": [],                                   # genre words, for the flop look-alikes
        "risk_factors": [],                             # factor codes of social_patterns.json factor_weights the game shows
        "verdict": {"idea": "", "one_line": "", "best_move": "", "strengths": [], "weak_spots": []},
        "scorecard": [{"area": k, "score": None, "label": "", "why": "", "source": ""} for k in AREA_KEYS],
        "comps": [],                                    # {"name", "appid", "why_close", "result", "source"}
        "proposals": [],
        "promises": [],                                 # stage slice: {"promise", "from", "reality", "evidence", "source"}
        "panel": {},                                    # optional, SIMULATO: {"size", "method", "anchors": [...], "results": [...]}
        "sources": [],
    }


def cmd_init(a) -> int:
    p = raw_path(a.launch_dir)
    if os.path.exists(p):
        print(f"{p} esiste già: non lo tocco")
        return 0
    stage = a.stage or "idea"
    basis = detect_basis(project_root(a.launch_dir)) if stage != "idea" else []
    save(a.launch_dir, skeleton(a.gdd, a.date or dt.date.today().isoformat(), stage, basis))
    print(f"scritto {p}" + (f" (base trovata: {', '.join(basis) or 'nessun file: aggiungila a mano in basis'})" if stage != "idea" else ""))
    return 0


# ---------------------------------------------------------------------------------------------------- scores
def scores_of(data: dict) -> dict:
    return {s.get("area"): s.get("score") for s in data.get("scorecard") or [] if isinstance(s, dict) and s.get("score") in (1, 2, 3, 4, 5)}


def after_scores(data: dict) -> dict | None:
    """Scorecard after the ACCEPTED proposals' score_delta [STIMA], capped to 1-5. None when no accepted proposal has a delta."""
    base = scores_of(data)
    acc = [p for p in data.get("proposals") or [] if isinstance(p, dict) and p.get("status") == "accettata" and p.get("score_delta")]
    if not acc or not base:
        return None
    out = dict(base)
    for p in acc:
        for area, d in (p.get("score_delta") or {}).items():
            if area in out and isinstance(d, (int, float)):
                out[area] = max(1, min(5, out[area] + d))
    return out


# ---------------------------------------------------------------------------------------------------- check
def _hours_ok(v) -> bool:
    if isinstance(v, (int, float)) and v >= 0:
        return True
    return isinstance(v, str) and bool(re.fullmatch(r"\s*\d+(\.\d+)?\s*(-\s*\d+(\.\d+)?)?\s*h?\s*", v))


def factor_codes() -> dict:
    try:
        return {k: v.get("label", k) for k, v in read_json(PATTERNS)["factor_weights"]["factors"].items()}
    except (OSError, ValueError, KeyError):
        return {}


def check(data: dict, today: str | None = None, root: str | None = None) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    dial = data.get("dial") or {}
    level = dial.get("level")
    untouch = set(dial.get("untouchable") or []) | {"engine"}
    if level not in LEVELS:
        errs.append("dial.level mancante: chiedi al proprietario quanto è disposto a cambiare il GDD (1, 2 o 3)")
        level = 3
    if not str(dial.get("heart") or "").strip():
        errs.append("dial.heart vuoto: chiedi per primo «cosa ti fa venire voglia di fare questo gioco?» e scrivi le sue parole")
    bad = [u for u in untouch if u not in TOUCH]
    if bad:
        warns.append(f"intoccabili fuori vocabolario (non controllabili): {', '.join(bad)}")

    stage = data.get("stage") or "idea"
    if stage not in STAGES:
        errs.append(f"stage '{stage}' non valido ({', '.join(STAGES)})")
        stage = "idea"
    if stage != "idea":
        basis = [b for b in data.get("basis") or [] if str(b).strip()]
        if not basis:
            errs.append(f"stage {stage}: `basis` vuoto (i file da cui leggi cosa fa davvero il gioco: mappa del gioco, gate, GAME_TASKS)")
        elif root:
            for b in basis:
                rel = re.sub(r"\s*\(.*\)$", "", str(b)).rstrip("/")
                if not os.path.exists(os.path.join(root, *rel.split("/"))):
                    warns.append(f"base '{b}' non trovata nel progetto")
    if stage == "slice":
        prom = [p for p in data.get("promises") or [] if isinstance(p, dict)]
        if not prom:
            errs.append("stage slice: `promises` vuoto (ogni punto forte promesso, e se nel gioco si vede)")
        for p in prom:
            if p.get("reality") not in REALITY:
                errs.append(f"promessa '{str(p.get('promise', '?'))[:40]}': reality deve essere {' / '.join(REALITY)}")
            if not str(p.get("evidence") or "").strip():
                errs.append(f"promessa '{str(p.get('promise', '?'))[:40]}': manca la prova (foto, run, gate)")

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

    codes = factor_codes()
    rf = data.get("risk_factors") or []
    unknown = [c for c in rf if codes and c not in codes]
    if unknown:
        warns.append(f"risk_factors fuori vocabolario (social_patterns.json): {', '.join(unknown)}")
    if not rf:
        warns.append("risk_factors vuoto: `flop-risk` non può confrontare il gioco con i flop reali")
    fr = data.get("flop_risk") or {}
    top = (fr.get("cases") or [{}])[0] if fr.get("cases") else {}
    flop_score = (areas.get("rischio_flop") or {}).get("score")
    if top and top.get("similarity", 0) >= FLOP_SIM_WARN and len(top.get("shared") or []) >= 2 and isinstance(flop_score, int) and flop_score > 3:
        warns.append(f"rischio_flop {flop_score}/5 ma il gioco somiglia al flop '{top.get('game')}' "
                     f"({round(100 * top['similarity'])}% dei fattori: {', '.join(top['shared'])}): rivedi il voto o spiega perché no")

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
        if lv == 3 and not str(p.get("keeps_heart") or "").strip():
            errs.append(f"{pid}: cambio di concept senza `keeps_heart` (come conserva ciò che il proprietario ama del gioco)")
        if stage != "idea" and p.get("kind") not in KINDS:
            errs.append(f"{pid}: a stage {stage} serve `kind` ({' / '.join(KINDS)})")
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
        sd = p.get("score_delta")
        if sd is not None:
            if not isinstance(sd, dict) or any(k not in AREA_KEYS or not isinstance(d, int) or not -3 <= d <= 3 for k, d in sd.items()):
                errs.append(f"{pid}: `score_delta` deve essere {{area: intero da -3 a +3}} con aree della pagella")
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
    if panel.get("results"):
        anchors = [x for x in panel.get("anchors") or [] if isinstance(x, dict)]
        if not anchors:
            warns.append("panel senza ancore vere: i punteggi non sono calibrati (2+ successi e 1 flop dei comparabili, `panel-score`)")
        elif len(anchors) < 3 or not any(x.get("kind") == "weak" for x in anchors):
            warns.append("ancore del panel insufficienti: servono 2+ successi veri e 1 gioco debole")
        elif not panel.get("calibration"):
            warns.append("panel con ancore ma senza calibrazione: lancia `gdd_review.py panel-score`")
        elif panel["calibration"].get("drift"):
            warns.append("ancore del panel fuori fascia: rifai il giudizio alla cieca prima di mostrare i punteggi")
    return errs, warns


def cmd_check(a) -> int:
    errs, warns = check(load(a.launch_dir), root=project_root(a.launch_dir))
    if a.json:
        print(json.dumps({"ok": not errs, "errors": errs, "warnings": warns}, ensure_ascii=False))
    else:
        for e in errs:
            print("❌ " + e)
        for w in warns:
            print("⚠ " + w)
        print("✅ revisione completa" if not errs else f"{len(errs)} errori")
    return 1 if errs else 0


# ---------------------------------------------------------------------------------------------------- panel with anchors
def panel_score(data: dict, tol: float = 8.0) -> dict:
    """Anchors (real games of the comps, judged blind with our versions) -> drift and the anchor-normalized score of each version."""
    import fg_waves as fw
    panel = data.get("panel") or {}
    anchors = []
    for x in panel.get("anchors") or []:
        if not isinstance(x, dict):
            continue
        x = dict(x)
        if not x.get("band") and isinstance(x.get("positive_pct"), (int, float)) and isinstance(x.get("reviews"), (int, float)):
            x["band"] = fw.anchor_band(x["positive_pct"], x["reviews"])
        anchors.append(x)
    cal = fw.calibration({"anchors": anchors}, tol) if anchors else None
    results = []
    for r in panel.get("results") or []:
        if not isinstance(r, dict):
            continue
        r = dict(r)
        raw = fw._verdicts_score(r.get("verdicts")) if r.get("verdicts") else (float(r["score"]) if isinstance(r.get("score"), (int, float)) else None)
        r["raw_score"] = raw
        r["norm_score"] = cal["map"](raw) if (cal and cal.get("map") and raw is not None) else None
        results.append(r)
    out = {"anchors": anchors, "results": results}
    if cal:
        out["calibration"] = {k: v for k, v in cal.items() if k not in ("map", "map_rubric")}
    return out


def cmd_panel_score(a) -> int:
    data = load(a.launch_dir)
    if not (data.get("panel") or {}).get("results"):
        raise SystemExit("panel.results vuoto: niente da calcolare")
    res = panel_score(data, a.tol)
    data["panel"].update(anchors=res["anchors"], results=res["results"])
    if "calibration" in res:
        data["panel"]["calibration"] = res["calibration"]
    save(a.launch_dir, data)
    cal = res.get("calibration")
    for r in res["results"]:
        print(f"{r.get('version')}: grezzo {r['raw_score']}" + (f" · normalizzato {r['norm_score']}" if r["norm_score"] is not None else ""))
    if not cal:
        print("⚠ nessuna ancora vera: punteggi grezzi, non calibrati")
        return 0
    for x in cal["anchors"]:
        print(f"  ancora {x['name']} ({x['kind']}): {x['raw']} contro fascia {x['band']}" + (f" ⚠ {x['why']}" if x["flag"] else ""))
    print(f"giudizio {cal['direction']}; {cal['method']}" + ("" if cal["enough"] else " · ancore insufficienti (2+ successi e 1 debole)"))
    if cal["drift"]:
        print("❌ ancore fuori fascia: rifai il giudizio alla cieca prima di mostrare i punteggi")
        return 3
    return 0


# ---------------------------------------------------------------------------------------------------- flop look-alikes
def _words(xs) -> set:
    return {w for x in xs or [] for w in re.split(r"[\s/,-]+", str(x).lower()) if len(w) > 2}


def flop_risk(data: dict, cases_path: str = CASES, top: int = 5) -> dict:
    """Flop cases with factors blamed by the comments (case_studies.json, dir neg): share of THEIR blamed factors this game shows
    (`risk_factors`), plus a small bonus for a shared genre word. Opinions of commenters, not measures: where to look first."""
    ours = set(data.get("risk_factors") or [])
    genres = _words(data.get("genres"))
    labels = factor_codes()
    try:
        recs = read_json(cases_path).get("records") or []
    except (OSError, ValueError):
        recs = []
    rows = []
    for r in recs:
        if r.get("outcome") != "flop":
            continue
        blamed = {f.get("code") for f in r.get("comment_factors") or [] if f.get("dir") == "neg" and f.get("code") not in (None, "other")}
        if not blamed:
            continue
        shared = sorted(ours & blamed)
        g_shared = sorted(genres & _words(r.get("genres")))
        sim = len(shared) / len(blamed) + (0.15 if g_shared and shared else 0)
        if not shared:
            continue
        rows.append(dict(game=r.get("game"), id=r.get("id"), similarity=round(min(1.0, sim), 2), shared=shared,
                         shared_labels=[labels.get(c, c) for c in shared], blamed=sorted(blamed), genres_shared=g_shared,
                         wishlists=r.get("wishlists_after"), tier=r.get("tier"), why=r.get("comments_summary") or r.get("why_author") or "",
                         url=r.get("source_url"), steam=r.get("steam_url")))
    rows.sort(key=lambda x: (-x["similarity"], -len(x["shared"]), x["game"] or ""))
    flops = sum(1 for r in recs if r.get("outcome") == "flop")
    return dict(date=dt.date.today().isoformat(), our_factors=sorted(ours), flops_checked=flops, cases=rows[:top],
                source="data/case_studies.json (post-mortem Reddit, references/09-reddit-casi.md)")


def cmd_flop_risk(a) -> int:
    data = load(a.launch_dir)
    if not data.get("risk_factors"):
        raise SystemExit("risk_factors vuoto: scrivi prima i fattori di rischio del gioco (codici di social_patterns.json factor_weights)")
    fr = flop_risk(data, top=a.top)
    if a.write:
        data["flop_risk"] = fr
        save(a.launch_dir, data)
    print(f"{fr['flops_checked']} flop reali confrontati; fattori del gioco: {', '.join(fr['our_factors'])}")
    for c in fr["cases"]:
        print(f"{round(100 * c['similarity'])}%  {c['game']}  ({', '.join(c['shared_labels'])})  {c['url'] or ''}")
    if not fr["cases"]:
        print("nessun flop con fattori in comune")
    return 0


# ---------------------------------------------------------------------------------------------------- second review (after the slice)
def compare(before: dict, after: dict) -> dict:
    sb, sa = scores_of(before), scores_of(after)
    areas = [dict(area=k, name=AREA_SHORT[k], before=sb.get(k), after=sa.get(k),
                  delta=(sa[k] - sb[k]) if k in sa and k in sb else None) for k in AREA_KEYS]
    prom = {str(p.get("from") or ""): p for p in after.get("promises") or [] if isinstance(p, dict)}
    accepted = []
    for p in before.get("proposals") or []:
        if isinstance(p, dict) and p.get("status") == "accettata":
            seen = prom.get(p.get("id"))
            accepted.append(dict(id=p.get("id"), title=p.get("title"), reality=(seen or {}).get("reality") or "non verificata",
                                 evidence=(seen or {}).get("evidence", "")))
    strengths = []
    for s in (before.get("verdict") or {}).get("strengths") or []:
        seen = next((p for p in after.get("promises") or [] if isinstance(p, dict) and str(p.get("promise", "")).strip().lower() == str(s).strip().lower()), None)
        strengths.append(dict(promise=s, reality=(seen or {}).get("reality") or "non verificata", evidence=(seen or {}).get("evidence", "")))
    extra = [p for p in after.get("promises") or [] if isinstance(p, dict) and p.get("from") not in {x["id"] for x in accepted}
             and str(p.get("promise", "")).strip().lower() not in {str(x["promise"]).strip().lower() for x in strengths}]
    kept = [x for x in accepted + strengths if x["reality"] == "si vede"]
    return dict(before_date=before.get("date"), after_date=after.get("date"), areas=areas, accepted=accepted, strengths=strengths, other=extra,
                kept=len(kept), checked=len(accepted) + len(strengths),
                mean_before=round(sum(sb.values()) / len(sb), 1) if sb else None, mean_after=round(sum(sa.values()) / len(sa), 1) if sa else None)


def compare_md(c: dict) -> str:
    L = [f"# Seconda revisione: promesse contro realtà ({c['before_date']} → {c['after_date']})", "",
         f"Promesse mantenute (si vedono nel gioco): **{c['kept']} su {c['checked']}**. Media della pagella {c['mean_before']} → {c['mean_after']}.", "",
         "## Pagella prima e dopo", "", "| Area | Prima | Dopo | Differenza |", "|---|---|---|---|"]
    for a in c["areas"]:
        d = "—" if a["delta"] is None else f"{a['delta']:+d}"
        L.append(f"| {a['name']} | {a['before'] or '—'} | {a['after'] or '—'} | {d} |")
    L += ["", "## Proposte accettate: si vedono nel gioco?", "", "| Proposta | Nel gioco | Prova |", "|---|---|---|"]
    for x in c["accepted"]:
        L.append(f"| {x['id']} {_cell(x['title'])} | {REALITY.get(x['reality'], '○ ' + x['reality'])} | {_cell(x['evidence'])} |")
    L += ["", "## Punti forti promessi dalla prima revisione", "", "| Promessa | Nel gioco | Prova |", "|---|---|---|"]
    for x in c["strengths"]:
        L.append(f"| {_cell(x['promise'])} | {REALITY.get(x['reality'], '○ ' + x['reality'])} | {_cell(x['evidence'])} |")
    if c["other"]:
        L += ["", "## Altre promesse verificate", ""] + [f"- {REALITY.get(p.get('reality'), p.get('reality'))} {p.get('promise')}: {p.get('evidence', '')}" for p in c["other"]]
    return "\n".join(L) + "\n"


def cmd_compare(a) -> int:
    c = compare(read_json(a.before), read_json(a.after))
    text = compare_md(c)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"scritto {a.md}: {c['kept']} promesse mantenute su {c['checked']}")
    else:
        print(text)
    return 0


# ---------------------------------------------------------------------------------------------------- predictions
def prediction_items(data: dict) -> list[dict]:
    date = data.get("date") or dt.date.today().isoformat()
    names = dict(AREAS)
    out = []
    for area, sc in scores_of(data).items():
        out.append(dict(id=f"gdd-{date}-{area}", date=date, source=f"Revisione GDD ({data.get('stage') or 'idea'}), pagella dell'idea",
                        metric=f"idea_{area}", value=sc, low=max(1, sc - 1), high=min(5, sc + 1), unit="/5", label="STIMA",
                        subject=names.get(area, area), actual_metric=f"idea_{area}_real", due=None,
                        note=f"Si chiude dopo l'uscita: stesso voto 1-5 dato dalle recensioni reali (metrics_track.py add --metric idea_{area}_real --value N). "
                             "Giusta = entro un punto."))
    return out


def cmd_predictions(a) -> int:
    import predictions as pr
    data = load(a.launch_dir)
    items = prediction_items(data)
    if not items:
        raise SystemExit("pagella senza voti: niente da registrare")
    d = pr.load(a.launch_dir)
    n = sum(pr.put(d, it) for it in items)
    if n:
        pr.save(a.launch_dir, d, dt.date.today())
    print(f"{n} previsioni nuove registrate ({len(items) - n} già presenti) in {pr.path_of(a.launch_dir)}")
    return 0


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
    stage = data.get("stage") or "idea"
    v = data.get("verdict") or {}
    props = [p for p in data.get("proposals") or [] if isinstance(p, dict)]
    L = [f"# Revisione dell'idea e del GDD — {data.get('date', '')}", "",
         "> Come leggerla: una **pagella** dell'idea confrontata con giochi veri, poi le **proposte** per migliorarla, divise per quanto "
         "cambiano il gioco. Ogni affermazione ha un'etichetta: **[FATTO]** dato con fonte · **[STIMA]** calcolo · **[OPINIONE]** giudizio "
         "con le sue ragioni · **[DA VERIFICARE]**. Il GDD lo cambia solo il proprietario: ogni proposta si accetta o si rifiuta.", ""]
    L += ["## In breve", "",
          f"- **Cosa si giudica:** {STAGES.get(stage, stage)}" + (f" — base: {', '.join(map(str, data.get('basis') or []))}" if stage != "idea" else ""),
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
    if dial.get("heart"):
        L.append(f"- **Il cuore del gioco, con le sue parole:** {dial['heart']}")
    if level in LEVELS:
        L.append(f"- **Livello {level}: {LEVELS[level]}** — {LEVEL_HELP[level]}.")
    else:
        L.append("- Livello non ancora scelto.")
    unt = [TOUCH.get(u, u) for u in (dial.get("untouchable") or [])]
    L.append("- **Intoccabili:** " + (", ".join(unt) if unt else "motore"))
    if dial.get("owner_words"):
        L.append(f"- **Parole del proprietario:** {dial['owner_words']}")
    L.append("")

    after = after_scores(data)
    L += ["## Pagella dell'idea", ""]
    L += (["| Area | Voto | Dopo le accettate [STIMA] | Perché | Etichetta e fonte |", "|---|---|---|---|---|"] if after
          else ["| Area | Voto | Perché | Etichetta e fonte |", "|---|---|---|---|"])
    areas = {s.get("area"): s for s in data.get("scorecard") or [] if isinstance(s, dict)}
    scores = []
    for key, name in AREAS:
        s = areas.get(key, {})
        if s.get("score") in (1, 2, 3, 4, 5):
            scores.append(s["score"])
        mid = f" {_bar(after.get(key))} {after.get(key) or ''} |" if after else ""
        L.append(f"| {name} | {_bar(s.get('score'))} {s.get('score') or ''} |{mid} {_cell(s.get('why'))} | {_cell(s.get('label'))} {_cell(s.get('source'))} |")
    if scores:
        L += ["", f"Media {sum(scores) / len(scores):.1f} su 5 ({len(scores)} aree)"
              + (f", {sum(after.values()) / len(after):.1f} con le proposte accettate [STIMA]" if after else "")
              + ". Un 2 o meno è un punto da sistemare prima di costruire."]
    L.append("")

    if stage == "slice" and data.get("promises"):
        L += ["## Promesse contro realtà", "", "| Promessa | Da | Nel gioco | Prova |", "|---|---|---|---|"]
        for p in data["promises"]:
            if isinstance(p, dict):
                L.append(f"| {_cell(p.get('promise'))} | {_cell(p.get('from'))} | {REALITY.get(p.get('reality'), _cell(p.get('reality')))} | {_cell(p.get('evidence'))} {_cell(p.get('source'))} |")
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

    fr = data.get("flop_risk") or {}
    if fr.get("cases"):
        L += ["## Somiglianza con flop reali", "",
              f"> Confronto con {fr.get('flops_checked')} flop documentati ({fr.get('source')}): quota dei fattori che i commenti incolpano "
              "e che questo gioco ha. Sono opinioni dei commentatori, non misure: dicono dove guardare per primo.", "",
              "| Flop | Somiglianza | Fattori in comune | Perché è andato male | Fonte |", "|---|---|---|---|---|"]
        for c in fr["cases"]:
            L.append(f"| {_cell(c.get('game'))} | {round(100 * c.get('similarity', 0))}% | {_cell(', '.join(c.get('shared_labels') or []))} | {_cell(c.get('why'))[:220]} | "
                     + (f"[post]({c['url']})" if c.get("url") else "") + " |")
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
            kind = f"{KINDS[p['kind']]} · " if p.get("kind") in KINDS else ""
            L += [f"#### {p.get('id')} · {kind}{p.get('title', '')} — {st}{when}", "",
                  f"- **Sezione del GDD:** {p.get('gdd_section', '')} · **cosa tocca:** {', '.join(TOUCH.get(t, t) for t in p.get('touches') or [])}",
                  f"- **Perché:** {p.get('why', '')}",
                  f"- **Effetto atteso:** {p.get('impact', '')}",
                  f"- **Costo:** {p.get('cost_hours', '')} h [STIMA] · **rischio:** {p.get('risk', '')} · **cosa si perde:** {p.get('loses', '')}"]
            if p.get("keeps_heart"):
                L.append(f"- **Cosa conserva del cuore del gioco:** {p['keeps_heart']}")
            if p.get("score_delta"):
                L.append("- **Effetto sulla pagella [STIMA]:** " + ", ".join(f"{AREA_SHORT.get(k, k)} {d:+d}" for k, d in p["score_delta"].items()))
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
        cal = panel.get("calibration") or {}
        L += ["## Panel rapido — SIMULATO", "",
              f"> SIMULATO: {panel.get('size', '?')} tester del genere, {panel.get('method', 'solo pitch e loop')}. Ordina le versioni, non prevede vendite."
              + (" Le versioni sono state giudicate alla cieca insieme a pitch di giochi veri (ancore): il punteggio normalizzato le usa come metro." if cal else
                 " Senza ancore vere: punteggi grezzi."), "",
              "| Versione | Capiscono il pitch | Wishlist | Punteggio grezzo | Normalizzato | Note |", "|---|---|---|---|---|---|"]
        for r in panel["results"]:
            if isinstance(r, dict):
                pok = f"{_cell(r.get('pitch_ok_pct'))}%" if r.get("pitch_ok_pct") is not None else "—"
                wl = f"{_cell(r.get('wishlist_pct'))}%" if r.get("wishlist_pct") is not None else "—"
                L.append(f"| {_cell(r.get('version'))} | {pok} | {wl} | {_cell(r.get('raw_score')) or '—'} | {_cell(r.get('norm_score')) or '—'} | {_cell(r.get('notes'))} |")
        if cal:
            L += ["", "| Ancora vera | Tipo | Punteggio | Fascia attesa | Esito |", "|---|---|---|---|---|"]
            for x in cal.get("anchors") or []:
                L.append(f"| {_cell(x.get('name'))} | {'debole' if x.get('kind') == 'weak' else 'successo'} | {_cell(x.get('raw'))} | {_cell(x.get('band'))} | "
                         f"{'⚠ ' + _cell(x.get('why')) if x.get('flag') else 'in fascia'} |")
            L.append("")
            L.append(f"Giudizio {cal.get('direction')}; {cal.get('method')}." + (" ❌ Ancore fuori fascia: punteggi da rifare." if cal.get("drift") else ""))
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
    d["dial"] = {"level": level, "untouchable": ["engine", "stile"], "heart": "cucinare sotto pressione con gli amici",
                 "owner_words": "la grafica resta", "asked": "2026-11-07"}
    d["risk_factors"] = ["hook_clarity", "genre_market"]
    d["genres"] = ["roguelite", "cooking"]
    d["verdict"] = {"idea": "promettente", "one_line": "Il loop regge, il gancio no.", "best_move": "Un gancio visibile nei primi 10 secondi",
                    "strengths": ["co-op caotica"]}
    for s in d["scorecard"]:
        s.update(score=3, label="[STIMA]", why="metodo nel testo")
    d["scorecard"][0].update(label="[FATTO]", source="steam_comps 2026-11-07", score=2)
    d["comps"] = [{"name": f"Gioco {i}", "appid": 1000 + i, "why_close": "stesso loop", "result": "1-3k recensioni"} for i in range(5)]
    base = {"now": "assente", "why": "w", "impact": "i", "risk": "r", "loses": "l", "cost_hours": "4-8", "status": "da_decidere",
            "evidence": [{"label": "[FATTO]", "text": "le recensioni negative citano la noia dopo 2 h", "source": "review_corpus 2026-11-07"}]}
    d["proposals"] = [dict(base, id="P-GDD-1", level=1, title="Gancio nei primi 10 s", gdd_section="Pitch", touches=["pitch"], proposed="testo",
                           score_delta={"gancio": 2}),
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
    three["proposals"].append(dict(three["proposals"][1], id="P-GDD-4", level=3))
    assert any("keeps_heart" in e for e in check(three)[0])
    nodial = _sample()
    nodial["dial"]["level"] = None
    nodial["dial"]["heart"] = ""
    e_ = check(nodial)[0]
    assert any("dial.level" in e for e in e_) and any("dial.heart" in e for e in e_)
    mid = _sample()
    mid["stage"] = "sviluppo"
    e_ = check(mid)[0]
    assert any("`basis` vuoto" in e for e in e_) and any("serve `kind`" in e for e in e_)
    mid["basis"] = ["GAME_TASKS.md"]
    for p in mid["proposals"]:
        p["kind"] = "taglio"
    assert not check(mid)[0]
    sl = _sample()
    sl["stage"], sl["basis"] = "slice", ["docs/gates/"]
    for p in sl["proposals"]:
        p["kind"] = "rinforzo"
    assert any("`promises` vuoto" in e for e in check(sl)[0])
    sl["promises"] = [{"promise": "co-op caotica", "reality": "in parte", "evidence": "screenshots/coop.png"}]
    assert not check(sl)[0]
    md = render(d)
    assert "## Pagella dell'idea" in md and "■■□□□ 2" in md and "### Cambi di struttura" in md and "> testo" in md
    assert "https://store.steampowered.com/app/1000/" in md and "Il cuore del gioco" in md
    assert after_scores(d) is None
    d["proposals"][0]["status"] = "accettata"
    assert after_scores(d)["gancio"] == 4 and "Dopo le accettate" in render(d)
    d["proposals"][0]["status"] = "da_decidere"
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
    items = prediction_items(data)
    assert len(items) == 10 and items[0]["id"] == "gdd-2026-11-07-gancio" and (items[0]["low"], items[0]["high"]) == (1, 3)
    c = compare(data, sl)
    assert c["checked"] == 3 and [x["reality"] for x in c["strengths"]] == ["in parte"]
    print("self-test OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Idea and GDD review: dial, scorecard, proposals, owner's choices.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--launch-dir", default="launch")
    i.add_argument("--gdd", default="GDD.md")
    i.add_argument("--stage", choices=list(STAGES))
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
    ps = sub.add_parser("panel-score")
    ps.add_argument("--launch-dir", default="launch")
    ps.add_argument("--tol", type=float, default=8.0)
    fr = sub.add_parser("flop-risk")
    fr.add_argument("--launch-dir", default="launch")
    fr.add_argument("--top", type=int, default=5)
    fr.add_argument("--write", action="store_true", help="save the result in gdd_review.json (shown in the page, used by check)")
    cp = sub.add_parser("compare")
    cp.add_argument("--before", required=True)
    cp.add_argument("--after", required=True)
    cp.add_argument("--md")
    pr = sub.add_parser("predictions")
    pr.add_argument("--launch-dir", default="launch")
    sub.add_parser("self-test")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "check": cmd_check, "render": cmd_render, "decide": cmd_decide, "pending": cmd_pending,
            "panel-score": cmd_panel_score, "flop-risk": cmd_flop_risk, "compare": cmd_compare, "predictions": cmd_predictions,
            "self-test": lambda _a: self_test()}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
