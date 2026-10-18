#!/usr/bin/env python3
"""Entity matching for social results: does this video / post really talk about THIS game?

Why: searching a platform by the game title alone returns many results about something else (a film, a song, another
game, a common word). GamesTracker (the owner's project, MIT) collected by title and kept everything; this module
scores every candidate and keeps it only above a threshold.

Signals (all from public fields of the result: title, description/text, channel/author, date, url):
  required  the exact title as a phrase (word boundaries, case and punctuation folded), or a link to the Steam page / appid
  strong    Steam store URL or appid in the text; developer or publisher name or handle in the text or as the author;
            an official channel / account of the game or studio
  medium    genre or tag words of the game in the text ("roguelite", "physics", "co-op"...), gaming context words
            ("gameplay", "steam", "demo", "trailer", "let's play", "indie game")
  date      published before the announce / store-page date -> rejected
  generic   titles of <= 2 words or made only of common words ("Decline", "HOOK", "Monitor", "The Wanderer") need a
            strong signal: the title alone proves nothing
  language  a result written in a script the game does not support (e.g. only Cyrillic text for an English/Italian
            game) loses points: it is usually something else with the same name

score(candidate, game) -> (0..100, reasons). keep(...) -> score >= THRESHOLD (default 50).

CLI, to measure precision on a hand-labelled sample (fixture format in tests/fixtures/entity_match_labels.json):
  python entity_match.py eval tests/fixtures/entity_match_labels.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import unicodedata

THRESHOLD = 50

# Common English words and words that are everywhere in gaming: a title made only of these is "generic".
COMMON = set("""
a an the of and or to in on at for with from by is are be it its this that these those my your our their his her we you they i me us
one two three four five six seven eight nine ten first last new old big small little great good bad best dark light red blue green black
white gold silver iron fire water ice earth wind sky sun moon star stars night day dawn dusk home house room door hall road path way world
land sea ocean island city town village forest garden field farm shop store market cafe kitchen school office station tower castle
dungeon cave mine space planet orbit galaxy time life death love war peace hope fear dream dreams soul souls heart mind spirit ghost
shadow shadows echo echoes legend legends hero heroes king queen knight knights lord god gods monster monsters beast dragon dragons cat cats
dog dogs bird birds fish bear sheep monkey wolf fox frog rabbit snake man men woman girl girls boy boys child children people friends
game games play player players simulator sim tycoon idle clicker survival survivor survivors arena battle battles war wars rush run runner
runners racing race racer jump jumper puzzle puzzles quest adventure adventures story tale tales saga chronicle chronicles online
defense defence tactics strategy shooter shot shoot hunt hunter hunters craft builder build factory empire kingdom kingdoms colony
escape return rise fall falls reborn rebirth origin origins edition remastered deluxe prologue demo chapter part episode vol volume
decline monitor hook knowledge ops wanderer remnants remnant guest apprentice messenger order project protocol signal sector zone
up down out over under after before again together alone beyond inside outside within without nowhere everything nothing something
""".split())
# Gaming context, in the main languages of creators ("review" is left out on purpose: films and products have reviews too).
CONTEXT = set("game games gaming gameplay gamer steam demo trailer playthrough walkthrough longplay indie lets play playing playtest wishlist "
              "roguelike roguelite coop multiplayer pc switch ps5 xbox nextfest gamedev devlog speedrun "
              "gioco giochi jogo jogando juego jugando spiel spiele jeu jeux oyun gra "
              "игра игру игры рогалик прохождение ゲーム 游戏 遊戲 게임".split())
# Results about another game platform with the same name (a Roblox map called "Tidefall") are about something else.
OTHER_PLATFORMS = set("roblox fortnite minecraft rblx gta5 gtav".split())
NON_LATIN = {"cyrillic": (0x0400, 0x04FF), "cjk": (0x4E00, 0x9FFF), "hiragana": (0x3040, 0x30FF), "hangul": (0xAC00, 0xD7AF),
             "arabic": (0x0600, 0x06FF), "thai": (0x0E00, 0x0E7F)}
LANG_SCRIPT = {"russian": "cyrillic", "ukrainian": "cyrillic", "simplified chinese": "cjk", "traditional chinese": "cjk", "japanese": "hiragana",
               "korean": "hangul", "arabic": "arabic", "thai": "thai"}


def fold(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[’'`´]", "", s)
    s = re.sub(r"[^\w]+", " ", s)
    return f" {s.strip()} "


def title_words(title: str) -> list[str]:
    t = re.sub(r"\s*[:\-–—|]\s.*$", "", title or "")   # "Game: Subtitle" -> "Game" also counts
    return [w for w in fold(t).split() if w]


def is_generic(title: str) -> bool:
    """Made only of common words ("The Wanderer", "Dead Weight"): the title alone proves nothing."""
    words = title_words(title)
    return bool(words) and all(w in COMMON or w.isdigit() for w in words)


def is_weak(title: str) -> bool:
    """One word (SHARKS, Monitor, Pathogenic) or generic: needs two independent kinds of evidence, not one."""
    return len(title_words(title)) == 1 or is_generic(title)


def scripts_of(text: str) -> set[str]:
    out = set()
    for ch in text or "":
        o = ord(ch)
        for name, (lo, hi) in NON_LATIN.items():
            if lo <= o <= hi:
                out.add(name)
    return out


def _date(x) -> datetime.date | None:
    if not x:
        return None
    if isinstance(x, datetime.date):
        return x
    try:
        return datetime.date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def gaming_signal(c: dict, g: dict) -> bool:
    body = fold(" ".join(str(c.get(k) or "") for k in ("title", "text")))
    gw = {fold(w).strip() for w in g.get("words") or [] if w}
    return any(f" {w} " in body or w in body.replace(" ", "") for w in CONTEXT) or any(w and f" {w} " in body for w in gw)


def ambiguity(cands: list[dict], g: dict) -> float:
    """Share of the results for this title with no gaming signal at all. The platform tells us how ambiguous the title is:
    'Sharks' or 'Monitor' return mostly non-game content (high), 'Denshattack' returns games (low)."""
    if not cands:
        return 1.0
    return round(sum(1 for c in cands if not gaming_signal(c, g)) / len(cands), 2)


def score(c: dict, g: dict, amb: float | None = None) -> tuple[int, list[str]]:
    """c: candidate {title, text, author, author_id, url, published}; g: game {title, appid, developers, publishers,
    handles, official_channels, words, languages, announced}; amb: ambiguity() of the batch the candidate came from
    (None = unknown, treated as ambiguous)."""
    head = fold(c.get("title"))
    body = fold(" ".join(str(c.get(k) or "") for k in ("title", "text")))
    raw = " ".join(str(c.get(k) or "") for k in ("title", "text", "url"))
    author = fold(c.get("author"))
    why: list[str] = []
    full, short = fold(g["title"]).strip(), " ".join(title_words(g["title"]))
    appid = str(g.get("appid") or "")
    store_link = bool(appid) and bool(re.search(rf"(store\.steampowered\.com/app/{appid}\b|s\.team/a/{appid}\b|steam://\w+/{appid}\b)", raw))
    exact = f" {full} " in body or (len(short.split()) >= 2 and f" {short} " in body)
    if not exact and not store_link:
        return 0, ["title phrase not found"]
    pub = _date(c.get("published"))
    ann = _date(g.get("announced"))
    if pub and ann and pub < ann:
        return 0, [f"published {pub} before the game existed ({ann})"]
    s = 30 if exact else 0
    if exact:
        why.append("exact title")
        if f" {full} " in head or f" {short} " in head:
            s += 10; why.append("title in the headline")
    strong = False
    if store_link:
        s += 50; strong = True; why.append("Steam link / appid")
    names = [fold(x).strip() for x in (g.get("developers") or []) + (g.get("publishers") or []) + (g.get("handles") or []) if x and len(fold(x).strip()) >= 3]
    if any(f" {n} " in body or f" {n} " in author for n in names):
        s += 35; strong = True; why.append("developer / publisher named")
    if c.get("author_id") and c.get("author_id") in (g.get("official_channels") or []):
        s += 50; strong = True; why.append("official channel")
    gw = {fold(w).strip() for w in g.get("words") or [] if w and fold(w).strip() not in ("indie", "casual", "action", "adventure", "simulation")}
    hits = sorted(w for w in gw if w and f" {w} " in body)
    if hits:
        s += min(20, 10 * len(hits)); why.append("genre words: " + ", ".join(hits[:3]))
    ctx = sorted(w for w in CONTEXT if f" {w} " in body or w in body.replace(" ", ""))
    if ctx:
        s += 10; why.append("gaming context")
    if any(f" {w} " in body for w in OTHER_PLATFORMS) and not strong:
        s -= 30; why.append("about another platform (Roblox, Fortnite...)")
    distinctive = amb is not None and amb <= 0.3 and not is_generic(g["title"])
    if distinctive and exact:
        s += 10; why.append(f"distinctive title (only {int(amb * 100)}% of its results are not about games)")
    kinds = int(strong) + int(bool(hits)) + int(bool(ctx)) + int(distinctive and exact)
    foreign = scripts_of(raw) - {LANG_SCRIPT.get(l.lower()) for l in g.get("languages") or []}
    if foreign and not kinds:
        s -= 25; why.append("other script and no gaming signal: " + ", ".join(sorted(foreign)))
    if is_weak(g["title"]) and not strong and kinds < 2:
        s = min(s, THRESHOLD - 1); why.append("one-word or common-word title: needs two kinds of evidence or a Steam link / the developer")
    return max(0, min(100, s)), why


def keep(c: dict, g: dict, threshold: int = THRESHOLD, amb: float | None = None) -> bool:
    return score(c, g, amb)[0] >= threshold


def score_batch(cands: list[dict], g: dict, threshold: int = THRESHOLD) -> list[dict]:
    """Score every result of one search together (ambiguity is measured on the batch)."""
    amb = ambiguity(cands, g)
    for c in cands:
        c["score"], c["why"] = score(c, g, amb)
        c["kept"] = c["score"] >= threshold
    return cands


def evaluate(labels: dict, threshold: int = THRESHOLD) -> dict:
    """Precision of 'keep everything the title search returned' (before) vs 'keep what passes the score' (after)."""
    games = {str(g["appid"]): g for g in labels["games"]}
    tp = fp = fn = tn = 0
    rel_total = 0
    per_game = {}
    amb = {k: ambiguity([it for it in labels["items"] if str(it["appid"]) == k], g) for k, g in games.items()}
    for it in labels["items"]:
        g = games[str(it["appid"])]
        ok = keep(it, g, threshold, amb[str(it["appid"])])
        rel = bool(it["relevant"])
        rel_total += rel
        tp += ok and rel; fp += ok and not rel; fn += (not ok) and rel; tn += (not ok) and not rel
        pg = per_game.setdefault(g["title"], [0, 0, 0])
        pg[0] += 1; pg[1] += rel; pg[2] += ok and rel
    n = len(labels["items"])
    return dict(n=n, games=len(games), relevant=rel_total, precision_before=round(rel_total / n, 3) if n else None,
                kept=tp + fp, precision_after=round(tp / (tp + fp), 3) if tp + fp else None, recall_after=round(tp / rel_total, 3) if rel_total else None,
                false_positives=fp, missed=fn, threshold=threshold, per_game=per_game)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("eval", help="precision before/after on a hand-labelled sample")
    e.add_argument("labels"); e.add_argument("--threshold", type=int, default=THRESHOLD)
    a = ap.parse_args(argv)
    with open(a.labels, encoding="utf-8") as f:
        res = evaluate(json.load(f), a.threshold)
    print(json.dumps({k: v for k, v in res.items() if k != "per_game"}, indent=1))
    for t, (n, rel, kept) in sorted(res["per_game"].items()):
        print(f"  {t[:40]:40s} risultati {n:3d}  pertinenti {rel:3d}  tenuti e pertinenti {kept:3d}", file=sys.stderr)


if __name__ == "__main__":
    main()
