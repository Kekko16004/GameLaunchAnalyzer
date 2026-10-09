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
  4. launch/issue_status.json: the OWNER'S DECISION on each issue key, kept up to date by Claude after every decision and every wave:
       {"run-variety": {"status": "pianificato", "note": "3-4 mappe nel gioco completo", "aliases": ["run ripetitive"]}, ...}
     status: aperto | in_lavorazione | da_verificare (= still to do now)  ·  risolto | pianificato | accettato | non_problema (= already decided).
     Every place that lists issues shows it as a badge with the note and splits "Da fare adesso" from "Già deciso" (collapsed).
     Optional "aliases" (regex, case-insensitive) let other texts (convergence matrix, verdict risks) point to the key; status.json
     -> issue_aliases {key: [regex]} does the same without touching the owner's file.

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
# owner's decision (issue_status.json): (pill kind, label, still to do now?, icon)
OWNER = {"aperto": ("warn", "Aperto", True, "warn"), "in_lavorazione": ("new", "In lavorazione", True, "work"), "da_verificare": ("warn", "Da verificare", True, "ask"),
         "risolto": ("ok", "Risolto", False, "ok"), "pianificato": ("mute", "Pianificato", False, "plan"), "accettato": ("mute", "Accettato così", False, "dash"),
         "non_problema": ("mute", "Non è un problema", False, "dash")}
UNDECIDED = ("warn", "Da decidere", True, "ask")
_ICON = {"ok": '<path d="M3.5 8.2l2.6 2.6L12.5 5" stroke="var(--good)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
         "warn": '<path d="M8 2L14.5 13.5H1.5z" fill="none" stroke="var(--warn)" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 6.5v3.2M8 11.6v.2" stroke="var(--ink)" stroke-width="1.6" stroke-linecap="round"/>',
         "work": '<circle cx="8" cy="8" r="5.6" fill="none" stroke="var(--s1)" stroke-width="1.6"/><path d="M8 4.8V8l2.2 1.4" stroke="var(--s1)" stroke-width="1.6" fill="none" stroke-linecap="round"/>',
         "ask": '<circle cx="8" cy="8" r="5.6" fill="none" stroke="var(--warn)" stroke-width="1.6"/><path d="M6.4 6.4a1.7 1.7 0 113 1c-.6.5-1.4.8-1.4 1.7M8 11.4v.2" stroke="var(--ink)" stroke-width="1.5" fill="none" stroke-linecap="round"/>',
         "plan": '<rect x="2.5" y="3.5" width="11" height="10" rx="1.5" fill="none" stroke="var(--ink2)" stroke-width="1.5"/><path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" stroke="var(--ink2)" stroke-width="1.5"/>',
         "dash": '<circle cx="8" cy="8" r="5.6" fill="none" stroke="var(--muted)" stroke-width="1.6"/><path d="M5.2 8h5.6" stroke="var(--muted)" stroke-width="1.6" stroke-linecap="round"/>'}

