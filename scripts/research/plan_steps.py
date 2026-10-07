#!/usr/bin/env python3
"""Step-by-step plan in launch/calendar.md: who does what, in which phase, by when, and what is already done.

The section the tool reads looks like this (the rest of calendar.md is free text and tables):

  ## ✅ Passi in ordine
  🤖 = li faccio io (Claude) · 👤 = li fai tu · 👤+🤖 = insieme
  ### FASE 1 — Adesso (ottobre)
  1. [ ] 👤 **Crea il modulo di feedback**: apri `tools/community/feedback-form.md` e segui le istruzioni (~20 min). · 📅 2026-10-20
  2. [x] 🤖 Lo collego al pulsante Feedback della beta (solo con il tuo ok).
  ### FASE 2 — Inizio novembre: test con persone vere
  3. [ ] 👤+🤖 **Pagina Steam "Coming Soon" online** entro il ~10 dicembre.  · 📅 2026-12-10

Rules: a step is `N. [ ] OWNER text`; OWNER is 👤, 🤖 or 👤+🤖; `· 📅 AAAA-MM-GG` is an optional due date; indented lines
below a step are notes of that step; a `###` heading starts a phase. Numbers are global and unique.

  plan_steps.py list    [--owner me|claude] [--open] [--calendar launch/calendar.md]
  plan_steps.py next    [--owner me|claude] [--limit 5] [--today D]      what is next, overdue first
  plan_steps.py done    3 5 [--calendar ...]                              tick steps (idempotent); `undo` unticks
  plan_steps.py summary [--json out.json] [--today D]                     progress per phase and overall
  plan_steps.py check                                                      format problems (duplicates, no owner, no date on user steps...)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

import common  # noqa: F401  (side effect: UTF-8 stdout, so emoji do not crash on Windows)

STEP = re.compile(r"^(\s*)(\d+)\.\s+\[( |x|X)\]\s*(.*)$")
DUE = re.compile(r"[·\-–]?\s*📅\s*(\d{4}-\d{2}-\d{2})")
SECTION = re.compile(r"^##\s+.*Passi in ordine", re.I)


def owner_of(text: str) -> tuple[str, str]:
    """('me' | 'claude' | 'both' | 'none', text without the owner marker)."""
    t = text.lstrip()
    m = re.match(r"(👤\s*\+\s*🤖|🤖\s*\+\s*👤|👤|🤖)\s*", t)
    if not m:
        return "none", text.strip()
    tok = m.group(1)
    return ("both" if "+" in tok else "me" if tok == "👤" else "claude"), t[m.end():].strip()


def parse(md: str) -> dict:
    """{'before': markdown before the steps section, 'after': markdown after it, 'intro': legend lines, 'phases': [...]}"""
    lines = md.replace("\r", "").split("\n")
    start = next((i for i, ln in enumerate(lines) if SECTION.match(ln)), None)
    if start is None:
        return dict(before=md, after="", intro="", phases=[], line_of={})
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    phases, cur, step, intro, line_of = [], None, None, [], {}
    for i in range(start + 1, end):
        ln = lines[i]
        if ln.startswith("### "):
            cur, step = dict(title=ln[4:].strip(), steps=[]), None
            phases.append(cur)
            continue
        m = STEP.match(ln)
        if m and cur is not None:
            owner, text = owner_of(m.group(4))
            due = DUE.search(text)
            step = dict(n=int(m.group(2)), done=m.group(3) != " ", owner=owner, text=DUE.sub("", text).strip(" ·"), due=due.group(1) if due else None, notes=[])
            cur["steps"].append(step)
            line_of[step["n"]] = i
        elif step is not None and ln.startswith((" ", "\t")) and ln.strip():
            step["notes"].append(ln.strip())
        elif cur is None and ln.strip() and not ln.strip().startswith("---"):
            intro.append(ln.strip())
        elif not ln.strip():
            step = None if cur is None else step
    return dict(before="\n".join(lines[:start]), after="\n".join(lines[end:]), intro=" ".join(intro), phases=phases, line_of=line_of)


def all_steps(plan: dict) -> list[dict]:
    return [dict(s, phase=p["title"]) for p in plan["phases"] for s in p["steps"]]


def status_of(s: dict, today: dt.date) -> str:
    if s["done"]:
        return "done"
    return "overdue" if s["due"] and dt.date.fromisoformat(s["due"]) < today else "open"


def summary(plan: dict, today: dt.date) -> dict:
    steps = all_steps(plan)
    by = lambda who: [s for s in steps if s["owner"] in (who, "both")]
    out = dict(total=len(steps), done=sum(s["done"] for s in steps), overdue=sum(1 for s in steps if status_of(s, today) == "overdue"),
               me_open=sum(1 for s in by("me") if not s["done"]), claude_open=sum(1 for s in by("claude") if not s["done"]), phases=[])
    for p in plan["phases"]:
        out["phases"].append(dict(title=p["title"], total=len(p["steps"]), done=sum(s["done"] for s in p["steps"])))
    return out


def next_steps(plan: dict, owner: str | None, limit: int, today: dt.date) -> list[dict]:
    steps = [s for s in all_steps(plan) if not s["done"] and (owner is None or s["owner"] in (owner, "both"))]
    steps.sort(key=lambda s: (status_of(s, today) != "overdue", s["due"] or "9999", s["n"]))
    return steps[:limit]


def check(plan: dict) -> list[str]:
    problems, seen, steps = [], set(), all_steps(plan)
    if not plan["phases"]:
        return ["no `## ✅ Passi in ordine` section with `### FASE` headings and numbered steps found"]
    for s in steps:
        if s["n"] in seen:
            problems.append(f"step {s['n']}: duplicate number")
        seen.add(s["n"])
        if s["owner"] == "none":
            problems.append(f"step {s['n']}: no owner (start with 👤, 🤖 or 👤+🤖)")
        if s["owner"] in ("me", "both") and not s["due"]:
            problems.append(f"step {s['n']}: user step without a date (add `· 📅 AAAA-MM-GG`)")
        if s["due"]:
            try:
                dt.date.fromisoformat(s["due"])
            except ValueError:
                problems.append(f"step {s['n']}: invalid date {s['due']}")
    dated = [(s["n"], s["due"]) for s in steps if s["due"]]
    for (n1, d1), (n2, d2) in zip(dated, dated[1:]):
        if d2 < d1:
            problems.append(f"steps {n1} -> {n2}: dates go backwards ({d1} then {d2}); fine only if the order is intentional")
    if sorted(seen) != list(range(1, len(seen) + 1)):
        problems.append("numbers are not 1..N without gaps")
    return problems


def set_done(path: str, numbers: list[int], value: bool) -> list[int]:
    md = open(path, encoding="utf-8").read()
    plan = parse(md)
    lines = md.split("\n")
    changed = []
    for n in numbers:
        i = plan["line_of"].get(n)
        if i is None:
            raise SystemExit(f"step {n} not found in {path}")
        new = re.sub(r"\[( |x|X)\]", "[x]" if value else "[ ]", lines[i], count=1)
        if new != lines[i]:
            lines[i] = new
            changed.append(n)
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    return changed


def fmt(s: dict, today: dt.date) -> str:
    who = {"me": "👤", "claude": "🤖", "both": "👤+🤖", "none": "?"}[s["owner"]]
    st = {"done": "[x]", "open": "[ ]", "overdue": "[!]"}[status_of(s, today)]
    return f"{s['n']:>2}. {st} {who} {re.sub(r'[*`]', '', s['text'])[:110]}" + (f"  (entro {s['due']})" if s["due"] else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calendar", default="launch/calendar.md"); ap.add_argument("--today")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "next"):
        s = sub.add_parser(name); s.add_argument("--owner", choices=["me", "claude"])
        if name == "list":
            s.add_argument("--open", action="store_true")
        else:
            s.add_argument("--limit", type=int, default=5)
    for name in ("done", "undo"):
        s = sub.add_parser(name); s.add_argument("numbers", nargs="+", type=int)
    s = sub.add_parser("summary"); s.add_argument("--json")
    sub.add_parser("check")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    if a.cmd in ("done", "undo"):
        ch = set_done(a.calendar, a.numbers, a.cmd == "done")
        print(f"{'ticked' if a.cmd == 'done' else 'unticked'}: {ch or 'nothing changed'}")
        return
    plan = parse(open(a.calendar, encoding="utf-8").read())
    if a.cmd == "check":
        pr = check(plan)
        print("\n".join(pr) if pr else f"OK: {len(all_steps(plan))} steps in {len(plan['phases'])} phases")
        sys.exit(1 if any("no `##" in p or "duplicate" in p or "no owner" in p or "invalid date" in p for p in pr) else 0)
    if a.cmd == "summary":
        o = summary(plan, today)
        print(f"{o['done']}/{o['total']} fatti, {o['overdue']} in ritardo; aperti: {o['me_open']} tuoi, {o['claude_open']} di Claude")
        for p in o["phases"]:
            print(f"  {p['done']}/{p['total']}  {p['title']}")
        if a.json:
            json.dump(o, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    if a.cmd == "next":
        for s in next_steps(plan, a.owner, a.limit, today):
            print(fmt(s, today))
        return
    for p in plan["phases"]:
        print(f"\n{p['title']}")
        for s in p["steps"]:
            if not (a.open and s["done"]) and (a.owner is None or s["owner"] in (a.owner, "both")):
                print("  " + fmt(s, today))


if __name__ == "__main__":
    main()
