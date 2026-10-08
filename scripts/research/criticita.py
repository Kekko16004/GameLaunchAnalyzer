#!/usr/bin/env python3
"""Criticalities ("criticità"), wave by wave, gate by gate, with their evolution. Used by status_page.py and report_html.py.

Sources, merged:
  1. the focus-group wave files (launch/fg/waves/wNN-*.json, same files fg_waves.py reads): the issues each wave found, how many
     testers raised them, severity, recommendation, optional `gate` ("0", "A", "B", "C") and `area`, and the fixes made before the wave.
     Waves of the two stages (beta / full) are kept apart. Everything is recomputed from the wave files at each run, so the view is
     always current: add a wave, regenerate the page.
  2. launch/criticita.csv: criticalities that do not come from a wave (the real test of Gate B, real reviews, pre-mortem, advice
     of someone): key,label,severity,source,gate,area,opened,status,closed,note   (opened: date or "ondata N")
  3. status.json -> critiques_by_wave (hand-written, see status_page.py): used for the waves that have no wave file.

What the page shows (one card, buttons on top): one panel per wave (every issue with severity, % of testers, change from the previous
wave, status new / persistent / rising / falling / back, gate, what to do; then the ones resolved in that wave with the fix), a panel
"per cancello" (which issues belong to which gate, born in which wave, open or resolved), and the "evoluzione" matrix (issue x wave).

  criticita.py add --key slow-opening --label "Apertura lenta" --severity alta --source playtest --gate B --opened 2027-01-10 [--note ...]
  criticita.py close slow-opening [--date 2027-01-20]
  criticita.py list
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import html
import json
import os
import re

import charts as C
import common  # noqa: F401  (side effect: UTF-8 stdout, so accents and symbols do not crash on a Windows console)

NOISE = 10   # percentage points: smaller changes between waves are noise (same default as fg_waves.py delta)
SEV = {"alta": 3, "media": 2, "bassa": 1}
SEV_PILL = {"alta": "crit", "media": "warn", "bassa": "mute"}
STAGE_LABEL = {"beta": "beta", "full": "gioco completo"}
STAGE_ORDER = {"": 0, "beta": 0, "full": 1}
STATUS_PILL = {"nuova": ("new", "Nuova"), "presente": ("mute", "Presente"), "persistente": ("mute", "Persistente"), "in aumento": ("crit", "In aumento"), "in calo": ("ok", "In calo"),
               "ricomparsa": ("warn", "Ricomparsa"), "risolta": ("ok", "Risolta"), "aperta": ("warn", "Aperta"), "in corso": ("warn", "In corso")}
SOURCES = {"onda": "ondata", "playtest": "test reale", "recensioni": "recensioni reali", "premortem": "pre-mortem", "altro": "altro"}
FIELDS = ["key", "label", "severity", "source", "gate", "area", "opened", "status", "closed", "note"]
MONTHS = "gen feb mar apr mag giu lug ago set ott nov dic".split()

CSS = """
.seg{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px}.seg button{background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:6px 12px;cursor:pointer;font:inherit;font-size:.85rem}
.seg button[aria-pressed="true"]{border-color:var(--s1);box-shadow:inset 0 0 0 1px var(--s1);font-weight:600}.cp[hidden]{display:none}
.pill{display:inline-block;border:1px solid var(--ring);border-radius:999px;padding:1px 9px;font-size:.78rem;font-weight:600;white-space:nowrap;background:var(--surface);color:var(--ink)}
.pill.crit{border-color:var(--crit)}.pill.warn{border-color:var(--warn)}.pill.ok{border-color:var(--good)}.pill.new{border-color:var(--s1)}.pill.mute{color:var(--ink2)}
.cp h4{margin:16px 0 6px;font-size:.95rem}.cp .meta{color:var(--ink2);font-size:.9rem;margin:0 0 8px}td.heat{text-align:center;font-variant-numeric:tabular-nums;min-width:64px}
.cp .chart svg{max-width:640px}.gatehead{display:flex;gap:10px;align-items:center;margin:14px 0 4px}.gatehead strong{font-size:1rem}svg.spark{vertical-align:middle}
"""
JS = """
(function(){document.querySelectorAll('[data-crit]').forEach(function(box){var bs=box.querySelectorAll('.seg button'),ps=box.querySelectorAll('.cp');
bs.forEach(function(b){b.addEventListener('click',function(){var w=b.getAttribute('data-p');bs.forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});ps.forEach(function(p){p.hidden=p.getAttribute('data-p')!==w;});});});});})();
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _date(s: str) -> str:
    try:
        d = dt.date.fromisoformat(str(s)[:10])
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    except ValueError:
        return str(s or "")


