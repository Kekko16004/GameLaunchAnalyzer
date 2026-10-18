#!/usr/bin/env python3
"""Non-Steam promotion calendar: online showcases, third-party Steam fests, itch.io, Reddit threads, streams, newsletters
and the Italian scene, with submission windows, requirements and who each one fits. Physical events (PAX, Gamescom...)
are kept in a separate optional list.

Source: the hand-curated file scripts/research/data/promo_events_fallback.json (every item with its URL and the day it was
read). `fetch` re-reads the public pages that print a submission deadline and keeps a date only when it is written next to
words like "deadline" or "submissions close" (marked "lettura automatica", to be confirmed); when a page cannot be read the
curated data stays. Dates that nobody has published stay null with status "DA VERIFICARE" and a 'pattern' (the usual
months): the tool never invents an exact day. Estimated reminders are always labelled as such.

  promo_events.py fetch    [-o ~/.game-launch-strategist/promo_events.json] [--offline] [--rate 2] [--today D]
  promo_events.py list     [--online-only] [--kind showcase|steam_fest_3rd|itch|reddit_recurring|stream|newsletter|italian]
  promo_events.py match    --launch-dir launch [--page 2026-10-31] [--itch 2026-11-10] [--demo 2026-12-20]
                           [--launch 2027-05-13] [--ea yes|no] [--tags-from launch/store_kit.json] [--tags "Cozy,Party"]
                           [--to 2027-12-31] [--all] [--include-physical] [--eligible key1,key2] [--country IT] [--today D]
  promo_events.py export-window --csv launch/window.csv [--include-estimated]
  promo_events.py deadlines --launch-dir launch [same options as match] [--max 12] [--md launch/promo-events.md]
                           [--replace-todo "festival di terzi"] [--dry-run]

Stages: before --page nothing public; from --page "coming_soon"; from --demo "demo"; from --launch "ea" (or "released"
with --ea no). An event fits when the stage at its date is one it accepts, its requirements are met in time (Steam page
by the deadline, public demo by the event, itch page, unreleased...), the genre fits (its theme words against the store
tags; "any" for general showcases) and nothing in our tags is excluded (horror-only shows and similar).
Priority [OPINIONE]: value 1-3 (reach for a small indie) x fit (2 theme match, 1 general): alta / media / bassa.

`deadlines` writes 👤 steps "candidati a X entro Y" into calendar.md (phase "### 📣 Eventi online e showcase") and TODO.md
(section "📣 Eventi online e showcase (promo_events.py)"), at most --max dated applications in the next 12 months (8-12 a
year is the target) plus the recurring habits (Reddit threads, newsletters), each with a stable id so re-running never
duplicates; it writes launch/_raw/promo_events_deadlines.json (top_moves.py proposes the nearest high-value application) and
a Markdown table by month (--md). `--replace-todo PATTERN` marks a generic TODO line ("10 festival di terzi...") as
superseded by the dated applications.

`export-window` adds the dated online events (kind "festival", weight 2 for the big June/August/December showcase weeks, 1
otherwise [OPINIONE]) to launch_window.py's window.csv, replacing only its own rows (source "promo_events.py"), never your
rows, and never a row that steam_events.py already wrote for the same event.
"""
from __future__ import annotations

import argparse
import calendar as _cal
import csv
import datetime as dt
import html
import os
import re

import common

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK = os.path.join(HERE, "data", "promo_events_fallback.json")
KINDS = ("showcase", "steam_fest_3rd", "itch", "reddit_recurring", "stream", "newsletter", "italian")
KIND_IT = {"showcase": "showcase digitale", "steam_fest_3rd": "fest di terzi su Steam", "itch": "itch.io", "reddit_recurring": "Reddit (thread fisso)",
           "stream": "diretta / stream", "newsletter": "newsletter / curatore", "italian": "scena italiana"}
ROLLING = ("weekly", "monthly", "rolling")
SRC_TAG = "promo_events.py"
ID_RE = re.compile(r"\[id promo:([a-z0-9_:\-]+)\]")
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                       "october", "november", "december"], 1)}
D = dt.date.fromisoformat
PRIO_N = {"alta": 3, "media": 2, "bassa": 1}


def default_out() -> str:
    return common.user_dir("promo_events.json")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def _eom(y: int, m: int) -> dt.date:
    return dt.date(y, m, _cal.monthrange(y, m)[1])


# ---------------------------------------------------------------- data
def load_fallback(path: str = FALLBACK) -> dict:
    return common.load_json(path)


def load(path: str | None = None) -> dict:
    """The user file if it exists, else the fallback (always something to work with)."""
    p = path or default_out()
    if os.path.exists(p):
        return common.load_json(p)
    return dict(load_fallback(), parser="fallback")


def validate(data: dict) -> list[str]:
    """Format problems of the curated file: unknown kind, a date without a source, a missing pattern for undated items."""
    bad = []
    for e in data.get("events", []):
        k = e.get("key", "?")
        if e.get("kind") not in KINDS:
            bad.append(f"{k}: kind {e.get('kind')!r}")
        if not e.get("url"):
            bad.append(f"{k}: url mancante")
        for ed in e.get("editions") or []:
            dated = any(ed.get(f) for f in ("start", "submission_deadline", "submission_open"))
            if dated and (ed.get("status") not in ("FATTO", "LETTURA_AUTO") or not ed.get("source") or not ed.get("read_on")):
                bad.append(f"{k}: data senza fonte o senza 'read_on'")
            if not dated and ed.get("status") == "FATTO":
                bad.append(f"{k}: FATTO senza date")
        if e.get("recurrence") not in ROLLING and not (e.get("editions") or (e.get("pattern") or {}).get("event_months")):
            bad.append(f"{k}: né edizioni datate né mesi abituali")
        if e.get("recurrence") not in ROLLING and not (e.get("pattern") or {}).get("text"):
            bad.append(f"{k}: pattern.text mancante")
    return bad


