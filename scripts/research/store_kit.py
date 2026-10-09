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
    "checklist": ["Content survey completed", "..."],
    "early_access": {                                  # only if the game ships in Early Access (Steam questionnaire, shown on the store page)
      "verified_on": "AAAA-MM-GG", "source": "https://partner.steamgames.com/doc/store/earlyaccess",
      "limits": {"why": 1200},                         # Valve declares none: the default is a readability limit [OPINIONE]
      "questions": [{"key": "why", "label": "Why Early Access?", "value": "..."},
                    {"key": "duration", ...}, {"key": "full_vs_ea", ...}, {"key": "current_state", ...}, {"key": "pricing", ...}, {"key": "community", ...}]},
    "accessibility": {"intro": "...", "features": [{"label": "Reduce motion", "value": "turns off head bob, camera shake and hit-stop"}]}
  },
  "itch": { ...same shape, long_description.format "markdown"... }
}
Usage: store_kit.py check|render|export launch/store_kit.json [--md launch/store_kit.md] [--dir launch/store_kit]

Live pages: the kit must follow the game. After every owner decision, gate or wave that changes what the game is or promises
(Early Access, multiplayer roadmap, accessibility, languages, price) Claude updates store_kit.json ("updated": date) and re-runs
check/render/export. `freshness(launch_dir)` (used by `check` and by STATUS.html) says "aggiornate al <date>" or "da aggiornare"
when the kit is older than the latest decision in 00-intenzioni.md (a "## AAAA-MM-GG" heading), the latest wave or the latest gate doc.
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
# Steam Early Access questionnaire (field names read on partner.steamgames.com/doc/store/earlyaccess on 2026-10-09; re-check them)
EA_QUESTIONS = [("why", "Why Early Access?"), ("duration", "Approximately how long will this game be in Early Access?"),
                ("full_vs_ea", "How is the full version planned to differ from the Early Access version?"),
                ("current_state", "What is the current state of the Early Access version?"),
                ("pricing", "Will the game be priced differently during and after Early Access?"),
                ("community", "How are you planning on involving the Community in your development process?")]
EA_SOFT_LIMIT = 1200   # Valve declares no limit; past this a player stops reading [OPINIONE]
PROMISE = re.compile(r"\b(guarantee[ds]?|definitely|we promise|will (?:definitely |surely )?(?:be (?:released|finished|out)|release|launch|ship)\s+(?:on|by|in)\s+(?:\w+\s+)?\d{4})\b", re.I)


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
        ea = p.get("early_access")
        if ea:
            if not ea.get("verified_on"):
                warns.append(f"{pf}: early_access.verified_on missing (question names change: re-read the Steamworks page)")
            got = {q.get("key"): q for q in ea.get("questions", [])}
            elim = ea.get("limits") or {}
            for key, label in EA_QUESTIONS:
                q = got.get(key)
                val = str((q or {}).get("value") or "").strip()
                if not val:
                    errs.append(f"{pf}: Early Access question '{label}' has no answer")
                    continue
                lim = elim.get(key) or (q or {}).get("limit") or EA_SOFT_LIMIT
                st[f"ea_{key}"] = len(val)
                if len(val) > lim:
                    (errs if elim.get(key) or (q or {}).get("limit") else warns).append(f"{pf}: Early Access '{key}' has {len(val)} characters (limit {lim})")
                if PROMISE.search(val):
                    warns.append(f"{pf}: Early Access '{key}' sounds like a promise ('{PROMISE.search(val).group(0)}'): Valve asks not to promise future features or dates")
            if pf == "steam" and not re.search(r"early access", assemble(p.get("long_description") or {}), re.I):
                warns.append("steam: the long description does not say the game is in Early Access")
        acc = p.get("accessibility")
        if acc:
            feats = acc.get("features") or []
            if not feats:
                errs.append(f"{pf}: accessibility block without features")
            for f in feats:
                if not str(f.get("label") or "").strip() or not str(f.get("value") or "").strip():
                    errs.append(f"{pf}: accessibility feature without label or description")
            st["accessibility_features"] = len(feats)
        stats[pf] = st
    return errs, warns, stats


def ea_rows(p: dict) -> list[tuple[str, str, str]]:
    ea = p.get("early_access") or {}
    got = {q.get("key"): q for q in ea.get("questions", [])}
    return [(got.get(k, {}).get("label") or label, str(got.get(k, {}).get("value") or ""), got.get(k, {}).get("note") or "") for k, label in EA_QUESTIONS if k in got]


