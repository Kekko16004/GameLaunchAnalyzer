#!/usr/bin/env python3
"""Deterministic roster for the simulated focus group: stable tester IDs and fixed trait sheets.

Why a script: the "update" mode of the skill compares the SAME testers across game versions. Their IDs and
traits must never change, and adding more testers must never alter the existing ones. Every trait is derived
from sha256(seed:ID), so the same seed + cohorts always give the same roster, and --per-group 27 -> 36 only
appends A-28.. / B-28.. (the first 27 of each group stay identical).

Casting follows the focus-group rules of the skill: every tester has a skill level, personality, speaking style
and (about 1 in 9) an accessibility need; a 10-person jury covering the mandatory roles (novice, expert, skeptic,
impatient, accessibility, contrarian, value hunter, clip/stream creator) is picked from the SAME IDs, so the
live debate keeps the same voices from wave to wave.

Two groups (A = core/experts, B = discovery/casual), 3 cohorts each (they come from the genre playbook),
cohort of tester n = cohorts[(n-1) % 3]. In every cohort at least 20% of the members are "contrarians"
(mandatory dissent: the skill requires >= 15% of each cohort to contradict its majority).

Everything here is FICTIONAL and simulated: names are invented, language weights are NOT market data.
The skill (or you) writes the narrative card of each tester afterwards (tastes, reference games, what makes
them quit); this tool only fixes the skeleton.

Examples:
  python roster.py --cohorts-a "veterani;min-maxer;critici di bilanciamento" \\
                   --cohorts-b "casual;scroller di clip;cacciatori di valore" --seed mygame \\
                   -o launch/fg/roster.json --md launch/fg/roster.md
  python roster.py ... --per-group 12      # Rapida mode (2 x 12)
  python roster.py ... --per-group 36      # later: appends A-28.., B-28.., existing rows untouched
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from common import load_json, log, write_json

NAMES = ("Luca Marta Giulia Matteo Sofia Davide Chiara Andrea Elena Paolo Sara Marco Anna Tommaso Irene Jonas Lena "
         "Felix Mia Noah Emma Liam Olivia Ethan Ava Lucas Zoe Mateo Valentina Diego Camila Pablo Lucia Joao Beatriz "
         "Rui Ines Pierre Camille Hugo Lea Jakub Kasia Piotr Ola Dmitri Katya Ivan Anya Kenji Yuki Haruto Mei Wei "
         "Jun Min Arjun Priya Rohan Anika Omar Layla Karim Nadia Tariq Amara Kofi Zuri Sam Alex Jordan Riley Casey "
         "Morgan Taylor Robin Ale Fede Greta Ilaria Nico Vera Teo Bruno Elia Dario Martina Rocco Silvia Enzo Dana "
         "Eli Rafa Sven Tess").split()

AGE = {"A": {"18-24": 15, "25-34": 35, "35-44": 30, "45-54": 15, "55+": 5},
       "B": {"18-24": 30, "25-34": 35, "35-44": 20, "45-54": 10, "55+": 5}}
HOURS = {"A": {"<10h": 5, "10-100h": 30, "100-500h": 35, "500h+": 30},
         "B": {"<10h": 35, "10-100h": 45, "100-500h": 18, "500h+": 2}}
DEVICE = {"PC desktop": 55, "laptop": 25, "Steam Deck": 15, "PC su TV con controller": 5}
PRICE = {"A": {"bassa": 25, "media": 45, "alta": 30}, "B": {"bassa": 15, "media": 40, "alta": 45}}
PATIENCE = {"A": {"bassa (~5 min)": 15, "media (~15 min)": 45, "alta (30+ min)": 40},
            "B": {"bassa (~5 min)": 40, "media (~15 min)": 40, "alta (30+ min)": 20}}
DISCOVERY = {"A": {"Reddit / Discord": 30, "YouTube": 30, "Steam browse / tag": 15, "streamer": 10, "amici": 10, "TikTok / Shorts": 5},
             "B": {"TikTok / Shorts": 30, "YouTube": 20, "streamer": 15, "Steam browse / tag": 15, "amici": 15, "Reddit / Discord": 5}}
PERSONALITY = {"A": {"scettico": 25, "meticoloso": 20, "analitico": 20, "schietto": 15, "entusiasta": 10, "ironico": 10},
               "B": {"impaziente": 25, "entusiasta": 20, "schietto": 15, "scettico": 15, "pacato": 15, "ironico": 10}}
STYLE = {"concisa": 25, "prolissa": 15, "tecnica": 20, "colloquiale": 25, "diretta": 15}
ACCESS = ["daltonismo (rosso-verde)", "bassa visione / testo piccolo", "schermo piccolo / Steam Deck", "una sola mano",
          "vincolo motorio (input lenti o limitati)", "sensibilità a luci lampeggianti / motion sickness",
          "udito ridotto (servono sottotitoli)"]
JURY_ROLES = (  # (role, predicate)
    ("principiante", lambda t: t["skill_level"] == "principiante"),
    ("esperto / veterano", lambda t: t["skill_level"] == "esperto" and t["group"] == "A"),
    ("scettico", lambda t: t["personality"] == "scettico"),
    ("impaziente", lambda t: t["patience"].startswith("bassa")),
    ("accessibilità", lambda t: bool(t["accessibility"])),
    ("bastian contrario", lambda t: t["contrarian"]),
    ("cacciatore di valore / rimborsi", lambda t: t["group"] == "B" and t["price_sensitivity"] == "alta"),
    ("creator di clip / streamer", lambda t: t["discovery"] in ("TikTok / Shorts", "streamer")),
)
LANGS = "EN:55,IT:10,DE:8,ES:8,PT-BR:7,FR:5,PL:4,RU:3"
BIAS = [
    "diffida degli asset store e dei giochi che sembrano un kit", "abbandona i tutorial lunghi, preferisce capire giocando",
    "legge sempre prima le recensioni negative", "compra solo se conosce almeno due comparabili",
    "si fida più del trailer che dei tag", "ama la difficoltà, odia le spiegazioni",
    "gioca soprattutto in co-op con amici", "gioca su schermo piccolo: sensibile al testo minuscolo",
    "sensibile ai dettagli tecnici: input lag, frame pacing", "preferisce stili low-poly o pixel art",
    "diffida degli early access", "ha centinaia di giochi nel backlog: serve un motivo forte per aggiungerne uno",
    "tollera il grind se la progressione è chiara", "cerca soprattutto atmosfera e musica",
    "scettico sui prezzi sopra i 15 euro", "si annoia se non c'è una prima scelta entro pochi minuti",
    "ama sperimentare build assurde", "valuta molto l'accessibilità (daltonismo, rimappatura tasti)",
    "segue pochi creator e si fida solo di quelli", "poca pazienza per le interfacce dense",
    "gioca la sera a fine giornata, sessioni brevi", "adora i giochi brevi e rigiocabili",
    "ostile all'AI generativa negli asset", "attratto dagli stili artistici distintivi",
]
VALUE_RX = re.compile(r"valore|saldi|rimbors|refund|value|deal", re.I)
SCROLL_RX = re.compile(r"scroll|clip|tiktok|short", re.I)
STREAM_RX = re.compile(r"stream|creator|reaction", re.I)
EXPERT_RX = re.compile(r"veteran|esperti|min-?max|critic|speedrun|competitiv|simmer|puristi", re.I)


def rng_for(seed: str, tid: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{seed}:{tid}".encode()).hexdigest(), 16))


def pick(r: random.Random, weights: dict):
    return r.choices(list(weights), weights=list(weights.values()), k=1)[0]


def parse_langs(s: str) -> dict:
    out = {}
    for part in s.split(","):
        k, _, v = part.partition(":")
        if k.strip():
            out[k.strip()] = float(v) if v.strip() else 1.0
    return out


def build_tester(group: str, n: int, cohorts: list[str], seed: str, langs: dict) -> dict:
    tid = f"{group}-{n:02d}"
    r = rng_for(seed, tid)
    c_idx, k = (n - 1) % 3, (n - 1) // 3
    cohort = cohorts[c_idx]
    price = "alta" if VALUE_RX.search(cohort) else pick(r, PRICE[group])
    patience = "bassa (~5 min)" if SCROLL_RX.search(cohort) else pick(r, PATIENCE[group])
    discovery = ("TikTok / Shorts" if SCROLL_RX.search(cohort) else "streamer" if STREAM_RX.search(cohort)
                 else pick(r, DISCOVERY[group]))
    hours = pick(r, HOURS[group]) if not EXPERT_RX.search(cohort) or group == "B" else pick(r, {"100-500h": 55, "500h+": 45})
    t = dict(
        id=tid, group=group, cohort=cohort, cohort_index=c_idx + 1,
        name=f"{r.choice(NAMES)} {r.choice('ABCDEFGHILMNOPRSTVZ')}.", age=pick(r, AGE[group]),
        hours_in_genre=hours, device=pick(r, DEVICE), price_sensitivity=price, patience=patience,
        discovery=discovery, language=pick(r, langs), starting_bias=r.choice(BIAS),
        contrarian=(k % 4 == 1))  # k-th member of the cohort: stable when appending, >= 20% of any cohort of 2+ members
    # drawn last so the traits above never depend on them
    t["skill_level"] = {"<10h": "principiante", "10-100h": "intermedio"}.get(hours, "esperto")
    t["personality"] = pick(r, PERSONALITY[group])
    t["speaking_style"] = pick(r, STYLE)
    acc = r.choice(ACCESS)
    t["accessibility"] = acc if (n - 1) % 9 == 5 else None  # n = 6, 15, 24...: stable when appending
    return t


def pick_jury(testers: list[dict], size: int = 10) -> list[dict]:
    """First tester (by ID order) that fills each mandatory role, then the earliest unused IDs alternating A/B.
    Depends only on earlier IDs, so appending testers does not change an existing jury."""
    testers = sorted(testers, key=lambda t: (int(t["id"][2:]), t["group"]))  # A-01, B-01, A-02, ...: new IDs always last
    chosen: dict[str, str] = {}
    for role, ok in JURY_ROLES:
        for t in testers:
            if t["id"] not in chosen and ok(t):
                chosen[t["id"]] = role
                break
    by_group = {g: [t for t in testers if t["group"] == g and t["id"] not in chosen] for g in "AB"}
    i = 0
    while len(chosen) < min(size, len(testers)) and (by_group["A"] or by_group["B"]):
        g = "AB"[i % 2]
        if by_group[g]:
            chosen[by_group[g].pop(0)["id"]] = "voce di coorte"
        i += 1
    return [dict(id=k, role=v) for k, v in chosen.items()]


def to_md(testers: list[dict], existing: str = "") -> str:
    head = ("# Roster del panel simulato\n\n"
            "Tester **fittizi**. Le colonne tecniche sono generate da `roster.py` e **non si modificano mai** "
            "(gli ID servono al delta in modalità Aggiornamento). Compila a mano solo la colonna *Scheda*: gusti, "
            "giochi di riferimento, cosa lo fa uscire dal gioco.\n\n"
            "| ID | Nome | Coorte | Età | Ore nel genere | Livello | Personalità | Stile | Dispositivo | Accessibilità | Prezzo | Pazienza | Scoperta | Lingua | Pregiudizio | Bastian contrario | Scheda |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    have = set(re.findall(r"^\| ([AB]-\d+) \|", existing, re.M))
    rows = [f"| {t['id']} | {t['name']} | {t['cohort']} | {t['age']} | {t['hours_in_genre']} | {t['skill_level']} | "
            f"{t['personality']} | {t['speaking_style']} | {t['device']} | {t['accessibility'] or '-'} | "
            f"{t['price_sensitivity']} | {t['patience']} | {t['discovery']} | {t['language']} | {t['starting_bias']} | "
            f"{'sì' if t['contrarian'] else 'no'} |  |\n" for t in testers if t["id"] not in have]
    if not existing:
        return head + "".join(rows)
    return existing.rstrip("\n") + "\n" + "".join(rows) if rows else existing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cohorts-a", required=True, help='3 cohorts of group A (core/experts), separated by ";"')
    ap.add_argument("--cohorts-b", required=True, help='3 cohorts of group B (discovery/casual), separated by ";"')
    ap.add_argument("--per-group", type=int, default=27, help="testers per group (default 27 = 54 total; Rapida 12)")
    ap.add_argument("--seed", required=True, help="fixed string (e.g. the game slug); changing it changes EVERYONE")
    ap.add_argument("--langs", default=LANGS, help=f'language weights, default "{LANGS}" (NOT market data: adjust to your target)')
    ap.add_argument("--force", action="store_true", help="overwrite an existing roster even if seed/cohorts differ")
    ap.add_argument("-o", "--out", default="-", help="roster .json (default stdout)")
    ap.add_argument("--md", help="roster .md; if it exists only rows for NEW ids are appended (hand-written cards are safe)")
    a = ap.parse_args()

    ca = [c.strip() for c in a.cohorts_a.split(";") if c.strip()]
    cb = [c.strip() for c in a.cohorts_b.split(";") if c.strip()]
    if len(ca) != 3 or len(cb) != 3:
        ap.error(f"exactly 3 cohorts per group are required (got {len(ca)} and {len(cb)})")
    langs = parse_langs(a.langs)
    meta = dict(seed=a.seed, cohorts_a=ca, cohorts_b=cb, langs=langs)

    if a.out != "-" and os.path.exists(a.out) and not a.force:
        old = load_json(a.out)
        if {k: old.get(k) for k in meta} != meta:
            raise SystemExit(f"{a.out} was made with a different seed/cohorts/langs: regenerating would change existing "
                             "tester traits and break the update delta. Use the same arguments, or --force to start over.")
    testers = [build_tester(g, n, c, a.seed, langs) for g, c in (("A", ca), ("B", cb)) for n in range(1, a.per_group + 1)]
    write_json(dict(meta, per_group=a.per_group, jury=pick_jury(testers), testers=testers), a.out)
    if a.md:
        existing = open(a.md, encoding="utf-8").read() if os.path.exists(a.md) else ""
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(to_md(testers, existing))
        log(f"wrote {a.md}")


if __name__ == "__main__":
    main()