# ---------------------------------------------------------------- fetch (optional)
DATE_RE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b"
                     r"|\b(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", re.I)
KEY_RE = re.compile(r"deadline|submissions? (?:close|closes|closing|are open until|due)|submit (?:by|before)|applications? (?:close|closes|due)|apply (?:by|before)|until", re.I)


def page_text(page: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _to_date(m: re.Match) -> dt.date | None:
    if m.group(1):
        mon, day, year = m.group(1), m.group(2), m.group(3)
    else:
        day, mon, year = m.group(4), m.group(5), m.group(6)
    mo = MONTHS.get(mon.lower()) or next((v for k, v in MONTHS.items() if k.startswith(mon.lower()[:3])), None)
    try:
        return dt.date(int(year), mo, int(day)) if mo else None
    except ValueError:
        return None


def find_deadline(page: str, today: dt.date) -> dt.date | None:
    """A future date written within ~120 characters after a deadline word; None if none or if two different ones compete."""
    txt = page_text(page)
    found = []
    for k in KEY_RE.finditer(txt):
        for m in DATE_RE.finditer(txt[k.start(): k.end() + 120]):
            d = _to_date(m)
            if d and d >= today:
                found.append(d)
                break
    found = sorted(set(found))
    return found[0] if len(found) == 1 else None


def fetch(offline: bool = False, rate: float = 2.0, fallback_path: str = FALLBACK, today: dt.date | None = None) -> dict:
    fb = load_fallback(fallback_path)
    today = today or dt.date.today()
    if offline:
        return dict(fb, parser="fallback", note="offline: dati curati a mano")
    th = common.Throttle(rate)
    events, read, failed, found = [], 0, 0, []
    for e in fb.get("events", []):
        e = dict(e)
        url = e.get("deadline_page")
        if url:
            try:
                page = common.http_get(url, throttle=th, retries=1).decode("utf-8", "replace")
                read += 1
                d = find_deadline(page, today)
                if d:
                    eds = [dict(x) for x in e.get("editions") or []]
                    hit = next((x for x in eds if x.get("submission_deadline") == d.isoformat()), None)
                    if not hit:
                        eds.append(dict(label=f"{d.year} (letto)", start=None, end=None, submission_open=None, submission_deadline=d.isoformat(),
                                        status="LETTURA_AUTO", source=url, read_on=today.isoformat()))
                        found.append(f"{e['name']}: scadenza {d} letta su {url}")
                    e["editions"] = eds
            except Exception as ex:  # noqa: BLE001
                failed += 1
                common.log(f"WARN {url} not read ({ex}): curated data kept")
        events.append(e)
    parser = "live" if read else "fallback"
    return dict(fb, events=events, parser=parser, fetched_on=today.isoformat(), pages_read=read, pages_failed=failed, found=found,
                note=f"{read} pagine lette, {failed} non lette il {today}; le date curate restano")


def diff(old: dict | None, new: dict) -> list[str]:
    if not old:
        return []
    o = {e["key"]: e for e in old.get("events", [])}
    out = []
    for e in new.get("events", []):
        p = o.get(e["key"])
        if not p:
            out.append(f"nuovo: {e['name']}")
        elif [(x.get("start"), x.get("submission_deadline")) for x in p.get("editions") or []] != [(x.get("start"), x.get("submission_deadline")) for x in e.get("editions") or []]:
            out.append(f"cambiato: {e['name']} (edizioni/scadenze)")
    return out


# ---------------------------------------------------------------- occurrences
def occurrences(e: dict, today: dt.date, to: dt.date) -> list[dict]:
    """Dated editions as published, plus estimated ones from the usual months for the years without a dated edition.
    Rolling items (weekly threads, newsletters) give one undated occurrence."""
    if e.get("recurrence") in ROLLING:
        return [dict(key=f"{e['key']}", event=e, start=None, end=None, deadline=None, opens=None, estimated=False, rolling=True, label=e["name"])]
    out, seen = [], set()
    for ed in e.get("editions") or []:
        start = D(ed["start"]) if ed.get("start") else None
        dl = D(ed["submission_deadline"]) if ed.get("submission_deadline") else None
        op = D(ed["submission_open"]) if ed.get("submission_open") else None
        ref = start or dl or op
        if not ref:
            continue
        if (start or dl or op) < today - dt.timedelta(days=1) and (not start or start < today):
            continue
        if ref > to:
            continue
        month = None
        if start:
            seen.add((start.year, start.month))
        else:                                 # only a deadline: it stands for the next usual month after it
            cands = sorted(dt.date(y, mo, 1) for y in (ref.year, ref.year + 1) for mo in (e.get("pattern") or {}).get("event_months") or [] if dt.date(y, mo, 1) > ref)
            if cands:
                month = (cands[0].year, cands[0].month)
                seen.add(month)
            else:
                seen.add((ref.year, ref.month))
        out.append(dict(key=f"{e['key']}:{ed.get('label') or ref.year}".replace(" ", "_").lower(), event=e, start=start, end=D(ed["end"]) if ed.get("end") else start, month=month,
                        deadline=dl, opens=op, estimated=False, rolling=False, label=f"{e['name']} {ed.get('label') or ref.year}",
                        status=ed.get("status"), source=ed.get("source"), read_on=ed.get("read_on")))
    pat = e.get("pattern") or {}
    for y in range(today.year, to.year + 2):
        for mo in pat.get("event_months") or []:
            if (y, mo) in seen or any(o["start"] and o["start"].year == y and abs(o["start"].month - mo) <= 1 for o in out):
                continue
            ev_first, ev_last = dt.date(y, mo, 1), _eom(y, mo)
            cm, om = pat.get("close_month"), pat.get("open_month")
            if isinstance(cm, dict):
                cm = cm.get(str(mo))
            if isinstance(om, dict):
                om = om.get(str(mo))
            dl = op = None
            if cm:
                cy = y if cm <= mo else y - 1
                dl = _eom(cy, cm)
            if om:
                oy = y if om <= (cm or mo) else y - 1
                if cm and om > cm:
                    oy = (dl.year if dl else y) - 1
                op = dt.date(oy, om, 1)
            if ev_last < today or ev_first > to:
                continue
            if dl and dl < today:
                continue                      # this year's window has passed
            label = f"{e['name']} {MESI[mo]} {y}" if len(pat.get("event_months") or []) > 1 else f"{e['name']} {y}"
            out.append(dict(key=f"{e['key']}:{y}-{mo:02d}", event=e, start=None, end=None, month=(y, mo), deadline=dl, opens=op, estimated=True,
                            rolling=False, label=label, status="DA VERIFICARE"))
    return sorted(out, key=lambda o: (o.get("deadline") or o.get("start") or dt.date(*o["month"], 1)))


# ---------------------------------------------------------------- matching one game
def our_tags(tags_from: str | None, extra: str | None) -> list[str]:
    tags = []
    if tags_from and os.path.exists(tags_from):
        kit = common.load_json(tags_from)
        for t in ((kit.get("steam") or {}).get("tags") or []):
            tags.append(t["tag"] if isinstance(t, dict) else str(t))
    tags += [t.strip() for t in (extra or "").split(",") if t.strip()]
    return list(dict.fromkeys(tags))


class Timeline:
    def __init__(self, page=None, itch=None, demo=None, launch=None, ea=True, eligible=None, country=None):
        self.page, self.itch, self.demo, self.launch, self.ea = page, itch, demo, launch, ea
        self.country = (country or "").upper() or None
        self.eligible = set(eligible or [])      # keys of team-restricted events we qualify for (--eligible)

    def stage(self, d: dt.date | None) -> str:
        if d is None:
            return "rolling"
        if self.launch and d >= self.launch:
            return "ea" if self.ea else "released"
        if self.demo and d >= self.demo:
            return "demo"
        if self.page and d >= self.page:
            return "coming_soon"
        return "none"

    def as_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, dt.date) else sorted(v) if isinstance(v, set) else v) for k, v in vars(self).items()}


