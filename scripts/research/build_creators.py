#!/usr/bin/env python3
"""Build a prioritized creators CSV from yt_research.py (subs) + social_verify.py outputs.

Inputs
  --youtube FILE      JSON from `yt_research.py subs` (repeatable)
  --social FILE       JSON from `social_verify.py` (repeatable; tiktok/instagram/twitch/youtube rows)
  --config FILE       optional JSON with manual curation:
      {
        "exclude":   ["Channel name", ...],                 # drop these (names or URLs)
        "lang":      {"Channel name": "IT", ...},           # language override per creator
        "topic_fit": {"PlateUp!": "cooking + roguelite"},   # why a topic matters (goes in `perche`)
        "notes":     {"<video or channel url>": "free note"},# extra note per row
        "topics":    {"<social video url>": "Game covered"}   # topic for social rows
      }

Language = config.lang > YouTube channel country (IT/DE/FR/ES/BR/PT/TR/PL/RU/JP) > --default-lang.
Segment by subs: nano <10k, micro <100k, medio <1M, grande >=1M.
Priority: A = subs < --tier-a-max and lang in --priority-langs
          B = (subs < --tier-b-max and lang in --priority-langs) or subs < --tier-a-max
          C = rest.   Social rows without follower counts: A if lang prioritized else B.

Example:
  python build_creators.py --youtube yt_shortlist.json --social tt_verified.json --config curation.json \
      --priority-langs IT,EN -o creators.csv
"""
from __future__ import annotations

import argparse
import datetime
from collections import Counter
from common import load_json, log, write_csv

COUNTRY_LANG = {"IT": "IT", "DE": "DE", "AT": "DE", "FR": "FR", "ES": "ES", "MX": "ES", "AR": "ES", "BR": "PT",
                "PT": "PT", "TR": "TR", "PL": "PL", "RU": "RU", "JP": "JA", "US": "EN", "GB": "EN", "CA": "EN", "AU": "EN"}
PLAT = {"tiktok": "TikTok", "youtube": "YouTube", "instagram": "Instagram", "twitch": "Twitch"}
FIELDS = ["piattaforma", "nome", "url", "lingua", "iscritti_follower", "segmento", "priorita", "gioco_coperto",
          "titolo_video", "url_video", "data_pubblicazione_circa", "views", "perche", "contatto", "data_verifica"]


def rel_to_date(when: str | None, days: int | None, ref: datetime.date) -> str:
    if when and len(when) >= 10 and when[4] == "-":
        return when[:10]
    if days is None:
        from yt_research import rel2days
        days = rel2days(when or "")
    return (ref - datetime.timedelta(days=days)).isoformat() if days is not None else ""


def segment(s: int) -> str:
    return "nano (<10k)" if s < 10_000 else "micro (10k-100k)" if s < 100_000 else \
        "medio (100k-1M)" if s < 1_000_000 else "grande (>1M)"


