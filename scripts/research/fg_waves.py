#!/usr/bin/env python3
"""Focus-group waves: validate, compute metrics, compare two waves, render the timeline.

The simulated panel judges the game; THIS tool does the arithmetic, so scores, deltas and trends are
reproducible and never computed by hand. A wave is one run of the (same) roster on one state of the game.

Wave file (launch/fg/waves/w01-YYYY-MM-DD.json), written after the panel has judged:
  {
    "wave": 1, "date": "2026-10-06", "build": "v0.3 / commit abc123", "label": "baseline",
    "evidence": "capsule v1, pitch v1, build 0.3",
    "controls": {"success": 41.2, "weak": 6.0},            # optional: scores the panel gave to control capsules
    "testers": [{"id": "A-01", "verdict": "WISHLIST", "click": true, "pitch_ok": true,
                 "issues": ["slow-opening", "tutorial-text"]}, ...],   # first issue = main criticism
    "issues":  [{"key": "slow-opening", "label": "Apertura lenta", "severity": "alta",
                 "recommendation": "..."}, ...],
    "fixes":   [{"issue": "slow-opening", "what": "tutorial shortened"}]   # waves > 1: fixes since the previous wave
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
GAP_FLAG = 15  # A/B score gap above which the skill requires an explanation


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
    return w


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
    return dict(wave=w["wave"], date=w["date"], build=w.get("build"), label=w.get("label"), evidence=w.get("evidence"),
                n=n, counts={k: cnt.get(k, 0) for k in W_}, pct={k: pct(cnt.get(k, 0), n) for k in W_}, score=sc,
                score_a=sa, score_b=sb, n_a=len(A), n_b=len(B),
                gap=None if sa is None or sb is None else round(abs(sa - sb), 1),
                click=dict(n=len(clicks), yes=sum(clicks), pct=pct(sum(clicks), len(clicks))),
                pitch=dict(n=len(pitch), yes=sum(pitch), pct=pct(sum(pitch), len(pitch))),
                issues=issues, controls=w.get("controls"), gate=dict(threshold=thr, basis=how, passed=sc is not None and sc >= thr))


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if c is None else str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def md_metrics(m: dict) -> str:
    c, p = m["counts"], m["pct"]
    gap = f"{m['gap']} points" + (" **> 15: explain it (core vs wide audience)**" if m["gap"] and m["gap"] > GAP_FLAG else "")
    s = [f"## Wave {m['wave']} ({m['date']}) {m['label'] or ''}", f"Build: {m['build']} | Evidence: {m['evidence']} | N = {m['n']} (A {m['n_a']}, B {m['n_b']})", "",
         f"**Wishlist score: {m['score']}** (gate {m['gate']['threshold']}, {m['gate']['basis']}: "
         f"{'PASS' if m['gate']['passed'] else 'BELOW'}) | A {m['score_a']} vs B {m['score_b']}, gap {gap}", "",
         table(["Verdict", "Count", "%"], [[k, c[k], p[k]] for k in W_]), "",
         f"First-glance click: {m['click']['yes']}/{m['click']['n']} ({m['click']['pct']}%) | "
         f"Pitch understood: {m['pitch']['yes']}/{m['pitch']['n']} ({m['pitch']['pct']}%)"]
    if m.get("controls"):
        s.append(f"Controls (panel score of reference capsules): {m['controls']}")
    s += ["", "### Issues (frequency x severity)", table(
        ["Issue", "Severity", "Seen by", "% of panel", "Main criticism of", "A / B", "Recommendation"],
        [[i["label"], i["severity"], i["freq"], i["pct"], i["main_criticism"], f"{i['groups']['A']} / {i['groups']['B']}", i["recommendation"]]
         for i in m["issues"]]), "",
         "_Simulated panel: scores order problems, they do not predict sales. With N=54 any percentage carries roughly +-13 points of uncertainty, and the sample is simulated._"]
    return "\n".join(s)


def md_delta(a: dict, b: dict, ma: dict, mb: dict, noise: float) -> str:
    ta, tb = {t["id"]: t for t in a["testers"]}, {t["id"]: t for t in b["testers"]}
    common = sorted(set(ta) & set(tb))
    only_a, only_b = sorted(set(ta) - set(tb)), sorted(set(tb) - set(ta))
    sa, sb = score([ta[i] for i in common]), score([tb[i] for i in common])
    fixes = {f.get("issue"): f.get("what") for f in b.get("fixes", [])}
    trans = Counter((ta[i]["verdict"], tb[i]["verdict"]) for i in common)
    out = [f"## Delta: wave {a['wave']} ({a['date']}) -> wave {b['wave']} ({b['date']})",
           f"Builds: {a.get('build')} -> {b.get('build')}", "",
           f"**Wishlist score on the same {len(common)} testers: {sa} -> {sb} ({sb - sa:+.1f})**" if common else "No tester in common: cannot compare.",
           f"All testers: {ma['score']} -> {mb['score']} ({mb['score'] - ma['score']:+.1f})"
           + (f" | new in wave {b['wave']}: {', '.join(only_b)}" if only_b else "") + (f" | dropped: {', '.join(only_a)}" if only_a else ""), ""]
    out += ["### Verdict movements (same testers)", table(["From", "To", "Testers"], [[x, y, n] for (x, y), n in sorted(trans.items(), key=lambda kv: (-kv[1], kv[0])) if x != y]) if any(x != y for x, y in trans) else "No verdict changed.", ""]
    keys = sorted({i["key"] for i in ma["issues"]} | {i["key"] for i in mb["issues"]})
    ia, ib = {i["key"]: i for i in ma["issues"]}, {i["key"]: i for i in mb["issues"]}
    rows = []
    for k in keys:
        pa, pb = (ia.get(k) or {}).get("pct") or 0.0, (ib.get(k) or {}).get("pct") or 0.0
        fa, fb = (ia.get(k) or {}).get("freq", 0), (ib.get(k) or {}).get("freq", 0)
        d = pb - pa
        st = ("NEW" if pa == 0 else "RESOLVED" if pb == 0 else "UNCHANGED" if abs(d) < noise else "IMPROVED" if d < 0 else "WORSE")
        rows.append([(ib.get(k) or ia.get(k))["label"], (ib.get(k) or ia.get(k))["severity"], f"{fa}/{ma['n']}", f"{fb}/{mb['n']}", f"{d:+.1f} pp", st, fixes.get(k, "")])
    order = {"WORSE": 0, "NEW": 1, "UNCHANGED": 2, "IMPROVED": 3, "RESOLVED": 4}
    rows.sort(key=lambda r: (order[r[5]], r[0]))
    out += ["### Effect on each issue", table(["Issue", "Severity", "Before", "After", "Change", "Status", "Fix applied"], rows),
            f"_Status uses a noise band of +-{noise} percentage points (default is an opinion, adjust with --noise)._", ""]
    chg = [[i, f"{ta[i]['verdict']} -> {tb[i]['verdict']}", (ta[i]['issues'] or ['-'])[0], (tb[i]['issues'] or ['-'])[0], ""]
           for i in common if ta[i]["verdict"] != tb[i]["verdict"] or ta[i]["issues"][:1] != tb[i]["issues"][:1]]
    out += ["### Per tester (verdict or main criticism changed)", table(["ID", "Verdict", "Main criticism before", "Main criticism after", "Attributed cause"], chg) if chg else "No change.", "",
            "_Same simulated testers with the same biases: the delta is directional, not proof. Confirm important improvements in the real test (Gate B)._"]
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
    rows, csv_rows, prev = [], [], None
    for m in ms:
        d = "" if prev is None else f"{m['score'] - prev['score']:+.1f}"
        top = m["issues"][0]["label"] if m["issues"] else "-"
        open_high = sum(1 for i in m["issues"] if i["severity"] == "alta")
        rows.append([m["wave"], m["date"], m["build"], m["n"], m["score"], d, f"{m['pct']['WISHLIST']}/{m['pct']['SALDI']}/{m['pct']['IGNORO']}/{m['pct']['REFUND']}",
                     m["click"]["pct"], m["pitch"]["pct"], f"{m['score_a']} / {m['score_b']}", open_high, top,
                     f"{'PASS' if m['gate']['passed'] else 'below'} ({m['gate']['threshold']})"])
        csv_rows.append(dict(wave=m["wave"], date=m["date"], build=m["build"], n=m["n"], score=m["score"], delta=d,
                             wishlist_pct=m["pct"]["WISHLIST"], saldi_pct=m["pct"]["SALDI"], ignoro_pct=m["pct"]["IGNORO"],
                             refund_pct=m["pct"]["REFUND"], click_pct=m["click"]["pct"], pitch_pct=m["pitch"]["pct"],
                             score_a=m["score_a"], score_b=m["score_b"], high_severity_issues=open_high, top_issue=top,
                             gate=m["gate"]["threshold"], gate_passed=m["gate"]["passed"]))
        prev = m
    txt = ["# Focus group timeline", "",
           f"Score trend: `{spark([m['score'] for m in ms])}` ({ms[0]['score']} -> {ms[-1]['score']}, {len(ms)} waves)", "",
           table(["Wave", "Date", "Build", "N", "Score", "Δ", "W/S/I/R %", "Click %", "Pitch %", "A / B", "High-sev. issues", "Top issue", "Gate A"], rows), "",
           "_Simulated waves with the same roster: directional trend, not proof or sales forecast. Differences within a few points are noise._"]
    if len(ms) > 1:
        first, last = {i["key"]: i for i in ms[0]["issues"]}, {i["key"]: i for i in ms[-1]["issues"]}
        gone = sorted(first[k]["label"] for k in first if k not in last)
        new = sorted(last[k]["label"] for k in last if k not in first)
        txt += ["", f"Since wave {ms[0]['wave']}: resolved issues: {', '.join(gone) or 'none'}; new issues: {', '.join(new) or 'none'}."]
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
