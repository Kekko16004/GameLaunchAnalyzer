#!/usr/bin/env python3
"""Copy-ready Steam and itch.io pages from ONE source file, launch/store_kit.json.

The skill writes store_kit.json (field values, long description as blocks with media slots, ordered tags,
screenshots, capsules, trailer, settings, checklist). This tool then:
  check   validates it: required fields, character counts against the limits declared IN the file, tag count,
          duplicated screenshot order, media slots that say what they show, leftover placeholders
  render  writes a readable Markdown sheet (goes into the written report)
  export  writes one text file per field and one per long description (placeholders marked) so you can paste
status_page.py shows the same data in the HTML page with a Copy button on every field.

Limits are NOT hard-coded: each platform carries `limits` (e.g. {"short_description": 300, "tags": 20}) with the
date they were verified, because store rules change (the skill marks them [DA VERIFICARE] until checked).

store_kit.json shape (keys not listed are ignored; every platform: steam, itch):
{
  "game": "Name", "language": "en", "verified_on": "AAAA-MM-GG",
  "steam": {
    "limits": {"short_description": 300, "tags": 20},
    "fields":  [{"key": "short_description", "label": "Short description", "value": "...", "note": "first 100 chars carry genre + promise"}],
    "long_description": {"format": "bbcode", "blocks": [
        {"type": "text", "value": "[h2]About this game[/h2] ..."},
        {"type": "media", "slot": "GIF 1", "what": "core loop: the buffet collapses", "file": "launch/media/gif1.gif", "alt": "..."}]},
    "tags": [{"tag": "Roguelite", "why": "closest comps all use it"}],        # ordered: the first 5 weigh most
    "avoid_tags": [{"tag": "Horror", "why": "promises what the game is not"}],
    "screenshots": [{"order": 1, "what": "pure gameplay with feedback", "caption": "...", "file": "..."}],
    "capsules": [{"name": "Header capsule", "size": "920x430", "what": "composition and what it says in 1.5 s"}],
    "trailer": {"duration_s": 60, "placement": "first media of the page", "script": "launch/04b-store-copy.md#trailer"},
    "settings": [{"label": "Languages", "value": "EN, IT", "note": ""}],
    "checklist": ["AI disclosure completed", "..."]
  },
  "itch": { ...same shape, long_description.format "markdown"... }
}
Usage: store_kit.py check|render|export launch/store_kit.json [--md launch/store_kit.md] [--dir launch/store_kit]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import common  # noqa: F401  (side effect: UTF-8 stdout, so emoji and arrows do not crash on Windows)

PLATFORMS = ("steam", "itch")
PLACEHOLDER = re.compile(r"<<<.*?>>>")
REQUIRED = {"steam": ["title", "short_description"], "itch": ["title", "tagline"]}


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def assemble(block: dict, platform: str = "steam") -> str:
    """Long description as one pasteable text; media slots become <<< ... >>> placeholders to replace with the upload."""
    parts = []
    for b in (block or {}).get("blocks", []):
        if b.get("type") == "media":
            parts.append(f"<<< {b.get('slot', 'MEDIA')} · {b.get('what', '')} · file: {b.get('file') or 'da produrre'} >>>")
        else:
            parts.append(str(b.get("value", "")).strip())
    return "\n\n".join(p for p in parts if p)


def field_value(p: dict, key: str):
    return next((f.get("value") for f in p.get("fields", []) if f.get("key") == key), None)


def validate(kit: dict) -> tuple[list[str], list[str], dict]:
    errs, warns, stats = [], [], {}
    if not kit.get("verified_on"):
        warns.append("verified_on missing: limits and rules must carry the date they were checked")
    for pf in PLATFORMS:
        p = kit.get(pf)
        if not p:
            warns.append(f"{pf}: section missing")
            continue
        limits, st = p.get("limits") or {}, {}
        for key in REQUIRED[pf]:
            if not field_value(p, key):
                errs.append(f"{pf}: required field '{key}' is empty or missing")
        for f in p.get("fields", []):
            n, lim = len(str(f.get("value") or "")), limits.get(f.get("key"))
            st[f["key"]] = n
            if lim and n > lim:
                errs.append(f"{pf}: '{f['key']}' has {n} characters, limit {lim}")
            if not lim and f.get("key") in ("short_description", "tagline"):
                warns.append(f"{pf}: no limit declared for '{f['key']}' (verify it and write it in limits)")
        ld = p.get("long_description") or {}
        text = assemble(ld, pf)
        st["long_description_chars"] = len(text)
        if not ld.get("blocks"):
            errs.append(f"{pf}: long_description has no blocks")
        for b in ld.get("blocks", []):
            if b.get("type") == "media" and not (b.get("what") or "").strip():
                errs.append(f"{pf}: media slot '{b.get('slot')}' does not say what it shows")
        if PLACEHOLDER.search(text):
            warns.append(f"{pf}: {len(PLACEHOLDER.findall(text))} media placeholders still to replace with real uploads")
        tags = p.get("tags") or []
        st["tags"] = len(tags)
        if not tags:
            errs.append(f"{pf}: no tags")
        if limits.get("tags") and len(tags) > limits["tags"]:
            errs.append(f"{pf}: {len(tags)} tags, limit {limits['tags']}")
        if len({t.get("tag", "").lower() for t in tags}) != len(tags):
            errs.append(f"{pf}: duplicated tags")
        shots = p.get("screenshots") or []
        orders = [s.get("order") for s in shots]
        if len(set(orders)) != len(orders):
            errs.append(f"{pf}: duplicated screenshot order")
        if pf == "steam" and len(shots) < 5:
            warns.append(f"steam: {len(shots)} screenshots planned (verify the minimum; comps usually have more)")
        st["screenshots"] = len(shots)
        for key in ("capsules",) + (("trailer",) if pf == "steam" else ()):
            if not p.get(key):
                warns.append(f"{pf}: '{key}' missing")
        stats[pf] = st
    return errs, warns, stats


def copy_rows(p: dict) -> list[tuple[str, str, str]]:
    """(label, value, note) for every simple field, then the long description, then the tag list."""
    rows = [(f.get("label") or f["key"], str(f.get("value") or ""), f.get("note") or "") for f in p.get("fields", [])]
    ld = p.get("long_description") or {}
    if ld.get("blocks"):
        rows.append((f"Descrizione lunga ({ld.get('format', 'text')})", assemble(ld), "i segnaposto <<< >>> vanno sostituiti con gli upload"))
    if p.get("tags"):
        rows.append(("Tag (in ordine, i primi 5 pesano di più)", ", ".join(t["tag"] for t in p["tags"]), ""))
    return rows


def to_md(kit: dict) -> str:
    L = [f"# Kit pagine store: {kit.get('game', '')}", "", f"Lingua dei testi: {kit.get('language', 'en')} · limiti verificati il {kit.get('verified_on', '[DA VERIFICARE]')}. Ogni campo si copia così com'è.", ""]
    for pf, title in (("steam", "Pagina Steam"), ("itch", "Pagina itch.io")):
        p = kit.get(pf)
        if not p:
            continue
        L += [f"## {title}", ""]
        for label, value, note in copy_rows(p):
            L += [f"### {label}", "", "```text", value, "```", ""] + ([f"_{note}_", ""] if note else [])
        if p.get("avoid_tags"):
            L += ["### Tag da evitare", ""] + [f"- **{t['tag']}**: {t.get('why', '')}" for t in p["avoid_tags"]] + [""]
        if p.get("tags"):
            L += ["### Perché questi tag", ""] + [f"{i}. **{t['tag']}**: {t.get('why', '')}" for i, t in enumerate(p["tags"], 1)] + [""]
        if p.get("screenshots"):
            L += ["### Screenshot, in ordine", "", "| # | Cosa mostra | Didascalia | File |", "|---|---|---|---|"]
            L += [f"| {s.get('order')} | {s.get('what', '')} | {s.get('caption', '')} | {s.get('file', 'da produrre')} |" for s in sorted(p["screenshots"], key=lambda s: s.get("order") or 0)] + [""]
        if p.get("capsules"):
            L += ["### Immagini e capsule", "", "| Nome | Misura | Cosa deve comunicare |", "|---|---|---|"] + [f"| {c.get('name')} | {c.get('size', '[DA VERIFICARE]')} | {c.get('what', '')} |" for c in p["capsules"]] + [""]
        if p.get("trailer"):
            t = p["trailer"]
            L += ["### Trailer", "", f"Durata prevista {t.get('duration_s', '?')} s · posizione: {t.get('placement', '')} · script: {t.get('script', '')}", ""]
        if p.get("settings"):
            L += ["### Impostazioni da compilare", "", "| Voce | Valore | Nota |", "|---|---|---|"] + [f"| {s.get('label')} | {s.get('value')} | {s.get('note', '')} |" for s in p["settings"]] + [""]
        if p.get("checklist"):
            L += ["### Controlli prima di pubblicare", ""] + [f"- [ ] {c}" for c in p["checklist"]] + [""]
    return "\n".join(L)


def export(kit: dict, outdir: str) -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    written = []
    for pf in PLATFORMS:
        p = kit.get(pf)
        if not p:
            continue
        for f in p.get("fields", []):
            path = os.path.join(outdir, f"{pf}_{re.sub(r'[^a-z0-9_]+', '_', f['key'].lower())}.txt")
            open(path, "w", encoding="utf-8", newline="\n").write(str(f.get("value") or "") + "\n")
            written.append(path)
        ld = p.get("long_description") or {}
        if ld.get("blocks"):
            path = os.path.join(outdir, f"{pf}_long_description.{'bbcode.txt' if ld.get('format') == 'bbcode' else 'md'}")
            open(path, "w", encoding="utf-8", newline="\n").write(assemble(ld) + "\n")
            written.append(path)
        if p.get("tags"):
            path = os.path.join(outdir, f"{pf}_tags.txt")
            open(path, "w", encoding="utf-8", newline="\n").write("\n".join(t["tag"] for t in p["tags"]) + "\n")
            written.append(path)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "render", "export"]); ap.add_argument("kit", nargs="?", default="launch/store_kit.json")
    ap.add_argument("--md", help="render: output file (default stdout)"); ap.add_argument("--dir", default="launch/store_kit", help="export: output folder")
    a = ap.parse_args()
    kit = load(a.kit)
    if a.cmd == "check":
        errs, warns, stats = validate(kit)
        for pf, st in stats.items():
            print(f"{pf}: " + ", ".join(f"{k}={v}" for k, v in st.items()))
        print("\n".join(f"ERROR {e}" for e in errs + []) + ("\n" if errs else "") + "\n".join(f"WARN  {w}" for w in warns))
        print("OK" if not errs else f"{len(errs)} errors")
        sys.exit(1 if errs else 0)
    if a.cmd == "render":
        text = to_md(kit)
        if a.md:
            open(a.md, "w", encoding="utf-8", newline="\n").write(text)
            print(f"wrote {a.md}")
        else:
            print(text)
        return
    for p in export(kit, a.dir):
        print("wrote", p)


if __name__ == "__main__":
    main()
