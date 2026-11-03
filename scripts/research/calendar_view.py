#!/usr/bin/env python3
"""The "Calendario" tab and the Roadmap of STATUS.html (used by status_page.py; no network, everything read from launch/).

Calendar: every dated thing of the project on month grids, from the current month (or the oldest overdue item) to the launch:
  launch/calendar.md     the steps of `## ✅ Passi in ordine` (👤 / 🤖 / 👤+🤖, done, overdue) and the dated rows of its tables
                         (fixed dates, tripwires of the plan and of the pre-mortem; "~~struck~~" rows are skipped)
  launch/TODO.md         lines with a date that are not already a step of the calendar
  launch/_raw/steam_events_deadlines.json   Valve deadlines, Next Fest and themed fests, seasonal sales (steam_events.py)
  launch/_raw/promo_events_deadlines.json   application deadlines and air dates of online showcases (promo_events.py)
  launch/fg/timeline.csv focus-group waves already run;  launch/_raw/wl_plan.json   the launch date
  status.json -> roadmap the key milestones (also drawn as the Roadmap)
Click a day: a panel lists what is due with details and links; hover: a small preview; a 14-day agenda on top.

Roadmap: only the real key milestones (closed test, Steam Direct, Coming Soon page, free beta, public demo, Next Fest, launch, 1.0).
status.json -> "roadmap": {"note": "...", "milestones": [{"date", "end"?, "title", "phase"?, "what", "needs", "state"? (done|next|later),
"step"? (number in calendar.md), "approx"? (bool)}]}. A milestone without a date is shown at the end as "data da decidere".
Without status.json -> roadmap the milestones are guessed from the calendar steps by keywords (best effort, labelled as such).
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import os
import re

import weblinks

MONTHS = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
MON3 = "gen feb mar apr mag giu lug ago set ott nov dic".split()
WEEKDAYS = "lun mar mer gio ven sab dom".split()
KIND = {"passo": "Passo", "todo": "TODO", "steam": "Evento Steam", "promo": "Showcase online", "scadenza": "Scadenza", "evento": "Evento",
        "ondata": "Focus group", "gate": "Cancello", "tripwire": "Tripwire", "lancio": "Lancio", "traguardo": "Traguardo"}
OWNER = {"me": "👤 Tu", "claude": "🤖 Claude", "both": "👤+🤖 Insieme", "none": "Evento"}
ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _j(p: str):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def plain(md: str) -> str:
    """Markdown -> plain text for titles (no **, `, links kept as their text)."""
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", md or "")
    t = re.sub(r"[*`]", "", t).replace("⭐ mossa top · ", "")
    return re.sub(r"\s+", " ", t).strip(" ·")


def title_of(md: str) -> str:
    """The bold part of a step ('**Paga Steam Direct** (100 $...)' -> 'Paga Steam Direct'), else the plain text cut at 110 chars."""
    m = re.search(r"\*\*(.+?)\*\*", md or "")
    t = plain(m.group(1) if m else md)
    return t if len(t) <= 110 else t[:107].rstrip() + "…"


def rich(md: str) -> str:
    """Escaped HTML of a markdown-ish line, with bold, code and clickable URLs (safe: the text is escaped first)."""
    t = esc(md)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return weblinks.linkify_text(t)


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", plain(s).lower()).strip()


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-zà-ù0-9]{5,}", plain(s).lower())}


def item(date, title, kind, owner="none", *, end=None, state=None, details="", source="", step=None, links=(), today=None, approx=False):
    d = _d(date)
    if not d:
        return None
    task = owner in ("me", "claude", "both") and kind not in ("evento", "lancio", "scadenza", "traguardo")
    if state is None:
        state = "event" if not task else "open"
    if task and state == "open" and today and d < today:
        state = "overdue"
    return dict(date=d.isoformat(), end=(_d(end).isoformat() if _d(end) and _d(end) > d else None), title=title, kind=kind, owner=owner, state=state,
                details=details, source=source, step=step, links=list(links), approx=approx)


# ---------------------------------------------------------------- collecting
def _tables(md: str):
    """Yield (heading, header cells, row cells) for every markdown table row."""
    lines, head, i = md.replace("\r", "").split("\n"), "", 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            head = ln.lstrip("#").strip()
        if ln.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            hdr, j = cells(ln), i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                yield head, hdr, cells(lines[j])
                j += 1
            i = j
            continue
        i += 1


def from_tables(md: str, today: dt.date) -> list[dict]:
    out = []
    for head, hdr, row in _tables(md):
        if not row or not ISO.search(row[0]) or "~~" in row[0]:
            continue
        dates = ISO.findall(row[0])
        h = [x.lower() for x in hdr]
        typ = row[h.index("tipo")].lower() if "tipo" in h and h.index("tipo") < len(row) else ""
        is_trip = "tripwire" in head.lower() or "tripwire" in typ
        kind = ("ondata" if "ondata" in typ else "gate" if "gate" in typ else "tripwire" if is_trip else "scadenza" if "scadenza" in typ else "evento")
        rec = re.match(r"\s*ogni\s+(\w+)", row[0], re.I)
        if is_trip and "tipo" not in h:
            title = "Tripwire: " + " · ".join(plain(c) for c in row[1:3] if c)
            details = " · ".join(f"{hdr[k]}: {row[k]}" for k in range(3, min(len(hdr), len(row))) if row[k])
        else:
            title = plain(row[1]) if len(row) > 1 else ""
            details = " · ".join(f"{hdr[k]}: {row[k]}" for k in range(2, min(len(hdr), len(row))) if row[k] and hdr[k].lower() != "tipo")
        if rec:
            title = f"Da qui ogni {rec.group(1)}: {title}"
        owner = "both" if kind in ("tripwire", "gate") else "claude" if kind == "ondata" else "none"
        st = "event" if owner == "none" else ("done" if _d(dates[0]) < today and kind == "ondata" else None)
        it = item(dates[0], title, kind, owner, end=dates[1] if len(dates) > 1 else None, state=st, details=details, source=f"calendar.md · {head}", today=today)
        if it:
            out.append(it)
    return out


