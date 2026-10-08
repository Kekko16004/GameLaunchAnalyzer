#!/usr/bin/env python3
"""One self-contained HTML status page for partners or a publisher: verdict, decision profile, key numbers, alerts,
the step-by-step calendar (who does what), wishlist vs scenarios, focus-group timeline, Go/No-Go gates, copy-ready Steam
and itch.io pages (a Copy button on every field), "if... then" contingency plans with live status, competitors, open TODOs
and the main documents (collapsible).

It only READS files already produced in `launch/` and writes `launch/STATUS.html` (no network, no external scripts, no
tracking: everything is inline, so the file can be attached to an email as is). All text coming from files is escaped.
  launch/status.json         verdict, gates, key numbers, intentions (written by the skill, see references/06-synthesis-output.md)
  launch/calendar.md         dates and the `## ✅ Passi in ordine` steps with 👤/🤖 owners (plan_steps.py reads them)
  launch/store_kit.json      copy-ready Steam and itch.io pages (store_kit.py)
  launch/_raw/contingencies.json + launch/metrics.csv    "if... then" scenarios and the numbers you record (metrics_track.py)
  launch/fg/timeline.csv     focus-group waves (fg_waves.py timeline --csv)
  launch/wishlists.csv + launch/_raw/wl_plan.json        wishlist tracker (wl_track.py)
  launch/watchlist.csv       comparables and competitors over time (watchlist.py)
  launch/creators.csv        creators found (build_creators.py), shown as a collapsible table
  launch/_raw/econ.json      economic plan (calc_econ.py);  launch/TODO.md and the reports in launch/
  launch/_raw/window.json    launch window: competitor crowding per week (launch_window.py), shown as a table and a chart
  launch/steamdb.csv         numbers read by hand on SteamDB (steamdb_assist.py)
  launch/fg/waves/wNN-metrics.md, wNN-delta.md   per-wave reports of the focus group (fg_waves.py)
On top: a sticky index of the sections, the verdict with the Go/No-Go gates at a glance, and an "Adesso" box (whose turn it is).
Charts ("Quadro d'insieme") come from report_charts.py; the same charts next to the text of the report are in report_html.py.
Anything missing is simply left out.

Sharing: the page contains strategy. --audience picks what goes in (default private):
  private    everything, including creators, community, legal/fiscal
  partner    everything except creators, community and legal/fiscal documents
  publisher  verdict, numbers, charts, gates, calendar dates, store pages, positioning, platform, focus group;
             no steps, economics, TODO, contingencies, competitors, creators, decision profile or full-game analysis
Add/remove documents with --include / --exclude (file stems such as 03-pricing) and sections with
--hide economics,todo,calendar,steps,storekit,contingencies,watchlist,intentions,creators,fullgame,charts,steamdb,fgwaves,window.
Publishing the page anywhere is YOUR decision: this tool only writes the local file.

  python status_page.py [--launch-dir launch] [--audience private] [-o launch/STATUS.html]
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
import metrics_track as mt
import charts as ch
import glossary as gl
import plan_steps as ps
import report_charts as rc
from launch_window import LABEL
import store_kit as sk
import watchlist as wlist
import wl_track as wl

MONTHS = "gen feb mar apr mag giu lug ago set ott nov dic".split()
DOCS = {  # stem -> title
    "REPORT": "Report completo", "00-intenzioni": "Intenzioni e decisioni", "04b-store-copy": "Testi dello store e trailer", "05d-contingenze": "Piani di contingenza (se… allora)", "00-brief": "Brief del progetto", "01b-positioning": "Posizionamento", "01-dev": "Audit del prodotto",
    "01c-full-game": "Gioco completo: analisi rapida", "02-platform": "Piattaforme, demo e gate", "03-pricing": "Prezzo ed economia", "05-focusgroup": "Focus group", "05c-premortem": "Pre-mortem",
    "04-clips": "Hook e clip", "03-pricing-calc": "Calcolo economico", "05a-critiche-simulate": "Critiche simulate", "05b-critiche-reali": "Critiche reali (con fonti)", "window": "Finestra di lancio: concorrenti",
    "06-creators": "Creator", "07-community": "Community e test reale", "08-brand-legal": "Brand, legale e fiscale"}
AUDIENCES = {
    "private": list(DOCS),
    "partner": ["REPORT", "00-intenzioni", "01b-positioning", "01c-full-game", "02-platform", "03-pricing", "03-pricing-calc", "04-clips", "05-focusgroup", "05a-critiche-simulate", "05b-critiche-reali", "05c-premortem", "05d-contingenze", "window"],
    "publisher": ["01b-positioning", "02-platform", "05-focusgroup"]}
HIDE_BY_AUDIENCE = {"private": set(), "partner": set(), "publisher": {"economics", "todo", "contingencies", "steps", "watchlist", "intentions", "creators", "fullgame", "steamdb", "fgwaves"}}

CSS = """
:root{color-scheme:light;--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--goodtext:#006300}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--goodtext:#0ca30c}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--goodtext:#0ca30c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px;overflow-wrap:anywhere}.card{min-width:0}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:36px 0 12px}h3{font-size:1rem;margin:20px 0 8px}
.sub{color:var(--ink2);margin:0 0 4px}.note{color:var(--muted);font-size:.85rem}.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
button.theme{background:var(--surface);color:var(--ink2);border:1px solid var(--ring);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit;font-size:.85rem}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px}.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr))}
.verdict{display:flex;gap:16px;align-items:flex-start}.verdict>div:first-child svg{width:40px;height:40px}.verdict>div:last-child{min-width:0}.verdict .big{font-size:1.25rem;font-weight:600}.tile .v{font-size:1.9rem;font-weight:600;line-height:1.1}.tile .l{color:var(--ink2);font-size:.85rem}.tile .d{color:var(--ink2);font-size:.85rem;margin-top:4px}
.state{display:inline-flex;align-items:center;gap:6px;font-weight:600;white-space:nowrap;flex:none}.state svg{flex:none}.g2{grid-template-columns:repeat(auto-fit,minmax(min(380px,100%),1fr))}ul.clean{list-style:none;margin:0;padding:0}ul.clean li{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-top:1px solid var(--grid)}ul.clean li:first-child{border-top:0}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}th{color:var(--ink2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}tr.past td{color:var(--muted)}details{margin-top:8px}summary{cursor:pointer;color:var(--ink2)}
.chart{position:relative}.chart svg{width:100%;height:auto;display:block}.tip{position:absolute;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:8px 10px;font-size:.85rem;white-space:pre-line;box-shadow:0 2px 10px rgba(0,0,0,.15);display:none;max-width:260px;z-index:2}
.doc{margin-top:12px}.doc h3{font-size:1rem}.doc h4,.doc h5{font-size:.95rem;margin:14px 0 6px}.doc code{background:var(--grid);padding:1px 4px;border-radius:4px;font-size:.85em}.doc pre{background:var(--grid);padding:10px;border-radius:8px;overflow-x:auto}.doc blockquote{margin:8px 0;padding-left:12px;border-left:3px solid var(--axis);color:var(--ink2)}
a{color:var(--s1)}footer{margin-top:40px}
.progress{height:10px;border-radius:5px;background:var(--grid);overflow:hidden;margin:8px 0}.progress span{display:block;height:100%;background:var(--s1);border-radius:5px}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.filters button,button.copy{background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:6px 12px;cursor:pointer;font:inherit;font-size:.85rem}
.filters button[aria-pressed="true"]{border-color:var(--s1);box-shadow:inset 0 0 0 1px var(--s1)}button.copy.ok{border-color:var(--good)}
ol.steps{list-style:none;margin:8px 0 0;padding:0}.step{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;padding:10px 0;border-top:1px solid var(--grid)}.step[hidden]{display:none}.step .meta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;font-size:.85rem;color:var(--ink2)}
.step .n{color:var(--muted);font-variant-numeric:tabular-nums}.step .stext{grid-column:2}.step .notes{grid-column:2;color:var(--ink2);font-size:.9rem}.owner{font-weight:600;color:var(--ink)}.step[data-state="done"] .stext{color:var(--muted)}
summary .count{color:var(--ink2);font-weight:400;margin-left:8px}.field{padding:10px 0;border-top:1px solid var(--grid)}.field:first-of-type{border-top:0}.fh{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap}
pre.val{background:var(--grid);padding:10px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;margin:6px 0;font:inherit;font-size:.9rem}.slot{border:2px dashed var(--axis);border-radius:8px;padding:12px;margin:6px 0;color:var(--ink2);font-size:.9rem}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{border:1px solid var(--ring);border-radius:999px;padding:3px 10px;font-size:.85rem;background:var(--surface)}.chip.top5{border-color:var(--s1);font-weight:600}.chip b{color:var(--muted);margin-right:4px;font-weight:400}
.gh{font-size:1.05rem;margin:26px 0 2px}.toc{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;gap:8px;overflow-x:auto;white-space:nowrap;padding:8px 0;margin:8px 0 0;border-bottom:1px solid var(--grid)}.toc+section{margin-top:12px}.toc a{flex:none;border:1px solid var(--ring);border-radius:999px;padding:3px 12px;font-size:.85rem;text-decoration:none;color:var(--ink2);background:var(--surface)}.toc a:hover,.toc a:focus{border-color:var(--s1);color:var(--ink)}h2{scroll-margin-top:56px}.gates{display:flex;gap:6px 16px;flex-wrap:wrap;margin:10px 0 2px;font-size:.9rem}@media print{.toc,.top button{display:none}body{background:#fff}}.over{color:var(--crit);font-weight:600}.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink2);font-size:.85rem;margin:6px 0}.legend i{display:inline-block;width:18px;height:0;border-top:2px solid;vertical-align:middle;margin-right:6px}
""" + ch.CHART_CSS + gl.CSS
JS = """
(function(){document.querySelectorAll('.copy').forEach(function(b){b.addEventListener('click',function(){var t=b.getAttribute('data-copy')||'';function ok(){var o=b.textContent;b.textContent='Copiato';b.classList.add('ok');setTimeout(function(){b.textContent=o;b.classList.remove('ok');},1500);}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,function(){fb(t,ok);});}else{fb(t,ok);}});});
function fb(t,ok){var a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();try{document.execCommand('copy');ok();}catch(e){}document.body.removeChild(a);}
document.querySelectorAll('.filters button').forEach(function(b){b.addEventListener('click',function(){var f=b.getAttribute('data-f');document.querySelectorAll('.filters button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
document.querySelectorAll('.step').forEach(function(s){var o=s.getAttribute('data-owner');s.hidden=!(f==='all'||o===f||o==='both');});});});
var b=document.getElementById('theme');if(b){b.addEventListener('click',function(){var r=document.documentElement,d=r.getAttribute('data-theme')==='dark'||(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);r.setAttribute('data-theme',d?'light':'dark');});}
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
OWNER = {"me": "👤 Tu", "claude": "🤖 Claude", "both": "👤+🤖 Insieme", "none": "—"}
STEP_STATE = {"done": ("pass", "Fatto"), "open": ("pending", "Da fare"), "overdue": ("warn", "In ritardo")}


def step_li(s: dict, today: dt.date) -> str:
    st = ps.status_of(s, today)
    due = f'<span>entro {fmt_date(s["due"])}</span>' if s.get("due") else ""
    notes = f'<div class="notes">{"<br>".join(inline(n) for n in s["notes"])}</div>' if s.get("notes") else ""
    return (f'<li class="step" data-owner="{s["owner"]}" data-state="{st}"><span class="n">{s["n"]}.</span><div class="meta">{state(*STEP_STATE[st])}<span class="owner">{OWNER[s["owner"]]}</span>{due}</div>'
            f'<div class="stext">{inline(s["text"])}</div>{notes}</li>')


GATE_NAMES = {"0": "Gate 0 · Posizionamento", "A": "Gate A · Qualità percepita", "B": "Gate B · Test reale", "C": "Gate C · Capsule"}


def now_block(plan: dict, today: dt.date) -> str:
    """The two boxes everybody reads first: what is the owner's turn now, and what is Claude's."""
    now_me, now_ai = ps.next_steps(plan, "me", 3, today), ps.next_steps(plan, "claude", 3, today)
    box = lambda title, items: (f'<div class="card"><h3>{title}</h3>' + ("<ul class=\"clean\">" + "".join(f'<li>{state(*STEP_STATE[ps.status_of(s, today)])}<span><strong>{s["n"]}.</strong> {inline(s["text"])}'
                                + (f' <span class="note">(entro {fmt_date(s["due"])})</span>' if s.get("due") else "") + "</span></li>" for s in items) + "</ul>" if items else "<p class=\"note\">Niente in sospeso.</p>") + "</div>")
    return '<h2>Adesso</h2><div class="grid g2">' + box("Tocca a te", now_me) + box("Tocca a Claude", now_ai) + "</div>"


def steps_section(plan: dict, today: dt.date) -> str:
    sm = ps.summary(plan, today)
    pct = round(100 * sm["done"] / sm["total"]) if sm["total"] else 0
    out = ['<h2>Passi in ordine</h2><div class="card">', f'<p class="sub">{esc(plan.get("intro") or "👤 = li fai tu · 🤖 = li fa Claude · 👤+🤖 = insieme")}</p>',
           f'<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}" aria-label="Avanzamento dei passi"><span style="width:{pct}%"></span></div>',
           f'<p><strong>{sm["done"]} di {sm["total"]}</strong> fatti · {sm["overdue"]} in ritardo · ancora aperti: {sm["me_open"]} tuoi, {sm["claude_open"]} di Claude</p>',
           '<div class="filters" role="group" aria-label="Filtra i passi"><button type="button" data-f="all" aria-pressed="true">Tutti</button><button type="button" data-f="me" aria-pressed="false">Solo i miei</button>'
           '<button type="button" data-f="claude" aria-pressed="false">Solo Claude</button></div></div>']
    first_open = next((k for k, p in enumerate(plan["phases"]) if any(not s["done"] for s in p["steps"])), 0)
    for k, p in enumerate(plan["phases"]):
        done = sum(s["done"] for s in p["steps"])
        out.append(f'<details class="card" style="margin-top:12px"{" open" if k == first_open else ""}><summary><strong>{inline(p["title"])}</strong><span class="count">{done}/{len(p["steps"])} fatti</span></summary>'
                   f'<ol class="steps">{"".join(step_li(x, today) for x in p["steps"])}</ol></details>')
    return "".join(out)


def copy_btn(text: str) -> str:
    return f'<button type="button" class="copy" data-copy="{esc(text)}">Copia</button>'


def kit_platform(pf: str, title: str, p: dict, verified: str) -> str:
    limits = p.get("limits") or {}
    o = [f'<details class="card" style="margin-top:12px" open><summary><strong>{esc(title)}</strong><span class="count">limiti verificati il {esc(verified or "[DA VERIFICARE]")}</span></summary>']
    for f in p.get("fields", []):
        val, lim = str(f.get("value") or ""), limits.get(f.get("key"))
        cnt = f'<span class="note">{len(val)}{"/" + str(lim) if lim else ""} caratteri</span>' + (f' {state("fail", "Oltre il limite")}' if lim and len(val) > lim else "")
        o.append(f'<div class="field"><div class="fh"><strong>{esc(f.get("label") or f["key"])}</strong><span>{cnt} {copy_btn(val)}</span></div><pre class="val">{esc(val)}</pre>' + (f'<p class="note">{esc(f["note"])}</p>' if f.get("note") else "") + "</div>")
    ld = p.get("long_description") or {}
    if ld.get("blocks"):
        full = sk.assemble(ld)
        o.append(f'<div class="field"><div class="fh"><strong>Descrizione lunga ({esc(ld.get("format", "testo"))})</strong><span><span class="note">{len(full)} caratteri</span> {copy_btn(full)}</span></div>'
                 '<p class="note">I riquadri tratteggiati sono i punti dove vanno foto e GIF: nel testo copiato compaiono come segnaposto &lt;&lt;&lt; … &gt;&gt;&gt; da sostituire con l\'upload.</p>')
        for b in ld["blocks"]:
            if b.get("type") == "media":
                o.append(f'<div class="slot"><strong>📷 {esc(b.get("slot", "Media"))}</strong>: {esc(b.get("what", ""))}<br><span class="note">file: {esc(b.get("file") or "da produrre")}{" · alt: " + esc(b["alt"]) if b.get("alt") else ""}</span></div>')
            else:
                o.append(f'<pre class="val">{esc(b.get("value", ""))}</pre>')
        o.append("</div>")
    if p.get("tags"):
        allt = ", ".join(t["tag"] for t in p["tags"])
        o.append(f'<div class="field"><div class="fh"><strong>Tag, in ordine</strong><span class="note">i primi 5 pesano di più {copy_btn(allt)}</span></div><div class="chips">'
                 + "".join(f'<span class="chip{" top5" if i <= 5 else ""}" title="{esc(t.get("why", ""))}"><b>{i}</b>{esc(t["tag"])}</span>' for i, t in enumerate(p["tags"], 1)) + "</div>"
                 + ("<details><summary>Perché questi tag</summary><ul>" + "".join(f'<li><strong>{esc(t["tag"])}</strong>: {esc(t.get("why", ""))}</li>' for t in p["tags"]) + "</ul></details>")
                 + ("<p class=\"note\">Da evitare: " + "; ".join(f"{esc(t['tag'])} ({esc(t.get('why', ''))})" for t in p["avoid_tags"]) + "</p>" if p.get("avoid_tags") else "") + "</div>")
    def tbl(title: str, head: list[str], rows: list[list]) -> str:
        return (f'<div class="field"><strong>{esc(title)}</strong><div class="wrap"><table><thead><tr>{"".join(f"<th>{esc(h)}</th>" for h in head)}</tr></thead><tbody>'
                + "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div></div>")
    if p.get("screenshots"):
        o.append(tbl("Screenshot, in ordine", ["#", "Cosa mostra", "Didascalia", "File"], [[x.get("order"), x.get("what", ""), x.get("caption", ""), x.get("file") or "da produrre"] for x in sorted(p["screenshots"], key=lambda x: x.get("order") or 0)]))
    if p.get("capsules"):
        o.append(tbl("Immagini e capsule", ["Nome", "Misura", "Cosa deve comunicare"], [[c.get("name"), c.get("size", "[DA VERIFICARE]"), c.get("what", "")] for c in p["capsules"]]))
    if p.get("trailer"):
        t = p["trailer"]
        o.append(f'<div class="field"><strong>Trailer</strong><p>Durata prevista {esc(t.get("duration_s", "?"))} s · posizione: {esc(t.get("placement", ""))} · script: {esc(t.get("script", ""))}</p></div>')
    if p.get("settings"):
        o.append(tbl("Impostazioni da compilare", ["Voce", "Valore", "Nota"], [[x.get("label"), x.get("value"), x.get("note", "")] for x in p["settings"]]))
    if p.get("checklist"):
        o.append('<div class="field"><strong>Controlli prima di pubblicare</strong><ul class="clean">' + "".join(f"<li>{state('pending', 'Da fare')}<span>{esc(c)}</span></li>" for c in p["checklist"]) + "</ul></div>")
    o.append("</details>")
    return "".join(o)


def kit_section(kit: dict) -> str:
    out = ['<h2>Pagine store: scheda copiabile</h2><p class="note">Ogni campo ha il suo pulsante Copia. I testi vengono da <code>store_kit.json</code>; i limiti di caratteri sono quelli dichiarati nel file con la data di verifica.</p>']
    for pf, title in (("steam", "Pagina Steam"), ("itch", "Pagina itch.io")):
        if kit.get(pf):
            out.append(kit_platform(pf, title, kit[pf], kit.get("verified_on", "")))
    return "".join(out)


SC_STATE = {"SCATTATO": ("fail", "Scattato"), "OK": ("pass", "Ok"), "SENZA DATI": ("pending", "Senza dati"), "NON ANCORA": ("na", "Non ancora attivo")}


def contingency_section(root: str, today: dt.date):
    path = os.path.join(root, "_raw", "contingencies.json")
    if not os.path.exists(path):
        return None, []
    rows = mt.read_metrics(os.path.join(root, "metrics.csv"), os.path.join(root, "wishlists.csv"))
    res = mt.evaluate(load_json(path), rows, today)
    order = ["SCATTATO", "SENZA DATI", "OK", "NON ANCORA"]
    res.sort(key=lambda r: (order.index(r["status"]), r.get("area", "")))
    n = {k: sum(1 for r in res if r["status"] == k) for k in order}
    o = [f'<h2>Se… allora: piani di contingenza</h2><p class="sub">{n["SCATTATO"]} scattati · {n["OK"]} ok · {n["SENZA DATI"]} senza dati · {n["NON ANCORA"]} non ancora attivi. Le soglie sono ipotesi dichiarate: la fonte è scritta sotto ogni scenario.</p>']
    alerts = []
    for r in res:
        if r["status"] == "SCATTATO":
            alerts.append(("ALARM" if r.get("severity") == "ALARM" else "ATTENZIONE", f"Scenario scattato · {r.get('area', '')}: {r['title']}"))
        sig = "".join(f"<li>{state('pass' if x['holds'] else 'fail' if x['holds'] is False else 'pending', 'Vero' if x['holds'] else 'Falso' if x['holds'] is False else 'Senza dati')}<span>{esc(x['label'])} {esc(x['op'])} {esc(x['threshold'])} → {esc(x['detail'])}</span></li>" for x in r["signals_eval"])
        body = [f'<ul class="clean">{sig}</ul>'] if sig else []
        if r.get("diagnosis"):
            body.append("<h3>Prima controlla</h3><ol>" + "".join(f"<li>{inline(d)}</li>" for d in r["diagnosis"]) + "</ol>")
        if r.get("actions"):
            body.append("<h3>Azioni, dalla più economica</h3><ul>" + "".join(f'<li>{inline(a["text"])} <span class="note">({esc(OWNER.get(a.get("owner", "none"), a.get("owner", "")))}, costo {esc(a.get("cost", "?"))})</span></li>' for a in r["actions"]) + "</ul>")
        if r.get("decision"):
            body.append(f"<h3>Decisione</h3><p>{inline(r['decision'])}</p>")
        if r.get("evidence"):
            body.append(f'<p class="note">Origine della soglia: {esc(r["evidence"])}</p>')
        o.append(f'<details class="card" style="margin-top:12px"{" open" if r["status"] == "SCATTATO" else ""}><summary>{state(*SC_STATE[r["status"]])} <strong>{esc(r.get("area", ""))}</strong> · {esc(r["title"])}'
                 f'<span class="count">{esc(r.get("severity", "ATTENZIONE"))}</span></summary>{"".join(body)}</details>')
    return "".join(o), alerts


def watch_section(root: str, today: dt.date):
    rows = wlist.read(os.path.join(root, "watchlist.csv"))
    if not rows:
        return None, []
    launch = None
    plan_path = os.path.join(root, "_raw", "wl_plan.json")
    if os.path.exists(plan_path):
        try:
            launch = dt.date.fromisoformat(load_json(plan_path).get("launch"))
        except (TypeError, ValueError):
            pass
    a = wlist.analyse(rows, today, launch, 30, 3.0)
    f = lambda v: "-" if v is None else fmt_n(v)
    body = ('<h2>Concorrenti e comparabili</h2><div class="card wrap"><table><thead><tr><th>Gioco</th><th>Ruolo</th><th class="n">Recensioni</th><th class="n">+7 giorni</th><th class="n">+30 giorni</th><th class="n">% positive</th><th>Uscita</th></tr></thead><tbody>'
            + "".join(f'<tr><td>{esc(g["name"])}</td><td>{esc(g["role"])}</td><td class="n">{f(g["reviews"])}</td><td class="n">{f(g["gain_7d"])}</td><td class="n">{f(g["gain_30d"])}</td><td class="n">{esc(g["pct_positive"] or "-")}</td><td>{esc(g["release"] or "-")}</td></tr>' for g in a["games"])
            + "</tbody></table><p class=\"note\">Dati pubblici di Steam. Le wishlist e le vendite degli altri giochi non sono pubbliche.</p></div>")
    return body, [(x["level"], f"{x['game']}: {x['text']}") for x in a["alerts"] if x["level"] != "INFO"]


def safe_href(u: str) -> str | None:
    u = (u or "").strip()
    return u if re.match(r"https?://[^\s\"'<>]+$", u) else None


def link(label: str, url: str) -> str:
    h = safe_href(url)
    return f'<a href="{esc(h)}" rel="noopener noreferrer">{esc(label)}</a>' if h else esc(label)


def creators_section(root: str):
    """creators.csv as a collapsible table: counts in the summary, every row inside. Only public data is shown (as written in the file)."""
    path = os.path.join(root, "creators.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    order = {"A": 0, "B": 1, "C": 2}
    rows.sort(key=lambda r: (order.get((r.get("priorita") or "").strip().upper(), 3), -(int(r["iscritti_follower"]) if (r.get("iscritti_follower") or "").isdigit() else 0)))
    pr = {k: sum(1 for r in rows if (r.get("priorita") or "").strip().upper() == k) for k in "ABC"}
    plat = {}
    for r in rows:
        plat[r.get("piattaforma") or "?"] = plat.get(r.get("piattaforma") or "?", 0) + 1
    cap = 500
    body = "".join(
        f'<tr><td>{esc(r.get("priorita"))}</td><td>{link(r.get("nome") or "", r.get("url") or "")}</td><td>{esc(r.get("piattaforma"))}</td><td>{esc(r.get("lingua"))}</td>'
        f'<td class="n">{esc(r.get("iscritti_follower"))}</td><td>{esc(r.get("segmento"))}</td><td>{esc(r.get("gioco_coperto"))}</td><td>{esc(r.get("perche"))}</td>'
        f'<td>{esc(r.get("contatto"))}</td><td>{link("video", r.get("url_video") or "") if safe_href(r.get("url_video") or "") else ""}</td></tr>' for r in rows[:cap])
    more = f'<p class="note">Mostrate le prime {cap} righe su {len(rows)}: il file completo è <code>creators.csv</code>.</p>' if len(rows) > cap else ""
    return (f'<h2>Creator</h2><details class="card"><summary><strong>{len(rows)} creator</strong><span class="count">priorità A {pr["A"]} · B {pr["B"]} · C {pr["C"]} · '
            + " · ".join(f"{esc(k)} {v}" for k, v in sorted(plat.items(), key=lambda kv: -kv[1])) + "</span></summary>"
            '<div class="wrap"><table><thead><tr><th>Pri.</th><th>Nome</th><th>Piattaforma</th><th>Lingua</th><th class="n">Follower</th><th>Segmento</th><th>Gioco coperto</th><th>Perché</th><th>Contatto</th><th>Video</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>{more}<p class="note">Solo contatti professionali pubblici. I follower di TikTok e Instagram vanno verificati a mano.</p></details>')


def full_game_section(fg: dict) -> str:
    gaps = "".join(f'<tr><td>{esc(g.get("area"))}</td><td>{esc(g.get("today"))}</td><td>{esc(g.get("target"))}</td><td>{esc(g.get("action"))}</td><td class="n">{esc(g.get("hours", ""))}</td></tr>' for g in fg.get("gaps", []))
    return (f'<h2>Beta oggi e gioco completo</h2><div class="card"><p>{esc(fg.get("summary", ""))}</p>'
            + (f'<div class="wrap"><table><thead><tr><th>Area</th><th>Beta oggi</th><th>Gioco completo</th><th>Cosa fare</th><th class="n">Ore</th></tr></thead><tbody>{gaps}</tbody></table></div>' if gaps else "")
            + '<p class="note">Analisi rapida del gioco completo sul piano, con confidenza bassa: serve a capire cosa migliorare adesso, non a prevederne l\'esito.</p></div>')


def steamdb_section(root: str):
    """What you read by hand on SteamDB (steamdb_assist.py add): latest values per game and the change since the previous record."""
    import steamdb_assist as sd
    rows = sd.read(os.path.join(root, "steamdb.csv"))
    if not rows:
        return None
    names = {}
    for fn, key in (("watchlist.csv", "appid"), ("comps.csv", "appid")):
        try:
            with open(os.path.join(root, fn), encoding="utf-8-sig", newline="") as f:
                names.update({r[key]: r.get("name") for r in csv.DictReader(f) if r.get(key) and r.get("name")})
        except OSError:
            pass
    by = {}
    for r in rows:
        by.setdefault(r["appid"], []).append(r)
    num = lambda r, k: (int(r[k]) if (r.get(k) or "").strip().lstrip("-").isdigit() else None)
    f = lambda v: "-" if v is None else fmt_n(v)
    body = []
    for aid, rs in sorted(by.items(), key=lambda kv: -(num(sorted(kv[1], key=lambda r: r["date"])[-1], "followers") or 0)):
        rs.sort(key=lambda r: r["date"])
        last, prev = rs[-1], rs[-2] if len(rs) > 1 else None
        d = "-" if not prev or num(last, "followers") is None or num(prev, "followers") is None else f"{num(last, 'followers') - num(prev, 'followers'):+,}".replace(",", ".")
        body.append(f'<tr><td>{esc(names.get(aid) or aid)}</td><td>{fmt_date(last["date"])}</td><td class="n">{f(num(last, "followers"))}</td><td class="n">{d}</td><td class="n">{f(num(last, "wishlist_rank"))}</td>'
                    f'<td class="n">{f(num(last, "peak_24h"))}</td><td class="n">{f(num(last, "peak_all_time"))}</td><td class="n">{esc(last.get("lowest_price") or "-")}</td></tr>')
    return ('<h2>SteamDB: numeri letti a mano</h2><div class="card wrap"><table><thead><tr><th>Gioco</th><th>Letto il</th><th class="n">Follower</th><th class="n">Variazione</th><th class="n">Posizione wishlist</th><th class="n">Picco 24 h</th>'
            '<th class="n">Picco assoluto</th><th class="n">Prezzo minimo</th></tr></thead><tbody>' + "".join(body)
            + '</tbody></table><p class="note">Registrati da una lettura manuale di SteamDB (nessuno scraping). La posizione tra i più desiderati non è il numero di wishlist: quello degli altri giochi non è pubblico.</p></div>')


def window_section(root: str) -> str | None:
    w = load_json(os.path.join(root, "_raw", "window.json")) if os.path.exists(os.path.join(root, "_raw", "window.json")) else None
    if not w or not w.get("weeks"):
        return None
    ch = w["chosen"]
    kind, word = {"libera": ("pass", "Settimana libera"), "nella media": ("warn", "Settimana nella media"), "affollata": ("fail", "Settimana affollata")}.get(ch["verdict"], ("info", ch["verdict"]))
    byw = {k["week"]: k for k in w["weeks"]}
    near = lambda wk: ", ".join(f'{esc(n["name"])} ({esc(n["date"])})' for n in byw[wk]["items"][:3]) or "niente in lista"
    best = "".join(f'<tr><td>{fmt_date(b["week"])}</td><td class="n">{b["score"]:g}</td><td>{near(b["week"])}</td></tr>' for b in w["best"])
    weigh = "".join(f'<li><span>{esc(n["name"])}: {esc(LABEL.get(n["kind"], n["kind"]))}, {fmt_date(n["date"])}, peso {n["weight"]:g} × {n["factor"]} = <strong>{n["points"]:g}</strong></span></li>' for n in byw[ch["week"]]["items"])
    nc = "".join(f"<li>{esc(x)}</li>" for x in w.get("not_counted", []))
    return (f'<h2>Finestra di lancio</h2><div class="card"><p>{state(kind, word)} <span class="sub">per il {fmt_date(w["launch"])} (punteggio {ch["score"]:g}; il {ch["quieter_weeks_pct"]}% delle settimane candidate è più tranquillo)</span></p>'
            + (f'<h3>Cosa pesa sulla tua settimana</h3><ul class="clean">{weigh}</ul>' if weigh else "")
            + f'<h3>Le 5 settimane più tranquille</h3><div class="wrap"><table><thead><tr><th>Settimana dal</th><th class="n">Punteggio</th><th>Cosa c\'è vicino</th></tr></thead><tbody>{best}</tbody></table></div>'
            + (f'<details><summary>Voci non conteggiate</summary><ul>{nc}</ul></details>' if nc else "")
            + f'<p class="note">Conta le {w.get("counted", 0)} voci in lista: una settimana libera qui non è libera nel mondo. Il punteggio confronta le settimane tra loro, non prevede le vendite.</p></div>')


def waves_section(root: str) -> str | None:
    """Per-wave reports written by fg_waves.py (metrics and delta), newest last, plus the timeline."""
    d = os.path.join(root, "fg")
    files = []
    wd = os.path.join(d, "waves")
    if os.path.isdir(wd):
        files += sorted((f for f in os.listdir(wd) if re.match(r"w\d+-(metrics|delta)\.md$", f)), key=lambda f: (int(re.match(r"w(\d+)", f).group(1)), "delta" in f))
    parts = []
    for f in files:
        m = re.match(r"w(\d+)-(metrics|delta)", f)
        parts.append(f'<details class="card doc"><summary><strong>Ondata {int(m.group(1))}: {"metriche" if m.group(2) == "metrics" else "cosa è cambiato rispetto alla precedente"}</strong></summary>'
                     f'{md_to_html(open(os.path.join(wd, f), encoding="utf-8").read())}</details>')
    return ("<h2>Ondate del focus group</h2>" + "".join(parts)) if parts else None


def key_tiles(st: dict, wl_a, fg_rows, plan: dict, econ, today: dt.date, hide: set) -> list:
    """The key numbers shown on top of STATUS.html and REPORT.html: (label, value, note)."""
    tiles = []
    if wl_a and "current" in wl_a:
        vel = wl_a.get("velocity_4w")
        tiles.append(("Wishlist", fmt_n(wl_a["current"]), f"{'+' if vel and vel > 0 else ''}{fmt_n(vel)} a settimana (ultime 4)" if vel is not None else f"dato del {fmt_date(wl_a['last_record'])}"))
        if "days_to_launch" in wl_a:
            tiles.append(("Giorni al lancio", fmt_n(wl_a["days_to_launch"]), fmt_date(wl_a["launch"])))
    if fg_rows:
        last, prev = fg_rows[-1], fg_rows[-2] if len(fg_rows) > 1 else None
        tiles.append(("Punteggio focus group", last["score"], f"ondata {last['wave']}" + (f", {float(last['score']) - float(prev['score']):+.1f} rispetto alla precedente" if prev else "")))
    if plan["phases"] and "steps" not in hide:
        sm = ps.summary(plan, today)
        tiles.append(("Passi fatti", f"{sm['done']}/{sm['total']}", f"{sm['overdue']} in ritardo" if sm["overdue"] else "nessuno in ritardo"))
    if econ:
        tiles.append(("Break-even", fmt_n(econ["breakeven"]["copies_with_time"]), f"copie (netto per copia {econ['net_per_copy']:.2f})"))
    gates = st.get("gates") or {}
    if gates:
        tiles.append(("Gate superati", f"{sum(1 for g in gates.values() if g.get('state') == 'pass')}/{len(gates)}", "Go/No-Go prima di Steam Direct"))
    for k in st.get("key_numbers", []):
        tiles.append((k.get("label", ""), k.get("value", ""), k.get("note", "")))
    return tiles


def build(root: str, audience: str, include: list[str], exclude: list[str], hide: set[str], today: dt.date) -> str:
    st = load_json(os.path.join(root, "status.json")) if os.path.exists(os.path.join(root, "status.json")) else {}
    hide = set(hide) | HIDE_BY_AUDIENCE[audience]
    wl_a, wl_svg = wishlist_section(root, today)
    fg_rows, fg_svg = timeline_section(root)
    econ = load_json(os.path.join(root, "_raw", "econ.json")) if os.path.exists(os.path.join(root, "_raw", "econ.json")) and "economics" not in hide else None
    cal_path = os.path.join(root, "calendar.md")
    cal_md = open(cal_path, encoding="utf-8").read() if os.path.exists(cal_path) else ""
    plan = ps.parse(cal_md) if cal_md else dict(phases=[])
    kit = load_json(os.path.join(root, "store_kit.json")) if os.path.exists(os.path.join(root, "store_kit.json")) and "storekit" not in hide else None
    cont_html, cont_alerts = (None, []) if "contingencies" in hide else contingency_section(root, today)
    watch_html, watch_alerts = (None, []) if "watchlist" in hide else watch_section(root, today)
    sec = []
    product = st.get("product") or {}
    v = st.get("verdict") or {}
    if v:
        kind, word = LIGHT.get(str(v.get("color", "")).lower(), ("info", str(v.get("color", "n/d"))))
        risks = "".join(f"<li>{state('warn', f'Rischio {k}')}<span>{esc(r)}</span></li>" for k, r in enumerate(v.get("risks", [])[:3], 1))
        sec.append(f'<section class="card verdict"><div>{ICONS[kind][0]}</div><div><div class="big">Verdetto: {esc(word)}{" (provvisorio)" if v.get("provisional") else ""}</div>'
                   f'<p>{esc(v.get("summary", ""))}</p>' + (f'<p class="sub">Probabilità stimata di recuperare i costi: {esc(v["probability"])}</p>' if v.get("probability") else "")
                   + (f'<ul class="clean">{risks}</ul>' if risks else "")
                   + ('<div class="gates">' + "".join(f'<span>{state({"pass": "pass", "fail": "fail", "pending": "pending"}.get(g.get("state"), "na"), GATE_NAMES.get(k, "Gate " + k))}</span>' for k, g in (st.get("gates") or {}).items()) + "</div>" if st.get("gates") else "")
                   + "</div></section>")
    if plan["phases"] and "steps" not in hide:
        sec.append(now_block(plan, today))
    it = st.get("intentions") or {}
    if it and "intentions" not in hide:
        rows = "".join(f'<tr><td>{esc(d.get("topic"))}</td><td>{esc(d.get("choice"))}</td><td>{esc(d.get("why", ""))}</td></tr>' for d in it.get("decisions", []))
        sec.append(f'<h2>Profilo decisionale</h2><div class="card"><p>{esc(it.get("summary", ""))}</p>' + (f'<div class="wrap"><table><thead><tr><th>Tema</th><th>Scelta</th><th>Perché</th></tr></thead><tbody>{rows}</tbody></table></div>' if rows else "") + "</div>")
    tiles = key_tiles(st, wl_a, fg_rows, plan, econ, today, hide)
    gates = st.get("gates") or {}
    if tiles:
        sec.append('<h2>Numeri chiave</h2><div class="grid g4">' + "".join(f'<div class="card tile"><div class="l">{esc(l)}</div><div class="v">{esc(val)}</div><div class="d">{esc(d)}</div></div>' for l, val, d in tiles) + "</div>")
    alerts = [(x["level"], x["text"]) for x in (wl_a or {}).get("alerts", [])] + cont_alerts + watch_alerts
    if alerts:
        icon = {"ALARM": ("fail", "Allarme"), "ATTENZIONE": ("warn", "Attenzione"), "INFO": ("info", "Info")}
        sec.append('<h2>Alert</h2><div class="card"><ul class="clean">' + "".join(f"<li>{state(*icon[lv])}<span>{esc(t)}</span></li>" for lv, t in sorted(alerts, key=lambda x: ["ALARM", "ATTENZIONE", "INFO"].index(x[0]))) + "</ul></div>")
    if plan["phases"] and "steps" not in hide:
        sec.append(steps_section(plan, today))
    if wl_svg or fg_svg:
        sec.append("<h2>Andamento</h2><div class=\"grid\">")
        if wl_svg:
            sec.append(f'<div class="card"><h3>Wishlist contro gli scenari</h3><div class="legend"><span><i style="border-color:var(--s1)"></i>Registrate</span><span><i style="border-color:var(--muted)"></i>Percorso degli scenari (lineare)</span></div>{wl_svg}'
                       '<p class="note">Wishlist inserite a mano da Steamworks. I percorsi sono lineari: semplificazione, i picchi (festival, lancio) non sono previsti.</p></div>')
        if fg_svg:
            sec.append(f'<div class="card"><h3>Focus group simulato, per ondata</h3>{fg_svg}<p class="note">Panel simulato con gli stessi tester: ordina i problemi, non prevede le vendite.</p></div>')
        sec.append("</div>")
    if "charts" not in hide:
        gs = rc.groups(root, today)
        if audience == "publisher":
            gs = [g for g in gs if g["key"] in ("fg", "market", "reviews", "window")]
        if gs:
            sec.append("<h2>Quadro d'insieme</h2>" + rc.render(gs))
    if gates:
        names = GATE_NAMES
        sec.append('<h2>Cancelli Go / No-Go</h2><div class="grid g4">' + "".join(
            f'<div class="card"><div>{state({"pass": "pass", "fail": "fail", "pending": "pending"}.get(g.get("state"), "na"))}</div><h3>{esc(names.get(k, "Gate " + k))}</h3><p class="note">{esc(g.get("note", ""))}</p></div>'
            for k, g in gates.items()) + "</div>")
    if cal_md and "calendar" not in hide:
        rest = (plan.get("before", "") + "\n" + plan.get("after", "")) if plan["phases"] else cal_md
        if rest.strip():
            sec.append(f'<h2>Date fisse e piano a ritroso</h2><details class="card doc" open><summary><strong>calendar.md</strong></summary>{md_to_html(rest)}</details>')
    if kit:
        sec.append(kit_section(kit))
    if "window" not in hide:
        wsec = window_section(root)
        if wsec:
            sec.append(wsec)
    if cont_html:
        sec.append(cont_html)
    if watch_html:
        sec.append(watch_html)
    if "steamdb" not in hide:
        sdb = steamdb_section(root)
        if sdb:
            sec.append(sdb)
    if "creators" not in hide:
        c = creators_section(root)
        if c:
            sec.append(c)
    if st.get("full_game") and "fullgame" not in hide:
        sec.append(full_game_section(st["full_game"]))
    todos, done, hours = read_todos(root)
    if todos and "todo" not in hide:
        sec.append(f'<h2>Prossime azioni</h2><div class="card"><p class="sub">{len(todos)} aperte, {done} chiuse, circa {hours:.0f} ore residue.</p><div class="wrap"><table><thead><tr><th>Azione</th><th>Scadenza</th><th class="n">Ore</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(t["action"])}</td><td>{esc(t["due"])}</td><td class="n">{esc(t["hours"])}</td></tr>' for t in todos[:10]) + "</tbody></table></div></div>")
    if econ:
        sec.append('<h2>Economia</h2><div class="card wrap"><table><thead><tr><th>Scenario</th><th class="n">Wishlist</th><th class="n">Copie</th><th class="n">Netto</th><th class="n">Utile (cassa)</th></tr></thead><tbody>' + "".join(
            f'<tr><td>{esc(s["name"])}</td><td class="n">{fmt_n(s["wishlists"])}</td><td class="n">{fmt_n(s["copies"])}</td><td class="n">{fmt_n(s["net"])}</td><td class="n">{fmt_n(s["profit_cash"])}</td></tr>' for s in econ["scenarios"])
            + f'</tbody></table><p class="note">Netto per copia {econ["net_per_copy"]:.2f}; aliquote e conversioni sono ipotesi dichiarate nel piano, da verificare.</p></div>')
    if "fgwaves" not in hide:
        wv = waves_section(root)
        if wv:
            sec.append(wv)
    stems = [x for x in (include or AUDIENCES[audience]) if x not in exclude]
    docs = []
    for stem in stems:
        p = os.path.join(root, f"{stem}.md")
        if os.path.exists(p):
            docs.append(f'<details class="card doc"><summary><strong>{esc(DOCS.get(stem, stem))}</strong></summary>{md_to_html(open(p, encoding="utf-8").read())}</details>')
    if docs:
        sec.append("<h2>Documenti</h2>" + "".join(docs))
    body_html, heads, own_ids = [], [], []
    for chunk in sec:   # every <h2> gets an anchor and a chip in the sticky index
        mine = set()

        def anchor(m):
            heads.append(re.sub(r"<[^>]+>", "", m.group(1)))
            mine.add(f"sec{len(heads)}")
            return f'<h2 id="sec{len(heads)}">{m.group(1)}</h2>'
        body_html.append(re.sub(r"<h2>(.*?)</h2>", anchor, chunk))
        own_ids.append(mine)
    anchors = gl.anchors_for([(f"sec{i}", h) for i, h in enumerate(heads, 1)])
    used: set = set()
    sec = [gl.enrich(c, anchors, own, used) for c, own in zip(body_html, own_ids)]   # plain-Italian tooltips and links to the section that deals with the thing
    glo = gl.glossary_html(used)
    toc = '<nav class="toc" aria-label="Sezioni">' + "".join(f'<a href="#sec{i}">{h}</a>' for i, h in enumerate(heads, 1)) + "</nav>" if len(heads) > 3 else ""
    name = st.get("game") or os.path.basename(os.path.dirname(os.path.abspath(root))) or "Progetto"
    label = {"private": "Uso interno", "partner": "Per i soci", "publisher": "Per il publisher"}[audience]
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stato del lancio, {esc(name)}</title>'
            f'<style>{CSS}</style></head><body><main><div class="top"><div><h1>{esc(name)}: stato del lancio</h1><p class="sub">Aggiornato il {fmt_date(st.get("updated") or today.isoformat())} · {esc(label)}'
            f'{" · modalità " + esc(st["mode"]) if st.get("mode") else ""}{" · valutato come: " + esc(product.get("label") or product.get("kind")) if product.get("kind") or product.get("label") else ""}</p><p class="sub">Questo è il <strong>cruscotto</strong>: cosa fare, numeri, pagine da copiare, piani. Il testo completo del report, con i grafici accanto a ogni sezione, è in <a href="REPORT.html">REPORT.html</a>.</p></div><button class="theme" id="theme" type="button">Tema chiaro/scuro</button></div>'
            + toc + "".join(sec) + glo + f'<footer class="note">Pagina generata da <code>status_page.py</code> il {today.isoformat()} da file locali, senza richieste di rete. Il focus group è simulato: non è un dato di mercato. '
            f'Cifre con fonte nei documenti; ciò che è etichettato [DA VERIFICARE] resta da verificare.</footer></main><script>{JS}{gl.JS}</script></body></html>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("--audience", default="private", choices=list(AUDIENCES))
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