CSS = """
.seg{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px}.seg button{background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:6px 12px;cursor:pointer;font:inherit;font-size:.85rem}
.seg button[aria-pressed="true"]{border-color:var(--s1);box-shadow:inset 0 0 0 1px var(--s1);font-weight:600}.cp[hidden]{display:none}
.pill{display:inline-block;border:1px solid var(--ring);border-radius:999px;padding:1px 9px;font-size:.78rem;font-weight:600;white-space:nowrap;background:var(--surface);color:var(--ink)}
.pill.crit{border-color:var(--crit)}.pill.warn{border-color:var(--warn)}.pill.ok{border-color:var(--good)}.pill.new{border-color:var(--s1)}.pill.mute{color:var(--ink2)}
.cp h4{margin:16px 0 6px;font-size:.95rem}.cp .meta{color:var(--ink2);font-size:.9rem;margin:0 0 8px}td.heat{text-align:center;font-variant-numeric:tabular-nums;min-width:64px}
.cp .chart svg{max-width:640px}.gatehead{display:flex;gap:10px;align-items:center;margin:14px 0 4px}.gatehead strong{font-size:1rem}svg.spark{vertical-align:middle}
.own{display:inline-flex;align-items:center;gap:4px}.own svg{flex:none}.onote{display:block;color:var(--ink2);font-size:.82rem;margin-top:2px;max-width:34ch}
details.decided{margin-top:10px}details.decided>summary{font-weight:600;color:var(--ink2)}td.nw,th.nw{white-space:nowrap}
.ctab td:first-child{min-width:14em}.ctab td.todo{min-width:16em}.ctab td.dec{min-width:11em}
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


def _pc(v) -> str:
    """A share of testers in Italian style: 5,6%."""
    return "" if v is None else f"{v:g}".replace(".", ",") + "%"


def load_owner(root: str) -> dict:
    """launch/issue_status.json -> {key: {status, note, aliases}}; keys starting with "_" are comments. Unknown statuses count as "aperto"."""
    p = os.path.join(root, "issue_status.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in (raw or {}).items():
        if str(k).startswith("_"):
            continue
        if isinstance(v, str):
            v = {"status": v}
        if not isinstance(v, dict):
            continue
        stt = str(v.get("status") or "aperto").strip().lower().replace(" ", "_").replace("-", "_")
        out[str(k)] = dict(status=stt if stt in OWNER else "aperto", note=str(v.get("note") or ""), aliases=[str(a) for a in (v.get("aliases") or []) if a])
    return out


def aliases(owner: dict, st: dict | None = None) -> list[tuple[str, "re.Pattern"]]:
    """[(key, compiled regex)] from issue_status.json aliases and status.json -> issue_aliases."""
    out = []
    pairs = [(k, a) for k, v in owner.items() for a in v.get("aliases", [])]
    for k, lst in ((st or {}).get("issue_aliases") or {}).items():
        pairs += [(k, a) for a in (lst if isinstance(lst, list) else [lst])]
    for k, a in pairs:
        try:
            out.append((k, re.compile(a, re.I)))
        except re.error:
            pass
    return out


def owner_info(key: str, owner: dict) -> tuple:
    """(pill kind, label, to do now?, icon, note) of the owner's decision on an issue; undecided issues are "to do now"."""
    o = owner.get(key)
    if not o:
        return UNDECIDED + ("",)
    return OWNER[o["status"]] + (o.get("note", ""),)


def is_now(key: str, owner: dict) -> bool:
    return owner_info(key, owner)[2]


def owner_badge(key: str, owner: dict, with_note: bool = True, prefix: str = "", tip: str | None = None) -> str:
    """The owner's decision as a pill (icon + word); the note below it (with_note) or in the tooltip; `tip` replaces the tooltip."""
    kind, text, _, icon, note = owner_info(key, owner)
    svg = f'<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">{_ICON[icon]}</svg>'
    tip = f' title="{esc(tip)}"' if tip else f' title="{esc(note)}"' if note and not with_note else ""
    return (f'<span class="pill {kind} own"{tip}>{svg}<span>{esc(prefix)}{esc(text)}</span></span>'
            + (f'<span class="onote">{esc(note)}</span>' if note and with_note else ""))


def owner_text(key: str, owner: dict) -> str:
    """Plain text of the decision, for tooltips: "Pianificato: nota"."""
    kind, text, _, icon, note = owner_info(key, owner)
    return text + (f": {note}" if note else "")


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


def _group(w: dict) -> str:
    """Waves of the same kind are compared with each other: beta with beta (and unlabelled waves), full game with full game."""
    return "full" if w.get("stage") == "full" else "beta"


