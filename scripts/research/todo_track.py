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
  todo_track.py add --section "Dev e pilastri" --text "🤖 **Fix X** (P-w10-1, key:new-too-much-ui) — 2026-10-20 — 2 h — nessuna — 0 errori"
  todo_track.py approve "P-w10-1" --date 2026-10-19 [--status-file launch/issue_status.json]
                                                        the owner approved the proposal: "ok del proprietario DATE" in the
                                                        Dipendenze field; with --status-file the line's key:<chiave> become
                                                        in_lavorazione (never an owner decision, never the gate/resolved fields)
  todo_track.py sync-decisions --decisions DECISIONI.md [--intents launch/00-intenzioni.md] [--write]
                                                        game-developer's D-NNN rows missing from "Decisioni prese" and from
                                                        00-intenzioni.md, copied under "Decisioni prese" with
                                                        "fonte: DECISIONI.md D-NNN" (dry run without --write; DECISIONI.md is never written)
Dev work lines (references/dev-link.md §5): `🤖 **Action** (P-wNN-n, key:<chiave>[,<chiave>]) — date — hours — dependencies — metric`.
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
PID = re.compile(r"\bP-w\d{2,}-\d+\b")
KEYS = re.compile(r"\bkey:([A-Za-z0-9_.,-]+)")
OK_OWNER = re.compile(r"ok del proprietario (\d{4}-\d{2}-\d{2})")
DECIDED = {"accettato", "non_problema", "pianificato", "sospeso"}   # owner decisions: approve never changes them
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
                          hours=hours, h=h_val, metric=f[4] if len(f) > 4 else "", done_note=done_note,
                          pid=(PID.search(body) or [None])[0], keys=[k for m_ in KEYS.findall(body) for k in m_.strip(",.").split(",") if k],
                          approved=(OK_OWNER.search(body) or [None, None])[1]))
    return dict(updated=upd, sections=sections, items=items, lines=lines)


def _find(t: dict, pattern: str, want_done: bool) -> list[dict]:
    m = re.fullmatch(r"#?(\d+)", pattern.strip())
    if m and pattern.strip().startswith("#"):
        return [x for x in t["items"] if x["n"] == int(m.group(1))]
    if PID.fullmatch(pattern.strip()):   # a proposal ID finds the line it belongs to (its first P-wNN-n), not lines that cite it
        own = [x for x in t["items"] if x["done"] == want_done and not x["dropped"] and x.get("pid") == pattern.strip()]
        if own:
            return own
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


