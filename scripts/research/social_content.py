#!/usr/bin/env python3
"""Social content module: what works on TikTok, Instagram Reels, X, Reddit and YouTube Shorts for indie games (evidence with
sources), a post planner that turns the game's best moments into a calendar per platform with hook variants, and a tracker
that learns which formats work for THIS game and feeds the plan, calendar.md and top_moves.py.

Evidence: `data/social_patterns.json` (patterns per platform with kind, strength measured / expert_opinion / anecdote and
sources with dates; honest benchmarks for small accounts; views -> wishlists conversions; flops; subreddit rules; posting
times). It is curated: platforms change, so every rule shows its date. Nothing here scrapes TikTok, Instagram or X: views
and likes come from YOUR analytics (CSV export or typed in), Reddit trends from public RSS (reddit_trends.py).

  social_content.py evidence [--platform tiktok] [--md out.md]           the rules and benchmarks, with sources
  social_content.py moments --from-clips launch/04-clips.md [--runs launch/fg/waves] -o launch/_raw/social_moments.json
                     moments = hook table rows (| H1 | **text** | scores...) + [TOP] lines of the wave runs
  social_content.py plan --moments launch/_raw/social_moments.json --start 2026-10-26 --weeks 6 \\
                     [--per-week tiktok=4,youtube_shorts=3,instagram=3,reddit=1,x=2] [--steam-live 2026-10-31] \\
                     [--learn launch/_raw/social_learn.json] [--calendar launch/calendar.md] -o launch/_raw/social_plan.json --md launch/social-plan.md
  social_content.py track add --date 2026-10-27 --platform tiktok --moment H1 --hook A --views 850 --likes 40 [--wishlists 6] [--url ...]
  social_content.py track import tiktok_export.csv [--platform tiktok]   merge an analytics export (common column names understood)
  social_content.py learn [--posts launch/social_posts.csv] -o launch/_raw/social_learn.json [--md]
                     per platform: median views vs the small-account benchmark; per moment / hook / format: lift vs your median,
                     wishlists per 1,000 views; winners (n >= 2, lift >= 1.5) and losers; small samples are said out loud

Posts file: launch/social_posts.csv (date, platform, url, moment, hook, format, length_s, views, likes, comments, shares, saves,
followers_delta, wishlists_delta, notes). Wishlist deltas are the ones you read in Steamworks for the day after the post: the
tool never estimates them for you.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import statistics

import common  # noqa: F401  (UTF-8 console)
from common import load_json, log, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "social_patterns.json")
PLATFORMS = ["tiktok", "youtube_shorts", "instagram", "reddit", "x"]
PLAT_IT = {"tiktok": "TikTok", "youtube_shorts": "YouTube Shorts", "instagram": "Instagram Reels", "reddit": "Reddit", "x": "X (Twitter)"}
ALIASES = {"tiktok": "tiktok", "tt": "tiktok", "shorts": "youtube_shorts", "youtube": "youtube_shorts", "yt": "youtube_shorts", "youtube_shorts": "youtube_shorts",
           "reels": "instagram", "instagram": "instagram", "ig": "instagram", "reddit": "reddit", "x": "x", "twitter": "x"}
# small-account typical views per post (from the benchmarks of data/social_patterns.json) [FATTO on the cases, STIMA for you]
TYPICAL = {"tiktok": 1000, "youtube_shorts": 400, "instagram": 500, "reddit": 2000, "x": 300}
LENGTH = {"tiktok": "15-30 s, che si ripete in loop", "youtube_shorts": "15-30 s (massimo 3 min)", "instagram": "15-30 s, file pulito senza filigrana",
          "reddit": "GIF o video di 15-30 s", "x": "clip di 30-60 s, link Steam in risposta"}
POST_COLS = ["date", "platform", "url", "moment", "hook", "format", "length_s", "views", "likes", "comments", "shares", "saves", "profile_visits", "followers_delta",
             "wishlists_delta", "clip", "utm", "notes"]
CSV_ALIAS = {"video views": "views", "views": "views", "visualizzazioni": "views", "plays": "views", "impressions": "views", "likes": "likes", "mi piace": "likes",
             "comments": "comments", "commenti": "comments", "shares": "shares", "condivisioni": "shares", "saves": "saves", "salvataggi": "saves",
             "date": "date", "post time": "date", "video publish time": "date", "data": "date", "link": "url", "video link": "url", "url": "url",
             "title": "notes", "video title": "notes", "titolo": "notes", "new followers": "followers_delta", "subscribers": "followers_delta",
             "profile views": "profile_visits", "profile visits": "profile_visits", "visite al profilo": "profile_visits"}


def load_db(path: str | None = None) -> dict:
    return load_json(path or DB)


def plat(x: str) -> str:
    p = ALIASES.get(str(x).strip().lower())
    if not p:
        raise SystemExit(f"unknown platform {x}: use {', '.join(PLATFORMS)}")
    return p


# ---------------------------------------------------------------- evidence
def evidence_md(db: dict, only: str | None = None) -> str:
    L = [f"# Social: cosa funziona per i giochi indie (prove del {db.get('generated')})", "", db.get("note", ""), ""]
    for p, v in db["platforms"].items():
        if only and p != only:
            continue
        L += [f"## {PLAT_IT.get(p, p)}", "", "| Regola | Tipo | Forza della prova | Fonte |", "|---|---|---|---|"]
        for r in v["patterns"]:
            s = (r.get("sources") or [{}])[0]
            L.append(f"| {r['rule']} | {r['kind']} | {r['strength']} | [{s.get('what', 'fonte')[:50]}]({s.get('url')}) {s.get('date', '')} |")
        if v.get("benchmarks"):
            L += ["", "**Cosa è un buon risultato (account piccolo):**", ""]
            L += [f"- {b['metric']}: buono {b.get('good')}; tipico {b.get('typical')} ([fonte]({(b.get('source') or {}).get('url')}))" for b in v["benchmarks"]]
        if v.get("conversion"):
            L += ["", "**Da visualizzazioni a wishlist:**", ""]
            L += [f"- {c['what']}: {c['value']} ([fonte]({(c.get('source') or {}).get('url')}))" for c in v["conversion"]]
        if v.get("flops"):
            L += ["", "**Perché i post falliscono:**", ""] + [f"- {f['why']}" for f in v["flops"]]
        L.append("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- moments
HOOK_ROW = re.compile(r"^\|\s*(H\d+)\s*\|\s*\*\*(.+?)\*\*[^|]*\|(.*)$")


def moments_from_clips(md: str) -> list[dict]:
    out = []
    for ln in md.splitlines():
        m = HOOK_ROW.match(ln.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(3).split("|")]
        nums = [int(re.sub(r"\D", "", c)) for c in cells if re.fullmatch(r"\**\d+\**", c)]
        score = nums[-1] if nums else None
        out.append(dict(id=m.group(1), label=m.group(2).strip(), score=score, source="04-clips.md", kind=kind_of(m.group(2))))
    return out


def moments_from_runs(folder: str) -> list[dict]:
    out, n = [], 0
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if not f.endswith(".md") or "run" not in f.lower():
                continue
            for ln in open(os.path.join(root, f), encoding="utf-8", errors="replace"):
                if "[TOP]" in ln:
                    n += 1
                    txt = re.sub(r"\s+", " ", re.sub(r"\[[A-Z\-:0-9]+\]", "", ln.strip("|- \n"))).strip()[:140]
                    out.append(dict(id=f"R{n}", label=txt, score=None, source=f, kind=kind_of(txt)))
    return out


def kind_of(text: str) -> str:
    t = text.lower()
    if re.search(r"croll|cade|crash|fail|fired|licenz|travolg|rompe|collapse", t):
        return "fail"
    if re.search(r"zio|nonna|tommy|cane|briciola|uncle|ospit|guest|bouquet|tarantella|fotograf", t):
        return "character"
    if re.search(r"perk|furgone|slot|run|carta|card|build|sinergi", t):
        return "roguelite"
    if re.search(r"high|alto|impila|stack|torre|tower|contatore", t):
        return "stack"
    return "chaos"


# generic hook variants per kind of moment: (on-screen text in the first 1-2 s, caption), English for an international audience.
# A game can override or extend them with --hooks FILE ({"fail": [["text", "caption"], ...], ...}) or per moment ("hooks" in the moments file).
HOOKS = {
    "fail": [("Wait for it…", "So close 😭 #indiegame"), ("POV: you thought you had it", "Would you survive this?"), ("0 mistakes allowed.", "This is how it ends")],
    "character": [("Every game has THAT character", "You know the one"), ("Rate this from 1 to 10", "Be honest"), ("Nobody warned me about him", "Why is he like this")],
    "stack": [("How high can you go?", "Guess the number before it falls"), ("More = better. Right?", "Greed is a mechanic"), ("Level 1 vs level 10", "It escalated")],
    "roguelite": [("This upgrade broke the game", "Build of the day"), ("Same run. One perk. Watch.", "Before/after"), ("One more run…", "It's 3 am")],
    "chaos": [("This is fine.", "It is not fine"), ("Worst possible timing", "Timing is everything"), ("I just wanted to do my job", "Chaos, every time")],
}


def load_hooks(path: str | None) -> dict:
    h = {k: list(v) for k, v in HOOKS.items()}
    if path and os.path.exists(path):
        for k, v in load_json(path).items():
            h[k] = [tuple(x) for x in v] + h.get(k, [])
    return h


def schedule_slots(start: dt.date, weeks: int, per_week: dict) -> list[tuple[dt.date, str]]:
    """Spread posts in each week: TikTok/Shorts/Reels on different days, Reddit on Tue/Sat, X on Wed/Fri. Same clip staggered 1-2 days."""
    days_for = {"tiktok": [0, 2, 4, 5, 6, 1, 3], "youtube_shorts": [1, 3, 6, 5, 0, 2, 4], "instagram": [2, 4, 6, 0, 1, 3, 5], "reddit": [1, 5, 3], "x": [2, 4, 0, 6]}
    out = []
    for w in range(weeks):
        base = start + dt.timedelta(days=7 * w)
        for p, n in per_week.items():
            for k in range(min(n, 7)):
                out.append((base + dt.timedelta(days=days_for[p][k % len(days_for[p])]), p))
    return sorted(out, key=lambda x: (x[0], PLATFORMS.index(x[1])))


def subreddit_queue(db: dict) -> list[dict]:
    order = {"high": 0, "medium": 1, "low": 2}
    subs = [s for s in db.get("subreddits", []) if s.get("fit_for_physics_comedy_roguelite") in ("high", "medium") and s["sub"] not in ("r/gamedev", "r/DestroyMyGame")]
    return sorted(subs, key=lambda s: (order.get(s.get("fit_for_physics_comedy_roguelite"), 3), -(s.get("subscribers_approx") or 0)))


COOLDOWN = {"r/IndieGaming": 14, "r/roguelikes": 90, "r/gaming": 30, "r/playmygame": 30}


def learned_weights(learn: dict | None) -> dict:
    """moment id -> weight from the tracker: winners x2, losers x0.5 (only with n >= 2)."""
    w = {}
    for r in (learn or {}).get("by_moment", []):
        if r.get("n", 0) >= 2 and r.get("lift"):
            w[r["key"]] = 2.0 if r["lift"] >= 1.5 else 0.5 if r["lift"] <= 0.6 else 1.0
    return w


def plan(db: dict, moments: list[dict], start: dt.date, weeks: int, per_week: dict, steam_live: dt.date | None, learn: dict | None = None,
         itch_live: dt.date | None = None, game: str = "the game", hooks: dict | None = None, note: str | None = None) -> dict:
    if not moments:
        raise SystemExit("no moments: run `moments` first (hook table in 04-clips.md or [TOP] lines of the runs)")
    w = learned_weights(learn)
    ranked = sorted(moments, key=lambda m: -((m.get("score") or 15) * w.get(m["id"], 1.0)))
    subs, last_sub = subreddit_queue(db), {}
    posts, used, hook_i = [], {}, {}
    slots = schedule_slots(start, weeks, per_week)
    for d, p in slots:
        # each moment goes round all platforms before a new one: cross-post the same clip (staggered), judge per platform
        cand = sorted(ranked, key=lambda m: (used.get((m["id"], p), 0), ranked.index(m)))
        m = cand[0]
        used[(m["id"], p)] = used.get((m["id"], p), 0) + 1
        H = hooks or HOOKS
        hk = [tuple(x) for x in (m.get("hooks") or [])] + list(H.get(m.get("kind") or "chaos", H["chaos"]))
        k = hook_i.get(m["id"], 0)
        hook_i[m["id"]] = k + 1
        a, b = hk[k % len(hk)], hk[(k + 1) % len(hk)]
        live = bool(steam_live and d >= steam_live)
        itch = bool(itch_live and d >= itch_live)
        cta = (f"Wishlist on Steam: {game}" + (" · free beta on itch.io" if itch else "")) if live else ("Free beta on itch.io" if itch else "Follow: Steam page coming soon")
        post = dict(date=d.isoformat(), platform=p, moment=m["id"], moment_label=m["label"], kind=m.get("kind"), length=LENGTH[p],
                    hook_a=a[0], hook_b=b[0], caption=a[1], cta=cta, steam_live=live)
        if p == "reddit":
            sub = next((s for s in subs if (d - last_sub.get(s["sub"], dt.date.min)).days >= COOLDOWN.get(s["sub"], 7)), None)
            if sub:
                last_sub[sub["sub"]] = d
                post["subreddit"] = sub["sub"]
                post["rules"] = sub.get("self_promo_rules", "")[:220]
            post["caption"] = "Titolo personale (es. \"My friend and I made a game about…\"), mai \"wishlist now\"; link Steam in un commento se le regole lo permettono"
        if p == "x":
            post["caption"] = f"{a[1]} — link Steam nella prima risposta, niente hashtag"
        posts.append(post)
    rules = {p: [r["rule"] for r in db["platforms"].get(p, {}).get("patterns", []) if r["kind"] in ("hook", "length", "format", "cta")][:4] for p in per_week}
    return dict(generated_on=dt.date.today().isoformat(), start=start.isoformat(), weeks=weeks, per_week=per_week, posts=posts, rules=rules,
                learned=bool(w), steam_live=steam_live.isoformat() if steam_live else None, itch_live=itch_live.isoformat() if itch_live else None,
                evidence_date=db.get("generated"), note=note)


def plan_md(pl: dict, db: dict) -> str:
    L = [f"# Piano social ({pl['start']}, {pl['weeks']} settimane)", "",
         f"Generato da `social_content.py plan` il {pl['generated_on']} · prove del {pl['evidence_date']} (`data/social_patterns.json`) · "
         + ("pesi aggiornati dai numeri veri dei nostri post." if pl["learned"] else "nessun numero dei nostri post ancora: i pesi vengono dai voti degli hook di `04-clips.md`."), "",
         "## Le regole che contano (con le prove)", ""]
    if pl.get("note"):
        L[4:4] = [f"> {pl['note']}", ""]
    for p, rs in pl["rules"].items():
        L.append(f"- **{PLAT_IT[p]}** ({pl['per_week'][p]} a settimana): " + " · ".join(rs))
    L += ["", "**Cosa è un buon risultato** (account piccolo, dalle fonti): " + "; ".join(
        f"{PLAT_IT[p]} tipico ~{TYPICAL[p]} visualizzazioni a post" for p in pl["per_week"]) + ". Un post virale al mese è già un successo [FATTO sui casi, STIMA per noi].", "",
          "**Come si fa un post:** primo secondo = il momento più forte del gioco già in corso (niente logo, niente intro), testo grande che dice il gancio, sottotitoli sempre, "
          "fine con la richiesta chiara. Lo stesso clip va su tutte le piattaforme a 1-2 giorni di distanza, file pulito senza filigrana di TikTok.", "",
          "**Prova A/B del gancio:** ogni riga ha due testi d'apertura (A e B). Usa A; quando lo stesso momento torna, usa B. Dopo 2 post per variante `learn` dice quale tenere.", "",
          "## Calendario", "", "| Data | Dove | Momento | Testo d'apertura A | B | Didascalia | Fine | Note |", "|---|---|---|---|---|---|---|---|"]
    for x in pl["posts"]:
        note = (x.get("subreddit", "") + ((": " + x["rules"]) if x.get("rules") else "")) if x["platform"] == "reddit" else x["length"]
        L.append(f"| {x['date']} | {PLAT_IT[x['platform']]} | {x['moment']} {x['moment_label'][:60]} | {x['hook_a']} | {x['hook_b']} | {x['caption']} | {x['cta']} | {note} |")
    L += ["", "## Dopo ogni post", "", "Il giorno dopo: `social_content.py track add` con visualizzazioni, like, condivisioni e le wishlist del giorno lette in Steamworks. "
          "Ogni domenica `learn` e poi `plan` di nuovo: i momenti che rendono tornano più spesso, quelli che non rendono escono.", ""]
    return "\n".join(L) + "\n"


def calendar_steps(pl: dict) -> list[dict]:
    weeks: dict = {}
    for x in pl["posts"]:
        d = dt.date.fromisoformat(x["date"])
        wk = (d - dt.timedelta(days=d.weekday())).isoformat()
        weeks.setdefault(wk, []).append(x)
    out = []
    for wk, xs in sorted(weeks.items()):
        cnt = {}
        for x in xs:
            cnt[x["platform"]] = cnt.get(x["platform"], 0) + 1
        moms = sorted({x["moment"] for x in xs})
        out.append(dict(who="👤", key=f"social:{wk}", due=max(x["date"] for x in xs),
                        text=f"**Post della settimana del {wk}**: " + ", ".join(f"{n} {PLAT_IT[p]}" for p, n in cnt.items()) + f" (momenti {', '.join(moms)}; testi in `social-plan.md`), poi i numeri con `track add`",
                        note="le regole e i ganci A/B sono nel piano; ~2-3 h a settimana"))
    return out


# ---------------------------------------------------------------- tracker
def read_posts(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_posts(path: str, rows: list[dict]):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=POST_COLS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r.get("date", ""), r.get("platform", ""))):
            w.writerow(r)


def num(v) -> float | None:
    if v in (None, ""):
        return None
    s = str(v).strip().replace(" ", "")
    m = re.fullmatch(r"([\d.,]+)\s*([kKmM]?)", s)
    if not m:
        return None
    x = m.group(1)
    x = x.replace(",", "") if re.search(r",\d{3}(\D|$)", x) or "." in x and "," in x else x.replace(",", ".")
    try:
        f = float(x)
    except ValueError:
        return None
    return f * {"k": 1e3, "m": 1e6}.get(m.group(2).lower(), 1)


def merge_posts(path: str, new: list[dict]) -> tuple[int, int]:
    rows = read_posts(path)
    key = lambda r: (r.get("url") or "") or f"{r.get('date')}|{r.get('platform')}|{r.get('moment')}|{r.get('hook')}"
    by = {key(r): r for r in rows}
    a = u = 0
    for r in new:
        r = {k: ("" if v is None else str(v)) for k, v in r.items() if k in POST_COLS}
        r["platform"] = plat(r.get("platform") or "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}", r.get("date", "")):
            raise SystemExit(f"bad date {r.get('date')!r} (AAAA-MM-GG)")
        r["date"] = r["date"][:10]
        k = key(r)
        if k in by:
            by[k].update({kk: vv for kk, vv in r.items() if vv != ""})
            u += 1
        else:
            by[k] = r
            a += 1
    write_posts(path, list(by.values()))
    return a, u


def import_rows(path: str, platform: str | None) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    out = []
    for r in raw:
        o = {}
        for k, v in r.items():
            kk = CSV_ALIAS.get(str(k).strip().lower(), str(k).strip().lower())
            if kk in POST_COLS and kk not in o:
                o[kk] = v
        if platform:
            o["platform"] = platform
        for f in ("views", "likes", "comments", "shares", "saves", "profile_visits", "followers_delta", "wishlists_delta"):
            if o.get(f) not in (None, ""):
                n = num(o[f])
                o[f] = "" if n is None else str(int(n))
        d = str(o.get("date", ""))
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", d) or re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", d)
        if m and len(m.group(1)) == 4:
            o["date"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        elif m:
            o["date"] = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"   # US exports: M/D/YYYY
        out.append(o)
    return out


def learn(rows: list[dict]) -> dict:
    res = dict(n=len(rows), platforms=[], by_moment=[], by_hook=[], by_format=[], by_clip=[], winners=[], losers=[], warnings=[])
    byp: dict = {}
    for r in rows:
        v = num(r.get("views"))
        if v is None:
            continue
        byp.setdefault(r["platform"], []).append((r, v))
    med_p = {}
    for p, xs in byp.items():
        vs = [v for _, v in xs]
        med = statistics.median(vs)
        med_p[p] = med
        wls = [(num(r.get("wishlists_delta")), v) for r, v in xs if num(r.get("wishlists_delta")) is not None]
        wl_per_k = round(1000 * sum(w for w, _ in wls) / sum(v for _, v in wls), 2) if wls and sum(v for _, v in wls) else None
        eng = [((num(r.get("likes")) or 0) + (num(r.get("shares")) or 0) * 2 + (num(r.get("comments")) or 0)) / v for r, v in xs if v]
        res["platforms"].append(dict(platform=p, n=len(xs), median_views=round(med), typical_small=TYPICAL.get(p), vs_typical=round(med / TYPICAL[p], 2) if TYPICAL.get(p) else None,
                                     best=round(max(vs)), wishlists_per_1k=wl_per_k, engagement=round(statistics.median(eng), 3) if eng else None))
        if len(xs) < 5:
            res["warnings"].append(f"{PLAT_IT.get(p, p)}: solo {len(xs)} post con numeri, troppo pochi per conclusioni (servono 5+)")
    for field, bucket in (("moment", "by_moment"), ("hook", "by_hook"), ("format", "by_format"), ("clip", "by_clip")):
        g: dict = {}
        for p, xs in byp.items():
            for r, v in xs:
                k = (r.get(field) or "").strip()
                if k:
                    g.setdefault(k, []).append(v / med_p[p] if med_p[p] else 1.0)
        for k, ls in g.items():
            lift = round(statistics.median(ls), 2)
            row = dict(key=k, n=len(ls), lift=lift)
            res[bucket].append(row)
            if len(ls) >= 2 and lift >= 1.5:
                res["winners"].append(dict(row, field=field))
            elif len(ls) >= 2 and lift <= 0.6:
                res["losers"].append(dict(row, field=field))
        res[bucket].sort(key=lambda r: -r["lift"])
    return res


def learn_md(ln: dict) -> str:
    L = [f"# Cosa funziona per il nostro gioco ({ln['n']} post registrati)", "", "| Piattaforma | Post | Visualizzazioni mediane | Tipico per un account piccolo | Migliore | Wishlist ogni 1.000 visual. |", "|---|---|---|---|---|---|"]
    for p in ln["platforms"]:
        L.append(f"| {PLAT_IT.get(p['platform'], p['platform'])} | {p['n']} | {p['median_views']} | ~{p['typical_small']} ({p['vs_typical']}×) | {p['best']} | {p['wishlists_per_1k'] if p['wishlists_per_1k'] is not None else '—'} |")
    for title, key in (("Momenti", "by_moment"), ("Ganci (A/B)", "by_hook"), ("Formati", "by_format")):
        if ln[key]:
            L += ["", f"**{title}** (× = rispetto alla mediana della piattaforma): " + ", ".join(f"{r['key']} {r['lift']}× (n {r['n']})" for r in ln[key])]
    if ln["winners"]:
        L += ["", "**Da rifare:** " + ", ".join(f"{w['field']} {w['key']} ({w['lift']}×, n {w['n']})" for w in ln["winners"])]
    if ln["losers"]:
        L += ["", "**Da togliere:** " + ", ".join(f"{w['field']} {w['key']} ({w['lift']}×, n {w['n']})" for w in ln["losers"])]
    L += [""] + [f"- ⚠️ {w}" for w in ln["warnings"]]
    return "\n".join(L) + "\n"


def parse_per_week(s: str) -> dict:
    out = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[plat(k)] = int(v)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evidence"); e.add_argument("--platform"); e.add_argument("--md")
    m = sub.add_parser("moments"); m.add_argument("--from-clips"); m.add_argument("--runs"); m.add_argument("-o", "--out")
    p = sub.add_parser("plan")
    p.add_argument("--moments", required=True); p.add_argument("--start"); p.add_argument("--weeks", type=int, default=6)
    p.add_argument("--per-week", default="tiktok=4,youtube_shorts=3,instagram=3,reddit=1,x=2"); p.add_argument("--steam-live", help="date the Steam page goes live: from then the CTA is the wishlist")
    p.add_argument("--itch-live", help="date the free itch.io build is out"); p.add_argument("--note", help="one line shown at the top of the plan")
    p.add_argument("--game", default="the game", help="name shown in the call to action"); p.add_argument("--hooks", help="JSON with game-specific hooks per kind")
    p.add_argument("--learn"); p.add_argument("--calendar"); p.add_argument("-o", "--out"); p.add_argument("--md")
    t = sub.add_parser("track"); ts = t.add_subparsers(dest="tcmd", required=True)
    ta = ts.add_parser("add")
    for f in POST_COLS:
        ta.add_argument(f"--{f.replace('_delta', '').replace('_', '-')}", dest=f)
    ta.add_argument("--posts", default=os.path.join("launch", "social_posts.csv"))
    ti = ts.add_parser("import"); ti.add_argument("file"); ti.add_argument("--platform"); ti.add_argument("--posts", default=os.path.join("launch", "social_posts.csv"))
    ln = sub.add_parser("learn"); ln.add_argument("--posts", default=os.path.join("launch", "social_posts.csv")); ln.add_argument("-o", "--out"); ln.add_argument("--md")
    a = ap.parse_args(argv)
    if a.cmd == "track":
        if a.tcmd == "add":
            r = {f: getattr(a, f) for f in POST_COLS if getattr(a, f) is not None}
            print("added %d, updated %d" % merge_posts(a.posts, [r]))
        else:
            print("added %d, updated %d" % merge_posts(a.posts, import_rows(a.file, plat(a.platform) if a.platform else None)))
        return
    if a.cmd == "learn":
        res = learn(read_posts(a.posts))
        res["generated_on"] = dt.date.today().isoformat()
        write_json(res, a.out)
        if a.md:
            open(a.md, "w", encoding="utf-8", newline="\n").write(learn_md(res))
        return
    db = load_db(a.db)
    if a.cmd == "evidence":
        txt = evidence_md(db, plat(a.platform) if a.platform else None)
        if a.md:
            open(a.md, "w", encoding="utf-8", newline="\n").write(txt)
        else:
            print(txt)
        return
    if a.cmd == "moments":
        ms = []
        if a.from_clips:
            ms += moments_from_clips(open(a.from_clips, encoding="utf-8").read())
        if a.runs:
            ms += moments_from_runs(a.runs)
        log(f"{len(ms)} moments")
        write_json(ms, a.out)
        return
    ms = load_json(a.moments)
    start = dt.date.fromisoformat(a.start) if a.start else dt.date.today()
    pl = plan(db, ms, start, a.weeks, parse_per_week(a.per_week), dt.date.fromisoformat(a.steam_live) if a.steam_live else None,
              load_json(a.learn) if a.learn and os.path.exists(a.learn) else None,
              dt.date.fromisoformat(a.itch_live) if a.itch_live else None, a.game, load_hooks(a.hooks), a.note)
    if a.out:
        write_json(pl, a.out)
    if a.md:
        open(a.md, "w", encoding="utf-8", newline="\n").write(plan_md(pl, db))
        log(f"wrote {a.md}")
    if a.calendar:
        import plan_steps as ps
        n = ps.add_block(a.calendar, "📱 Social", f"📱 Social (da social_content.py, aggiornato il {dt.date.today().isoformat()})", calendar_steps(pl))
        log(f"calendar: {n} steps added")


if __name__ == "__main__":
    main()
