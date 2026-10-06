#!/usr/bin/env python3
"""One self-contained HTML status page for partners or a publisher: verdict, key numbers, wishlist vs scenarios,
focus-group timeline, Go/No-Go gates, calendar, open TODOs, and the main documents (collapsible).

It only READS files already produced in `launch/` and writes `launch/STATUS.html` (no network, no external scripts,
no tracking: everything is inline, so the file can be attached to an email as is):
  launch/status.json         verdict, gates, key numbers (written by the skill, see references/06-synthesis-output.md)
  launch/fg/timeline.csv     focus-group waves (fg_waves.py timeline --csv)
  launch/wishlists.csv + launch/_raw/wl_plan.json   wishlist tracker (wl_track.py)
  launch/_raw/econ.json      economic plan (calc_econ.py)
  launch/calendar.md, launch/TODO.md, launch/REPORT.md and the other documents
Anything missing is simply left out.

Sharing: the page contains strategy. --audience picks what goes in (default partner):
  private    everything, including pre-mortem, creators, community, legal/fiscal
  partner    verdict, numbers, charts, gates, calendar, economics, positioning, platform, pricing, focus group, pre-mortem
  publisher  verdict, positioning, platform, focus group, charts, calendar (no economics, no pricing, no pre-mortem)
Add/remove with --include / --exclude (file stems such as 03-pricing) and --hide economics,todo,calendar.
Publishing the page anywhere is YOUR decision: this tool only writes the local file.

  python status_page.py [--launch-dir launch] [--audience partner] [-o launch/STATUS.html]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import os
import re
from common import load_json, log
import wl_track as wl

MONTHS = "gen feb mar apr mag giu lug ago set ott nov dic".split()
DOCS = {  # stem -> title
    "REPORT": "Report completo", "00-brief": "Brief del progetto", "01b-positioning": "Posizionamento", "01-dev": "Audit del prodotto",
    "02-platform": "Piattaforme, demo e gate", "03-pricing": "Prezzo ed economia", "05-focusgroup": "Focus group", "05c-premortem": "Pre-mortem",
    "06-creators": "Creator", "07-community": "Community e test reale", "08-brand-legal": "Brand, legale e fiscale"}
AUDIENCES = {
    "private": list(DOCS),
    "partner": ["REPORT", "01b-positioning", "02-platform", "03-pricing", "05-focusgroup", "05c-premortem"],
    "publisher": ["01b-positioning", "02-platform", "05-focusgroup"]}
HIDE_BY_AUDIENCE = {"private": set(), "partner": set(), "publisher": {"economics", "todo"}}

CSS = """
:root{color-scheme:light;--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
--s1:#2a78d6;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--goodtext:#006300}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--goodtext:#0ca30c}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--goodtext:#0ca30c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px;overflow-wrap:anywhere}.card{min-width:0}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:36px 0 12px}h3{font-size:1rem;margin:20px 0 8px}
.sub{color:var(--ink2);margin:0 0 4px}.note{color:var(--muted);font-size:.85rem}.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
button.theme{background:var(--surface);color:var(--ink2);border:1px solid var(--ring);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit;font-size:.85rem}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px}.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr))}
.verdict{display:flex;gap:16px;align-items:flex-start}.verdict>div:first-child svg{width:40px;height:40px}.verdict>div:last-child{min-width:0}.verdict .big{font-size:1.25rem;font-weight:600}.tile .v{font-size:1.9rem;font-weight:600;line-height:1.1}.tile .l{color:var(--ink2);font-size:.85rem}.tile .d{color:var(--ink2);font-size:.85rem;margin-top:4px}
.state{display:inline-flex;align-items:center;gap:6px;font-weight:600}.state svg{flex:none}ul.clean{list-style:none;margin:0;padding:0}ul.clean li{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-top:1px solid var(--grid)}ul.clean li:first-child{border-top:0}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}th{color:var(--ink2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}tr.past td{color:var(--muted)}details{margin-top:8px}summary{cursor:pointer;color:var(--ink2)}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}.tip{position:absolute;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:8px 10px;font-size:.85rem;white-space:pre-line;box-shadow:0 2px 10px rgba(0,0,0,.15);display:none;max-width:260px;z-index:2}
.doc{margin-top:12px}.doc h3{font-size:1rem}.doc h4,.doc h5{font-size:.95rem;margin:14px 0 6px}.doc code{background:var(--grid);padding:1px 4px;border-radius:4px;font-size:.85em}.doc pre{background:var(--grid);padding:10px;border-radius:8px;overflow-x:auto}.doc blockquote{margin:8px 0;padding-left:12px;border-left:3px solid var(--axis);color:var(--ink2)}
a{color:var(--s1)}footer{margin-top:40px}.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink2);font-size:.85rem;margin:6px 0}.legend i{display:inline-block;width:18px;height:0;border-top:2px solid;vertical-align:middle;margin-right:6px}
"""
JS = """
(function(){var b=document.getElementById('theme');if(b){b.addEventListener('click',function(){var r=document.documentElement,d=r.getAttribute('data-theme')==='dark'||(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);r.setAttribute('data-theme',d?'light':'dark');});}
document.querySelectorAll('.chart').forEach(function(c){var tip=c.querySelector('.tip'),cross=c.querySelector('.cross');
c.querySelectorAll('.hit').forEach(function(h){function show(){var x=h.getAttribute('data-x');if(cross){cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.style.display='block';}
tip.textContent=h.getAttribute('data-tip');tip.style.display='block';var svg=c.querySelector('svg'),k=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width;tip.style.left=Math.min(x*k+12,c.clientWidth-270)+'px';tip.style.top='8px';}
function hide(){tip.style.display='none';if(cross)cross.style.display='none';}
h.addEventListener('pointerenter',show);h.addEventListener('focus',show);h.addEventListener('pointerleave',hide);h.addEventListener('blur',hide);});});})();
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def fmt_n(n) -> str:
    return "n/d" if n is None else f"{int(round(n)):,}".replace(",", ".")


