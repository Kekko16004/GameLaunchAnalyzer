#!/usr/bin/env python3
"""Genre benchmarks from public data: how the most reviewed games of a Steam tag are doing, by release year, price
and demo, and where YOUR numbers would sit.

Source: SteamSpy tag lists (the ~100 most reviewed games per tag) enriched with Steam store data (release date,
price, demo). Everything is public; nothing needs a login or a local database.

HONEST LIMIT, read it before quoting numbers: the lists contain the MOST REVIEWED games of the tag, so the
distributions describe the visible, successful tail, NOT the median game of the genre (most releases never appear).
"Reviews needed to enter the list" is therefore a bar for being visible, not an expectation. Reviews per year is
a proxy of sales, not sales. The tool gives orders of magnitude to reason with; it does not forecast.

Outputs: distributions (p25 / median / p75 / p90) of reviews, reviews per year, % positive, price, age; cohorts by
release year (how crowded the genre is and how recent releases perform); price bands; demo vs no demo;
Spearman price vs reviews per year; with --mine the percentile of your own values.

Examples:
  python genre_bench.py --tag Roguelike --tag Cooking --enrich 80 --md launch/_raw/genre_bench.md -o launch/_raw/genre_bench.json
  python genre_bench.py --tag "City Builder" --mine price=19.99 --mine reviews_per_year=500
"""
from __future__ import annotations

import argparse
import datetime
import statistics
from common import log, set_rate, write_json
import steam_discover as sd
from store_bench import parse_release, quantile, spearman, strength

NUMERIC = ["reviews_total", "reviews_per_year", "pct_positive", "price", "age_years"]
PRICE_BANDS = [("< 5", 0, 5), ("5-10", 5, 10), ("10-15", 10, 15), ("15-20", 15, 20), ("20+", 20, 10 ** 6)]


def dist(vals):
    v = [float(x) for x in vals if isinstance(x, (int, float))]
    return None if not v else dict(n=len(v), p25=round(quantile(v, .25), 2), median=round(quantile(v, .5), 2), p75=round(quantile(v, .75), 2), p90=round(quantile(v, .9), 2))


def add_derived(rows: list[dict], today: datetime.date) -> list[dict]:
    for r in rows:
        rel = parse_release(r.get("release_date"))
        r["release_year"] = rel.year if rel else None
        r["age_years"] = round(max((today - rel).days / 365.25, 0), 2) if rel and not r.get("coming_soon") else None
        r["reviews_per_year"] = round(r["reviews_total"] / max(r["age_years"], 0.25), 1) if r.get("age_years") and r.get("reviews_total") else None
        if r.get("price_base_cents") is not None:
            r["price"] = r["price_base_cents"] / 100
        elif r.get("is_free"):
            r["price"] = 0.0
        else:
            r["price"] = (float(r["price_cents"]) / 100) if str(r.get("price_cents") or "").isdigit() else None
        r["has_demo"] = 1 if r.get("has_demo") else 0
    return rows


def percentile_of(value: float, vals: list[float]) -> float:
    return round(100 * sum(1 for x in vals if x <= value) / len(vals), 1) if vals else 50.0


def analyse(rows: list[dict], mine: dict[str, float]) -> dict:
    usable = [r for r in rows if r.get("reviews_per_year")]
    res = dict(n_listed=len(rows), n_with_age=len(usable), distributions={k: dist([r.get(k) for r in rows]) for k in NUMERIC}, cohorts=[], price_bands=[], demo=[], mine=[])
    for y in sorted({r["release_year"] for r in usable if r["release_year"]}):
        g = [r for r in usable if r["release_year"] == y]
        res["cohorts"].append(dict(year=y, n=len(g), median_reviews=statistics.median(r["reviews_total"] for r in g), median_reviews_per_year=round(statistics.median(r["reviews_per_year"] for r in g), 1),
                                   median_pct_positive=round(statistics.median(r["pct_positive"] for r in g if r.get("pct_positive") is not None), 1) if any(r.get("pct_positive") is not None for r in g) else None))
    for label, lo, hi in PRICE_BANDS:
        g = [r for r in usable if r.get("price") is not None and lo <= r["price"] < hi]
        if g:
            res["price_bands"].append(dict(band=label, n=len(g), median_reviews_per_year=round(statistics.median(r["reviews_per_year"] for r in g), 1)))
    for flag, label in ((1, "con demo"), (0, "senza demo")):
        g = [r for r in usable if r["has_demo"] == flag]
        if g:
            res["demo"].append(dict(group=label, n=len(g), median_reviews_per_year=round(statistics.median(r["reviews_per_year"] for r in g), 1)))
    pp = [(r["price"], r["reviews_per_year"]) for r in usable if r.get("price") is not None]
    rho = spearman([p for p, _ in pp], [v for _, v in pp])
    res["price_vs_reviews"] = dict(rho=rho, n=len(pp), strength=strength(rho, len(pp)))
    all_reviews = sorted(r["reviews_total"] for r in rows if r.get("reviews_total"))
    res["visibility_bar"] = dict(min_reviews_in_list=all_reviews[0] if all_reviews else None, p25_reviews=res["distributions"]["reviews_total"] and res["distributions"]["reviews_total"]["p25"])
    for key, value in mine.items():
        vals = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
        d = dist(vals)
        res["mine"].append(dict(feature=key, value=value, percentile=percentile_of(value, vals), median=d and d["median"], p75=d and d["p75"], n=len(vals)))
    return res


