#!/usr/bin/env python3
"""Export every report chart as a standalone .svg (light colors) into launch/charts/, plus launch/charts/index.md.

Markdown cannot draw charts, so this lets REPORT.md and the other reports embed them: `![Pilastri](charts/product-1.svg)`
(open the .md in any viewer that shows images). Same data as REPORT.html and STATUS.html: built from files in launch/.

  python charts_export.py [--launch-dir launch] [--out launch/charts]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re

from common import log
import charts as C
import report_charts as rc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("--out"); ap.add_argument("--today")
    a = ap.parse_args()
    out = a.out or os.path.join(a.launch_dir, "charts")
    os.makedirs(out, exist_ok=True)
    idx = ["# Grafici", "", "Generati da `charts_export.py` con i dati di `launch/`. Incollali nei report con `![testo](charts/nome.svg)`.", ""]
    n = 0
    for g in rc.groups(a.launch_dir, dt.date.fromisoformat(a.today) if a.today else dt.date.today()):
        idx += [f"## {g['title']}", ""]
        for i, html in enumerate(g["charts"], 1):
            svg = C.standalone_svg(html)
            if not svg:
                continue
            t = re.search(r"<h3>(.*?)</h3>", html)
            title = t.group(1) if t else f"{g['title']} {i}"
            name = f"{g['key']}-{i}.svg"
            with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as f:
                f.write(svg)
            idx += [f"### {title}", "", f"![{title}]({name})", ""]
            n += 1
    with open(os.path.join(out, "index.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(idx))
    log(f"wrote {n} charts in {out}")


if __name__ == "__main__":
    main()
