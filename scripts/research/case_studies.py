#!/usr/bin/env python3
"""Real launch and Next Fest case studies: what games like ours did at our stage, with the source of every number.

Records come from public dev posts and post-mortems (Reddit, blogs, Game Developer, How To Market A Game...). Each one keeps
the source URL and its date, and `confidence` says whether the numbers are self-reported (almost always) or verified.
The curated seed lives in the skill (`data/case_studies.json`, with aggregate `benchmarks` from larger surveys); what you
add goes to your private file `~/.game-launch-strategist/case_studies.json` (never into the skill), and both are read together.

  case_studies.py add --game "X" --genres roguelite,comedy --event next_fest --date 2026-02 --wl-before 1900 --wl-after 4100 \\
                      --source https://... --source-date 2026-02-28 [--team-size 2 --price 9.99 --did "trailer on IGN; 2 youtubers"]
  case_studies.py import posts.json|posts.csv                    merge records (same id or same game+event+date = update)
  case_studies.py query [--genre roguelite] [--event next_fest] [--wl-min 1000 --wl-max 3000] [--team-max 5] [--md]
  case_studies.py bench --entering 2000 [--genre roguelite] [--band 0.5]     Next Fest gain for games entering with ~N wishlists
  case_studies.py tripwires --entering 600,1000,2000 --calendar launch/calendar.md [--fest "Next Fest febbraio 2027"]
                      writes "### 📊 Next Fest: cosa aspettarsi" in the Tripwire section of calendar.md (idempotent)
  case_studies.py md -o launch/case-studies.md [--genre ...]     readable summary with benchmarks and the "our stage" table

Honesty rules built in: medians come with n and the interval between the 25th and 75th percentile; fewer than 5 similar
records = "campione piccolo" and the survey benchmark (n in the hundreds) leads; self-reported posts are survivorship-biased
(people post when it went well), so the case median is shown NEXT to the survey median, never instead of it.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import statistics

import common
from common import load_json, log, user_dir, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "case_studies.json")
NUM_FIELDS = ("wishlists_before", "wishlists_after", "wishlists_at_launch", "followers", "demo_players", "sales_first_week", "sales_first_month",
              "sales_total", "team_size", "appid")
FLOAT_FIELDS = ("price_usd", "demo_median_playtime_min")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:60]


def load(db: str | None = None, local: str | None = None) -> dict:
    """Seed + private records (private ones win on the same id)."""
    d = load_json(db or DB) if os.path.exists(db or DB) else {}
    recs = {r["id"]: dict(r, origin="skill") for r in d.get("records", [])}
    lp = local if local is not None else user_dir("case_studies.json")
    if lp and os.path.exists(lp):
        for r in (load_json(lp) or {}).get("records", []):
            recs[r["id"]] = dict(r, origin="mine")
    return dict(meta=d.get("meta") or {}, benchmarks=d.get("benchmarks") or [], records=list(recs.values()))


def clean(r: dict) -> dict:
    o = dict(r)
    for k in NUM_FIELDS:
        v = o.get(k)
        if v in ("", None):
            o[k] = None
        else:
            try:
                o[k] = int(float(str(v).replace(",", "").replace(".", "") if isinstance(v, str) and re.match(r"^\d{1,3}([.,]\d{3})+$", v) else v))
            except ValueError:
                o[k] = None
    for k in FLOAT_FIELDS:
        v = o.get(k)
        try:
            o[k] = None if v in ("", None) else float(v)
        except ValueError:
            o[k] = None
    for k in ("genres", "what_they_did"):
        v = o.get(k)
        if isinstance(v, str):
            o[k] = [x.strip() for x in re.split(r"[;,|]" if k == "genres" else r"[;|]", v) if x.strip()]
        o[k] = [x.lower() for x in (o.get(k) or [])] if k == "genres" else (o.get(k) or [])
    if not o.get("id"):
        o["id"] = slug(f"{o.get('game')}-{o.get('event')}-{o.get('date')}")
    if not o.get("source_url") or not str(o["source_url"]).startswith("http"):
        raise SystemExit(f"{o.get('game')}: every record needs source_url (http...)")
    o.setdefault("confidence", "self_reported")
    o.setdefault("checked", dt.date.today().isoformat())
    return o


def merge(path: str, new: list[dict]) -> tuple[int, int]:
    cur = load_json(path) if os.path.exists(path) else {"records": []}
    by = {r["id"]: r for r in cur.get("records", [])}
    key = lambda r: (str(r.get("game", "")).lower(), r.get("event"), str(r.get("date", ""))[:7])
    by_key = {key(r): r["id"] for r in by.values()}
    added = updated = 0
    for r in new:
        r = clean(r)
        rid = r["id"] if r["id"] in by else by_key.get(key(r), r["id"])
        if rid in by:
            by[rid] = {**by[rid], **{k: v for k, v in r.items() if v not in (None, [], "")}, "id": rid}
            updated += 1
        else:
            by[rid] = r
            by_key[key(r)] = rid
            added += 1
    cur["records"] = sorted(by.values(), key=lambda r: (str(r.get("date", "")), r["id"]))
    write_json(cur, path)
    return added, updated


def read_file(path: str) -> list[dict]:
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    d = load_json(path)
    return d.get("records", d) if isinstance(d, dict) else d


# ---------------------------------------------------------------- queries and benchmarks
def query(recs: list[dict], genre: str | None = None, event: str | None = None, wl_min: int | None = None, wl_max: int | None = None,
          team_max: int | None = None) -> list[dict]:
    out = []
    for r in recs:
        if genre and not any(genre.lower() in g for g in (r.get("genres") or [])):
            continue
        if event and r.get("event") != event:
            continue
        wb = r.get("wishlists_before")
        if (wl_min is not None or wl_max is not None) and wb is None:
            continue
        if wl_min is not None and wb < wl_min or wl_max is not None and wb > wl_max:
            continue
        if team_max is not None and r.get("team_size") and r["team_size"] > team_max:
            continue
        out.append(r)
    return out


def quart(xs: list[float]) -> tuple[float, float, float]:
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0], xs[0], xs[0]
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return q[0], statistics.median(xs), q[2]


def survey_for(benchmarks: list[dict], n: int, event: str = "next_fest") -> dict | None:
    """The survey bucket (e.g. Zukowski's 1,000-9,999) that contains N wishlists at entry; latest first."""
    hits = [b for b in benchmarks if b.get("event", "next_fest") == event and b.get("bucket_min") is not None
            and b["bucket_min"] <= n <= (b.get("bucket_max") if b.get("bucket_max") is not None else 10 ** 9) and b.get("median_gain") is not None]
    return sorted(hits, key=lambda b: str(b.get("date", "")), reverse=True)[0] if hits else None


def bench(recs: list[dict], benchmarks: list[dict], entering: int, genre: str | None = None, band: float = 0.5) -> dict:
    """Next Fest gain for games that entered with about `entering` wishlists: our case records + the survey bucket."""
    pool = [r for r in recs if r.get("event") == "next_fest" and r.get("wishlists_before") and r.get("wishlists_after") is not None
            and r["wishlists_after"] >= r["wishlists_before"]]
    if genre:
        g_pool = [r for r in pool if any(genre.lower() in g for g in r.get("genres") or [])]
        pool = g_pool if len(g_pool) >= 3 else pool
    used_band, near = band, []
    for b in sorted({band, 0.75}):          # never wider than +-75 %: a 300-wishlist game says nothing about one with 2,000
        near = [r for r in pool if entering * (1 - b) <= r["wishlists_before"] <= entering * (1 + b)]
        used_band = b
        if len(near) >= 5:
            break
    out = dict(entering=entering, band=used_band, n=len(near), genre=genre, records=[r["id"] for r in near])
    if near:
        gains = [r["wishlists_after"] - r["wishlists_before"] for r in near]
        mult = [r["wishlists_after"] / r["wishlists_before"] for r in near]
        g25, gm, g75 = quart(gains)
        m25, mm, m75 = quart(mult)
        out.update(gain_p25=round(g25), gain_median=round(gm), gain_p75=round(g75), mult_median=round(mm, 2), mult_p25=round(m25, 2), mult_p75=round(m75, 2),
                   small_sample=len(near) < 5)
    sv = survey_for(benchmarks, entering)
    if sv:
        out["survey"] = dict(label=sv.get("label"), median_gain=sv["median_gain"], n=sv.get("n"), url=sv.get("url"), date=sv.get("date"),
                             bucket=[sv.get("bucket_min"), sv.get("bucket_max")])
    # the line to trust: the survey (large n, less survivorship bias) unless it is missing
    if sv:
        lo = round(sv["median_gain"] * 0.5)
        hi = round(sv["median_gain"] * 1.6)
        if near and not out.get("small_sample"):
            lo, hi = min(lo, out["gain_p25"]), max(hi, out["gain_p75"])
        out["expected"] = dict(low=lo, mid=sv["median_gain"], high=hi, basis="sondaggio" + (" + casi" if near else ""))
    elif near:
        out["expected"] = dict(low=out["gain_p25"], mid=out["gain_median"], high=out["gain_p75"], basis="casi (campione piccolo)" if out["small_sample"] else "casi")
    return out


def fmt(n) -> str:
    return "?" if n is None else f"{int(n):,}".replace(",", ".")


def tripwire_md(rows: list[dict], fest: str, today: dt.date) -> str:
    L = [f"Da `case_studies.py` ({today.isoformat()}): quante wishlist porta il Next Fest a chi entra con N wishlist. "
         "**[FATTO]** il sondaggio (n alto) e **[STIMA]** la forchetta; i casi singoli sono auto-dichiarati e di solito ottimisti (chi posta è chi è andato bene).", "",
         f"| Entri nel {fest} con | Atteso alla fine del fest [STIMA] | Mediana del sondaggio | Casi simili (n, mediana) | Se sei sotto la forchetta bassa |",
         "|---|---|---|---|---|"]
    for b in rows:
        e = b.get("expected") or {}
        sv = b.get("survey") or {}
        cases = f"{b['n']}, +{fmt(b.get('gain_median'))}" + (" (pochi)" if b.get("small_sample") else "") if b["n"] else "nessuno"
        rng = f"+{fmt(e.get('low'))} … +{fmt(e.get('high'))} (totale {fmt(b['entering'] + (e.get('low') or 0))} … {fmt(b['entering'] + (e.get('high') or 0))})" if e else "?"
        svs = f"+{fmt(sv.get('median_gain'))} ([fonte]({sv['url']}), {sv.get('date')}, n = {sv.get('n') or '?'})" if sv else "—"
        L.append(f"| {fmt(b['entering'])} | {rng} | {svs} | {cases} | il problema è la pagina o la demo, non il fest: rivedi capsule, primi 5 s del trailer, demo→wishlist |")
    return "\n".join(L)


def stage_table(recs: list[dict], genre: str | None, limit: int = 12) -> list[str]:
    rows = [r for r in recs if not genre or any(genre.lower() in g for g in r.get("genres") or [])] or recs
    rows = sorted(rows, key=lambda r: (r.get("wishlists_before") or r.get("wishlists_at_launch") or 0))[:limit]
    L = ["| Gioco | Genere | Quando | Evento | Wishlist prima → dopo | All'uscita | Vendite | Cosa hanno fatto | Fonte |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        sales = r.get("sales_first_week") or r.get("sales_first_month") or r.get("sales_total")
        L.append(f"| {r.get('game')} | {', '.join((r.get('genres') or [])[:3])} | {r.get('date') or '?'} | {r.get('event') or '?'} | "
                 f"{fmt(r.get('wishlists_before'))} → {fmt(r.get('wishlists_after'))} | {fmt(r.get('wishlists_at_launch'))} | {fmt(sales)} | "
                 f"{'; '.join((r.get('what_they_did') or [])[:3])} | [{r.get('source_kind') or 'fonte'}]({r.get('source_url')}) {r.get('source_date') or ''} |")
    return L


def to_md(data: dict, genre: str | None, entering: list[int], today: dt.date) -> str:
    recs = data["records"]
    L = ["# Casi reali: cosa hanno fatto giochi come il nostro", "",
         f"Generato da `case_studies.py` il {today.isoformat()} · {len(recs)} casi ({sum(1 for r in recs if r.get('origin') == 'mine')} aggiunti da te) · "
         f"{len(data['benchmarks'])} benchmark da sondaggi. Numeri **auto-dichiarati** dagli sviluppatori salvo dove scritto; ogni riga ha la fonte.", "",
         "## Next Fest: quanto porta, in base a quante wishlist hai quando entri", ""]
    rows = [bench(recs, data["benchmarks"], n, genre) for n in entering]
    L.append(tripwire_md(rows, "Next Fest", today))
    L += ["", "## Benchmark dai sondaggi", "", "| Cosa | Valore | n | Fonte |", "|---|---|---|---|"]
    for b in data["benchmarks"]:
        L.append(f"| {b.get('label')} | {b.get('value') or ('+' + fmt(b.get('median_gain')) if b.get('median_gain') is not None else '?')} | {b.get('n') or '?'} | [{b.get('source') or 'fonte'}]({b.get('url')}) {b.get('date') or ''} |")
    L += ["", f"## Giochi alla nostra fase{(' (' + genre + ')') if genre else ''}", ""] + stage_table(recs, genre)
    L += ["", "_Correlazione non è causa; chi pubblica i propri numeri di solito è andato meglio della media (bias del sopravvissuto)._"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db"); ap.add_argument("--local", help="private records file (default ~/.game-launch-strategist/case_studies.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add")
    for f in ("game", "genres", "event", "date", "fest", "publisher", "source", "source-date", "source-kind", "did", "note", "confidence"):
        a_.add_argument(f"--{f}")
    for f in ("wl-before", "wl-after", "wl-launch", "followers", "demo-players", "sales-week", "sales-month", "sales-total", "team-size", "appid"):
        a_.add_argument(f"--{f}", type=int)
    a_.add_argument("--price", type=float)
    i_ = sub.add_parser("import"); i_.add_argument("file")
    q_ = sub.add_parser("query")
    q_.add_argument("--genre"); q_.add_argument("--event"); q_.add_argument("--wl-min", type=int); q_.add_argument("--wl-max", type=int)
    q_.add_argument("--team-max", type=int); q_.add_argument("--md", action="store_true")
    b_ = sub.add_parser("bench"); b_.add_argument("--entering", type=int, required=True); b_.add_argument("--genre"); b_.add_argument("--band", type=float, default=0.5)
    t_ = sub.add_parser("tripwires"); t_.add_argument("--entering", default="600,1000,2000"); t_.add_argument("--genre")
    t_.add_argument("--calendar", required=True); t_.add_argument("--fest", default="Next Fest"); t_.add_argument("-o", "--out")
    m_ = sub.add_parser("md"); m_.add_argument("--genre"); m_.add_argument("--entering", default="300,600,1000,2000,5000"); m_.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    today = dt.date.today()
    local = a.local if a.local is not None else user_dir("case_studies.json")
    if a.cmd == "add":
        r = dict(game=a.game, genres=a.genres, event=a.event, date=a.date, fest=a.fest, publisher=a.publisher, source_url=a.source,
                 source_date=a.source_date, source_kind=a.source_kind, what_they_did=a.did, outcome_note=a.note, confidence=a.confidence or "self_reported",
                 wishlists_before=a.wl_before, wishlists_after=a.wl_after, wishlists_at_launch=a.wl_launch, followers=a.followers, demo_players=a.demo_players,
                 sales_first_week=a.sales_week, sales_first_month=a.sales_month, sales_total=a.sales_total, team_size=a.team_size, appid=a.appid, price_usd=a.price)
        print("added %d, updated %d" % merge(local, [{k: v for k, v in r.items() if v is not None}]))
        return
    if a.cmd == "import":
        print("added %d, updated %d" % merge(local, read_file(a.file)))
        return
    data = load(a.db, local)
    if a.cmd == "query":
        rows = query(data["records"], a.genre, a.event, a.wl_min, a.wl_max, a.team_max)
        print("\n".join(stage_table(rows, None, 100)) if a.md else json.dumps(rows, ensure_ascii=False, indent=1))
        return
    if a.cmd == "bench":
        print(json.dumps(bench(data["records"], data["benchmarks"], a.entering, a.genre, a.band), ensure_ascii=False, indent=1))
        return
    ents = [int(x) for x in str(a.entering).split(",") if x.strip()]
    if a.cmd == "tripwires":
        import plan_steps as ps
        rows = [bench(data["records"], data["benchmarks"], n, a.genre) for n in ents]
        ok = ps.upsert_section(a.calendar, "📊 Next Fest: cosa aspettarsi", f"📊 Next Fest: cosa aspettarsi (da case_studies.py, aggiornato il {today.isoformat()})",
                               tripwire_md(rows, a.fest, today), after_prefix="3. Tripwire")
        if a.out:
            write_json(dict(generated_on=today.isoformat(), fest=a.fest, rows=rows), a.out)
        log(("updated " if ok else "not found: ") + a.calendar)
        return
    text = to_md(data, a.genre, ents, today)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
