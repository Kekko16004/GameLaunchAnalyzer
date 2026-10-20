#!/usr/bin/env python3
"""Weekly READY-TO-POST social kit and the clip registry with storyboards. Practical first: one person, 2-3 hours a week.

The kit for a week has 3-4 posts. Each post: the exact clip (an existing file, or the storyboard id to record), 2-3 hook
texts for the first 1-2 seconds (which one to use this time, for the A/B test), caption, hashtags, platforms with day and
time (same clip cross-posted TikTok -> Shorts -> Reels on consecutive days), the call to action right for the date (before
the Steam page: follow; after: the Steam link with UTM parameters so Steamworks shows the wishlists per post), a one-line
"why" with its source, and the 5-minute logging line to paste the next day. One Reddit post a week: title, subreddit, rules
to check. At the top, "what worked last week -> what changes this week", computed from the posts you logged.

Clip registry (`launch/clips.json`), written once per game and kept up to date:
  {"game": "...", "steam_appid": null, "page_live": "AAAA-MM-GG", "itch_live": "AAAA-MM-GG",
   "hashtags": {"tiktok": ["#indiegame", ...], ...}, "post_times": {"tiktok": "18:30", ...}, "time_note": "...",
   "reddit": [{"sub": "r/indiegames", "flair": "Video", "cooldown_days": 7, "rules_check": ["...", "..."]}],
   "clips": [{"id": "C01", "title": "...", "priority": 1, "status": "todo|recorded|posted|retired", "file": null,
              "length_s": 15, "aspect": "9:16", "platforms": ["tiktok", "youtube_shorts", "instagram", "reddit"],
              "hooks": ["text A", "text B", "text C"], "caption": "...", "reddit_title": "...", "why": "...", "source": "url",
              "record": {"tool": "...", "how": "...", "scene": "...", "setup": "...", "takes": "..."},
              "shots": [{"t": "0.0-1.5", "screen": "...", "camera": "...", "text": "...", "audio": "..."}],
              "end_frame": "...", "music": "...", "avoid": ["..."]}]}

  social_kit.py clips --clips launch/clips.json [--md launch/clips.md]       check every storyboard is complete; write "Clip da fare"
  social_kit.py set C01 --status recorded --file media/clips/raw/x.mp4 [--clips ...]   update a clip (file must exist)
  social_kit.py kit --clips launch/clips.json --start 2026-10-20 [--weeks 2] [--posts 4] [--learn launch/_raw/social_learn.json] \\
                    [--out-dir launch/social-kit] [-o launch/_raw/social_kit.json] [--calendar launch/calendar.md]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import urllib.parse

import common  # noqa: F401
from common import load_json, log, write_json
import social_content as sc

REQUIRED = ("id", "title", "status", "length_s", "aspect", "platforms", "hooks", "caption", "why", "record", "shots", "end_frame")
DAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
STATUS_IT = {"todo": "da registrare", "recorded": "registrata", "posted": "pubblicata", "retired": "ritirata"}


def check_clips(reg: dict, root: str | None = None) -> list[str]:
    pr = []
    for c in reg.get("clips", []):
        miss = [f for f in REQUIRED if not c.get(f)]
        if miss:
            pr.append(f"{c.get('id', '?')}: mancano {', '.join(miss)}")
        if c.get("status") not in STATUS_IT:
            pr.append(f"{c.get('id')}: stato sconosciuto {c.get('status')}")
        if len(c.get("hooks") or []) < 2:
            pr.append(f"{c.get('id')}: servono almeno 2 testi d'apertura per la prova A/B")
        for k in ("tool", "how", "scene", "setup"):
            if not (c.get("record") or {}).get(k):
                pr.append(f"{c.get('id')}: come registrarla, manca '{k}'")
        if c.get("status") in ("recorded", "posted") and c.get("file") and root and not os.path.exists(os.path.join(root, c["file"])):
            pr.append(f"{c.get('id')}: il file {c['file']} non esiste")
        if any(not s_.get("t") or not s_.get("screen") for s_ in c.get("shots") or []):
            pr.append(f"{c.get('id')}: ogni inquadratura vuole tempo e cosa si vede")
    return pr


def clips_md(reg: dict) -> str:
    cl = reg.get("clips", [])
    cnt = {k: sum(1 for c in cl if c.get("status") == k) for k in STATUS_IT}
    L = [f"# Clip da fare: {reg.get('game', '')}", "",
         f"{len(cl)} clip · da registrare {cnt['todo']} · registrate {cnt['recorded']} · pubblicate {cnt['posted']}. Ogni clip ha lo storyboard completo: "
         "si gira e si monta senza ripianificare. Lo stato si aggiorna con `social_kit.py set <id> --status recorded --file <percorso>`.", "",
         "| Clip | Stato | Durata | Formato | Dove | File |", "|---|---|---|---|---|---|"]
    for c in cl:
        L.append(f"| {c['id']} {c['title']} | {STATUS_IT.get(c.get('status'), c.get('status'))} | {c.get('length_s')} s | {c.get('aspect')} | "
                 f"{', '.join(sc.PLAT_IT.get(p, p) for p in c.get('platforms', []))} | {c.get('file') or '—'} |")
    for c in cl:
        r = c.get("record") or {}
        L += ["", f"## {c['id']} · {c['title']} ({STATUS_IT.get(c.get('status'), c.get('status'))})", "",
              f"**Perché:** {c.get('why')} ({c.get('source', '')})", "",
              f"**Durata e formato:** {c.get('length_s')} s, {c.get('aspect')}, per {', '.join(sc.PLAT_IT.get(p, p) for p in c.get('platforms', []))}.", "",
              f"**Come registrarla:** {r.get('tool')} · {r.get('how')}", f"- Scena: {r.get('scene')}", f"- Preparazione: {r.get('setup')}"]
        if r.get("takes"):
            L.append(f"- Prese: {r['takes']}")
        L += ["", "| Tempo | Cosa si vede | Camera | Testo a schermo | Audio |", "|---|---|---|---|---|"]
        L += [f"| {s_['t']} | {s_['screen']} | {s_.get('camera', '')} | {s_.get('text', '')} | {s_.get('audio', '')} |" for s_ in c.get("shots", [])]
        L += ["", "**Testi d'apertura (A/B):** " + " · ".join(f"{chr(65 + i)}: \"{h}\"" for i, h in enumerate(c.get("hooks", []))),
              f"**Sottotitoli:** sempre, bianchi con contorno, in basso al centro sopra l'area dei pulsanti dell'app.",
              f"**Musica/effetti:** {c.get('music', '')}", f"**Ultimo fotogramma:** {c.get('end_frame')}"]
        if c.get("avoid"):
            L.append("**Da evitare:** " + "; ".join(c["avoid"]))
    return "\n".join(L) + "\n"


def utm_link(reg: dict, platform: str, week: str, content: str) -> str | None:
    base = reg.get("steam_url") or (f"https://store.steampowered.com/app/{reg['steam_appid']}/" if reg.get("steam_appid") else None)
    if not base:
        return None
    q = urllib.parse.urlencode(dict(utm_source=platform, utm_medium="social", utm_campaign=f"kit-{week}", utm_content=content))
    return f"{base}{'&' if '?' in base else '?'}{q}"


def clip_weights(learn: dict | None) -> dict:
    w = {}
    for r in (learn or {}).get("by_clip", []):
        if r.get("n", 0) >= 2 and r.get("lift"):
            w[r["key"]] = 2.0 if r["lift"] >= 1.5 else 0.4 if r["lift"] <= 0.6 else 1.0
    return w


def best_hook(clip: dict, learn: dict | None, use_count: int) -> tuple[int, str]:
    """Index of the hook to use: a proven winner for this clip if any, else the next untested one (A, then B, then C)."""
    rows = {r["key"]: r for r in (learn or {}).get("by_hook", [])}
    tested = [(i, rows[f"{clip['id']}-{chr(65 + i)}"]) for i in range(len(clip["hooks"])) if f"{clip['id']}-{chr(65 + i)}" in rows]
    win = [x for x in tested if x[1].get("n", 0) >= 2 and x[1].get("lift", 0) >= 1.3]
    if win:
        i, r = max(win, key=lambda x: x[1]["lift"])
        return i, f"il testo {chr(65 + i)} ha reso {r['lift']}× (n {r['n']}): si tiene"
    i = use_count % len(clip["hooks"])
    return i, f"prova del testo {chr(65 + i)}"


def week_kit(reg: dict, monday: dt.date, posts: int, learn: dict | None, used: dict, db: dict, start: dt.date | None = None) -> dict:
    page = dt.date.fromisoformat(reg["page_live"]) if reg.get("page_live") else None
    itch = dt.date.fromisoformat(reg["itch_live"]) if reg.get("itch_live") else None
    wk = monday.isoformat()
    pre = bool(page and monday + dt.timedelta(days=6) < page)
    w = clip_weights(learn)
    pool = [c for c in reg["clips"] if c.get("status") != "retired"]
    pool.sort(key=lambda c: (used.get(c["id"], 0) / w.get(c["id"], 1.0), -w.get(c["id"], 1.0), c.get("priority", 99)))
    n_video = max(1, posts - 1)                                          # the last slot is the weekly Reddit post (after the page)
    chosen = pool[:n_video]
    if pre and len(chosen) >= 2:
        chosen = [chosen[0], chosen[0]] + chosen[1:n_video - 1]          # before the page: same clip, two hooks = a clean A/B test
    times = reg.get("post_times") or {}
    tags = reg.get("hashtags") or {}
    out = []
    # posts start the day after the kit is made (time to edit the text on the clip), spread over what is left of the week
    first = max(monday, (start or monday) + dt.timedelta(days=1)) if start and start > monday else monday
    span = (monday + dt.timedelta(days=6) - first).days
    chosen = chosen[:max(1, min(len(chosen), span // 2 + 1))]
    step = max(1, span // max(1, len(chosen))) if len(chosen) > 1 else 0
    for k, c in enumerate(chosen):
        d = first + dt.timedelta(days=min(span, k * step))
        hi, hwhy = best_hook(c, learn, used.get(c["id"], 0))
        used[c["id"]] = used.get(c["id"], 0) + 1
        live = bool(page and d >= page)
        cross = [p for p in ("tiktok", "youtube_shorts", "instagram") if p in c.get("platforms", [])]
        slots = []
        for j, p in enumerate(cross):
            pd = d + dt.timedelta(days=j)
            link = utm_link(reg, p, wk, f"{c['id']}-{chr(65 + hi)}") if live else None
            cta = ("Wishlist on Steam" + (" · free beta on itch.io" if itch and pd >= itch else "")) if (page and pd >= page) else "Follow: Steam page " + (page.strftime("%b %d") if page else "soon")
            slots.append(dict(platform=p, date=pd.isoformat(), day=DAYS_IT[pd.weekday()], time=times.get(p, "18:30"), cta=cta,
                              link=link or ("<link Steam con UTM: si genera appena c'è l'AppID>" if page and pd >= page else None), hashtags=tags.get(p, [])))
        status = c.get("status")
        clip_line = c["file"] if c.get("file") and status in ("recorded", "posted") else f"DA REGISTRARE entro il {max(first - dt.timedelta(days=1), d - dt.timedelta(days=2)).isoformat()}: storyboard {c['id']} in clips.md"
        out.append(dict(kind="video", clip=c["id"], title=c["title"], clip_file=clip_line, status=status, length_s=c["length_s"], aspect=c["aspect"],
                        hooks=c["hooks"], use_hook=hi, hook_why=hwhy, caption=c["caption"], slots=slots, why=c["why"], source=c.get("source"),
                        log=[f"social_content.py track add --date {s_['date']} --platform {s_['platform']} --clip {c['id']} --hook {c['id']}-{chr(65 + hi)} "
                             f"--views __ --likes __ --comments __ --profile-visits __" + (" --wishlists __ --utm " + s_["platform"] if s_["link"] else "") for s_ in slots]))
    # Reddit: one post a week, the clip with the best record (or the first), sub by cooldown
    if not pre and reg.get("reddit"):
        best = (sorted(chosen, key=lambda c: -w.get(c["id"], 1.0)) or pool)[0]
        last = used.setdefault("_reddit_last", {})
        ok = [r for r in reg["reddit"] if (monday - dt.date.fromisoformat(last.get(r["sub"], "2000-01-01"))).days >= r.get("cooldown_days", 7)]
        # least recently used first (never used = oldest), so one community does not see us every week
        sub = min(ok, key=lambda r: (last.get(r["sub"], "2000-01-01"), reg["reddit"].index(r))) if ok else reg["reddit"][0]
        last[sub["sub"]] = monday.isoformat()
        rd = monday + dt.timedelta(days=1)
        out.append(dict(kind="reddit", clip=best["id"], title=best.get("reddit_title") or best["title"], subreddit=sub["sub"], flair=sub.get("flair"),
                        date=rd.isoformat(), day=DAYS_IT[rd.weekday()], time=times.get("reddit", "15:00"), rules_check=sub.get("rules_check", []),
                        link=utm_link(reg, "reddit", wk, best["id"]) if page and rd >= page else None,
                        why="clip nativa di 15-30 s con titolo personale: il formato dei post Reddit che hanno portato migliaia di wishlist (Laysara, Song of Iron)",
                        source="https://howtomarketagame.com/2022/01/10/how-a-two-person-team-earned-11000-wishlists-with-one-reddit-post/",
                        log=[f"social_content.py track add --date {rd.isoformat()} --platform reddit --clip {best['id']} --views __ --likes __ --comments __" + (" --wishlists __ --utm reddit" if page and rd >= page else "")]))
    return dict(week=wk, pre_page=pre, posts=out)


def lessons(learn: dict | None) -> list[str]:
    if not learn or not learn.get("n"):
        return ["Nessun numero registrato ancora: questa settimana si raccolgono i primi (5 minuti il giorno dopo ogni post)."]
    L = []
    for p in learn.get("platforms", []):
        L.append(f"{sc.PLAT_IT.get(p['platform'], p['platform'])}: mediana {p['median_views']} visualizzazioni su {p['n']} post ({p['vs_typical']}× il tipico di un account piccolo)"
                 + (f", {p['wishlists_per_1k']} wishlist ogni 1.000" if p.get("wishlists_per_1k") is not None else "") + ".")
    for x in learn.get("winners", [])[:3]:
        L.append(f"Funziona: {x['field']} {x['key']} ({x['lift']}×, n {x['n']}) → torna più spesso questa settimana.")
    for x in learn.get("losers", [])[:3]:
        L.append(f"Non funziona: {x['field']} {x['key']} ({x['lift']}×, n {x['n']}) → esce o cambia testo d'apertura.")
    L += learn.get("warnings", [])[:2]
    return L


def kit_md(reg: dict, k: dict, learn: dict | None) -> str:
    L = [f"# Kit social della settimana del {k['week']} ({reg.get('game', '')})", "",
         "Tempo: ~2-3 h in tutto (montaggio dei testi 20 min a clip, caricamento 5 min a piattaforma, registrazione dei numeri 5 min al giorno).",
         ("**Prima della pagina Steam:** si costruisce il profilo e si provano i testi d'apertura (stessa clip, due testi, due giorni diversi). Niente link." if k["pre_page"]
          else "**Pagina Steam online:** ogni post porta il link con UTM, così in Steamworks (UTM Analytics) si vedono visite e wishlist per post."), "",
         "## Cosa ha funzionato → cosa cambia", ""] + [f"- {x}" for x in lessons(learn)] + [""]
    todo = sorted({p["clip"] for p in k["posts"] if p["kind"] == "video" and p.get("status") == "todo"})
    if todo:
        L += [f"> **Clip ancora da registrare: {', '.join(todo)}** (storyboard in `clips.md`). Se non sono pronte, i post slittano: "
              "rifai il kit con `social_kit.py kit --start <giorno in cui sono pronte>`. Non si posta materiale vecchio o bocciato.", ""]
    for n, p in enumerate(k["posts"], 1):
        if p["kind"] == "video":
            L += [f"## Post {n}: {p['clip']} · {p['title']}", "",
                  f"- **Clip:** {p['clip_file']} ({p['length_s']} s, {p['aspect']})",
                  f"- **Testo nei primi 1-2 s:** **\"{p['hooks'][p['use_hook']]}\"** ({p['hook_why']}). Alternative: " + " · ".join(f"\"{h}\"" for i, h in enumerate(p["hooks"]) if i != p["use_hook"]),
                  f"- **Didascalia:** {p['caption']}", "- **Dove e quando:**"]
            for s_ in p["slots"]:
                L.append(f"  - {sc.PLAT_IT[s_['platform']]}: {s_['day']} {s_['date']} alle {s_['time']} · fine: \"{s_['cta']}\"" + (f" · link: {s_['link']}" if s_.get("link") else "")
                         + (f" · {' '.join(s_['hashtags'])}" if s_.get("hashtags") else ""))
            L += [f"- **Perché:** {p['why']} ([fonte]({p['source']}))" if p.get("source") else f"- **Perché:** {p['why']}",
                  "- **Il giorno dopo (5 min):**", "```"] + p["log"] + ["```", ""]
        else:
            L += [f"## Post {n}: Reddit · {p['subreddit']}", "",
                  f"- **Quando:** {p['day']} {p['date']} alle {p['time']} (mattina negli USA)", f"- **Titolo:** {p['title']}",
                  f"- **Clip:** {p['clip']} caricata come video nativo (non link YouTube)" + (f"; flair \"{p['flair']}\"" if p.get("flair") else ""),
                  "- **Controlla prima di postare:** " + "; ".join(p["rules_check"]),
                  f"- **Link:** solo in un commento, se le regole lo permettono: {p['link']}" if p.get("link") else "- **Link:** nessuno (pagina Steam non ancora online)",
                  f"- **Perché:** {p['why']} ([fonte]({p['source']}))", "- **Il giorno dopo (5 min):**", "```"] + p["log"] + ["```", ""]
    L += ["## Domenica (10 min)", "", "```", "social_content.py learn -o launch/_raw/social_learn.json --md launch/_raw/social_learn.md",
          "social_kit.py kit --clips launch/clips.json --start <lunedì prossimo> --learn launch/_raw/social_learn.json", "```",
          "Il kit della settimana dopo si rifà da solo con quello che ha funzionato."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clips"); c.add_argument("--clips", default=os.path.join("launch", "clips.json")); c.add_argument("--md"); c.add_argument("--root", default=".")
    s = sub.add_parser("set"); s.add_argument("id"); s.add_argument("--status", choices=list(STATUS_IT)); s.add_argument("--file")
    s.add_argument("--clips", default=os.path.join("launch", "clips.json")); s.add_argument("--root", default=".")
    k = sub.add_parser("kit")
    k.add_argument("--clips", default=os.path.join("launch", "clips.json")); k.add_argument("--start"); k.add_argument("--weeks", type=int, default=1)
    k.add_argument("--posts", type=int, default=4); k.add_argument("--learn"); k.add_argument("--out-dir", default=os.path.join("launch", "social-kit"))
    k.add_argument("-o", "--out"); k.add_argument("--calendar")
    a = ap.parse_args(argv)
    reg = load_json(a.clips)
    if a.cmd == "clips":
        pr = check_clips(reg, a.root)
        if a.md:
            open(a.md, "w", encoding="utf-8", newline="\n").write(clips_md(reg))
            log(f"wrote {a.md}")
        print("\n".join(pr) if pr else f"OK: {len(reg.get('clips', []))} clip con storyboard completo")
        raise SystemExit(1 if pr else 0)
    if a.cmd == "set":
        c_ = next((x for x in reg["clips"] if x["id"] == a.id), None)
        if not c_:
            raise SystemExit(f"clip {a.id} non trovata")
        if a.file:
            if not os.path.exists(os.path.join(a.root, a.file)):
                raise SystemExit(f"il file {a.file} non esiste")
            c_["file"] = a.file
        if a.status:
            c_["status"] = a.status
        write_json(reg, a.clips)
        return
    start = dt.date.fromisoformat(a.start) if a.start else dt.date.today()
    monday = start - dt.timedelta(days=start.weekday())
    learn = load_json(a.learn) if a.learn and os.path.exists(a.learn) else None
    db = sc.load_db()
    used: dict = {}
    kits = []
    os.makedirs(a.out_dir, exist_ok=True)
    for i in range(a.weeks):
        kw = week_kit(reg, monday + dt.timedelta(days=7 * i), a.posts, learn, used, db, start if i == 0 else None)
        kits.append(kw)
        path = os.path.join(a.out_dir, f"kit-{kw['week']}.md")
        open(path, "w", encoding="utf-8", newline="\n").write(kit_md(reg, kw, learn if i == 0 else None))
        log(f"wrote {path}")
    if a.out:
        write_json(dict(generated_on=dt.date.today().isoformat(), game=reg.get("game"), kits=kits), a.out)
    if a.calendar:
        import plan_steps as ps
        steps = [dict(who="👤", key=f"social:{kw['week']}", due=(dt.date.fromisoformat(kw["week"]) + dt.timedelta(days=6)).isoformat(),
                      text=f"**Kit social della settimana del {kw['week']}**: {sum(1 for p in kw['posts'] if p['kind'] == 'video')} clip su TikTok/Shorts/Reels"
                      + (" + 1 post Reddit" if any(p["kind"] == "reddit" for p in kw["posts"]) else "") + f" (`social-kit/kit-{kw['week']}.md`), numeri il giorno dopo",
                      note="~2-3 h a settimana; domenica `learn` e il kit dopo si rifà da solo") for kw in kits]
        n = ps.add_block(a.calendar, "📱 Social", f"📱 Social (da social_kit.py, aggiornato il {dt.date.today().isoformat()})", steps)
        log(f"calendar: {n} steps added")


if __name__ == "__main__":
    main()