def analyse(waves: list, owner: dict | None = None) -> dict:
    """Per wave: rows with status against the previous wave OF THE SAME KIND (beta / full game), resolved issues with their fix;
    per issue: history, state today and the owner's decision (issue_status.json)."""
    owner = owner or {}
    seen: dict = {"beta": set(), "full": set()}
    last_of: dict = {}
    hist: dict = {}
    panels = []
    for i, w in enumerate(waves):
        g = _group(w)
        cur = {x["key"]: x for x in w["issues"]}
        pi = last_of.get(g)
        prev = {x["key"]: x for x in waves[pi]["issues"]} if pi is not None else {}
        rows = []
        for k, x in cur.items():
            if pi is None:
                st, delta = "presente", None
            elif k not in prev:
                st, delta = ("ricomparsa" if k in seen[g] else "nuova"), None
            else:
                delta = round(x["pct"] - prev[k]["pct"], 1)
                st = "in aumento" if delta >= NOISE else "in calo" if delta <= -NOISE else "persistente"
            rows.append(dict(x, status=st, delta=delta, now=is_now(k, owner)))
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
        seen[g] |= set(cur)
        last_of[g] = i
        panels.append(dict(index=i, wave=w, rows=rows, resolved=resolved, fixes=w["fixes"], prev_index=pi,
                           counts=dict(persistenti=sum(1 for r in rows if r["status"] in ("persistente", "in aumento", "in calo", "presente")), nuove=sum(1 for r in rows if r["status"] in ("nuova", "ricomparsa")), risolte=len(resolved))))
    latest = set(last_of.values())
    issues = []
    for h in hist.values():
        is_open = any(i in h["points"] for i in latest)
        lastp = max(h["points"]) if h["points"] else 0
        nxt = next((j for j in range(lastp + 1, len(waves)) if _group(waves[j]) == _group(waves[lastp])), None)
        issues.append(dict(h, open=is_open, today="aperta" if is_open else "risolta", last_pct=h["points"].get(lastp), resolved_in=None if is_open else nxt,
                           now=is_open and is_now(h["key"], owner), owner=owner.get(h["key"])))
    issues.sort(key=lambda x: (not x["open"], not x["now"], -SEV.get(x["severity"], 2), -(x["last_pct"] or 0), x["key"]))
    return dict(panels=panels, issues=issues, latest=dict((_group(waves[i]), i) for i in latest))


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
    return "" if d is None else (f"+{d:g} punti" if d > 0 else f"{d:g} punti" if d < 0 else "invariato").replace(".", ",")


def _table(head: list, rows: list, num: tuple = ()) -> str:
    h = "".join((f'<th class="n nw">{esc(x)}</th>' if k in num else f"<th>{esc(x)}</th>") for k, x in enumerate(head))
    return f'<div class="wrap"><table class="ctab"><thead><tr>{h}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def split_now(items: list, key=lambda x: x["key"], owner: dict | None = None) -> tuple[list, list]:
    """(to do now, already decided) according to the owner's decisions."""
    owner = owner or {}
    now = [x for x in items if is_now(key(x), owner)]
    return now, [x for x in items if not is_now(key(x), owner)]


def _two_parts(now_html: str, n_now: int, decided_html: str, n_dec: int, what: str = "criticità") -> str:
    out = f"<h4>Da fare adesso ({n_now})</h4>" + (now_html if n_now else f'<p class="note">Nessuna {esc(what)} da affrontare adesso: le altre sono già decise.</p>')
    if n_dec:
        out += f'<details class="decided"><summary>Già deciso ({n_dec}): risolte, pianificate, accettate o non considerate un problema</summary>{decided_html}</details>'
    return out