def genre_fit(e: dict, tags: list[str]) -> tuple[int, list[str], list[str]]:
    """(2 theme match, 1 general showcase, 0 no fit), the theme words hit, the excluded words hit."""
    low = [t.lower() for t in tags]
    def hit(kw):
        return any(kw == t or kw in t or (len(t) > 3 and t in kw) for t in low)
    ex = sorted({kw for kw in e.get("exclude") or [] if hit(kw)})
    if ex:
        return 0, [], ex
    if e.get("requires_fit"):
        need = [kw for kw in e["requires_fit"] if hit(kw)]
        if not need:
            return 0, [], []
    words = sorted({kw for kw in e.get("match") or [] if hit(kw)})
    if words:
        return 2, words, []
    return (1 if e.get("fit") == "any" else 0), [], []


def check(o: dict, tl: Timeline, tags: list[str], today: dt.date) -> dict:
    e = o["event"]
    when = o.get("start") or (dt.date(*o["month"], 15) if o.get("month") else None)
    dl = o.get("deadline") or (when - dt.timedelta(days=e.get("lead_days") or 42) if when else None)
    reasons = []
    if e.get("team_country") and e["team_country"].upper() != (tl.country or ""):
        reasons.append(f"solo team con sede in {e['team_country']} (--country)")
    if e.get("team_only") and e["key"] not in tl.eligible:
        reasons.append(f"riservato a {e['team_only']} (--eligible {e['key']} se il team rientra)")
    fit, words, ex = genre_fit(e, tags)
    if ex:
        reasons.append("genere escluso: " + ", ".join(ex))
    elif not fit:
        reasons.append("tema non compatibile con i nostri tag")
    if o["rolling"]:
        ready = {"steam_page": tl.page, "itch_page": tl.itch, "demo": tl.demo, "released": tl.launch}
        need = [ready.get(r) for r in e.get("requires") or [] if r in ready]
        start = max([d for d in need if d] + [today]) if need and all(need) else (today if not need else None)
        if need and not all(need):
            reasons.append("serve " + ", ".join(r for r in e.get("requires") if r in ready and not ready[r]))
        st = tl.stage(start) if start else "none"
        if start and e.get("stages") and st not in e["stages"] and "rolling" not in e["stages"]:
            reasons.append(f"accetta solo {', '.join(e['stages'])}")
        return dict(ok=not reasons, reasons=reasons, fit=fit, words=words, when=None, deadline=None, trigger=start, stage=st)
    st = tl.stage(when)
    if e.get("stages") and st not in e["stages"]:
        reasons.append(f"alla data dell'evento saremo '{st}', accetta {', '.join(e['stages'])}")
    req = e.get("requires") or []
    if "steam_page" in req and (not tl.page or (dl and tl.page > dl)):
        reasons.append("serve la pagina Steam pubblica entro la scadenza")
    if "itch_page" in req and (not tl.itch or (dl and tl.itch > dl)):
        reasons.append("serve la pagina itch entro la scadenza")
    if "demo" in req and (not tl.demo or (when and tl.demo > when)):
        reasons.append("serve una demo pubblica alla data dell'evento")
    if "build" in req and dl and not ((tl.itch and tl.itch <= dl) or (tl.demo and tl.demo <= dl)):
        reasons.append("serve una build giocabile da mandare entro la scadenza")
    if "unreleased" in req and tl.launch and when and when >= tl.launch:
        reasons.append("solo giochi non ancora usciti")
    if "released" in req and (not tl.launch or (when and when < tl.launch)):
        reasons.append("solo giochi già usciti (spesso con sconto)")
    if dl and dl < today:
        reasons.append("scadenza passata")
    return dict(ok=not reasons, reasons=reasons, fit=fit, words=words, when=when, deadline=dl, stage=st, dl_estimated=not o.get("deadline"), dl_lead=not o.get("deadline"))


