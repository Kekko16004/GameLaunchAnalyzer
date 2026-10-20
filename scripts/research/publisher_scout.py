#!/usr/bin/env python3
"""Publisher scout: which publishers could really sign THIS game, how likely it is, and what unlocks the better ones.

Reads the curated database `data/publishers.json` (every entry has sources with dates; fields that could not be confirmed
are listed in `unverified` and shown as [DA VERIFICARE]) and a game profile, then ranks every publisher by fit:

  genre/tag fit   35   declared genres + (with --live) the real Steam catalog: share of their titles that share >= 2 of our tags
  stage           15   our stage (concept ... released) against the stages they sign at
  traction        15   wishlists / demo against what they ask (min_traction)
  team size       10   our team inside the team sizes they sign
  price point     10   our price inside their catalog's price band
  platform         5   our platforms against theirs
  region/language  5   same country, or a language we share
  avoid_genres   -20   they say they do not sign it

and gives each one a TIER with an honest probability band per pitch [STIMA] and the concrete next step:
  realistic_now        fit good, requirements met, not hyper-selective
  realistic_after      fit good but a requirement is missing (e.g. "public demo + 2,000 wishlists"): the unlock is written
  stretch              selective publisher with a fair fit, or a weaker fit with an easy publisher
  dream                hyper-selective (or poor fit): pitch only with a breakout
It never answers "nobody fits": the best realistic options are always listed, plus what would unlock the higher tiers.
Closed or not-for-third-parties publishers are listed apart, never ranked.

The probability per pitch is base rate x fit x requirements, from `meta.base_rates` of the database (cited there).
"At least one deal pitching the top N" assumes independent answers: it is an upper bound, labelled as such.

With/without publisher (--econ launch/_raw/econ.json from calc_econ.py): for each wishlist scenario, what you keep alone vs with
deal profiles (marketing-only 30 %, full deal 50 % with advance and recoup) and the BREAK-EVEN UPLIFT: how many times more
copies the publisher must sell for you to earn the same. Rev shares and advances vary by deal [DA VERIFICARE per deal].

  publisher_scout.py rank --game launch/_raw/publisher_game.json [--live] [--econ launch/_raw/econ.json]
                          [--cache launch/_raw/publisher_catalog.json] -o launch/_raw/publisher_scout.json --md launch/publisher-scout.md
  publisher_scout.py catalog yogscast-games team17 [--cache ...]     live Steam catalog + SteamSpy tags of some publishers
  publisher_scout.py check [--max-age 180]                           database checks: sources, dates, vocabulary, stale entries
  publisher_scout.py compare --econ launch/_raw/econ.json [--rev-share 0.5] [--advance 20000] [--recoup 10000] [--uplift 2]

Game profile (JSON): {"name", "tags": [...most important first], "stage": "vertical_slice", "wishlists": 0, "has_demo": false,
"team_size": 2, "price_usd": 9.99, "platforms": ["pc"], "country": "IT", "languages": ["it", "en"], "next_milestones":
[{"stage": "demo", "date": "2026-12-20"}], "publisher_question": "yes|no|dont_know"}.
Network only with --live / catalog (Steam store search + SteamSpy, ~1 request/s, cached 30 days). Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import urllib.parse

import common
from common import load_json, log, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "publishers.json")
STAGES = ["concept", "prototype", "vertical_slice", "demo", "early_access", "finished", "released"]
STAGE_IT = {"concept": "idea", "prototype": "prototipo", "vertical_slice": "vertical slice", "demo": "demo pubblica", "early_access": "Early Access",
            "finished": "gioco finito", "released": "già uscito"}
TIERS = ["realistic_now", "realistic_after", "stretch", "dream"]
TIER_IT = {"realistic_now": "realistico adesso", "realistic_after": "realistico dopo un passo", "stretch": "difficile", "dream": "sogno"}
SELECTIVITY = ["low", "medium", "high", "very_high"]
# per-pitch chance of a signed deal for a GOOD-FIT pitch [STIMA]; the database meta can override with cited numbers
BASE_RATES = {"low": (0.05, 0.15), "medium": (0.02, 0.07), "high": (0.008, 0.03), "very_high": (0.002, 0.01)}
WEIGHTS = dict(genre=35, stage=15, traction=15, team=10, price=10, platform=5, region=5)
SYN = {"rogue-lite": "roguelite", "roguelite": "roguelite", "rogue-like": "roguelike", "roguelike": "roguelike", "action roguelike": "roguelite",
       "funny": "comedy", "comedy": "comedy", "humor": "comedy", "humour": "comedy", "physics": "physics", "co-op": "co-op", "online co-op": "co-op",
       "local co-op": "co-op", "coop": "co-op", "co op": "co-op", "multiplayer": "multiplayer", "party game": "party", "party": "party",
       "first-person": "first-person", "first person": "first-person", "fps": "first-person", "casual": "casual", "simulation": "simulation",
       "sim": "simulation", "cooking": "cooking", "food": "cooking", "management": "management", "arcade": "arcade", "cozy": "cozy",
       "wholesome": "cozy", "cute": "cute", "deckbuilder": "deckbuilding", "deckbuilding": "deckbuilding", "card game": "deckbuilding",
       "job simulator": "simulation", "time management": "management", "chaotic": "chaos", "chaos": "chaos", "replay value": "replay",
       "procedural generation": "procedural", "3d": "3d", "stylized": "stylized", "cartoony": "cartoon", "cartoon": "cartoon", "colorful": "colorful",
       "puzzle": "puzzle", "action": "action", "strategy": "strategy", "indie": "indie", "singleplayer": "singleplayer", "family friendly": "family"}
GENERIC = {"indie", "singleplayer", "3d", "colorful", "multiplayer", "action", "casual", "2d", "pixel graphics", "atmospheric", "great soundtrack"}
JUNK_TITLE = re.compile(r"\b(demo|soundtrack|ost|dlc|artbook|art book|supporter pack|playtest|season pass|bundle|pack|expansion)\b", re.I)


def norm(t: str) -> str:
    t = str(t).strip().lower().replace("_", " ")
    return SYN.get(t, t)


def tagset(xs) -> list[str]:
    out = []
    for x in xs or []:
        n = norm(x)
        if n and n not in out:
            out.append(n)
    return out


# ---------------------------------------------------------------- database
def load_db(path: str | None = None) -> dict:
    d = load_json(path or DB)
    if isinstance(d, list):
        d = dict(meta={}, publishers=d)
    d.setdefault("meta", {})
    d.setdefault("publishers", [])
    return d


def base_rates(db: dict) -> dict:
    br = dict(BASE_RATES)
    for k, v in ((db.get("meta") or {}).get("base_rates") or {}).items():
        if k in br and isinstance(v, dict) and "low" in v and "high" in v:
            br[k] = (float(v["low"]), float(v["high"]))
    return br


def check_db(db: dict, today: dt.date, max_age: int = 180) -> list[str]:
    """Problems that make an entry untrustworthy. Empty list = OK."""
    pr, ids = [], set()
    for p in db["publishers"]:
        pid = p.get("id") or "?"
        if pid in ids:
            pr.append(f"{pid}: duplicate id")
        ids.add(pid)
        for f in ("name", "status", "genres", "sources", "checked"):
            if not p.get(f):
                pr.append(f"{pid}: missing {f}")
        for s in p.get("sources") or []:
            if not str(s.get("url", "")).startswith("http") or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(s.get("date", ""))):
                pr.append(f"{pid}: source without url or date ({s.get('url')})")
        for st in p.get("deal_stages") or []:
            if st not in STAGES:
                pr.append(f"{pid}: unknown stage {st}")
        if p.get("selectivity") and p["selectivity"] not in SELECTIVITY:
            pr.append(f"{pid}: unknown selectivity {p['selectivity']}")
        if p.get("status") not in ("active", "uncertain", "restructured", "closed", "not_publisher"):
            pr.append(f"{pid}: unknown status {p.get('status')}")
        try:
            age = (today - dt.date.fromisoformat(str(p.get("checked"))[:10])).days
            if age > max_age:
                pr.append(f"{pid}: checked {age} days ago (> {max_age}): verify again")
        except ValueError:
            pr.append(f"{pid}: bad checked date")
    return pr


# ---------------------------------------------------------------- live Steam catalog (public endpoints, cached)
def steam_catalog(names: list[str], limit: int = 25) -> list[dict]:
    """Titles published by these Steam publisher names (store search), demos/soundtracks/DLC removed."""
    seen, out = set(), []
    for name in names:
        url = f"https://store.steampowered.com/search/results/?publisher={urllib.parse.quote(name)}&infinite=1&count=100&start=0&cc=us&l=english"
        try:
            d = common.get_json(url)
        except Exception as e:  # noqa: BLE001
            log(f"WARN catalog {name}: {type(e).__name__}")
            continue
        h = d.get("results_html") or ""
        for m in re.finditer(r'data-ds-appid="(\d+)".*?<span class="title">(.*?)</span>', h, re.S):
            aid, title = int(m.group(1)), re.sub(r"&amp;", "&", m.group(2))
            if aid in seen or JUNK_TITLE.search(title):
                continue
            seen.add(aid)
            out.append(dict(appid=aid, title=title))
    return out[:limit]


def steamspy_tags(appid: int) -> list[str]:
    try:
        d = common.get_json(f"https://steamspy.com/api.php?request=appdetails&appid={appid}")
    except Exception:  # noqa: BLE001
        return []
    tags = d.get("tags") or {}
    return [k for k, _ in sorted(tags.items(), key=lambda kv: -kv[1])][:12] if isinstance(tags, dict) else []


def fetch_catalog(p: dict, cache: dict, today: dt.date, limit: int = 20, max_age: int = 30) -> dict | None:
    c = cache.get(p["id"])
    if c and (today - dt.date.fromisoformat(c["fetched"])).days <= max_age:
        return c
    names = p.get("steam_publisher_names") or [p["name"]]
    titles = steam_catalog(names, limit)
    if not titles:
        return c
    for t in titles:
        t["tags"] = steamspy_tags(t["appid"])
    c = dict(fetched=today.isoformat(), names=names, titles=titles)
    cache[p["id"]] = c
    return c


def catalog_fit(cat: dict | None, game_tags: list[str]) -> dict | None:
    """Share of their real titles that share >= 2 specific tags with our game, and the closest titles."""
    if not cat or not cat.get("titles"):
        return None
    mine = [t for t in game_tags if t not in GENERIC] or game_tags
    rows = []
    for t in cat["titles"]:
        tt = set(tagset(t.get("tags")))
        if not tt:
            continue
        common_ = [x for x in mine if x in tt]
        rows.append((len(common_), t["title"], t["appid"], common_))
    if not rows:
        return None
    hits = [r for r in rows if r[0] >= 2]
    rows.sort(key=lambda r: -r[0])
    return dict(n=len(rows), share=round(len(hits) / len(rows), 3), fetched=cat.get("fetched"),
                closest=[dict(title=r[1], appid=r[2], shared=r[3]) for r in rows[:3] if r[0] >= 1])


# ---------------------------------------------------------------- scoring
def stage_index(s: str | None) -> int:
    return STAGES.index(s) if s in STAGES else 0


def genre_score(game_tags: list[str], p: dict, cf: dict | None) -> tuple[float, list[str]]:
    g = tagset(p.get("genres"))
    mine = [t for t in game_tags if t not in GENERIC] or game_tags
    # weighted by our tag order: the first tags are what the game IS
    w = [1.0 / (1 + 0.35 * i) for i in range(len(mine))]
    hit = [t for t in mine if t in g]
    declared = sum(wi for t, wi in zip(mine, w) if t in g) / max(1e-9, sum(w[: min(len(w), 5)]))
    declared = min(1.0, declared)
    if cf:
        live = min(1.0, cf["share"] / 0.35)      # a third of the catalog sharing 2+ tags = a perfect genre home
        return 0.5 * declared + 0.5 * live, hit
    return declared, hit


def score(game: dict, p: dict, cf: dict | None = None) -> dict:
    tags = tagset(game.get("tags"))
    parts, needs = {}, []
    g, hit = genre_score(tags, p, cf)
    parts["genre"] = g
    # stage
    gi, stages = stage_index(game.get("stage")), [s for s in (p.get("deal_stages") or []) if s in STAGES]
    if not stages:
        parts["stage"] = 0.6
    elif game.get("stage") in stages:
        parts["stage"] = 1.0
    elif gi < min(stage_index(s) for s in stages):
        parts["stage"] = 0.2
        needs.append(dict(kind="stage", stage=STAGES[min(stage_index(s) for s in stages)]))
    else:
        parts["stage"] = 0.6
    # traction
    mt = p.get("min_traction") or {}
    wl, need_wl = int(game.get("wishlists") or 0), int(mt.get("wishlists") or 0)
    tr = 1.0
    if need_wl and wl < need_wl:
        tr = max(0.1, wl / need_wl)
        needs.append(dict(kind="wishlists", wishlists=need_wl))
    if mt.get("demo") and not game.get("has_demo"):
        tr = min(tr, 0.4)
        if not any(n["kind"] == "stage" and stage_index(n["stage"]) >= stage_index("demo") for n in needs):
            needs.append(dict(kind="demo"))
    parts["traction"] = tr
    # team
    ts, team = p.get("team_size"), int(game.get("team_size") or 1)
    parts["team"] = 0.7 if not ts else (1.0 if ts[0] <= team <= ts[1] else 0.3)
    # price
    pb, price = p.get("price_band_usd"), float(game.get("price_usd") or 0)
    if not pb or not price:
        parts["price"] = 0.7
    elif pb[0] <= price <= pb[1]:
        parts["price"] = 1.0
    else:
        gap = (pb[0] - price) / pb[0] if price < pb[0] else (price - pb[1]) / pb[1]
        parts["price"] = 0.5 if gap <= 0.3 else 0.1
    # platform
    plats, mine = set(p.get("platforms") or []), set(game.get("platforms") or ["pc"])
    parts["platform"] = 0.7 if not plats else (1.0 if mine & plats else 0.0)
    # region / language
    langs = set(p.get("languages") or [])
    if p.get("hq") and game.get("country") and str(p["hq"]).upper().startswith(str(game["country"]).upper()):
        parts["region"] = 1.0
    elif langs & set(game.get("languages") or []):
        parts["region"] = 0.6
    else:
        parts["region"] = 0.4
    fit = sum(WEIGHTS[k] * v for k, v in parts.items())
    avoid = [t for t in tags if t in tagset(p.get("avoid_genres"))]
    if avoid:
        fit -= 20
    return dict(fit=round(max(0.0, min(100.0, fit)), 1), parts={k: round(v, 2) for k, v in parts.items()}, genre_hits=hit, avoid_hits=avoid, needs=needs)


def needs_text(needs: list[dict]) -> str:
    out = []
    for n in needs:
        if n["kind"] == "stage":
            out.append(STAGE_IT.get(n["stage"], n["stage"]))
        elif n["kind"] == "wishlists":
            out.append(f"{n['wishlists']:,} wishlist".replace(",", "."))
        elif n["kind"] == "demo":
            out.append("demo pubblica")
    return " + ".join(out)


def tier_of(p: dict, s: dict) -> str:
    sel = p.get("selectivity") or "medium"
    fit, unmet = s["fit"], bool(s["needs"])
    if fit < 35 or s["avoid_hits"] or s["parts"]["genre"] < 0.15:
        return "dream"                      # off-genre: no amount of traction makes it realistic
    if p.get("open_submissions") is False:
        return "dream" if sel == "very_high" else "stretch"
    if sel == "very_high":
        return "stretch" if fit >= 80 and not unmet else "dream"
    if sel == "high":
        return "stretch" if fit >= 55 else "dream"
    if fit < 50 or p.get("status") in ("uncertain", "restructured") or p.get("open_submissions") is None:
        return "stretch"                    # unclear whether they still sign or take pitches: never "realistic" until verified
    return "realistic_after" if unmet else "realistic_now"


def probability(p: dict, s: dict, br: dict) -> tuple[float, float]:
    lo, hi = br.get(p.get("selectivity") or "medium", br["medium"])
    f = max(0.3, min(1.3, s["fit"] / 70))
    req = 0.4 if s["needs"] else 1.0
    st = 0.5 if p.get("status") in ("uncertain", "restructured") else 1.0
    sub = 0.5 if p.get("open_submissions") is None else 0.3 if p.get("open_submissions") is False else 1.0
    k = f * req * st * sub
    return round(lo * k, 4), round(hi * k, 4)


def pct(x: float) -> str:
    v = x * 100
    return f"{v:.1f}".replace(".", ",") if v < 10 else f"{v:.0f}"


def band(lo: float, hi: float) -> str:
    return f"{pct(lo)}-{pct(hi)} %"


def next_step(p: dict, s: dict, game: dict) -> str:
    asks = p.get("asks_for") or []
    how = {"form": "dal modulo", "email": "per email", "platform": "dalla piattaforma indicata", "invite_only": "solo su invito: cerca un'introduzione (evento, contatto comune)"}.get(p.get("submission_method"), "")
    url = p.get("submission_url")
    send = f"invia {how}" + (f" ({url})" if url and p.get("submission_method") != "invite_only" else "") if how else (f"invia da {url}" if url else "trova il canale di invio [DA VERIFICARE]")
    if p.get("submission_method") == "invite_only":
        send = how
    pack = ", ".join(asks[:4]) if asks else "pitch deck di 10 slide, build giocabile, trailer di 60-90 s"
    if s["needs"]:
        return f"Prima: {needs_text(s['needs'])}. Poi {send} con {pack}."
    if p.get("open_submissions") is None:
        return f"Verifica che accettino proposte adesso; se sì {send} con {pack}."
    return f"Adesso: {send} con {pack}; un solo sollecito dopo 4 settimane."


def rank(db: dict, game: dict, catalogs: dict | None = None) -> dict:
    br = base_rates(db)
    rows, excluded = [], []
    tags = tagset(game.get("tags"))
    for p in db["publishers"]:
        if p.get("status") in ("closed", "not_publisher"):
            excluded.append(dict(id=p["id"], name=p["name"], status=p["status"], note=p.get("notes", "")))
            continue
        cf = catalog_fit((catalogs or {}).get(p["id"]), tags) if catalogs is not None else None
        s = score(game, p, cf)
        t = tier_of(p, s)
        lo, hi = probability(p, s, br)
        why = []
        if s["genre_hits"]:
            why.append("generi in comune: " + ", ".join(s["genre_hits"][:4]))
        else:
            why.append("nessun genere in comune dichiarato")
        if cf:
            why.append(f"catalogo Steam reale: {round(cf['share'] * 100)} % dei loro {cf['n']} giochi ha 2+ tag come i nostri (letto il {cf['fetched']})")
        if s["avoid_hits"]:
            why.append("dicono di non firmare: " + ", ".join(s["avoid_hits"]))
        if s["parts"]["team"] < 1 and p.get("team_size"):
            why.append(f"di solito firmano team da {p['team_size'][0]}-{p['team_size'][1]} persone")
        if s["parts"]["price"] < 1 and p.get("price_band_usd"):
            why.append(f"prezzi del loro catalogo {p['price_band_usd'][0]}-{p['price_band_usd'][1]} $")
        if p.get("status") in ("uncertain", "restructured"):
            why.append(f"stato: {p['status']} (vedi note)")
        if p.get("open_submissions") is None:
            why.append("invio delle proposte aperto? [DA VERIFICARE]")
        elif p.get("open_submissions") is False:
            why.append("niente invio aperto: serve un contatto")
        comps = (cf or {}).get("closest") or [dict(title=c.get("title"), appid=c.get("appid")) for c in (p.get("comparables") or [])[:3]]
        rows.append(dict(id=p["id"], name=p["name"], tier=t, fit=s["fit"], parts=s["parts"], p_low=lo, p_high=hi, band=band(lo, hi),
                         needs=s["needs"], unlock=needs_text(s["needs"]), why=why, next_step=next_step(p, s, game), comparables=comps,
                         submission_url=p.get("submission_url"), asks_for=p.get("asks_for") or [], red_flags=p.get("red_flags") or [],
                         deal_types=p.get("deal_types") or [], selectivity=p.get("selectivity"), status=p.get("status"),
                         unverified=p.get("unverified") or [], checked=p.get("checked"), sources=p.get("sources") or [], catalog=cf))
    rows.sort(key=lambda r: (TIERS.index(r["tier"]), -(r["p_low"] + r["p_high"]), -r["fit"]))
    by_tier = {t: [r for r in rows if r["tier"] == t] for t in TIERS}
    # never "nobody fits": the best options by probability, whatever their tier
    best = sorted(rows, key=lambda r: -(r["p_low"] + r["p_high"]))[:5]
    unlocks = {}
    for r in rows:
        if r["tier"] in ("realistic_after", "stretch") and r["unlock"]:
            unlocks.setdefault(r["unlock"], []).append(r["name"])
    top = [r for r in rows if r["tier"] in ("realistic_now", "realistic_after")][:10] or best
    p_none = 1.0
    for r in top:
        p_none *= 1 - (r["p_low"] + r["p_high"]) / 2
    return dict(game=game.get("name"), generated_on=dt.date.today().isoformat(), n=len(rows), rows=rows, excluded=excluded,
                counts={t: len(v) for t, v in by_tier.items()}, best=[r["id"] for r in best],
                unlocks=[dict(unlock=k, publishers=v) for k, v in sorted(unlocks.items(), key=lambda kv: -len(kv[1]))],
                pitch_top=dict(n=len(top), p_any=round(1 - p_none, 3), names=[r["name"] for r in top]),
                base_rates={k: list(v) for k, v in base_rates(db).items()}, base_rates_source=(db.get("meta") or {}).get("base_rates_source"),
                db_checked=(db.get("meta") or {}).get("checked"))


# ---------------------------------------------------------------- with / without publisher
DEAL_PROFILES = [
    dict(key="marketing_only", label="Solo marketing (publisher piccolo)", rev_share=0.30, advance=0, recoup=3000, uplift=(1.3, 2.0)),
    dict(key="full_deal", label="Accordo completo (finanziamento + marketing)", rev_share=0.50, advance=20000, recoup=10000, uplift=(2.0, 4.0)),
]


def dev_income(copies: float, net: float, cash: float, rev_share: float, advance: float, recoup: float, uplift: float) -> float:
    """What the developer keeps with a publisher: the advance, plus their share of what is left after the publisher recoups
    advance + its marketing spend (recoup before the split, the common indie structure [DA VERIFICARE per contratto])."""
    revenue = copies * uplift * net
    return advance + (1 - rev_share) * max(0.0, revenue - advance - recoup) - cash


def breakeven_uplift(copies: float, net: float, cash: float, rev_share: float, advance: float, recoup: float) -> float | None:
    """Copies multiplier the publisher must deliver for you to earn what you would earn alone. 0 = the advance alone beats it."""
    alone = copies * net - cash
    if copies <= 0 or net <= 0:
        return None
    if advance - cash >= alone:
        return 0.0
    u = ((alone + cash - advance) / (1 - rev_share) + advance + recoup) / (copies * net)
    return round(u, 2)


def compare(econ: dict, profiles: list[dict] | None = None) -> dict:
    net, cash = float(econ["net_per_copy"]), float((econ.get("costs") or {}).get("cash") or 0)
    out = []
    for sc in econ.get("scenarios") or []:
        copies = float(sc["copies"])
        alone = round(copies * net - cash, 2)
        deals = []
        for d in profiles or DEAL_PROFILES:
            lo_u, hi_u = d["uplift"]
            deals.append(dict(key=d["key"], label=d["label"], rev_share=d["rev_share"], advance=d["advance"], recoup=d["recoup"], uplift=[lo_u, hi_u],
                              income_low=round(dev_income(copies, net, cash, d["rev_share"], d["advance"], d["recoup"], lo_u), 2),
                              income_high=round(dev_income(copies, net, cash, d["rev_share"], d["advance"], d["recoup"], hi_u), 2),
                              breakeven_uplift=breakeven_uplift(copies, net, cash, d["rev_share"], d["advance"], d["recoup"])))
        out.append(dict(name=sc["name"], wishlists=sc.get("wishlists"), copies=int(copies), alone=alone, deals=deals))
    prof = [dict(d, recoup_copies=math.ceil((d["advance"] + d["recoup"]) / net) if net else None) for d in (profiles or DEAL_PROFILES)]
    return dict(net_per_copy=net, cash=cash, scenarios=out, profiles=prof)


# ---------------------------------------------------------------- report
GIVE_UP = ["30-50 % dei ricavi netti per sempre (o per anni), dopo che il publisher ha recuperato anticipo e spese [DA VERIFICARE per contratto]",
           "decisioni su data di uscita, prezzo, sconti e a volte nome e contenuti",
           "a volte i diritti sul gioco (IP) o sui seguiti: da leggere riga per riga",
           "tempo: trattativa e contratto richiedono settimane o mesi; servono un avvocato e il commercialista"]
GET = ["soldi subito (anticipo) se il publisher finanzia", "marketing, stampa, creator e festival con contatti che noi non abbiamo",
       "porting console, QA, localizzazione, rating", "un nome che i curatori e la stampa riconoscono"]


def fmt_money(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def to_md(res: dict, cmp_: dict | None, game: dict, top: int = 15) -> str:
    rows = res["rows"]
    L = [f"# Publisher per {res.get('game') or 'il gioco'}: lista per fasce e confronto con/senza", "",
         f"Generato da `publisher_scout.py` il {res['generated_on']} · database verificato il {res.get('db_checked') or '?'} · {res['n']} publisher valutati.",
         "Le probabilità sono **[STIMA]**: probabilità che **un** invio ben fatto finisca in un contratto, da base rate × aderenza × requisiti "
         f"({res.get('base_rates_source') or 'base rate della skill [OPINIONE]'}). Servono a mettere in ordine, non sono promesse.", ""]
    q = game.get("publisher_question")
    L += ["## La domanda: publisher sì, no o non so?", "",
          f"Risposta del proprietario: **{ {'yes': 'sì', 'no': 'no', 'dont_know': 'non so'}.get(q, q or 'non ancora chiesta') }**. "
          + ("Per questo sotto ci sono **tutti e due gli scenari** con i numeri." if q in (None, "dont_know") else ""), ""]
    L += ["## In breve", ""]
    c = res["counts"]
    L.append(f"- Realistici adesso: **{c['realistic_now']}** · realistici dopo un passo: **{c['realistic_after']}** · difficili: **{c['stretch']}** · sogni: **{c['dream']}**.")
    pt = res["pitch_top"]
    if pt["n"]:
        L.append(f"- Se proponi il gioco ai primi {pt['n']} realistici, la probabilità di almeno un'offerta è al massimo circa **{round(pt['p_any'] * 100)} %** "
                 "[STIMA, tetto: le risposte non sono indipendenti]. Vuol dire che **va pianificato il lancio da soli** e il publisher è un'opzione in più.")
    if not c["realistic_now"]:
        L.append("- Nessuno è realistico **adesso**: non è un no, è un \"non ancora\". I più vicini e cosa li sblocca sono qui sotto.")
    for u in res["unlocks"][:3]:
        L.append(f"- **{u['unlock']}** sblocca: {', '.join(u['publishers'][:8])}.")
    L.append("")
    L += ["## Classifica", "", "| # | Publisher | Fascia | Aderenza | Probabilità per invio [STIMA] | Perché | Prossimo passo |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows[:top], 1):
        why = "; ".join(r["why"][:3])
        if r["red_flags"]:
            why += "; attenzione: " + "; ".join(r["red_flags"][:2])
        tier = TIER_IT[r["tier"]] + (f" ({r['unlock']})" if r["tier"] == "realistic_after" else "")
        L.append(f"| {i} | {r['name']} | {tier} | {r['fit']:.0f}/100 | {r['band']} | {why} | {r['next_step']} |")
    rest = rows[top:]
    if rest:
        L += ["", "Gli altri: " + ", ".join(f"{r['name']} ({TIER_IT[r['tier']]}, {r['band']})" for r in rest) + "."]
    if res["excluded"]:
        L += ["", "Non utilizzabili (chiusi o non fanno publishing per terzi): " + "; ".join(f"{x['name']} ({x['status']})" for x in res["excluded"]) + "."]
    unv = [r for r in rows[:top] if r["unverified"]]
    if unv:
        L += ["", "**[DA VERIFICARE]** per publisher: " + "; ".join(f"{r['name']}: {', '.join(r['unverified'][:4])}" for r in unv) + "."]
    if cmp_:
        L += ["", "## Con o senza publisher: i nostri numeri", "",
              f"Dal piano economico (`calc_econ.py`): netto per copia {cmp_['net_per_copy']:.2f} $, costi di cassa {fmt_money(cmp_['cash'])} $. "
              "Profili di accordo tipici [DA VERIFICARE per contratto]: " + "; ".join(
                  f"{d['label']}: {round(d['rev_share'] * 100)} % al publisher, anticipo {fmt_money(d['advance'])} $, spese da recuperare {fmt_money(d['recoup'])} $, "
                  f"il publisher fa vendere da {d['uplift'][0]}× a {d['uplift'][1]}× [STIMA]" for d in cmp_["profiles"]) + ".", "",
              "| Scenario | Copie da soli | Da soli ti restano | " + " | ".join(f"{d['label']}: ti restano | ...serve vendere ×" for d in cmp_["profiles"]) + " |",
              "|---|---|---|" + "---|---|" * len(cmp_["profiles"])]
        for s in cmp_["scenarios"]:
            cells = []
            for d in s["deals"]:
                be = d["breakeven_uplift"]
                cells += [f"{fmt_money(d['income_low'])} … {fmt_money(d['income_high'])} $", "l'anticipo basta" if be == 0 else (f"{be}×" if be is not None else "?")]
            L.append(f"| {s['name']} | {fmt_money(s['copies'])} | {fmt_money(s['alone'])} $ | " + " | ".join(cells) + " |")
        for d in cmp_["profiles"]:
            if d.get("advance") and d.get("recoup_copies"):
                L.append("")
                L.append(f"**{d['label']}:** il publisher rientra di anticipo e spese solo oltre **{fmt_money(d['recoup_copies'])} copie**. "
                         "Un anticipo così lo offre solo chi crede che il gioco le superi: se i nostri scenari restano sotto, l'offerta realistica è più piccola "
                         "o senza anticipo. La colonna \"ti restano\" con l'anticipo è vera solo se quell'offerta arriva davvero.")
        L += ["", "**Come si legge \"serve vendere ×\":** quante volte più copie deve farti vendere il publisher perché ti resti quanto da solo. "
              "Se è sopra 3×, il publisher conviene solo se porta davvero un pubblico che da soli non raggiungiamo (o se ci serve l'anticipo per finire il gioco).", "",
              "**Cosa dai:** " + "; ".join(GIVE_UP) + ".", "", "**Cosa ricevi:** " + "; ".join(GET) + ".", ""]
    L += ["## Come lo uso", "",
          "1. Non fermare il piano da soli: pagina, demo, Next Fest e wishlist servono **anche** per convincere un publisher (chiedono numeri).",
          "2. Manda le proposte a 5-10 publisher della fascia \"realistico\" alla volta, non a tutti: una proposta respinta di solito non si ripresenta con la stessa build.",
          "3. Quando arrivano demo pubblica e le wishlist della riga \"sblocca\", rilancia `publisher_scout.py rank` e manda alla fascia successiva.",
          "4. Un contratto si firma solo dopo averlo fatto leggere a un avvocato: rev share, recupero delle spese, diritti, durata, uscita dal contratto.", ""]
    L += ["## Fonti", "", "Ogni publisher ha le sue fonti con data in `data/publishers.json` della skill; le principali:", ""]
    for r in rows[:top]:
        for s in r["sources"][:2]:
            L.append(f"- {r['name']}: {s.get('what', '')} — {s.get('url')} (letto {s.get('date')})")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--game", required=True); r.add_argument("--db"); r.add_argument("--live", action="store_true", help="read the real Steam catalogs (network)")
    r.add_argument("--cache", help="catalog cache JSON (default next to -o)"); r.add_argument("--econ", help="calc_econ.py JSON for the with/without comparison")
    r.add_argument("--catalog-limit", type=int, default=15, help="titles per publisher read with --live"); r.add_argument("--top", type=int, default=15); r.add_argument("-o", "--out"); r.add_argument("--md"); r.add_argument("--rate", type=float, default=1.0)
    c = sub.add_parser("catalog")
    c.add_argument("ids", nargs="+"); c.add_argument("--db"); c.add_argument("--cache", required=True); c.add_argument("--rate", type=float, default=1.0)
    k = sub.add_parser("check")
    k.add_argument("--db"); k.add_argument("--max-age", type=int, default=180)
    m = sub.add_parser("compare")
    m.add_argument("--econ", required=True); m.add_argument("--rev-share", type=float); m.add_argument("--advance", type=float)
    m.add_argument("--recoup", type=float); m.add_argument("--uplift", type=float); m.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    today = dt.date.today()
    if a.cmd == "check":
        db = load_db(a.db)
        pr = check_db(db, today, a.max_age)
        print("\n".join(pr) if pr else f"OK: {len(db['publishers'])} publishers, all with sources and dates")
        raise SystemExit(1 if any("missing" in x or "without url" in x or "duplicate" in x or "unknown" in x for x in pr) else 0)
    if a.cmd == "compare":
        prof = None
        if any(v is not None for v in (a.rev_share, a.advance, a.recoup, a.uplift)):
            u = a.uplift or 1.0
            prof = [dict(key="custom", label="Accordo indicato", rev_share=a.rev_share if a.rev_share is not None else 0.5, advance=a.advance or 0,
                         recoup=a.recoup or 0, uplift=(u, u))]
        res = compare(load_json(a.econ), prof)
        write_json(res, a.out)
        return
    db = load_db(a.db)
    common.set_rate(a.rate)
    if a.cmd == "catalog":
        cache = load_json(a.cache) if os.path.exists(a.cache) else {}
        for pid in a.ids:
            p = next((x for x in db["publishers"] if x["id"] == pid), None)
            if not p:
                log(f"unknown id {pid}")
                continue
            cat = fetch_catalog(p, cache, today)
            log(f"{pid}: {len((cat or {}).get('titles') or [])} titles")
        write_json(cache, a.cache)
        return
    game = load_json(a.game)
    catalogs = None
    if a.live:
        cpath = a.cache or os.path.join(os.path.dirname(os.path.abspath(a.out or a.game)), "publisher_catalog.json")
        catalogs = load_json(cpath) if os.path.exists(cpath) else {}
        for p in db["publishers"]:
            if p.get("status") not in ("closed", "not_publisher"):
                fetch_catalog(p, catalogs, today, a.catalog_limit)
                write_json(catalogs, cpath)          # saved as it goes: an interrupted run resumes from the cache
    res = rank(db, game, catalogs)
    cmp_ = compare(load_json(a.econ)) if a.econ and os.path.exists(a.econ) else None
    if cmp_:
        res["compare"] = cmp_
    res["publisher_question"] = game.get("publisher_question")
    if a.out:
        write_json(res, a.out)
    text = to_md(res, cmp_, game, a.top)
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        log(f"wrote {a.md}")
    elif not a.out:
        print(text)


if __name__ == "__main__":
    main()