def wave_panel(p: dict, manual: list, gate_names: dict, owner: dict | None = None) -> str:
    owner = owner or {}
    w = p["wave"]
    prev = w["_all"][p["prev_index"]] if p.get("prev_index") is not None else None
    head = (f'<p class="meta"><strong>{esc(wave_label(w))}</strong> · {esc(_date(w["date"]))}' + (f' · versione {esc(w["build"])}' if w.get("build") else "")
            + f' · punteggio <strong>{esc(str(w["score"]).replace(".", ","))}</strong> (soglia {esc(str(w["gate_threshold"]).replace(".", ","))}) · {w["n_testers"]} tester · {len(p["rows"])} criticità'
            + (f" · confronto con l'{esc(wave_label(prev))}" if prev else "") + "</p>")
    out = [head]
    if p["fixes"]:
        out.append("<h4>Cosa è stato corretto prima di questa ondata</h4><ul>" + "".join(f'<li>{esc(f.get("what"))}' + (f' <span class="note">(criticità: {esc(f.get("issue"))})</span>' if f.get("issue") else "") + "</li>" for f in p["fixes"]) + "</ul>")
    if p["rows"]:
        has_gate = any(r["gate"] for r in p["rows"])

        def row(r):
            g = gate_names.get(r["gate"], f"Gate {r['gate']}") if r["gate"] else "—"
            return (f'<tr><td><strong>{esc(r["label"])}</strong>' + (f'<br><span class="note">{esc(r["area"])}</span>' if r["area"] else "") + f'</td><td class="nw">{sev_pill(r["severity"])}</td>'
                    f'<td class="n nw">{_pc(r["pct"])}<br><span class="note">{r["freq"]} su {w["n_testers"]}</span></td>'
                    f'<td class="nw">{status_pill(r["status"])}' + (f'<br><span class="note">{esc(_delta(r["delta"]))}</span>' if r["delta"] is not None else "") + "</td>"
                    f'<td class="dec">{owner_badge(r["key"], owner)}</td>' + (f'<td class="nw">{esc(g)}</td>' if has_gate else "") + f'<td class="todo">{esc(r.get("recommendation") or "")}</td></tr>')
        cols = ["Criticità", "Gravità", "Tester", "Rispetto a prima", "Decisione"] + (["Cancello"] if has_gate else []) + ["Cosa fare"]
        now, dec = split_now(p["rows"], owner=owner)
        out.append(_two_parts(_table(cols, [row(r) for r in now], (2,)), len(now), _table(cols, [row(r) for r in dec], (2,)), len(dec)))
    else:
        out.append("<p>Nessuna criticità segnalata dai tester in questa ondata.</p>")
    if p["resolved"]:
        out.append("<h4>Sparite in questa ondata (c'erano nella precedente dello stesso tipo)</h4><ul>" + "".join(f'<li>{pill("ok", "Sparita")} <strong>{esc(r["label"])}</strong> (era al {_pc(r["pct"])})' + (f' · correzione: {esc(r["fix"])}' if r.get("fix") else "") + f' · {owner_badge(r["key"], owner, with_note=False)}</li>' for r in p["resolved"]) + "</ul>")
    if manual:
        out.append("<h4>Da altre fonti in questo periodo</h4>" + _table(["Criticità", "Fonte", "Gravità", "Stato", "Decisione", "Cancello", "Nota"], [
            f'<tr><td><strong>{esc(m["label"])}</strong></td><td>{esc(SOURCES.get(m["source"], m["source"]))}</td><td class="nw">{sev_pill(m["severity"])}</td><td class="nw">{status_pill(m["status"])}</td><td class="dec">{owner_badge(m["key"], owner) if m["key"] in owner else ""}</td><td>{esc(gate_names.get(m["gate"], "") if m["gate"] else "—")}</td><td>{esc(m["note"])}</td></tr>' for m in manual]))
    return "".join(out)


def manual_wave_panel(m: dict) -> str:
    """A wave written by hand in status.json (critiques_by_wave): the owner's format, shown as is."""
    items = "".join(f'<tr><td>{esc(c.get("issue"))}</td><td>{sev_pill(str(c.get("severity", "")).lower())}</td><td class="n">{esc(c.get("seen_by", ""))}</td><td>{status_pill(str(c.get("status", "")).lower())}</td><td>{esc(c.get("gate", "") or "—")}</td><td>{esc(c.get("action", ""))}</td></tr>' for c in m.get("items", []))
    return (f'<p class="meta"><strong>{esc(m.get("wave", ""))}</strong>' + (f' · {esc(m["score"])}' if m.get("score") else "") + "</p>" + (f'<p class="sub">{esc(m["note"])}</p>' if m.get("note") else "")
            + (_table(["Criticità", "Gravità", "Visto da", "Stato", "Cancello", "Cosa si fa"], [items]) if items else "<p>Nessuna criticità registrata.</p>"))


