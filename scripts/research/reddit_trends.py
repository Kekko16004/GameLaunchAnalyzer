#!/usr/bin/env python3
"""What performs on a subreddit right now: formats (video, GIF, image, gallery, text/devlog, YouTube, Steam link) and title hooks
of the TOP posts compared with what everybody posts (NEW), from Reddit's public RSS feeds.

Why RSS: the anonymous JSON endpoints answer 403 to scripts; the public Atom feeds (`/r/<sub>/top/.rss?t=week`) are meant to be
read by feed readers. With REDDIT_CLIENT_ID/SECRET in the private keys file the official OAuth API is used instead, and then
scores and comment counts are real. Without OAuth the feed has NO scores: the rank in the top list is the signal
(position 1 = most upvoted), so the tool reports shares and LIFT (share among top posts / share among new posts), not upvotes.
If Reddit answers 403/429 the tool stops for that feed, never retries around a block, and writes the manual steps.
Agent Reach (reach.py, --reach auto by default): when the owner is logged in to Reddit in Agent Reach's browser
(`reach.py doctor` says reddit is ready) the subreddit's latest posts come with REAL upvotes and comments; "top" is then the
best quarter by upvotes of those posts and "new" is all of them (mode "reach"). It is used before RSS when ready, and after an
RSS block otherwise. Not ready = manual steps, as before.

  reddit_trends.py scan indiegames IndieDev IndieGaming IndieGameWishlist --t week [--limit 100] -o launch/_raw/reddit_trends.json
                         [--md launch/_raw/reddit_trends.md] [--raw-dir launch/_raw/reddit_rss] [--manual launch/ricerche-manuali.md]
  reddit_trends.py parse feed.rss [--baseline new.rss]       offline: same analysis from saved feeds (tests, reruns)

Output: per subreddit the formats and title features with share in top, share in new, lift; the top 10 titles (paraphrase them
in reports, never paste whole posts); and concrete suggestions for clips and titles, labelled [STIMA] (n of one week is small).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as htmlmod
import json
import os
import re
import xml.etree.ElementTree as ET

import common
import reach
import reddit_backends as rb
from common import load_env, log, write_json

ATOM = "{http://www.w3.org/2005/Atom}"
UA = "game-launch-strategist/1.0 (indie launch research; public RSS)"
FEATURES = {
    "first_person": (r"\b(i|i've|i'm|we|we've|my|our)\b", "parla in prima persona (\"ho fatto\", \"il mio gioco\")"),
    "question": (r"\?", "fa una domanda"),
    "number": (r"\d", "contiene un numero (anni, giorni, wishlist, copie)"),
    "time_effort": (r"\b(\d+\s*(years?|months?|weeks?|days?|hours?)|years? of|after \w+ (years?|months?))\b", "racconta il tempo o la fatica (\"dopo 3 anni\")"),
    "first_game": (r"\bfirst (game|indie|steam)\b|\bdebut\b", "\"il mio primo gioco\""),
    "solo": (r"\bsolo\b|\bby myself\b|\balone\b", "sviluppatore da solo"),
    "milestone": (r"\b(release[sd]?|launch(ed)?|out now|wishlists?|demo|steam page|next fest|finally)\b", "annuncia un traguardo (uscita, demo, wishlist)"),
    "feedback": (r"\b(feedback|thoughts|what do you think|opinion|which one|help me|rate)\b", "chiede un parere"),
    "before_after": (r"\b(before|after|vs\.?|then and now|progress|evolution|comparison)\b", "prima/dopo o progressi"),
    "emotion": (r"\b(finally|proud|happy|excited|nervous|scared|can't believe|crying|dream|love)\b", "emozione esplicita"),
    "humor": (r"\b(lol|funny|chaos|chaotic|accidentally|bug|physics|ragdoll|oops|wobbl|fail)\b", "umorismo, caos, fisica, fallimenti"),
    "trailer": (r"\btrailer\b", "parola \"trailer\""),
}
FORMAT_IT = {"video": "video caricato su Reddit", "gif": "GIF", "image": "immagine", "gallery": "galleria di immagini", "text": "solo testo (devlog, domanda)",
             "youtube": "link a YouTube", "steam": "link alla pagina Steam", "itch": "link a itch.io", "link": "altro link"}


def classify(entry_html: str, permalink: str) -> str:
    h = htmlmod.unescape(entry_html or "")
    m = re.search(r'<a href="([^"]+)">\[link\]</a>', h)
    target = m.group(1) if m else ""
    t = target.lower()
    if "v.redd.it" in t or "v.redd.it" in h:
        return "video"
    if re.search(r"\.gifv?(\?|$)", t) or ("i.redd.it" in t and ".gif" in t) or re.search(r"preview\.redd\.it/[^\"']+\.gif", h):
        return "gif"
    if "reddit.com/gallery" in t:
        return "gallery"
    if "i.redd.it" in t or re.search(r"\.(png|jpe?g|webp)(\?|$)", t) or "i.imgur.com" in t:
        return "image"
    if "youtube.com" in t or "youtu.be" in t:
        return "youtube"
    if "store.steampowered.com" in t:
        return "steam"
    if "itch.io" in t:
        return "itch"
    if not t or (permalink and t.split("?")[0].rstrip("/") == permalink.split("?")[0].rstrip("/")) or "/comments/" in t:
        return "text"
    return "link"


def parse_feed(xml_text: str) -> list[dict]:
    """Atom feed -> [{rank, title, url, format, published, features}]. Robust to junk before the XML."""
    i = xml_text.find("<?xml")
    xml_text = xml_text[i:] if i > 0 else xml_text
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"not an RSS/Atom feed: {e}") from e
    if not root.tag.endswith("feed"):
        raise ValueError(f"not an Atom feed (root <{root.tag}>): probably a block or login page")
    out = []
    for k, e in enumerate(root.findall(f"{ATOM}entry"), 1):
        title = (e.findtext(f"{ATOM}title") or "").strip()
        link = e.find(f"{ATOM}link")
        url = link.get("href") if link is not None else ""
        content = e.findtext(f"{ATOM}content") or ""
        fmt = classify(content, url)
        low = title.lower()
        feats = [f for f, (rx, _) in FEATURES.items() if re.search(rx, low)]
        out.append(dict(rank=k, title=title, url=url, format=fmt, published=(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated") or "")[:10],
                        words=len(title.split()), features=feats))
    return out


def shares(posts: list[dict], key: str) -> dict:
    n = len(posts) or 1
    c: dict = {}
    for p in posts:
        vals = p[key] if isinstance(p[key], list) else [p[key]]
        for v in vals:
            c[v] = c.get(v, 0) + 1
    return {k: round(v / n, 3) for k, v in c.items()}


def weighted_top_share(posts: list[dict], key: str) -> dict:
    """Shares where the first posts of the top list weigh more (rank 1 = weight 1, rank 25 ~ 0.3): order is our only signal without scores."""
    tot, c = 0.0, {}
    for p in posts:
        w = 1 / (1 + 0.1 * (p["rank"] - 1))
        tot += w
        for v in (p[key] if isinstance(p[key], list) else [p[key]]):
            c[v] = c.get(v, 0) + w
    return {k: round(v / tot, 3) for k, v in c.items()} if tot else {}


def analyse(top: list[dict], new: list[dict] | None) -> dict:
    res = dict(n_top=len(top), n_new=len(new or []))
    for key, labels in (("format", FORMAT_IT), ("features", {k: v[1] for k, v in FEATURES.items()})):
        st, sn = weighted_top_share(top, key), shares(new or [], key) if new else {}
        rows = []
        for k in sorted(set(st) | set(sn), key=lambda x: -st.get(x, 0)):
            a, b = st.get(k, 0), sn.get(k, 0)
            lift = round(a / b, 2) if b >= 0.02 else None
            rows.append(dict(key=k, label=labels.get(k, k), top_share=a, new_share=b, lift=lift))
        res[key] = rows
    ws = sorted(p["words"] for p in top)
    res["title_words_median"] = ws[len(ws) // 2] if ws else None
    res["top_titles"] = [dict(rank=p["rank"], title=p["title"][:140], format=p["format"], url=p["url"]) for p in top[:10]]
    return res


def suggestions(an: dict, sub: str) -> list[str]:
    out = []
    fm = [r for r in an.get("format", []) if r["top_share"] >= 0.1]
    if fm:
        best = max(fm, key=lambda r: (r["lift"] or 1) * r["top_share"])
        out.append(f"r/{sub}: il formato che rende di più è **{best['label']}** ({round(best['top_share'] * 100)} % dei post in alto"
                   + (f", {best['lift']}× rispetto a quanto viene pubblicato" if best["lift"] else "") + ") [STIMA, una settimana di dati].")
    weak = [r for r in an.get("format", []) if r["lift"] is not None and r["lift"] < 0.6 and r["new_share"] >= 0.1]
    for r in weak[:2]:
        out.append(f"r/{sub}: **{r['label']}** si pubblica molto ({round(r['new_share'] * 100)} %) ma arriva poco in alto ({r['lift']}×): evitalo qui.")
    ft = [r for r in an.get("features", []) if r["lift"] and r["lift"] >= 1.3 and r["top_share"] >= 0.12]
    for r in sorted(ft, key=lambda r: -r["lift"])[:3]:
        out.append(f"r/{sub}: titoli che **{r['label']}** vanno meglio ({r['lift']}×).")
    if an.get("title_words_median"):
        out.append(f"r/{sub}: titolo mediano dei post in alto: {an['title_words_median']} parole.")
    return out


def oauth_headers() -> dict | None:
    import reddit_rules as rr
    try:
        return rr.oauth_headers()
    except Exception as e:  # noqa: BLE001
        log(f"WARN oauth: {type(e).__name__}")
        return None


def fetch_rss(sub: str, kind: str, t: str, limit: int) -> str:
    q = f"?t={t}&limit={limit}" if kind == "top" else f"?limit={limit}"
    return common.get_text(f"https://www.reddit.com/r/{sub}/{kind}/.rss{q}", headers={"User-Agent": os.environ.get("REDDIT_USER_AGENT") or UA}, retries=2)


def row_of(k: int, x: dict) -> dict:
    """A Reddit-shaped post (API, JSON, archive) -> one row of the analysis."""
    url = x.get("url") or ""
    fmt = "video" if x.get("is_video") else "gallery" if x.get("is_gallery") else "text" if x.get("is_self") else classify(f'<a href="{url}">[link]</a>', "https://www.reddit.com" + (x.get("permalink") or ""))
    title = x.get("title") or ""
    return dict(rank=k, title=title, url="https://www.reddit.com" + (x.get("permalink") or ""), format=fmt, score=x.get("score"), comments=x.get("num_comments"),
                published=common.ts_to_date(x.get("created_utc") or 0), words=len(title.split()), features=[f for f, (rx, _) in FEATURES.items() if re.search(rx, title.lower())])


def fetch_chain(sub: str, t: str, limit: int) -> tuple[list[dict], list[dict], str, str]:
    """RSS / OAuth / Agent Reach failed: the other backends of reddit_backends (public JSON, Arctic Shift archive, ThreadSnoop).
    Returns top, new, backend, note. Raises when none answers."""
    only = [b for b in rb.order() if b in ("json", "arctic", "threadsnoop")]
    top = rb.listing(sub, "top", t, limit, only=only)
    if not top["ok"]:
        raise RuntimeError("; ".join(f"{b}: {o}" for b, o in top["attempts"]) or "nessun backend")
    new = rb.listing(sub, "new", t, limit, only=only)
    def rows(res):
        out = []
        for k, p in enumerate(res.get("posts") or [], 1):
            raw = dict(p.get("raw") or {})
            perma = (p.get("url") or "").replace("https://www.reddit.com", "")
            out.append(row_of(k, dict(raw, title=p.get("title"), permalink=perma, score=p.get("score"), num_comments=p.get("num_comments"),
                                      url=raw.get("url") or p.get("link") or "", created_utc=0)) | dict(published=p.get("published") or ""))
        return out
    t_rows = rows(top)
    n_rows = rows(new) if new["ok"] else t_rows
    return t_rows, n_rows, top["backend"], top.get("note") or ""


def fetch_oauth(sub: str, kind: str, t: str, limit: int, h: dict) -> list[dict]:
    d = common.get_json(f"https://oauth.reddit.com/r/{sub}/{kind}?t={t}&limit={limit}&raw_json=1", headers=h)
    out = []
    for k, c in enumerate(d.get("data", {}).get("children", []), 1):
        out.append(row_of(k, c.get("data") or {}))
    return out


def reach_format(raw: dict) -> str:
    hint, dest = str(raw.get("post_hint") or ""), str(raw.get("url_overridden_by_dest") or raw.get("url") or "")
    if raw.get("gallery_urls"):
        return "gallery"
    if "video" in hint and "rich" not in hint:
        return "video"
    if hint == "image":
        return "gif" if re.search(r"\.gifv?(\?|$)", dest) else "image"
    if hint in ("link", "rich:video") or (dest and "/comments/" not in dest):
        return classify(f'<a href="{dest}">[link]</a>', "")
    return "text"


def fetch_reach(sub: str, limit: int) -> tuple[list[dict], list[dict]]:
    """Latest posts with real upvotes via Agent Reach (site tool, owner's login). top = best quarter by upvotes, new = all."""
    res = reach.posts("reddit", sub, min(limit, 100))
    if not res["ok"]:
        raise RuntimeError("agent-reach " + str((res.get("error") or {}).get("code")))
    rows = []
    for it in res["items"]:
        raw = it.get("raw") if isinstance(it.get("raw"), dict) else {}
        title = it.get("title") or ""
        rows.append(dict(title=title, url=it.get("url") or "", format=reach_format(raw), score=it["metrics"].get("score"), comments=it["metrics"].get("comments"),
                         published=it.get("published") or "", words=len(title.split()), features=[f for f, (rx, _) in FEATURES.items() if re.search(rx, title.lower())]))
    new = [dict(r, rank=k) for k, r in enumerate(rows, 1)]
    top = sorted(rows, key=lambda r: -(r.get("score") or 0))[:max(5, len(rows) // 4)]
    return [dict(r, rank=k) for k, r in enumerate(top, 1)], new


MANUAL = """
## Reddit: tendenze (reddit_trends.py) — da fare a mano se il feed è bloccato
Il feed pubblico ha risposto {status} il {date}. Non si aggira il blocco. A mano (10 minuti):
1. Apri https://www.reddit.com/r/{sub}/top/?t=week e guarda i primi 25 post.
2. Per ognuno annota: formato (video, GIF, immagine, testo, link), parole del titolo, se è un gioco "fisico/comico", upvote.
3. Ripeti con https://www.reddit.com/r/{sub}/new/ per 25 post (è il "di solito si pubblica").
4. Salva la tabella in `launch/_raw/reddit_trends_manual.csv` (colonne: list,rank,format,title,upvotes) e chiedi a Claude di analizzarla.
Oppure: crea un'app "script" gratuita su https://www.reddit.com/prefs/apps e metti REDDIT_CLIENT_ID e REDDIT_CLIENT_SECRET nel file privato delle chiavi.
Oppure (punteggi veri, senza chiavi): `! python <skill>/scripts/research/reach.py login reddit` (login tuo, account secondario; il percorso vero lo stampa `reach.py setup`) e poi `reach.py doctor --live`.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("subs", nargs="+"); s.add_argument("--t", default="week", choices=["day", "week", "month", "year", "all"])
    s.add_argument("--limit", type=int, default=100); s.add_argument("--rate", type=float, default=6.0, help="seconds between requests (default 6)")
    s.add_argument("-o", "--out"); s.add_argument("--md"); s.add_argument("--raw-dir"); s.add_argument("--manual", help="ricerche-manuali.md to append blocked steps to")
    s.add_argument("--env-file"); s.add_argument("--reach", default="auto", choices=["auto", "on", "off"], help="Agent Reach backend (default auto)")
    s.add_argument("--no-chain", action="store_true", help="do not fall back to the other Reddit backends (public JSON, Arctic Shift archive, ThreadSnoop)")
    p = sub.add_parser("parse")
    p.add_argument("feed"); p.add_argument("--baseline"); p.add_argument("--sub", default="?"); p.add_argument("-o", "--out")
    a = ap.parse_args(argv)
    if a.cmd == "parse":
        top = parse_feed(open(a.feed, encoding="utf-8").read())
        new = parse_feed(open(a.baseline, encoding="utf-8").read()) if a.baseline else None
        an = analyse(top, new)
        an["suggestions"] = suggestions(an, a.sub)
        write_json(an, a.out)
        return
    load_env(a.env_file)
    common.set_rate(a.rate)
    reach.configure(mode=a.reach, manual=a.manual)
    h = oauth_headers() if common.has_key("REDDIT_CLIENT_ID") and common.has_key("REDDIT_CLIENT_SECRET") else None
    use_reach = a.reach != "off" and reach.enabled()
    mode = "oauth" if h else "reach" if use_reach and (a.reach == "on" or reach.ready("reddit")) else "rss"
    log(f"mode: {mode}")
    today = dt.date.today().isoformat()
    notes = dict(rss="RSS: no scores, rank = signal; lift = share in top / share in new", oauth="OAuth: real scores",
                 reach="Agent Reach: latest posts with real upvotes; top = best quarter by upvotes (period = the latest posts, not --t)")
    res = dict(generated_on=today, mode=mode, t=a.t, subs={}, blocked=[], note=notes[mode])
    for sname in a.subs:
        sname = sname.removeprefix("r/").strip("/")
        try:
            if h:
                top, new = fetch_oauth(sname, "top", a.t, a.limit, h), fetch_oauth(sname, "new", a.t, a.limit, h)
            elif mode == "reach":
                top, new = fetch_reach(sname, a.limit)
            else:
                tx, nx = fetch_rss(sname, "top", a.t, a.limit), fetch_rss(sname, "new", a.t, a.limit)
                if a.raw_dir:
                    os.makedirs(a.raw_dir, exist_ok=True)
                    for kind, txt in (("top", tx), ("new", nx)):
                        open(os.path.join(a.raw_dir, f"{sname}-{kind}-{today}.rss"), "w", encoding="utf-8").write(txt)
                top, new = parse_feed(tx), parse_feed(nx)
        except Exception as e:  # noqa: BLE001
            status = getattr(e, "code", type(e).__name__)
            if mode == "rss" and use_reach:
                try:
                    top, new = fetch_reach(sname, a.limit)
                    an = analyse(top, new)
                    an["suggestions"] = suggestions(an, sname)
                    an["mode"] = "reach"
                    res["subs"][sname] = an
                    log(f"r/{sname}: RSS bloccato ({status}), letto con agent-reach: {len(new)} post con voti veri")
                    continue
                except Exception as e2:  # noqa: BLE001
                    status = f"{status}; agent-reach: {e2}"
            if not a.no_chain:
                try:
                    top, new, backend, note = fetch_chain(sname, a.t, a.limit)
                    an = analyse(top, new)
                    an["suggestions"] = suggestions(an, sname)
                    an.update(mode=backend, note=note)
                    res["subs"][sname] = an
                    log(f"r/{sname}: {mode} bloccato ({status}), letto via {backend}: {len(top)} top, {len(new)} nuovi")
                    continue
                except Exception as e3:  # noqa: BLE001
                    status = f"{status}; altri backend: {e3}"
            log(f"r/{sname}: blocked ({status})" + ("; manual steps written" if a.manual else ""))
            res["blocked"].append(dict(sub=sname, status=str(status)))
            if a.manual:
                with open(a.manual, "a", encoding="utf-8") as f:
                    f.write(MANUAL.format(status=status, date=today, sub=sname))
            continue
        an = analyse(top, new)
        an["suggestions"] = suggestions(an, sname)
        res["subs"][sname] = an
        log(f"r/{sname}: {len(top)} top, {len(new)} new")
    write_json(res, a.out)
    if a.md:
        L = [f"# Reddit: cosa funziona adesso ({today}, top della settimana contro i nuovi)", "",
             f"Modo: {mode}. {res['note']}. Campione piccolo: una settimana. I titoli sono riassunti, non copiati.", ""]
        for sname, an in res["subs"].items():
            L += [f"## r/{sname} (top {an['n_top']}, nuovi {an['n_new']})", "", "| Formato | Tra i migliori | Tra i nuovi | Rende × |", "|---|---|---|---|"]
            L += [f"| {r['label']} | {round(r['top_share'] * 100)} % | {round(r['new_share'] * 100)} % | {r['lift'] or '—'} |" for r in an["format"]]
            L += ["", "| Nel titolo | Tra i migliori | Tra i nuovi | Rende × |", "|---|---|---|---|"]
            L += [f"| {r['label']} | {round(r['top_share'] * 100)} % | {round(r['new_share'] * 100)} % | {r['lift'] or '—'} |" for r in an["features"] if r["top_share"] >= 0.05]
            L += [""] + [f"- {x}" for x in an["suggestions"]] + [""]
        if res["blocked"]:
            L += ["## Bloccati", ""] + [f"- r/{b['sub']}: {b['status']} → passi manuali in `ricerche-manuali.md`" for b in res["blocked"]]
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(L) + "\n")
        log(f"wrote {a.md}")


if __name__ == "__main__":
    main()