REACH_N = {"alta": 3, "media": 2, "piccola": 1}
ODDS_N = {"bassa": 1, "media": 2, "alta": 3}


def score(e: dict, fit: int) -> int:
    """Priority: alta >= 6, media >= 4. Value score [OPINIONE] = reach (alta 3, media 2, piccola ma affidabile 1) x acceptance odds for a small unknown
    team (bassa 1, media 2, alta 3) x genre fit (2 theme match, 1 general). 1..18."""
    return REACH_N.get(e.get("reach_tier") or "piccola", 1) * ODDS_N.get(e.get("odds") or "bassa", 1) * max(fit, 0)


def tier(e: dict) -> str:
    """'fattibile' = a real chance to be shown; 'tentativo' = famous long shot (worth a try, never the plan)."""
    return "tentativo" if (e.get("odds") or "bassa") == "bassa" else "fattibile"


def priority(e: dict, fit: int) -> str:
    sc = score(e, fit)
    return "alta" if sc >= 6 else "media" if sc >= 4 else "bassa"


def plan(data: dict, today: dt.date, tl: Timeline, tags: list[str], to: dt.date | None = None, include_physical: bool = False,
         keep_all: bool = False) -> dict:
    to = to or ((tl.launch + dt.timedelta(days=120)) if tl.launch else today + dt.timedelta(days=365))
    rows, rejected = [], []
    for e in data.get("events", []):
        if not e.get("online", True) and not include_physical:
            continue
        for o in occurrences(e, today, to):
            c = check(o, tl, tags, today)
            row = dict(key=o["key"], event_key=e["key"], name=o["label"], kind=e["kind"], online=e.get("online", True), url=e.get("submit_url") or e.get("url"),
                       cost=e.get("cost"), cost_note=e.get("cost_note"), requires=e.get("requires") or [], reach=e.get("reach_note"), why=e.get("why_us") or e.get("matters_for"),
                       fit=c["fit"], match=c["words"], priority=priority(e, c["fit"]) if c["ok"] else None, score=score(e, c["fit"]),
                       reach_tier=e.get("reach_tier"), odds=e.get("odds"), odds_why=e.get("odds_why"), tier=tier(e), next_step=e.get("next_step"), lineup=e.get("lineup"), plan=e.get("plan", True), stage=c["stage"], dl_lead=bool(c.get("dl_lead")) and not o["rolling"], estimated=o["estimated"] or bool(c.get("dl_estimated") and not o["rolling"]), rolling=o["rolling"],
                       start=o["start"].isoformat() if o.get("start") else None, month=f"{o['month'][0]}-{o['month'][1]:02d}" if o.get("month") else None,
                       deadline=c["deadline"].isoformat() if c.get("deadline") else None, opens=o["opens"].isoformat() if o.get("opens") else None,
                       trigger=c["trigger"].isoformat() if c.get("trigger") else None, pattern=(e.get("pattern") or {}).get("text"),
                       weekday=e.get("weekday"), status=o.get("status") or e.get("status"), source=o.get("source") or e.get("source") or e.get("url"),
                       read_on=o.get("read_on") or e.get("read_on") or data.get("read_on"), reasons=c["reasons"])
            (rows if c["ok"] else rejected).append(row)
    if keep_all:
        rows += rejected
    def sort_key(r):
        return (r.get("deadline") or r.get("trigger") or r.get("start") or "9999", -PRIO_N.get(r.get("priority") or "bassa", 0))
    rows.sort(key=sort_key)
    return dict(computed_on=today.isoformat(), timeline=tl.as_dict(), tags=tags, to=to.isoformat(), events_read_on=data.get("read_on"),
                parser=data.get("parser"), matches=rows, rejected=rejected, physical=[e for e in data.get("events", []) if not e.get("online", True)],
                physical_note=data.get("physical_note"))


# ---------------------------------------------------------------- steps for calendar.md / TODO.md
def _mese(d: str | None) -> str:
    if not d:
        return "?"
    x = D(d)
    return f"{MESI[x.month]} {x.year}"