def gate_panel(an: dict, waves: list, register: list, gate_states: dict, gate_names: dict, owner: dict | None = None) -> str:
    owner = owner or {}
    groups: dict = {}
    for h in an["issues"]:
        groups.setdefault(h["gate"], []).append(dict(key=h["key"], label=h["label"], severity=h["severity"], born=wave_label(waves[h["first"]]), today=h["today"], pct=h["last_pct"],
                                                     resolved_in=(wave_label(waves[h["resolved_in"]]) if h["resolved_in"] is not None and h["resolved_in"] < len(waves) else None), source="ondata", area=h["area"]))
    for m in register:
        wi = wave_index_for(m["opened"], waves) if waves else None
        groups.setdefault(m["gate"], []).append(dict(key=m["key"], label=m["label"], severity=m["severity"], born=(wave_label(waves[wi]) if wi is not None else _date(m["opened"]) or "n/d"), today=m["status"], pct=None,
                                                     resolved_in=_date(m["closed"]) if m["closed"] else None, source=SOURCES.get(m["source"], m["source"]), area=m["area"]))
    order = [g for g in ("0", "A", "B", "C") if g in groups] + ([""] if "" in groups else [])
    if not order:
        return "<p>Nessuna criticità è ancora collegata a un cancello. Nel file dell'ondata, accanto a ogni criticità, scrivi <code>\"gate\": \"A\"</code> (o 0, B, C).</p>"
    out = []
    if order == [""]:
        out.append('<p class="note">Nessuna criticità è collegata a un cancello (manca <code>"gate"</code> nei file delle ondate): qui sono tutte insieme.</p>')

    def row(x):
        return (f'<tr><td><strong>{esc(x["label"])}</strong>' + (f'<br><span class="note">{esc(x["area"])}</span>' if x["area"] else "") + f'</td><td class="nw">{sev_pill(x["severity"])}</td><td class="nw">{esc(x["born"])}</td><td class="nw">{status_pill(x["today"])}'
                + (f'<br><span class="note">sparita: {esc(x["resolved_in"])}</span>' if x["today"] == "risolta" and x["resolved_in"] else "")
                + f'</td><td class="n nw">{_pc(x["pct"])}</td><td class="dec">{owner_badge(x["key"], owner)}</td><td>{esc(x["source"])}</td></tr>')
    head = ["Criticità", "Gravità", "Nata in", "Nei tester oggi", "Ultima %", "Decisione", "Fonte"]
    for g in order:
        stt = gate_states.get(g, {}).get("state") if g else None
        name = gate_names.get(g, f"Gate {g}") if g else "Non collegate a un cancello"
        badge = {"pass": pill("ok", "Superato"), "fail": pill("crit", "Non superato"), "pending": pill("mute", "Da fare")}.get(stt, "")
        items = sorted(groups[g], key=lambda x: (x["today"] == "risolta", -SEV.get(x["severity"], 2), x["label"]))
        now = [x for x in items if x["today"] != "risolta" and is_now(x["key"], owner)]
        dec = [x for x in items if x not in now]
        out.append(f'<div class="gatehead"><strong>{esc(name)}</strong> {badge} <span class="note">{len(now)} da fare adesso su {len(items)}</span></div>'
                   + _two_parts(_table(head, [row(x) for x in now], (4,)), len(now), _table(head, [row(x) for x in dec], (4,)), len(dec)))
    return "".join(out)


def evolution_panel(an: dict, waves: list, owner: dict | None = None) -> str:
    owner = owner or {}
    n = len(waves)
    labels = [wave_label(w) for w in waves]
    ser = [("persistenti", "Già presenti", "var(--s1)"), ("nuove", "Nuove o ricomparse", "var(--warn)"), ("risolte", "Sparite nell'ondata", "var(--good)")]
    svg, tbl = C.stacked([dict(label=labels[p["index"]], values=p["counts"]) for p in an["panels"]], ser, aria="Criticità per ondata", percent=False)
    charts = C.wrap(svg, title="Come cambiano le criticità", why="Per ogni ondata: quante c'erano già nell'ondata precedente dello stesso tipo (beta con beta, gioco completo con gioco completo), quante sono nuove e quante sono sparite. Più verde e meno giallo = meglio.", leg=C.legend([(l, c) for _, l, c in ser]), table=tbl)
    head = "".join(f'<th class="nw">Ondata {w["n"]}' + (f'<br><span class="note">{esc(STAGE_LABEL.get(w["stage"], w["stage"]))}</span>' if w.get("stage") else "") + "</th>" for w in waves)

    def row(h):
        cells = ""
        for i in range(n):
            v = h["points"].get(i)
            cells += f'<td class="heat" style="background:color-mix(in srgb,var(--s1) {min(int(v), 100)}%,transparent)" title="{esc(labels[i])}: {_pc(v)} dei tester">{_pc(v)}</td>' if v is not None else '<td class="heat" style="color:var(--muted)" title="non segnalata">—</td>'
        return (f'<tr><td><strong>{esc(h["label"])}</strong><br>{sev_pill(h["severity"])}' + (f' <span class="note">{esc(("Gate " + h["gate"]))}</span>' if h["gate"] else "")
                + f'</td>{cells}<td>{spark(h["points"], n, "andamento di " + h["label"])}</td><td class="nw">{status_pill(h["today"])}</td><td class="dec">{owner_badge(h["key"], owner)}</td></tr>')
    th = f'<thead><tr><th>Criticità</th>{head}<th>Andamento</th><th>Nei tester oggi</th><th>Decisione</th></tr></thead>'
    now = [h for h in an["issues"] if h["now"]]
    dec = [h for h in an["issues"] if not h["now"]]
    t = lambda rows: f'<div class="wrap"><table class="ctab">{th}<tbody>{"".join(row(h) for h in rows)}</tbody></table></div>'
    return (charts + "<h4>Criticità × ondata</h4><p class=\"meta\">Ogni cella è la quota di tester che ha segnalato quella criticità in quell'ondata; più scura = più persone. Il trattino vuol dire che non è stata segnalata. "
            "«Da fare adesso» sono quelle ancora segnalate e senza una decisione chiusa.</p>" + _two_parts(t(now), len(now), t(dec), len(dec)))