def pill(kind: str, text: str) -> str:
    return f'<span class="pill {kind}">{esc(text)}</span>'


def sev_pill(sev: str) -> str:
    return pill(SEV_PILL.get(sev, "mute"), f"Gravità {sev}" if sev else "Gravità n/d")


def status_pill(st: str) -> str:
    kind, text = STATUS_PILL.get(st, ("mute", st or "n/d"))
    return pill(kind, text)


def gate_key(g) -> str:
    g = str(g or "").strip().upper()
    return g[:1] if g[:1] in ("0", "A", "B", "C") else ""


def wave_label(w: dict) -> str:
    st = STAGE_LABEL.get(w.get("stage") or "", w.get("stage") or "")
    return f"Ondata {w['n']}" + (f" · {st}" if st and any(x.get("stage") for x in w.get("_all", [w])) else "")


# ---------------------------------------------------------------- data
def load_waves(root: str) -> tuple[list, list]:
    """(waves, problems). Waves come from the wave files, ordered by number and stage (beta before full)."""
    wd = os.path.join(root, "fg", "waves")
    files = glob.glob(os.path.join(wd, "w[0-9]*.json"))
    if not files:
        return [], []
    import fg_waves
    rp = os.path.join(root, "fg", "roster.json")
    roster = None
    try:
        roster = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else None
    except (OSError, ValueError):
        roster = None
    waves, problems = [], []
    for f in files:
        try:
            w = fg_waves.load_wave(f, roster)
            m = fg_waves.metrics(w)
        except (SystemExit, Exception) as e:   # a broken wave file must not take the page down: say so in the panel
            problems.append(f"{os.path.basename(f)}: {str(e).splitlines()[-1][:120] if str(e) else type(e).__name__}")
            continue
        issues = []
        for x in m["issues"]:
            d = w["_defined"].get(x["key"], {})
            issues.append(dict(x, gate=gate_key(d.get("gate")), area=d.get("area") or ""))
        waves.append(dict(n=int(w["wave"]), stage=(w.get("stage") or ""), date=str(w["date"]), build=w.get("build"), label=w.get("label"), score=m["score"], gate_threshold=m["gate"]["threshold"],
                          n_testers=m["n"], issues=issues, fixes=w.get("fixes") or []))
    waves.sort(key=lambda w: (w["n"], STAGE_ORDER.get(w["stage"], 0), w["date"]))
    for w in waves:
        w["_all"] = waves
    return waves, problems


def read_register(root: str) -> list[dict]:
    p = os.path.join(root, "criticita.csv")
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("key") or r.get("label") or "").strip():
                sev = (r.get("severity") or "media").strip().lower()
                out.append(dict(key=(r.get("key") or r.get("label")).strip(), label=(r.get("label") or r.get("key")).strip(), severity=sev if sev in SEV else "media",
                                source=(r.get("source") or "altro").strip().lower(), gate=gate_key(r.get("gate")), area=(r.get("area") or "").strip(), opened=(r.get("opened") or "").strip(),
                                status=("risolta" if (r.get("status") or "").strip().lower().startswith("ris") else "in corso" if (r.get("status") or "").strip().lower().startswith("in c") else "aperta"),
                                closed=(r.get("closed") or "").strip(), note=(r.get("note") or "").strip()))
    return out


def wave_index_for(opened: str, waves: list) -> int | None:
    """Index of the wave a manual criticality belongs to: "ondata N" or the last wave whose date is not after `opened`."""
    m = re.search(r"ondata\s*(\d+)", opened or "", re.I)
    if m:
        for i, w in enumerate(waves):
            if w["n"] == int(m.group(1)):
                return i
    try:
        d = dt.date.fromisoformat((opened or "")[:10])
    except ValueError:
        return None
    idx = None
    for i, w in enumerate(waves):
        try:
            if dt.date.fromisoformat(w["date"][:10]) <= d:
                idx = i
        except ValueError:
            pass
    return idx


