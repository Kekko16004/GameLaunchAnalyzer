#!/usr/bin/env python3
"""Inline SVG charts, stdlib only, shared by status_page.py, report_html.py and charts_export.py.

Every function returns an HTML string: <div class="chart"> with an <svg> (colors are CSS variables, so the same chart
follows the light/dark theme of the page), invisible hit areas for the hover tooltip (the page script reads data-tip /
data-x), direct value labels, a legend whenever there are two or more series, and a "Vista tabella" with the numbers.
`standalone_svg(html)` turns one chart into a self-contained .svg file with fixed light colors, so it can be dropped
into a Markdown report or a slide: `![](charts/x.svg)`.

Rules followed (data-viz method): one axis (no dual axes), 2px lines, thin bars anchored to the baseline with the data
end rounded, a 2px gap between stacked segments, text in ink colors (never in the series color), status colors always
paired with a word, no number on every point except where the bar is the point.
Colors: --s1 blue, --s2 orange, --s3 aqua, --s4 yellow (categorical, in this order); --good/--warn/--crit for status.
"""
from __future__ import annotations

import html
import re

W = 520   # viewBox width: charts sit in cards about 480 px wide, so text keeps close to 1:1
SERIES = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]
TOKENS_LIGHT = {"bg": "#fcfcfb", "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7",
                "ring": "#e1e0d9", "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "s4": "#eda100", "good": "#0ca30c", "warn": "#fab219", "crit": "#d03b3b"}

CSS = ("--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;", "--s2:#d95926;--s3:#199e70;--s4:#c98500;")   # (light, dark) additions to the page tokens
CHART_CSS = """
.chart text{font-family:inherit}.chart .cap{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink2);font-size:.85rem;margin:2px 0 6px}
.lg{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink2);font-size:.85rem;margin:4px 0 8px}.lg span{display:inline-flex;align-items:center;gap:6px}.lg i{display:inline-block;width:12px;height:12px;border-radius:3px}
.chartbox h3{margin:0 0 2px}.chartbox .why{color:var(--muted);font-size:.85rem;margin:0 0 8px}.chartbox{min-width:0}
.cgrid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(440px,100%),1fr))}
@media print{.chart .tip{display:none!important}}
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def fmt_n(n) -> str:
    return "n/d" if n is None else f"{int(round(n)):,}".replace(",", ".")


def fmt_pct(v) -> str:
    return "n/d" if v is None else f"{v:.0f}%"


def nice_axis(lo: float, hi: float, max_intervals: int = 5) -> tuple[float, float, float]:
    span = hi - lo if hi > lo else (abs(hi) or 1.0)
    raw = span / max_intervals
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 10 ** -(len(str(int(1 / raw))))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    lo2, hi2 = (lo // step) * step, -(-hi // step) * step
    return lo2, hi2, step


def table_view(headers: list[str], rows: list[list]) -> str:
    head = "".join(f'<th{" class=n" if k else ""}>{esc(h)}</th>' for k, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td{" class=n" if k else ""}>{esc(c)}</td>' for k, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<details><summary>Vista tabella</summary><div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>'


def legend(items: list[tuple[str, str]]) -> str:
    return '<div class="lg">' + "".join(f'<span><i style="background:{c}"></i>{esc(l)}</span>' for l, c in items) + "</div>"


def wrap(svg: str, *, title: str = "", why: str = "", leg: str = "", table: str = "", note: str = "") -> str:
    """A titled card body: title, one line saying what to read, legend, the chart, the table view and a note."""
    return (f'<div class="chartbox">' + (f"<h3>{esc(title)}</h3>" if title else "") + (f'<p class="why">{esc(why)}</p>' if why else "") + leg
            + f'<div class="chart">{svg}<div class="tip" role="status"></div></div>{table}' + (f'<p class="note">{esc(note)}</p>' if note else "") + "</div>")


def _short(s: str, n: int = 30) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _bar_path(x0: float, x1: float, y: float, h: float, r: float = 4) -> str:
    """Horizontal bar from x0 (baseline, square) to x1 (data end, rounded), either direction."""
    if abs(x1 - x0) < 0.5:
        return f"M{x0:.1f},{y:.1f}h1v{h:.1f}h-1z"
    d = 1 if x1 > x0 else -1
    r = min(r, abs(x1 - x0), h / 2)
    return (f"M{x0:.1f},{y:.1f}H{x1 - d * r:.1f}a{r:.1f},{r:.1f} 0 0 {1 if d > 0 else 0} {d * r:.1f},{r:.1f}V{y + h - r:.1f}"
            f"a{r:.1f},{r:.1f} 0 0 {1 if d > 0 else 0} {-d * r:.1f},{r:.1f}H{x0:.1f}z")


def hbar(items: list[dict], *, aria: str, fmt=fmt_n, unit: str = "", ref: tuple[float, str] | None = None, label_w: int = 150, vmax: float | None = None) -> tuple[str, str]:
    """items: {label, value, tip?, color?}. Signed values draw left/right of a zero line. Returns (svg, table_html)."""
    n, rh, T = len(items), 30, 14 if ref else 6
    vals = [i["value"] for i in items if i["value"] is not None]
    lo, hi = min(vals + [0]), max(vals + [ref[0] if ref else 0, vmax or 0, 1e-9])
    R = 58
    px0, px1 = label_w + (46 if lo < 0 else 0), W - R   # signed values: room on the left for the value label of negative bars
    sx = lambda v: px0 + (v - lo) / (hi - lo) * (px1 - px0)
    H = T + n * rh + 8
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    zero = sx(0)
    g.append(f'<line x1="{zero:.1f}" x2="{zero:.1f}" y1="{T - 4}" y2="{H - 6}" stroke="var(--axis)" stroke-width="1"/>')
    if ref:
        rx = sx(ref[0])
        g.append(f'<line x1="{rx:.1f}" x2="{rx:.1f}" y1="{T - 4}" y2="{H - 6}" stroke="var(--ink2)" stroke-width="1.5" stroke-dasharray="4 3"/>'
                 f'<text x="{rx:.1f}" y="9" text-anchor="middle" font-size="11" fill="var(--ink2)">{esc(ref[1])}</text>')
    for k, it in enumerate(items):
        y = T + k * rh
        v = it["value"]
        g.append(f'<text x="{label_w - 10}" y="{y + rh / 2 + 4:.1f}" text-anchor="end" font-size="12" fill="var(--ink2)">{esc(_short(it["label"], 24))}</text>')
        if v is None:
            g.append(f'<text x="{zero + 6:.1f}" y="{y + rh / 2 + 4:.1f}" font-size="12" fill="var(--muted)">n/d</text>')
            continue
        col = it.get("color") or "var(--s1)"
        bx = sx(v)
        g.append(f'<path d="{_bar_path(zero, bx, y + 5, rh - 10)}" fill="{col}"/>')
        tx, anchor = (bx + 6, "start") if v >= 0 else (bx - 6, "end")
        g.append(f'<text x="{tx:.1f}" y="{y + rh / 2 + 4:.1f}" text-anchor="{anchor}" font-size="12" font-weight="600" fill="var(--ink)" style="font-variant-numeric:tabular-nums">{esc(fmt(v))}{esc(unit)}</text>')
    for k, it in enumerate(items):
        if it["value"] is None:
            continue
        y = T + k * rh
        g.append(f'<rect class="hit" tabindex="0" x="0" y="{y}" width="{W}" height="{rh}" fill="transparent" data-x="{sx(it["value"]):.1f}" data-tip="{esc(it.get("tip") or (str(it["label"]) + ": " + fmt(it["value"]) + unit))}"/>')
    g.append("</svg>")
    table = table_view(["Voce", "Valore"], [[i["label"], "n/d" if i["value"] is None else fmt(i["value"]) + unit] for i in items])
    return "".join(g), table


def stacked(rows: list[dict], series: list[tuple[str, str, str]], *, aria: str, percent: bool = True, label_w: int = 100) -> tuple[str, str]:
    """rows: {label, values:{key: number}, tip?}. series: (key, label, color). 100% stacked bars with a 2px gap between segments;
    the share (100% bars) or the count (percent=False) of each segment is written under the bar in muted ink (never inside, never in the series color)."""
    rh, T = 48, 6
    n = len(rows)
    H = T + n * rh + 4
    px0, px1 = label_w, W - 12
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    allmax = max((sum(r["values"].get(k, 0) or 0 for k, _, _ in series) for r in rows), default=1) or 1
    table = []
    for i, r in enumerate(rows):
        y = T + i * rh
        tot = sum(r["values"].get(k, 0) or 0 for k, _, _ in series) or 1
        scale = (px1 - px0) * (1 if percent else tot / allmax)
        g.append(f'<text x="{label_w - 10}" y="{y + 18}" text-anchor="end" font-size="12" fill="var(--ink2)">{esc(_short(r["label"], 16))}</text>')
        x = px0
        tip = [r["label"]]
        trow = [r["label"]]
        for k, lab, col in series:
            v = r["values"].get(k, 0) or 0
            w = scale * v / tot
            share = 100 * v / tot
            tip.append(f"{lab}: {fmt_n(v)}" + (f" ({share:.0f}%)" if not percent or True else ""))
            trow.append(f"{fmt_n(v)} ({share:.0f}%)")
            if w > 0.5:
                g.append(f'<rect x="{x:.1f}" y="{y + 4}" width="{max(w - 2, 0.5):.1f}" height="22" rx="2" fill="{col}"/>')
                if share >= 6 or (not percent and v):   # counts when the bars are counts, shares when they are 100% bars
                    g.append(f'<text x="{x + w / 2 - 1:.1f}" y="{y + 40}" text-anchor="middle" font-size="11" fill="var(--ink2)" style="font-variant-numeric:tabular-nums">{f"{share:.0f}%" if percent else f"{v:g}"}</text>')
            x += w
        g.append(f'<rect class="hit" tabindex="0" x="{px0}" y="{y}" width="{px1 - px0}" height="{rh}" fill="transparent" data-x="{px0 + 10}" data-tip="{esc(r.get("tip") or chr(10).join(tip))}"/>')
        table.append(trow)
    g.append("</svg>")
    return "".join(g), table_view(["Voce"] + [l for _, l, _ in series], table)


def columns(items: list[dict], *, aria: str, fmt=fmt_n, unit: str = "", color: str = "var(--s1)") -> tuple[str, str]:
    """Vertical columns (one series): value above, label below."""
    n = len(items)
    L, R, T, B, H = 42, 10, 22, 34, 240
    vmax = max([i["value"] or 0 for i in items] + [1e-9])
    lo, hi, step = nice_axis(0, vmax)
    sy = lambda v: T + (1 - (v - lo) / (hi - lo)) * (H - T - B)
    slot = (W - L - R) / max(n, 1)
    bw = min(44, slot * 0.6)
    label_every = max(1, int(-(-44 // slot)))   # thin slots: label every k-th column
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    k = 0
    while lo + step * k <= hi + 1e-9:
        v = lo + step * k
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="var(--grid)"/><text x="{L - 8}" y="{sy(v) + 4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{fmt_n(v)}</text>')
        k += 1
    g.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(0):.1f}" y2="{sy(0):.1f}" stroke="var(--axis)"/>')
    for i, it in enumerate(items):
        cx = L + slot * (i + 0.5)
        v = it["value"]
        if v == 0 and it.get("stub"):   # a zero that must stay visible (e.g. a free week): a 4 px stub in its color
            g.append(f'<rect x="{cx - bw / 2:.1f}" y="{sy(0) - 4:.1f}" width="{bw:.1f}" height="4" rx="2" fill="{it.get("color") or color}"/>')
        if v is not None:
            top = sy(v)
            g.append(f'<path d="M{cx - bw / 2:.1f},{sy(0):.1f}V{top + 4:.1f}a4,4 0 0 1 4,-4H{cx + bw / 2 - 4:.1f}a4,4 0 0 1 4,4V{sy(0):.1f}z" fill="{it.get("color") or color}"/>')
            if slot >= 30 or it.get("show_value"):   # many thin columns: values live in the tooltip and the table view
                g.append(f'<text x="{cx:.1f}" y="{top - 6:.1f}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--ink)">{esc(fmt(v))}{esc(unit)}</text>')
        if i % label_every == 0:
            g.append(f'<text x="{cx:.1f}" y="{H - 12}" text-anchor="middle" font-size="11" fill="var(--muted)">{esc(_short(it["label"], 11))}</text>')
        g.append(f'<rect class="hit" tabindex="0" x="{cx - slot / 2:.1f}" y="{T}" width="{slot:.1f}" height="{H - T - B}" fill="transparent" data-x="{cx:.1f}" data-tip="{esc(it.get("tip") or (str(it["label"]) + ": " + ("n/d" if v is None else fmt(v) + unit)))}"/>')
    g.append("</svg>")
    return "".join(g), table_view(["Voce", "Valore"], [[i["label"], "n/d" if i["value"] is None else fmt(i["value"]) + unit] for i in items])


def bullets(rows: list[dict], *, aria: str, label_w: int = 160) -> tuple[str, str]:
    """rows: {label, value, target?, max (default 100), unit, tip?}. A track, a bar, a target tick; the verdict is written in words
    ("sopra la soglia" / "sotto la soglia"), never by color alone."""
    rh, T = 40, 8
    H = T + len(rows) * rh + 4
    px0, px1 = label_w, W - 96
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    table = []
    for i, r in enumerate(rows):
        y = T + i * rh
        mx = r.get("max") or 100
        sx = lambda v: px0 + max(0, min(v, mx)) / mx * (px1 - px0)
        v, tg, u = r["value"], r.get("target"), r.get("unit", "")
        g.append(f'<text x="{label_w - 10}" y="{y + 20}" text-anchor="end" font-size="12" fill="var(--ink2)">{esc(_short(r["label"], 22))}</text>'
                 f'<rect x="{px0}" y="{y + 10}" width="{px1 - px0}" height="14" rx="4" fill="var(--grid)"/>')
        word = ""
        if v is not None:
            ok = tg is None or v >= tg
            g.append(f'<path d="{_bar_path(px0, sx(v), y + 10, 14)}" fill="{"var(--s1)" if ok else "var(--warn)"}"/>')
            word = "" if tg is None else ("sopra la soglia" if ok else "sotto la soglia")
            g.append(f'<text x="{px1 + 10}" y="{y + 21}" font-size="12" font-weight="600" fill="var(--ink)" style="font-variant-numeric:tabular-nums">{fmt_n(v) if abs(v) >= 100 else round(v, 1)}{esc(u)}</text>'
                     + (f'<text x="{px1 + 10}" y="{y + 35}" font-size="11" fill="var(--ink2)">{word}</text>' if word else ""))
        if tg is not None:
            g.append(f'<line x1="{sx(tg):.1f}" x2="{sx(tg):.1f}" y1="{y + 5}" y2="{y + 29}" stroke="var(--ink)" stroke-width="2"/>')
        g.append(f'<rect class="hit" tabindex="0" x="0" y="{y}" width="{W}" height="{rh}" fill="transparent" data-x="{sx(v if v is not None else 0):.1f}" data-tip="{esc(r.get("tip") or r["label"] + ": " + ("n/d" if v is None else f"{v}{u}") + (f" (soglia {tg}{u})" if tg is not None else ""))}"/>')
        table.append([r["label"], "n/d" if v is None else f"{v}{u}", "" if tg is None else f"{tg}{u}", word])
    g.append("</svg>")
    return "".join(g), table_view(["Voce", "Valore", "Soglia", "Esito"], table)


def standalone_svg(chart_html: str, title: str = "") -> str:
    """One chart as a self-contained SVG file (light colors, white background, hit areas and tooltips removed)."""
    m = re.search(r"<svg .*?</svg>", chart_html, re.S)
    if not m:
        return ""
    svg = re.sub(r'<rect class="hit"[^>]*/>', "", m.group(0))
    svg = re.sub(r"var\(--([a-z0-9]+)\)", lambda k: TOKENS_LIGHT.get(k.group(1), "#000"), svg)
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w, h = (vb.group(1), vb.group(2)) if vb else ("720", "300")
    svg = svg.replace("<svg ", f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="system-ui,Segoe UI,Arial,sans-serif" ', 1)
    return svg.replace(">", f'><rect width="100%" height="100%" fill="{TOKENS_LIGHT["bg"]}"/>', 1) if svg.startswith("<svg") else svg
