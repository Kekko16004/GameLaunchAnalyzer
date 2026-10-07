#!/usr/bin/env python3
"""Steam tag names: resolve what the user typed into the spellings SteamSpy actually knows, and check the answer.

Why: SteamSpy matches tag names loosely and case-sensitively. "Roguelite" returns the list of another tag,
while the right spelling is "Rogue-lite"; "Rogue-like" and "Roguelike" are both in use; a typo such as
"rogueliek" returns nothing. A wrong list silently poisons every benchmark built on it.

What this module does for every tag the user gives:
  1. spellings: the official Steam tag names (live list, with a built-in fallback) whose letters match once
     hyphens, spaces and case are ignored ("roguelite" -> Rogue-lite), the usual aliases, generated hyphen forms
     ("Rogue-lite", "Roguelite", "Rogue lite") and, for typos, the closest known names (difflib)
  2. query each spelling on SteamSpy
  3. VERIFY each list: take its most reviewed games and look at their own tags (SteamSpy appdetails); a list is
     accepted only if most of those games really carry the tag. Lists that fail are discarded with a warning.
Accepted lists of the same input are merged (one game counted once).

Command line, to see how a name resolves:
  python steam_tags.py Roguelite "Rogue-like" rogueliek "co op"
"""
from __future__ import annotations

import argparse
import difflib
import re

from common import log, q, safe_json, set_rate

# Common Steam tags, exact spelling. Fallback when the live tag list cannot be read; the live list wins.
BUILTIN_TAGS = [
    "Action", "Action RPG", "Action Roguelike", "Action-Adventure", "Adventure", "Anime", "Arcade", "Atmospheric", "Automation", "Base Building", "Beat 'em up",
    "Bullet Hell", "Building", "Card Game", "Casual", "Choices Matter", "City Builder", "Clicker", "Colony Sim", "Colorful", "Comedy", "Competitive", "Cooking", "Co-op",
    "Online Co-Op", "Local Co-Op", "Local Multiplayer", "Cozy", "Crafting", "CRPG", "Cute", "Cyberpunk", "Dark", "Dark Fantasy", "Dating Sim", "Deckbuilding", "Detective",
    "Difficult", "Driving", "Early Access", "Exploration", "Family Friendly", "Fantasy", "Farming Sim", "Fast-Paced", "Female Protagonist", "Fighting", "First-Person", "FPS",
    "Free to Play", "Funny", "Gore", "Great Soundtrack", "Hack and Slash", "Hand-drawn", "Horror", "Idle", "Incremental", "Indie", "JRPG", "Life Sim", "Local Multiplayer",
    "Management", "Massively Multiplayer", "Metroidvania", "Multiplayer", "Music", "Mystery", "Narrative", "Open World", "Party Game", "Party-Based RPG", "Pixel Graphics",
    "Platformer", "2D Platformer", "3D Platformer", "Point & Click", "Post-apocalyptic", "Procedural Generation", "Psychological Horror", "Puzzle", "PvP", "Racing", "Real Time Strategy",
    "Relaxing", "Replay Value", "Retro", "Rhythm", "Rogue-like", "Roguelike", "Rogue-lite", "Roguelike Deckbuilder", "RPG", "Sandbox", "Sci-fi", "Shooter", "Simulation", "Singleplayer",
    "Souls-like", "Space", "Sports", "Stealth", "Story Rich", "Strategy", "Stylized", "Survival", "Survival Horror", "Tactical", "Team-Based", "Third Person", "Third-Person Shooter",
    "Top-Down", "Top-Down Shooter", "Tower Defense", "Turn-Based Combat", "Turn-Based Strategy", "Turn-Based Tactics", "Twin Stick Shooter", "Violent", "Visual Novel", "Walking Simulator",
    "Wholesome", "Zombies", "2D", "3D", "Boomer Shooter", "Hidden Object", "Escape Room", "Mining", "Trading", "Tycoon", "Medieval", "Pirates", "Robots", "Magic", "Mechs", "Time Management",
]
# what people type -> official spellings
ALIASES = {
    "roguelite": ["Rogue-lite"], "roguelike": ["Roguelike", "Rogue-like"], "roguelikes": ["Roguelike", "Rogue-like"], "roguelites": ["Rogue-lite"],
    "deckbuilder": ["Deckbuilding", "Roguelike Deckbuilder"], "deckbuild": ["Deckbuilding"], "deckbuilding": ["Deckbuilding"],
    "soulslike": ["Souls-like"], "soulslikes": ["Souls-like"], "coop": ["Co-op", "Online Co-Op"], "cooperative": ["Co-op"],
    "scifi": ["Sci-fi"], "sciencefiction": ["Sci-fi"], "pointandclick": ["Point & Click"], "pnc": ["Point & Click"], "beatemup": ["Beat 'em up"],
    "hackandslash": ["Hack and Slash"], "hacknslash": ["Hack and Slash"], "citybuilding": ["City Builder"], "citybuilder": ["City Builder"],
    "pixelart": ["Pixel Graphics"], "pixel": ["Pixel Graphics"], "fps": ["FPS"], "firstpersonshooter": ["FPS"], "rts": ["Real Time Strategy"],
    "tbs": ["Turn-Based Strategy"], "farming": ["Farming Sim"], "farmsim": ["Farming Sim"], "lifesimulation": ["Life Sim"], "survivalhorror": ["Survival Horror"],
    "autobattler": ["Auto Battler"], "bulletheaven": ["Bullet Hell"], "shmup": ["Shoot 'Em Up"], "cozygame": ["Cozy"], "relaxing": ["Relaxing"], "visualnovels": ["Visual Novel"],
    "vn": ["Visual Novel"], "idlegame": ["Idle"], "tycoon": ["Management", "Tycoon"], "citysim": ["City Builder"], "colonysim": ["Colony Sim"], "metroidvanias": ["Metroidvania"],
}
SPLIT_SUFFIXES = ("like", "lite", "vania", "based", "fi", "op", "builder", "building", "lib")  # "rogue|lite", "souls|like", "co|op", "sci|fi"