def analyse(waves: list) -> dict:
    """Per wave: rows with status against the previous wave, resolved issues with their fix; per issue: history and state today."""
    seen: set = set()
    hist: dict = {}
    panels = []
    for i, w in enumerate(waves):
        cur = {x["key"]: x for x in w["issues"]}
        prev = {x["key"]: x for x in waves[i - 1]["issues"]} if i else {}
        rows = []
        for k, x in cur.items():
            if i == 0:
                st, delta = "presente", None
            elif k not in prev:
                st, delta = ("ricomparsa" if k in seen else "nuova"), None
            else:
                delta = round(x["pct"] - prev[k]["pct"], 1)
                st = "in aumento" if delta >= NOISE else "in calo" if delta <= -NOISE else "persistente"
            rows.append(dict(x, status=st, delta=delta))
        rows.sort(key=lambda r: (-SEV.get(r["severity"], 2), -(r["pct"] or 0), r["key"]))
        resolved = []
        for k, x in prev.items():
            if k not in cur:
                fix = next((f.get("what") for f in w["fixes"] if f.get("issue") == k), None)
                resolved.append(dict(x, fix=fix))
        resolved.sort(key=lambda r: (-SEV.get(r["severity"], 2), r["key"]))
        for k, x in cur.items():
            h = hist.setdefault(k, dict(key=k, first=i, points={}, label=x["label"], severity=x["severity"], gate=x["gate"], area=x["area"], recommendation=x.get("recommendation")))
            h["points"][i] = x["pct"]
            h.update(label=x["label"], severity=x["severity"], recommendation=x.get("recommendation") or h["recommendation"])
            if x["gate"]:
                h["gate"] = x["gate"]
            if x["area"]:
                h["area"] = x["area"]
        seen |= set(cur)
        panels.append(dict(index=i, wave=w, rows=rows, resolved=resolved, fixes=w["fixes"],
                           counts=dict(persistenti=sum(1 for r in rows if r["status"] in ("persistente", "in aumento", "in calo", "presente")), nuove=sum(1 for r in rows if r["status"] in ("nuova", "ricomparsa")), risolte=len(resolved))))
    last = len(waves) - 1
    issues = []
    for h in hist.values():
        is_open = last in h["points"]
        gone = max(h["points"]) if h["points"] else 0
        issues.append(dict(h, open=is_open, today="aperta" if is_open else "risolta", last_pct=h["points"].get(max(h["points"])), resolved_in=None if is_open else gone + 1))
    issues.sort(key=lambda x: (not x["open"], -SEV.get(x["severity"], 2), -(x["last_pct"] or 0), x["key"]))
    return dict(panels=panels, issues=issues)


# ---------------------------------------------------------------- html
def spark(points: dict, n: int, label: str) -> str:
    if len(points) < 1:
        return ""
    W, H = 70, 18
    xs = [4 + (W - 8) * (i / max(n - 1, 1)) for i in range(n)]
    mx = max(max(points.values()), 1)
    pts = [(xs[i], H - 3 - (H - 6) * (points[i] / mx)) for i in sorted(points)]
    d = " ".join(f"{'M' if k == 0 or sorted(points)[k] - sorted(points)[k - 1] > 1 else 'L'}{x:.1f},{y:.1f}" for k, (x, y) in enumerate(pts))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="var(--s1)"/>' for x, y in pts)
    return f'<svg class="spark" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}"><path d="{d}" fill="none" stroke="var(--s1)" stroke-width="1.5"/>{dots}</svg>'


def _delta(d) -> str:
    return "" if d is None else (f"+{d:g} punti" if d > 0 else f"{d:g} punti" if d < 0 else "invariato")


