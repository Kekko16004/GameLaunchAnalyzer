#!/usr/bin/env python3
"""Large real-review corpus: what players punish and reward, in YOUR comparables and in the wider genre,
and what they say about the features YOUR game has.

Two groups of games, so you can see what is specific to your closest comparables and what is genre-wide:
  comps  : the closest comparables (--comps APPID...)
  genre  : other games of the same type (--genre-tag TAG... via SteamSpy tag lists, or --genre-ids / a
           steam_discover.py JSON/CSV). Their reviews often apply to your game too.
Per game it samples negative reviews (what is punished) and positive reviews (what is rewarded) through the public
Steam reviews endpoint (see steam_reviews.py), the SAME number of reviews per game so mega-hits do not dominate.

Outputs (all from real reviews, each with game, date, playtime and URL):
  * complaint themes and praise themes per group: macro-average share across games and breadth (in how many games
    the theme is at least 10% of the sample)
  * with --my-features: for every feature of your game (a regex per label) how often it is mentioned in negative
    vs positive reviews, a verdict (rewarded / punished / divisive / rarely discussed) and the most helpful
    reviews that mention it, to read and paraphrase

Fetched reviews are cached per game in --cache-dir (resume after an interruption; --refresh to refetch).
Keyword themes are English-only heuristics: read the example reviews before concluding anything.

Examples:
  python review_corpus.py --comps 1599600 728880 --genre-tag Roguelike Cooking --max-genre-games 20 \\
      --my-features my_features.json -o launch/_raw/corpus.json --md launch/_raw/corpus.md
  python review_corpus.py --comps 1599600 --genre-ids discover.json --neg-per-game 100 --pos-per-game 60

my_features.json:  {"cooking": "cook|recipe|kitchen|chef", "co-op": "co-?op|with friends", "permadeath": ["permadeath", "perma death"]}
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import statistics
from collections import defaultdict
from common import load_json, log, read_list, set_rate, write_csv, write_json
import steam_reviews as sr
import steam_discover as sd

BREADTH_MIN_PCT = 10.0   # a theme "appears" in a game when it is at least this % of the game's sample
MIN_SAMPLE = 20          # games with fewer sampled reviews are left out of the macro averages


def compile_features(path: str | None) -> dict:
    if not path:
        return {}
    out = {}
    for label, rx in load_json(path).items():
        out[label] = re.compile("|".join(re.escape(x) for x in rx) if isinstance(rx, list) else rx, re.I)
    return out


def cached_reviews(appid: int, kind: str, a, cache_dir: str) -> list[dict]:
    path = os.path.join(cache_dir, f"{appid}_{kind}.json")
    if os.path.exists(path) and not a.refresh:
        return load_json(path)
    opts = sr.default_opts(type=kind, limit=a.neg_per_game if kind == "negative" else a.pos_per_game, language=a.language,
                           within_days=a.within_days, sort=a.sort, max_pages=a.max_pages)
    revs = sr.fetch_reviews(appid, opts, {})["reviews"]
    os.makedirs(cache_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(revs, f, ensure_ascii=False)
    return revs


def tag_reviews(revs: list[dict], themes: dict, features: dict) -> None:
    for r in revs:
        r["themes"] = [k for k, rx in themes.items() if rx.search(r["text"])]
        r["features"] = [k for k, rx in features.items() if rx.search(r["text"])]


def aggregate_group(games: list[dict], kind: str, theme_names: list[str]) -> list[dict]:
    usable = [g for g in games if len(g[kind]) >= MIN_SAMPLE]
    rows = []
    for t in theme_names:
        per_game = [100 * sum(1 for r in g[kind] if t in r["themes"]) / len(g[kind]) for g in usable]
        tot = sum(len(g[kind]) for g in usable)
        cnt = sum(1 for g in usable for r in g[kind] if t in r["themes"])
        if not per_game or not cnt:
            continue
        rows.append(dict(theme=t, macro_pct=round(statistics.mean(per_game), 1), pooled_pct=round(100 * cnt / tot, 1),
                         breadth=sum(1 for p in per_game if p >= BREADTH_MIN_PCT), games=len(usable), reviews_with_theme=cnt))
    rows.sort(key=lambda r: (-r["macro_pct"], -r["breadth"]))
    return rows


def feature_stats(games: list[dict], features: dict, top_n: int = 8) -> list[dict]:
    out = []
    for label in features:
        row = dict(feature=label)
        for kind, key in (("negative", "neg"), ("positive", "pos")):
            allr = [(g, r) for g in games for r in g[kind]]
            hit = [(g, r) for g, r in allr if label in r["features"]]
            row[f"{key}_n"], row[f"{key}_share"] = len(hit), round(100 * len(hit) / len(allr), 1) if allr else None
            hit.sort(key=lambda gr: -(gr[1].get("votes_up") or 0))
            row[f"{key}_examples"] = [dict(game=g["name"], group=g["group"], date=r["date"], hours=r["playtime_at_review_h"],
                                           votes_up=r["votes_up"], url=r["url"], excerpt=r["text"][:300]) for g, r in hit[:top_n]]
        n, p = row["neg_share"] or 0, row["pos_share"] or 0
        row["verdict"] = ("rarely discussed" if max(n, p) < 3 else "rewarded" if p >= 1.5 * n else "punished" if n >= 1.5 * p else "divisive")
        out.append(row)
    return out


def build(games: list[dict], features: dict) -> dict:
    res = dict(groups={})
    neg_t, pos_t = sorted({t for g in games for r in g["negative"] for t in r["themes"]}), sorted({t for g in games for r in g["positive"] for t in r["themes"]})
    for name in ("comps", "genre", "all"):
        gs = games if name == "all" else [g for g in games if g["group"] == name]
        if gs:
            res["groups"][name] = dict(games=len(gs), reviews_negative=sum(len(g["negative"]) for g in gs), reviews_positive=sum(len(g["positive"]) for g in gs),
                                       punished=aggregate_group(gs, "negative", neg_t), rewarded=aggregate_group(gs, "positive", pos_t))
    if features:
        res["features"] = {name: feature_stats([g for g in games if name == "all" or g["group"] == name], features)
                           for name in ("all", "comps", "genre") if any(name == "all" or g["group"] == name for g in games)}
    return res


def md(res: dict, games: list[dict], today: str, features: dict) -> str:
    n_rev = sum(len(g["negative"]) + len(g["positive"]) for g in games)
    L = ["# Corpus di recensioni reali (calcolato da `review_corpus.py`)", "",
         f"**{n_rev} recensioni Steam reali da {len(games)} giochi** ({sum(g['group'] == 'comps' for g in games)} comparabili, "
         f"{sum(g['group'] == 'genre' for g in games)} dello stesso genere), raccolte il {today}. Stesso numero di recensioni per gioco, "
         f"percentuali medie tra i giochi (macro) così nessun mega-hit domina. Temi per parola chiave in inglese: euristica da verificare leggendo gli esempi.", ""]
    for key, title in (("punished", "Cosa il pubblico punisce (recensioni negative)"), ("rewarded", "Cosa il pubblico premia (recensioni positive)")):
        L += [f"## {title}", "", "| Tema | Comparabili: % media | in quanti giochi | Genere: % media | in quanti giochi |", "|---|---|---|---|---|"]
        c = {r["theme"]: r for r in res["groups"].get("comps", {}).get(key, [])}
        gn = {r["theme"]: r for r in res["groups"].get("genre", {}).get(key, [])}
        for t in sorted(set(c) | set(gn), key=lambda t: -max((c.get(t) or {}).get("macro_pct", 0), (gn.get(t) or {}).get("macro_pct", 0)))[:12]:
            L.append(f"| {t} | {(c.get(t) or {}).get('macro_pct', '-')} | {(c.get(t) or {}).get('breadth', '-')}/{res['groups'].get('comps', {}).get('games', '-')} | "
                     f"{(gn.get(t) or {}).get('macro_pct', '-')} | {(gn.get(t) or {}).get('breadth', '-')}/{res['groups'].get('genre', {}).get('games', '-')} |")
        L.append("")
    if features:
        L += ["## Le caratteristiche del tuo gioco nelle recensioni", "", "| Caratteristica | % nelle negative | % nelle positive | Esito | Recensioni che la citano (neg / pos) |", "|---|---|---|---|---|"]
        L += [f"| {f['feature']} | {f['neg_share']} | {f['pos_share']} | {f['verdict']} | {f['neg_n']} / {f['pos_n']} |" for f in res["features"]["all"]]
        L += ["", "Esempi (più utili) in `corpus.json` → `features`: leggili e parafrasali, non incollarli nei deliverable.", ""]
    L += ["## Limiti", "", "- Campioni non casuali (ordine di utilità o recenti, vedi `--sort`): sovrarappresentano i problemi più discussi.",
          "- Parole chiave in inglese; recensioni in altre lingue non sono contate (a meno di aggiungere pattern).",
          "- I giochi del genere sono scelti dalle liste per tag di SteamSpy (circa i primi 100 per recensioni): bias verso i più noti.",
          "- Correlazioni e frequenze descrivono il pubblico di quei giochi, non garantiscono che valgano per il tuo."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comps", nargs="*", default=[], help="app ids of the closest comparables")
    ap.add_argument("--genre-tag", nargs="*", help="Steam tags: other games of the same type (SteamSpy)")
    ap.add_argument("--genre-ids", nargs="*", default=[], help="app ids, or a .json/.csv/.txt from steam_discover.py")
    ap.add_argument("--max-genre-games", type=int, default=20)
    ap.add_argument("--min-reviews", type=int, default=300, help="genre games need at least this many Steam reviews (default 300)")
    ap.add_argument("--max-reviews", type=int, help="skip genre games with more reviews than this (skip mega-hits)")
    ap.add_argument("--neg-per-game", type=int, default=150); ap.add_argument("--pos-per-game", type=int, default=100)
    ap.add_argument("--within-days", type=int, default=730, help="only reviews of the last N days (default 730)")
    ap.add_argument("--language", default="english"); ap.add_argument("--sort", default="helpful", choices=["helpful", "recent"])
    ap.add_argument("--max-pages", type=int, default=15)
    ap.add_argument("--my-features", help="JSON {label: regex or [keywords]} of the features of YOUR game")
    ap.add_argument("--cache-dir", default="launch/_raw/corpus"); ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--rate", type=float, default=1.2)
    ap.add_argument("-o", "--out", default="-"); ap.add_argument("--md"); ap.add_argument("--csv", help="CSV of the reviews that mention your features")
    a = ap.parse_args()
    set_rate(a.rate)

    comp_ids = [int(x) for x in a.comps]
    genre_rows = []
    if a.genre_tag:
        genre_rows += sd.candidates(a.genre_tag, min_reviews=a.min_reviews, max_reviews=a.max_reviews, top=a.max_genre_games + len(comp_ids))
    for item in a.genre_ids:
        if os.path.exists(item):
            data = load_json(item) if item.endswith(".json") else None
            genre_rows += [dict(appid=int(r["appid"]), name=r.get("name")) for r in data] if data else [dict(appid=int(x)) for x in read_list(None, item)]
        else:
            genre_rows.append(dict(appid=int(item)))
    seen, plan = set(comp_ids), [dict(appid=i, group="comps", name=None) for i in comp_ids]
    for r in genre_rows:
        if r["appid"] not in seen and sum(p["group"] == "genre" for p in plan) < a.max_genre_games:
            seen.add(r["appid"])
            plan.append(dict(appid=r["appid"], group="genre", name=r.get("name")))
    if not plan:
        ap.error("no games: give --comps and/or --genre-tag / --genre-ids")

    features = compile_features(a.my_features)
    themes = {**sr.compile_themes(None, "negative"), **sr.compile_themes(None, "positive")}
    games = []
    for i, p in enumerate(plan, 1):
        name = p["name"] or sr.game_name(p["appid"]) or str(p["appid"])
        g = dict(appid=p["appid"], name=name, group=p["group"], negative=cached_reviews(p["appid"], "negative", a, a.cache_dir),
                 positive=cached_reviews(p["appid"], "positive", a, a.cache_dir))
        for kind in ("negative", "positive"):
            tag_reviews(g[kind], sr.compile_themes(None, kind), features)
        games.append(g)
        log(f"[{i}/{len(plan)}] {p['group']:5} {name}: {len(g['negative'])} negative, {len(g['positive'])} positive")
    res = build(games, features)
    today = datetime.date.today().isoformat()
    res.update(generated=today, params={k: v for k, v in vars(a).items() if k not in ("out", "md", "csv")}, games=[
        dict(appid=g["appid"], name=g["name"], group=g["group"], negative=len(g["negative"]), positive=len(g["positive"])) for g in games])
    text = md(res, games, today, features)
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.md}")
    else:
        print(text)
    if a.out != "-":
        write_json(res, a.out)
    if a.csv and features:
        rows = [dict(game=g["name"], group=g["group"], sentiment=kind, date=r["date"], hours=r["playtime_at_review_h"], votes_up=r["votes_up"],
                     features="; ".join(r["features"]), url=r["url"]) for g in games for kind in ("negative", "positive") for r in g[kind] if r["features"]]
        write_csv(rows, a.csv)


if __name__ == "__main__":
    main()