def steps(res: dict, today: dt.date, max_apps: int = 12, max_habits: int = 4, max_longshots: int = 2) -> list[dict]:
    """The applications to put in the plan: by value score, at most max_apps in the next 12 months, of which at most
    max_longshots famous long shots (odds 'bassa', one edition per show, reserved); then back in date order. Plus the recurring habits."""
    apps = [r for r in res["matches"] if not r["rolling"] and r.get("plan", True)
            and (r["priority"] in ("alta", "media") if r["tier"] == "fattibile" else r["score"] >= 3)]
    horizon = (today + dt.timedelta(days=365)).isoformat()
    apps = [r for r in apps if (r.get("deadline") or r.get("start") or "9999") <= horizon]
    # long shots get a small reserved share (free 10-minute forms are worth it), never the bulk of the plan
    ranked = sorted(apps, key=lambda r: (-r["score"], r.get("deadline") or "9999"))
    longs = [r for r in ranked if r["tier"] == "tentativo"]
    seen_ev, long_pick = set(), []
    for r in longs:                      # at most one edition per famous show
        if r["event_key"] not in seen_ev and len(long_pick) < max_longshots:
            long_pick.append(r); seen_ev.add(r["event_key"])
    feas = [r for r in ranked if r["tier"] == "fattibile"][:max(0, max_apps - len(long_pick))]
    best = feas + long_pick[:max(0, max_apps - len(feas))]
    best = sorted(best, key=lambda r: r.get("deadline") or r.get("start") or "9999")
    out = []
    for r in best:
        req = _req_it(r["requires"])
        lab = "possibilità reale" if r["tier"] == "fattibile" else "tentativo: famoso e difficile"
        head = f"{KIND_IT[r['kind']]}, {lab}, valore {r['score']}/18"
        nxt = f" · prossimo passo: {r['next_step']}" if r.get("next_step") else ""
        if r.get("dl_lead"):
            due = max(today, D(r["deadline"]) - dt.timedelta(days=7)).isoformat()
            text = f"**Candidati a {r['name']}** ({head}): scadenza non pubblicata, di solito qualche settimana prima, verso il {r['deadline']} [STIMA]"
            note = f"date non pubblicate: {r.get('pattern') or ''} · serve: {req}{nxt} · {r['url']}"
        elif r["estimated"]:
            opens = r.get("opens")
            due = max(today, D(opens)).isoformat() if opens else max(today, D(r["deadline"]) - dt.timedelta(days=21)).isoformat()
            text = (f"**Candidati a {r['name']}** ({head}): candidature di solito "
                    f"{('da ' + MESI[D(opens).month] + ' ') if opens else ''}fino a fine {MESI[D(r['deadline']).month]} [DA VERIFICARE]")
            note = f"date non pubblicate: {r.get('pattern') or ''} · promemoria fine finestra {r['deadline']} [STIMA] · serve: {req}{nxt} · {r['url']}"
        else:
            dl = r.get("deadline")
            due = max(today, D(dl) - dt.timedelta(days=5)).isoformat() if dl else today.isoformat()
            text = f"**Candidati a {r['name']}** entro il {dl or '?'} ({head})"
            note = f"scadenza {dl} [FATTO {r.get('source')}, letto {r.get('read_on')}]" + (" (lettura automatica: controlla)" if r.get("status") == "LETTURA_AUTO" else "") + f" · serve: {req}{nxt} · {r['url']}"
        if r.get("cost") and r["cost"] != "free":
            note += f" · costo: {r.get('cost_note') or r['cost']}"
        out.append(dict(key=r["key"], event=r["name"], who="👤", kind="candidatura", deadline=r.get("deadline"), due=due, estimated=r["estimated"],
                        priority=r["priority"], score=r["score"], tier=r["tier"], text=text, note=note + f" [id promo:{r['key']}]"))
    out.sort(key=lambda st: (st["due"], st.get("deadline") or ""))     # the phase reads in reminder order
    habits = [r for r in res["matches"] if r["rolling"] and r.get("plan", True) and r["priority"] in ("alta", "media")]
    for r in sorted(habits, key=lambda r: (-r["score"], r.get("trigger") or ""))[:max_habits]:
        day = f" ogni {r['weekday']}" if r.get("weekday") else ""
        out.append(dict(key=r["key"], event=r["name"], who="👤", kind="abitudine", deadline=None, due=r.get("trigger") or today.isoformat(), estimated=False,
                        priority=r["priority"], score=r["score"], tier=r["tier"], text=f"**{r['name']}**{day}: {r.get('why') or ''}".rstrip(": "),
                        note=f"{r.get('pattern') or ''} · serve: {_req_it(r['requires'])} · {r['url']} [id promo:{r['key']}]"))
    return out


def _req_it(req: list[str]) -> str:
    it = dict(steam_page="pagina Steam", itch_page="pagina itch", demo="demo pubblica", build="build per la giuria", trailer="trailer",
              unreleased="gioco non uscito", released="gioco uscito", discount="sconto", gameplay_video="video di gameplay", italian_team="team italiano")
    return ", ".join(it.get(r, r) for r in req) or "niente di particolare"


def _ids(raw: str) -> set[str]:
    return set(ID_RE.findall(raw))


GENERIC = {"the", "and", "fest", "festival", "show", "showcase", "games", "game", "steam", "next", "edition", "dal", "del", "della", "di"} | set(MESI[1:])


def _name_words(event: str) -> list[str]:
    base = re.sub(r"\(.*?\)", " ", event.lower())          # "Indie Fan Fest (Next Fest di febbraio) 2027" -> "indie fan fest 2027"
    return [w for w in re.findall(r"[a-zà-ù]{3,}", base) if w not in GENERIC][:2] or [event.lower()]


def _hand_written(raw_low: str, st: dict) -> bool:
    """A step or TODO line written by hand that already names the event and one of its dates."""
    dates = [d for d in (st.get("deadline"), st.get("due")) if d]
    ws = _name_words(st["event"])
    return any(any(d in ln for d in dates) and all(w in ln for w in ws) and re.match(r"^\s*(\d+\.|-)\s*\[", ln) for ln in raw_low.split(chr(10)))