_official: list[str] | None = None


def norm(s: str) -> str:
    """Letters and digits only, lower case: 'Rogue-lite' == 'roguelite' == 'ROGUE LITE'."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def official_names() -> list[str]:
    """Live Steam tag list (popular tags endpoint) merged with the built-in one; read once per run."""
    global _official
    if _official is None:
        data = safe_json("https://store.steampowered.com/tagdata/populartags/english", default=[])
        live = [t["name"] for t in data if isinstance(t, dict) and t.get("name")] if isinstance(data, list) else []
        if not live:
            log("note: live Steam tag list not available, using the built-in list of common tags")
        _official = list(dict.fromkeys(live + BUILTIN_TAGS))
    return _official


def pretty(token: str) -> str:
    return "-".join(p.capitalize() for p in token.split("-"))


def generated_forms(name: str) -> list[str]:
    """Spelling variants of one input: as typed, joined, hyphenated at the usual morphemes, spaced."""
    n = norm(name)
    forms = [name.strip(), name.strip().title(), n.capitalize()]
    for suf in SPLIT_SUFFIXES:
        if n.endswith(suf) and len(n) - len(suf) >= 2:
            head = n[: -len(suf)]
            forms += [pretty(f"{head}-{suf}"), f"{head.capitalize()} {suf}", f"{head.capitalize()}{suf}"]
    return forms


def spellings(name: str, names: list[str] | None = None) -> tuple[list[str], str]:
    """(candidate spellings in priority order, how the input was understood)."""
    names = names or official_names()
    n = norm(name)
    exact = [t for t in names if norm(t) == n]
    out, how = list(exact), "exact (hyphens, spaces and case ignored)" if exact else ""
    for alias in ALIASES.get(n, []):
        if alias not in out:
            out.append(alias)
            how = how or "alias"
    if not out:
        close = difflib.get_close_matches(n, [norm(t) for t in names], n=3, cutoff=0.8)
        for c in close:
            out += [t for t in names if norm(t) == c]
        how = f"corrected (closest known tag: {', '.join(out[:3])})" if out else "not a known tag name, trying generated spellings"
    out += generated_forms(name)
    seen, uniq = set(), []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq, how


def fetch_list(spelling: str) -> dict:
    d = safe_json(f"https://steamspy.com/api.php?request=tag&tag={q(spelling)}")
    return d if isinstance(d, dict) else {}


def carries_tag(appid: str, tag: str) -> bool | None:
    """Does this game carry the tag in its own SteamSpy tags? None if SteamSpy could not tell."""
    d = safe_json(f"https://steamspy.com/api.php?request=appdetails&appid={appid}")
    tags = d.get("tags") if isinstance(d, dict) else None
    if not isinstance(tags, dict) or not tags:
        return None
    return norm(tag) in {norm(k) for k in tags}


def verify_list(spelling: str, games: dict, sample: int = 3) -> bool | None:
    """True if most of the most reviewed games in the list really carry the tag, False if not, None if unverifiable."""
    top = sorted(games.items(), key=lambda kv: -((kv[1].get("positive") or 0) + (kv[1].get("negative") or 0)))[:sample]
    answers = [carries_tag(aid, spelling) for aid, _ in top]
    known = [a for a in answers if a is not None]
    if not known:
        return None
    return sum(known) >= max(1, (len(known) + 1) // 2) if len(known) > 1 else known[0]


def collect(name: str, *, variants: bool = True, validate: bool = True) -> tuple[dict, dict]:
    """Merged SteamSpy lists for one input tag. Returns ({appid: game}, report)."""
    names = official_names()
    cands, how = spellings(name, names) if variants else ([name], "exact spelling as typed")
    report = dict(input=name, understood=how, tried=[], accepted=[], rejected=[], unverified=[])
    merged: dict = {}
    pending: list[tuple[str, dict]] = []
    for sp in cands:
        games = fetch_list(sp)
        report["tried"].append(dict(spelling=sp, games=len(games)))
        if not games:
            continue
        ok = verify_list(sp, games) if validate else None
        if ok is False:
            report["rejected"].append(sp)
            log(f"WARN tag {name!r}: SteamSpy list for spelling {sp!r} ({len(games)} games) does not carry that tag, discarded")
            continue
        if ok is None:
            report["unverified"].append(sp)
            pending.append((sp, games))
            continue
        report["accepted"].append(sp)
        for aid, g in games.items():
            merged.setdefault(str(aid), g)
        if not variants:
            break
    if not merged and pending:  # nothing could be verified: keep the unverified lists rather than return nothing
        log(f"note: tag {name!r}: lists could not be verified (SteamSpy appdetails unavailable), using them as they are")
        for _sp, games in pending:
            for aid, g in games.items():
                merged.setdefault(str(aid), g)
    elif pending and merged:
        report["unverified"] = []
    if not merged:
        log(f"WARN tag {name!r}: no usable list (understood as: {how}). Check the spelling on https://store.steampowered.com/tag/browse")
    return merged, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+"); ap.add_argument("--no-variants", action="store_true"); ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--rate", type=float, default=1.2)
    a = ap.parse_args()
    set_rate(a.rate)
    for t in a.tags:
        games, r = collect(t, variants=not a.no_variants, validate=not a.no_validate)
        print(f"\n{t!r}: understood as {r['understood']}")
        for x in r["tried"]:
            tag = "accepted" if x["spelling"] in r["accepted"] else "REJECTED (wrong list)" if x["spelling"] in r["rejected"] else "unverified" if x["spelling"] in r["unverified"] else "empty"
            print(f"  {x['spelling']:28} {x['games']:4} games  {tag}")
        print(f"  -> {len(games)} games after merging accepted lists")


if __name__ == "__main__":
    main()