def fmt_date(s) -> str:
    try:
        d = dt.date.fromisoformat(str(s)[:10])
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    except ValueError:
        return esc(s)


ICONS = {  # always paired with a text label: colour never carries the meaning alone
    "pass": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="8" fill="var(--good)"/><path d="M5 9.5l2.6 2.6L13 6.5" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>', "Superato"),
    "fail": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="8" fill="var(--crit)"/><path d="M6 6l6 6M12 6l-6 6" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/></svg>', "Non superato"),
    "pending": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7.2" fill="none" stroke="var(--muted)" stroke-width="2"/><path d="M9 5v4.5l3 1.5" stroke="var(--muted)" stroke-width="2" fill="none" stroke-linecap="round"/></svg>', "Da fare"),
    "warn": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M9 1.5L17 16H1z" fill="var(--warn)"/><path d="M9 6.5v4.5M9 13v.8" stroke="#0b0b0b" stroke-width="2" stroke-linecap="round"/></svg>', "Attenzione"),
    "info": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="8" fill="none" stroke="var(--muted)" stroke-width="2"/><path d="M9 8v5M9 5.2v.8" stroke="var(--muted)" stroke-width="2" stroke-linecap="round"/></svg>', "Info"),
    "na": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7.2" fill="none" stroke="var(--muted)" stroke-width="2"/><path d="M5 9h8" stroke="var(--muted)" stroke-width="2" stroke-linecap="round"/></svg>', "Non applicabile")}
LIGHT = {"verde": ("pass", "Verde"), "giallo": ("warn", "Giallo"), "rosso": ("fail", "Rosso")}


def state(kind: str, label: str | None = None) -> str:
    svg, default = ICONS.get(kind, ICONS["info"])
    return f'<span class="state">{svg}<span>{esc(label or default)}</span></span>'


# ----------------------------------------------------------------------------- markdown
def inline(t: str) -> str:
    t = esc(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?!\w)", r"<em>\1</em>", t)

    def link(m):
        url = html.unescape(m.group(2)).strip()
        return f'<a href="{esc(url)}" rel="noopener noreferrer">{m.group(1)}</a>' if re.match(r"(https?://|#|[\w./-]+$)", url) and not url.lower().startswith("javascript") else m.group(1)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)