def priority(s: int | None, lang: str, langs: set, a_max: int, b_max: int) -> str:
    if s is None:
        return "A" if lang in langs else "B"
    if s < a_max and lang in langs:
        return "A"
    if (s < b_max and lang in langs) or s < a_max:
        return "B"
    return "C"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--youtube", action="append", default=[])
    ap.add_argument("--social", action="append", default=[])
    ap.add_argument("--config")
    ap.add_argument("--priority-langs", default="EN", help="comma separated, e.g. IT,EN")
    ap.add_argument("--default-lang", default="EN")
    ap.add_argument("--tier-a-max", type=int, default=200_000)
    ap.add_argument("--tier-b-max", type=int, default=1_000_000)
    ap.add_argument("--ref-date", default=datetime.date.today().isoformat(),
                    help="date the search ran (to convert '2w ago'); default today")
    ap.add_argument("-o", "--out", default="creators.csv")
    a = ap.parse_args()

    cfg = load_json(a.config) if a.config else {}
    excl = set(cfg.get("exclude", []))
    lang_over, fit, notes = cfg.get("lang", {}), cfg.get("topic_fit", {}), cfg.get("notes", {})
    langs = {x.strip().upper() for x in a.priority_langs.split(",") if x.strip()}
    ref = datetime.date.fromisoformat(a.ref_date)
    today = datetime.date.today().isoformat()
    rows = []
    no_subs = 0

    for path in a.youtube:
        for c in load_json(path):
            name, url = c["ch"].strip(), "https://www.youtube.com" + c["url"]
            if name in excl or url in excl:
                continue
            if c.get("subs") is None:
                no_subs += 1
                continue
            s = c["subs"]
            lang = lang_over.get(name) or c.get("lang") or COUNTRY_LANG.get((c.get("country") or "").upper()) or a.default_lang
            v = c["vids"][0]
            topic = v.get("topic") or v.get("game") or v.get("query", "")
            why = f"Video recente su {topic}" + (f" ({fit[topic]})" if topic in fit else "") + \
                  f"; {len(c['vids'])} video pertinenti trovati"
            vurl = "https://www.youtube.com/watch?v=" + v["vid"]
            if notes.get(vurl) or notes.get(url):
                why += "; " + (notes.get(vurl) or notes.get(url))
            rows.append(dict(piattaforma="YouTube", nome=name, url=url, lingua=lang, iscritti_follower=s,
                             segmento=segment(s), priorita=priority(s, lang, langs, a.tier_a_max, a.tier_b_max),
                             gioco_coperto=topic, titolo_video=v["title"], url_video=vurl,
                             data_pubblicazione_circa=rel_to_date(v.get("when"), v.get("days"), ref),
                             views=v.get("views") if v.get("views") is not None else "",
                             perche=why, contatto="contatto da trovare sul canale", data_verifica=today))

    for path in a.social:
        for r in load_json(path):
            if not r.get("ok") or r.get("author") in excl or r.get("author_url") in excl:
                continue
            name = r.get("author") or ""
            lang = lang_over.get(name) or lang_over.get(r.get("author_url", "")) or a.default_lang
            why = notes.get(r["url"]) or notes.get(r.get("author_url", "")) or (r.get("title") or "")[:120]
            src = {"tiktok": "oEmbed TikTok; data ricavata dall'ID del video", "youtube": "oEmbed YouTube",
                   "instagram": "oEmbed Instagram (Graph API)", "twitch": "Twitch Helix API"}.get(r.get("platform"), "")
            rows.append(dict(piattaforma=PLAT.get(r.get("platform"), r.get("platform") or ""),
                             nome=name, url=r.get("author_url") or "", lingua=lang,
                             iscritti_follower=("usa yt_research.py subs" if r.get("platform") == "youtube"
                                               else "non verificabile senza login"), segmento="da verificare",
                             priorita=priority(None, lang, langs, a.tier_a_max, a.tier_b_max),
                             gioco_coperto=cfg.get("topics", {}).get(r["url"], ""), titolo_video=(r.get("title") or "")[:150],
                             url_video=r["url"], data_pubblicazione_circa=r.get("date", ""),
                             views=r.get("views") or "", perche=f"{why} (verificato con {src})",
                             contatto="contatto da trovare sul canale", data_verifica=today))

    order, lord = {"A": 0, "B": 1, "C": 2}, {l: i for i, l in enumerate(a.priority_langs.upper().split(","))}
    rows.sort(key=lambda r: (order[r["priorita"]], lord.get(r["lingua"], 99), r["piattaforma"] == "YouTube",
                             r["iscritti_follower"] if isinstance(r["iscritti_follower"], int) else 0))
    if no_subs:
        log(f"WARN {no_subs} YouTube channels skipped: subscriber count unknown (hidden or unreadable); check them by hand")
    write_csv(rows, a.out, FIELDS)
    log("priorita", dict(Counter(r["priorita"] for r in rows)), "| lingua", dict(Counter(r["lingua"] for r in rows)),
        "| piattaforma", dict(Counter(r["piattaforma"] for r in rows)))


if __name__ == "__main__":
    main()