def _table(head: list, rows: list) -> str:
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    return f'<div class="wrap"><table><thead><tr>{h}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def wave_panel(p: dict, manual: list, gate_names: dict) -> str:
    w = p["wave"]
    prev_score = None
    head = f'<p class="meta"><strong>{esc(wave_label(w))}</strong> · {esc(_date(w["date"]))}' + (f' · versione {esc(w["build"])}' if w.get("build") else "") + f' · punteggio <strong>{esc(w["score"])}</strong> (soglia {esc(w["gate_threshold"])}) · {w["n_testers"]} tester · {len(p["rows"])} criticità</p>'
    out = [head]
    if p["fixes"]:
        out.append("<h4>Cosa è stato corretto prima di questa ondata</h4><ul>" + "".join(f'<li>{esc(f.get("what"))}' + (f' <span class="note">(criticità: {esc(f.get("issue"))})</span>' if f.get("issue") else "") + "</li>" for f in p["fixes"]) + "</ul>")
    if p["rows"]:
        body = []
        for r in p["rows"]:
            g = gate_names.get(r["gate"], f"Gate {r['gate']}") if r["gate"] else "—"
            body.append(f'<tr><td><strong>{esc(r["label"])}</strong>' + (f'<br><span class="note">{esc(r["area"])}</span>' if r["area"] else "") + f'</td><td>{sev_pill(r["severity"])}</td><td class="n">{r["pct"]:g}%<br><span class="note">{r["freq"]} su {w["n_testers"]}</span></td>'
                        f'<td>{status_pill(r["status"])}' + (f'<br><span class="note">{esc(_delta(r["delta"]))}</span>' if r["delta"] is not None else "") + f'</td><td>{esc(g)}</td><td>{esc(r.get("recommendation") or "")}</td></tr>')
        out.append("<h4>Criticità trovate in questa ondata</h4>" + _table(["Criticità", "Gravità", "Tester", "Stato", "Cancello", "Cosa fare"], body))
    else:
        out.append("<p>Nessuna criticità segnalata dai tester in questa ondata.</p>")
    if p["resolved"]:
        out.append("<h4>Risolte in questa ondata (c'erano nella precedente)</h4><ul>" + "".join(f'<li>{pill("ok", "Risolta")} <strong>{esc(r["label"])}</strong> (era al {r["pct"]:g}%)' + (f' · correzione: {esc(r["fix"])}' if r.get("fix") else "") + "</li>" for r in p["resolved"]) + "</ul>")
    if manual:
        out.append("<h4>Da altre fonti in questo periodo</h4>" + _table(["Criticità", "Fonte", "Gravità", "Stato", "Cancello", "Nota"], [
            f'<tr><td><strong>{esc(m["label"])}</strong></td><td>{esc(SOURCES.get(m["source"], m["source"]))}</td><td>{sev_pill(m["severity"])}</td><td>{status_pill(m["status"])}</td><td>{esc(gate_names.get(m["gate"], "") if m["gate"] else "—")}</td><td>{esc(m["note"])}</td></tr>' for m in manual]))
    return "".join(out)


def manual_wave_panel(m: dict) -> str:
    """A wave written by hand in status.json (critiques_by_wave): the owner's format, shown as is."""
    items = "".join(f'<tr><td>{esc(c.get("issue"))}</td><td>{sev_pill(str(c.get("severity", "")).lower())}</td><td class="n">{esc(c.get("seen_by", ""))}</td><td>{status_pill(str(c.get("status", "")).lower())}</td><td>{esc(c.get("gate", "") or "—")}</td><td>{esc(c.get("action", ""))}</td></tr>' for c in m.get("items", []))
    return (f'<p class="meta"><strong>{esc(m.get("wave", ""))}</strong>' + (f' · {esc(m["score"])}' if m.get("score") else "") + "</p>" + (f'<p class="sub">{esc(m["note"])}</p>' if m.get("note") else "")
            + (_table(["Criticità", "Gravità", "Visto da", "Stato", "Cancello", "Cosa si fa"], [items]) if items else "<p>Nessuna criticità registrata.</p>"))