def md_to_html(md: str) -> str:
    out, lines, i = [], md.replace("\r", "").split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            out.append(f"<pre>{esc(chr(10).join(lines[i + 1:j]))}</pre>")
            i = j + 1
            continue
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            head, j, rows = cells(ln), i + 2, []
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(cells(lines[j]))
                j += 1
            out.append('<div class="wrap"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>")
            i = j
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", ln)
        if m:
            lvl = min(len(m.group(1)) + 2, 5)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
        elif re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            tag, items = ("ol" if re.match(r"^\s*\d+\.", ln) else "ul"), []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        elif ln.startswith(">"):
            out.append(f"<blockquote>{inline(ln.lstrip('> '))}</blockquote>")
        elif ln.strip() and not re.match(r"^-{3,}$", ln.strip()):
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out)


# ----------------------------------------------------------------------------- charts
def nice_axis(lo: float, hi: float, max_intervals: int = 5) -> tuple[float, float, float]:
    """(min, max, step): round tick values (step = 1, 2, 2.5 or 5 x a power of ten), at most `max_intervals` intervals."""
    span = max(hi - lo, 1e-9)
    mag = 10 ** math.floor(math.log10(span / max_intervals))
    for k in (1, 2, 2.5, 5, 10, 20, 25, 50):
        step = k * mag
        lo2 = math.floor(lo / step) * step
        n = max(math.ceil(round((hi - lo2) / step, 9)), 1)
        if n <= max_intervals:
            return lo2, lo2 + n * step, step
    return lo, hi, span