def accessibility_text(p: dict, fmt: str = "text") -> str:
    """The accessibility block as pasteable text: intro + one line per feature (bbcode list on Steam, markdown on itch)."""
    acc = p.get("accessibility") or {}
    feats = acc.get("features") or []
    if not feats:
        return ""
    if fmt == "bbcode":
        body = "[list]\n" + "\n".join(f"[*][b]{f['label']}[/b]: {f['value']}" for f in feats) + "\n[/list]"
    else:
        body = "\n".join(f"- **{f['label']}**: {f['value']}" for f in feats)
    return ((acc.get("intro") or "").strip() + "\n" + body).strip()


def freshness(root: str, kit_path: str | None = None) -> dict:
    """{"kit_date", "stale": bool, "newer": [(what, date)]}: is the kit older than the latest decision, wave or gate?"""
    import datetime as dt
    import glob
    kit_path = kit_path or os.path.join(root, "store_kit.json")
    if not os.path.exists(kit_path):
        return {}
    try:
        kd = str(load(kit_path).get("updated") or "")[:10]
        kit_date = dt.date.fromisoformat(kd)
    except (ValueError, OSError, json.JSONDecodeError):
        kit_date = dt.date.fromtimestamp(os.path.getmtime(kit_path))
    newer = []
    try:
        dates = re.findall(r"^#{2,3}\s+(\d{4}-\d{2}-\d{2})", open(os.path.join(root, "00-intenzioni.md"), encoding="utf-8").read(), re.M)
        if dates and max(dates) > kit_date.isoformat():
            newer.append(("ultima decisione in 00-intenzioni.md", max(dates)))
    except OSError:
        pass
    wd = []
    for f in glob.glob(os.path.join(root, "fg", "waves", "w[0-9]*.json")):
        try:
            wd.append(str(load(f).get("date") or "")[:10])
        except (OSError, json.JSONDecodeError):
            pass
    if wd and max(wd) > kit_date.isoformat():
        newer.append(("ultima ondata del focus group", max(wd)))
    gates = glob.glob(os.path.join(os.path.dirname(os.path.abspath(root)), "docs", "gates", "*.md"))
    if gates:
        g = max(gates, key=os.path.getmtime)
        gd = dt.date.fromtimestamp(os.path.getmtime(g)).isoformat()
        if gd > kit_date.isoformat():
            newer.append((f"ultimo gate ({os.path.basename(g)})", gd))
    return dict(kit_date=kit_date.isoformat(), stale=bool(newer), newer=newer)


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
        if p.get("early_access"):
            ea = p["early_access"]
            L += ["### Early Access: le domande di Steam", "", f"_Domande lette su {ea.get('source', 'partner.steamgames.com/doc/store/earlyaccess')} il {ea.get('verified_on', '[DA VERIFICARE]')}. Valve: niente promesse su date o funzioni future._", ""]
            for label, value, note in ea_rows(p):
                L += [f"#### {label}", "", "```text", value, "```", ""] + ([f"_{note}_", ""] if note else [])
        if p.get("accessibility"):
            L += ["### Accessibilità (da copiare)", "", "```text", accessibility_text(p, "bbcode" if pf == "steam" else "md"), "```", ""]
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
        for k, (label, value, _) in zip([q for q, _ in EA_QUESTIONS if q in {x.get("key") for x in (p.get("early_access") or {}).get("questions", [])}], ea_rows(p)):
            path = os.path.join(outdir, f"{pf}_early_access_{k}.txt")
            open(path, "w", encoding="utf-8", newline="\n").write(value + "\n")
            written.append(path)
        if p.get("accessibility"):
            path = os.path.join(outdir, f"{pf}_accessibility.txt")
            open(path, "w", encoding="utf-8", newline="\n").write(accessibility_text(p, "bbcode" if pf == "steam" else "md") + "\n")
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
        fr = freshness(os.path.dirname(os.path.abspath(a.kit)), a.kit)
        if fr:
            print(f"pagine store: aggiornate al {fr['kit_date']}" if not fr["stale"] else
                  f"pagine store: DA AGGIORNARE (kit del {fr['kit_date']}; più recenti: " + "; ".join(f"{w} {d}" for w, d in fr["newer"]) + ")")
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
