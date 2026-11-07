#!/usr/bin/env python3
"""Genre memory for the idea review: what the public of a genre punishes and rewards, merged across every review corpus already
computed (review_corpus.py -> launch/_raw/corpus*.json, in any project), so the next idea of the same genre starts from data.

The store lives in the user's folder (~/.game-launch-strategist/genre_patterns.json, or $GLS_HOME), never in the repository:
for each genre the runs merged (date, games, reviews, source file) and, for each review theme, the mean share of reviews that cite it
(average of the per-run macro %, weighted by games) and in how many runs it shows. A run is identified by file + generation date:
building twice does not count it twice.

  genre_patterns.py build   [--corpus launch/_raw/corpus.json ...] [--genre roguelite]   default: launch/_raw/corpus*.json;
                                                                                          genre = params.genre_tag of the corpus
  genre_patterns.py show    [--genre roguelite] [--json]
  genre_patterns.py suggest --genre roguelite [--top 4] [--json]   proposal candidates for gdd_review.json, each with its evidence
  genre_patterns.py self-test

The themes are keyword counts on English reviews (review_corpus.py): [FATTO] as frequencies, the suggestions are [OPINIONE].
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
import tempfile

try:
    import common
    user_dir = common.user_dir
except ImportError:  # pragma: no cover
    def user_dir(*parts):
        return os.path.join(os.environ.get("GLS_HOME") or os.path.join(os.path.expanduser("~"), ".game-launch-strategist"), *parts)
try:
    from theme_labels import label as theme_label
except ImportError:  # pragma: no cover
    def theme_label(k):
        return k

MIN_PCT = 3.0   # themes below this share are noise for a suggestion

# theme -> (scorecard area of gdd_review.py, what to propose). Punished themes: what to prevent; rewarded: what to lean on.
PUNISHED_HINT = {
    "repetitive_shallow": ("progressione", "più varietà tra una sessione e l'altra (eventi, modificatori, obiettivi diversi) prima di aggiungere contenuti uguali"),
    "onboarding_tutorial": ("prima_ora", "insegnare giocando nei primi minuti, una regola alla volta, senza muri di testo"),
    "difficulty_balance": ("loop", "curva di difficoltà dichiarata e regolabile; fortuna sempre compensabile con scelte"),
    "bugs_crashes": ("scope", "meno sistemi e più tempo di test: lo scope deve lasciare spazio alla stabilità"),
    "performance": ("scope", "budget di prestazioni fissato presto (Steam Deck incluso)"),
    "price_value_length": ("prezzo", "durata e prezzo coerenti con i comparabili; dire chiaramente quante ore offre"),
    "content_depth": ("progressione", "un contenuto finale solido (fine partita, sblocchi tardi) invece di tante cose a metà"),
    "ui_ux_controls": ("prima_ora", "controlli e menu provati presto con gente vera; rimappatura e controller dal primo giorno"),
    "multiplayer_netcode": ("scope", "multiplayer solo se è il cuore del gioco: costa caro e se è vuoto viene punito"),
    "story_writing_audio": ("differenza", "scrittura e audio curati dove il giocatore li sente di più, non ovunque"),
    "art_visuals": ("clip", "uno stile riconoscibile e coerente, anche semplice, invece di un realismo a metà"),
    "ai_generated_assets": ("rischio_flop", "niente asset generati riconoscibili: il pubblico li punisce"),
    "ai_behavior": ("loop", "nemici leggibili e prevedibili prima che intelligenti"),
    "monetization_dlc": ("prezzo", "niente sensazione di gioco tagliato per i DLC"),
    "dev_support": ("rischio_flop", "piano di aggiornamenti dopo l'uscita, comunicato sulla pagina"),
    "steam_deck": ("scope", "compatibilità Steam Deck verificata"),
    "refund_mentions": ("prima_ora", "le prime 2 ore devono convincere: è la finestra del rimborso"),
}
REWARDED_HINT = {
    "fun_addictive": ("loop", "il momento 'ancora una partita' messo in vetrina: pitch, trailer e prima sessione"),
    "art_style": ("clip", "lo stile come gancio: capsule e primi secondi del trailer"),
    "music_sound": ("differenza", "audio come firma del gioco (musica originale, suoni soddisfacenti)"),
    "depth_variety": ("progressione", "combinazioni e build: dirlo nel pitch, mostrarle nelle clip"),
    "replayability": ("progressione", "ogni partita diversa: generazione, modificatori, sfide"),
    "value_for_money": ("prezzo", "tante ore per il prezzo: dirlo nella pagina"),
    "story_characters": ("differenza", "personaggi con cui affezionarsi, anche in un gioco di sistemi"),
    "polish_feel": ("loop", "feel e risposta dei comandi curati prima dei contenuti"),
    "coop_friends": ("mercato", "co-op tra amici se è naturale per il gioco: gli amici lo vendono"),
    "content_amount": ("progressione", "quantità di contenuti visibile (numeri nella pagina)"),
    "dev_support_positive": ("rischio_flop", "presenza dello sviluppatore: patch note, risposte, roadmap"),
    "easy_to_learn": ("prima_ora", "facile da iniziare, difficile da padroneggiare"),
    "relaxing_cozy": ("gancio", "il tono rilassante come promessa chiara del pitch"),
    "challenge_rewarding": ("loop", "sfida giusta che premia la bravura, con progressi visibili"),
}


def store_path() -> str:
    return user_dir("genre_patterns.json")


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_store(path: str | None = None) -> dict:
    p = path or store_path()
    if os.path.exists(p):
        try:
            return read_json(p)
        except (OSError, ValueError):
            pass
    return {"updated": None, "genres": {}}


def save_store(d: dict, path: str | None = None) -> str:
    p = path or store_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p


def genre_key(g) -> str:
    if isinstance(g, (list, tuple)):
        g = "+".join(sorted(str(x).strip().lower() for x in g if str(x).strip()))
    return str(g or "").strip().lower()


def corpus_genre(res: dict) -> str:
    return genre_key((res.get("params") or {}).get("genre_tag") or [])


def merge(store: dict, res: dict, source: str, genre: str | None = None) -> str | None:
    """Add one corpus run to the store. Returns the genre key, or None when the run has no genre or is already in."""
    g = genre_key(genre) if genre else corpus_genre(res)
    if not g:
        return None
    grp = (res.get("groups") or {}).get("all") or {}
    if not grp:
        return None
    run_id = f"{os.path.abspath(source)}|{res.get('generated')}"
    entry = store["genres"].setdefault(g, {"runs": [], "punished": {}, "rewarded": {}})
    if any(r["id"] == run_id for r in entry["runs"]):
        return None
    n_games = int(grp.get("games") or 0)
    entry["runs"].append(dict(id=run_id, date=res.get("generated"), source=source.replace("\\", "/"), games=n_games,
                              reviews=int(grp.get("reviews_negative") or 0) + int(grp.get("reviews_positive") or 0)))
    for kind in ("punished", "rewarded"):
        for row in grp.get(kind) or []:
            t = entry[kind].setdefault(row["theme"], {"sum_w": 0.0, "w": 0, "runs": 0, "breadth": 0, "games": 0})
            t["sum_w"] += float(row.get("macro_pct") or 0) * max(1, n_games)
            t["w"] += max(1, n_games)
            t["runs"] += 1
            t["breadth"] += int(row.get("breadth") or 0)
            t["games"] += int(row.get("games") or n_games)
    return g


def summary(entry: dict, kind: str) -> list[dict]:
    rows = [dict(theme=k, label=theme_label(k), mean_pct=round(v["sum_w"] / v["w"], 1) if v["w"] else 0.0, runs=v["runs"],
                 breadth=v["breadth"], games=v["games"]) for k, v in (entry.get(kind) or {}).items()]
    rows.sort(key=lambda r: (-r["mean_pct"], -r["breadth"]))
    return rows


def find(store: dict, genre: str) -> tuple[str, dict] | tuple[None, None]:
    g = genre_key(genre)
    if g in store["genres"]:
        return g, store["genres"][g]
    for k, v in store["genres"].items():            # "roguelite" finds "deckbuilding+roguelite"
        if g and g in k.split("+"):
            return k, v
    return None, None


def suggest(store: dict, genre: str, top: int = 4) -> dict:
    g, entry = find(store, genre)
    if not entry:
        return dict(genre=genre, found=False, candidates=[])
    runs = entry["runs"]
    n = dict(runs=len(runs), games=sum(r["games"] for r in runs), reviews=sum(r["reviews"] for r in runs),
             dates=sorted({r["date"] for r in runs if r.get("date")}))
    cands = []
    for kind, hints, verb in (("punished", PUNISHED_HINT, "punito"), ("rewarded", REWARDED_HINT, "premiato")):
        for row in [r for r in summary(entry, kind) if r["theme"] in hints and r["mean_pct"] >= MIN_PCT][:top]:
            area, text = hints[row["theme"]]
            cands.append(dict(kind=kind, theme=row["theme"], area=area, proposal=text, label="[OPINIONE]",
                              evidence=dict(label="[FATTO]", text=f"'{row['label']}' {verb} nel {row['mean_pct']}% delle recensioni "
                                            f"{'negative' if kind == 'punished' else 'positive'} del genere ({row['runs']} corpus, {n['games']} giochi)",
                                            source=f"genre_patterns.json {g} ({', '.join(n['dates'])})")))
    return dict(genre=g, found=True, **n, candidates=cands)


def cmd_build(a) -> int:
    files = a.corpus or sorted(glob.glob(os.path.join("launch", "_raw", "corpus*.json")))
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise SystemExit("nessun corpus trovato: prima review_corpus.py --genre-tag ... -o launch/_raw/corpus.json")
    store = load_store()
    added = []
    for f in files:
        try:
            res = read_json(f)
        except (OSError, ValueError):
            print(f"⚠ {f}: non leggibile")
            continue
        g = merge(store, res, f, a.genre)
        if g:
            added.append(f"{g} ← {f}")
        elif not (a.genre or corpus_genre(res)):
            print(f"⚠ {f}: nessun genere (manca params.genre_tag): usa --genre")
    store["updated"] = dt.date.today().isoformat()
    p = save_store(store)
    print("\n".join(added) if added else "niente di nuovo (corpus già unite)")
    print(f"{p}: {len(store['genres'])} generi")
    return 0


def cmd_show(a) -> int:
    store = load_store()
    keys = [find(store, a.genre)[0]] if a.genre else sorted(store["genres"])
    keys = [k for k in keys if k]
    if a.json:
        print(json.dumps({k: dict(runs=store["genres"][k]["runs"], punished=summary(store["genres"][k], "punished"),
                                  rewarded=summary(store["genres"][k], "rewarded")) for k in keys}, ensure_ascii=False, indent=1))
        return 0
    if not keys:
        print("nessun genere in memoria" + (f" per '{a.genre}'" if a.genre else "") + ": `genre_patterns.py build`")
        return 0
    for k in keys:
        e = store["genres"][k]
        print(f"## {k}: {len(e['runs'])} corpus, {sum(r['games'] for r in e['runs'])} giochi, date {', '.join(sorted({str(r['date']) for r in e['runs']}))}")
        for kind, word in (("punished", "punito"), ("rewarded", "premiato")):
            print(f"  {word}: " + "; ".join(f"{r['label']} {r['mean_pct']}%" for r in summary(e, kind)[:6]))
    return 0


def cmd_suggest(a) -> int:
    s = suggest(load_store(), a.genre, a.top)
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    if not s["found"]:
        print(f"nessun dato per '{a.genre}': prima review_corpus.py sul genere, poi `genre_patterns.py build`")
        return 0
    print(f"{s['genre']}: {s['runs']} corpus, {s['games']} giochi, {s['reviews']} recensioni ({', '.join(s['dates'])})")
    for c in s["candidates"]:
        print(f"- [{c['area']}] {c['proposal']} [OPINIONE]\n    {c['evidence']['text']} [FATTO]")
    return 0


def self_test() -> int:
    tmp = tempfile.mkdtemp()
    os.environ["GLS_HOME"] = tmp
    res = {"generated": "2026-11-01", "params": {"genre_tag": ["Roguelite", "Deckbuilding"]},
           "groups": {"all": {"games": 10, "reviews_negative": 900, "reviews_positive": 600,
                              "punished": [{"theme": "repetitive_shallow", "macro_pct": 20.0, "breadth": 7, "games": 10},
                                           {"theme": "steam_deck", "macro_pct": 1.0, "breadth": 0, "games": 10}],
                              "rewarded": [{"theme": "replayability", "macro_pct": 30.0, "breadth": 9, "games": 10}]}}}
    res2 = json.loads(json.dumps(res))
    res2["generated"] = "2026-11-05"
    res2["groups"]["all"]["games"] = 30
    res2["groups"]["all"]["punished"][0]["macro_pct"] = 10.0
    store = load_store()
    assert merge(store, res, "a/corpus.json") == "deckbuilding+roguelite"
    assert merge(store, res, "a/corpus.json") is None                       # same run twice: counted once
    assert merge(store, res2, "b/corpus.json") == "deckbuilding+roguelite"
    rep = summary(store["genres"]["deckbuilding+roguelite"], "punished")[0]
    assert rep["theme"] == "repetitive_shallow" and rep["mean_pct"] == 12.5 and rep["runs"] == 2, rep   # (20*10 + 10*30) / 40
    s = suggest(store, "roguelite")
    assert s["found"] and s["runs"] == 2 and s["games"] == 40 and s["dates"] == ["2026-11-01", "2026-11-05"]
    assert [c["theme"] for c in s["candidates"]] == ["repetitive_shallow", "replayability"]   # steam_deck below MIN_PCT
    assert s["candidates"][0]["area"] == "progressione" and "12.5%" in s["candidates"][0]["evidence"]["text"]
    assert not suggest(store, "racing")["found"]
    p = save_store(store)
    assert p.startswith(tmp) and load_store()["genres"]
    print("self-test OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Genre memory: what each genre's public punishes and rewards, merged across corpora.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--corpus", nargs="*")
    b.add_argument("--genre", help="genre key when the corpus has no params.genre_tag")
    s = sub.add_parser("show")
    s.add_argument("--genre")
    s.add_argument("--json", action="store_true")
    g = sub.add_parser("suggest")
    g.add_argument("--genre", required=True)
    g.add_argument("--top", type=int, default=4)
    g.add_argument("--json", action="store_true")
    sub.add_parser("self-test")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "show": cmd_show, "suggest": cmd_suggest, "self-test": lambda _a: self_test()}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