def line_chart(title: str, points: list[tuple[float, float, str]], *, xlabels: list[tuple[float, str]], ymin: float, ymax: float, ystep: float,
               refs: list[tuple[str, list[tuple[float, float]], bool]] = (), markers: list[tuple[float, float, str, str]] = (), xmax_pad: float = 0.0) -> str:
    """points: (x, y, tooltip); refs: (label, [(x, y)...], is_line); markers: (x, y, tooltip, status class)."""
    W, H, L, R, T, B = 720, 300, 54, 120, 16, 34
    xs = [p[0] for p in points] + [x for _, pts, _ in refs for x, _ in pts] + [m[0] for m in markers]
    x0, x1 = min(xs), max(xs) + xmax_pad
    x1 = x1 if x1 > x0 else x0 + 1
    sx = lambda x: L + (x - x0) / (x1 - x0) * (W - L - R)
    sy = lambda y: T + (1 - (y - ymin) / (ymax - ymin)) * (H - T - B)
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">']
    for k in range(int(round((ymax - ymin) / ystep)) + 1):
        v = ymin + ystep * k
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="var(--grid)" stroke-width="1"/>'
                 f'<text x="{L - 8}" y="{sy(v) + 4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)" style="font-variant-numeric:tabular-nums">{fmt_n(v)}</text>')
    g.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(ymin):.1f}" y2="{sy(ymin):.1f}" stroke="var(--axis)" stroke-width="1"/>')
    for x, label in xlabels:
        g.append(f'<text x="{sx(x):.1f}" y="{H - 10}" text-anchor="middle" font-size="11" fill="var(--muted)">{esc(label)}</text>')
    for label, pts, _ in refs:
        d = " ".join(f"{'M' if k == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for k, (x, y) in enumerate(pts))
        g.append(f'<path d="{d}" fill="none" stroke="var(--muted)" stroke-width="1.5"/>'
                 f'<text x="{sx(pts[-1][0]) + 8:.1f}" y="{sy(pts[-1][1]) + 4:.1f}" font-size="11" fill="var(--ink2)">{esc(label)}</text>')
    if points:
        d = " ".join(f"{'M' if k == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for k, (x, y, _) in enumerate(points))
        g.append(f'<path d="{d}" fill="none" stroke="var(--s1)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        for x, y, _ in points:
            g.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="var(--s1)" stroke="var(--surface)" stroke-width="2"/>')
        lx, ly, _ = points[-1]
        g.append(f'<text x="{sx(lx) + 8:.1f}" y="{sy(ly) + 4:.1f}" font-size="12" font-weight="600" fill="var(--ink)">{fmt_n(ly)}</text>')
    for x, y, tip, cls in markers:
        col = {"crit": "var(--crit)", "good": "var(--good)"}.get(cls, "var(--muted)")
        g.append(f'<path d="M{sx(x):.1f},{sy(y) - 6:.1f} l6,6 l-6,6 l-6,-6z" fill="{col}" stroke="var(--surface)" stroke-width="2"><title>{esc(tip)}</title></path>')
    g.append(f'<line class="cross" x1="0" x2="0" y1="{T}" y2="{H - B}" stroke="var(--axis)" stroke-width="1" style="display:none"/>')
    n = len(points)
    for k, (x, y, tip) in enumerate(points):
        lo = sx(points[k - 1][0]) if k else L
        hi = sx(points[k + 1][0]) if k + 1 < n else sx(x) + 20
        a, b = (lo + sx(x)) / 2, (sx(x) + hi) / 2
        g.append(f'<rect class="hit" tabindex="0" x="{a:.1f}" y="{T}" width="{max(b - a, 8):.1f}" height="{H - T - B}" fill="transparent" data-x="{sx(x):.1f}" data-tip="{esc(tip)}"/>')
    g.append("</svg>")
    return f'<div class="chart">{"".join(g)}<div class="tip" role="status"></div></div>'


def table_view(headers: list[str], rows: list[list]) -> str:
    return ('<details><summary>Vista tabella</summary><div class="wrap"><table><thead><tr>' + "".join(f'<th{" class=n" if k else ""}>{esc(h)}</th>' for k, h in enumerate(headers))
            + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f'<td{" class=n" if k else ""}>{esc(c)}</td>' for k, c in enumerate(r)) + "</tr>" for r in rows) + "</tbody></table></div></details>")


def wishlist_section(root: str, today: dt.date):
    rows = wl.read_rows(os.path.join(root, "wishlists.csv"))
    if not rows:
        return None, None
    plan_path = os.path.join(root, "_raw", "wl_plan.json")
    plan = load_json(plan_path) if os.path.exists(plan_path) else None
    a = wl.analyse(rows, plan, today)
    base = dt.date.fromisoformat(rows[0]["date"])
    day = lambda s: (dt.date.fromisoformat(s) - base).days
    pts = [(day(r["date"]), r["wishlists"], f"{fmt_date(r['date'])}\n{fmt_n(r['wishlists'])} wishlist" + (f"\n{r['note']}" if r["note"] else "")) for r in rows]
    refs, markers, ymax = [], [], max(r["wishlists"] for r in rows)
    pad = 0.0
    if plan:
        start = dt.date.fromisoformat(plan.get("start") or rows[0]["date"])
        sv = wl.at(rows, start) if wl.at(rows, start) is not None else rows[0]["wishlists"]
        for name, target in sorted(plan.get("targets", {}).items(), key=lambda kv: kv[1]):
            refs.append((f"{name}: {fmt_n(target)}", [(day(str(start)), sv), (day(plan["launch"]), target)], True))
            ymax = max(ymax, target)
        pad = max(day(plan["launch"]) - max(p[0] for p in pts), 0)
        for t in a.get("tripwires", []):
            cls = "crit" if t["status"] == "ALLARME" else "good" if t["status"] == "OK" else "muted"
            markers.append((day(t["date"]), t["min_wishlists"], f"Tripwire {t['date']}: {t['label']} (soglia {fmt_n(t['min_wishlists'])}, {t['status']})", cls))
            ymax = max(ymax, t["min_wishlists"])
    span = max(p[0] for p in pts) + pad
    ticks = [(span * k / 4, fmt_date((base + dt.timedelta(days=round(span * k / 4))).isoformat())) for k in range(5)]
    ay = nice_axis(0, ymax * 1.05)
    svg = line_chart("Wishlist registrate contro gli scenari", pts, xlabels=ticks, ymin=ay[0], ymax=ay[1], ystep=ay[2], refs=refs, markers=markers, xmax_pad=pad)
    svg += table_view(["Data", "Wishlist", "Nota"], [[r["date"], fmt_n(r["wishlists"]), r["note"]] for r in rows])
    return a, svg


def timeline_section(root: str):
    path = os.path.join(root, "fg", "timeline.csv")
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None, None
    pts = [(k, float(r["score"]), f"Ondata {r['wave']} ({fmt_date(r['date'])})\nPunteggio {r['score']}\nBuild {r.get('build') or '-'}\nClick {r.get('click_pct')}% · pitch {r.get('pitch_pct')}%") for k, r in enumerate(rows)]
    gate = float(rows[-1]["gate"]) if rows[-1].get("gate") else None
    lo, hi = min([p[1] for p in pts] + ([gate] if gate is not None else []) + [0]), max([p[1] for p in pts] + ([gate] if gate is not None else []) + [40])
    refs = [(f"Gate A: {fmt_n(gate)}", [(0, gate), (max(len(pts) - 1, 1), gate)], True)] if gate is not None else []
    ay = nice_axis(min(lo - 5, 0), hi + 10)
    svg = line_chart("Punteggio wishlist del focus group per ondata", pts, xlabels=[(k, f"Ondata {r['wave']}") for k, r in enumerate(rows)], ymin=ay[0], ymax=ay[1], ystep=ay[2], refs=refs,
                     xmax_pad=0.0 if len(pts) > 1 else 1)
    svg += table_view(["Ondata", "Data", "Punteggio", "Variazione", "Click %", "Pitch %", "A / B"], [[r["wave"], r["date"], r["score"], r.get("delta") or "", r.get("click_pct"), r.get("pitch_pct"), f"{r.get('score_a')} / {r.get('score_b')}"] for r in rows])
    return rows, svg


# ----------------------------------------------------------------------------- other sources
def read_calendar(root: str):
    p = os.path.join(root, "calendar.md")
    if not os.path.exists(p):
        return []
    rows, header = [], None
    for ln in open(p, encoding="utf-8").read().splitlines():
        if ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if header is None and cells and cells[0].lower().startswith("data"):
                header = cells
            elif header and not re.match(r"^[-:\s|]+$", ln) and re.match(r"\d{4}-\d{2}-\d{2}", cells[0]):
                rows.append(cells)
    return sorted(rows, key=lambda r: r[0])


def read_todos(root: str):
    p = os.path.join(root, "TODO.md")
    if not os.path.exists(p):
        return [], 0, 0.0
    open_, done = [], 0
    for ln in open(p, encoding="utf-8").read().splitlines():
        m = re.match(r"^\s*(?:[-*]\s*)?\[( |x|X)\]\s*(.+)", ln)
        if not m:
            continue
        if m.group(1) != " ":
            done += 1
            continue
        parts = [x.strip() for x in m.group(2).split("|")]
        hours = re.search(r"[\d.,]+", parts[2]) if len(parts) > 2 else None
        open_.append(dict(action=parts[0], due=parts[1] if len(parts) > 1 else "", hours=parts[2] if len(parts) > 2 else "", metric=parts[-1] if len(parts) > 4 else "",
                          h=float(hours.group(0).replace(",", ".")) if hours else 0.0))
    open_.sort(key=lambda t: t["due"] if re.match(r"\d{4}-\d{2}-\d{2}", t["due"]) else "9999")
    return open_, done, sum(t["h"] for t in open_)


# ----------------------------------------------------------------------------- page
def build(root: str, audience: str, include: list[str], exclude: list[str], hide: set[str], today: dt.date) -> str:
    st = load_json(os.path.join(root, "status.json")) if os.path.exists(os.path.join(root, "status.json")) else {}
    hide = set(hide) | HIDE_BY_AUDIENCE[audience]
    wl_a, wl_svg = wishlist_section(root, today)
    fg_rows, fg_svg = timeline_section(root)
    econ = load_json(os.path.join(root, "_raw", "econ.json")) if os.path.exists(os.path.join(root, "_raw", "econ.json")) and "economics" not in hide else None
    sec = []
    v = st.get("verdict") or {}
    if v:
        kind, word = LIGHT.get(str(v.get("color", "")).lower(), ("info", str(v.get("color", "n/d"))))
        risks = "".join(f"<li>{state('warn', f'Rischio {k}')}<span>{esc(r)}</span></li>" for k, r in enumerate(v.get("risks", [])[:3], 1))
        sec.append(f'<section class="card verdict"><div>{ICONS[kind][0]}</div><div><div class="big">Verdetto: {esc(word)}{" (provvisorio)" if v.get("provisional") else ""}</div>'
                   f'<p>{esc(v.get("summary", ""))}</p>' + (f'<p class="sub">Probabilità stimata di recuperare i costi: {esc(v["probability"])}</p>' if v.get("probability") else "")
                   + (f'<ul class="clean">{risks}</ul>' if risks else "") + "</div></section>")
    tiles = []
    if wl_a and "current" in wl_a:
        vel = wl_a.get("velocity_4w")
        tiles.append(("Wishlist", fmt_n(wl_a["current"]), f"{'+' if vel and vel > 0 else ''}{fmt_n(vel)} a settimana (ultime 4)" if vel is not None else f"dato del {fmt_date(wl_a['last_record'])}"))
        if "days_to_launch" in wl_a:
            tiles.append(("Giorni al lancio", fmt_n(wl_a["days_to_launch"]), fmt_date(wl_a["launch"])))
    if fg_rows:
        last, prev = fg_rows[-1], fg_rows[-2] if len(fg_rows) > 1 else None
        tiles.append(("Punteggio focus group", last["score"], f"ondata {last['wave']}" + (f", {float(last['score']) - float(prev['score']):+.1f} rispetto alla precedente" if prev else "")))
    if econ:
        tiles.append(("Break-even", fmt_n(econ["breakeven"]["copies_with_time"]), f"copie (netto per copia {econ['net_per_copy']:.2f})"))
    gates = st.get("gates") or {}
    if gates:
        tiles.append(("Gate superati", f"{sum(1 for g in gates.values() if g.get('state') == 'pass')}/{len(gates)}", "Go/No-Go prima di Steam Direct"))
    for k in st.get("key_numbers", []):
        tiles.append((k.get("label", ""), k.get("value", ""), k.get("note", "")))
    if tiles:
        sec.append('<h2>Numeri chiave</h2><div class="grid g4">' + "".join(f'<div class="card tile"><div class="l">{esc(l)}</div><div class="v">{esc(val)}</div><div class="d">{esc(d)}</div></div>' for l, val, d in tiles) + "</div>")
    if wl_a and wl_a.get("alerts"):
        icon = {"ALARM": ("fail", "Allarme"), "ATTENZIONE": ("warn", "Attenzione"), "INFO": ("info", "Info")}
        sec.append('<h2>Alert wishlist</h2><div class="card"><ul class="clean">' + "".join(f"<li>{state(*icon[x['level']])}<span>{esc(x['text'])}</span></li>"
                   for x in sorted(wl_a["alerts"], key=lambda x: ["ALARM", "ATTENZIONE", "INFO"].index(x["level"]))) + "</ul></div>")
    if wl_svg or fg_svg:
        sec.append("<h2>Andamento</h2><div class=\"grid\">")
        if wl_svg:
            sec.append(f'<div class="card"><h3>Wishlist contro gli scenari</h3><div class="legend"><span><i style="border-color:var(--s1)"></i>Registrate</span><span><i style="border-color:var(--muted)"></i>Percorso degli scenari (lineare)</span></div>{wl_svg}'
                       '<p class="note">Wishlist inserite a mano da Steamworks. I percorsi sono lineari: semplificazione, i picchi (festival, lancio) non sono previsti.</p></div>')
        if fg_svg:
            sec.append(f'<div class="card"><h3>Focus group simulato, per ondata</h3>{fg_svg}<p class="note">Panel simulato con gli stessi tester: ordina i problemi, non prevede le vendite.</p></div>')
        sec.append("</div>")
    if gates:
        names = {"0": "Gate 0 · Posizionamento", "A": "Gate A · Qualità percepita", "B": "Gate B · Test reale", "C": "Gate C · Capsule"}
        sec.append('<h2>Cancelli Go / No-Go</h2><div class="grid g4">' + "".join(
            f'<div class="card"><div>{state({"pass": "pass", "fail": "fail", "pending": "pending"}.get(g.get("state"), "na"))}</div><h3>{esc(names.get(k, "Gate " + k))}</h3><p class="note">{esc(g.get("note", ""))}</p></div>'
            for k, g in gates.items()) + "</div>")
    cal = read_calendar(root)
    if cal and "calendar" not in hide:
        today_s = today.isoformat()
        sec.append('<h2>Calendario</h2><div class="card wrap"><table><thead><tr><th>Data</th><th>Evento</th><th>Tipo</th></tr></thead><tbody>' + "".join(
            f'<tr class="{"past" if r[0] < today_s else ""}"><td>{fmt_date(r[0])}</td><td>{esc(r[1] if len(r) > 1 else "")}</td><td>{esc(r[2] if len(r) > 2 else "")}</td></tr>' for r in cal) + "</tbody></table></div>")
    todos, done, hours = read_todos(root)
    if todos and "todo" not in hide:
        sec.append(f'<h2>Prossime azioni</h2><div class="card"><p class="sub">{len(todos)} aperte, {done} chiuse, circa {hours:.0f} ore residue.</p><div class="wrap"><table><thead><tr><th>Azione</th><th>Scadenza</th><th class="n">Ore</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(t["action"])}</td><td>{esc(t["due"])}</td><td class="n">{esc(t["hours"])}</td></tr>' for t in todos[:10]) + "</tbody></table></div></div>")
    if econ:
        sec.append('<h2>Economia</h2><div class="card wrap"><table><thead><tr><th>Scenario</th><th class="n">Wishlist</th><th class="n">Copie</th><th class="n">Netto</th><th class="n">Utile (cassa)</th></tr></thead><tbody>' + "".join(
            f'<tr><td>{esc(s["name"])}</td><td class="n">{fmt_n(s["wishlists"])}</td><td class="n">{fmt_n(s["copies"])}</td><td class="n">{fmt_n(s["net"])}</td><td class="n">{fmt_n(s["profit_cash"])}</td></tr>' for s in econ["scenarios"])
            + f'</tbody></table><p class="note">Netto per copia {econ["net_per_copy"]:.2f}; aliquote e conversioni sono ipotesi dichiarate nel piano, da verificare.</p></div>')
    stems = [s for s in (include or AUDIENCES[audience]) if s not in exclude]
    docs = []
    for stem in stems:
        p = os.path.join(root, f"{stem}.md")
        if os.path.exists(p):
            docs.append(f'<details class="card doc"><summary><strong>{esc(DOCS.get(stem, stem))}</strong></summary>{md_to_html(open(p, encoding="utf-8").read())}</details>')
    if docs:
        sec.append("<h2>Documenti</h2>" + "".join(docs))
    name = st.get("game") or os.path.basename(os.path.dirname(os.path.abspath(root))) or "Progetto"
    label = {"private": "Uso interno", "partner": "Per i soci", "publisher": "Per il publisher"}[audience]
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stato del lancio, {esc(name)}</title>'
            f'<style>{CSS}</style></head><body><main><div class="top"><div><h1>{esc(name)}: stato del lancio</h1><p class="sub">Aggiornato il {fmt_date(st.get("updated") or today.isoformat())} · {esc(label)}'
            f'{" · modalità " + esc(st["mode"]) if st.get("mode") else ""}</p></div><button class="theme" id="theme" type="button">Tema chiaro/scuro</button></div>'
            + "".join(sec) + f'<footer class="note">Pagina generata da <code>status_page.py</code> il {today.isoformat()} da file locali, senza richieste di rete. Il focus group è simulato: non è un dato di mercato. '
            f'Cifre con fonte nei documenti; ciò che è etichettato [DA VERIFICARE] resta da verificare.</footer></main><script>{JS}</script></body></html>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("--audience", default="partner", choices=list(AUDIENCES))
    ap.add_argument("--include", nargs="*", default=[], help=f"document stems to show instead of the audience default ({', '.join(DOCS)})")
    ap.add_argument("--exclude", nargs="*", default=[], help="document stems to leave out"); ap.add_argument("--hide", default="", help="comma list: economics,todo,calendar")
    ap.add_argument("--today", help="override today (YYYY-MM-DD)"); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    root = a.launch_dir
    if not os.path.isdir(root):
        raise SystemExit(f"{root} not found")
    page = build(root, a.audience, a.include, a.exclude, {x for x in a.hide.split(",") if x}, dt.date.fromisoformat(a.today) if a.today else dt.date.today())
    out = a.out or os.path.join(root, "STATUS.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    log(f"wrote {out} ({len(page) // 1024} KB, audience {a.audience}). Nothing was published: sharing it is your decision.")


if __name__ == "__main__":
    main()
