#!/usr/bin/env python3
"""Steam's own event calendar: seasonal sales, Next Fest, themed fests, with deadlines and who each one matters for.

Source: Valve's public page https://partner.steamgames.com/doc/marketing/upcoming_events (no login), plus the Next Fest
edition pages for the registration deadline and the themed-fest rules page. When the page cannot be read or parsed, the
hand-curated fallback in scripts/research/data/steam_events_fallback.json is used (and the output says so). Dates that
Valve has not published stay null with status "DA VERIFICARE" and a 'pattern' ("Summer Sale usually late June - early
July"): the tool never invents an exact day.

  steam_events.py fetch    [-o ~/.game-launch-strategist/steam_events.json] [--offline] [--rate 2]
  steam_events.py list     [--from 2026-10-01 --to 2027-06-30] [--kind seasonal_sale|next_fest|themed_fest|other]
  steam_events.py export-window --csv launch/window.csv          sales and fests into launch_window.py's window.csv
  steam_events.py deadlines --launch-dir launch [--launch 2027-05-13] [--next-fest nextfest_feb_2027]
                            [--tags-from launch/store_kit.json] [--tags "Simulation,Party"] [--demo yes|no]
                            [--local-coop no] [--dry-run] [--today D]

`export-window` replaces only the rows it wrote before (source starting with "steam_events.py"), never the rows you added
by hand, so re-running it never duplicates. Weights [OPINIONE]: seasonal sale 4 (the store is taken over by the sale;
launching inside one hides you from Popular Upcoming / New & Trending), Next Fest 4 (same reason), themed fest 1 (a
smaller, genre-specific page). One row per week of the event, so a two-week sale weighs on both weeks.

`deadlines` writes 👤 steps with dates into calendar.md (phase "### 📆 Eventi Steam") and TODO.md (section
"📆 Eventi Steam") through plan_steps / todo_track formats, without duplicates (a step that already names the same event
and the same date is left alone): the Next Fest registration and its Valve milestones for the edition you pick (default:
the last one that ends before your launch, as Zukowski advises), every themed fest whose theme matches your store tags
(registration deadline from Valve when published, otherwise "about 6 weeks before" [DA VERIFICARE]), and a warning when
your launch date falls inside a seasonal sale or Next Fest, or too late to join the next seasonal sale (30-day rule).
It also writes launch/_raw/steam_events_deadlines.json (read by top_moves.py) and launch/steam-events.md.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import re

import common

URL = "https://partner.steamgames.com/doc/marketing/upcoming_events"
NF_DOC = "https://partner.steamgames.com/doc/marketing/upcoming_events/nextfest/{slug}"
HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK = os.path.join(HERE, "data", "steam_events_fallback.json")
KINDS = ("seasonal_sale", "next_fest", "themed_fest", "other")
KIND_IT = {"seasonal_sale": "saldi stagionali", "next_fest": "Next Fest", "themed_fest": "fest a tema", "other": "altro"}
WEIGHT = {"seasonal_sale": 4, "next_fest": 4, "themed_fest": 1, "other": 1}
WINDOW_KIND = {"seasonal_sale": "sale", "next_fest": "festival", "themed_fest": "festival", "other": "festival"}
SRC_TAG = "steam_events.py"
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                       "october", "november", "december"], 1)}
MON3 = {k[:3]: v for k, v in MONTHS.items()}
D = dt.date.fromisoformat


def default_out() -> str:
    return common.user_dir("steam_events.json")


# ---------------------------------------------------------------- parsing the official page
def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", html.unescape(s)).strip()


def _body(page: str) -> str:
    i = page.find("documentation_bbcode")
    body = page[i:] if i >= 0 else page
    j = body.find("Steamworks is the set of tools")
    return body[:j] if j > 0 else body


def _date(day: int, month: str, year: int) -> str | None:
    m = MONTHS.get(month.lower()) or MON3.get(month.lower()[:3])
    try:
        return dt.date(year, m, day).isoformat() if m else None
    except ValueError:
        return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def parse_sales(body: str) -> list[dict]:
    """'<strong>Winter Sale 2026</strong> | 17 December, 2026 - 4 January, 2027' or '... | TBD'."""
    out = []
    for m in re.finditer(r"<strong>\s*((?:Winter|Spring|Summer|Autumn|Fall)\s+Sale\s+(\d{4}))\s*</strong>\s*\|\s*([^<]+)", body):
        name, year, when = m.group(1).strip(), int(m.group(2)), _text(m.group(3))
        r = re.match(r"(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})", when)
        ev = dict(key=_slug(name), name=f"Steam {name}", kind="seasonal_sale", start=None, end=None, registration_deadline=None, source=URL)
        if r:
            ev["start"], ev["end"] = _date(int(r.group(1)), r.group(2), int(r.group(3))), _date(int(r.group(4)), r.group(5), int(r.group(6)))
        if not (ev["start"] and ev["end"]):
            ev.update(start=None, end=None, status="DA VERIFICARE", pattern=f"Valve scrive '{when}'")
        else:
            ev["status"] = "confermato"
        ev["matters_for"] = "giochi usciti da almeno 30 giorni, con uno sconto; per chi lancia: il negozio è occupato dai saldi"
        out.append(ev)
    return out


def parse_fests(body: str) -> list[dict]:
    """Rows of the '<YEAR> Fests' tables: <tr><td>Oct 12<br>Oct 19</td><td>Name</td><td><a href=optin/sale/slug>…</a></td><td>notes</td></tr>."""
    out = []
    parts = re.split(r"(\d{4})\s+Fests", body)
    for k in range(1, len(parts) - 1, 2):
        year, chunk = int(parts[k]), parts[k + 1]
        chunk = re.split(r"\d{4}\s+Fests|Next Fest</h2>|bb_section", chunk)[0]
        for row in re.finditer(r"<tr>\s*<td>\s*([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*<br\s*/?>\s*([A-Za-z]{3,9})\.?\s+(\d{1,2})\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*</tr>", chunk, re.S):
            m1, d1, m2, d2, name, reg, notes = row.groups()
            start, end = _date(int(d1), m1, year), _date(int(d2), m2, year)
            if start and end and end < start:          # a fest across new year
                end = _date(int(d2), m2, year + 1)
            name = _text(name)
            slug = re.search(r"optin/sale/([a-z0-9_]+)", reg)
            more = re.search(r'href="([^"]+/themed_sales/[^"]+)"', notes)
            note = re.sub(r"\s*More info\.?\s*$", "", _text(notes)).strip()
            out.append(dict(key=slug.group(1) if slug else _slug(f"{name} {year}"), name=name, kind="themed_fest", start=start, end=end, registration_deadline=None,
                            status="confermato" if start and end else "DA VERIFICARE", matters_for=note, match=fest_keywords(name),
                            source=more.group(1) if more else URL, optin=f"https://partner.steamgames.com/optin/sale/{slug.group(1)}" if slug else None))
    return out


def parse_nextfests(body: str) -> list[dict]:
    """'Next Fest | October 19 - October 26, 2026', 'Next Fest | February 22 - March 1, 2027', 'Next Fest | June 14 - 21, 2027'."""
    out = []
    for m in re.finditer(r"Next Fest\s*\|\s*([A-Za-z]+)\s+(\d{1,2})\s*[-–]\s*(?:([A-Za-z]+)\s+)?(\d{1,2}),?\s+(\d{4})(?=(.{0,900}))", body, re.S):
        m1, d1, m2, d2, year, tail = m.groups()
        year = int(year)
        start, end = _date(int(d1), m1, year), _date(int(d2), m2 or m1, year)
        if start and end and end < start:
            start = _date(int(d1), m1, year - 1)
        doc = re.search(r'href="([^"]+/nextfest/[a-z0-9_]+)"', tail)
        slug = re.search(r"optin/sale/(nextfest_[a-z0-9_]+)", tail)
        month_it = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}
        mo = D(start).month if start else 0
        out.append(dict(key=slug.group(1) if slug else f"nextfest_{_slug(m1)}_{year}", name=f"Steam Next Fest {month_it.get(mo, m1)} {D(start).year if start else year}",
                        kind="next_fest", start=start, end=end, registration_deadline=None, status="confermato" if start and end else "DA VERIFICARE",
                        matters_for="solo giochi non usciti con pagina pubblica e demo giocabile, che escono dopo la fine del fest", source=doc.group(1) if doc else URL))
    return out


def _lines(page: str) -> list[str]:
    s = re.sub(r"<script.*?</script>", "", _body(page), flags=re.S)
    s = re.sub(r"<(?:br|/p|/li|/h\d|/tr|/div|/td)[^>]*>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return [re.sub(r"\s+", " ", ln).strip() for ln in s.split("\n") if ln.strip()]


def parse_nextfest_edition(page: str) -> dict:
    """Registration deadline and milestones of an edition page: 'January 2027' headings, then lines like
    'January 10, 11:59pm PST - Registration Deadline' or 'February 22 - Steam Next Fest begins ...'."""
    res, year, ms = {}, None, []
    for ln in _lines(page):
        h = re.match(r"^([A-Z][a-z]+)\s+(\d{4})$", ln)
        if h and h.group(1).lower() in MONTHS:
            year = int(h.group(2))
            continue
        m = re.match(r"^([A-Z][a-z]+)\s+(\d{1,2})(?:,[^-–]{0,40})?\s+[-–]\s+(.+)$", ln)
        if m and year and m.group(1).lower() in MONTHS:
            d = _date(int(m.group(2)), m.group(1), year)
            if d:
                what = m.group(3).strip()
                ms.append([d, what[:120]])
                if "registration deadline" in what.lower() and "registration_deadline" not in res:
                    res["registration_deadline"] = d
    if ms:
        res["milestones"] = ms
    return res


def fest_keywords(name: str) -> list[str]:
    base = re.sub(r"\b(fest|festival|steam|sale|\d{4}|[ivx]+)\b", " ", name.lower())
    words = [w for w in re.split(r"[^a-z0-9\-]+", base.replace(" vs. ", " ")) if len(w) > 2]
    joined = " ".join(words).strip()
    # the whole theme ('shop keeper'); a single word only for one-word themes ('racing'): broad words alone ('rpg',
    # 'strategy', 'co-op') would match too many games. The curated fallback has better words for the known fests.
    return [joined] if joined else []


def parse_page(page: str) -> list[dict]:
    body = _body(page)
    return parse_sales(body) + parse_fests(body) + parse_nextfests(body)


def merge(live: list[dict], fallback: list[dict]) -> list[dict]:
    """Live items win (by key, by kind + name, or by kind + start date); fallback-only items are kept (patterns for
    unpublished dates) and the curated details (theme words, Italian milestones) are added to the live items."""
    out = {e["key"]: dict(e) for e in live}
    by_name = {(e["kind"], _slug(e["name"])): e["key"] for e in live}
    by_start = {(e["kind"], e.get("start")): e["key"] for e in live if e.get("start")}
    for f in fallback:
        k = f["key"] if f["key"] in out else by_name.get((f["kind"], _slug(f["name"]))) or (by_start.get((f["kind"], f.get("start"))) if f.get("start") else None)
        if k:
            e = out[k]
            if f.get("match"):                      # curated theme words first: they were checked by hand
                e["match"] = list(dict.fromkeys(f["match"] + [m for m in e.get("match") or [] if m not in f["match"]]))
            fm, lm = f.get("milestones") or [], e.get("milestones") or []
            if fm and (not lm or {d for d, _ in fm} <= {d for d, _ in lm}):
                e["milestones"] = fm                # same dates: keep the curated Italian wording
            for fld in ("matters_for", "registration_deadline"):
                if f.get(fld) and not e.get(fld):
                    e[fld] = f[fld]
            if f.get("pattern") and not e.get("start"):
                e["pattern"] = (e["pattern"] + "; " if e.get("pattern") else "") + f["pattern"]
            continue
        out[f["key"]] = dict(f, origin="fallback")
    return sorted(out.values(), key=lambda e: (e.get("start") or "9999", e["name"]))


def load_fallback(path: str = FALLBACK) -> dict:
    return common.load_json(path)


def fetch(offline: bool = False, rate: float = 2.0, fallback_path: str = FALLBACK, today: dt.date | None = None) -> dict:
    fb = load_fallback(fallback_path)
    today = today or dt.date.today()
    if offline:
        return dict(fb, parser="fallback", read_on=fb.get("read_on"), note="offline: dati curati a mano")
    th = common.Throttle(rate)
    try:
        page = common.http_get(URL, throttle=th).decode("utf-8", "replace")
        live = parse_page(page)
    except Exception as e:  # noqa: BLE001
        common.log(f"WARN upcoming_events not read ({e}): using the fallback")
        return dict(fb, parser="fallback", note=f"pagina ufficiale non letta il {today}: {e}")
    if len([e for e in live if e["kind"] == "seasonal_sale"]) < 2 or not any(e["kind"] == "next_fest" for e in live):
        common.log("WARN the page did not parse as expected (layout changed?): using the fallback")
        return dict(fb, parser="fallback", note=f"pagina letta il {today} ma non riconosciuta: dati curati a mano")
    for e in live:
        e["read_on"] = today.isoformat()
        if e["kind"] == "next_fest" and e["source"] != URL:
            try:
                e.update({k: v for k, v in parse_nextfest_edition(common.http_get(e["source"], throttle=th).decode("utf-8", "replace")).items() if v})
            except Exception as ex:  # noqa: BLE001
                common.log(f"WARN {e['source']} not read: {ex}")
    events = merge(live, fb.get("events", []))
    return dict(source=URL, read_on=today.isoformat(), parser="live", rules=fb.get("rules", {}), events=events)


def load(path: str | None = None) -> dict:
    """The user file if it exists, else the fallback (always something to work with)."""
    p = path or default_out()
    if os.path.exists(p):
        return common.load_json(p)
    return dict(load_fallback(), parser="fallback")


def diff(old: dict | None, new: dict) -> list[str]:
    if not old:
        return []
    o = {e["key"]: e for e in old.get("events", [])}
    out = []
    for e in new.get("events", []):
        p = o.get(e["key"])
        if not p:
            out.append(f"nuovo: {e['name']} {e.get('start') or e.get('pattern')}")
        elif (p.get("start"), p.get("end"), p.get("registration_deadline")) != (e.get("start"), e.get("end"), e.get("registration_deadline")):
            out.append(f"cambiato: {e['name']} {p.get('start')}..{p.get('end')} -> {e.get('start')}..{e.get('end')} (iscrizione {e.get('registration_deadline')})")
    return out


# ---------------------------------------------------------------- window.csv
def window_rows(events: list[dict], read_on: str) -> list[dict]:
    rows = []
    for e in events:
        if not (e.get("start") and e.get("end")):
            continue
        s, en = D(e["start"]), D(e["end"])
        day, i = s, 0
        while day <= en:
            i += 1
            label = e["name"] if i == 1 else f"{e['name']} (settimana {i})"
            rows.append(dict(date=day.isoformat(), name=label, kind=WINDOW_KIND[e["kind"]], weight=WEIGHT[e["kind"]],
                             source=f"{SRC_TAG}, {e.get('source') or URL}, letto {e.get('read_on') or read_on}",
                             note=f"{KIND_IT[e['kind']]} {e['start']}..{e['end']} [OPINIONE sul peso]"))
            day += dt.timedelta(days=7)
        if (en - s).days % 7 and (en - (day - dt.timedelta(days=7))).days >= 4:   # a long tail after the last weekly row
            rows.append(dict(date=en.isoformat(), name=f"{e['name']} (ultimi giorni)", kind=WINDOW_KIND[e["kind"]], weight=WEIGHT[e["kind"]],
                             source=f"{SRC_TAG}, {e.get('source') or URL}, letto {e.get('read_on') or read_on}", note=f"{KIND_IT[e['kind']]} {e['start']}..{e['end']}"))
    return rows


def export_window(data: dict, csv_path: str) -> dict:
    import launch_window as lw
    keep = []
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            keep = [r for r in csv.DictReader(f) if not (r.get("source") or "").startswith(SRC_TAG)]
    ours = window_rows(data.get("events", []), data.get("read_on", ""))
    hand = {((r.get("date") or "").strip(), (r.get("name") or "").strip().lower()) for r in keep}
    ours = [r for r in ours if (r["date"], r["name"].lower()) not in hand]
    rows = sorted(keep + ours, key=lambda r: (r.get("date") or "", r.get("name") or ""))
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lw.FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    skipped = [e["name"] for e in data.get("events", []) if not (e.get("start") and e.get("end"))]
    return dict(written=len(ours), kept=len(keep), not_dated=skipped)


def window_items(path: str | None = None) -> list[dict]:
    """For launch_window.py: the same rows as items (date objects), from the user file or the fallback."""
    data = load(path)
    out = []
    for r in window_rows(data.get("events", []), data.get("read_on", "")):
        out.append(dict(date=D(r["date"]), name=r["name"], kind=r["kind"], weight=float(r["weight"]), source=r["source"], origin="steam_events"))
    return out


# ---------------------------------------------------------------- deadlines for one game
def our_tags(tags_from: str | None, extra: str | None) -> list[str]:
    tags = []
    if tags_from and os.path.exists(tags_from):
        kit = common.load_json(tags_from)
        for t in ((kit.get("steam") or {}).get("tags") or []):
            tags.append(t["tag"] if isinstance(t, dict) else str(t))
    tags += [t.strip() for t in (extra or "").split(",") if t.strip()]
    return list(dict.fromkeys(tags))


def fest_match(ev: dict, tags: list[str], local_coop: bool) -> list[str]:
    low = [t.lower() for t in tags]
    if ev["key"].startswith("couch_coop") and not local_coop:
        return []
    hits = []
    for kw in ev.get("match") or fest_keywords(ev["name"]):
        if any(kw == t or kw in t or (len(t) > 3 and t in kw) for t in low):
            hits.append(kw)
    return sorted(set(hits))


def plan(data: dict, today: dt.date, launch: dt.date | None, tags: list[str], demo: bool, local_coop: bool, next_fest: str | None) -> dict:
    ev = data.get("events", [])
    steps, warnings, fests, eligible_nf = [], [], [], []
    # a Next Fest is still possible if its registration is open and the demo can still pass review (3 weeks before the start)
    nfs = [e for e in ev if e["kind"] == "next_fest" and e.get("end") and D(e["start"]) >= today + dt.timedelta(days=21)
           and (not e.get("registration_deadline") or D(e["registration_deadline"]) >= today) and (not launch or D(e["end"]) < launch)]
    chosen = next((e for e in nfs if e["key"] == next_fest), None) if next_fest else (nfs[-1] if nfs else None)
    for e in nfs:
        eligible_nf.append(dict(key=e["key"], name=e["name"], start=e["start"], end=e["end"], registration_deadline=e.get("registration_deadline"), chosen=e is chosen))
    if chosen:
        reg = chosen.get("registration_deadline")
        if reg and D(reg) >= today:
            steps.append(dict(key=f"{chosen['key']}:reg", event=chosen["name"], who="👤", kind="registrazione", deadline=reg, due=(D(reg) - dt.timedelta(days=5)).isoformat(),
                              text=f"**Iscrivi la demo allo {chosen['name']}** in Steamworks (pagina pubblica e demo giocabile entro l'inizio del fest; un gioco entra in un solo Next Fest)",
                              note=f"scadenza Valve {reg} [FATTO {chosen.get('source')}, letto {chosen.get('read_on') or data.get('read_on')}]" + ("" if demo else " · ATTENZIONE: oggi non risulta una demo")))
        for d, what in chosen.get("milestones") or []:
            useful = re.search(r"trailer|revision|review|submit|press preview|begins|live|demo", what, re.I) and not re.search(r"opt out|q&a|zoom|concludes|wrap-up", what, re.I)
            if d == reg or D(d) < today or not useful:
                continue
            steps.append(dict(key=f"{chosen['key']}:{d}", event=chosen["name"], who="👤", kind="scadenza", deadline=d, due=(D(d) - dt.timedelta(days=3)).isoformat() if D(d) - dt.timedelta(days=3) >= today else d,
                              text=f"**{chosen['name']}: {what}**", note=f"data Valve {d} [FATTO, letto {chosen.get('read_on') or data.get('read_on')}]"))
    for e in ev:
        if e["kind"] != "themed_fest":
            continue
        hits = fest_match(e, tags, local_coop)
        row = dict(key=e["key"], name=e["name"], start=e.get("start"), end=e.get("end"), status=e.get("status"), matters_for=e.get("matters_for"), match=hits)
        if not hits:
            continue
        fests.append(row)
        if not e.get("start"):
            steps.append(dict(key=f"{e['key']}:watch", event=e["name"], who="👤+🤖", kind="da verificare", deadline=None, due=(today + dt.timedelta(days=28)).isoformat(),
                              text=f"**Controlla se Valve ha annunciato il {e['name']}** (tema compatibile con i nostri tag: {', '.join(hits)})", note=f"[DA VERIFICARE] {e.get('pattern') or ''}"))
            continue
        if D(e["end"]) < today:
            continue
        reg = e.get("registration_deadline")
        est = not reg
        dl = D(reg) if reg else D(e["start"]) - dt.timedelta(days=42)
        if D(e["start"]) < today:
            continue
        label = f"scadenza Valve {reg}" if reg else f"scadenza non pubblicata: di solito ~6 settimane prima, cioè verso il {dl.isoformat()} [DA VERIFICARE nell'invito o in {e.get('source')}]"
        steps.append(dict(key=f"{e['key']}:reg", event=e["name"], who="👤", kind="registrazione", deadline=dl.isoformat(), estimated=est,
                          due=max(today, dl - dt.timedelta(days=5)).isoformat(),
                          text=f"**Iscriviti al {e['name']}** ({e['start']} → {e['end']}) se arriva l'invito: tema compatibile con i tag {', '.join(hits)}; ci si iscrive anche come Coming Soon o con la demo",
                          note=label))
    sales = [e for e in ev if e["kind"] == "seasonal_sale"]
    if launch:
        for e in sales + [x for x in ev if x["kind"] == "next_fest"]:
            if e.get("start") and D(e["start"]) - dt.timedelta(days=2) <= launch <= D(e["end"]):
                warnings.append(dict(event=e["name"], start=e["start"], end=e["end"], level="ALARM",
                                     text=f"La data di uscita {launch} cade dentro lo {e['name']} ({e['start']} → {e['end']}): il negozio è occupato dall'evento e le liste dei nuovi giochi si vedono meno. Sposta la data prima o dopo."))
        nxt = next((e for e in sales if e.get("start") and D(e["start"]) > launch), None)
        if nxt:
            last_ok = D(nxt["start"]) - dt.timedelta(days=30)
            ok = launch <= last_ok
            warnings.append(dict(event=nxt["name"], start=nxt["start"], end=nxt["end"], level="INFO" if ok else "WARN",
                                 text=(f"Con l'uscita il {launch} puoi entrare con uno sconto nello {nxt['name']} ({nxt['start']}): serve essere usciti da almeno 30 giorni, cioè entro il {last_ok}."
                                       if ok else f"Con l'uscita il {launch} NON puoi scontare il gioco nello {nxt['name']} ({nxt['start']}): servono 30 giorni dall'uscita (ultima data utile {last_ok}).")))
        for e in sales:
            if not e.get("start") and e.get("pattern"):
                warnings.append(dict(event=e["name"], start=None, end=None, level="INFO", text=f"{e['name']}: date non pubblicate [DA VERIFICARE] ({e['pattern']})."))
    return dict(computed_on=today.isoformat(), launch=launch.isoformat() if launch else None, tags=tags, demo=demo, local_coop=local_coop,
                events_read_on=data.get("read_on"), parser=data.get("parser"), next_fests=eligible_nf, next_fest_chosen=chosen["key"] if chosen else None,
                themed_fests=fests, steps=steps, warnings=warnings)


def _name_words(ev: str) -> list[str]:
    if "next fest" in ev.lower():
        return ["fest"]                     # hand-written steps say "il fest", "Next Fest", "video ufficiale del fest"
    w = [x for x in re.findall(r"[a-z]{4,}", ev.lower()) if x not in ("steam", "fest", "festival", "sale", "febbraio", "giugno", "ottobre")]
    return w[:2] or [ev.lower()]


def _already(text_low: str, st: dict) -> bool:
    dates = {d for d in (st.get("deadline"), st.get("due")) if d}
    return any(d in text_low for d in dates) and all(w in text_low for w in _name_words(st["event"]))


def write_calendar(path: str, res: dict, today: dt.date) -> int:
    import plan_steps as ps
    if not os.path.exists(path):
        return 0
    raw = open(path, encoding="utf-8").read().replace("\r", "")
    lines = raw.split("\n")
    plan_ = ps.parse(raw)
    if not plan_["phases"]:
        return 0
    texts = [s["text"].lower() + " " + " ".join(s.get("notes") or []).lower() for s in ps.all_steps(plan_)]
    # notes are indented lines under a step: include the raw lines too
    texts.append(raw.lower())
    nmax = max((s["n"] for s in ps.all_steps(plan_)), default=0)
    add = []
    for st in res["steps"] + [dict(key="warn", event=w["event"], who="👤+🤖", deadline=w.get("start"), due=w.get("start"), kind="avviso",
                                    text=f"**⚠️ {w['text']}**", note="") for w in res["warnings"] if w["level"] in ("ALARM", "WARN")]:
        if any(_already(t, st) for t in texts[:-1]) or _already_line(raw.lower(), st):
            continue
        nmax += 1
        due = st.get("due") or today.isoformat()
        add.append(f"{nmax}. [ ] {st['who']} {st['text']}. · 📅 {due}")
        if st.get("note"):
            add.append(f"   - {st['note']}")
    if not add:
        return 0
    head_txt = f"### 📆 Eventi Steam (da steam_events.py, aggiornato il {today.isoformat()})"
    head = next((k for k, ln in enumerate(lines) if ln.startswith("### 📆 Eventi Steam")), None)
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


def _already_line(raw_low: str, st: dict) -> bool:
    """A single line of the file that names the event and one of its dates (steps written by hand, TODO lines, tables)."""
    dates = [d for d in (st.get("deadline"), st.get("due")) if d]
    ws = _name_words(st["event"])
    # steps without a real deadline ("controlla se Valve ha annunciato...") get a due date relative to the day of the run:
    # for them the same bold title on a step or TODO line is enough, so re-running on another day does not add a copy
    m = None if st.get("deadline") else re.search(r"\*\*(.+?)\*\*", st.get("text") or "")
    title = m.group(1).lower() if m else None
    return any(re.match(r"^\s*(\d+\.|-)\s*\[", ln) and ((any(d in ln for d in dates) and all(w in ln for w in ws)) or (title and title in ln)) for ln in raw_low.split("\n"))


def write_todo(path: str, res: dict, today: dt.date) -> int:
    import todo_track as tt
    if not os.path.exists(path):
        return 0
    n = 0
    for st in res["steps"] + [dict(event=w["event"], who="👤", deadline=w.get("start"), due=w.get("start"), text=f"**⚠️ {w['text']}**", note="")
                              for w in res["warnings"] if w["level"] in ("ALARM", "WARN")]:
        raw = open(path, encoding="utf-8").read().lower()
        if _already_line(raw, st):
            continue
        tt.add(path, "📆 Eventi Steam (steam_events.py)", f"{st['who']} {st['text']} — {st.get('due') or today.isoformat()} — 0,5 h — "
               f"{'pagina Steam pubblica' if 'next fest' in st['event'].lower() else 'invito Valve'} — {st.get('note') or 'fatto in Steamworks'}", today)
        n += 1
    return n


def md(res: dict, data: dict) -> str:
    L = ["# Calendario degli eventi Steam", "",
         f"Fonte: [pagina ufficiale Valve]({URL}), letta il {data.get('read_on')} ({'lettura automatica' if data.get('parser') == 'live' else 'dati curati a mano: pagina non letta'}). "
         f"Calcolato il {res['computed_on']} per l'uscita del **{res['launch'] or 'data non indicata'}**. Le date senza giorno sono **[DA VERIFICARE]**: mai inventate.", "",
         "## Tutti gli eventi", "", "| Evento | Tipo | Dal | Al | Iscrizione | Per chi conta |", "|---|---|---|---|---|---|"]
    for e in data.get("events", []):
        L.append(f"| {e['name']} | {KIND_IT.get(e['kind'], e['kind'])} | {e.get('start') or '[DA VERIFICARE]'} | {e.get('end') or (e.get('pattern') or '')} | "
                 f"{e.get('registration_deadline') or ('~6 settimane prima [DA VERIFICARE]' if e['kind'] == 'themed_fest' and e.get('start') else '-')} | {e.get('matters_for') or ''} |")
    L += ["", "## Per il nostro gioco", ""]
    if res["warnings"]:
        L += [f"- **{w['level']}** {w['text']}" for w in res["warnings"]]
    nf = [f"{n['name']} ({n['start']} → {n['end']}, iscrizione {n.get('registration_deadline') or '[DA VERIFICARE]'})" + (" ◀ scelto" if n["chosen"] else "") for n in res["next_fests"]]
    L += ["", "Next Fest possibili prima dell'uscita: " + ("; ".join(nf) if nf else "nessuno"), ""]
    L += ["Fest a tema compatibili con i nostri tag (" + ", ".join(res["tags"]) + "):", ""]
    L += [f"- {f['name']} ({f.get('start') or '[DA VERIFICARE]'} → {f.get('end') or ''}): parole in comune {', '.join(f['match'])}. {f.get('matters_for') or ''}" for f in res["themed_fests"]] or ["- nessuno nel calendario pubblicato"]
    L += ["", "## Regole (Valve, lette il " + str(data.get("read_on")) + ")", ""] + [f"- {v}" for v in (data.get("rules") or {}).values()]
    L += ["", "## Come usarlo", "- Mai lanciare dentro un saldo stagionale o un Next Fest: va bene la settimana prima o dopo [OPINIONE, Zukowski 2023].",
          "- I fest a tema sono visibilità gratis: l'invito arriva per email se i tag e la pagina corrispondono; controlla i tag prima della scadenza.",
          "- Rilancia `steam_events.py fetch` e `deadlines` ogni settimana: Valve aggiunge eventi nel corso dell'anno."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- CLI
def cmd_fetch(a):
    out = a.out or default_out()
    old = common.load_json(out) if os.path.exists(out) else None
    data = fetch(offline=a.offline, rate=a.rate, today=D(a.today) if a.today else None)
    common.write_json(data, out)
    n = len(data.get("events", []))
    print(f"steam_events: {n} eventi ({data.get('parser')}, letto {data.get('read_on')}) -> {out}")
    for line in diff(old, data):
        print("  " + line)


def cmd_list(a):
    data = load(a.events)
    for e in data.get("events", []):
        if a.kind and e["kind"] != a.kind:
            continue
        if a.start and e.get("end") and e["end"] < a.start:
            continue
        if a.end and e.get("start") and e["start"] > a.end:
            continue
        when = f"{e['start']} -> {e['end']}" if e.get("start") else f"[DA VERIFICARE] {e.get('pattern', '')}"
        reg = f" · iscrizione {e['registration_deadline']}" if e.get("registration_deadline") else ""
        print(f"{when:28} {KIND_IT.get(e['kind'], e['kind']):17} {e['name']}{reg}")
    print(f"(fonte {data.get('source')}, letto {data.get('read_on')}, {data.get('parser')})")


def cmd_export(a):
    r = export_window(load(a.events), a.csv)
    print(f"window.csv: {r['written']} righe degli eventi Steam, {r['kept']} righe tue conservate -> {a.csv}")
    if r["not_dated"]:
        print("  senza date (non conteggiati): " + ", ".join(r["not_dated"]))


def cmd_deadlines(a):
    today = D(a.today) if a.today else dt.date.today()
    data = load(a.events)
    tags_from = a.tags_from or os.path.join(a.launch_dir, "store_kit.json")
    res = plan(data, today, D(a.launch) if a.launch else None, our_tags(tags_from, a.tags), a.demo == "yes", a.local_coop == "yes", a.next_fest)
    os.makedirs(os.path.join(a.launch_dir, "_raw"), exist_ok=True)
    common.write_json(res, os.path.join(a.launch_dir, "_raw", "steam_events_deadlines.json"))
    with open(os.path.join(a.launch_dir, "steam-events.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(md(res, data))
    for w in res["warnings"]:
        print(f"{w['level']}: {w['text']}")
    for s in res["steps"]:
        print(f"{s['due']}  {s['who']} {re.sub(r'[*]', '', s['text'])}  ({s.get('note')})")
    if a.dry_run:
        print("(dry run: calendar.md e TODO.md non toccati)")
        return
    c = write_calendar(os.path.join(a.launch_dir, "calendar.md"), res, today)
    t = write_todo(os.path.join(a.launch_dir, "TODO.md"), res, today)
    print(f"calendar.md: {c} passi aggiunti · TODO.md: {t} voci aggiunte · {os.path.join(a.launch_dir, 'steam-events.md')}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("-o", "--out"); p.add_argument("--offline", action="store_true"); p.add_argument("--rate", type=float, default=2.0); p.add_argument("--today")
    p = sub.add_parser("list"); p.add_argument("--events"); p.add_argument("--from", dest="start"); p.add_argument("--to", dest="end"); p.add_argument("--kind", choices=KINDS)
    p = sub.add_parser("export-window"); p.add_argument("--events"); p.add_argument("--csv", default="launch/window.csv")
    p = sub.add_parser("deadlines"); p.add_argument("--events"); p.add_argument("--launch-dir", default="launch"); p.add_argument("--launch")
    p.add_argument("--next-fest"); p.add_argument("--tags-from"); p.add_argument("--tags"); p.add_argument("--demo", choices=["yes", "no"], default="yes")
    p.add_argument("--local-coop", choices=["yes", "no"], default="no"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--today")
    a = ap.parse_args(argv)
    dict(fetch=cmd_fetch, list=cmd_list, **{"export-window": cmd_export, "deadlines": cmd_deadlines})[a.cmd](a)


if __name__ == "__main__":
    main()