def gate_panel(an: dict, waves: list, register: list, gate_states: dict, gate_names: dict) -> str:
    groups: dict = {}
    for h in an["issues"]:
        groups.setdefault(h["gate"], []).append(dict(label=h["label"], severity=h["severity"], born=wave_label(waves[h["first"]]), today=h["today"], pct=h["last_pct"], resolved_in=(wave_label(waves[h["resolved_in"]]) if h["resolved_in"] is not None and h["resolved_in"] < len(waves) else None),
                                                     source="ondata", area=h["area"]))
    for m in register:
        wi = wave_index_for(m["opened"], waves) if waves else None
        groups.setdefault(m["gate"], []).append(dict(label=m["label"], severity=m["severity"], born=(wave_label(waves[wi]) if wi is not None else _date(m["opened"]) or "n/d"), today=m["status"], pct=None,
                                                     resolved_in=_date(m["closed"]) if m["closed"] else None, source=SOURCES.get(m["source"], m["source"]), area=m["area"]))
    order = [g for g in ("0", "A", "B", "C") if g in groups] + (["" ] if "" in groups else [])
    if not order:
        return "<p>Nessuna criticità è ancora collegata a un cancello. Nel file dell'ondata, accanto a ogni criticità, scrivi <code>\"gate\": \"A\"</code> (o 0, B, C).</p>"
    out = []
    for g in order:
        stt = gate_states.get(g, {}).get("state") if g else None
        name = gate_names.get(g, f"Gate {g}") if g else "Non collegate a un cancello"
        badge = {"pass": pill("ok", "Superato"), "fail": pill("crit", "Non superato"), "pending": pill("mute", "Da fare")}.get(stt, "")
        rows = [f'<tr><td><strong>{esc(x["label"])}</strong>' + (f'<br><span class="note">{esc(x["area"])}</span>' if x["area"] else "") + f'</td><td>{sev_pill(x["severity"])}</td><td>{esc(x["born"])}</td><td>{status_pill(x["today"])}' + (f'<br><span class="note">risolta: {esc(x["resolved_in"])}</span>' if x["today"] == "risolta" and x["resolved_in"] else "")
                + f'</td><td class="n">{"" if x["pct"] is None else format(x["pct"], "g") + "%"}</td><td>{esc(x["source"])}</td></tr>' for x in sorted(groups[g], key=lambda x: (x["today"] == "risolta", -SEV.get(x["severity"], 2), x["label"]))]
        n_open = sum(1 for x in groups[g] if x["today"] != "risolta")
        out.append(f'<div class="gatehead"><strong>{esc(name)}</strong> {badge} <span class="note">{n_open} aperte su {len(groups[g])}</span></div>' + _table(["Criticità", "Gravità", "Nata in", "Oggi", "Ultima %", "Fonte"], rows))
    return "".join(out)


def evolution_panel(an: dict, waves: list) -> str:
    n = len(waves)
    labels = [wave_label(w) for w in waves]
    ser = [("persistenti", "Già presenti", "var(--s1)"), ("nuove", "Nuove o ricomparse", "var(--warn)"), ("risolte", "Risolte nell'ondata", "var(--good)")]
    svg, tbl = C.stacked([dict(label=labels[p["index"]], values=p["counts"]) for p in an["panels"]], ser, aria="Criticità per ondata", percent=False)
    charts = C.wrap(svg, title="Come cambiano le criticità", why="Per ogni ondata: quante c'erano già, quante sono nuove e quante si sono risolte. Più verde e meno giallo = meglio.", leg=C.legend([(l, c) for _, l, c in ser]), table=tbl)
    head = "".join(f"<th>{esc(l)}</th>" for l in labels)
    rows = []
    for h in an["issues"]:
        cells = ""
        for i in range(n):
            v = h["points"].get(i)
            cells += f'<td class="heat" style="background:color-mix(in srgb,var(--s1) {min(int(v), 100)}%,transparent)" title="{esc(labels[i])}: {v:g}% dei tester">{v:g}%</td>' if v is not None else '<td class="heat" style="color:var(--muted)" title="non segnalata">—</td>'
        rows.append(f'<tr><td><strong>{esc(h["label"])}</strong><br>{sev_pill(h["severity"])}' + (f' <span class="note">{esc(("Gate " + h["gate"]))}</span>' if h["gate"] else "") + f'</td>{cells}<td>{spark(h["points"], n, "andamento di " + h["label"])}</td><td>{status_pill(h["today"])}</td></tr>')
    table = f'<div class="wrap"><table><thead><tr><th>Criticità</th>{head}<th>Andamento</th><th>Oggi</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    return charts + "<h4>Criticità × ondata</h4><p class=\"meta\">Ogni cella è la quota di tester che ha segnalato quella criticità in quell'ondata; più scura = più persone. Il trattino vuol dire che non è stata segnalata.</p>" + table


