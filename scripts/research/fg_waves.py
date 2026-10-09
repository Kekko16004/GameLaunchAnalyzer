#!/usr/bin/env python3
"""Focus-group waves: validate, compute metrics, compare two waves, render the timeline.

The simulated panel judges the game; THIS tool does the arithmetic, so scores, deltas and trends are
reproducible and never computed by hand. A wave is one run of the (same) roster on one state of the game.

Wave file (launch/fg/waves/w01-YYYY-MM-DD.json), written after the panel has judged:
  {
    "wave": 1, "date": "2026-10-06", "build": "v0.3 / commit abc123", "label": "baseline", "stage": "beta",   # stage: beta | full (what the panel is asked to judge)
    "evidence": "capsule v1, pitch v1, build 0.3",
    "controls": {"success": 41.2, "weak": 6.0},            # optional: scores the panel gave to control capsules
    "testers": [{"id": "A-01", "verdict": "WISHLIST", "click": true, "pitch_ok": true, "would_buy": true,   # would_buy (optional): would pay the planned launch price
                 "issues": ["slow-opening", "tutorial-text"]}, ...],   # first issue = main criticism
    "issues":  [{"key": "slow-opening", "label": "Apertura lenta", "severity": "alta",
                 "recommendation": "...", "gate": "A", "area": "Primi minuti"}, ...],   # gate (0|A|B|C) and area: optional, used to group the criticalities in STATUS.html
    "fixes":   [{"issue": "slow-opening", "what": "tutorial shortened"}],   # waves > 1: fixes since the previous wave
    "ceiling": {                                        # the two CEILING questions (04-focus-group.md, Passo 3b):
      "version": {"testers": [{"id": "A-01", "verdict": "WISHLIST", "reason": "risolvibile: ..."}]},   # THIS version with only in-scope fixes
                  # (bugs, clarity, polish; no new content or modes). If not asked: {"estimate": "55-58", "note": "..."} = [STIMA], not measured
      "full":    {"testers": [...]}                     # the full game with the planned content
    }   # reason "risolvibile: ..." or "gusto/genere: ...". Old files with a single {"testers": [...]} block are read as "full".
  }
verdict: WISHLIST | SALDI | IGNORO | REFUND.  severity: alta | media | bassa.  Reuse the SAME issue keys across waves.

Score = ((W*1.0) + (S*0.4) - (I*0.2) - (R*0.8)) / N * 100   (range -80..100, NOT a percentage).
Gate A threshold: --gate N, else 80% of controls.success (min 30), else 35.

Commands:
  metrics  WAVE.json [--roster roster.json] [--gate N] [-o out.json|out.md]
  delta    BEFORE.json AFTER.json [--roster roster.json] [--noise 10] [-o delta.md]
  timeline DIR [--roster roster.json] [--gate N] [-o timeline.md] [--csv timeline.csv]

The panel is simulated: deltas are directional, not proof. Confirm important changes with real testers.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
from collections import Counter
from common import load_json, log, write_csv, write_json

W_ = {"WISHLIST": 1.0, "SALDI": 0.4, "IGNORO": -0.2, "REFUND": -0.8}
SEV = {"alta": 3, "media": 2, "bassa": 1}
GAP_FLAG = 15
CEIL_NEAR_POINTS = 5     # ceiling minus score at or below this: close to the game's potential
CEIL_NEAR_SHARE = 90     # or score at or above this % of the ceiling  # A/B score gap above which the skill requires an explanation


def die(msgs):
    raise SystemExit("INVALID WAVE:\n  - " + "\n  - ".join(msgs))


def load_wave(path: str, roster: dict | None = None) -> dict:
    w = load_json(path)
    errs, warns = [], []
    for k in ("wave", "date", "testers"):
        if k not in w:
            errs.append(f"missing key '{k}'")
    if errs:
        die(errs)
    seen = set()
    for t in w["testers"]:
        tid = str(t.get("id", ""))
        if not re.fullmatch(r"[AB]-\d{2,}", tid):
            errs.append(f"bad tester id {tid!r}")
        if tid in seen:
            errs.append(f"duplicate tester {tid}")
        seen.add(tid)
        v = re.sub(r"[\[\]\s]", "", str(t.get("verdict", ""))).upper()
        if v not in W_:
            errs.append(f"{tid}: verdict {t.get('verdict')!r} not in {list(W_)}")
        t["verdict"], t["issues"] = v, [str(x) for x in (t.get("issues") or [])]
    defined = {i["key"]: i for i in w.get("issues", [])}
    for i in defined.values():
        if i.get("severity") not in SEV:
            errs.append(f"issue {i['key']}: severity must be one of {list(SEV)}")
    used = {k for t in w["testers"] for k in t["issues"]}
    if used - set(defined):
        warns.append(f"issue keys used by testers but not defined (severity assumed 'media'): {sorted(used - set(defined))}")
    if set(defined) - used:
        warns.append(f"issues defined but never raised by a tester: {sorted(set(defined) - used)}")
    if roster:
        ids = {t["id"] for t in roster["testers"]}
        if seen - ids:
            errs.append(f"testers not in the roster: {sorted(seen - ids)}")
        if len(seen) < len(ids):
            warns.append(f"{len(ids) - len(seen)} roster testers are not in this wave (fine only if the panel is deliberately smaller)")
    if errs:
        die(errs)
    for m in warns:
        log("WARN", m)
    w["_defined"] = defined
    w["stage"] = infer_stage(w, path)
    return w


def infer_stage(w: dict, path: str = "") -> str:
    """beta | full | "" : the "stage" key, else the file name suffix (-beta / -full), else the label ("beta", "completo", "full")."""
    st = str(w.get("stage") or "").strip().lower()
    if st in ("beta", "full"):
        return st
    m = re.search(r"-(beta|full)\.json$", os.path.basename(path or ""), re.I)
    if m:
        return m.group(1).lower()
    lab = str(w.get("label") or "").lower()
    if re.search(r"\b(gioco completo|completo|full)\b", lab):
        return "full"
    if re.search(r"\bbeta\b", lab):
        return "beta"
    return ""


STAGE_IT = {"beta": "beta", "full": "gioco completo", "": ""}
VERDICT_IT = {"WISHLIST": "Wishlist subito", "SALDI": "Aspetta i saldi", "IGNORO": "Scorre oltre", "REFUND": "Compra e rimborsa"}
SEV_IT = {"alta": "alta", "media": "media", "bassa": "bassa"}


def score(testers: list[dict]) -> float | None:
    return round(sum(W_[t["verdict"]] for t in testers) / len(testers) * 100, 1) + 0.0 if testers else None


def pct(a: int, n: int):
    return round(100 * a / n, 1) if n else None


def gate_of(w: dict, gate: float | None):
    if gate is not None:
        return gate, "manual"
    s = (w.get("controls") or {}).get("success")
    if s is not None:
        return max(30.0, round(0.8 * s, 1)), "80% of the success control (min 30)"
    return 35.0, "default"


def metrics(w: dict, gate: float | None = None) -> dict:
    ts, n = w["testers"], len(w["testers"])
    cnt = Counter(t["verdict"] for t in ts)
    clicks = [t["click"] for t in ts if isinstance(t.get("click"), bool)]
    pitch = [t["pitch_ok"] for t in ts if isinstance(t.get("pitch_ok"), bool)]
    buy = [t["would_buy"] for t in ts if isinstance(t.get("would_buy"), bool)]
    A, B = [t for t in ts if t["id"][0] == "A"], [t for t in ts if t["id"][0] == "B"]
    sa, sb = score(A), score(B)
    issues = []
    for key in {k for t in ts for k in t["issues"]}:
        d = w["_defined"].get(key, {})
        freq = sum(1 for t in ts if key in t["issues"])
        main = sum(1 for t in ts if t["issues"][:1] == [key])
        issues.append(dict(key=key, label=d.get("label", key), severity=d.get("severity", "media"), freq=freq,
                           pct=pct(freq, n), main_criticism=main, weighted=freq * SEV[d.get("severity", "media")],
                           groups=dict(A=sum(1 for t in A if key in t["issues"]), B=sum(1 for t in B if key in t["issues"])),
                           recommendation=d.get("recommendation")))
    issues.sort(key=lambda i: (-i["weighted"], -i["freq"], i["key"]))
    thr, how = gate_of(w, gate)
    sc = score(ts)
    blocks = ceiling_blocks(w)
    ceil = ceiling_of(blocks.get("version"), sc)          # margin and "near the ceiling" use THIS version's ceiling
    ceil_full = ceiling_of(blocks.get("full"), sc)
    est = (blocks.get("version") or {}).get("estimate") if isinstance(blocks.get("version"), dict) else None
    return dict(wave=w["wave"], date=w["date"], build=w.get("build"), label=w.get("label"), stage=w.get("stage"), evidence=w.get("evidence"),
                n=n, counts={k: cnt.get(k, 0) for k in W_}, pct={k: pct(cnt.get(k, 0), n) for k in W_}, score=sc,
                score_a=sa, score_b=sb, n_a=len(A), n_b=len(B),
                gap=None if sa is None or sb is None else round(abs(sa - sb), 1),
                click=dict(n=len(clicks), yes=sum(clicks), pct=pct(sum(clicks), len(clicks))),
                pitch=dict(n=len(pitch), yes=sum(pitch), pct=pct(sum(pitch), len(pitch))),
                buy=dict(n=len(buy), yes=sum(buy), pct=pct(sum(buy), len(buy))),
                issues=issues, controls=w.get("controls"), gate=dict(threshold=thr, basis=how, passed=sc is not None and sc >= thr), ceiling=ceil,
                ceiling_full=ceil_full, ceiling_estimate=None if ceil else (dict(value=str(est), note=str((blocks.get("version") or {}).get("note") or "")) if est else None))


def ceiling_blocks(w: dict) -> dict:
    """{"version": block, "full": block}. A legacy single block {"testers": [...]} is the FULL-game ceiling (testers imagined planned content)."""
    c = w.get("ceiling") or {}
    if not isinstance(c, dict):
        return {}
    if "version" in c or "full" in c:
        return {k: c.get(k) for k in ("version", "full") if c.get(k)}
    return {"full": c} if c.get("testers") else {}


def ceiling_of(block, sc):
    """Score, headroom and share of one ceiling block (None when it has no valid tester verdicts)."""
    cts = [t for t in ((block or {}).get("testers") or []) if str(t.get("verdict", "")).strip("[] ").upper() in W_]
    if not cts:
        return None
    for t in cts:
        t["verdict"] = str(t["verdict"]).strip("[] ").upper()
    cs = score(cts)
    stuck = [t for t in cts if t["verdict"] != "WISHLIST"]
    reasons = Counter((t.get("reason") or "").split(":")[0].strip().lower() or "n/d" for t in stuck)
    head = None if sc is None or cs is None else round(cs - sc, 1)
    share = None if not cs or sc is None or cs <= 0 else round(100 * sc / cs, 1)
    return dict(score=cs, n=len(cts), headroom=head, share=share, counts={k: sum(1 for t in cts if t["verdict"] == k) for k in W_},
                stuck=len(stuck), reasons=dict(reasons), near=(head is not None and (head <= CEIL_NEAR_POINTS or (share or 0) >= CEIL_NEAR_SHARE)))


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _n(v) -> str:
    """Numbers in Italian style (comma as decimal separator)."""
    return "-" if v is None else f"{v:g}".replace(".", ",") if isinstance(v, float) else str(v)


def md_metrics(m: dict) -> str:
    c, p = m["counts"], m["pct"]
    stage = STAGE_IT.get(m.get("stage") or "", m.get("stage") or "")
    gap = f"{_n(m['gap'])} punti" + (" **oltre 15: va spiegato (pubblico esperto contro pubblico largo)**" if m["gap"] and m["gap"] > GAP_FLAG else "")
    s = [f"## Ondata {m['wave']} ({m['date']})" + (f" · {stage}" if stage else "") + (f" · {m['label']}" if m.get("label") else ""),
         f"Versione: {m['build']} | Materiale mostrato: {m['evidence']} | Tester: {m['n']} (gruppo A {m['n_a']}, gruppo B {m['n_b']})", "",
         f"**Punteggio wishlist: {_n(m['score'])}** (soglia {_n(m['gate']['threshold'])}: {'superata' if m['gate']['passed'] else 'NON superata'}) | gruppo A {_n(m['score_a'])}, gruppo B {_n(m['score_b'])}, distanza {gap}", "",
         table(["Cosa farebbe il tester", "Quanti", "%"], [[VERDICT_IT[k], c[k], _n(p[k])] for k in W_]), "",
         f"Cliccherebbe al primo sguardo: {m['click']['yes']} su {m['click']['n']} ({_n(m['click']['pct'])}%) | "
         f"Ha capito il gioco dal pitch: {m['pitch']['yes']} su {m['pitch']['n']} ({_n(m['pitch']['pct'])}%)"]
    if m.get("buy", {}).get("n"):
        s.append(f"Pagherebbe il prezzo previsto: {m['buy']['yes']} su {m['buy']['n']} ({_n(m['buy']['pct'])}%) (beta gratuita: quanto fa venire voglia di comprare il gioco completo)")
    if m.get("controls"):
        s.append("Capsule di confronto (punteggio dato dal panel): " + ", ".join(f"{'riuscita' if k == 'success' else 'debole' if k == 'weak' else k} {_n(v)}" for k, v in m["controls"].items()))
    c, cf, ce = m.get("ceiling"), m.get("ceiling_full"), m.get("ceiling_estimate")
    if c:
        s += ["", "### Tetto di questa versione: il massimo con le sole correzioni possibili adesso (bug, chiarezza, rifinitura; niente contenuti nuovi)",
              f"**Tetto di questa versione: {_n(c['score'])}** | oggi {_n(m['score'])} = {_n(c['share'])}% del tetto | margine ancora da prendere: **{_n(c['headroom'])} punti**",
              "Verdetti al tetto: " + ", ".join(f"{VERDICT_IT[k]} {v}" for k, v in c["counts"].items()) +
              f" | non arrivano a Wishlist nemmeno così: {c['stuck']} su {c['n']}" + (f" (motivi: {', '.join(f'{k} {v}' for k, v in c['reasons'].items())})" if c["reasons"] else ""),
              ("**Vicino al tetto di questa versione: smettere di aggiungere idee e passare ai test con persone vere.**" if c["near"] else
               "Ancora margine: lavorare solo sui problemi risolvibili adesso, non su idee nuove.")]
    elif ce:
        s += ["", f"### Tetto di questa versione: non misurato · stima {ce['value']} [STIMA]" + (f" ({ce['note']})" if ce.get("note") else "")]
    if cf:
        s += ["", "### Tetto del gioco completo: con i contenuti pianificati (non è margine di oggi)",
              f"**Tetto del gioco completo: {_n(cf['score'])}** | non arrivano a Wishlist nemmeno così: {cf['stuck']} su {cf['n']}"
              + (f" (motivi: {', '.join(f'{k} {v}' for k, v in cf['reasons'].items())})" if cf["reasons"] else "")]
    s += ["", "### Problemi (quanti li citano × gravità)", table(
        ["Problema", "Gravità", "Citato da", "% del panel", "Critica principale di", "A / B", "Cosa fare"],
        [[i["label"], SEV_IT.get(i["severity"], i["severity"]), i["freq"], _n(i["pct"]), i["main_criticism"], f"{i['groups']['A']} / {i['groups']['B']}", i["recommendation"] or ""]
         for i in m["issues"]]), "",
         "_Panel simulato: i punteggi ordinano i problemi, non prevedono le vendite. Con 54 tester ogni percentuale ha un margine di circa ±13 punti, e il campione è simulato._"]
    return "\n".join(s)


def md_delta(a: dict, b: dict, ma: dict, mb: dict, noise: float) -> str:
    ta, tb = {t["id"]: t for t in a["testers"]}, {t["id"]: t for t in b["testers"]}
    common = sorted(set(ta) & set(tb))
    only_a, only_b = sorted(set(ta) - set(tb)), sorted(set(tb) - set(ta))
    sa, sb = score([ta[i] for i in common]), score([tb[i] for i in common])
    fixes = {f.get("issue"): f.get("what") for f in b.get("fixes", [])}
    trans = Counter((ta[i]["verdict"], tb[i]["verdict"]) for i in common)
    stage = STAGE_IT.get(b.get("stage") or "", "")
    out = [f"## Cosa è cambiato: ondata {a['wave']} ({a['date']}) -> ondata {b['wave']} ({b['date']})" + (f" · {stage}" if stage else ""),
           f"Versioni: {a.get('build')} -> {b.get('build')}", "",
           f"**Punteggio wishlist sugli stessi {len(common)} tester: {_n(sa)} -> {_n(sb)} ({sb - sa:+.1f})**".replace(".", ",") if common else "Nessun tester in comune: non si possono confrontare.",
           f"Tutti i tester: {_n(ma['score'])} -> {_n(mb['score'])} ({mb['score'] - ma['score']:+.1f})".replace(".", ",")
           + (f" | nuovi nell'ondata {b['wave']}: {', '.join(only_b)}" if only_b else "") + (f" | usciti: {', '.join(only_a)}" if only_a else ""), ""]
    out += ["### Verdetti che cambiano (stessi tester)", table(["Prima", "Dopo", "Tester"], [[VERDICT_IT[x], VERDICT_IT[y], n] for (x, y), n in sorted(trans.items(), key=lambda kv: (-kv[1], kv[0])) if x != y]) if any(x != y for x, y in trans) else "Nessun verdetto è cambiato.", ""]
    keys = sorted({i["key"] for i in ma["issues"]} | {i["key"] for i in mb["issues"]})
    ia, ib = {i["key"]: i for i in ma["issues"]}, {i["key"]: i for i in mb["issues"]}
    rows = []
    for k in keys:
        pa, pb = (ia.get(k) or {}).get("pct") or 0.0, (ib.get(k) or {}).get("pct") or 0.0
        fa, fb = (ia.get(k) or {}).get("freq", 0), (ib.get(k) or {}).get("freq", 0)
        d = pb - pa
        st = ("NUOVO" if pa == 0 else "RISOLTO" if pb == 0 else "INVARIATO" if abs(d) < noise else "MIGLIORATO" if d < 0 else "PEGGIORATO")
        rows.append([(ib.get(k) or ia.get(k))["label"], (ib.get(k) or ia.get(k))["severity"], f"{fa} su {ma['n']}", f"{fb} su {mb['n']}", f"{d:+.1f} punti".replace(".", ","), st, fixes.get(k, "")])
    order = {"PEGGIORATO": 0, "NUOVO": 1, "INVARIATO": 2, "MIGLIORATO": 3, "RISOLTO": 4}
    rows.sort(key=lambda r: (order[r[5]], r[0]))
    out += ["### Effetto su ogni problema", table(["Problema", "Gravità", "Prima", "Dopo", "Variazione", "Esito", "Correzione fatta"], rows),
            f"_L'esito usa una fascia di rumore di ±{noise:g} punti percentuali (valore di default: un'opinione, si cambia con --noise)._", ""]
    chg = [[i, f"{VERDICT_IT[ta[i]['verdict']]} -> {VERDICT_IT[tb[i]['verdict']]}", (ta[i]['issues'] or ['-'])[0], (tb[i]['issues'] or ['-'])[0], ""]
           for i in common if ta[i]["verdict"] != tb[i]["verdict"] or ta[i]["issues"][:1] != tb[i]["issues"][:1]]
    out += ["### Per tester (verdetto o critica principale cambiati)", table(["ID", "Verdetto", "Critica principale prima", "Critica principale dopo", "Causa attribuita"], chg) if chg else "Nessun cambiamento.", "",
            "_Stessi tester simulati con gli stessi gusti: il confronto indica una direzione, non è una prova. Le migliorie importanti si confermano nel test reale (Gate B)._"]
    return "\n".join(out)


def spark(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    return "".join("▁▂▃▄▅▆▇█"[0 if hi == lo else int((v - lo) / (hi - lo) * 7)] for v in vals)


def load_dir(d: str, roster):
    files = sorted(glob.glob(os.path.join(d, "w[0-9]*.json")), key=lambda p: int(re.match(r"w(\d+)", os.path.basename(p)).group(1)))
    ws = [load_wave(f, roster) for f in files]
    if not ws:
        raise SystemExit(f"no wave files (w01-....json) in {d}")
    return ws


def cmd_metrics(a):
    roster = load_json(a.roster) if a.roster else None
    m = metrics(load_wave(a.wave, roster), a.gate)
    if a.out and a.out.endswith(".json"):
        write_json(m, a.out)
    elif a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(md_metrics(m) + "\n")
        log(f"wrote {a.out}")
    else:
        print(md_metrics(m))


def cmd_delta(a):
    roster = load_json(a.roster) if a.roster else None
    wa, wb = load_wave(a.before, roster), load_wave(a.after, roster)
    if wb["wave"] <= wa["wave"]:
        log("WARN 'after' wave number is not greater than 'before'")
    txt = md_delta(wa, wb, metrics(wa), metrics(wb), a.noise)
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(txt + "\n")
        log(f"wrote {a.out}")
    else:
        print(txt)


def cmd_timeline(a):
    roster = load_json(a.roster) if a.roster else None
    ms = [metrics(w, a.gate) for w in load_dir(a.dir, roster)]
    rows, csv_rows, prevs = [], [], {}
    for m in ms:
        prev = prevs.get(m.get("stage") or "beta")   # beta and full waves are compared only with waves of the same kind
        d = "" if prev is None else f"{m['score'] - prev['score']:+.1f}"
        top = m["issues"][0]["label"] if m["issues"] else "-"
        open_high = sum(1 for i in m["issues"] if i["severity"] == "alta")
        rows.append([m["wave"], STAGE_IT.get(m.get("stage") or "", "") or "-", m["date"], m["build"], m["n"], m["score"], d, f"{m['pct']['WISHLIST']}/{m['pct']['SALDI']}/{m['pct']['IGNORO']}/{m['pct']['REFUND']}",
                     m["click"]["pct"], m["pitch"]["pct"], f"{m['score_a']} / {m['score_b']}", open_high, top,
                     f"{'superato' if m['gate']['passed'] else 'sotto'} ({m['gate']['threshold']})",
                     (m["ceiling"] or {}).get("score", "-"), (m["ceiling"] or {}).get("headroom", "-"), (m.get("ceiling_full") or {}).get("score", "-")])
        csv_rows.append(dict(wave=m["wave"], stage=m.get("stage") or "", date=m["date"], build=m["build"], n=m["n"], score=m["score"], delta=d,
                             wishlist_pct=m["pct"]["WISHLIST"], saldi_pct=m["pct"]["SALDI"], ignoro_pct=m["pct"]["IGNORO"],
                             refund_pct=m["pct"]["REFUND"], click_pct=m["click"]["pct"], pitch_pct=m["pitch"]["pct"], buy_pct=m["buy"]["pct"],
                             score_a=m["score_a"], score_b=m["score_b"], high_severity_issues=open_high, top_issue=top,
                             gate=m["gate"]["threshold"], gate_passed=m["gate"]["passed"],
                             ceiling=(m["ceiling"] or {}).get("score"), headroom=(m["ceiling"] or {}).get("headroom"),
                             ceiling_estimate=(m.get("ceiling_estimate") or {}).get("value"), ceiling_full=(m.get("ceiling_full") or {}).get("score")))
        prevs[m.get("stage") or "beta"] = m
    txt = ["# Focus group: andamento delle ondate", "",
           f"Andamento del punteggio: `{spark([m['score'] for m in ms])}` ({_n(ms[0]['score'])} -> {_n(ms[-1]['score'])}, {len(ms)} ondate)", "",
           table(["Ondata", "Tipo", "Data", "Versione", "Tester", "Punteggio", "Variazione", "Wishlist/Saldi/Ignora/Rimborso %", "Click %", "Pitch %", "A / B", "Problemi gravi", "Problema principale", "Gate A", "Tetto di questa versione", "Margine", "Tetto del gioco completo"], rows), "",
           "_Ondate simulate con gli stessi tester: indicano una direzione, non sono una prova né una previsione di vendita. Differenze di pochi punti sono rumore. Beta e gioco completo si confrontano solo con ondate dello stesso tipo._"]
    if len(ms) > 1:
        first, last = {i["key"]: i for i in ms[0]["issues"]}, {i["key"]: i for i in ms[-1]["issues"]}
        gone = sorted(first[k]["label"] for k in first if k not in last)
        new = sorted(last[k]["label"] for k in last if k not in first)
        txt += ["", f"Dall'ondata {ms[0]['wave']}: problemi spariti: {', '.join(gone) or 'nessuno'}; problemi nuovi: {', '.join(new) or 'nessuno'}."]
    out = "\n".join(txt) + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(out)
        log(f"wrote {a.out}")
    else:
        print(out)
    if a.csv:
        write_csv(csv_rows, a.csv)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("metrics", help="validate one wave and compute its metrics")
    m.add_argument("wave"); m.add_argument("--roster"); m.add_argument("--gate", type=float); m.add_argument("-o", "--out")
    m.set_defaults(fn=cmd_metrics)
    d = sub.add_parser("delta", help="compare two waves")
    d.add_argument("before"); d.add_argument("after"); d.add_argument("--roster")
    d.add_argument("--noise", type=float, default=10.0, help="percentage-point band treated as unchanged (default 10: one tester moves 2-4 points)")
    d.add_argument("-o", "--out"); d.set_defaults(fn=cmd_delta)
    t = sub.add_parser("timeline", help="all waves of a folder, with trends")
    t.add_argument("dir"); t.add_argument("--roster"); t.add_argument("--gate", type=float)
    t.add_argument("-o", "--out"); t.add_argument("--csv"); t.set_defaults(fn=cmd_timeline)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
