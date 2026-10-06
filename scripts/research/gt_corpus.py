#!/usr/bin/env python3
"""Read a GamesTracker database (SQLite, READ-ONLY) and turn it into real benchmarks for a launch strategy.

GamesTracker (github.com/Kekko16004/GamesTracker) runs a collector that stores, for hundreds of recently released
games, append-only snapshots of reviews, players and owner estimates, store-page signals, and a timeline of
social posts. This tool never writes to that database and never needs the network: point it at the file that
lives on YOUR machine (default `data/gamestracker.db` of the GamesTracker folder).

  info      what the corpus contains (tables, games, snapshot range, top tags) and whether it is big enough
  genre     benchmarks for a genre/tag: distributions of reviews at +1/+7/+30/+90 days, % positive, price, page
            signals, demo share, social posts before launch; best quartile vs the rest; Spearman correlations;
            --mine key=value places YOUR numbers in the distribution (percentile)
  comps     per-game table (same fields) for given app ids or a tag, ready for launch/_raw
  marketing social-post timeline relative to release (posts per window, platform mix) for best vs rest
  window    tracked games releasing in the next N days for a tag (competition in your launch window)
  project   your own project saved in GamesTracker (concept, simulator result, discount plan)

DB path: --db, or env GAMESTRACKER_DB, or ./data/gamestracker.db, or ../GamesTracker/data/gamestracker.db.

Honest limits: GamesTracker filters out "trash" with its quality score (discarded games are excluded by default),
so benchmarks describe decently made games, not the whole market; its owner estimates come from SteamSpy
(ranges); wishlists are not public and are NOT in the corpus; social metrics co-occur with growth, they do not
prove it caused it.

Examples:
  python gt_corpus.py info --db C:/tools/GamesTracker/data/gamestracker.db
  python gt_corpus.py genre --tag Roguelike --tag "Deck Building" --released-after 2024-01-01 --mine price=14.99 --mine screenshot_count=8 --md launch/_raw/gt_genre.md
  python gt_corpus.py window --tag Roguelike --days 365
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import sqlite3
import statistics
from common import log, write_json
from store_bench import quantile, spearman, strength

WINDOWS = {"reviews_d1": (1, 1), "reviews_d7": (7, 3), "reviews_d30": (30, 10), "reviews_d90": (90, 20)}
NUMERIC = ["reviews_d7", "reviews_d30", "reviews_d90", "pct_positive_d30", "price", "screenshot_count", "description_length",
           "has_trailer", "has_demo", "posts_pre30", "posts_total", "first_post_days_before", "peak_players", "quality_score"]
PAGE_AND_MARKETING = ["price", "screenshot_count", "description_length", "has_trailer", "has_demo", "posts_pre30", "posts_total", "first_post_days_before"]


# ----------------------------------------------------------------------------- db access
def find_db(path: str | None) -> str:
    for c in [path, os.environ.get("GAMESTRACKER_DB"), "data/gamestracker.db", "../GamesTracker/data/gamestracker.db"]:
        if c and os.path.exists(c):
            return c
    raise SystemExit("GamesTracker database not found: pass --db PATH (the file data/gamestracker.db inside the GamesTracker folder) or set GAMESTRACKER_DB")


class DB(sqlite3.Connection):
    """sqlite3 connection that can carry the set of table names."""
    tables: set


def connect(path: str) -> DB:
    con = sqlite3.connect(pathlib.Path(path).resolve().as_uri() + "?mode=ro", uri=True, factory=DB)  # read-only: cannot modify the tracker
    con.row_factory = sqlite3.Row
    have = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    missing = {"games", "game_snapshots"} - have
    if missing:
        raise SystemExit(f"{path} does not look like a GamesTracker database (missing tables: {sorted(missing)})")
    con.tables = have
    return con


def parse_dt(v):
    if not v:
        return None
    s = str(v).replace("T", " ").replace("Z", "")
    try:
        return dt.datetime.fromisoformat(s.split("+")[0].strip())
    except ValueError:
        return None


def jl(v):
    try:
        x = json.loads(v) if isinstance(v, str) else v
        return x if isinstance(x, (list, dict)) else []
    except (TypeError, ValueError):
        return []


def norm(s) -> str:
    return str(s or "").strip().lower()


# ----------------------------------------------------------------------------- corpus
def load_games(con, tags: list[str], require_all: bool, after: str | None, min_quality: float | None, include_discarded: bool,
               appids: list[str] | None = None) -> list[dict]:
    games = []
    for g in con.execute("select * from games"):
        g = dict(g)
        if norm(g.get("platform")) != "steam" or (g.get("discarded") and not include_discarded):
            continue
        if appids and str(g["external_id"]) not in appids:
            continue
        labels = {norm(x) for x in jl(g.get("genres")) + jl(g.get("tags"))}
        want = [norm(t) for t in tags]
        if want and not ((all(w in labels for w in want)) if require_all else any(w in labels for w in want)):
            continue
        rel = (parse_dt(g.get("release_date")) or dt.datetime(1970, 1, 1)).date() if g.get("release_date") else None
        if after and (not rel or rel < dt.date.fromisoformat(after)):
            continue
        if min_quality is not None and (g.get("quality_score") or 0) < min_quality:
            continue
        g["_release"], g["_labels"] = rel, sorted(labels)
        games.append(g)
    return games


def snapshots_of(con, game_id: int) -> list[dict]:
    out = []
    for s in con.execute("select * from game_snapshots where game_id=? order by captured_at", (game_id,)):
        s = dict(s)
        s["dt"], s["extra_d"] = parse_dt(s["captured_at"]), (jl(s.get("extra")) if s.get("extra") else {})
        if s["dt"]:
            out.append(s)
    return out


def at_window(snaps, release, target, tol, key="total_reviews"):
    best = None
    for s in snaps:
        if s.get(key) is None or release is None:
            continue
        diff = abs((s["dt"].date() - release).days - target)
        if diff <= tol and (best is None or diff < best[0]):
            best = (diff, s)
    return best[1] if best else None


def enrich(con, g: dict) -> dict:
    snaps, rel = snapshots_of(con, g["id"]), g["_release"]
    row = dict(appid=g["external_id"], title=g["title"], release_date=str(rel) if rel else None, price=g.get("price"), tags=g["_labels"],
               has_demo=1 if g.get("has_demo") else 0, quality_score=g.get("quality_score"), store_url=g.get("store_url"))
    for key, (target, tol) in WINDOWS.items():
        s = at_window(snaps, rel, target, tol)
        row[key] = s["total_reviews"] if s else None
        if key == "reviews_d30":
            row["pct_positive_d30"] = round(100 * s["total_positive"] / s["total_reviews"], 1) if s and s["total_reviews"] and s.get("total_positive") is not None else None
    players = [s["current_players"] for s in snaps if s.get("current_players") is not None]
    row["peak_players"] = max(players) if players else None
    owners = [s["steamspy_estimate"] for s in snaps if s.get("steamspy_estimate")]
    row["owners_estimate_latest"] = owners[-1] if owners else None
    extra = next((s["extra_d"] for s in reversed(snaps) if isinstance(s["extra_d"], dict) and "screenshot_count" in s["extra_d"]), {})
    row.update(screenshot_count=extra.get("screenshot_count"), description_length=extra.get("description_length"),
               has_trailer=(1 if extra.get("has_trailer") else 0) if extra else None)
    posts = []
    if "social_posts" in con.tables:
        posts = [dict(p) for p in con.execute("select platform, posted_at, views, likes from social_posts where game_id=?", (g["id"],))]
    rel_days = []
    for p in posts:
        d = parse_dt(p["posted_at"])
        if d and rel:
            rel_days.append(((d.date() - rel).days, norm(p["platform"]), p.get("views") or 0))
    row["posts_total"] = len(posts) if "social_posts" in con.tables else None
    row["posts_pre30"] = sum(1 for d, _, _ in rel_days if -30 <= d < 0) if rel_days or posts else (0 if "social_posts" in con.tables else None)
    row["first_post_days_before"] = max((-d for d, _, _ in rel_days if d < 0), default=None)
    row["_post_days"] = rel_days
    return row


def build_rows(con, a, appids=None) -> list[dict]:
    games = load_games(con, a.tag or [], getattr(a, "all", False), getattr(a, "released_after", None), getattr(a, "min_quality", None),
                       getattr(a, "include_discarded", False), appids)
    today = dt.date.today()
    return [enrich(con, g) for g in games if not (g["_release"] and g["_release"] > today)]  # unreleased games have no outcomes


# ----------------------------------------------------------------------------- analysis
def dist(vals):
    v = [float(x) for x in vals if isinstance(x, (int, float))]
    return None if not v else dict(n=len(v), p25=round(quantile(v, .25), 2), median=round(quantile(v, .5), 2), p75=round(quantile(v, .75), 2), p90=round(quantile(v, .9), 2))


def percentile_of(value: float, vals: list[float]) -> float:
    return round(100 * sum(1 for x in vals if x <= value) / len(vals), 1) if vals else 50.0


def genre_report(rows: list[dict], mine: dict[str, float]) -> dict:
    res = dict(n_games=len(rows), distributions={k: dist([r.get(k) for r in rows]) for k in NUMERIC}, note="")
    scored = [r for r in rows if r.get("reviews_d30")]
    if len(scored) < 8:
        res["note"] = f"Solo {len(scored)} giochi con recensioni a +30 giorni: statistiche poco affidabili."
    ordered = sorted(scored, key=lambda r: -r["reviews_d30"])
    k = max(1, len(ordered) // 4)
    top, rest = ordered[:k], ordered[k:]
    res["best_quartile"] = dict(size=len(top), games=[r["title"] for r in top][:15])
    res["best_vs_rest"] = []
    for f in PAGE_AND_MARKETING + ["pct_positive_d30"]:
        tv, rv = [r[f] for r in top if isinstance(r.get(f), (int, float))], [r[f] for r in rest if isinstance(r.get(f), (int, float))]
        pairs = [(float(r[f]), math.log(r["reviews_d30"])) for r in scored if isinstance(r.get(f), (int, float)) and r["reviews_d30"] > 0]
        rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
        res["best_vs_rest"].append(dict(feature=f, median_best=round(statistics.median(tv), 2) if tv else None, median_rest=round(statistics.median(rv), 2) if rv else None,
                                        rho_log_reviews_d30=rho, strength=strength(rho, len(pairs)), n=len(pairs)))
    res["mine"] = []
    for key, value in mine.items():
        vals = [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]
        d = dist(vals)
        res["mine"].append(dict(feature=key, value=value, percentile=percentile_of(value, vals), median=d and d["median"], p75=d and d["p75"], n=len(vals)))
    return res


def genre_md(res: dict, meta: dict) -> str:
    L = [f"# Benchmark reali dal corpus GamesTracker", "",
         f"**{res['n_games']} giochi Steam** (filtri: {meta['filters']}), snapshot dal {meta['first_snapshot']} al {meta['last_snapshot']}, letti il {meta['read_on']}. "
         "Fonte: database GamesTracker dell'utente, sola lettura. Il collector scarta i giochi di bassa qualità: i valori descrivono giochi decenti, non tutto il mercato. "
         "Wishlist non pubbliche, quindi assenti.", ""]
    if res["note"]:
        L += [f"**{res['note']}**", ""]
    L += ["## Distribuzioni", "", "| Metrica | n | p25 | mediana | p75 | p90 |", "|---|---|---|---|---|---|"]
    L += [f"| {k} | {d['n']} | {d['p25']} | {d['median']} | {d['p75']} | {d['p90']} |" for k, d in res["distributions"].items() if d]
    L += ["", f"## Quartile migliore (per recensioni a +30 giorni) contro il resto", "", f"Migliori ({res['best_quartile']['size']}): {', '.join(res['best_quartile']['games'][:10])}", "",
          "| Caratteristica | Mediana migliori | Mediana resto | ρ con log(recensioni +30g) | Forza | n |", "|---|---|---|---|---|---|"]
    L += [f"| {r['feature']} | {r['median_best']} | {r['median_rest']} | {r['rho_log_reviews_d30']} | {r['strength']} | {r['n']} |" for r in res["best_vs_rest"]]
    if res["mine"]:
        L += ["", "## Il tuo gioco nella distribuzione", "", "| Metrica | Tuo valore | Percentile | Mediana | p75 | n |", "|---|---|---|---|---|---|"]
        L += [f"| {m['feature']} | {m['value']} | {m['percentile']} | {m['median']} | {m['p75']} | {m['n']} |" for m in res["mine"]]
    L += ["", "_Correlazione non è causalità: budget, genere, tempismo e fortuna confondono. Usa mediane e quartili come punto di partenza, e dichiara n e filtri._"]
    return "\n".join(L) + "\n"


BUCKETS = [("-90..-61", -90, -61), ("-60..-31", -60, -31), ("-30..-8", -30, -8), ("-7..-1", -7, -1), ("0..+6", 0, 6), ("+7..+30", 7, 30)]


def marketing_report(rows: list[dict]) -> dict:
    scored = sorted([r for r in rows if r.get("reviews_d30")], key=lambda r: -r["reviews_d30"])
    k = max(1, len(scored) // 4)
    groups = dict(best=scored[:k], rest=scored[k:])
    out = dict(games=len(scored), groups={})
    for name, gs in groups.items():
        n = max(len(gs), 1)
        buckets = {b: sum(1 for r in gs for d, _, _ in r["_post_days"] if lo <= d <= hi) / n for b, lo, hi in BUCKETS}
        plat = {}
        for r in gs:
            for _, p, _ in r["_post_days"]:
                plat[p] = plat.get(p, 0) + 1
        tot = sum(plat.values()) or 1
        out["groups"][name] = dict(games=len(gs), posts_per_game_by_window=buckets, platform_share={p: round(100 * c / tot, 1) for p, c in sorted(plat.items(), key=lambda kv: -kv[1])},
                                   median_views_per_post=statistics.median([v for r in gs for _, _, v in r["_post_days"] if v]) if any(v for r in gs for _, _, v in r["_post_days"]) else None)
    return out


def marketing_md(m: dict) -> str:
    L = ["# Timeline di marketing relativa all'uscita (corpus GamesTracker)", "", f"{m['games']} giochi con recensioni a +30 giorni; migliori = quartile alto per recensioni a +30 giorni. Solo co-occorrenza: i post non provano di aver causato la crescita.", "",
         "| Finestra (giorni dall'uscita) | Post/gioco: migliori | Post/gioco: resto |", "|---|---|---|"]
    b, r = m["groups"].get("best"), m["groups"].get("rest")
    for name, _, _ in BUCKETS:
        L.append(f"| {name} | {round(b['posts_per_game_by_window'][name], 2) if b else '-'} | {round(r['posts_per_game_by_window'][name], 2) if r else '-'} |")
    for g in ("best", "rest"):
        if m["groups"].get(g):
            L += ["", f"Mix di piattaforme ({g}): " + ", ".join(f"{p} {s}%" for p, s in m["groups"][g]["platform_share"].items()) + f" | mediana views per post: {m['groups'][g]['median_views_per_post']}"]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- commands
def meta_of(con, a, rows) -> dict:
    r = con.execute("select min(captured_at) a, max(captured_at) b from game_snapshots").fetchone()
    f = [f"tag {', '.join(a.tag)}" if getattr(a, "tag", None) else "tutti i tag"]
    if getattr(a, "released_after", None):
        f.append(f"uscito dopo {a.released_after}")
    if getattr(a, "min_quality", None) is not None:
        f.append(f"quality score >= {a.min_quality}")
    f.append("inclusi scartati" if getattr(a, "include_discarded", False) else "scartati esclusi")
    return dict(filters="; ".join(f), first_snapshot=str(r["a"])[:10], last_snapshot=str(r["b"])[:10], read_on=dt.date.today().isoformat())


def emit(text: str, obj, a):
    if getattr(a, "md", None):
        open(a.md, "w", encoding="utf-8", newline="\n").write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if getattr(a, "out", None):
        write_json(obj, a.out)


def cmd_info(a):
    con = connect(find_db(a.db))
    cnt = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in sorted(con.tables) if not t.startswith("sqlite_") and t not in ("apscheduler_jobs",)}
    games = [dict(g) for g in con.execute("select id, platform, release_date, discarded, genres, tags from games")]
    steam = [g for g in games if norm(g["platform"]) == "steam"]
    with_m1 = con.execute("select count(distinct game_id) from game_snapshots where lower(snapshot_type) = 'm1'").fetchone()[0]
    tags: dict[str, int] = {}
    for g in steam:
        for t in set(jl(g["tags"]) + jl(g["genres"])):
            tags[t] = tags.get(t, 0) + 1
    r = con.execute("select min(captured_at) a, max(captured_at) b from game_snapshots").fetchone()
    L = ["# Corpus GamesTracker", "", f"Database: {find_db(a.db)}", f"Righe per tabella: {cnt}",
         f"Giochi Steam: {len(steam)} (scartati dal quality filter: {sum(1 for g in steam if g['discarded'])}); con snapshot a +1 mese: {with_m1}",
         f"Snapshot dal {str(r['a'])[:10]} al {str(r['b'])[:10]}", "Tag più frequenti: " + ", ".join(f"{t} ({n})" for t, n in sorted(tags.items(), key=lambda kv: -kv[1])[:25]), ""]
    L.append("Corpus adeguato per benchmark di genere (>= 30 giochi con dati a +30 giorni nel tag)." if with_m1 >= 30 else
             f"ATTENZIONE: solo {with_m1} giochi con snapshot a +1 mese: lascia girare il collector più a lungo prima di fidarti dei percentili.")
    print("\n".join(L))


def cmd_genre(a):
    con = connect(find_db(a.db))
    rows = build_rows(con, a)
    mine = {}
    for kv in a.mine or []:
        k, _, v = kv.partition("=")
        mine[k] = float(v)
    res = genre_report(rows, mine)
    meta = meta_of(con, a, rows)
    emit(genre_md(res, meta), dict(meta=meta, **res), a)


def cmd_comps(a):
    con = connect(find_db(a.db))
    rows = build_rows(con, a, [str(x) for x in a.appids] if a.appids else None)
    rows.sort(key=lambda r: -(r.get("reviews_d30") or 0))
    rows = rows[:a.limit]
    for r in rows:
        r.pop("_post_days", None)
    write_json(rows, a.out or "-")


def cmd_marketing(a):
    con = connect(find_db(a.db))
    m = marketing_report(build_rows(con, a))
    emit(marketing_md(m), m, a)


def cmd_window(a):
    con = connect(find_db(a.db))
    today = dt.date.today()
    games = [g for g in load_games(con, a.tag or [], False, None, None, True) if g["_release"] and today <= g["_release"] <= today + dt.timedelta(days=a.days)]
    games.sort(key=lambda g: g["_release"])
    rows = [dict(release_date=str(g["_release"]), title=g["title"], price=g.get("price"), tags=g["_labels"][:8], url=g.get("store_url")) for g in games]
    L = [f"# Uscite tracciate nei prossimi {a.days} giorni ({', '.join(a.tag or ['tutti i tag'])})", ""]
    L += [f"- {r['release_date']}: {r['title']} ({r['price']}) {r['url'] or ''}" for r in rows] or ["Nessuna: il collector scopre soprattutto uscite recenti e potrebbe non coprire il futuro. Controlla a mano le uscite annunciate."]
    emit("\n".join(L) + "\n", rows, a)


def cmd_project(a):
    con = connect(find_db(a.db))
    if "projects" not in con.tables:
        raise SystemExit("this GamesTracker database has no `projects` table (My Projects feature not used)")
    rows = [dict(r) for r in con.execute("select * from projects")]
    if a.name:
        rows = [r for r in rows if a.name.lower() in (r["name"] or "").lower()]
    for r in rows:
        for k in ("concept_data", "simulator_data", "discount_plan"):
            r[k] = jl(r.get(k))
    L = ["# Progetti in GamesTracker", ""]
    for r in rows:
        L += [f"## {r['name']} (genere: {r.get('genre')})", r.get("description") or "", f"- concept: chiavi {sorted(r['concept_data'])[:12]}",
              f"- simulatore qualità: {json.dumps(r['simulator_data'], ensure_ascii=False)[:600]}", f"- piano sconti: {json.dumps(r['discount_plan'], ensure_ascii=False)[:600]}", ""]
    emit("\n".join(L) if rows else "Nessun progetto trovato.\n", rows, a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="path of gamestracker.db (read-only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def filt(p):
        p.add_argument("--tag", action="append", help="genre or tag (repeatable; any of them unless --all)")
        p.add_argument("--all", action="store_true", help="game must have every --tag")
        p.add_argument("--released-after", help="YYYY-MM-DD"); p.add_argument("--min-quality", type=float)
        p.add_argument("--include-discarded", action="store_true", help="include games discarded by GamesTracker's quality filter")

    s = sub.add_parser("info"); s.set_defaults(fn=cmd_info)
    s = sub.add_parser("genre"); filt(s); s.add_argument("--mine", action="append", help="key=value of YOUR game, e.g. price=14.99 screenshot_count=8")
    s.add_argument("--md"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_genre)
    s = sub.add_parser("comps"); filt(s); s.add_argument("--appids", nargs="*"); s.add_argument("--limit", type=int, default=40); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_comps)
    s = sub.add_parser("marketing"); filt(s); s.add_argument("--md"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_marketing)
    s = sub.add_parser("window"); s.add_argument("--tag", action="append"); s.add_argument("--days", type=int, default=365); s.add_argument("--md"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_window)
    s = sub.add_parser("project"); s.add_argument("--name"); s.add_argument("--md"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_project)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