def build(root: str, st: dict | None = None, gate_names: dict | None = None, bare: bool = False):
    """Returns (html of the card without the heading, data for the Q&A) or (None, None) when there is nothing to show."""
    st = st or {}
    gate_names = gate_names or {"0": "Gate 0 · Posizionamento", "A": "Gate A · Qualità percepita", "B": "Gate B · Test reale", "C": "Gate C · Capsule"}
    gate_states = st.get("gates") or {}
    waves, problems = load_waves(root)
    register = read_register(root)
    manual = [m for m in (st.get("critiques_by_wave") or []) if isinstance(m, dict)]
    manual_only = []
    derived_nums = {w["n"] for w in waves}
    for m in manual:
        num = re.search(r"\d+", str(m.get("wave", "")))
        if not (num and int(num.group(0)) in derived_nums):
            manual_only.append(m)
    if not waves and not register and not manual_only:
        return None, None
    an = analyse(waves) if waves else dict(panels=[], issues=[])
    by_wave: dict = {}
    loose = []
    for m in register:
        wi = wave_index_for(m["opened"], waves) if waves else None
        (by_wave.setdefault(wi, []) if wi is not None else loose).append(m)
    buttons, panels = [], []
    last_key = None
    for p in an["panels"]:
        key = f"w{p['index']}"
        last_key = key
        buttons.append((key, wave_label(p["wave"]), _date(p["wave"]["date"])))
        panels.append((key, wave_panel(p, by_wave.get(p["index"], []), gate_names)))
    for j, m in enumerate(manual_only):
        key = f"m{j}"
        buttons.insert(0, (key, str(m.get("wave", f"Ondata {j + 1}")), ""))
        panels.insert(0, (key, manual_wave_panel(m)))
        last_key = last_key or key
    if waves or register:
        buttons.append(("gates", "Per cancello", ""))
        panels.append(("gates", gate_panel(an, waves, register + [], gate_states, gate_names)))
    if len(waves) > 1:
        buttons.append(("evo", "Evoluzione", ""))
        panels.append(("evo", evolution_panel(an, waves)))
    default = last_key or buttons[0][0]
    btn = "".join(f'<button type="button" data-p="{k}" aria-pressed="{"true" if k == default else "false"}">{esc(lab)}' + (f' <span class="note">{esc(sub)}</span>' if sub else "") + "</button>" for k, lab, sub in buttons)
    pan = "".join(f'<div class="cp" data-p="{k}"{"" if k == default else " hidden"}>{body}</div>' for k, body in panels)
    warn = f'<p class="note">File di ondata non letti: {esc("; ".join(problems))}</p>' if problems else ""
    card = (f'<div class="{"" if bare else "card "}" data-crit>'
            '<p class="sub">Le criticità trovate dal focus group, ondata per ondata, e da altre fonti (test reale, recensioni, pre-mortem). Scegli un\'ondata per vedere solo le sue; '
            '<strong>Per cancello</strong> le raggruppa per Go/No-Go, <strong>Evoluzione</strong> mostra come cambiano. Si aggiorna a ogni nuova ondata.</p>'
            f'<div class="seg" role="group" aria-label="Scegli cosa vedere">{btn}</div>{pan}{warn}</div>')
    data = dict(waves=[p["wave"] for p in an["panels"]], panels=an["panels"], issues=an["issues"], register=register, manual=manual_only)
    return card, data


# ---------------------------------------------------------------- manual register CLI
def _write(path: str, rows: list[dict]):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _read_raw(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (r.get(k) or "") for k in FIELDS} for r in csv.DictReader(f)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="launch/criticita.csv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("--key", required=True); p.add_argument("--label"); p.add_argument("--severity", choices=list(SEV), default="media"); p.add_argument("--source", choices=list(SOURCES), default="altro")
    p.add_argument("--gate", default=""); p.add_argument("--area", default=""); p.add_argument("--opened", default=dt.date.today().isoformat()); p.add_argument("--note", default="")
    p = sub.add_parser("close"); p.add_argument("key"); p.add_argument("--date", default=dt.date.today().isoformat())
    sub.add_parser("list")
    a = ap.parse_args()
    rows = _read_raw(a.csv)
    if a.cmd == "add":
        new = dict(key=a.key, label=a.label or a.key, severity=a.severity, source=a.source, gate=a.gate.upper(), area=a.area, opened=a.opened, status="aperta", closed="", note=a.note)
        rows = [r for r in rows if r["key"] != a.key] + [new]
        _write(a.csv, rows)
        print(f"recorded {a.key} ({a.severity}, {a.source}) in {a.csv}")
    elif a.cmd == "close":
        hit = [r for r in rows if r["key"] == a.key]
        if not hit:
            raise SystemExit(f"{a.key} not found in {a.csv}")
        hit[0].update(status="risolta", closed=a.date)
        _write(a.csv, rows)
        print(f"closed {a.key} on {a.date}")
    else:
        print("\n".join(f"{r['key']:28} {r['severity']:6} {r['source']:10} gate {r['gate'] or '-':2} {r['status']:9} {r['opened']}  {r['label']}" for r in rows) or "no criticalities recorded")


if __name__ == "__main__":
    main()
