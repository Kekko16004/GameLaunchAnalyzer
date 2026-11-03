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
  launch/_raw/publisher_scout.json   publisher shortlist by tier + with/without comparison (publisher_scout.py); status.json -> publisher.question
  launch/_raw/social_plan.json, social_learn.json, reddit_trends.json   social plan, what works for this game, Reddit trends (social_content.py, reddit_trends.py)
  launch/trailer/<v>/kit.json   Trailer tab: copyable master + negative prompt, storyboard cards, competitor trailers, QA (trailer_kit.py build)
  honest odds                one card per decision with its basis and cross-check (honest_odds.py), in Riepilogo
  status.json -> roadmap     key milestones (closed test, Steam Direct, Coming Soon, free beta, demo, Next Fest, launch, 1.0): see calendar_view.py
  Calendario tab             every dated item of calendar.md, TODO.md, Steam and online events, waves (calendar_view.py); every URL is a link (weblinks.py)
  launch/fg/waves/wNN-metrics.md, wNN-delta.md   per-wave reports of the focus group (fg_waves.py)
Layout: a sticky bar of TABS (Riepilogo · Gioco e test · Marketing e social · Trailer · Piano e soldi · Calendario · Mercato reale · Documenti; pure CSS + a few lines
of inline JS, the last tab is remembered in localStorage), a wide page (up to 1400 px) that still works at 390 px. Riepilogo holds
the verdict with the Go/No-Go gates at a glance, the "Adesso" box (whose turn it is), key numbers, alerts and trends.
Live state: launch/issue_status.json (the owner's decision on every focus-group issue, see criticita.py) is shown as a badge with its
note wherever issues appear (criticalities per wave and per gate, evolution matrix, top-issues chart, convergence table of the
documents, verdict risks, real-review themes) and splits "Da fare adesso" from "Già deciso". TODO.md is read live (todo_track.py
marks lines done): open / done per section, and a warning when it was not updated after the latest wave or decision.
Marketing e social opens with marketing_glance.py (what to do now, channels, numbers against the real cases, the flop traffic light);
the rest of the tab is folded. Charts ("Quadro d'insieme") come from report_charts.py; the same charts are exported as .svg for the Markdown reports by charts_export.py.
  launch/criticita.csv       criticalities from other sources (real test, reviews, pre-mortem): criticita.py add
  launch/qa.json             your questions and the answers given (qa.py add); status.json -> qa and critiques_by_wave are read too
  launch/issue_status.json   the owner's decisions on the issues (aperto, in_lavorazione, da_verificare, risolto, pianificato, accettato, non_problema)
  status.json -> issue_aliases {issue key: [regex]}   lets a verdict risk or a row of a document table point to an issue key
Anything missing is simply left out.

Sharing: the page contains strategy. --audience picks what goes in (default private):
  private    everything, including creators, community, legal/fiscal
  partner    everything except creators, community and legal/fiscal documents
  publisher  verdict, numbers, charts, gates, calendar dates, store pages, positioning, platform, focus group;
             no steps, economics, TODO, contingencies, competitors, creators, decision profile or full-game analysis
Add/remove documents with --include / --exclude (file stems such as 03-pricing) and sections with
--hide economics,todo,calendar,steps,storekit,contingencies,watchlist,intentions,creators,fullgame,charts,steamdb,fgwaves,window,critiques,qa,roadmap,
publisher,social,odds,trailer
(calendar also hides the Calendario tab).
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
import glob
import re
from common import load_json, log
import metrics_track as mt
import charts as ch
import criticita as cr
import market_page as mp
import glossary as gl
import qa as qamod
import plan_steps as ps
import report_charts as rc
import todo_track as tt
from launch_window import LABEL
import store_kit as sk
import watchlist as wlist
import wl_track as wl
import calendar_view as cv
import weblinks
import trailer_kit as tk
import marketing_glance as mg

MONTHS = "gen feb mar apr mag giu lug ago set ott nov dic".split()
DOCS = {  # stem -> title
    "REPORT": "Report completo", "00-intenzioni": "Intenzioni e decisioni", "04b-store-copy": "Testi dello store e trailer", "05d-contingenze": "Piani di contingenza (se… allora)", "00-brief": "Brief del progetto", "01b-positioning": "Posizionamento", "01-dev": "Audit del prodotto",
    "01c-full-game": "Gioco completo: analisi rapida", "02-platform": "Piattaforme, demo e gate", "03-pricing": "Prezzo ed economia", "05-focusgroup": "Focus group", "05c-premortem": "Pre-mortem",
    "04-clips": "Hook e clip", "03-pricing-calc": "Calcolo economico", "05a-critiche-simulate": "Critiche simulate", "05b-critiche-reali": "Critiche reali (con fonti)", "window": "Finestra di lancio: concorrenti",
    "06-creators": "Creator", "07-community": "Community e test reale", "08-brand-legal": "Brand, legale e fiscale",
    "publisher-scout": "Publisher: lista per fasce e confronto con/senza", "social-plan": "Piano social (post e ganci)", "clips": "Clip da fare (storyboard)", "case-studies": "Casi reali: cosa hanno fatto giochi come il nostro"}
AUDIENCES = {
    "private": list(DOCS),
    "partner": ["REPORT", "00-intenzioni", "01b-positioning", "01c-full-game", "02-platform", "03-pricing", "03-pricing-calc", "04-clips", "05-focusgroup", "05a-critiche-simulate", "05b-critiche-reali", "05c-premortem", "05d-contingenze", "window", "publisher-scout", "social-plan", "clips", "case-studies"],
    "publisher": ["01b-positioning", "02-platform", "05-focusgroup"]}
HIDE_BY_AUDIENCE = {"private": set(), "partner": set(), "publisher": {"economics", "todo", "contingencies", "steps", "watchlist", "intentions", "creators", "fullgame", "steamdb", "fgwaves", "critiques", "qa", "publisher", "social", "odds", "trailer"}}

CSS = """
:root{color-scheme:light;--bg:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--goodtext:#006300}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--goodtext:#0ca30c}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--goodtext:#0ca30c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1400px;margin:0 auto;padding:24px clamp(16px,3vw,40px) 64px;overflow-wrap:break-word}.card{min-width:0}h1{font-size:1.6rem;margin:0 0 4px}h2{font-size:1.15rem;margin:36px 0 12px}h3{font-size:1rem;margin:20px 0 8px}
.sub{color:var(--ink2);margin:0 0 4px}.note{color:var(--muted);font-size:.85rem}.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
button.theme{background:var(--surface);color:var(--ink2);border:1px solid var(--ring);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit;font-size:.85rem}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px}.grid{display:grid;gap:12px}.g4{grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr))}
.verdict{display:flex;gap:16px;align-items:flex-start}.verdict>div:first-child svg{width:40px;height:40px}.verdict>div:last-child{min-width:0}.verdict .big{font-size:1.25rem;font-weight:600}.tile .v{font-size:1.9rem;font-weight:600;line-height:1.1}.tile .l{color:var(--ink2);font-size:.85rem}.tile .d{color:var(--ink2);font-size:.85rem;margin-top:4px}
.state{display:inline-flex;align-items:center;gap:6px;font-weight:600;white-space:nowrap;flex:none}.state svg{flex:none}.g2{grid-template-columns:repeat(auto-fit,minmax(min(380px,100%),1fr))}ul.clean{list-style:none;margin:0;padding:0}ul.clean li{display:flex;gap:8px;align-items:flex-start;padding:6px 0;border-top:1px solid var(--grid)}ul.clean li:first-child{border-top:0}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--grid);vertical-align:top;overflow-wrap:normal;word-break:normal}th{color:var(--ink2);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}td.nw,th.nw{white-space:nowrap}.doc td{min-width:8em}.doc td:first-child{min-width:11em}.doc td a{overflow-wrap:anywhere}
.ptab td:first-child{min-width:12em}.ptab td:nth-child(3),.ptab td:nth-child(4){min-width:16em}table.ours td:first-child{min-width:12em}table.ours td:nth-child(2){min-width:18em}
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
.gh{font-size:1.05rem;margin:26px 0 2px}.toc{display:flex;gap:8px;flex-wrap:wrap;padding:4px 0 8px;margin:4px 0 0}.toc a{flex:none;border:1px solid var(--ring);border-radius:999px;padding:3px 12px;font-size:.85rem;text-decoration:none;color:var(--ink2);background:var(--surface)}.toc a:hover,.toc a:focus{border-color:var(--s1);color:var(--ink)}
h2{scroll-margin-top:72px}.gates{display:flex;gap:6px 16px;flex-wrap:wrap;margin:10px 0 2px;font-size:.9rem}
.tabs{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;gap:4px;overflow-x:auto;padding:10px 0 0;margin:14px 0 0;border-bottom:1px solid var(--axis);scrollbar-width:thin}
.tabs button{flex:none;display:inline-flex;align-items:center;gap:6px;background:transparent;color:var(--ink2);border:1px solid transparent;border-bottom:0;border-radius:10px 10px 0 0;padding:8px 14px;cursor:pointer;font:inherit;font-size:.95rem;margin-bottom:-1px}
.tabs button[aria-selected="true"]{background:var(--surface);color:var(--ink);border-color:var(--axis);font-weight:600;border-bottom:1px solid var(--surface)}.tabs button:focus-visible{outline:2px solid var(--s1);outline-offset:-2px}.tabs svg{flex:none}
.tabs .cnt{font-size:.75rem;font-weight:600;border-radius:999px;padding:0 7px;border:1px solid var(--warn);color:var(--ink)}[role=tabpanel]{padding-top:4px}[role=tabpanel][hidden]{display:none}
.risk-own{display:inline-flex;gap:6px;flex-wrap:wrap;margin-left:6px}.todo-sec{margin-top:10px}.todo-sec summary{font-weight:600}.todo-l{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;padding:8px 0;border-top:1px solid var(--grid)}.todo-l .meta{grid-column:2;color:var(--ink2);font-size:.85rem;display:flex;gap:12px;flex-wrap:wrap}
.todo-l.done .txt{color:var(--muted);text-decoration:line-through;text-decoration-color:var(--axis)}.wgrid{display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr));margin:8px 0}.wgrid .tile .v{font-size:1.4rem}
.chart svg{max-width:860px}.stage{display:inline-block;border-radius:6px;padding:1px 8px;font-size:.8rem;font-weight:600;border:1px solid var(--s1);color:var(--ink)}.stage.full{border-color:var(--s2)}
@media print{.tabs,.top button{display:none}body{background:#fff}[role=tabpanel][hidden]{display:block}}.over{color:var(--crit);font-weight:600}.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink2);font-size:.85rem;margin:6px 0}.legend i{display:inline-block;width:18px;height:0;border-top:2px solid;vertical-align:middle;margin-right:6px}
""" + ch.CHART_CSS + gl.CSS + cr.CSS + qamod.CSS
# Visual layer (2026-10): typography, spacing, cards, consistent badges, sticky blurred tabs, phone width without horizontal scroll.
# Appended after the base CSS above, same class names: everything that existed keeps working.
CSS_POLISH = """
:root{--bg:#f5f5f2;--surface:#ffffff;--surface2:#f0efeb;--ink:#141413;--ink2:#4e4d49;--muted:#85837c;--grid:#e6e5df;--axis:#cbc9bf;--ring:rgba(20,20,19,.09);
--shadow:0 1px 2px rgba(20,20,19,.04),0 4px 16px rgba(20,20,19,.05);--radius:14px}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--bg:#0e0f11;--surface:#17181b;--surface2:#1e1f23;--ink:#f3f2ee;--ink2:#c5c3bb;--muted:#8f8d86;--grid:#2a2b2f;--axis:#3b3c41;--ring:rgba(255,255,255,.09);--shadow:0 1px 2px rgba(0,0,0,.3),0 6px 20px rgba(0,0,0,.25)}}
:root[data-theme="dark"]{--bg:#0e0f11;--surface:#17181b;--surface2:#1e1f23;--ink:#f3f2ee;--ink2:#c5c3bb;--muted:#8f8d86;--grid:#2a2b2f;--axis:#3b3c41;--ring:rgba(255,255,255,.09);--shadow:0 1px 2px rgba(0,0,0,.3),0 6px 20px rgba(0,0,0,.25)}
html{-webkit-text-size-adjust:100%}body{font:15.5px/1.55 "Inter","Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,Roboto,sans-serif;-webkit-font-smoothing:antialiased;font-feature-settings:"cv11","ss01"}
main{overflow-x:clip}h1{font-size:clamp(1.4rem,2.6vw,2rem);letter-spacing:-.02em;line-height:1.15}
h2{font-size:1.2rem;letter-spacing:-.01em;margin:40px 0 14px;display:flex;align-items:center;gap:10px}h2::before{content:"";width:4px;height:1.05em;border-radius:2px;background:var(--s1);flex:none}
h3{letter-spacing:-.005em}.sub{line-height:1.5}
.card{border-radius:var(--radius);padding:18px;box-shadow:var(--shadow);border-color:var(--ring)}.card .card{box-shadow:none}
details>summary{list-style:none;display:flex;align-items:center;gap:8px;flex-wrap:wrap}details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"";width:7px;height:7px;border-right:2px solid var(--muted);border-bottom:2px solid var(--muted);transform:rotate(-45deg);transition:transform .15s;flex:none;margin:0 3px}
details[open]>summary::before{transform:rotate(45deg)}details.card>summary{font-size:.98rem}
.top{flex-wrap:wrap;padding:6px 0 2px}button.theme{border-radius:999px;padding:7px 14px;box-shadow:var(--shadow)}
.tabs{background:color-mix(in srgb,var(--bg) 82%,transparent);backdrop-filter:saturate(1.4) blur(10px);-webkit-backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--grid);gap:2px;padding:10px 0 8px;margin:18px 0 0}
.tabs button{border-radius:999px;border:1px solid transparent;padding:7px 14px;margin:0;font-size:.92rem}.tabs button:hover{background:var(--surface2);color:var(--ink)}
.tabs button[aria-selected="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink);border-bottom:1px solid var(--ink)}
.tabs .cnt{border:0;background:var(--warn);color:#141413;padding:0 7px;line-height:1.5}.tabs .cnt.late{background:var(--crit);color:#fff}
.toc{gap:6px;padding:6px 0 4px}.toc a{background:var(--surface);box-shadow:var(--shadow);border-color:var(--ring)}
.tile{display:flex;flex-direction:column;gap:2px}.tile .l{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}.tile .v{font-size:1.75rem;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.tile .d{font-size:.82rem;line-height:1.4}.grid{gap:14px}
table{font-size:.88rem}th{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);background:var(--surface2)}th:first-child{border-top-left-radius:8px}th:last-child{border-top-right-radius:8px}
tbody tr:hover td{background:color-mix(in srgb,var(--s1) 4%,transparent)}.wrap{-webkit-overflow-scrolling:touch}
.chip,.mbadge,.stage,.tagx,.due,.owner{border-radius:999px;font-size:.78rem;line-height:1.5}
.state{font-size:.88rem}.state svg{width:16px;height:16px}
.progress{height:8px;background:var(--surface2)}.progress span{background:linear-gradient(90deg,var(--s3),var(--s1))}
a{color:var(--s1);text-underline-offset:2px}a.ext{text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--s1) 40%,transparent);overflow-wrap:anywhere}
a.ext::after{content:"↗";font-size:.75em;margin-left:2px;opacity:.7}a.ext:hover{border-bottom-color:var(--s1)}
/* steps and dense event lists */
ol.steps{margin-top:4px}.step{grid-template-columns:2.1em minmax(0,1fr);gap:3px 12px;padding:12px 4px;border-top:1px solid var(--grid);border-radius:8px}
.step .n{grid-row:span 4;width:2em;height:2em;border-radius:50%;display:grid;place-items:center;font-size:.78rem;font-weight:600;background:var(--surface2);color:var(--ink2)}
.step[data-state="done"] .n{background:color-mix(in srgb,var(--good) 18%,transparent);color:var(--goodtext)}.step[data-state="overdue"] .n{background:color-mix(in srgb,var(--crit) 16%,transparent);color:var(--crit)}
.step .meta{gap:6px 8px}.owner{font-weight:600;padding:0 9px;border:1px solid var(--ring);background:var(--surface)}.owner.o-me{border-color:#e5732f}.owner.o-claude{border-color:#2a78d6}.owner.o-both{border-color:#159a6c}
.due{padding:0 9px;border:1px solid var(--ring);color:var(--ink2);font-variant-numeric:tabular-nums}.due.soon{border-color:var(--warn);color:var(--ink)}.due.late{border-color:var(--crit);color:var(--crit);font-weight:600}
.step .stext,.step .stags,.step .snext,.step .sdet,.step .notes{grid-column:2;min-width:0}.stitle{font-weight:600}.stail{color:var(--ink2)}.step .stext strong{font-weight:600}
.stags{display:flex;flex-wrap:wrap;gap:5px;margin-top:3px}.tagx{border:1px solid var(--ring);background:var(--surface2);padding:0 9px;color:var(--ink2);max-width:100%;overflow:hidden;text-overflow:ellipsis}
.tagx b{font-weight:600;color:var(--ink);margin-right:3px}.tagx.top{border-color:#f5b400;background:color-mix(in srgb,#f5b400 14%,transparent);color:var(--ink);font-weight:600}.tagx.lnk{background:transparent}
.snext{font-size:.9rem;color:var(--ink);background:color-mix(in srgb,var(--s1) 7%,transparent);border-radius:8px;padding:5px 10px;margin-top:4px}
.sdet{margin-top:2px}.sdet summary{font-size:.82rem;color:var(--muted)}.sdet .notes{margin-top:4px}
.step.flash{background:color-mix(in srgb,var(--s1) 12%,transparent);transition:background .4s}
.todo-l{padding:10px 2px}.todo-l .meta{gap:6px 12px}
.hero{box-shadow:var(--shadow)}.hero .big{font-size:1.35rem;letter-spacing:-.01em}
@media (max-width:700px){body{font-size:15px}main{padding:16px 14px 56px}.card{padding:14px}h2{margin:30px 0 10px;font-size:1.1rem}.tile .v{font-size:1.45rem}
.g4{grid-template-columns:repeat(2,minmax(0,1fr))}.g2{grid-template-columns:1fr}.tabs button{padding:6px 11px;font-size:.88rem}.verdict{flex-direction:column}
.doc td,.doc td:first-child,.ptab td:first-child,.ptab td:nth-child(3),.ptab td:nth-child(4),table.ours td:first-child,table.ours td:nth-child(2){min-width:7em}
.step{grid-template-columns:1.9em minmax(0,1fr);gap:3px 9px}pre,pre.val{max-width:100%}}
@media (max-width:700px){.top{position:relative;padding-right:84px}button.theme{position:absolute;top:4px;right:0;padding:5px 11px;font-size:.8rem}.top .sub+.sub{display:none}}
@media (max-width:420px){.g4{grid-template-columns:1fr}}
"""
# Clarity layer (2026-11): one token set (paper, ink, 2 accents, 3 status colours), one type scale, flat hairline cards,
# status colours that mean the same everywhere (green done/ok, orange in progress, red to do/problem), theme saved, print-friendly.
CSS_V3 = """
:root{--bg:#f6f5f1;--surface:#ffffff;--surface2:#efede7;--ink:#1c1b18;--ink2:#4f4d47;--muted:#7d7a72;--grid:#e4e2da;--rule:#e4e2da;--axis:#c9c6bb;--ring:rgba(28,27,24,.10);
--acc:#2b67c6;--acc2:#c8622a;--acc-soft:#e6eefa;--s1:var(--acc);--good:#1e9a52;--goodtext:#14743d;--warn:#e38b00;--crit:#cf3a3a;
--shadow:0 1px 0 rgba(28,27,24,.03);--radius:12px;--fs-0:.8125rem;--fs-1:.9375rem;--fs-2:1.0625rem;--fs-3:1.3125rem;--fs-4:1.75rem}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--bg:#121315;--surface:#1a1b1e;--surface2:#232428;--ink:#efeee9;--ink2:#c2c0b8;--muted:#8e8c85;--grid:#2c2d31;--rule:#2c2d31;--axis:#3d3e43;--ring:rgba(255,255,255,.09);
--acc:#6a9ef0;--acc2:#ee8a4e;--acc-soft:#1f2b3f;--good:#3cc275;--goodtext:#5fd38f;--warn:#f0a32a;--crit:#ef6060;--shadow:none}}
:root[data-theme="dark"]{--bg:#121315;--surface:#1a1b1e;--surface2:#232428;--ink:#efeee9;--ink2:#c2c0b8;--muted:#8e8c85;--grid:#2c2d31;--rule:#2c2d31;--axis:#3d3e43;--ring:rgba(255,255,255,.09);
--acc:#6a9ef0;--acc2:#ee8a4e;--acc-soft:#1f2b3f;--good:#3cc275;--goodtext:#5fd38f;--warn:#f0a32a;--crit:#ef6060;--shadow:none}
html,body{overflow-x:clip}body{font-family:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,Roboto,sans-serif;font-size:var(--fs-1);line-height:1.6;background:var(--bg);color:var(--ink)}
h1{font-size:var(--fs-4);font-weight:700}h2{font-size:var(--fs-3);font-weight:650;margin:44px 0 14px}h2::before{background:var(--acc)}h3{font-size:var(--fs-2);font-weight:600}
.sub,.note,.tile .d,.tile .l,th,.chip,.tagx,.due,.owner,.mbadge,.stage,summary .count{font-size:var(--fs-0)}.tile .v{font-size:var(--fs-4)}.hero .big,.verdict .big{font-size:var(--fs-3)}
.tile .l{text-transform:none;letter-spacing:0;color:var(--ink2)}th{text-transform:none;letter-spacing:0;color:var(--ink2);font-weight:600}
.card{background:var(--surface);border:1px solid var(--ring);box-shadow:var(--shadow);border-radius:var(--radius);padding:20px}.card .card{border-color:var(--rule)}
a{color:var(--acc)}a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.tabs{scrollbar-width:none}.tabs::-webkit-scrollbar{display:none}.tabs button[aria-selected="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.toc a{box-shadow:none}.toc a:hover,.toc a:focus{border-color:var(--acc)}
button.theme{display:inline-flex;align-items:center;gap:6px;box-shadow:none;border:1px solid var(--ring);background:var(--surface);color:var(--ink)}button.theme svg{flex:none}
details>summary{cursor:pointer}summary:hover{color:var(--ink)}
.chartbox .why::before{content:"Come si legge: ";font-weight:600;color:var(--ink)}
.owner.o-me{border-color:var(--acc2)}.owner.o-claude{border-color:var(--acc)}.owner.o-both{border-color:var(--ink2)}
.progress span{background:var(--good)}
@media (max-width:700px){h2{font-size:var(--fs-2);margin:32px 0 10px}.card{padding:14px}.tile .v{font-size:var(--fs-3)}.toc{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding-bottom:6px}.toc::-webkit-scrollbar{display:none}.top{padding-right:52px}button.theme{padding:8px}button.theme span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
@media print{:root{--bg:#fff;--surface:#fff;--shadow:none}body{background:#fff;color:#000}.tabs,.toc,button.theme,button.copy,.filters,.tip{display:none!important}
[role=tabpanel]{display:block!important}.card,details.fold,li.step,.num{break-inside:avoid}a{color:inherit;text-decoration:underline}main{max-width:none;padding:0}h2{break-after:avoid}}
"""
THEME_HEAD = "(function(){try{var t=localStorage.getItem('gls-theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}catch(e){}})();"
THEME_JS = """
(function(){var b=document.getElementById('theme');if(!b)return;var r=document.documentElement;
function dark(){return r.getAttribute('data-theme')==='dark'||(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);}
function label(){var d=dark();b.querySelector('span').textContent=d?'Tema chiaro':'Tema scuro';b.setAttribute('aria-label',d?'Passa al tema chiaro':'Passa al tema scuro');b.setAttribute('aria-pressed',d?'true':'false');}
b.addEventListener('click',function(){var t=dark()?'light':'dark';r.setAttribute('data-theme',t);try{localStorage.setItem('gls-theme',t);}catch(e){}label();});label();
var opened=[];addEventListener('beforeprint',function(){opened=[].slice.call(document.querySelectorAll('details:not([open])'));opened.forEach(function(d){d.open=true;});});
addEventListener('afterprint',function(){opened.forEach(function(d){d.open=false;});opened=[];});})();
"""
JS = """
(function(){document.querySelectorAll('.copy').forEach(function(b){b.addEventListener('click',function(){var t=b.getAttribute('data-copy')||'';function ok(){var o=b.textContent;b.textContent='Copiato';b.classList.add('ok');setTimeout(function(){b.textContent=o;b.classList.remove('ok');},1500);}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,function(){fb(t,ok);});}else{fb(t,ok);}});});
function fb(t,ok){var a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();try{document.execCommand('copy');ok();}catch(e){}document.body.removeChild(a);}
document.querySelectorAll('.filters button').forEach(function(b){b.addEventListener('click',function(){var f=b.getAttribute('data-f');document.querySelectorAll('.filters button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
document.querySelectorAll('.step').forEach(function(s){var o=s.getAttribute('data-owner');s.hidden=!(f==='all'||o===f||o==='both');});});});
document.querySelectorAll('.chart').forEach(function(c){var tip=c.querySelector('.tip'),cross=c.querySelector('.cross');
c.querySelectorAll('.hit').forEach(function(h){function show(){var x=h.getAttribute('data-x');if(cross){cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.style.display='block';}
tip.textContent=h.getAttribute('data-tip');tip.style.display='block';var svg=c.querySelector('svg'),k=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width;tip.style.left=Math.min(x*k+12,c.clientWidth-270)+'px';tip.style.top='8px';}
function hide(){tip.style.display='none';if(cross)cross.style.display='none';}
h.addEventListener('pointerenter',show);h.addEventListener('focus',show);h.addEventListener('pointerleave',hide);h.addEventListener('blur',hide);});});})();
(function(){var tabs=[].slice.call(document.querySelectorAll('.tabs [role=tab]'));if(!tabs.length)return;var KEY='status-tab:'+document.title;
function show(id,focus){var ok=false;tabs.forEach(function(t){var on=t.getAttribute('aria-controls')===id;if(on)ok=true;t.setAttribute('aria-selected',on?'true':'false');t.tabIndex=on?0:-1;if(on&&focus)t.focus();if(on){var bar=t.parentNode;bar.scrollLeft=Math.max(0,t.offsetLeft-(bar.clientWidth-t.offsetWidth)/2);}});
if(!ok)return false;document.querySelectorAll('[role=tabpanel]').forEach(function(p){p.hidden=p.id!==id;});try{localStorage.setItem(KEY,id);}catch(e){}return true;}
tabs.forEach(function(t,i){t.addEventListener('click',function(){show(t.getAttribute('aria-controls'));});
t.addEventListener('keydown',function(e){var k=e.key,j=k==='ArrowRight'?i+1:k==='ArrowLeft'?i-1:k==='Home'?0:k==='End'?tabs.length-1:-9;if(j===-9)return;e.preventDefault();j=(j+tabs.length)%tabs.length;show(tabs[j].getAttribute('aria-controls'),true);});});
function reveal(h){var el=h&&document.getElementById(h);if(!el)return false;var p=el.closest('[role=tabpanel]');if(p&&p.hidden)show(p.id);if(el.tagName==='DETAILS')el.open=true;var a=el.parentElement;while(a){if(a.tagName==='DETAILS')a.open=true;a=a.parentElement;}if(/^cal-[0-9]/.test(h)&&window.calSelect)window.calSelect(h.slice(4),false);el.scrollIntoView({block:'center'});if(el.classList.contains('step')){el.classList.add('flash');setTimeout(function(){el.classList.remove('flash');},1800);}return true;}
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href^="#"]');if(!a)return;var h=a.getAttribute('href').slice(1);if(h&&reveal(h)){e.preventDefault();try{history.replaceState(null,'','#'+h);}catch(x){}}});
var start=null;try{start=localStorage.getItem(KEY);}catch(e){}if(location.hash&&reveal(location.hash.slice(1)))return;if(!(start&&show(start)))show(tabs[0].getAttribute('aria-controls'));})();
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
    "pending": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7.2" fill="none" stroke="var(--crit)" stroke-width="2"/><path d="M9 5v4.5l3 1.5" stroke="var(--crit)" stroke-width="2" fill="none" stroke-linecap="round"/></svg>', "Da fare"),
    "warn": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M9 1.5L17 16H1z" fill="var(--warn)"/><path d="M9 6.5v4.5M9 13v.8" stroke="#0b0b0b" stroke-width="2" stroke-linecap="round"/></svg>', "Attenzione"),
    "info": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="8" fill="none" stroke="var(--muted)" stroke-width="2"/><path d="M9 8v5M9 5.2v.8" stroke="var(--muted)" stroke-width="2" stroke-linecap="round"/></svg>', "Info"),
    "na": ('<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><circle cx="9" cy="9" r="7.2" fill="none" stroke="var(--muted)" stroke-width="2"/><path d="M5 9h8" stroke="var(--muted)" stroke-width="2" stroke-linecap="round"/></svg>', "Non applicabile")}
LIGHT = {"verde": ("pass", "Verde"), "giallo": ("warn", "Giallo"), "rosso": ("fail", "Rosso")}


def state(kind: str, label: str | None = None) -> str:
    svg, default = ICONS.get(kind, ICONS["info"])
    return f'<span class="state">{svg}<span>{esc(label or default)}</span></span>'


# ----------------------------------------------------------------------------- markdown
def inline(t: str) -> str:
    """Escaped Markdown line: `code`, **bold**, *italic*, [text](url) and bare http(s) URLs as short clickable links."""
    t = esc(t)
    keep: list = []

    def stash(h: str) -> str:
        keep.append(h)
        return f"\x00{len(keep) - 1}\x00"
    t = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{m.group(1)}</code>"), t)

    def link(m):
        url = html.unescape(m.group(2)).strip()
        if not re.match(r"(https?://|#|[\w./-]+$)", url) or url.lower().startswith("javascript"):
            return m.group(1)
        ext = ' target="_blank" rel="noopener noreferrer"' if url.lower().startswith("http") else ""
        return stash(f'<a href="{esc(url)}"{ext}>{m.group(1)}</a>')
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, t)
    t = weblinks.URL.sub(lambda m: stash(weblinks.linkify_text(m.group(0))), t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?!\w)", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], t)


def md_to_html(md: str, row_hook=None) -> str:
    """Small Markdown renderer. row_hook(cells) -> extra html appended to the first cell of a table row (owner's decision badges)."""
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
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}{(row_hook(r) or '') if (row_hook and k == 0) else ''}</td>" for k, c in enumerate(r)) + "</tr>" for r in rows) + "</tbody></table></div>")
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
    """Focus-group score per wave: the beta waves as the main line, the full-game waves as a grey line with diamonds (never mixed)."""
    path = os.path.join(root, "fg", "timeline.csv")
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None, None
    stg = rc.stage_of(root)
    for r in rows:
        r["_stage"] = (r.get("stage") or stg.get(str(r.get("wave")), "")).strip()
    num = lambda v: float(str(v).replace(",", ".")) if str(v or "").strip() not in ("", "-") else None
    xs = {r["wave"]: k for k, r in enumerate(rows)}
    tip = lambda r: (f"Ondata {r['wave']} · {'gioco completo' if r['_stage'] == 'full' else 'beta' if r['_stage'] == 'beta' else 'senza tipo'} ({fmt_date(r['date'])})\nPunteggio {r['score']}"
                     + (f"\nTetto di questa versione {r['ceiling']} (margine {r.get('headroom')})" if num(r.get("ceiling")) is not None else f"\nTetto di questa versione: non misurato, stima {r['ceiling_estimate']} [STIMA]" if r.get("ceiling_estimate") else "")
                     + (f"\nTetto del gioco completo {r['ceiling_full']}" if num(r.get("ceiling_full")) is not None else "") + f"\nClick {r.get('click_pct') or '-'}% · pitch {r.get('pitch_pct') or '-'}%")
    beta = [r for r in rows if r["_stage"] != "full"]
    full = [r for r in rows if r["_stage"] == "full"]
    pts = [(xs[r["wave"]], float(r["score"]), tip(r)) for r in beta]
    refs, markers = [], []
    if full:
        refs.append(("Gioco completo", [(xs[r["wave"]], float(r["score"])) for r in full], True))
        markers += [(xs[r["wave"]], float(r["score"]), tip(r), "muted") for r in full]
    gate = num(rows[-1].get("gate"))
    if gate is not None:
        refs.append((f"Gate A: {fmt_n(gate)}", [(0, gate), (max(len(rows) - 1, 1), gate)], True))
    ceils = [(xs[r["wave"]], num(r["ceiling"]), f"Tetto di questa versione, ondata {r['wave']}: {r['ceiling']}", "good") for r in rows if num(r.get("ceiling")) is not None]
    markers += ceils
    vals = [float(r["score"]) for r in rows] + ([gate] if gate is not None else []) + [c[1] for c in ceils]
    ay = nice_axis(min(min(vals) - 5, 0), max(vals + [40]) + 10)
    svg = line_chart("Punteggio wishlist del focus group per ondata", pts or [(0, 0.0, "")], xlabels=[(k, f"{r['wave']}") for k, r in enumerate(rows)], ymin=ay[0], ymax=ay[1], ystep=ay[2], refs=refs, markers=markers,
                     xmax_pad=0.0 if len(rows) > 1 else 1)
    svg += table_view(["Ondata", "Tipo", "Data", "Punteggio", "Variazione", "Tetto di questa versione", "Margine", "Tetto del gioco completo", "Click %", "Pitch %", "A / B"],
                      [[r["wave"], {"full": "gioco completo", "beta": "beta"}.get(r["_stage"], "-"), r["date"], r["score"], r.get("delta") or "", r.get("ceiling") or (f"~{r['ceiling_estimate']} [STIMA]" if r.get("ceiling_estimate") else ""),
                        r.get("headroom") or "", r.get("ceiling_full") or "", r.get("click_pct"), r.get("pitch_pct"), f"{r.get('score_a')} / {r.get('score_b')}"] for r in rows])
    return rows, svg


# ----------------------------------------------------------------------------- other sources
def read_todos(root: str):
    """(open items, done count, open hours) from TODO.md: kept for qa. The full live view is todo_section()."""
    t = tt.parse(os.path.join(root, "TODO.md"))
    if not t:
        return [], 0, 0.0
    open_ = [dict(action=x["action"], due=x["due"], hours=x["hours"], metric=x["metric"], h=x["h"]) for x in t["items"] if not x["done"] and not x.get("dropped")]
    open_.sort(key=lambda x: x["due"] if re.match(r"\d{4}-\d{2}-\d{2}", x["due"]) else "9999")
    return open_, sum(1 for x in t["items"] if x["done"]), sum(x["h"] for x in open_)


def todo_section(root: str, today: dt.date) -> str | None:
    """TODO.md, live: progress, open vs done per section (done collapsed), overdue flagged, and a warning when the file was not
    touched after the latest wave or decision (Claude updates it after every gate, wave and decision: todo_track.py done/add)."""
    path = os.path.join(root, "TODO.md")
    t = tt.parse(path)
    if not t or not t["items"]:
        return None
    gone = [x for x in t["items"] if x.get("dropped")]
    items = [x for x in t["items"] if not x.get("dropped")]
    n_done = sum(1 for x in items if x["done"])
    pct = round(100 * n_done / len(items))
    overdue = [x for x in items if not x["done"] and x["due_date"] and x["due_date"] < today]
    newer = []
    mt_todo = os.path.getmtime(path)
    for label, f in (("l'ultima ondata del focus group", sorted(glob.glob(os.path.join(root, "fg", "waves", "w[0-9]*.json")))[-1:] or [None]), ("le tue decisioni (issue_status.json)", [os.path.join(root, "issue_status.json")]),
                     ("il calendario a passi", [os.path.join(root, "calendar.md")])):
        f = f[0]
        if f and os.path.exists(f) and os.path.getmtime(f) > mt_todo + 60:
            newer.append(f"{label} ({dt.date.fromtimestamp(os.path.getmtime(f)).isoformat()})")
    stale = (f'<p>{state("warn", "Da aggiornare")} <span>TODO.md è del {dt.date.fromtimestamp(mt_todo).isoformat()}, più vecchio di {esc(", ".join(newer))}. '
             'Claude deve spuntare le voci fatte e aggiungere le nuove (<code>todo_track.py done</code> / <code>add</code>).</span></p>') if newer else ""

    def line(x):
        who = {"me": "👤 Tu", "claude": "🤖 Claude", "both": "👤+🤖 Insieme"}.get(x["owner"], "")
        st = ("pass", "Fatto") if x["done"] else ("fail", "In ritardo") if x in overdue else ("pending", "Da fare")
        meta = [m for m in (who, f"entro {x['due']}" if x["due"] else "", f"{x['hours']}" if x["hours"] else "", f"misura: {x['metric']}" if x["metric"] else "", x["done_note"]) if m]
        return (f'<div class="todo-l{" done" if x["done"] else ""}"><span>{state(*st)}</span><span class="txt">{inline(x["action"])}</span>'
                + (f'<div class="meta">{"".join(f"<span>{inline(m)}</span>" for m in meta)}</div>' if meta else "") + "</div>")
    out = [f'<h2>Cose da fare (TODO)</h2><div class="card"><p class="sub">Dal file <code>TODO.md</code> (aggiornato: {esc(t.get("updated") or "n/d")}). '
           f'<strong>{len(items) - n_done} aperte</strong>, {n_done} fatte su {len(items)}' + (f' · <span class="over">{len(overdue)} in ritardo</span>' if overdue else "") + "</p>"
           f'<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}" aria-label="Voci della TODO fatte"><span style="width:{pct}%"></span></div>{stale}</div>']
    for sec in t["sections"]:
        its = [x for x in items if x["section"] == sec]
        if not its:
            continue
        op, dn = [x for x in its if not x["done"]], [x for x in its if x["done"]]
        out.append(f'<details class="card todo-sec"{" open" if op and sec == next((s2 for s2 in t["sections"] if any(not x["done"] and x["section"] == s2 for x in items)), None) else ""}>'
                   f'<summary>{inline(sec)}<span class="count">{len(op)} da fare · {len(dn)} fatte</span></summary>'
                   + "".join(line(x) for x in op)
                   + (f'<details class="decided"><summary>Fatte ({len(dn)})</summary>{"".join(line(x) for x in dn)}</details>' if dn else "") + "</details>")
    if gone:
        out.append(f'<details class="card todo-sec"><summary>Superate dalle tue decisioni<span class="count">{len(gone)}</span></summary>'
                   + "".join(f'<div class="todo-l done"><span>{state("na", "Superata")}</span><span class="txt">{inline(x["action"])}</span><div class="meta"><span>{inline(x["done_note"])}</span></div></div>' for x in gone) + "</details>")
    return "".join(out)


# ----------------------------------------------------------------------------- page
OWNER = {"me": "👤 Tu", "claude": "🤖 Claude", "both": "👤+🤖 Insieme", "none": "—"}
STEP_STATE = {"done": ("pass", "Fatto"), "open": ("pending", "Da fare"), "overdue": ("fail", "In ritardo")}


def note_parts(note: str) -> dict:
    """A tool-written step note ("scadenza 2026-10-23 [FATTO https://…, letto …] · serve: trailer · prossimo passo: … · https://… [id promo:x]")
    -> {'next': one line, 'chips': [(label, value)], 'links': [url], 'rest': [segments]}: the dense event lists read at a glance."""
    out = dict(next="", chips=[], links=[], rest=[])
    note = re.sub(r"^\s*-\s*", "", note or "")
    note = re.sub(r"\s*\[id [^\]]+\]\s*$", "", note)
    for seg in [x.strip() for x in note.split(" · ") if x.strip()]:
        low = seg.lower()
        if low.startswith("prossimo passo:"):
            out["next"] = seg.split(":", 1)[1].strip()
        elif re.match(r"(serve|costo|scadenza|promemoria fine finestra|data valve)\b", low) and len(seg) < 140:
            m = re.match(r"([^:\d\[]+?):\s+(.*)$", seg)
            k, v = (m.group(1), m.group(2)) if m else seg.split(" ", 1) if " " in seg else (seg, "")
            out["chips"].append((k.strip(), v.strip()))
        elif re.fullmatch(r"https?://\S+", seg):
            out["links"].append(seg)
        else:
            out["rest"].append(seg)
    return out


def step_li(s: dict, today: dt.date) -> str:
    st = ps.status_of(s, today)
    due = ""
    if s.get("due"):
        n = (dt.date.fromisoformat(s["due"]) - today).days
        rel = "" if s["done"] else " · oggi" if n == 0 else f" · tra {n} g" if 0 < n <= 30 else f" · {-n} g fa" if n < 0 else ""
        due = f'<span class="due{" late" if st == "overdue" else " soon" if not s["done"] and 0 <= n <= 7 else ""}">📅 {fmt_date(s["due"])}{rel}</span>'
    m = re.match(r"(\s*(?:⭐ mossa top · )?\*\*.+?\*\*)(.*)$", s["text"])
    head, tail = (m.group(1), m.group(2).strip()) if m else (s["text"], "")
    val = re.search(r"valore (\d+/\d+)", tail)
    tail = re.sub(r",?\s*valore \d+/\d+", "", tail).replace("()", "").strip()
    top = "⭐" in head
    chips, nexts, links, rest = [], [], [], []
    for note in s.get("notes") or []:
        p = note_parts(note)
        if p["next"] or p["chips"] or p["links"]:
            chips += p["chips"]; links += p["links"]; rest += p["rest"]
            if p["next"]:
                nexts.append(p["next"])
        else:
            rest.append(note)
    body = [f'<div class="stext"><span class="stitle">{inline(head.replace("⭐ mossa top · ", ""))}</span>' + (f' <span class="stail">{inline(tail)}</span>' if tail else "") + "</div>"]
    tags = ([f'<span class="tagx top">⭐ mossa top</span>'] if top else []) + ([f'<span class="tagx">valore {esc(val.group(1))}</span>'] if val else []) \
        + [f'<span class="tagx"><b>{esc(k)}</b> {inline(v)}</span>' for k, v in chips[:4]] + [f'<span class="tagx lnk">{weblinks.anchor(u)}</span>' for u in links[:2]]
    if tags:
        body.append(f'<div class="stags">{"".join(tags)}</div>')
    if nexts:
        body.append(f'<div class="snext">→ {inline(nexts[0])}</div>')
    if rest:
        body.append(f'<details class="sdet"><summary>Dettagli</summary><div class="notes">{"<br>".join(inline(n) for n in rest)}</div></details>' if (nexts or tags) else
                    f'<div class="notes">{"<br>".join(inline(n) for n in rest)}</div>')
    return (f'<li class="step" id="step-{s["n"]}" data-owner="{s["owner"]}" data-state="{st}"><span class="n">{s["n"]}</span><div class="meta">{state(*STEP_STATE[st])}<span class="owner o-{s["owner"]}">{OWNER[s["owner"]]}</span>{due}</div>'
            + "".join(body) + "</li>")


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
    if p.get("early_access"):
        ea = p["early_access"]
        elim = ea.get("limits") or {}
        o.append(f'<div class="field"><strong>Early Access: le domande di Steam</strong><p class="note">Compaiono sulla pagina del gioco. Domande lette su {esc(ea.get("source") or "partner.steamgames.com/doc/store/earlyaccess")} il {esc(ea.get("verified_on") or "[DA VERIFICARE]")}. '
                 'Valve chiede di non promettere date o funzioni future.</p>')
        for k, (label, value, note) in zip([q.get("key") for q in ea.get("questions", []) if q.get("key") in dict(sk.EA_QUESTIONS)], sk.ea_rows(p)):
            lim = elim.get(k) or sk.EA_SOFT_LIMIT
            over = f' {state("warn", "Lungo da leggere")}' if len(value) > lim else ""
            o.append(f'<div class="field"><div class="fh"><strong>{esc(label)}</strong><span><span class="note">{len(value)} caratteri</span>{over} {copy_btn(value)}</span></div><pre class="val">{esc(value)}</pre>' + (f'<p class="note">{esc(note)}</p>' if note else "") + "</div>")
        o.append("</div>")
    if p.get("accessibility"):
        txt = sk.accessibility_text(p, "bbcode" if pf == "steam" else "md")
        o.append(f'<div class="field"><div class="fh"><strong>Accessibilità</strong><span><span class="note">{len(p["accessibility"].get("features") or [])} opzioni</span> {copy_btn(txt)}</span></div>'
                 + "<ul class=\"clean\">" + "".join(f'<li>{state("pass", "Nel gioco")}<span><strong>{esc(f.get("label"))}</strong>: {esc(f.get("value"))}</span></li>' for f in p["accessibility"].get("features") or []) + "</ul>"
                 + (f'<p class="note">{esc(p["accessibility"]["note"])}</p>' if p["accessibility"].get("note") else "") + "</div>")
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


def kit_section(kit: dict, root: str | None = None) -> str:
    fr = sk.freshness(root) if root else {}
    fresh = ""
    if fr:
        fresh = (f'<p>{state("pass", "Pagine store aggiornate")} <span>al {fmt_date(fr["kit_date"])}: nessuna decisione, ondata o gate più recente.</span></p>' if not fr["stale"] else
                 f'<p>{state("warn", "Pagine store da aggiornare")} <span>Il kit è del {fmt_date(fr["kit_date"])}; dopo sono arrivati: ' + "; ".join(f"{esc(w)} ({fmt_date(d)})" for w, d in fr["newer"])
                 + '. Claude li aggiorna.</span></p>')
    out = [f'<h2>Pagine store: scheda copiabile</h2><div class="card">{fresh}<p class="note">Ogni campo ha il suo pulsante Copia. I limiti di caratteri sono quelli verificati alla data scritta accanto a ogni pagina.</p></div>']
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


def waves_md_section(root: str) -> str | None:
    """Fallback when there are no wave .json files: the per-wave reports written by fg_waves.py (metrics and delta), as Markdown."""
    d = os.path.join(root, "fg")
    files = []
    wd = os.path.join(d, "waves")
    if os.path.isdir(wd):
        files += sorted((f for f in os.listdir(wd) if re.match(r"w\d+-(metrics|delta)(-[a-z0-9]+)?\.md$", f)), key=lambda f: (int(re.match(r"w(\d+)", f).group(1)), "delta" in f, f))
    parts = []
    for f in files:
        m = re.match(r"w(\d+)-(metrics|delta)(?:-([a-z0-9]+))?", f)
        variant = {"beta": " · beta gratuita", "full": " · gioco completo"}.get(m.group(3) or "", f" · {m.group(3)}" if m.group(3) else "")
        parts.append(f'<details class="card doc"><summary><strong>Ondata {int(m.group(1))}{variant}: {"metriche e criticità" if m.group(2) == "metrics" else "cosa è cambiato rispetto alla precedente"}</strong></summary>'
                     f'{md_to_html(open(os.path.join(wd, f), encoding="utf-8").read())}</details>')
    return ("<h2>Ondate del focus group</h2>" + "".join(parts)) if parts else None


def waves_section(root: str) -> str | None:
    """One card per wave, newest first, built from the wave files (not from the English .md): beta or full game in clear,
    score against the threshold, change against the previous wave OF THE SAME KIND, ceiling and headroom, what testers would do,
    and the issues still to do with the owner's decision."""
    import fg_waves
    ws = rc.wave_files(root)
    if not ws:
        return waves_md_section(root)
    owner = cr.load_owner(root)
    f = lambda v: "n/d" if v is None else f"{v:g}".replace(".", ",")
    parts, prev_by = [], {}
    cards = []
    for w in ws:
        try:
            m = fg_waves.metrics(w)
        except (SystemExit, Exception):
            continue
        g = "full" if w.get("stage") == "full" else "beta"
        prev = prev_by.get(g)
        prev_by[g] = m
        cards.append((w, m, prev))
    for k, (w, m, prev) in enumerate(reversed(cards)):
        stg = w.get("stage") or ""
        badge = {"beta": '<span class="stage">Beta gratuita</span>', "full": '<span class="stage full">Gioco completo (proiezione)</span>'}.get(stg, '<span class="stage">Tipo non indicato</span>')
        delta = "" if not prev else f" ({'+' if m['score'] - prev['score'] >= 0 else ''}{f(round(m['score'] - prev['score'], 1))} rispetto all'ondata {prev['wave']})"
        ok = m["gate"]["passed"]
        tiles = [("Punteggio", f(m["score"]), f"soglia {f(m['gate']['threshold'])}: {'superata' if ok else 'non superata'}")]
        c, cf, ce = m.get("ceiling"), m.get("ceiling_full"), m.get("ceiling_estimate")
        if c:
            tiles.append(("Tetto di questa versione", f(c["score"]), f"margine {f(c['headroom'])} punti · oggi al {f(c['share'])}% del tetto"))
        elif ce:
            tiles.append(("Tetto di questa versione", "~" + str(ce["value"]).replace(".", ","), "non misurato [STIMA]"))
        if cf:
            tiles.append(("Tetto del gioco completo", f(cf["score"]), "con i contenuti pianificati: non è margine di oggi"))
        tiles += [("Wishlist subito", f(m["pct"]["WISHLIST"]) + "%", ""), ("Aspetta i saldi", f(m["pct"]["SALDI"]) + "%", ""), ("Scorre oltre", f(m["pct"]["IGNORO"]) + "%", ""), ("Compra e rimborsa", f(m["pct"]["REFUND"]) + "%", "")]
        if m["click"]["n"]:
            tiles.append(("Clicca al primo sguardo", f(m["click"]["pct"]) + "%", ""))
        if m["pitch"]["n"]:
            tiles.append(("Capisce il gioco", f(m["pitch"]["pct"]) + "%", ""))
        if m["buy"]["n"]:
            tiles.append(("Pagherebbe il prezzo", f(m["buy"]["pct"]) + "%", ""))
        body = [f'<p class="meta">{badge} · {fmt_date(m["date"])} · {m["n"]} tester' + (f' · versione {esc(m["build"])}' if m.get("build") else "") + "</p>",
                '<div class="wgrid">' + "".join(f'<div class="card tile"><div class="l">{esc(l)}</div><div class="v">{esc(v)}</div>' + (f'<div class="d">{esc(d)}</div>' if d else "") + "</div>" for l, v, d in tiles) + "</div>"]
        if c:
            reasons = ", ".join(f"{esc(r)} {n}" for r, n in c["reasons"].items())
            near_badge = state("pass", "Vicino al tetto") if c["near"] else state("info", "C'è ancora margine")
            body.append(f'<p>{near_badge} '
                        + ("<span>Il gioco è vicino al massimo che questo panel gli darebbe: smettere di aggiungere idee e passare ai test con persone vere.</span>" if c["near"] else
                           f"<span>Mancano {f(c['headroom'])} punti al tetto di questa versione: lavorare solo sui problemi risolvibili, non su idee nuove. {c['stuck']} tester su {c['n']} non metterebbero il gioco in wishlist nemmeno sistemato" + (f" (motivi: {reasons})" if reasons else "") + ": non è il loro gioco.</span>") + "</p>")
        elif ce:
            body.append(f'<p>{state("info", "Tetto di questa versione non misurato")} <span>Stima ~{esc(ce["value"])} [STIMA]' + (f": {esc(ce['note'])}" if ce.get("note") else "") + ". Nella prossima ondata chiedi le due domande del tetto (questa versione / gioco completo).</span></p>")
        elif stg != "full":
            body.append('<p class="note">In questa ondata non è stata fatta la domanda del tetto di questa versione (cosa farebbero i tester se si sistemasse solo ciò che si può sistemare adesso).</p>')
        if cf:
            body.append(f'<p class="note">Tetto del gioco completo {f(cf["score"])}: è il punteggio immaginato con i contenuti pianificati. Non è margine raggiungibile con questa versione.</p>')
        now = [i for i in m["issues"] if cr.is_now(i["key"], owner)]
        dec = len(m["issues"]) - len(now)
        if now:
            body.append(f"<h3>Da fare adesso ({len(now)})</h3><ul class=\"clean\">" + "".join(f'<li><span><strong>{esc(i["label"])}</strong> <span class="note">{f(i["pct"])}% dei tester · gravità {esc(i["severity"])}' + (f' · nato col gate {i["from_gate_dev"]}' if i.get("from_gate_dev") is not None else "") + f'</span> {cr.owner_badge(i["key"], owner, with_note=False)}</span></li>' for i in now[:8]) + "</ul>")
        if dec:
            body.append(f'<p class="note">Altre {dec} critiche di questa ondata hanno già una decisione: sono nella sezione Criticità, sotto «Già deciso».</p>')
        if w.get("evidence"):
            body.append(f'<p class="note">Cosa hanno visto i tester: {esc(w["evidence"])}</p>')
        title = f"Ondata {m['wave']} · {'gioco completo' if stg == 'full' else 'beta' if stg == 'beta' else 'senza tipo'} · {fmt_date(m['date'])}: punteggio {f(m['score'])}{delta}"
        parts.append(f'<details class="card doc"{" open" if k < 2 else ""}><summary><strong>{esc(title)}</strong></summary>{"".join(body)}</details>')
    intro = ('<p class="sub">Ogni ondata è lo stesso gruppo di tester simulati sullo stato del gioco di quel giorno. Le ondate <strong>beta</strong> giudicano la beta gratuita; '
             'quelle <strong>gioco completo</strong> giudicano il gioco finito come da piano (sono una proiezione). Si confrontano solo con ondate dello stesso tipo. '
             'Il <strong>tetto di questa versione</strong> è il punteggio che il panel darebbe se si sistemasse solo ciò che si può sistemare adesso (bug, chiarezza, rifinitura, niente contenuti nuovi); il <strong>margine</strong> è quanto manca. '
             'Il <strong>tetto del gioco completo</strong> conta anche i contenuti pianificati: dice dove può arrivare il gioco finito, non quanto si guadagna oggi.</p>')
    return ("<h2>Ondate del focus group</h2>" + intro + "".join(parts)) if parts else None


def key_tiles(st: dict, wl_a, fg_rows, plan: dict, econ, today: dt.date, hide: set) -> list:
    """The key numbers shown on top of STATUS.html: (label, value, note)."""
    tiles = []
    if wl_a and "current" in wl_a:
        vel = wl_a.get("velocity_4w")
        tiles.append(("Wishlist", fmt_n(wl_a["current"]), f"{'+' if vel and vel > 0 else ''}{fmt_n(vel)} a settimana (ultime 4)" if vel is not None else f"dato del {fmt_date(wl_a['last_record'])}"))
        if "days_to_launch" in wl_a:
            tiles.append(("Giorni al lancio", fmt_n(wl_a["days_to_launch"]), fmt_date(wl_a["launch"])))
    if fg_rows:
        typed = any(r.get("_stage") for r in fg_rows)
        for kind, name in (("beta", "Punteggio focus group" + (" · beta" if typed else "")), ("full", "Punteggio focus group · gioco completo")):
            rs = [r for r in fg_rows if (r.get("_stage") == "full") == (kind == "full")]
            if not rs:
                continue
            last, prev = rs[-1], rs[-2] if len(rs) > 1 else None
            tiles.append((name, str(last["score"]).replace(".", ","), f"ondata {last['wave']}" + (f", {float(last['score']) - float(prev['score']):+.1f} rispetto all'ondata {prev['wave']}".replace(".", ",") if prev else "")))
            name_v = "Tetto di questa versione" + (" (beta)" if kind == "beta" and typed else "" if kind == "beta" else " (gioco completo)")
            if str(last.get("ceiling") or "").strip():
                tiles.append((name_v, str(last["ceiling"]).replace(".", ","), f"margine {str(last.get('headroom')).replace('.', ',')} punti: quanto si può ancora guadagnare con le sole correzioni possibili adesso"))
            elif str(last.get("ceiling_estimate") or "").strip():
                tiles.append((name_v, "~" + str(last["ceiling_estimate"]).replace(".", ","), "non misurato [STIMA]: chiedere la domanda del tetto di questa versione alla prossima ondata"))
            if kind == "beta" and str(last.get("ceiling_full") or "").strip():
                tiles.append(("Tetto del gioco completo", str(last["ceiling_full"]).replace(".", ","), "con i contenuti pianificati: non è margine di oggi"))
    if plan["phases"] and "steps" not in hide:
        sm = ps.summary(plan, today)
        tiles.append(("Passi fatti", f"{sm['done']}/{sm['total']}", f"{sm['overdue']} in ritardo" if sm["overdue"] else "nessuno in ritardo"))
    if econ:
        be = econ["breakeven"]
        if str(st.get("breakeven_basis", "")).lower() == "cash" and "copies_cash" in be:   # status.json: "breakeven_basis": "cash" counts only the money spent, not the hours
            tiles.append(("Break-even (soldi spesi)", fmt_n(be["copies_cash"]), f"copie (netto per copia {econ['net_per_copy']:.2f}; contando le ore {fmt_n(be.get('copies_with_time'))})"))
        else:
            tiles.append(("Break-even", fmt_n(be["copies_with_time"]), f"copie (netto per copia {econ['net_per_copy']:.2f})"))
    gates = st.get("gates") or {}
    if gates:
        tiles.append(("Gate superati", f"{sum(1 for g in gates.values() if g.get('state') == 'pass')}/{len(gates)}", "Go/No-Go prima di Steam Direct"))
    for k in st.get("key_numbers", []):
        tiles.append((k.get("label", ""), k.get("value", ""), k.get("note", "")))
    return tiles


TABS = [("riepilogo", "Riepilogo", '<path d="M3 3h5v5H3zM10 3h5v5h-5zM3 10h5v5H3zM10 10h5v5h-5z"/>'),
        ("gioco", "Gioco e test", '<path d="M4 6h10a2 2 0 012 2v3a2 2 0 01-2 2h-1.5L11 11H7l-1.5 2H4a2 2 0 01-2-2V8a2 2 0 012-2zM6 8v2M5 9h2M12 9h.5"/>'),
        ("marketing", "Marketing e social", '<path d="M3 7v4h2l5 3V4L5 7zM13 6.5a3 3 0 010 5"/>'),
        ("trailer", "Trailer", '<path d="M2 4h14v10H2zM2 7h14M5 4l1.5 3M9 4l1.5 3M13 4l1.5 3M7.5 9.5v3l2.6-1.5z"/>'),
        ("piano", "Piano e soldi", '<path d="M3 4h12v11H3zM3 7h12M6 2v3M12 2v3M6 10h2M10 10h2M6 12.5h2"/>'),
        ("calendario", "Calendario", '<path d="M3 4h12v11H3zM3 7.5h12M6 2v3M12 2v3"/><circle cx="7" cy="11" r="1.2" fill="currentColor"/><path d="M10 11h2.5"/>'),
        ("mercato", "Mercato reale", '<path d="M3 15V9M7 15V5M11 15V8M15 15V3M2 15.5h14"/>'),
        ("docs", "Documenti", '<path d="M5 2h6l3 3v11H5zM11 2v3h3M7 8h5M7 10.5h5M7 13h3"/>')]
TAB_INTRO = {"riepilogo": "Il punto della situazione: verdetto, cosa tocca adesso, numeri chiave e andamento.",
             "gioco": "Il gioco e i test: pilastri, criticità ondata per ondata con le tue decisioni, focus group, recensioni reali dei giochi simili.",
             "marketing": "In cima: cosa fare adesso, i canali, i numeri contro i casi reali e il controllo «perché floppa». Sotto, da aprire: pagine store da copiare, clip, piano social, creator, prove e documenti.",
             "trailer": "Il trailer: prompt completo da copiare (positivo e negativo), storyboard a schede (una per inquadratura: tempo, cosa si vede, camera, testo, audio, come girarla), trailer dei concorrenti misurati e controlli di qualità.",
             "piano": "Quando e quanto: passi in ordine, TODO, cancelli, date, economia, piani se… allora, concorrenti e finestra di lancio.",
             "calendario": "Tutte le date in un colpo d'occhio: traguardi, passi tuoi e di Claude, scadenze di Steam e degli showcase, ondate del focus group, fino al lancio.",
             "mercato": "Il mercato vero, non simulato: quanti giochi escono, quanti sono al nostro livello, quanti vendono, cosa hanno fatto i vincenti, il metro oggettivo, concorrenti, KPI e previsioni contro realtà.",
             "docs": "I documenti completi, le domande e risposte e il glossario."}
DOC_TAB = {"01-dev": "gioco", "05-focusgroup": "gioco", "05a-critiche-simulate": "gioco", "05b-critiche-reali": "gioco", "01c-full-game": "gioco",
           "01b-positioning": "marketing", "04-clips": "marketing", "04b-store-copy": "marketing", "06-creators": "marketing", "07-community": "marketing",
           "02-platform": "piano", "03-pricing": "piano", "03-pricing-calc": "piano", "05c-premortem": "piano", "05d-contingenze": "piano", "window": "piano",
           "publisher-scout": "piano", "social-plan": "marketing", "clips": "marketing", "case-studies": "piano"}
GROUP_TAB = {"product": "gioco", "fg": "gioco", "reviews": "gioco", "fullgame": "gioco", "creators": "marketing", "market": "piano", "window": "piano", "econ": "piano", "plan": "piano"}


def issue_matcher(root: str, st: dict, owner: dict):
    """f(text) -> [issue keys] by the issue labels of the wave files (same text) and the aliases (issue_status.json, status.json issue_aliases)."""
    labels = {}
    for w in rc.wave_files(root):
        for k, d in (w.get("_defined") or {}).items():
            if d.get("label"):
                labels[re.sub(r"\W+", " ", d["label"]).strip().lower()] = k
    al = cr.aliases(owner, st)

    def f(text: str) -> list:
        t = re.sub(r"[*_`]", "", text or "")
        norm = re.sub(r"\W+", " ", t).strip().lower()
        keys = []
        if norm in labels:
            keys.append(labels[norm])
        for k, rx in al:
            if rx.search(t) and k not in keys:
                keys.append(k)
        return keys[:4]
    return f


def badges_for(keys: list, owner: dict, root_labels: dict | None = None) -> str:
    """Owner's decisions for a list of issue keys, deduplicated by status; the issue name and the note are in the tooltip."""
    if not keys:
        return ""
    seen, out = {}, []
    for k in keys:
        txt = cr.owner_text(k, owner)
        st_ = (owner.get(k) or {}).get("status", "da decidere")
        name = (root_labels or {}).get(k, k)
        seen.setdefault(st_, []).append(f"{name}: {txt}")
    for st_, tips in seen.items():
        k = next(k for k in keys if (owner.get(k) or {}).get("status", "da decidere") == st_)
        out.append(cr.owner_badge(k, owner, with_note=False, tip=" · ".join(tips)))
    return '<span class="risk-own">' + "".join(out) + "</span>"


def render_group(g: dict) -> str:
    wide = ' style="grid-column:1/-1"'
    full = g["key"] in ("product", "reviews")
    return (f'<h2>{esc(g["title"])}</h2><p class="sub">{esc(g["intro"])}</p><div class="cgrid">'
            + "".join(f'<div class="card"{wide if (g.get("wide") or full) else ""}>{c}</div>' for c in g["charts"]) + "</div>")


TIER_LABEL = {"realistic_now": ("pass", "Realistico adesso"), "realistic_after": ("warn", "Realistico dopo un passo"), "stretch": ("pending", "Difficile"), "dream": ("na", "Sogno")}
SOCIAL_NAMES = {"tiktok": "TikTok", "youtube_shorts": "Shorts", "instagram": "Reels", "reddit": "Reddit", "x": "X"}


def _raw(root: str, name: str):
    p = os.path.join(root, "_raw", name)
    return load_json(p) if os.path.exists(p) else None


def publisher_section(root: str, st: dict) -> str | None:
    """Publisher: the owner's answer (yes / no / don't know), the ranked list by tier and the with/without comparison (publisher_scout.py)."""
    d = _raw(root, "publisher_scout.json")
    if not d:
        return None
    q = (st.get("publisher") or {}).get("question") or d.get("publisher_question")
    ans = {"yes": "sì", "no": "no", "dont_know": "non so"}.get(q, q or "non ancora chiesta")
    c = d.get("counts") or {}
    rows = []
    for r in d["rows"][:12]:
        unlock = f' <span class="note">{esc(r["unlock"])}</span>' if r.get("unlock") and r["tier"] != "realistic_now" else ""
        rows.append(f'<tr><td>{esc(r["name"])}</td><td>{state(*TIER_LABEL.get(r["tier"], ("info", r["tier"])))}{unlock}</td>'
                    f'<td class="n">{r["fit"]:.0f}</td><td class="n">{esc(r["band"])}</td><td>{esc(r["next_step"])}</td></tr>')
    cmp_ = d.get("compare")
    ctab = ""
    if cmp_:
        heads = "".join(f'<th class="n">{esc(p_["label"])}</th><th class="n">serve vendere ×</th>' for p_ in cmp_["profiles"])
        body = []
        for s_ in cmp_["scenarios"]:
            cells = "".join(f'<td class="n">{fmt_n(x["income_low"])} … {fmt_n(x["income_high"])}</td><td class="n">'
                            + ("basta l'anticipo" if x["breakeven_uplift"] == 0 else esc(x["breakeven_uplift"])) + "</td>" for x in s_["deals"])
            body.append(f'<tr><td>{esc(s_["name"])}</td><td class="n">{fmt_n(s_["copies"])}</td><td class="n">{fmt_n(s_["alone"])}</td>{cells}</tr>')
        ctab = (f'<h3>Con o senza publisher: cosa ti resta ($)</h3><div class="wrap"><table><thead><tr><th>Scenario</th><th class="n">Copie</th><th class="n">Da soli</th>{heads}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
                '<p class="note">"Serve vendere ×": quante volte più copie deve farti vendere il publisher perché ti resti quanto da solo. Rev share e anticipi cambiano da contratto a contratto [DA VERIFICARE].</p>')
    pt = d.get("pitch_top") or {}
    head = (f'<h2>Publisher: sì, no o non so?</h2><div class="card"><p>Risposta del proprietario: <strong>{esc(ans)}</strong>. Realistici adesso: <strong>{c.get("realistic_now", 0)}</strong> · '
            f'dopo un passo: <strong>{c.get("realistic_after", 0)}</strong> · difficili: {c.get("stretch", 0)} · sogni: {c.get("dream", 0)}.</p>')
    if pt.get("n"):
        head += (f"<p>Proponendo il gioco ai primi {pt['n']} realistici, la probabilità di almeno un'offerta è al massimo circa <strong>{round(100 * pt.get('p_any', 0))} %</strong> [STIMA]: "
                 "il piano resta quello da soli, il publisher è un'opzione in più.</p>")
    head += "".join(f'<p class="sub">Sblocca di più: <strong>{esc(u["unlock"])}</strong> → {esc(", ".join(u["publishers"][:6]))}</p>' for u in (d.get("unlocks") or [])[:2])
    return (head + f'<div class="wrap"><table><thead><tr><th>Publisher</th><th>Fascia</th><th class="n">Aderenza</th><th class="n">Per invio [STIMA]</th><th>Prossimo passo</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>{ctab}'
            + f'<p class="note">Da <code>publisher_scout.py</code> del {esc(d.get("generated_on", ""))}; dettagli e fonti in publisher-scout.md.</p></div>')


def social_section(root: str, today: dt.date) -> str | None:
    """Social: the next 7 days of planned posts, what works for THIS game (learn) and the Reddit trends (reddit_trends.py)."""
    pl, ln, rt = _raw(root, "social_plan.json"), _raw(root, "social_learn.json"), _raw(root, "reddit_trends.json")
    if not (pl or ln or rt):
        return None
    N = SOCIAL_NAMES
    H = ['<h2>Social: piano e cosa funziona</h2><div class="card">']
    if pl and _raw(root, "social_kit.json"):
        pl = None                      # the weekly ready-to-post kit (clips_kit_section) replaces the long plan table
    if pl:
        nxt = [x for x in pl["posts"] if today <= dt.date.fromisoformat(x["date"]) <= today + dt.timedelta(days=7)]
        if not nxt:
            nxt = [x for x in pl["posts"] if dt.date.fromisoformat(x["date"]) >= today][:8]
        if nxt:
            H.append("<h3>I prossimi post</h3><div class=\"wrap\"><table><thead><tr><th>Data</th><th>Dove</th><th>Momento</th><th>Testo d'apertura (A / B)</th><th>Fine</th></tr></thead><tbody>"
                     + "".join(f'<tr><td class="nw">{fmt_date(x["date"])}</td><td>{esc(N.get(x["platform"], x["platform"]))}{(" " + esc(x["subreddit"])) if x.get("subreddit") else ""}</td>'
                               f'<td>{esc(x["moment"])} {esc(x["moment_label"][:50])}</td><td>{esc(x["hook_a"])} / {esc(x["hook_b"])}</td><td>{esc(x["cta"])}</td></tr>' for x in nxt)
                     + "</tbody></table></div>")
    if ln and ln.get("platforms"):
        H.append('<h3>Cosa funziona per noi (numeri veri)</h3><div class="wrap"><table><thead><tr><th>Dove</th><th class="n">Post</th><th class="n">Visual. mediane</th><th class="n">× il tipico</th><th class="n">Wishlist / 1.000</th></tr></thead><tbody>'
                 + "".join(f'<tr><td>{esc(N.get(p_["platform"], p_["platform"]))}</td><td class="n">{p_["n"]}</td><td class="n">{fmt_n(p_["median_views"])}</td><td class="n">{esc(p_["vs_typical"])}</td>'
                           f'<td class="n">{esc(p_["wishlists_per_1k"] if p_["wishlists_per_1k"] is not None else "—")}</td></tr>' for p_ in ln["platforms"])
                 + "</tbody></table></div>" + (f'<p>Da rifare: {esc(", ".join(str(w.get("label") or w["key"]).replace("_", " ") for w in ln["winners"]))}</p>' if ln.get("winners") else "")
                 + "".join(f'<p class="note">{esc(w)}</p>' for w in ln.get("warnings", [])))
    elif pl:
        H.append('<p class="sub">Nessun post registrato ancora: dopo ogni post passa a Claude visualizzazioni, like e wishlist del giorno dopo.</p>')
    if rt and rt.get("subs"):
        sug = [x for an in rt["subs"].values() for x in an.get("suggestions", [])][:6]
        H.append(f'<h3>Reddit questa settimana ({esc(rt.get("generated_on", ""))})</h3><ul>' + "".join(f"<li>{inline(x)}</li>" for x in sug) + "</ul>")
    elif rt and rt.get("blocked"):
        H.append(f'<p class="note">Reddit: feed non leggibili il {esc(rt.get("generated_on", ""))} ({esc(", ".join(b["sub"] + " " + b["status"] for b in rt["blocked"][:4]))}): passi manuali nel documento delle ricerche manuali.</p>')
    H.append("</div>")
    return "".join(H)


def odds_section(root: str) -> str | None:
    """Honest odds: one card per decision with basis, label and the cross-check between sources (honest_odds.py)."""
    import honest_odds as ho
    cs = ho.cards(root, dt.date.today())
    if not cs:
        return None
    items = []
    for c in cs:
        cc = c.get("cross_check") or {}
        mark = state("pass", "Concordano") if cc.get("agree") else state("warn", "Non concordano") if cc.get("agree") is False else ""
        items.append(f'<div class="card tile"><div class="l">{esc(c["decision"])}</div><div class="v" style="font-size:1.3rem">{esc(c["odds"])}</div>'
                     f'<div class="d">{esc(c["label"])} · {esc(c["basis"])}</div>' + (f'<div class="d">{esc("; ".join(c["also"]))}</div>' if c.get("also") else "")
                     + f'<div class="d"><strong>Cosa la sposta:</strong> {esc(c["moves"])}</div>' + (f'<div class="d">{mark} {esc(cc.get("note", ""))}</div>' if cc.get("note") else "") + "</div>")
    return '<h2>Probabilità oneste, decisione per decisione</h2><div class="grid g2">' + "".join(items) + "</div>"


CLIP_STATE = {"todo": ("pending", "Da registrare"), "recorded": ("warn", "Registrata"), "posted": ("pass", "Pubblicata"), "retired": ("na", "Ritirata")}


def clips_kit_section(root: str, today: dt.date) -> str | None:
    """'Clip da fare' (launch/clips.json, social_kit.py) with status todo / recorded / posted, and this week's ready-to-post kit."""
    p = os.path.join(root, "clips.json")
    reg = load_json(p) if os.path.exists(p) else None
    kits = _raw(root, "social_kit.json")
    if not (reg or kits):
        return None
    H = []
    if kits and kits.get("kits"):
        cur = next((k for k in kits["kits"] if dt.date.fromisoformat(k["week"]) <= today < dt.date.fromisoformat(k["week"]) + dt.timedelta(days=7)), None) \
            or next((k for k in kits["kits"] if dt.date.fromisoformat(k["week"]) > today), None)
        if cur:
            rows = []
            for x in cur["posts"]:
                if x["kind"] == "video":
                    when = ", ".join(f'{SOCIAL_NAMES.get(s_["platform"], s_["platform"])} {fmt_date(s_["date"])} {esc(s_["time"])}' for s_ in x["slots"])
                    rows.append(f'<tr><td>{esc(x["clip"])} {esc(x["title"])}</td><td>{esc(x["hooks"][x["use_hook"]])}</td><td>{when}</td><td>{state(*CLIP_STATE.get(x.get("status"), ("info", x.get("status") or "")))}</td></tr>')
                else:
                    rows.append(f'<tr><td>Reddit {esc(x["subreddit"])}</td><td>{esc(x["title"])}</td><td>{fmt_date(x["date"])} {esc(x["time"])}</td><td></td></tr>')
            H.append(f'<h2>Kit social della settimana</h2><div class="card"><p class="sub">Settimana del {fmt_date(cur["week"])}' + (" · prima della pagina Steam: profilo e prova dei testi d'apertura" if cur.get("pre_page") else " · link Steam con UTM") + "</p>"
                     f'<div class="wrap"><table><thead><tr><th>Post</th><th>Testo nei primi 2 s</th><th>Dove e quando</th><th>Clip</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
                     f'<p class="note">Il kit completo della settimana (didascalie, hashtag, regole Reddit, riga per i numeri) è nel documento del kit del {fmt_date(cur["week"])}. Circa 2-3 ore a settimana.</p></div>')
    if reg and reg.get("clips"):
        cl = reg["clips"]
        cnt = {k: sum(1 for c in cl if c.get("status") == k) for k in CLIP_STATE}
        rows = "".join(f'<tr><td>{esc(c["id"])}</td><td>{esc(c["title"])}</td><td>{state(*CLIP_STATE.get(c.get("status"), ("info", c.get("status") or "")))}</td>'
                       f'<td class="n">{esc(c.get("length_s"))} s</td><td>{esc((c.get("record") or {}).get("scene", ""))}</td><td>{esc(c.get("file") or "—")}</td></tr>' for c in cl)
        H.append(f'<h2>Clip da fare</h2><div class="card"><p>{len(cl)} clip con storyboard completo · da registrare <strong>{cnt["todo"]}</strong> · registrate {cnt["recorded"]} · pubblicate {cnt["posted"]}.</p>'
                 f'<div class="wrap"><table><thead><tr><th>Clip</th><th>Cosa</th><th>Stato</th><th class="n">Durata</th><th>Dove si gira</th><th>File</th></tr></thead><tbody>{rows}</tbody></table></div>'
                 '<p class="note">Storyboard secondo per secondo, inquadrature, testi, audio e come registrarla: documento «Clip da fare» qui sotto. Quando una clip è registrata o pubblicata dillo a Claude, che ne aggiorna lo stato.</p></div>')
    return "".join(H)


def build(root: str, audience: str, include: list[str], exclude: list[str], hide: set[str], today: dt.date) -> str:
    st = load_json(os.path.join(root, "status.json")) if os.path.exists(os.path.join(root, "status.json")) else {}
    hide = set(hide) | HIDE_BY_AUDIENCE[audience]
    owner = cr.load_owner(root)
    match = issue_matcher(root, st, owner)
    labels = {k: d.get("label", k) for w in rc.wave_files(root) for k, d in (w.get("_defined") or {}).items()}
    wl_a, wl_svg = wishlist_section(root, today)
    fg_rows, fg_svg = timeline_section(root)
    econ = load_json(os.path.join(root, "_raw", "econ.json")) if os.path.exists(os.path.join(root, "_raw", "econ.json")) and "economics" not in hide else None
    cal_path = os.path.join(root, "calendar.md")
    cal_md = open(cal_path, encoding="utf-8").read() if os.path.exists(cal_path) else ""
    plan = ps.parse(cal_md) if cal_md else dict(phases=[])
    kit = load_json(os.path.join(root, "store_kit.json")) if os.path.exists(os.path.join(root, "store_kit.json")) and "storekit" not in hide else None
    cont_html, cont_alerts = (None, []) if "contingencies" in hide else contingency_section(root, today)
    watch_html, watch_alerts = (None, []) if "watchlist" in hide else watch_section(root, today)
    sec = []   # (tab, html chunk)
    add = lambda tab, chunk: chunk and sec.append((tab, chunk))
    product = st.get("product") or {}
    v = st.get("verdict") or {}
    mk = mp.load(root, today)
    crit_pre = None
    if "critiques" not in hide:
        try:
            _, crit_pre = cr.build(root, st, GATE_NAMES)
        except Exception:  # noqa: BLE001
            crit_pre = None
    lk, lw = LIGHT.get(str(v.get("color", "")).lower(), ("info", str(v.get("color", "n/d"))))
    beta_rows = [r for r in (fg_rows or []) if (r.get("_stage") or "beta") != "full"]
    gate_thr = None
    if beta_rows:
        try:
            gate_thr = float(str(beta_rows[-1].get("gate") or "").replace(",", "."))
        except ValueError:
            gate_thr = None
    add("riepilogo", mp.hero(mk, st, fg_rows or [], crit_pre, plan, ({"pass": "ok", "fail": "crit"}.get(lk, lk), lw), gate_thr))
    rm = None if "roadmap" in hide else cv.roadmap(root, st, plan, today)
    add("riepilogo", cv.roadmap_html(rm, today))
    if v:
        kind, word = LIGHT.get(str(v.get("color", "")).lower(), ("info", str(v.get("color", "n/d"))))
        risks = []
        for k, r in enumerate(v.get("risks", [])[:3], 1):
            text, keys = (r.get("text", ""), r.get("issues") or []) if isinstance(r, dict) else (r, [])
            keys = keys or match(text)
            risks.append(f"<li>{state('warn', f'Rischio {k}')}<span>{esc(text)}{badges_for(keys, owner, labels)}</span></li>")
        add("riepilogo", f'<details class="card verdict"><summary><strong>Verdetto del semaforo: {esc(word)}{" (provvisorio)" if v.get("provisional") else ""}</strong> · dettaglio, rischi e cancelli</summary><div><div>{ICONS[kind][0]}</div>'
            f'<p>{esc(v.get("summary", ""))}</p>' + (f'<p class="sub">Probabilità stimata di recuperare i costi: {esc(v["probability"])}</p>' if v.get("probability") else "")
            + (f'<ul class="clean">{"".join(risks)}</ul>' if risks else "")
            + ('<div class="gates">' + "".join(f'<span>{state({"pass": "pass", "fail": "fail", "pending": "pending"}.get(g.get("state"), "na"), GATE_NAMES.get(k, "Gate " + k))}</span>' for k, g in (st.get("gates") or {}).items()) + "</div>" if st.get("gates") else "")
            + "</div></details>")
    if plan["phases"] and "steps" not in hide:
        add("riepilogo", now_block(plan, today))
    add("riepilogo", mp.riepilogo_card(mk, fg_rows or []))
    if "odds" not in hide:
        try:
            add("riepilogo", odds_section(root))
        except Exception as e:  # noqa: BLE001
            log(f"WARN odds: {e}")
    tiles = key_tiles(st, wl_a, fg_rows, plan, econ, today, hide)
    gates = st.get("gates") or {}
    if tiles:
        add("riepilogo", '<h2>Numeri chiave</h2><div class="grid g4">' + "".join(f'<div class="card tile"><div class="l">{esc(l)}</div><div class="v">{esc(val)}</div><div class="d">{esc(d)}</div></div>' for l, val, d in tiles) + "</div>")
    alerts = [(x["level"], x["text"]) for x in (wl_a or {}).get("alerts", [])] + cont_alerts + watch_alerts
    fr = sk.freshness(root) if kit else {}
    if fr.get("stale"):
        alerts.append(("ATTENZIONE", f"Pagine store da aggiornare: il kit è del {fr['kit_date']}, dopo sono arrivati " + "; ".join(f"{w} ({d})" for w, d in fr["newer"])))
    if alerts:
        icon = {"ALARM": ("fail", "Allarme"), "ATTENZIONE": ("warn", "Attenzione"), "INFO": ("info", "Info")}
        add("riepilogo", '<h2>Alert</h2><div class="card"><ul class="clean">' + "".join(f"<li>{state(*icon[lv])}<span>{esc(t)}</span></li>" for lv, t in sorted(alerts, key=lambda x: ["ALARM", "ATTENZIONE", "INFO"].index(x[0]))) + "</ul></div>")
    if wl_svg or fg_svg:
        chunk = ["<h2>Andamento</h2><div class=\"grid g2\">"]
        if wl_svg:
            chunk.append(f'<div class="card"><h3>Wishlist contro gli scenari</h3><div class="legend"><span><i style="border-color:var(--s1)"></i>Registrate</span><span><i style="border-color:var(--muted)"></i>Percorso degli scenari (lineare)</span></div>{wl_svg}'
                         '<p class="note">Wishlist inserite a mano da Steamworks. I percorsi sono lineari: semplificazione, i picchi (festival, lancio) non sono previsti.</p></div>')
        if fg_svg:
            chunk.append(f'<div class="card"><h3>Focus group simulato, per ondata</h3><div class="legend"><span><i style="border-color:var(--s1)"></i>Beta</span><span><i style="border-color:var(--muted)"></i>Gioco completo (rombi) e soglia</span><span><i style="border-color:var(--good)"></i>Tetto (rombo verde)</span></div>{fg_svg}<p class="note">Panel simulato con gli stessi tester: ordina i problemi, non prevede le vendite. Beta e gioco completo non si confrontano tra loro.</p></div>')
        chunk.append("</div>")
        add("riepilogo", "".join(chunk))
    it = st.get("intentions") or {}
    if it and "intentions" not in hide:
        rows = "".join(f'<tr><td>{esc(d.get("topic"))}</td><td>{esc(d.get("choice"))}</td><td>{esc(d.get("why", ""))}</td></tr>' for d in it.get("decisions", []))
        add("riepilogo", f'<h2>Profilo decisionale</h2><details class="card"><summary>{esc(it.get("summary", "") or "Le tue scelte")}</summary>' + (f'<div class="wrap"><table><thead><tr><th>Tema</th><th>Scelta</th><th>Perché</th></tr></thead><tbody>{rows}</tbody></table></div>' if rows else "") + "</details>")

    # ---- charts by group, placed in their tab
    gs = []
    if "charts" not in hide:
        gs = [g for g in rc.groups(root, today) if g["key"] != "criticita"]
        if audience == "publisher":
            gs = [g for g in gs if g["key"] in ("fg", "market", "reviews", "window")]
    G = {g["key"]: g for g in gs}

    # ---- Gioco e test
    if "product" in G:
        add("gioco", render_group(dict(G["product"], title="Pilastri: dove regge il gioco", intro="Pilastro per pilastro: come sta oggi, perché, e cosa fare dove non regge.")))
    crit_data = None
    if "critiques" not in hide:
        crit_html, crit_data = cr.build(root, st, GATE_NAMES)
        if crit_html:
            add("gioco", "<h2>Criticità, ondata per ondata</h2>" + crit_html)
    if "fg" in G:
        add("gioco", render_group(G["fg"]))
    add("gioco", mp.gioco_card(mk))
    if "fgwaves" not in hide:
        add("gioco", waves_section(root))
    if "reviews" in G:
        add("gioco", render_group(G["reviews"]))
    if st.get("full_game") and "fullgame" not in hide:
        add("gioco", full_game_section(st["full_game"]) + ("".join(f'<div class="card" style="margin-top:12px">{c}</div>' for c in G["fullgame"]["charts"]) if "fullgame" in G else ""))

    # ---- Marketing e social: at a glance on top (marketing_glance.py), everything else folded below
    mk_glance = None if "social" in hide else mg.glance(root, plan, today, wl_a, ps=ps)
    fold = mg.wrap_fold if mk_glance else (lambda c, n="": c)
    if mk_glance:
        add("marketing", mk_glance[0])
    add("marketing", fold(mp.marketing_card(mk)))
    if kit:
        add("marketing", fold(kit_section(kit, root), " · ".join(t for k_, t in (("steam", "Steam"), ("itch", "itch.io")) if kit.get(k_))))
    if "social" not in hide:
        add("marketing", "".join(fold(x) for x in re.split(r"(?=<h2>)", clips_kit_section(root, today) or "") if x) or None)
        add("marketing", fold(social_section(root, today)))
    if "creators" not in hide:
        c = creators_section(root)
        if c:
            add("marketing", fold(c + ("".join(f'<div class="card" style="margin-top:12px">{x}</div>' for x in G["creators"]["charts"]) if "creators" in G else "")))
    if mk_glance:
        for x in mk_glance[1]:
            add("marketing", x)

    if "trailer" not in hide:
        add("trailer", tk.status_section(root, esc, copy_btn))

    # ---- Piano e soldi
    if plan["phases"] and "steps" not in hide:
        add("piano", steps_section(plan, today) + ("".join(f'<div class="card" style="margin-top:12px">{x}</div>' for x in G["plan"]["charts"]) if "plan" in G else ""))
    if "todo" not in hide:
        add("piano", todo_section(root, today))
    if gates:
        add("piano", '<h2>Cancelli Go / No-Go</h2><div class="grid g4">' + "".join(
            f'<div class="card"><div>{state({"pass": "pass", "fail": "fail", "pending": "pending"}.get(g.get("state"), "na"))}</div><h3>{esc(GATE_NAMES.get(k, "Gate " + k))}</h3><p class="note">{esc(g.get("note", ""))}</p></div>'
            for k, g in gates.items()) + "</div>")
    if cal_md and "calendar" not in hide:
        rest = (plan.get("before", "") + "\n" + plan.get("after", "")) if plan["phases"] else cal_md
        if rest.strip():
            add("piano", f'<h2>Date fisse e piano a ritroso</h2><details class="card doc"><summary><strong>calendar.md</strong></summary>{md_to_html(rest)}</details>')
    if econ:
        add("piano", '<h2>Economia</h2><div class="card wrap"><table><thead><tr><th>Scenario</th><th class="n">Wishlist</th><th class="n">Copie</th><th class="n">Netto</th><th class="n">Utile (cassa)</th></tr></thead><tbody>' + "".join(
            f'<tr><td>{esc(s_["name"])}</td><td class="n">{fmt_n(s_["wishlists"])}</td><td class="n">{fmt_n(s_["copies"])}</td><td class="n">{fmt_n(s_["net"])}</td><td class="n">{fmt_n(s_["profit_cash"])}</td></tr>' for s_ in econ["scenarios"])
            + f'</tbody></table><p class="note">Netto per copia {econ["net_per_copy"]:.2f}; aliquote e conversioni sono ipotesi dichiarate nel piano, da verificare.</p></div>'
            + ('<div class="cgrid" style="margin-top:12px">' + "".join(f'<div class="card">{x}</div>' for x in G["econ"]["charts"]) + "</div>" if "econ" in G else ""))
    elif "econ" in G:
        add("piano", render_group(G["econ"]))
    add("piano", mp.piano_card(mk, econ))
    if "publisher" not in hide:
        add("piano", publisher_section(root, st))
    add("piano", cont_html)
    if "window" not in hide:
        wsec = window_section(root)
        add("piano", (wsec or "") + ('<div class="cgrid" style="margin-top:12px">' + "".join(f'<div class="card">{x}</div>' for x in G["window"]["charts"]) + "</div>" if "window" in G else "") if (wsec or "window" in G) else None)
    add("piano", watch_html)
    if "steamdb" not in hide:
        add("piano", steamdb_section(root))
    if "market" in G:
        add("piano", render_group(dict(G["market"], title="Mercato e comparabili")))

    # ---- Calendario: month grids from today to the launch, every dated item, click a day for the details
    if "calendar" not in hide and audience != "publisher":
        items = cv.collect(root, plan, st, today, tt.parse(os.path.join(root, "TODO.md")) if "todo" not in hide else None)
        if rm:
            for m_ in rm["milestones"]:
                it = cv.item(m_.get("date"), "Traguardo: " + m_["title"], "traguardo", end=m_.get("end"), source="Roadmap (status.json)", step=m_.get("step"),
                             approx=bool(m_.get("approx")), details="")
                if it:
                    it.pop("details", None)
                    it["html"] = "<br>".join(cv.rich(x) for x in (m_.get("what"), ("Serve: " + m_["needs"]) if m_.get("needs") else "") if x)
                    items.append(it)
            items.sort(key=lambda x: (x["date"], {"lancio": 0, "traguardo": 1, "scadenza": 2}.get(x["kind"], 5), x["title"]))
        launch_d = next((dt.date.fromisoformat(x["date"]) for x in items if x["kind"] == "lancio"), None)
        if items:
            add("calendario", cv.roadmap_html(rm, today, compact=True) + cv.calendar_html(items, rm, today, launch_d))

    # ---- Mercato reale
    for chunk in mp.tab(mk, root):
        add("mercato", chunk)

    # ---- documents, each in the tab it belongs to; the rest + Q&A in Documenti
    stems = [x for x in (include or AUDIENCES[audience]) if x not in exclude]

    def hook(cells):
        return badges_for(match(cells[0]) if cells else [], owner, labels)
    per_tab: dict = {}
    for stem in stems:
        pth = os.path.join(root, f"{stem}.md")
        if os.path.exists(pth):
            tab = DOC_TAB.get(stem, "docs")
            per_tab.setdefault(tab, []).append(f'<details class="card doc"><summary><strong>{esc(DOCS.get(stem, stem))}</strong> <span class="note">{esc(stem)}.md</span></summary>{md_to_html(open(pth, encoding="utf-8").read(), hook)}</details>')
    for tab in ("gioco", "marketing", "piano"):
        if per_tab.get(tab):
            add(tab, "<h2>Documenti di questa parte</h2>" + "".join(per_tab[tab]))
    if per_tab.get("docs"):
        add("docs", "<h2>Documenti</h2>" + "".join(per_tab["docs"]))
    if "qa" not in hide:
        jload = lambda *p_: load_json(os.path.join(root, *p_)) if os.path.exists(os.path.join(root, *p_)) else None
        add("docs", qamod.build(root, dict(st=st, wl_a=wl_a, econ=econ, window=jload("_raw", "window.json"), crit=crit_data, plan=plan, today=today, gate_names=GATE_NAMES,
                                           contingencies=(jload("_raw", "contingencies.json") or {}).get("scenarios") if "contingencies" not in hide else None)))

    # ---- anchors, glossary, tabs
    body_html, heads, own_ids, tabs_of = [], [], [], []
    for tab, chunk in sec:   # every <h2> gets an anchor
        mine = set()

        def anchor(m):
            heads.append((tab, re.sub(r"<[^>]+>", "", m.group(1))))
            mine.add(f"sec{len(heads)}")
            return f'<h2 id="sec{len(heads)}">{m.group(1)}</h2>'
        body_html.append(re.sub(r"<h2>(.*?)</h2>", anchor, chunk))
        own_ids.append(mine)
        tabs_of.append(tab)
    anchors = gl.anchors_for([(f"sec{i}", h) for i, (_, h) in enumerate(heads, 1)])
    used: set = set()
    body_html = [weblinks.linkify_html(qamod.resolve_links(c, anchors)) for c in body_html]   # every URL clickable, before the glossary
    chunks = [gl.enrich(c, anchors, own, used) for c, own in zip(body_html, own_ids)]   # plain-Italian tooltips and links to the section that deals with the thing
    glo = gl.glossary_html(used)
    n_now = sum(1 for x in (crit_data or {}).get("issues", []) if x.get("now"))
    n_late = ps.summary(plan, today)["overdue"] if plan["phases"] else 0
    panels, buttons = [], []
    for tab, title, icon in TABS:
        mine = [c for c, t in zip(chunks, tabs_of) if t == tab]
        if tab == "docs" and glo:
            mine.append(glo)
        if not mine:
            continue
        hs = [(i, h) for i, (t, h) in enumerate(heads, 1) if t == tab]
        idx = ('<nav class="toc" aria-label="In questa scheda">' + "".join(f'<a href="#sec{i}">{esc(h)}</a>' for i, h in hs) + "</nav>") if len(hs) > 2 else ""
        cnt = f' <span class="cnt" title="Criticità da fare adesso">{n_now}</span>' if tab == "gioco" and n_now else ""
        if tab == "calendario" and n_late:
            cnt = f' <span class="cnt late" title="Cose in ritardo">{n_late}</span>'
        buttons.append(f'<button type="button" role="tab" id="tab-{tab}" aria-controls="p-{tab}" aria-selected="{"true" if not buttons else "false"}" tabindex="{0 if not buttons else -1}">'
                       f'<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">{icon}</svg><span>{esc(title)}</span>{cnt}</button>')
        panels.append(f'<section role="tabpanel" id="p-{tab}" aria-labelledby="tab-{tab}"{"" if len(panels) == 0 else " hidden"}><p class="sub" style="margin-top:12px">{esc(TAB_INTRO[tab])}</p>{idx}{"".join(mine)}</section>')
    nav = f'<div class="tabs" role="tablist" aria-label="Parti della pagina">{"".join(buttons)}</div>' if len(buttons) > 1 else ""
    name = st.get("game") or os.path.basename(os.path.dirname(os.path.abspath(root))) or "Progetto"
    label = {"private": "Uso interno", "partner": "Per i soci", "publisher": "Per il publisher"}[audience]
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stato del lancio, {esc(name)}</title>'
            f'<script>{THEME_HEAD}</script><style>{CSS}{mp.CSS}{CSS_POLISH}{cv.CSS}{mg.CSS}{CSS_V3}</style></head><body><main><div class="top"><div><h1>{esc(name)}: stato del lancio</h1><p class="sub">Aggiornato il {fmt_date(today.isoformat())}{(" · analisi del " + fmt_date(st["updated"])) if st.get("updated") and str(st["updated"])[:10] != today.isoformat() else ""} · {esc(label)}'
            f'{" · modalità " + esc(st["mode"]) if st.get("mode") else ""}{" · valutato come: " + esc(product.get("label") or product.get("kind")) if product.get("kind") or product.get("label") else ""}</p><p class="sub">Questo è il <strong>cruscotto</strong>: cosa fare, numeri, pagine da copiare, piani. Il report completo da leggere con calma è il file REPORT.md nella cartella del lancio.</p></div><button class="theme" id="theme" type="button" title="Cambia tema chiaro o scuro"><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1.5a6.5 6.5 0 010 13z" fill="currentColor"/></svg><span>Tema</span></button></div>'
            + nav + "".join(panels) + f'<footer class="note">Pagina generata da <code>status_page.py</code> il {today.isoformat()} da file locali, senza richieste di rete. Il focus group è simulato: non è un dato di mercato. '
            f'Cifre con fonte nei documenti; ciò che è etichettato [DA VERIFICARE] resta da verificare.</footer></main><script>{JS}{THEME_JS}{gl.JS}{cr.JS}{qamod.JS}{cv.JS}</script></body></html>')


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