def approve(path: str, pattern: str, date: str, status_file: str | None = None, today: dt.date | None = None) -> dict:
    """The owner approved a proposal (references/dev-link.md §5.2): "ok del proprietario DATE" in the Dipendenze field of the ONE
    open line matching pattern (e.g. "P-w10-1"); with status_file, every key:<chiave> of the line becomes in_lavorazione, with a
    note. Owner decisions (accettato, non_problema, pianificato, sospeso) and keys already risolto are not touched; the fields
    the developer writes (gate, resolved) are never touched."""
    today = today or dt.date.today()
    dt.date.fromisoformat(date)
    t = parse(path)
    if not t:
        raise SystemExit(f"{path} not found")
    hit = _find(t, pattern, False)
    if len(hit) != 1:
        raise SystemExit(f"{len(hit)} open lines match {pattern!r}; be more specific:\n" + "\n".join(f"  #{x['n']} {x['action'][:100]}" for x in hit[:15]))
    x = hit[0]
    ln = t["lines"][x["line"]]
    m = ITEM.match(ln)
    head, body = ln[:m.start(3)], m.group(3).rstrip()
    sep = " — " if " — " in body else " | " if " | " in body else " — "
    f = body.split(sep)
    while len(f) < 4:
        f.append("-")
    ok = f"ok del proprietario {date}"
    deps = f[3].strip()
    if OK_OWNER.search(deps):
        deps = OK_OWNER.sub(ok, deps)
    elif deps.lower().strip(" .") in ("", "-", "nessuna", "nessuno", "n/d"):
        deps = ok
    else:
        deps = f"{deps}; {ok}"
    f[3] = deps
    t["lines"][x["line"]] = head + sep.join(f)
    _write(path, t, today)
    res = dict(item=x, keys=x["keys"], changed=[], skipped=[])
    if status_file and x["keys"]:
        import json
        st = {}
        if os.path.exists(status_file):
            with open(status_file, encoding="utf-8") as fh:
                st = json.load(fh)
        tag = f"Approvata dal proprietario il {date}" + (f" ({x['pid']})" if x["pid"] else "") + "."
        for k in x["keys"]:
            e = st.get(k)
            if isinstance(e, dict) and e.get("status") in DECIDED:
                res["skipped"].append(f"{k}: decisione del proprietario ({e['status']})")
                continue
            if isinstance(e, dict) and e.get("status") == "risolto":
                res["skipped"].append(f"{k}: già risolto (se è tornato, riaprilo: \"ricomparso dopo il gate NN\")")
                continue
            if isinstance(e, dict) and e.get("status") == "in_lavorazione" and tag in (e.get("note") or ""):
                continue
            e = e if isinstance(e, dict) else {}
            old = e.get("status", "nuova")
            e["status"] = "in_lavorazione"
            e["note"] = tag + (" · " + e["note"] if e.get("note") else "")
            st[k] = e
            res["changed"].append(f"{k}: {old} -> in_lavorazione")
        if res["changed"]:
            with open(status_file, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(st, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
    return res


def read_dev_decisions(path: str) -> list[dict]:
    """D-NNN rows of game-developer's DECISIONI.md (table `| ID | Data | Area | Decisione | Fonte | Note |`, or bullets `- D-NNN ...`)."""
    rows, cols = [], None
    for ln in open(path, encoding="utf-8").read().splitlines():
        s_ = ln.strip()
        if s_.startswith("|"):
            c = [x.strip() for x in s_.strip("|").split("|")]
            low = [x.lower() for x in c]
            if "id" in low and any(x.startswith("decision") for x in low):
                cols = {name: low.index(name) for name in low}
                continue
            if c and re.fullmatch(r"D-\d{2,}", c[0]):
                g = lambda name, pos: c[cols[name]] if cols and name in cols and cols[name] < len(c) else (c[pos] if pos < len(c) else "")
                dec = next((c[cols[k]] for k in (cols or {}) if k.startswith("decision") and cols[k] < len(c)), c[3] if len(c) > 3 else "")
                rows.append(dict(id=c[0], date=g("data", 1), area=g("area", 2), decision=dec, source=g("fonte", 4), note=g("note", 5)))
            continue
        m = re.match(r"^\s*[-*]\s*\**(D-\d{2,})\**\s*[:—–-]?\s*(?:\((\d{4}-\d{2}-\d{2})\))?\s*[:—–-]?\s*(.+)$", ln)
        if m:
            rows.append(dict(id=m.group(1), date=m.group(2) or "", area="", decision=m.group(3).strip(), source="", note=""))
    return rows


def sync_decisions(todo_path: str, decisions_path: str, intents_path: str | None = None, write: bool = False, today: dt.date | None = None) -> list[dict]:
    """Decisions of DECISIONI.md missing from BOTH launch registers ("Decisioni prese" of TODO.md and 00-intenzioni.md) are copied
    under "Decisioni prese" with "fonte: DECISIONI.md D-NNN" (references/dev-link.md §4.2). Rows that came from launch/ (their
    Fonte cites launch/, TODO.md or 00-intenzioni) are not copied back. DECISIONI.md is only read."""
    today = today or dt.date.today()
    have = open(todo_path, encoding="utf-8").read() if os.path.exists(todo_path) else ""
    if intents_path and os.path.exists(intents_path):
        have += "\n" + open(intents_path, encoding="utf-8").read()
    todo = []
    for d in read_dev_decisions(decisions_path):
        if re.search(rf"\b{re.escape(d['id'])}\b", have):
            continue
        if re.search(r"launch/|00-intenzioni|TODO\.md", d["source"], re.I):
            continue
        area = re.sub(r"[*_`]", "", d["area"]).strip()
        line = (f"- **{area[:1].upper() + area[1:]}:** " if area else "- ") + d["decision"].strip()
        line += f" (fonte: DECISIONI.md {d['id']}" + (f", {d['date']}" if d["date"] else "") + ")"
        if d["note"]:
            line += f" — {d['note']}"
        todo.append(dict(d, line=line))
    if write and todo:
        t = parse(todo_path) or dict(lines=["# TODO", f"Aggiornato: {today.isoformat()}", ""], items=[], sections=[])
        lines = t["lines"]
        idx = next((k for k, ln in enumerate(lines) if re.match(r"^#{2,3}\s+Decisioni prese", ln, re.I)), None)
        if idx is None:
            first = next((k for k, ln in enumerate(lines) if re.match(r"^#{2,3}\s+", ln)), len(lines))
            lines[first:first] = ["## Decisioni prese", ""]
            idx = first
        end = next((k for k in range(idx + 1, len(lines)) if re.match(r"^#{1,3}\s+", lines[k])), len(lines))
        while end > idx + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = [x["line"] for x in todo]
        t["lines"] = lines
        _write(todo_path, t, today)
    return todo


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
    p = sub.add_parser("approve"); p.add_argument("pattern"); p.add_argument("--date", required=True); p.add_argument("--status-file")
    p = sub.add_parser("sync-decisions"); p.add_argument("--decisions", required=True); p.add_argument("--intents"); p.add_argument("--write", action="store_true")
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
    elif a.cmd == "approve":
        r = approve(a.file, a.pattern, a.date, a.status_file, today)
        print(f"approvata: #{r['item']['n']} {r['item']['action'][:100]} (ok del proprietario {a.date})")
        for c in r["changed"]:
            print("  issue_status: " + c)
        for c in r["skipped"]:
            print("  non tocco " + c)
        if a.status_file and not r["keys"]:
            print("  la riga non ha key:<chiave>: issue_status.json non cambia")
    elif a.cmd == "sync-decisions":
        if not os.path.exists(a.decisions):
            print(f"{a.decisions} non c'è (niente game-developer): nessuna decisione da importare.")
            return
        new = sync_decisions(a.file, a.decisions, a.intents, a.write, today)
        print(("IMPORTATE" if a.write else "DA IMPORTARE (aggiungi --write)") + f": {len(new)}")
        for x in new:
            print("  " + x["line"])
    else:
        add(a.file, a.section, a.text, today)
        print(f"aggiunta in «{a.section}»")


if __name__ == "__main__":
    main()
