#!/usr/bin/env python3
"""Hyperlinks between the Markdown documents in launch/ and a plain-Italian glossary at the end of REPORT.md.

  * When a document mentions something that has its own file ("creator" -> 06-creators.md, "calendario a passi" -> calendar.md,
    "pagine Steam" -> store_kit.md, "pre-mortem" -> 05c-premortem.md ...) the FIRST mention in that document becomes a relative link,
    if the target file exists and is not the document itself. A file name written in backticks (`calendar.md`) becomes a link too.
  * REPORT.md ends with a "Glossario" (between markers, replaced at each run) explaining only the terms the report uses, in simple words.
Nothing is touched inside code blocks, inline code (except a file name), headings, existing links, images, URLs or HTML.
Safe to re-run: a target already linked in a document is not linked again. Only .md files in launch/ (and launch/history) are written.

  python md_enrich.py [--launch-dir launch] [--dry-run] [--no-glossary]
"""
from __future__ import annotations

import argparse
import os
import re

import common  # noqa: F401  (side effect: UTF-8 stdout)
import glossary as gl

# (regex of the words, target file(s) tried in order)
LINKS = [
    (r"creator|outreach", ["06-creators.md"]), (r"community|subreddit|discord", ["07-community.md"]),
    (r"calendario a passi|passi in ordine|calendario dei passi", ["calendar.md"]), (r"pagin[ae] steam|pagin[ae] itch|store kit|kit delle pagine", ["store_kit.md"]),
    (r"piano economico|break-?even", ["03-pricing-calc.md", "03-pricing.md"]), (r"\bprezzo\b|prezzi", ["03-pricing.md"]), (r"focus group|ondat[ae]", ["05-focusgroup.md"]),
    (r"critiche simulate", ["05a-critiche-simulate.md"]), (r"critiche reali", ["05b-critiche-reali.md"]), (r"pre-?mortem", ["05c-premortem.md"]),
    (r"contingenz[ae]|se… allora|se\.\.\. allora", ["05d-contingenze.md"]), (r"posizionamento", ["01b-positioning.md"]), (r"audit|pilastri", ["01-dev.md"]),
    (r"gioco completo", ["01c-full-game.md"]), (r"finestra di lancio", ["window.md"]), (r"legale|fiscale", ["08-brand-legal.md"]),
    (r"testi dello store|capsule", ["04b-store-copy.md"]), (r"\bhook\b|\bclip\b|trailer", ["04-clips.md"]), (r"tracker delle wishlist|stato delle wishlist", ["wishlist-status.md"]),
    (r"\bTODO\b", ["TODO.md"]), (r"intenzioni|profilo decisionale", ["00-intenzioni.md"]),
]
PROTECT = re.compile(r"(`[^`]*`|!?\[[^\]]*\]\([^)]*\)|<[^>\s][^>]*>|https?://\S+|\[[^\]]*\]\[[^\]]*\])")
FENCE = re.compile(r"^\s*(```|~~~)")
G_START, G_END = "<!-- glossario:inizio -->", "<!-- glossario:fine -->"


def rel(frm: str, to: str) -> str:
    return os.path.relpath(to, os.path.dirname(frm)).replace(os.sep, "/")


def enrich_text(text: str, path: str, root: str, known: set) -> tuple[str, int]:
    """Returns the text with links added and how many were added."""
    out, in_code, in_comment, added = [], False, False, 0
    linked = set(re.findall(r"\]\((?:\./)?([^)#\s]+)(?:#[^)]*)?\)", text))      # targets already linked somewhere in this document
    done_files = {os.path.normpath(os.path.join(os.path.dirname(path), l)) for l in linked}
    me = os.path.normpath(path)
    compiled = [(re.compile(r"(?<![\w-])(?:" + rx + r")(?![\w-])", re.I), files) for rx, files in LINKS]
    for line in text.split("\n"):
        if FENCE.match(line):
            in_code = not in_code
            out.append(line)
            continue
        if "<!--" in line and "-->" not in line:
            in_comment = True
        if in_code or in_comment or line.lstrip().startswith("#") or G_START in line:
            if "-->" in line:
                in_comment = False
            out.append(line)
            continue
        parts = PROTECT.split(line)
        for i, seg in enumerate(parts):
            if i % 2:   # protected: only a back-ticked file name becomes a link
                m = re.fullmatch(r"`([\w./-]+\.md)`", seg)
                if m:
                    target = os.path.normpath(os.path.join(root, m.group(1)))
                    if m.group(1) in known and target != me and target not in done_files:
                        parts[i] = f"[{seg}]({rel(path, target)})"
                        done_files.add(target)
                        added += 1
                continue
            for rx, files in compiled:
                tgt = next((os.path.join(root, f) for f in files if f in known), None)
                if not tgt or os.path.normpath(tgt) == me or os.path.normpath(tgt) in done_files:
                    continue
                m = rx.search(seg)
                if m:
                    seg = seg[:m.start()] + f"[{m.group(0)}]({rel(path, tgt)})" + seg[m.end():]
                    done_files.add(os.path.normpath(tgt))
                    added += 1
            parts[i] = seg
        out.append("".join(parts))
    return "\n".join(out), added


def glossary_md(text: str) -> str:
    plain = re.sub(r"```.*?```|`[^`]*`|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or " ", text, flags=re.S)
    plain = plain.split(G_START)[0]
    keys = sorted({m.lastgroup for m in gl._RX.finditer(plain) if gl.TERMS[m.lastgroup][1]}, key=lambda k: gl.LABEL.get(k, k).lower())
    if not keys:
        return ""
    return "\n".join([G_START, "## Glossario: le parole usate", ""] + [f"- **{gl.LABEL.get(k, k)}**: {gl.TERMS[k][1]}" for k in keys] + ["", G_END])


def strip_glossary(text: str) -> str:
    return re.sub(rf"\n*{re.escape(G_START)}.*?{re.escape(G_END)}\n*", "\n", text, flags=re.S).rstrip("\n") + "\n"


def run(root: str, dry: bool = False, glossary: bool = True) -> dict:
    files = []
    for d in (root, os.path.join(root, "history")):
        if os.path.isdir(d):
            files += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".md")]
    known = {f for f in os.listdir(root) if f.endswith(".md")}
    stats = {}
    for p in files:
        old = open(p, encoding="utf-8").read()
        body = strip_glossary(old) if G_START in old else old
        new, n = enrich_text(body, p, root, known)
        if glossary and os.path.basename(p) == "REPORT.md":
            g = glossary_md(new)
            new = new.rstrip("\n") + ("\n\n" + g if g else "") + "\n"
        if new != old:
            stats[os.path.relpath(p, root).replace(os.sep, "/")] = n
            if not dry:
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch-dir", default="launch"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--no-glossary", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(a.launch_dir):
        raise SystemExit(f"{a.launch_dir} not found")
    st = run(a.launch_dir, a.dry_run, not a.no_glossary)
    print(("would change " if a.dry_run else "changed ") + (", ".join(f"{k} (+{v} links)" for k, v in st.items()) or "nothing"))


if __name__ == "__main__":
    main()
