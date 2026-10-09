#!/usr/bin/env python3
"""TODO.md kept alive: list, count, mark done, reopen, add. STATUS.html reads the same file (open vs done per section).

TODO.md lines look like  `- [ ] 👤 **Action** details — 2026-10-20 — 2 h — dependencies — metric`  (fields separated by " — ";
"|" works too). 👤 = the owner, 🤖 = Claude, 👤+🤖 = together. Sections are the `## ` headings.
Rule of the skill: after EVERY gate, wave or owner decision Claude runs `done` on what was finished and `add` for what is new,
so the TODO never lags behind the project (STATUS.html warns when TODO.md is older than the latest wave or decision).

  todo_track.py [--file launch/TODO.md] list [--open|--done] [--section TEXT]
  todo_track.py stats                                   open / done per section, overdue
  todo_track.py done  "words of the line" [--by me|claude] [--note "gate 48"] [--date 2026-10-09]
  todo_track.py done  "#12"                             the 12th item of the file (numbers as printed by `list`)
  todo_track.py reopen "words of the line"
  todo_track.py drop  "words of the line" --why "decisione del proprietario: clip a beta finita (voce #7)"
                                                        made obsolete by a decision: `[-]`, kept for the record, not counted
  todo_track.py add --section "Dev e pilastri" --text "🤖 **Fix X** — 2026-10-20 — 2 h — nessuna — 0 errori"
A pattern must match exactly one open (or, for reopen, done) line; otherwise the candidates are printed and nothing changes.
`done` turns `[ ]` into `[x]`, appends "· fatto il DATE (da 👤/🤖, NOTE)" and refreshes the "Aggiornato:" date at the top.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re

import common  # noqa: F401  (UTF-8 console on Windows)

ITEM = re.compile(r"^(\s*(?:[-*]\s*)?)\[( |x|X|-)\]\s*(.+)$")
DONE_NOTE = re.compile(r"\s*·\s*(?:fatto|superata) il (\d{4}-\d{2}-\d{2})[^·]*$")


def _owner(text: str) -> str:
    if "👤+🤖" in text or ("👤" in text and "🤖" in text[:12]):
        return "both"
    if text.lstrip().startswith("👤") or "👤" in text[:6]:
        return "me"
    if text.lstrip().startswith("🤖") or "🤖" in text[:6]:
        return "claude"
    return ""


def split_fields(body: str) -> list[str]:
    sep = " — " if " — " in body else " | " if " | " in body else None
    return [x.strip() for x in body.split(sep)] if sep else [body.strip()]


def parse(path: str) -> dict | None:
    """{"updated", "sections": [names in order], "items": [{n, line, section, done, dropped, owner, action, due, due_date, hours, h, metric, done_note}]}.
    dropped = `[-]`: made obsolete by a decision; it is neither open nor done."""
    if not os.path.exists(path):
        return None
    lines = open(path, encoding="utf-8").read().splitlines()
    sec, sections, items = "Senza sezione", [], []
    upd = None
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*Aggiornat[oa]\s*:\s*(\d{4}-\d{2}-\d{2})", ln, re.I)
        if m and upd is None:
            upd = m.group(1)
        h = re.match(r"^#{2,3}\s+(.*)", ln)
        if h:
            sec = h.group(1).strip()
            continue
        m = ITEM.match(ln)
        if not m:
            continue
        if sec not in sections:
            sections.append(sec)
        body = m.group(3)
        dn = DONE_NOTE.search(body)
        done_note = ""
        if dn:
            done_note = dn.group(0).strip(" ·")
            body = body[:dn.start()]
        f = split_fields(body)
        action = re.sub(r"^\s*(👤\+🤖|👤|🤖)\s*", "", f[0])
        due = f[1] if len(f) > 1 else ""
        dm = re.search(r"\d{4}-\d{2}-\d{2}", due)
        hours = f[2] if len(f) > 2 else ""
        hm = re.search(r"(\d+(?:[.,]\d+)?)(?:\s*[-–]\s*(\d+(?:[.,]\d+)?))?\s*h\b", hours)
        h_val = 0.0
        if hm:
            lo = float(hm.group(1).replace(",", "."))
            hi = float(hm.group(2).replace(",", ".")) if hm.group(2) else lo
            h_val = (lo + hi) / 2
        items.append(dict(n=len(items) + 1, line=i, section=sec, done=m.group(2) in "xX", dropped=m.group(2) == "-", owner=_owner(f[0]), action=action.strip(), due=due, due_date=dt.date.fromisoformat(dm.group(0)) if dm else None,
                          hours=hours, h=h_val, metric=f[4] if len(f) > 4 else "", done_note=done_note))
    return dict(updated=upd, sections=sections, items=items, lines=lines)


def _find(t: dict, pattern: str, want_done: bool) -> list[dict]:
    m = re.fullmatch(r"#?(\d+)", pattern.strip())
    if m and pattern.strip().startswith("#"):
        return [x for x in t["items"] if x["n"] == int(m.group(1))]
    words = [w for w in re.split(r"\s+", pattern.lower()) if w]
    norm = lambda s: re.sub(r"[*`_]", "", s).lower()
    return [x for x in t["items"] if x["done"] == want_done and not x["dropped"] and all(w in norm(t["lines"][x["line"]]) for w in words)]


def _write(path: str, t: dict, today: dt.date):
    lines = t["lines"]
    for k, ln in enumerate(lines[:6]):
        if re.match(r"^\s*Aggiornat[oa]\s*:\s*\d{4}-\d{2}-\d{2}", ln, re.I):
            lines[k] = re.sub(r"\d{4}-\d{2}-\d{2}", today.isoformat(), ln, count=1)
            break
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def mark_done(path: str, pattern: str, by: str = "", note: str = "", today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    t = parse(path)
    if not t:
        raise SystemExit(f"{path} not found")
    hit = _find(t, pattern, False)
    if len(hit) != 1:
        raise SystemExit(f"{len(hit)} open lines match {pattern!r}; be more specific:\n" + "\n".join(f"  #{x['n']} {x['action'][:100]}" for x in _find(t, pattern, False)[:15]))
    x = hit[0]
    who = {"me": "👤", "claude": "🤖", "both": "👤+🤖"}.get(by, "")
    extra = ", ".join(v for v in (f"da {who}" if who else "", note) if v)
    ln = t["lines"][x["line"]]
    ln = re.sub(r"\[ \]", "[x]", ln, count=1).rstrip() + f" · fatto il {today.isoformat()}" + (f" ({extra})" if extra else "")
    t["lines"][x["line"]] = ln
    _write(path, t, today)
    return x


def drop(path: str, pattern: str, why: str, today: dt.date | None = None) -> dict:
    """Mark an open line as made obsolete by a decision: `[-]` plus "· superata il DATE (why)". Kept for the record, never counted."""
    today = today or dt.date.today()
    t = parse(path)
    hit = _find(t, pattern, False)
    if len(hit) != 1:
        raise SystemExit(f"{len(hit)} open lines match {pattern!r}")
    x = hit[0]
    t["lines"][x["line"]] = re.sub(r"\[ \]", "[-]", t["lines"][x["line"]], count=1).rstrip() + f" · superata il {today.isoformat()}" + (f" ({why})" if why else "")
    _write(path, t, today)
    return x


def reopen(path: str, pattern: str, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    t = parse(path)
    hit = _find(t, pattern, True)
    if len(hit) != 1:
        raise SystemExit(f"{len(hit)} done lines match {pattern!r}")
    x = hit[0]
    ln = re.sub(r"\[[xX]\]", "[ ]", t["lines"][x["line"]], count=1)
    t["lines"][x["line"]] = DONE_NOTE.sub("", ln)
    _write(path, t, today)
    return x


def add(path: str, section: str, text: str, today: dt.date | None = None):
    today = today or dt.date.today()
    t = parse(path) or dict(lines=["# TODO", f"Aggiornato: {today.isoformat()}", ""], items=[], sections=[])
    lines = t["lines"]
    line = text if re.match(r"^\s*[-*]\s*\[", text) else f"- [ ] {text}"
    idx = next((k for k, ln in enumerate(lines) if re.match(r"^#{2,3}\s+", ln) and section.lower() in ln.lower()), None)
    if idx is None:
        lines += ["", f"## {section}", line]
    else:
        end = next((k for k in range(idx + 1, len(lines)) if re.match(r"^#{1,3}\s+", lines[k])), len(lines))
        while end > idx + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, line)
    t["lines"] = lines
    _write(path, t, today)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default="launch/TODO.md"); ap.add_argument("--today")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--open", action="store_true"); p.add_argument("--done", action="store_true"); p.add_argument("--section", default="")
    sub.add_parser("stats")
    p = sub.add_parser("done"); p.add_argument("pattern"); p.add_argument("--by", choices=["me", "claude", "both", ""], default=""); p.add_argument("--note", default=""); p.add_argument("--date")
    p = sub.add_parser("reopen"); p.add_argument("pattern")
    p = sub.add_parser("drop"); p.add_argument("pattern"); p.add_argument("--why", default="")
    p = sub.add_parser("add"); p.add_argument("--section", required=True); p.add_argument("--text", required=True)
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if a.cmd == "list":
        t = parse(a.file) or dict(items=[])
        for x in t["items"]:
            if (a.open and x["done"]) or (a.done and not x["done"]) or (a.section and a.section.lower() not in x["section"].lower()):
                continue
            late = " IN RITARDO" if not x["done"] and x["due_date"] and x["due_date"] < today else ""
            print(f"#{x['n']:<3} [{'x' if x['done'] else '-' if x['dropped'] else ' '}] {x['action'][:110]}  ({x['due'] or '-'}{late})")
    elif a.cmd == "stats":
        t = parse(a.file)
        if not t:
            raise SystemExit(f"{a.file} not found")
        live = [x for x in t["items"] if not x["dropped"]]
        tot_o = sum(1 for x in live if not x["done"])
        late = [x for x in live if not x["done"] and x["due_date"] and x["due_date"] < today]
        print(f"TODO: {tot_o} aperte, {len(live) - tot_o} fatte su {len(live)}; superate: {len(t['items']) - len(live)}; in ritardo: {len(late)}; aggiornato: {t['updated'] or 'n/d'}")
        for sname in t["sections"]:
            its = [x for x in live if x["section"] == sname]
            print(f"  {sum(1 for x in its if not x['done']):>3} da fare · {sum(1 for x in its if x['done']):>3} fatte  {sname}")
        for x in late[:15]:
            print(f"  IN RITARDO #{x['n']} {x['action'][:90]} ({x['due']})")
    elif a.cmd == "done":
        x = mark_done(a.file, a.pattern, a.by, a.note, dt.date.fromisoformat(a.date) if a.date else today)
        print(f"fatto: #{x['n']} {x['action'][:100]}")
    elif a.cmd == "drop":
        x = drop(a.file, a.pattern, a.why, today)
        print(f"superata: #{x['n']} {x['action'][:100]}")
    elif a.cmd == "reopen":
        x = reopen(a.file, a.pattern, today)
        print(f"riaperta: #{x['n']} {x['action'][:100]}")
    else:
        add(a.file, a.section, a.text, today)
        print(f"aggiunta in «{a.section}»")


if __name__ == "__main__":
    main()