def md(res: dict, tags: list[str], today: str) -> str:
    L = ["# Benchmark di genere da dati pubblici (calcolato da `genre_bench.py`)", "",
         f"Tag: {', '.join(tags)}. {res['n_listed']} giochi tra i più recensiti (SteamSpy), {res['n_with_age']} con data di uscita; letti il {today}. "
         "**Questi giochi sono la coda alta del genere (i più recensiti), non il gioco mediano**: le cifre dicono cosa serve per essere visibili, non cosa aspettarsi. "
         "Recensioni per anno sono un proxy delle vendite, non vendite.", "",
         "## Distribuzioni", "", "| Metrica | n | p25 | mediana | p75 | p90 |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {d['n']} | {d['p25']} | {d['median']} | {d['p75']} | {d['p90']} |" for k, d in res["distributions"].items() if d]
    if res["cohorts"]:
        L += ["", "## Per anno di uscita (quanto è affollato e come vanno le uscite recenti)", "", "| Anno | Giochi in lista | Mediana recensioni | Mediana recensioni/anno | Mediana % positive |", "|---|---|---|---|---|"]
        L += [f"| {c['year']} | {c['n']} | {c['median_reviews']:.0f} | {c['median_reviews_per_year']} | {c['median_pct_positive']} |" for c in res["cohorts"]]
    if res["price_bands"]:
        L += ["", "## Per fascia di prezzo", "", "| Prezzo | Giochi | Mediana recensioni/anno |", "|---|---|---|"]
        L += [f"| {b['band']} | {b['n']} | {b['median_reviews_per_year']} |" for b in res["price_bands"]]
        pv = res["price_vs_reviews"]
        L += ["", f"Correlazione di rango prezzo / recensioni per anno: ρ = {pv['rho']} ({pv['strength']}, n = {pv['n']}). Nessuna causalità: i giochi più costosi sono spesso di team più grandi."]
    if res["demo"]:
        L += ["", "## Demo", "", "| Gruppo | Giochi | Mediana recensioni/anno |", "|---|---|---|"] + [f"| {d['group']} | {d['n']} | {d['median_reviews_per_year']} |" for d in res["demo"]]
    vb = res["visibility_bar"]
    L += ["", f"## Soglia di visibilità", "", f"Per comparire tra i più recensiti del tag servono almeno {vb['min_reviews_in_list']} recensioni; il quartile basso della lista è a {vb['p25_reviews']}."]
    if res["mine"]:
        L += ["", "## I tuoi numeri nella distribuzione", "", "| Metrica | Tuo valore | Percentile | Mediana | p75 | n |", "|---|---|---|---|---|---|"]
        L += [f"| {m['feature']} | {m['value']} | {m['percentile']} | {m['median']} | {m['p75']} | {m['n']} |" for m in res["mine"]]
    L += ["", "_Correlazione non è causalità. Cita sempre n, tag e data di lettura (**[FATTO]** con questi limiti)._"]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tag", action="append", required=True, help="Steam tag (repeatable), case-sensitive on SteamSpy, e.g. Roguelike")
    ap.add_argument("--require-all", action="store_true"); ap.add_argument("--exact-tags", action="store_true", help="use tag names exactly as typed"); ap.add_argument("--no-validate-tags", action="store_true"); ap.add_argument("--min-reviews", type=int, default=50)
    ap.add_argument("--top", type=int, default=100, help="games kept after filters (default 100)")
    ap.add_argument("--enrich", type=int, default=80, help="games enriched with release date, price, demo (1 request each; default 80)")
    ap.add_argument("--mine", action="append", help="key=value of YOUR game: reviews_total, reviews_per_year, price, pct_positive")
    ap.add_argument("--cc", default="us"); ap.add_argument("--lang", default="english"); ap.add_argument("--rate", type=float, default=1.2)
    ap.add_argument("--md"); ap.add_argument("-o", "--out")
    a = ap.parse_args()
    set_rate(a.rate)
    rows = sd.candidates(a.tag, a.require_all, a.min_reviews, None, a.top, variants=not a.exact_tags, validate=not a.no_validate_tags)
    for i, r in enumerate(rows[:a.enrich], 1):
        sd.enrich(r, a.cc, a.lang)
        if i % 20 == 0:
            log(f"enriched {i}/{min(a.enrich, len(rows))}")
    for r in rows:
        r["matched_tags"] = "; ".join(r["matched_tags"])
    today = datetime.date.today()
    rows = add_derived(rows, today)
    mine = {}
    for kv in a.mine or []:
        k, _, v = kv.partition("=")
        mine[k] = float(v)
    res = analyse(rows, mine)
    text = md(res, a.tag, today.isoformat())
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if a.out:
        write_json(dict(tags=a.tag, read_on=today.isoformat(), analysis=res, games=rows), a.out)


if __name__ == "__main__":
    main()