def collect(root: str, plan: dict, st: dict, today: dt.date, todo: dict | None = None) -> list[dict]:
    items: list = []
    steps = [dict(s, phase=p["title"]) for p in plan.get("phases", []) for s in p["steps"]]
    for s in steps:
        if not s.get("due"):
            continue
        ph = s["phase"].lower()
        txt = s["text"]
        kind = ("steam" if "eventi steam" in ph else "promo" if "eventi online" in ph or "showcase" in ph else "ondata" if re.search(r"ondata\s+\d|focus group", txt, re.I)
                else "tripwire" if "tripwire" in txt.lower() else "passo")
        state = "done" if s["done"] else None
        it = item(s["due"], title_of(txt), kind, s["owner"] if s["owner"] != "none" else "both", state=state, today=today, step=s["n"], source=f"calendar.md · {plain(s['phase'])}",
                  details="\n".join([txt] + list(s.get("notes") or [])))
        if it:
            items.append(it)
    step_keys = {(it["date"], _norm(it["title"])) for it in items}
    step_titles = {_norm(it["title"]) for it in items}
    # tables of calendar.md (fixed dates, tripwires): skipped when a step on the same day says the same thing
    for it in from_tables(plan.get("before", "") + "\n" + plan.get("after", ""), today):
        same_day = [x for x in items if x["date"] == it["date"]]
        if any(len(_words(x["title"] + " " + x["details"]) & _words(it["title"])) >= 2 for x in same_day):
            continue
        items.append(it)
    # TODO.md lines with a date that are not a step already
    if todo:
        for x in todo.get("items", []):
            if x.get("dropped") or not x.get("due_date"):
                continue
            t = title_of(x["action"])
            if _norm(t) in step_titles or (x["due_date"].isoformat(), _norm(t)) in step_keys:
                continue
            if any(x["due_date"].isoformat() == i["date"] and len(_words(i["title"]) & _words(t)) >= 2 for i in items):
                continue
            meta = " · ".join(v for v in (x.get("hours"), f"misura: {x['metric']}" if x.get("metric") else "", x.get("done_note")) if v)
            it = item(x["due_date"], t, "todo", x.get("owner") or "both", state="done" if x["done"] else None, today=today, source=f"TODO.md · {plain(x['section'])}",
                      details=x["action"] + (f"\n{meta}" if meta else ""))
            if it:
                items.append(it)
    # Steam events: fest ranges, themed fests, sales, Valve deadlines
    se = _j(os.path.join(root, "_raw", "steam_events_deadlines.json")) or {}
    for nf in se.get("next_fests") or []:
        if nf.get("chosen") or len(se.get("next_fests") or []) == 1:
            it = item(nf.get("start"), nf["name"], "steam", end=nf.get("end"), details=f"Iscrizione entro {nf.get('registration_deadline') or '?'}", source="steam_events.py",
                      links=["https://partner.steamgames.com/doc/marketing/upcoming_events"])
            if it:
                items.append(it)
    for f in se.get("themed_fests") or []:
        if f.get("start"):
            it = item(f["start"], f["name"], "steam", end=f.get("end"), details=f"Fest a tema di Steam ({f.get('status', '')}): {f.get('matters_for', '')}", source="steam_events.py")
            if it:
                items.append(it)
    for w in se.get("warnings") or []:
        if w.get("start"):
            it = item(w["start"], w["event"], "evento", end=w.get("end"), details=w.get("text", ""), source="steam_events.py")
            if it:
                items.append(it)
    for s_ in se.get("steps") or []:
        if s_.get("deadline") and s_.get("deadline") != s_.get("due"):
            it = item(s_["deadline"], f"Scadenza Valve: {title_of(s_.get('text', ''))}", "scadenza", details=s_.get("note", ""), source="steam_events.py")
            if it and not any(x["date"] == it["date"] and x["kind"] == "scadenza" for x in items):
                items.append(it)
    # online showcases: application deadlines and air dates
    pe = _j(os.path.join(root, "_raw", "promo_events_deadlines.json")) or {}
    for m in pe.get("matches") or []:
        if not m.get("plan"):
            continue
        url = m.get("url") or ""
        info = "\n".join(v for v in (f"**Prossimo passo:** {m['next_step']}" if m.get("next_step") else "", m.get("why"), f"**Possibilità:** {m.get('odds')}" if m.get("odds") else "",
                                      f"**Serve:** {', '.join(m.get('requires') or [])}" if m.get("requires") else "", f"**Costo:** {m['cost_note']}" if m.get("cost_note") else "") if v)
        if m.get("deadline"):
            it = item(m["deadline"], f"Chiudono le candidature: {m['name']}", "scadenza", details=info, source="promo_events.py", links=[url] if url else [], approx=bool(m.get("estimated")))
            if it:
                items.append(it)
        if m.get("start"):
            it = item(m["start"], f"In onda: {m['name']}", "evento", details=info, source="promo_events.py", links=[u for u in (m.get("lineup") or url,) if u])
            if it:
                items.append(it)
    # focus-group waves already run (one entry per day)
    tl = os.path.join(root, "fg", "timeline.csv")
    if os.path.exists(tl):
        with open(tl, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        by: dict = {}
        for r in rows:
            by.setdefault(r.get("date"), []).append(r)
        for d, rs in by.items():
            txt = "; ".join(f"ondata {r['wave']}{' (' + r['stage'] + ')' if r.get('stage') else ''}: {str(r['score']).replace('.', ',')}" for r in rs)
            it = item(d, "Focus group: " + ", ".join(f"ondata {r['wave']}" for r in rs), "ondata", "claude", state="done", details=txt + " (SIMULATO)", source="fg/timeline.csv")
            if it:
                items.append(it)
    # launch
    wp = _j(os.path.join(root, "_raw", "wl_plan.json")) or {}
    launch = _d(wp.get("launch")) or _d((pe.get("timeline") or {}).get("launch")) or _d(se.get("launch"))
    if launch:
        same = [x for x in items if x["date"] == launch.isoformat() and re.search(r"\b(lancio|uscita|release|launch)\b", x["title"], re.I)]
        for x in same:
            x["kind"] = "lancio"            # the launch step itself becomes the launch marker of the calendar
        if not same and not any(x["kind"] == "lancio" for x in items):
            items.append(item(launch, "Uscita del gioco", "lancio", details="Data di uscita del piano (wl_plan.json)", source="_raw/wl_plan.json"))
    for it in items:
        it["html"] = "<br>".join(rich(x) for x in (it.pop("details") or "").split("\n") if x.strip())
        it["links"] = [u for u in it["links"] if weblinks.SAFE.match(u or "")]
    items.sort(key=lambda x: (x["date"], {"lancio": 0, "traguardo": 1, "scadenza": 2}.get(x["kind"], 5), x["title"]))
    return items


# ---------------------------------------------------------------- roadmap
GUESS = [("test", r"\b(amici|friends|closed test|tester esterni|test con)\b", "Test con persone vere"),
         ("direct", r"steam direct", "Steam Direct pagato"),
         ("page", r"coming soon", "Pagina Coming Soon su Steam"),
         ("beta", r"\bbeta\b.*\bitch\b|\bitch\b.*\bbeta\b|beta (gratuita|pubblica)", "Beta gratuita"),
         ("demo", r"demo (steam )?pubblica|demo steam pubblica|pubblica la demo", "Demo Steam pubblica"),
         ("fest", r"next fest", "Steam Next Fest"),
         ("launch", r"^\W*lancio\b|\buscita in early access\b|\brelease\b", "Uscita")]


def roadmap(root: str, st: dict, plan: dict, today: dt.date) -> dict | None:
    """{'note', 'guessed', 'milestones': [{date, end, title, phase, what, needs, state, step, approx}]} with state done / next / later."""
    steps = {s["n"]: s for p in plan.get("phases", []) for s in p["steps"]}
    rm = st.get("roadmap") or {}
    ms, guessed = [dict(m) for m in rm.get("milestones") or [] if m.get("title")], False
    if not ms:
        seen = set()
        for p in plan.get("phases", []):
            for s in p["steps"]:
                if not s.get("due"):
                    continue
                for key, rx, name in GUESS:
                    if key not in seen and re.search(rx, plain(s["text"]), re.I):
                        seen.add(key)
                        ms.append(dict(date=s["due"], title=name, what=title_of(s["text"]), step=s["n"]))
                        break
        guessed = bool(ms)
    if not ms:
        return None
    for m in ms:
        s = steps.get(m.get("step"))
        if not m.get("state"):
            d = _d(m.get("date"))
            m["state"] = "done" if (s and s["done"]) or (not s and d and (_d(m.get("end")) or d) < today) else "todo"
        m["late"] = m["state"] != "done" and _d(m.get("date")) is not None and _d(m.get("date")) < today
    ms.sort(key=lambda m: (_d(m.get("date")) is None, m.get("date") or "9999"))
    nxt = next((m for m in ms if m["state"] not in ("done",)), None)
    for m in ms:
        if m["state"] not in ("done", "next", "later"):
            m["state"] = "next" if m is nxt else "later"
    return dict(note=rm.get("note", ""), milestones=ms, guessed=guessed)


def _fdate(d: dt.date | None, approx=False) -> str:
    return "data da decidere" if not d else ("~" if approx else "") + f"{d.day} {MON3[d.month - 1]} {d.year}"


def roadmap_html(rm: dict | None, today: dt.date, compact: bool = False) -> str:
    if not rm:
        return ""
    ms = rm["milestones"]
    dated = [_d(m.get("date")) for m in ms if _d(m.get("date"))]
    first, last = (min(dated + [today]), max(dated + [today])) if dated else (today, today)
    span = max((last - first).days, 1)
    pos = lambda d: round(100 * (d - first).days / span, 2)
    done = sum(1 for m in ms if m["state"] == "done")
    nxt = next((m for m in ms if m["state"] == "next"), None)
    days_to = ((_d(nxt.get("date")) - today).days if nxt and _d(nxt.get("date")) else None)
    # proportional rail: today and every milestone at its real date
    dots = "".join(f'<a class="rm-dot {m["state"]}{" late" if m.get("late") else ""}" style="left:{pos(_d(m["date"]))}%" href="#cal-{esc(m["date"])}" '
                   f'title="{esc(_fdate(_d(m["date"]), m.get("approx")) + " · " + m["title"])}"><span class="sr">{esc(m["title"])}</span></a>' for m in ms if _d(m.get("date")))
    months, d = [], dt.date(first.year, first.month, 1)
    while d <= last:
        if d >= first:
            months.append(f'<span class="rm-m" style="left:{pos(d)}%">{MON3[d.month - 1]}{" " + str(d.year)[2:] if d.month == 1 else ""}</span>')
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    rail = (f'<div class="rm-rail" aria-hidden="false"><div class="rm-track"><span class="rm-fill" style="width:{pos(today)}%"></span></div>{"".join(months)}{dots}'
            f'<span class="rm-today" style="left:{pos(today)}%"><b>Oggi</b></span></div>')
    cards = []
    for k, m in enumerate(ms, 1):
        d = _d(m.get("date"))
        e = _d(m.get("end"))
        when = (_fdate(d, m.get("approx")).rsplit(" ", 1)[0] if e and d and e.year == d.year else _fdate(d, m.get("approx"))) + (f" → {_fdate(e)}" if e else "")
        badge = {"done": "Fatto", "next": "Prossimo", "later": "Più avanti"}[m["state"]] + (" · in ritardo" if m.get("late") else "")
        rel = ""
        if d and m["state"] != "done":
            n = (d - today).days
            rel = "oggi" if n == 0 else f"tra {n} giorni" if 0 < n <= 60 else f"tra {round(n / 7)} settimane" if n > 0 and n <= 180 else f"tra {round(n / 30.4)} mesi" if n > 0 else f"{-n} giorni fa"
        link = (f'<a class="rm-go" href="#cal-{esc(m["date"])}">Vedi il giorno</a>' if d else "") + (f'<a class="rm-go" href="#step-{int(m["step"])}">Passo {int(m["step"])}</a>' if str(m.get("step") or "").isdigit() else "")
        cards.append(f'<li class="rm-card {m["state"]}{" late" if m.get("late") else ""}"><div class="rm-mark" aria-hidden="true">{"✓" if m["state"] == "done" else k}</div>'
                     f'<div class="rm-body"><div class="rm-when"><span>{esc(when)}</span>{f"<em>{esc(rel)}</em>" if rel else ""}</div>'
                     f'<h3>{esc(m["title"])}</h3>' + (f'<p class="rm-phase">{esc(m["phase"])}</p>' if m.get("phase") else "")
                     + (f'<p><b>Cosa succede</b> {rich(m["what"])}</p>' if m.get("what") else "") + (f'<p><b>Serve</b> {rich(m["needs"])}</p>' if m.get("needs") else "")
                     + f'<div class="rm-foot"><span class="rm-badge {m["state"]}">{esc(badge)}</span>{link}</div></div></li>')
    head = (f'<p class="sub">{done} di {len(ms)} traguardi raggiunti' + (f' · prossimo: <strong>{esc(nxt["title"])}</strong>' + (f" ({'oggi' if days_to == 0 else f'tra {days_to} giorni' if days_to and days_to > 0 else f'in ritardo di {-days_to} giorni' if days_to else ''})" if days_to is not None else "") if nxt else "") + "</p>")
    note = f'<p class="rm-note">{rich(rm["note"])}</p>' if rm.get("note") else ""
    guess = '<p class="note">Traguardi ricavati in automatico dai passi del calendario: Claude li sostituisce con quelli veri in <code>status.json</code> → <code>roadmap</code>.</p>' if rm.get("guessed") else ""
    chips = "".join(f'<a class="rm-chip {m["state"]}{" late" if m.get("late") else ""}" href="#cal-{esc(m["date"])}"><b>{esc(_fdate(_d(m["date"]), m.get("approx")).rsplit(" ", 1)[0])}</b> {esc(m["title"])}</a>'
                    if _d(m.get("date")) else f'<span class="rm-chip later"><b>da decidere</b> {esc(m["title"])}</span>' for m in ms)
    return (f'<h2>Roadmap</h2><div class="card roadmap{" compact" if compact else ""}">{head}{note}{rail}'
            + (f'<div class="rm-chips">{chips}</div>' if compact else f'<ol class="rm-list">{"".join(cards)}</ol>') + f'{guess}</div>')


# ---------------------------------------------------------------- calendar
def _month_iter(a: dt.date, b: dt.date):
    d = dt.date(a.year, a.month, 1)
    while d <= b:
        yield d
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def _days_of(it: dict) -> list[str]:
    d0, d1 = _d(it["date"]), _d(it.get("end")) or _d(it["date"])
    return [(d0 + dt.timedelta(days=k)).isoformat() for k in range(min((d1 - d0).days, 40) + 1)]


def _cls(it: dict) -> str:
    return f'o-{it["owner"]} k-{it["kind"]} s-{it["state"]}'


def calendar_html(items: list[dict], rm: dict | None, today: dt.date, launch: dt.date | None = None) -> str:
    if not items:
        return ""
    by: dict = {}
    for k, it in enumerate(items):
        it["id"] = k
        for d in _days_of(it):
            by.setdefault(d, []).append(k)
    overdue = [it for it in items if it["state"] == "overdue"]
    start = min([today] + [_d(it["date"]) for it in overdue])
    launch = launch or max((_d(it["date"]) for it in items), default=today)
    end = max(launch, today)
    if (end - today).days > 550:
        end = today + dt.timedelta(days=550)
    months = list(_month_iter(start, end))
    cur = next((k for k, m in enumerate(months) if m.year == today.year and m.month == today.month), 0)
    grids = []
    for k, m in enumerate(months):
        nxt = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        cells = ['<div class="cal-dow">' + "".join(f"<span>{w}</span>" for w in WEEKDAYS) + "</div><div class=\"cal-days\">"]
        cells += ['<span class="cal-pad"></span>'] * m.weekday()
        d = m
        while d < nxt:
            iso = d.isoformat()
            ids = by.get(iso, [])
            its = [items[i] for i in ids]
            flags = " ".join(x for x in ("today" if d == today else "", "past" if d < today else "", "has" if its else "", "late" if any(i["state"] == "overdue" for i in its) else "",
                                         "launch" if any(i["kind"] == "lancio" for i in its) else "", "ms" if any(i["kind"] == "traguardo" for i in its) else "", "we" if d.weekday() >= 5 else "") if x)
            pills = "".join(f'<span class="pill {_cls(i)}">{esc(i["title"][:38])}</span>' for i in its[:3]) + (f'<span class="more">+{len(its) - 3}</span>' if len(its) > 3 else "")
            dots = "".join(f'<i class="{_cls(i)}"></i>' for i in its[:5])
            aria = f"{d.day} {MONTHS[d.month - 1]}: " + (f"{len(its)} voci" if its else "niente")
            cells.append(f'<button type="button" class="cal-d {flags}" data-d="{iso}" id="cal-{iso}" aria-label="{esc(aria)}"><span class="n">{d.day}</span>'
                         + (f'<span class="pills">{pills}</span><span class="dots">{dots}</span>' if its else "") + "</button>")
            d += dt.timedelta(days=1)
        cells.append("</div>")
        n_items = len({i for dd, ids in by.items() if dd[:7] == m.isoformat()[:7] for i in ids})
        grids.append(f'<section class="cal-month" data-m="{k}"{"" if k == cur else " hidden"} aria-label="{MONTHS[m.month - 1]} {m.year}">'
                     f'<h3 class="cal-title">{MONTHS[m.month - 1].capitalize()} {m.year} <span class="note">{n_items} voci</span></h3>{"".join(cells)}</section>')
    # agenda: overdue + next 14 days
    ag = []
    for k in range(14):
        d = today + dt.timedelta(days=k)
        its = [items[i] for i in by.get(d.isoformat(), []) if items[i]["state"] != "done"]
        if not its:
            continue
        lab = "Oggi" if k == 0 else "Domani" if k == 1 else f"{WEEKDAYS[d.weekday()].capitalize()} {d.day} {MON3[d.month - 1]}"
        ag.append(f'<button type="button" class="ag-day{" today" if k == 0 else ""}" data-d="{d.isoformat()}"><span class="ag-h">{esc(lab)}</span>'
                  + "".join(f'<span class="ag-i {_cls(i)}"><i></i>{esc(i["title"][:60])}</span>' for i in its[:4]) + (f'<span class="more">+{len(its) - 4} altre</span>' if len(its) > 4 else "") + "</button>")
    late_box = ""
    if overdue:
        late_box = ('<div class="cal-late"><strong>In ritardo ({})</strong>'.format(len(overdue)) + "".join(
            f'<button type="button" class="late-i" data-d="{it["date"]}"><span class="when">{_fdate(_d(it["date"]))}</span> {esc(OWNER.get(it["owner"], ""))} · {esc(it["title"][:80])}</button>' for it in overdue[:8]) + "</div>")
    counts = {}
    for it in items:
        if it["state"] != "done":
            counts[it["owner"]] = counts.get(it["owner"], 0) + 1
    legend = ('<div class="cal-legend" role="group" aria-label="Filtra il calendario">'
              '<button type="button" data-f="all" aria-pressed="true">Tutto</button>'
              f'<button type="button" data-f="me" aria-pressed="false"><i class="o-me"></i>👤 Tu <span>{counts.get("me", 0)}</span></button>'
              f'<button type="button" data-f="claude" aria-pressed="false"><i class="o-claude"></i>🤖 Claude <span>{counts.get("claude", 0)}</span></button>'
              f'<button type="button" data-f="both" aria-pressed="false"><i class="o-both"></i>👤+🤖 Insieme <span>{counts.get("both", 0)}</span></button>'
              f'<button type="button" data-f="none" aria-pressed="false"><i class="o-none"></i>Eventi e scadenze <span>{counts.get("none", 0)}</span></button>'
              '<span class="cal-key"><i class="k-late"></i>in ritardo · <i class="k-today"></i>oggi · <i class="k-launch"></i>lancio</span></div>')
    data = {str(it["id"]): {k: it[k] for k in ("date", "end", "title", "kind", "owner", "state", "html", "source", "step", "links", "approx")} for it in items}
    payload = json.dumps(dict(items=data, days=by, today=today.isoformat(), kind=KIND, owner=OWNER), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    n_open = sum(1 for it in items if it["state"] in ("open", "overdue"))
    intro = (f'<p class="sub">{len(items)} date dal piano, dalla TODO, dagli eventi Steam e online e dal focus group · {n_open} cose ancora da fare · '
             f'{len(overdue)} in ritardo. Clicca un giorno per i dettagli; passa sopra per un\'anteprima.</p>')
    return (f'<h2>Calendario</h2>{intro}<div class="cal" id="cal" data-f="all">'
            f'<div class="agenda"><div class="ag-head"><strong>Prossimi 14 giorni</strong></div><div class="ag-row">{"".join(ag) or "<p class=note>Niente in scadenza nei prossimi 14 giorni.</p>"}</div>{late_box}</div>'
            f'{legend}<div class="cal-wrap"><div class="cal-main"><div class="cal-nav"><button type="button" class="cal-prev" aria-label="Mese precedente">‹</button>'
            f'<button type="button" class="cal-today">Oggi</button><button type="button" class="cal-next" aria-label="Mese successivo">›</button>'
            f'<select class="cal-pick" aria-label="Vai al mese">' + "".join(f'<option value="{k}"{" selected" if k == cur else ""}>{MONTHS[m.month - 1]} {m.year}</option>' for k, m in enumerate(months))
            + f'</select></div>{"".join(grids)}</div>'
            f'<aside class="cal-panel" aria-live="polite"><div class="cal-panel-in"><p class="note">Clicca un giorno del calendario: qui compare cosa c\'è da fare, chi lo fa, i dettagli e i link.</p></div></aside></div>'
            f'<div class="cal-tip" role="tooltip" hidden></div></div><script type="application/json" id="cal-data">{payload}</script>')


CSS = """
.cal{--o-me:#8a63d2;--o-claude:#2a78d6;--o-both:#0e8fa8;--o-none:#7d7a72;position:relative}
:root[data-theme="dark"] .cal{--o-me:#f08a4b;--o-claude:#5a9cf0;--o-both:#2dbb88;--o-none:#a68bea}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])) .cal{--o-me:#f08a4b;--o-claude:#5a9cf0;--o-both:#2dbb88;--o-none:#a68bea}}
.cal .o-me{--c:var(--o-me)}.cal .o-claude{--c:var(--o-claude)}.cal .o-both{--c:var(--o-both)}.cal .o-none{--c:var(--o-none)}
.agenda{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:12px 14px;margin:0 0 12px}
.ag-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.ag-row{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;scroll-snap-type:x mandatory}
.ag-day{flex:0 0 min(230px,78%);scroll-snap-align:start;text-align:left;background:var(--bg);border:1px solid var(--ring);border-radius:12px;padding:10px;cursor:pointer;font:inherit;color:var(--ink);display:flex;flex-direction:column;gap:5px}
.ag-day.today{border-color:var(--s1);box-shadow:inset 0 0 0 1px var(--s1)}.ag-day:hover{border-color:var(--axis)}.ag-h{font-weight:700;font-size:.85rem}
.ag-i{display:flex;gap:7px;align-items:flex-start;font-size:.84rem;line-height:1.3}.ag-i i{flex:none;width:8px;height:8px;border-radius:50%;background:var(--c);margin-top:5px}.ag-i.s-overdue{color:var(--crit)}
.cal-late{margin-top:10px;padding-top:10px;border-top:1px dashed var(--grid);display:flex;flex-wrap:wrap;gap:6px;align-items:center}.cal-late strong{color:var(--crit);margin-right:4px}
.late-i{font:inherit;font-size:.82rem;background:transparent;border:1px solid color-mix(in srgb,var(--crit) 45%,transparent);color:var(--ink);border-radius:999px;padding:3px 10px;cursor:pointer;text-align:left}.late-i .when{color:var(--crit);font-weight:600}
.cal-legend{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:0 0 10px}.cal-legend button{font:inherit;font-size:.83rem;display:inline-flex;gap:6px;align-items:center;background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:999px;padding:4px 11px;cursor:pointer}
.cal-legend button span{color:var(--muted);font-variant-numeric:tabular-nums}.cal-legend button[aria-pressed="true"]{border-color:var(--s1);box-shadow:inset 0 0 0 1px var(--s1)}
.cal-legend i,.cal-key i{display:inline-block;width:10px;height:10px;border-radius:3px;background:var(--c)}.cal-key{color:var(--muted);font-size:.8rem;margin-left:auto;display:inline-flex;gap:5px;align-items:center}
.cal-key .k-late{background:transparent;border:2px solid var(--crit)}.cal-key .k-today{background:transparent;border:2px solid var(--s1);border-radius:50%}.cal-key .k-launch{background:linear-gradient(135deg,#f5b400,#e5732f)}
.cal-wrap{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:14px;align-items:start}
.cal-main{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:12px}
.cal-nav{display:flex;gap:6px;align-items:center;margin-bottom:6px}.cal-nav button,.cal-nav select{font:inherit;font-size:.9rem;background:var(--bg);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:5px 11px;cursor:pointer}
.cal-nav select{margin-left:auto;text-transform:capitalize}.cal-prev,.cal-next{font-size:1.1rem!important;line-height:1;padding:4px 12px!important}
.cal-title{margin:6px 2px 8px;font-size:1.15rem}.cal-title .note{font-weight:400;margin-left:6px}
.cal-dow,.cal-days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px}.cal-dow span{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;padding:0 6px 2px}
.cal-d{position:relative;min-height:92px;display:flex;flex-direction:column;align-items:stretch;gap:3px;text-align:left;background:var(--bg);border:1px solid var(--grid);border-radius:10px;padding:5px;cursor:pointer;font:inherit;color:var(--ink);overflow:hidden}
.cal-d:hover,.cal-d:focus-visible{border-color:var(--axis);outline:none;box-shadow:0 2px 10px rgba(0,0,0,.08)}.cal-d.we{background:color-mix(in srgb,var(--bg) 70%,var(--grid))}
.cal-d .n{font-size:.8rem;font-weight:600;color:var(--ink2);font-variant-numeric:tabular-nums}.cal-d.past{opacity:.62}.cal-d.past.late{opacity:1}
.cal-d.today{border:2px solid var(--s1)}.cal-d.today .n{background:var(--s1);color:#fff;border-radius:999px;padding:0 7px;align-self:flex-start}
.cal-d.late{box-shadow:inset 0 0 0 1px var(--crit);border-color:var(--crit)}.cal-d.launch{background:linear-gradient(135deg,color-mix(in srgb,#f5b400 22%,var(--bg)),color-mix(in srgb,#e5732f 18%,var(--bg)))}
.cal-d.sel{outline:2px solid var(--ink);outline-offset:1px}
.pills{display:flex;flex-direction:column;gap:2px;min-width:0}.pill{display:block;font-size:.7rem;line-height:1.25;padding:2px 5px;border-radius:5px;background:color-mix(in srgb,var(--c) 16%,transparent);border-left:3px solid var(--c);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pill.s-done{opacity:.55;text-decoration:line-through}.pill.s-overdue{background:color-mix(in srgb,var(--crit) 16%,transparent);border-left-color:var(--crit)}.pill.k-lancio,.pill.k-traguardo{font-weight:700}.pill.k-traguardo,.pill.k-lancio{background:color-mix(in srgb,#f5b400 22%,transparent);border-left-color:#e0a100}
.more{font-size:.68rem;color:var(--muted);padding-left:3px}.dots{display:none;gap:3px;flex-wrap:wrap}.dots i{width:7px;height:7px;border-radius:50%;background:var(--c)}.dots i.s-overdue{background:var(--crit)}
.cal[data-f="me"] .pill:not(.o-me):not(.o-both),.cal[data-f="claude"] .pill:not(.o-claude):not(.o-both),.cal[data-f="both"] .pill:not(.o-both),.cal[data-f="none"] .pill:not(.o-none){display:none}
.cal[data-f="me"] .dots i:not(.o-me):not(.o-both),.cal[data-f="claude"] .dots i:not(.o-claude):not(.o-both),.cal[data-f="both"] .dots i:not(.o-both),.cal[data-f="none"] .dots i:not(.o-none){display:none}
.cal-panel{position:sticky;top:64px;background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:14px;max-height:calc(100vh - 84px);overflow:auto}
.cal-panel h3{margin:0 0 2px;font-size:1.05rem}.cal-panel .cnt{color:var(--muted);font-size:.85rem;margin:0 0 10px}
.ev{border:1px solid var(--grid);border-left:4px solid var(--c);border-radius:10px;padding:9px 11px;margin:8px 0;background:var(--bg)}.ev.s-overdue{border-left-color:var(--crit)}.ev.s-done{opacity:.7}
.ev .t{font-weight:600;line-height:1.35}.ev .tags{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 5px}.tag{font-size:.72rem;border-radius:999px;padding:1px 8px;border:1px solid var(--ring);color:var(--ink2);background:var(--surface)}
.tag.own{border-color:var(--c);color:var(--ink)}.tag.late{border-color:var(--crit);color:var(--crit);font-weight:600}.tag.done{border-color:var(--good)}
.ev .d{font-size:.85rem;color:var(--ink2);margin-top:6px;overflow-wrap:anywhere}.ev .src{font-size:.75rem;color:var(--muted);margin-top:6px}.ev .lk{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.ev .lk a{font-size:.8rem}
.cal-tip{position:absolute;z-index:40;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:10px;padding:8px 10px;box-shadow:0 8px 24px rgba(0,0,0,.18);font-size:.8rem;max-width:280px}
.cal-tip b{display:block;margin-bottom:4px}.cal-tip div{display:flex;gap:6px;align-items:flex-start;margin:2px 0}.cal-tip i{flex:none;width:8px;height:8px;border-radius:50%;background:var(--c);margin-top:4px}
@media (max-width:1000px){.cal-wrap{grid-template-columns:1fr}.cal-panel{position:static;max-height:none}}
@media (max-width:700px){.cal-d{min-height:52px;padding:4px;border-radius:8px}.pills{display:none}.dots{display:flex}.cal-dow span{padding:0;text-align:center}.cal-d .n{font-size:.78rem}.cal-key{margin-left:0}.cal-main{padding:8px}}
@media print{.cal-month[hidden]{display:block}.cal-panel,.cal-nav,.cal-legend{display:none}}
/* roadmap */
.roadmap{padding:18px 18px 14px}.rm-note{background:color-mix(in srgb,var(--s1) 9%,transparent);border-left:3px solid var(--s1);border-radius:8px;padding:8px 12px;margin:8px 0 6px;font-size:.92rem}
.rm-rail{position:relative;height:58px;margin:18px 10px 6px}.rm-track{position:absolute;left:0;right:0;top:22px;height:6px;border-radius:3px;background:var(--grid);overflow:hidden}.rm-fill{display:block;height:100%;background:linear-gradient(90deg,var(--s3),var(--s1))}
.rm-m{position:absolute;top:36px;transform:translateX(-50%);font-size:.7rem;color:var(--muted);white-space:nowrap}
.rm-dot{position:absolute;top:16px;width:18px;height:18px;margin-left:-9px;border-radius:50%;background:var(--surface);border:3px solid var(--axis);z-index:2}
.rm-dot.done{background:var(--good);border-color:var(--good)}.rm-dot.next{border-color:var(--s1);background:var(--s1);box-shadow:0 0 0 5px color-mix(in srgb,var(--s1) 25%,transparent)}.rm-dot.late{border-color:var(--crit)}
.rm-today{position:absolute;top:0;bottom:22px;width:0;border-left:2px dashed var(--crit);z-index:1}.rm-today b{position:absolute;top:-6px;left:4px;font-size:.7rem;color:var(--crit);white-space:nowrap}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.rm-list{list-style:none;margin:10px 0 0;padding:0;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(218px,1fr);gap:10px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x proximity}
.rm-card{scroll-snap-align:start;display:flex;flex-direction:column;gap:8px;position:relative}
.rm-mark{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:.85rem;border:2px solid var(--axis);color:var(--ink2);background:var(--surface);position:relative;z-index:1}
.rm-card:not(:last-child)::before{content:"";position:absolute;top:14px;left:30px;right:-10px;height:2px;background:var(--grid)}
.rm-card.done .rm-mark{background:var(--good);border-color:var(--good);color:#fff}.rm-card.next .rm-mark{background:var(--s1);border-color:var(--s1);color:#fff;box-shadow:0 0 0 5px color-mix(in srgb,var(--s1) 22%,transparent)}
.rm-card.done:not(:last-child)::before{background:var(--good)}.rm-card.late .rm-mark{border-color:var(--crit)}
.rm-body{flex:1;background:var(--bg);border:1px solid var(--grid);border-radius:12px;padding:10px 12px;display:flex;flex-direction:column;gap:4px}.rm-card.next .rm-body{border-color:var(--s1);box-shadow:0 4px 18px color-mix(in srgb,var(--s1) 14%,transparent)}
.rm-card.done .rm-body{opacity:.78}.rm-when{display:flex;justify-content:space-between;gap:6px;font-size:.78rem;color:var(--ink2);font-variant-numeric:tabular-nums}.rm-when em{font-style:normal;color:var(--muted)}
.rm-body h3{margin:2px 0 0;font-size:.98rem;line-height:1.3}.rm-phase{margin:0;font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.rm-body p{margin:0;font-size:.84rem;line-height:1.4;color:var(--ink2)}.rm-body p b{color:var(--ink);font-weight:600;margin-right:3px}
.rm-foot{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:auto;padding-top:6px}.rm-badge{font-size:.72rem;font-weight:600;border-radius:999px;padding:1px 9px;border:1px solid var(--axis)}
.rm-badge.done{border-color:var(--good);color:var(--goodtext)}.rm-badge.next{border-color:var(--s1);color:var(--s1)}.rm-card.late .rm-badge{border-color:var(--crit);color:var(--crit)}
.rm-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.rm-chip{font-size:.8rem;text-decoration:none;color:var(--ink);border:1px solid var(--ring);background:var(--bg);border-radius:999px;padding:3px 10px}
.rm-chip b{font-weight:600;color:var(--ink2);margin-right:2px}.rm-chip.done{opacity:.6}.rm-chip.next{border-color:var(--s1);box-shadow:inset 0 0 0 1px var(--s1)}.rm-chip.late{border-color:var(--crit)}.roadmap.compact{padding-bottom:6px}.roadmap.compact .rm-note{display:none}
.rm-go{font-size:.78rem;text-decoration:none;border-bottom:1px dotted currentColor}
@media (max-width:700px){.rm-list{grid-auto-flow:row;grid-auto-columns:auto}.rm-card{flex-direction:row}.rm-card:not(:last-child)::before{top:30px;bottom:-10px;left:14px;right:auto;width:2px;height:auto}.rm-rail{margin:18px 4px 4px}.rm-m:nth-child(even){display:none}}
"""

JS = r"""
(function(){var root=document.getElementById('cal'),src=document.getElementById('cal-data');if(!root||!src)return;var D;try{D=JSON.parse(src.textContent);}catch(e){return;}
var MON='gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split(' '),WD='domenica lunedì martedì mercoledì giovedì venerdì sabato'.split(' ');
var months=[].slice.call(root.querySelectorAll('.cal-month')),pick=root.querySelector('.cal-pick'),panel=root.querySelector('.cal-panel-in'),tip=root.querySelector('.cal-tip'),cur=0;
months.forEach(function(m,i){if(!m.hidden)cur=i;});
function show(i){i=Math.max(0,Math.min(months.length-1,i));months.forEach(function(m,k){m.hidden=k!==i;});cur=i;if(pick)pick.value=String(i);}
function longDate(iso){var p=iso.split('-'),d=new Date(+p[0],+p[1]-1,+p[2]);var w=WD[d.getDay()];return w.charAt(0).toUpperCase()+w.slice(1)+' '+(+p[2])+' '+MON[+p[1]-1]+' '+p[0];}
function el(t,c,txt){var e=document.createElement(t);if(c)e.className=c;if(txt!=null)e.textContent=txt;return e;}
function safe(u){return /^https?:\/\/[^\s"'<>`]+$/i.test(u||'');}
function host(u){try{var x=new URL(u);return (x.hostname.replace(/^www\./,'')+x.pathname).replace(/\/$/,'').slice(0,40);}catch(e){return u.slice(0,40);}}
function itemsOf(iso){return (D.days[iso]||[]).map(function(k){return D.items[String(k)];}).filter(function(it){var f=root.getAttribute('data-f');return f==='all'||it.owner===f||(it.owner==='both'&&(f==='me'||f==='claude'));});}
function select(iso,scroll){var b=document.getElementById('cal-'+iso);root.querySelectorAll('.cal-d.sel').forEach(function(x){x.classList.remove('sel');});
 if(b){b.classList.add('sel');var m=b.closest('.cal-month');if(m)show(months.indexOf(m));}
 var its=itemsOf(iso);panel.innerHTML='';panel.appendChild(el('h3','',longDate(iso)));
 var diff=Math.round((new Date(iso)-new Date(D.today))/864e5);panel.appendChild(el('p','cnt',(its.length?its.length+(its.length===1?' voce':' voci'):'Niente in calendario')+' · '+(diff===0?'oggi':diff>0?'tra '+diff+' giorni':(-diff)+' giorni fa')));
 its.forEach(function(it){var c=el('div','ev o-'+it.owner+' s-'+it.state);var tg=el('div','tags');tg.appendChild(el('span','tag',D.kind[it.kind]||it.kind));
  if(it.owner!=='none')tg.appendChild(el('span','tag own o-'+it.owner,D.owner[it.owner]));
  if(it.state==='overdue')tg.appendChild(el('span','tag late','In ritardo'));if(it.state==='done')tg.appendChild(el('span','tag done','Fatto'));if(it.approx)tg.appendChild(el('span','tag','data stimata'));
  if(it.end)tg.appendChild(el('span','tag','fino al '+it.end.split('-').reverse().slice(0,2).join('/')));
  c.appendChild(tg);c.appendChild(el('div','t',it.title));if(it.html){var d=el('div','d');d.innerHTML=it.html;c.appendChild(d);}
  var lk=el('div','lk');(it.links||[]).forEach(function(u){if(!safe(u))return;var a=el('a','',host(u));a.href=u;a.target='_blank';a.rel='noopener noreferrer';a.title=u;lk.appendChild(a);});
  if(it.step){var a=el('a','','Apri il passo '+it.step+' nel piano');a.href='#step-'+it.step;lk.appendChild(a);}if(lk.childNodes.length)c.appendChild(lk);
  c.appendChild(el('div','src','Fonte: '+it.source));panel.appendChild(c);});
 if(scroll&&window.innerWidth<1000)panel.parentNode.scrollIntoView({behavior:'smooth',block:'start'});
 try{history.replaceState(null,'','#cal-'+iso);}catch(e){}}
root.addEventListener('click',function(e){var b=e.target.closest('[data-d]');if(b&&root.contains(b)){select(b.getAttribute('data-d'),true);}
 var f=e.target.closest('.cal-legend button');if(f){root.setAttribute('data-f',f.getAttribute('data-f'));root.querySelectorAll('.cal-legend button').forEach(function(x){x.setAttribute('aria-pressed',x===f?'true':'false');});}});
root.querySelector('.cal-prev').addEventListener('click',function(){show(cur-1);});root.querySelector('.cal-next').addEventListener('click',function(){show(cur+1);});
root.querySelector('.cal-today').addEventListener('click',function(){select(D.today,false);});if(pick)pick.addEventListener('change',function(){show(+pick.value);});
root.addEventListener('pointerover',function(e){var b=e.target.closest('.cal-d.has');if(!b||e.pointerType==='touch'){tip.hidden=true;return;}var its=itemsOf(b.getAttribute('data-d'));if(!its.length){tip.hidden=true;return;}
 tip.innerHTML='';tip.appendChild(el('b','',longDate(b.getAttribute('data-d'))));its.slice(0,5).forEach(function(it){var r=el('div','o-'+it.owner);r.appendChild(el('i'));r.appendChild(el('span','',(it.state==='overdue'?'⚠ ':'')+it.title));tip.appendChild(r);});
 if(its.length>5)tip.appendChild(el('div','','+'+(its.length-5)+' altre'));tip.hidden=false;var rr=root.getBoundingClientRect(),br=b.getBoundingClientRect();
 var x=br.left-rr.left+br.width/2-140,th=tip.offsetHeight||80;tip.style.left=Math.max(4,Math.min(x,rr.width-284))+'px';tip.style.top=((br.bottom+th+12>innerHeight&&br.top-th-8>0)?(br.top-rr.top-th-6):(br.bottom-rr.top+6))+'px';});
root.addEventListener('pointerleave',function(){tip.hidden=true;});root.addEventListener('focusin',function(e){if(e.target.classList.contains('cal-d'))tip.hidden=true;});
root.addEventListener('keydown',function(e){var b=e.target.closest&&e.target.closest('.cal-d');if(!b)return;var k={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[e.key];if(!k)return;e.preventDefault();
 var p=b.getAttribute('data-d').split('-'),d=new Date(Date.UTC(+p[0],+p[1]-1,+p[2]+k)),iso=d.toISOString().slice(0,10),n=document.getElementById('cal-'+iso);if(n){var m=n.closest('.cal-month');show(months.indexOf(m));n.focus();}});
window.calSelect=select;var h=location.hash.match(/^#cal-(\d{4}-\d{2}-\d{2})$/);if(h)select(h[1],false);})();
"""