def build(root: str, st: dict | None = None, gate_names: dict | None = None, bare: bool = False):
    """Returns (html of the card without the heading, data for the Q&A) or (None, None) when there is nothing to show."""
    st = st or {}
    gate_names = gate_names or {"0": "Gate 0 · Posizionamento", "A": "Gate A · Qualità percepita", "B": "Gate B · Test reale", "C": "Gate C · Capsule"}
    gate_states = st.get("gates") or {}
    owner = load_owner(root)
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
    an = analyse(waves, owner) if waves else dict(panels=[], issues=[], latest={})
    by_wave: dict = {}
    loose = []
    for m in register:
        wi = wave_index_for(m["opened"], waves) if waves else None
        (by_wave.setdefault(wi, []) if wi is not None else loose).append(m)
    buttons, panels = [], []
    last_key = None
    for p in an["panels"]:
        key = f"w{p['index']}"
        if _group(p["wave"]) == "beta" or last_key is None or not any(_group(x["wave"]) == "beta" for x in an["panels"]):
            last_key = key   # the panel open by default: the latest beta wave (what the owner is shipping), else the latest wave
        buttons.append((key, wave_label(p["wave"]), _date(p["wave"]["date"])))
        panels.append((key, wave_panel(p, by_wave.get(p["index"], []), gate_names, owner)))
    for j, m in enumerate(manual_only):
        key = f"m{j}"
        buttons.insert(0, (key, str(m.get("wave", f"Ondata {j + 1}")), ""))
        panels.insert(0, (key, manual_wave_panel(m)))
        last_key = last_key or key
    if waves or register:
        buttons.append(("gates", "Per cancello", ""))
        panels.append(("gates", gate_panel(an, waves, register + [], gate_states, gate_names, owner)))
    if len(waves) > 1:
        buttons.append(("evo", "Evoluzione", ""))
        panels.append(("evo", evolution_panel(an, waves, owner)))
    default = last_key or buttons[0][0]
    btn = "".join(f'<button type="button" data-p="{k}" aria-pressed="{"true" if k == default else "false"}">{esc(lab)}' + (f' <span class="note">{esc(sub)}</span>' if sub else "") + "</button>" for k, lab, sub in buttons)
    pan = "".join(f'<div class="cp" data-p="{k}"{"" if k == default else " hidden"}>{body}</div>' for k, body in panels)
    warn = f'<p class="note">File di ondata non letti: {esc("; ".join(problems))}</p>' if problems else ""
    card = (f'<div class="{"" if bare else "card "}" data-crit>'
            '<p class="sub">Le criticità trovate dal focus group, ondata per ondata, e da altre fonti (test reale, recensioni, pre-mortem). Scegli un\'ondata per vedere solo le sue; '
            '<strong>Per cancello</strong> le raggruppa per Go/No-Go, <strong>Evoluzione</strong> mostra come cambiano. Si aggiorna a ogni nuova ondata e a ogni tua decisione (<code>issue_status.json</code>): '
            'in alto ciò che è <strong>da fare adesso</strong>, chiuso sotto ciò che è <strong>già deciso</strong>. Le ondate beta si confrontano con le beta, quelle del gioco completo con quelle del gioco completo.</p>'
            f'<div class="seg" role="group" aria-label="Scegli cosa vedere">{btn}</div>{pan}{warn}</div>')
    data = dict(waves=[p["wave"] for p in an["panels"]], panels=an["panels"], issues=an["issues"], register=register, manual=manual_only, owner=owner, latest=an.get("latest", {}))
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
