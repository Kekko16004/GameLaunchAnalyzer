#!/usr/bin/env python3
"""REPORT.md as one illustrated, self-contained HTML page: launch/REPORT.html.

The Markdown report stays the source of truth (and what the skill writes). This tool reads it and the data files in
`launch/`, and produces a page where each section of the report carries its own charts next to the text:
  Audit / pillars        pillars by grade, hours to reach PASS
  Critiques / waves      tester verdicts per wave, latest-wave indicators, most frequent criticisms, real review themes
  Market / price         genre by year and price band, comparables, trailer length, economics (price -> net, scenarios vs break-even)
  Platforms / calendar   steps by phase, wishlist and focus-group trend lines
  Creators               creators by platform and priority
  Full game              hours to close each gap
A chart group that matches no section goes to an "Quadro d'insieme" block at the top. At the top there are also the
verdict and the key numbers of `status.json`. Charts follow the light/dark theme, have a hover tooltip, a legend and a
table view, and print cleanly. No network, no external scripts. The page contains strategy: do not share it blindly.

  python report_html.py [--launch-dir launch] [-o launch/REPORT.html] [--hide-charts economics,...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re

from common import load_json, log
import glossary as gl
import report_charts as rc
import status_page as sp

MATCH = [  # chart group -> section titles it belongs next to (first matching section wins)
    ("product", r"audit|pilastr"),
    ("fg", r"critich|ondat|focus"),
    ("reviews", r"critich|recension"),
    ("market", r"mercato|comparabil"),
    ("econ", r"prezz|economi|mercato"),
    ("plan", r"piattaform|calendario|gate|cancell"),
    ("window", r"piattaform|calendario|gate|cancell|lancio"),
    ("creators", r"creator"),
    ("fullgame", r"gioco completo|beta oggi"),
]
EXTRA_CSS = """
.toc{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 4px}.toc a{border:1px solid var(--ring);border-radius:999px;padding:3px 12px;font-size:.85rem;text-decoration:none;color:var(--ink2);background:var(--surface)}
.toc a:hover{border-color:var(--s1);color:var(--ink)}details.sec>summary{font-size:1.1rem;padding:4px 0}details.sec .inner{margin-top:8px}.charts{margin-top:16px;border-top:1px solid var(--grid);padding-top:4px}
@media print{body{background:#fff}.top button,.toc{display:none}details.sec{break-inside:avoid-page}details.sec:not([open])>*:not(summary){display:block}}
"""


def split_sections(md: str) -> tuple[str, list[tuple[str, str]]]:
    parts = re.split(r"(?m)^## ", md.replace("\r", ""))
    return parts[0], [(p.split("\n", 1)[0].strip(), p.split("\n", 1)[1] if "\n" in p else "") for p in parts[1:]]


def build(root: str, today: dt.date, hide: set[str]) -> str:
    rp = os.path.join(root, "REPORT.md")
    if not os.path.exists(rp):
        raise SystemExit(f"{rp} not found: write the report first (references/06-synthesis-output.md)")
    head_md, secs = split_sections(open(rp, encoding="utf-8").read())
    st = load_json(os.path.join(root, "status.json")) if os.path.exists(os.path.join(root, "status.json")) else {}
    groups = {g["key"]: g for g in rc.groups(root, today) if g["key"] not in hide}
    placed: dict[int, list[dict]] = {}
    for key, rx in MATCH:
        if key not in groups:
            continue
        for i, (title, _) in enumerate(secs):
            if re.search(rx, title, re.I):
                placed.setdefault(i, []).append(groups.pop(key))
                break
    top = []
    v = st.get("verdict") or {}
    if v:
        kind, word = sp.LIGHT.get(str(v.get("color", "")).lower(), ("info", str(v.get("color", "n/d"))))
        risks = "".join(f"<li>{sp.state('warn', f'Rischio {k}')}<span>{sp.esc(r)}</span></li>" for k, r in enumerate(v.get("risks", [])[:3], 1))
        top.append(f'<section class="card verdict"><div>{sp.ICONS[kind][0]}</div><div><div class="big">Verdetto: {sp.esc(word)}{" (provvisorio)" if v.get("provisional") else ""}</div><p>{sp.esc(v.get("summary", ""))}</p>'
                   + (f'<p class="sub">Probabilità stimata di recuperare i costi: {sp.esc(v["probability"])}</p>' if v.get("probability") else "") + (f'<ul class="clean">{risks}</ul>' if risks else "") + "</div></section>")
    wl_a, wl_svg = sp.wishlist_section(root, today)
    fg_rows, fg_svg = sp.timeline_section(root)
    econ_path = os.path.join(root, "_raw", "econ.json")
    cal_path = os.path.join(root, "calendar.md")
    plan = sp.ps.parse(open(cal_path, encoding="utf-8").read()) if os.path.exists(cal_path) else dict(phases=[])
    tiles = sp.key_tiles(st, wl_a, fg_rows, plan, load_json(econ_path) if os.path.exists(econ_path) else None, today, set())
    if tiles:
        top.append('<div class="grid g4" style="margin-top:12px">' + "".join(f'<div class="card tile"><div class="l">{sp.esc(l)}</div><div class="v">{sp.esc(val)}</div><div class="d">{sp.esc(d)}</div></div>' for l, val, d in tiles) + "</div>")
    trend = ""
    if wl_svg:
        trend += f'<div class="card"><h3>Wishlist contro gli scenari</h3>{wl_svg}</div>'
    if fg_svg:
        trend += f'<div class="card"><h3>Punteggio del focus group, per ondata</h3>{fg_svg}</div>'
    if trend:
        top.append(f'<h2 id="trend">Andamento</h2><div class="cgrid">{trend}</div>')
    if groups:
        top.append("<h2 id=\"overview\">Quadro d'insieme</h2>" + rc.render(list(groups.values())))
    body = []
    for i, (title, text) in enumerate(secs):
        charts = rc.render(placed.get(i, []))
        body.append(f'<details class="card doc sec" id="s{i}" open><summary><strong>{sp.esc(title)}</strong></summary><div class="inner">{sp.md_to_html(text)}'
                    + (f'<div class="charts">{charts}</div>' if charts else "") + "</div></details>")
    present = "".join(top)
    heads = [(i, t) for i, t in (("trend", "Andamento"), ("overview", "Quadro d'insieme")) if f'id="{i}"' in present] + [(f"s{i}", t) for i, (t, _) in enumerate(secs)]
    anchors = gl.anchors_for(heads)
    used: set = set()
    own_top = lambda c: {x for x in ("trend", "overview") if f'id="{x}"' in c}
    top = [gl.enrich(c, anchors, own_top(c), used) for c in top]   # plain-Italian tooltips and links to the section that deals with the thing
    body = [gl.enrich(c, anchors, {f"s{i}"}, used) for i, c in enumerate(body)]
    glo = gl.glossary_html(used)
    title_line = re.search(r"(?m)^# (.+)$", head_md)
    name = st.get("game") or (title_line.group(1).strip() if title_line else "Report")
    strip_no = lambda t: re.sub(r"^\d+\.\s*", "", t)
    toc = '<nav class="toc" aria-label="Sezioni">' + "".join(f'<a href="#s{i}">{sp.esc(strip_no(t))}</a>' for i, (t, _) in enumerate(secs)) + "</nav>"
    product = st.get("product") or {}
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Report di lancio, {sp.esc(name)}</title>'
            f'<style>{sp.CSS}{EXTRA_CSS}</style></head><body><main><div class="top"><div><h1>{sp.esc(name)}: report di lancio</h1><p class="sub">Generato il {sp.fmt_date(today.isoformat())}'
            f'{" · valutato come: " + sp.esc(product.get("label") or product.get("kind")) if product.get("kind") or product.get("label") else ""}</p><p class="sub">Questo è il <strong>report completo</strong>, da leggere. Per cosa fare adesso, i passi, le pagine da copiare e i piani usa il cruscotto <a href="STATUS.html">STATUS.html</a>.</p></div>'
            f'<button class="theme" id="theme" type="button">Tema chiaro / scuro</button></div>{toc}'
            + "".join(top) + "<h2>Il report</h2>" + "".join(body) + glo
            + f'<footer class="note">Pagina generata da <code>report_html.py</code> da <code>REPORT.md</code> e dai dati in <code>launch/</code>, senza richieste di rete. Il focus group è simulato: non è un dato di mercato. '
              f'Contiene strategia: non condividerla senza averla letta. Ciò che è etichettato [DA VERIFICARE] resta da verificare.</footer></main><script>{sp.JS}{gl.JS}</script></body></html>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("-o", "--out")
    ap.add_argument("--hide-charts", default="", help="comma list of chart groups to leave out: product,fg,market,reviews,window,econ,plan,creators,fullgame")
    ap.add_argument("--today", help="override today (YYYY-MM-DD)")
    a = ap.parse_args()
    page = build(a.launch_dir, dt.date.fromisoformat(a.today) if a.today else dt.date.today(), {x for x in a.hide_charts.split(",") if x})
    out = a.out or os.path.join(a.launch_dir, "REPORT.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    log(f"wrote {out} ({len(page) // 1024} KB). Local file: nothing was published.")


if __name__ == "__main__":
    main()