def write_calendar(path: str, sts: list[dict], today: dt.date) -> int:
    import plan_steps as ps
    if not os.path.exists(path) or not sts:
        return 0
    raw = open(path, encoding="utf-8").read().replace("\r", "")
    lines = raw.split("\n")
    plan_ = ps.parse(raw)
    if not plan_["phases"]:
        return 0
    have = _ids(raw)
    nmax = max((s["n"] for s in ps.all_steps(plan_)), default=0)
    add = []
    for st in sts:
        if st["key"] in have or _hand_written(raw.lower(), st):
            continue
        nmax += 1
        add.append(f"{nmax}. [ ] {st['who']} {st['text']}. · 📅 {st['due']}")
        add.append(f"   - {st['note']}")
    if not add:
        return 0
    head_txt = f"### 📣 Eventi online e showcase (da promo_events.py, aggiornato il {today.isoformat()})"
    head = next((k for k, ln in enumerate(lines) if ln.startswith("### 📣 Eventi online")), None)
    if head is None:
        sec = next(k for k, ln in enumerate(lines) if ps.SECTION.match(ln))
        end = next((k for k in range(sec + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
        while end > sec + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = [head_txt] + add
    else:
        lines[head] = head_txt
        end = next((k for k in range(head + 1, len(lines)) if lines[k].startswith("#")), len(lines))
        while end > head + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = add
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    return sum(1 for a in add if re.match(r"^\d+\.", a))


def write_todo(path: str, sts: list[dict], today: dt.date) -> int:
    import todo_track as tt
    if not os.path.exists(path):
        return 0
    n = 0
    for st in sts:
        raw = open(path, encoding="utf-8").read()
        if st["key"] in _ids(raw) or _hand_written(raw.lower(), st):
            continue
        hours = "0,5-1 h" if st["kind"] == "candidatura" else "15 min a settimana"
        dep = re.search(r"serve: ([^·\[]+)", st["note"])
        tt.add(path, "📣 Eventi online e showcase (promo_events.py)",
               f"{st['who']} {st['text']} — {st['due']} — {hours} — {(dep.group(1).strip() if dep else 'pagina pubblica')} — {'candidatura inviata' if st['kind'] == 'candidatura' else 'post fatti'} · {st['note']}", today)
        n += 1
    return n


def replace_generic(path: str, pattern: str, n_steps: int, today: dt.date) -> bool:
    import todo_track as tt
    t = tt.parse(path)
    if not t:
        return False
    hit = [x for x in t["items"] if not x["done"] and not x["dropped"] and pattern.lower() in t["lines"][x["line"]].lower()]
    if len(hit) != 1:
        return False
    tt.drop(path, f"#{hit[0]['n']}",
            f"sostituita da {n_steps} candidature datate nella sezione 📣 Eventi online e showcase (promo_events.py)", today)
    return True


# ---------------------------------------------------------------- Markdown
def _cost(r: dict) -> str:
    return r.get("cost_note") or {"free": "gratis", "paid": "a pagamento"}.get(r.get("cost") or "", "?")


def _dl_txt(r: dict) -> str:
    if not r.get("deadline"):
        return "[DA VERIFICARE]"
    if r.get("dl_lead"):
        return f"~{r['deadline']} (stima: qualche settimana prima) [DA VERIFICARE]"
    return f"fine {_mese(r['deadline'])} [DA VERIFICARE]" if r["estimated"] else f"**{r['deadline']}** [FATTO]"


def _next_txt(r: dict, due: dict) -> str:
    d = due.get(r["key"])
    txt = r.get("next_step") or ("candidati" if r.get("plan", True) else "non pianificato")
    return (txt + (f" — 📅 {d}" if d else "")).replace("|", "/")


def md(res: dict, data: dict, sts: list[dict]) -> str:
    chosen = {s["key"] for s in sts}
    due = {s["key"]: s["due"] for s in sts}
    tl = res["timeline"]
    L = ["# Eventi online per promuovere il gioco", "",
         f"Calcolato il {res['computed_on']} da `promo_events.py` (dati curati letti il {data.get('read_on')}; {data.get('note') or 'nessuna rilettura automatica'}). "
         f"Tappe: pagina Steam {tl.get('page') or '-'}, beta itch {tl.get('itch') or '-'}, demo {tl.get('demo') or '-'}, uscita {tl.get('launch') or '-'}. Tag: {', '.join(res['tags']) or '-'}.", "",
         "**Come leggerlo.** **Valore** = pubblico (alto 3, medio 2, piccolo ma affidabile 1) × probabilità che un gioco piccolo come il nostro venga preso "
         "(bassa 1, media 2, alta 3) × tema (2 in tema, 1 generico): da 1 a 18 [OPINIONE, i criteri sono scritti accanto]. "
         "✅ = è nel calendario e nella TODO. Le date senza fonte sono **[DA VERIFICARE]**: indicano i mesi abituali, mai un giorno inventato. "
         "Obiettivo: **8-12 candidature l'anno**, prima quelle fattibili e in tema.", ""]
    apps = [r for r in res["matches"] if not r["rolling"]]
    first = {}
    for r in sorted(apps, key=lambda r: r.get("deadline") or r.get("start") or "9999"):
        first.setdefault(r["event_key"], r)          # one row per event in the ranking: the next edition
    head = ["| Valore | Evento | Tipo | Pubblico | Probabilità per noi (perché) | Scadenza | Cosa serve | Costo | Prossimo passo | |", "|---|---|---|---|---|---|---|---|---|---|"]
    for title, tier_ in (("## 1. Fattibili: possibilità reale di essere mostrati", "fattibile"), ("## 2. Vale un tentativo: famosi e difficili (mai il piano principale)", "tentativo")):
        rows = sorted([r for r in first.values() if r["tier"] == tier_], key=lambda r: (-r["score"], r.get("deadline") or "9999"))
        L += [title, ""]
        if not rows:
            L += ["- nessuno nel periodo", ""]
            continue
        L += head
        for r in rows:
            L.append(f"| **{r['score']}** | [{r['name']}]({r['url']}) | {KIND_IT[r['kind']]} | {r.get('reach_tier') or '?'}{(': ' + r['reach']) if r.get('reach') else ''} | "
                     f"{r.get('odds') or '?'}{(': ' + r['odds_why']) if r.get('odds_why') else ''} | {_dl_txt(r)} | {_req_it(r['requires'])} | {_cost(r)} | "
                     f"{_next_txt(r, due)} | {'✅' if r['key'] in chosen else ''} |")
        L.append("")
    L += ["## 3. Mese per mese (scadenze)", "", "| Mese | Evento | Va in onda | Scadenza | Valore | |", "|---|---|---|---|---|---|"]
    for r in sorted(apps, key=lambda r: r.get("deadline") or r.get("start") or "9999"):
        k = (r.get("deadline") or r.get("start") or "")[:7]
        onair = r.get("start") or (f"{MESI[int(r['month'][5:])]} {r['month'][:4]} [DA VERIFICARE]" if r.get("month") else "?")
        L.append(f"| {_mese(k + '-01') if k else '?'} | {r['name']} | {onair} | {_dl_txt(r)} | {r['score']} ({r['tier']}) | {'✅' if r['key'] in chosen else ''} |")
    hab = [r for r in res["matches"] if r["rolling"]]
    if hab:
        L += ["", "## 4. Abitudini (sempre aperte, nessuna scadenza)", "", "| Dove | Tipo | Quando | Cosa serve | Valore | Perché | |", "|---|---|---|---|---|---|---|"]
        for r in sorted(hab, key=lambda r: -r["score"]):
            L.append(f"| [{r['name']}]({r['url']}) | {KIND_IT[r['kind']]} | {('ogni ' + r['weekday']) if r.get('weekday') else (r.get('pattern') or '')} | {_req_it(r['requires'])} | "
                     f"{r['score']} | {(r.get('why') or '').replace('|', '/')} | {'✅' if r['key'] in chosen else ''} |")
    rej = [r for r in res["rejected"]]
    if rej:
        L += ["", "## 5. Scartati per ora (e perché)", ""]
        seen = set()
        for r in rej:
            if r["event_key"] in seen:
                continue
            seen.add(r["event_key"])
            L.append(f"- {r['name']}: {'; '.join(r['reasons'])}")
    phys = res.get("physical") or []
    if phys:
        L += ["", "## 6. Eventi fisici (facoltativi)", ""]
        if res.get("physical_note"):
            L += [res["physical_note"], ""]
        L += ["| Evento | Dove | Quando | Costo indicativo | Note |", "|---|---|---|---|---|"]
        for e in phys:
            L.append(f"| [{e['name']}]({e.get('url')}) | {e.get('where') or ''} | {(e.get('pattern') or {}).get('text') or ''} | {e.get('cost_note') or e.get('cost') or '?'} | {e.get('matters_for') or ''} |")
    L += ["", "Rilancia `promo_events.py deadlines` ogni settimana (lo fa il job del lunedì): i promemoria si aggiungono una volta sola."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- window.csv
def window_rows(data: dict, include_estimated: bool = False, steam_names: set[str] | None = None) -> list[dict]:
    steam_names = steam_names or set()
    rows = []
    for e in data.get("events", []):
        if not e.get("online", True) or e.get("recurrence") in ROLLING or not e.get("window_weight", 1):
            continue
        if _slug(e["name"]) in steam_names:
            continue
        w = e.get("window_weight", 1)
        for ed in e.get("editions") or []:
            if not ed.get("start"):
                continue
            s, en = D(ed["start"]), D(ed.get("end") or ed["start"])
            day, i = s, 0
            while day <= en:
                i += 1
                rows.append(dict(date=day.isoformat(), name=f"{e['name']} {ed.get('label') or s.year}" + ("" if i == 1 else f" (settimana {i})"), kind="festival", weight=w,
                                 source=f"{SRC_TAG}, {ed.get('source') or e.get('url')}, letto {ed.get('read_on') or data.get('read_on')}",
                                 note=f"{KIND_IT[e['kind']]} {ed['start']}..{ed.get('end') or ed['start']} [OPINIONE sul peso]"))
                day += dt.timedelta(days=7)
        if include_estimated:
            years = {D(ed["start"]).year for ed in e.get("editions") or [] if ed.get("start")}
            for mo in (e.get("pattern") or {}).get("event_months") or []:
                for y in (dt.date.today().year, dt.date.today().year + 1):
                    if y in years:
                        continue
                    rows.append(dict(date=dt.date(y, mo, 15).isoformat(), name=f"{e['name']} {MESI[mo]} {y} (stima)", kind="festival", weight=max(0.5, w / 2),
                                     source=f"{SRC_TAG}, {e.get('url')}, mese abituale", note=f"mese abituale, giorno NON noto [DA VERIFICARE]: {(e.get('pattern') or {}).get('text') or ''}"))
    return rows


def export_window(data: dict, csv_path: str, include_estimated: bool = False, steam_events_path: str | None = None) -> dict:
    import launch_window as lw
    keep = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            keep = [r for r in csv.DictReader(f) if not (r.get("source") or "").startswith(SRC_TAG)]
    steam_names = set()
    try:
        import steam_events
        steam_names = {_slug(e["name"]) for e in steam_events.load(steam_events_path).get("events", [])}
    except Exception as ex:  # noqa: BLE001
        common.log(f"WARN steam_events not loaded ({ex})")
    steam_names |= {_slug(re.sub(r"\s*\(settimana \d+\)$", "", r.get("name") or "")) for r in keep if (r.get("source") or "").startswith("steam_events.py")}
    ours = window_rows(data, include_estimated, steam_names)
    hand = {((r.get("date") or "").strip(), _slug(r.get("name") or "")) for r in keep}
    hand_names = {_slug(re.sub(r"\s*\(settimana \d+\)$", "", r.get("name") or "")) for r in keep}
    before = len(ours)
    ours = [r for r in ours if (r["date"], _slug(r["name"])) not in hand and _slug(re.sub(r"\s*\(settimana \d+\)$", "", r["name"])) not in hand_names]
    rows = sorted(keep + ours, key=lambda r: (r.get("date") or "", r.get("name") or ""))
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lw.FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return dict(written=len(ours), kept=len(keep), skipped_dupes=before - len(ours))


# ---------------------------------------------------------------- CLI
def _timeline(a, launch_dir: str) -> Timeline:
    launch = a.launch
    if not launch:
        p = os.path.join(launch_dir, "_raw", "steam_events_deadlines.json")
        if os.path.exists(p):
            launch = common.load_json(p).get("launch")
    f = lambda s: D(s) if s else None  # noqa: E731
    return Timeline(page=f(a.page), itch=f(a.itch), demo=f(a.demo), launch=f(launch), ea=a.ea == "yes", eligible=[x.strip() for x in (a.eligible or "").split(",") if x.strip()], country=a.country)


def _res(a):
    today = D(a.today) if a.today else dt.date.today()
    data = load(a.events)
    tags_from = a.tags_from or os.path.join(a.launch_dir, "store_kit.json")
    tl = _timeline(a, a.launch_dir)
    res = plan(data, today, tl, our_tags(tags_from, a.tags), D(a.to) if a.to else None, a.include_physical, getattr(a, "all", False))
    return today, data, res


def cmd_fetch(a):
    out = a.out or default_out()
    old = common.load_json(out) if os.path.exists(out) else None
    data = fetch(offline=a.offline, rate=a.rate, today=D(a.today) if a.today else None)
    common.write_json(data, out)
    print(f"promo_events: {len(data.get('events', []))} eventi ({data.get('parser')}; {data.get('note')}) -> {out}")
    for line in (data.get("found") or []) + diff(old, data):
        print("  " + line)


def cmd_list(a):
    data = load(a.events)
    for e in data.get("events", []):
        if (a.online_only and not e.get("online", True)) or (a.kind and e["kind"] != a.kind):
            continue
        eds = [x for x in e.get("editions") or [] if x.get("start") or x.get("submission_deadline")]
        when = "; ".join(f"{x.get('start') or '?'} (scad. {x.get('submission_deadline') or '?'}) [{x.get('status')}]" for x in eds) or \
            (f"ogni {e['weekday']}" if e.get("weekday") else f"[DA VERIFICARE] {(e.get('pattern') or {}).get('text') or e.get('recurrence')}")
        print(f"{KIND_IT[e['kind']]:24} {'online' if e.get('online', True) else 'FISICO':7} {e.get('cost') or '?':5} {e['name']}: {when} · {e.get('submit_url') or e.get('url')}")
    print(f"(dati curati letti il {data.get('read_on')}, {data.get('parser') or 'file utente'})")


def cmd_match(a):
    today, data, res = _res(a)
    os.makedirs(os.path.join(a.launch_dir, "_raw"), exist_ok=True)
    common.write_json({k: v for k, v in res.items() if k != "physical"}, os.path.join(a.launch_dir, "_raw", "promo_events_match.json"))
    for r in res["matches"]:
        when = r.get("deadline") or r.get("trigger") or "-"
        est = " [stima]" if r["estimated"] else ""
        flag = (r["priority"] or "NO").upper()
        print(f"{flag:6} {when}{est:8} {KIND_IT[r['kind']]:24} {r['name']}" + (f"  ({'; '.join(r['reasons'])})" if r["reasons"] else "") + (f"  temi: {', '.join(r['match'])}" if r["match"] else ""))
    print(f"{len(res['matches'])} compatibili, {len(res['rejected'])} scartati · tappe {res['timeline']}")


def cmd_export(a):
    r = export_window(load(a.events), a.csv, a.include_estimated, a.steam_events)
    print(f"window.csv: {r['written']} righe degli eventi online, {r['kept']} righe esistenti conservate, {r['skipped_dupes']} doppioni saltati -> {a.csv}")


def cmd_deadlines(a):
    today, data, res = _res(a)
    sts = steps(res, today, a.max)
    os.makedirs(os.path.join(a.launch_dir, "_raw"), exist_ok=True)
    common.write_json(dict({k: v for k, v in res.items() if k not in ("physical", "rejected")}, steps=sts), os.path.join(a.launch_dir, "_raw", "promo_events_deadlines.json"))
    mdp = a.md or os.path.join(a.launch_dir, "promo-events.md")
    with open(mdp, "w", encoding="utf-8", newline="\n") as f:
        f.write(md(res, data, sts))
    for s in sts:
        print(f"{s['due']}  {s['who']} {re.sub(r'[*]', '', s['text'])}")
    if a.dry_run:
        print(f"(dry run: calendar.md e TODO.md non toccati) · {mdp}")
        return
    c = write_calendar(os.path.join(a.launch_dir, "calendar.md"), sts, today)
    t = write_todo(os.path.join(a.launch_dir, "TODO.md"), sts, today)
    rep = replace_generic(os.path.join(a.launch_dir, "TODO.md"), a.replace_todo, len([s for s in sts if s["kind"] == "candidatura"]), today) if a.replace_todo else False
    print(f"calendar.md: {c} passi aggiunti · TODO.md: {t} voci aggiunte" + (" · voce generica superata" if rep else "") + f" · {mdp}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("-o", "--out"); p.add_argument("--offline", action="store_true"); p.add_argument("--rate", type=float, default=2.0); p.add_argument("--today")
    p = sub.add_parser("list"); p.add_argument("--events"); p.add_argument("--online-only", action="store_true"); p.add_argument("--kind", choices=KINDS)
    for name in ("match", "deadlines"):
        p = sub.add_parser(name)
        p.add_argument("--events"); p.add_argument("--launch-dir", default="launch"); p.add_argument("--page"); p.add_argument("--itch"); p.add_argument("--demo")
        p.add_argument("--launch"); p.add_argument("--ea", choices=["yes", "no"], default="yes"); p.add_argument("--tags-from"); p.add_argument("--tags")
        p.add_argument("--to"); p.add_argument("--include-physical", action="store_true"); p.add_argument("--today")
        p.add_argument("--country", help="team country code (IT...) for national showcases and sales")
        p.add_argument("--eligible", help="keys of team-restricted events the team qualifies for (regional, women-led...)")
        if name == "match":
            p.add_argument("--all", action="store_true")
        else:
            p.add_argument("--max", type=int, default=12); p.add_argument("--md"); p.add_argument("--replace-todo"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("export-window"); p.add_argument("--events"); p.add_argument("--csv", default="launch/window.csv"); p.add_argument("--include-estimated", action="store_true")
    p.add_argument("--steam-events")
    a = ap.parse_args(argv)
    dict(fetch=cmd_fetch, list=cmd_list, match=cmd_match, **{"export-window": cmd_export, "deadlines": cmd_deadlines})[a.cmd](a)


if __name__ == "__main__":
    main()
