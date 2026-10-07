#!/usr/bin/env python3
"""Store page + trailer analysis of the comparables, and how those features relate to how the games performed.

For each Steam app id it measures, automatically and from public data:
  page    : short description length, long description length/words, GIFs, other images, looping videos,
            headings, bullet items, screenshots, trailers, languages, achievements, categories, demo, price...
  trailer : duration (MP4 header with tiny HTTP Range reads, or the HLS / DASH playlist: Steam now serves trailers
            as adaptive streams, usually without any MP4; no video is downloaded for this) and, when `ffmpeg`
            is installed, cut analysis of the first seconds: time to first cut, cuts in the first 5 s,
            average shot length. With --frames-dir it also saves frames at 0/2/5/10/20/30 s so the hook can be
            JUDGED by looking at them (the tool measures pacing, it cannot understand what the hook is).
  outcome : Steam review count, % positive, reviews per year since release (a proxy for sales, age-corrected).
`analyze` then gives, per feature, quartiles across the comparables, the median of the best third (by reviews
per year) vs the rest, and Spearman rank correlations with log(reviews per year) and % positive.

Honest limits: a handful of comparables makes correlations weak (the report prints n); correlation is not
causation (budget, genre, timing and luck confound); the tool never decides what a good hook is.

Commands:
  fetch   APPID... [--ids-file F] [--frames-dir D] [--no-trailer] -o pages.json
  analyze pages.json [--md store_bench.md] [-o analysis.json]
  run     APPID... [...]  (fetch + analyze)

Examples:
  python store_bench.py run 1599600 728880 --ids-file comps_ids.txt --frames-dir launch/_raw/hooks \\
      -o launch/_raw/store_pages.json --md launch/_raw/store_bench.md
"""
from __future__ import annotations

import argparse
import datetime
import html as htmllib
import math
import os
import re
import shutil
import statistics
import subprocess
import struct
import urllib.parse
from common import get_text, http_range, load_json, log, read_list, safe_json, set_rate, write_json, write_output

MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
FEATURES = ["short_desc_chars", "desc_chars", "desc_words", "gifs", "looping_videos", "images", "headings", "bullets", "screenshots",
            "trailers", "trailer_s", "time_to_first_cut_s", "cuts_first_5s", "avg_shot_s_first_30s", "languages", "achievements",
            "categories_n", "has_demo", "price"]


# ----------------------------------------------------------------------------- page
def strip_tags(h: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def analyze_html(h: str) -> dict:
    h = h or ""
    text = strip_tags(h)
    return dict(desc_chars=len(text), desc_words=len(text.split()),
                gifs=len(re.findall(r"<img[^>]+\.gif", h, re.I)), images=len(re.findall(r"<img\b", h, re.I)),
                looping_videos=len(re.findall(r"<video\b", h, re.I)), headings=len(re.findall(r"<h[1-4]\b", h, re.I)),
                bullets=len(re.findall(r"<li\b", h, re.I)))


def parse_release(s: str | None):
    s = (s or "").strip()
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%b %Y", "%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def page_features(appid: int, cc: str, lang: str) -> dict:
    d = safe_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}&l={lang}")
    d = (d.get(str(appid)) or {}).get("data") or {}
    r = safe_json(f"https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all&num_per_page=0&filter=all").get("query_summary") or {}
    po, rd = d.get("price_overview") or {}, d.get("release_date") or {}
    langs = re.split(r"\*?languages with full audio support", strip_tags(d.get("supported_languages") or ""))[0]
    movies = d.get("movies") or []
    main = next((m for m in movies if m.get("highlight")), movies[0] if movies else None)
    rel = parse_release(rd.get("date"))
    years = max(((datetime.date.today() - rel).days / 365.25) if rel and not rd.get("coming_soon") else 0, 0)
    total, pos = r.get("total_reviews"), r.get("total_positive")
    o = dict(appid=appid, name=d.get("name"), url=f"https://store.steampowered.com/app/{appid}/", release_date=rd.get("date"),
             years_since_release=round(years, 2), short_desc=d.get("short_description"), short_desc_chars=len((d.get("short_description") or "").strip()),
             screenshots=len(d.get("screenshots") or []), trailers=len(movies), trailer_names=[m.get("name") for m in movies],
             languages=len([x for x in langs.split(",") if x.strip()]), achievements=(d.get("achievements") or {}).get("total"),
             categories_n=len(d.get("categories") or []), categories=[c["description"] for c in d.get("categories") or []],
             genres=[g["description"] for g in d.get("genres") or []], controller_support=d.get("controller_support"),
             has_demo=1 if d.get("demos") else 0, price=(po.get("initial") / 100 if po.get("initial") else (0 if d.get("is_free") else None)),
             metacritic=(d.get("metacritic") or {}).get("score"), recommendations=(d.get("recommendations") or {}).get("total"),
             reviews_total=total, pct_positive=round(100 * pos / total, 1) if total else None,
             reviews_per_year=round(total / max(years, 0.25), 1) if total is not None and years else None,
             _movies=movie_sources(main) if main else [])
    o.update(analyze_html(d.get("about_the_game") or d.get("detailed_description")))
    return o


# ----------------------------------------------------------------------------- trailer
# Steam used to serve trailers as MP4/WebM files; it now serves adaptive streams (HLS .m3u8 and DASH .mpd), often with no MP4 at all.
# Every URL found in a `movies` entry is classified by its file extension, so the tool works with any of them.
KIND_BY_EXT = {".mp4": "mp4", ".webm": "webm", ".m3u8": "hls", ".mpd": "dash"}
DURATION_ORDER = ("mp4", "hls", "dash", "webm")   # cheapest and most reliable first


def movie_sources(movie: dict) -> list[tuple[str, str]]:
    """[(kind, url)] for a Steam `movies` entry: any key, any nesting, ordered mp4 > hls > dash > webm."""
    found: list[tuple[str, str]] = []

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str) and v.startswith("http"):
            kind = KIND_BY_EXT.get(os.path.splitext(urllib.parse.urlparse(v).path.lower())[1])
            if kind and (kind, v) not in found:
                found.append((kind, v))
    walk(movie)
    return sorted(found, key=lambda kv: DURATION_ORDER.index(kv[0]))


def parse_iso_duration(s: str) -> float | None:
    """'PT1M32.5S' / 'PT90S' / 'PT1H2M3S' -> seconds."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", (s or "").strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, sec = (float(x) if x else 0.0 for x in m.groups())
    return round(d * 86400 + h * 3600 + mi * 60 + sec, 2)


def mpd_duration(url: str) -> float | None:
    """DASH: mediaPresentationDuration of the manifest, or the sum of the Period durations."""
    try:
        text = get_text(url)
    except Exception as e:  # noqa: BLE001
        log(f"WARN dash manifest {url[:60]}: {e}")
        return None
    m = re.search(r'mediaPresentationDuration="([^"]+)"', text)
    if m:
        return parse_iso_duration(m.group(1))
    periods = [parse_iso_duration(x) for x in re.findall(r'<Period[^>]*\bduration="([^"]+)"', text)]
    return round(sum(periods), 2) if periods and all(p is not None for p in periods) else None


def hls_duration(url: str, depth: int = 0) -> float | None:
    """HLS: sum of #EXTINF in the media playlist (a master playlist is followed to its lowest-bandwidth variant)."""
    try:
        text = get_text(url)
    except Exception as e:  # noqa: BLE001
        log(f"WARN hls playlist {url[:60]}: {e}")
        return None
    if "#EXT-X-STREAM-INF" in text and depth < 2:
        lines = [ln.strip() for ln in text.splitlines()]
        best = None
        for i, ln in enumerate(lines):
            if ln.startswith("#EXT-X-STREAM-INF"):
                bw = re.search(r"BANDWIDTH=(\d+)", ln)
                nxt = next((x for x in lines[i + 1:] if x and not x.startswith("#")), None)
                if nxt and (best is None or int(bw.group(1) if bw else 10 ** 12) < best[0]):
                    best = (int(bw.group(1) if bw else 10 ** 12), nxt)
        return hls_duration(urllib.parse.urljoin(url, best[1]), depth + 1) if best else None
    durations = re.findall(r"#EXTINF:([0-9.]+)", text)
    return round(sum(float(x) for x in durations), 2) if durations else None


def ffprobe_duration(src: str) -> float | None:
    """Last resort for any format, if ffprobe is installed."""
    if not shutil.which("ffprobe"):
        return None
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True, timeout=120)
        return round(float(p.stdout.strip().splitlines()[0]), 2)
    except Exception:  # noqa: BLE001
        return None


def trailer_duration(kind: str, url: str) -> float | None:
    d = {"mp4": mp4_duration, "hls": hls_duration, "dash": mpd_duration}.get(kind, lambda _u: None)(url)
    return d if d is not None else ffprobe_duration(url)


def mp4_duration(url: str, max_hops: int = 12) -> float | None:
    """Duration in seconds from the MP4 `moov/mvhd` box, walking top-level boxes with 16-byte Range reads."""
    off = 0
    for _ in range(max_hops):
        try:
            head, total, status = http_range(url, off, 16)
        except Exception as e:  # noqa: BLE001
            log(f"WARN mp4 header {url[:60]}: {e}")
            return None
        if status != 206 and off:
            return None  # server ignores Range: cannot skip boxes
        if len(head) < 8:
            return None
        size, typ = struct.unpack(">I4s", head[:8])
        hdr = 8
        if size == 1 and len(head) >= 16:
            size, hdr = struct.unpack(">Q", head[8:16])[0], 16
        if typ == b"moov":
            size = size or (total - off if total else 0)
            if not 8 < size <= 16 * 1024 * 1024:
                return None
            box, _, _ = http_range(url, off, size)
            i = box.find(b"mvhd")
            if i < 0:
                return None
            v = box[i + 4]
            if v == 1:
                ts, dur = struct.unpack(">IQ", box[i + 24:i + 36])
            else:
                ts, dur = struct.unpack(">II", box[i + 16:i + 24])
            return round(dur / ts, 2) if ts else None
        if size == 0 or (total and off + size >= total):
            return None
        off += size
    return None


def scene_cuts(src: str, seconds: int = 30, threshold: float = 0.3) -> list[float] | None:
    """Timestamps (s) of scene changes in the first `seconds`, via ffmpeg; None if ffmpeg is missing or fails."""
    if not shutil.which("ffmpeg"):
        return None
    try:
        p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-t", str(seconds), "-i", src, "-an", "-vf",
                            f"select=gt(scene\\,{threshold}),showinfo", "-f", "null", "-"], capture_output=True, text=True, timeout=180)
    except Exception as e:  # noqa: BLE001
        log(f"WARN ffmpeg: {e}")
        return None
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", p.stderr)]


def pacing(cuts: list[float] | None, window: int = 30) -> dict:
    """Cut statistics over the first `window` seconds (the trailer length if it is shorter than 30 s)."""
    if cuts is None:
        return dict(time_to_first_cut_s=None, cuts_first_5s=None, avg_shot_s_first_30s=None)
    cuts = [c for c in cuts if c > 0.1]  # the very first frame is not a cut
    return dict(time_to_first_cut_s=round(cuts[0], 2) if cuts else None, cuts_first_5s=sum(1 for c in cuts if c <= 5),
                avg_shot_s_first_30s=round(window / (len(cuts) + 1), 2))


def save_frames(src: str, outdir: str, appid: int, times=(0, 2, 5, 10, 20, 30)) -> list[str]:
    if not shutil.which("ffmpeg"):
        return []
    os.makedirs(outdir, exist_ok=True)
    out = []
    for t in times:
        path = os.path.join(outdir, f"{appid}_{t:02d}s.jpg")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", src, "-frames:v", "1", "-q:v", "3", path],
                       capture_output=True, timeout=120)
        if os.path.exists(path):
            out.append(path)
    return out


def trailer_features(o: dict, frames_dir: str | None) -> None:
    """Trailer duration, pacing and hook frames from whichever video format Steam provides."""
    sources = o.pop("_movies", None)
    if sources is None and o.get("_movie"):   # older callers: a single MP4 URL
        sources = [("mp4", o["_movie"])]
    o.pop("_movie", None)
    o.update(trailer_s=None, trailer_url=None, trailer_kind=None, trailer_formats=[k for k, _ in (sources or [])], hook_frames=[], **pacing(None))
    if not sources:
        return
    kind, url = sources[0]
    for k, u in sources:                      # first format whose duration can be read
        d = trailer_duration(k, u)
        if d is not None:
            kind, url, o["trailer_s"] = k, u, d
            break
    o.update(trailer_url=url, trailer_kind=kind)
    cuts = scene_cuts(url)
    o.update(pacing(cuts, int(min(30, o["trailer_s"] or 30))))
    o["ffmpeg"] = cuts is not None
    if frames_dir:
        o["hook_frames"] = save_frames(url, frames_dir, o["appid"])


# ----------------------------------------------------------------------------- statistics
def quantile(vals: list[float], q: float) -> float:
    v = sorted(vals)
    pos = q * (len(v) - 1)
    lo = int(pos)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (pos - lo)


def ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r, i = [0.0] * len(vals), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 4 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 2) if den else None


def strength(rho, n):
    if rho is None:
        return "n/d"
    a = abs(rho)
    s = "forte" if a >= 0.5 else "moderata" if a >= 0.3 else "debole o assente"
    return s + (" (campione piccolo)" if n < 12 else "")


def analyze(rows: list[dict]) -> dict:
    rows = [r for r in rows if r.get("reviews_per_year")]
    res = dict(n_games=len(rows), features=[], note="")
    if len(rows) < 4:
        res["note"] = "Meno di 4 giochi con dati di recensioni: nessuna statistica affidabile."
    ordered = sorted(rows, key=lambda r: -r["reviews_per_year"])
    k = max(1, len(rows) // 3) if len(rows) >= 9 else max(1, len(rows) // 2)
    top, rest = ordered[:k], ordered[k:]
    res["top_group"] = dict(size=len(top), definition="best third by reviews per year" if len(rows) >= 9 else "best half by reviews per year (few games)",
                            games=[r["name"] for r in top])
    for f in FEATURES:
        pairs = [(r[f], r) for r in rows if isinstance(r.get(f), (int, float))]
        if len(pairs) < 3:
            continue
        v = [float(p[0]) for p in pairs]
        tv = [float(r[f]) for r in top if isinstance(r.get(f), (int, float))]
        rv = [float(r[f]) for r in rest if isinstance(r.get(f), (int, float))]
        lrpy = [math.log(r["reviews_per_year"]) for _, r in pairs]
        pp = [(float(p[0]), r["pct_positive"]) for p in pairs for r in [p[1]] if r.get("pct_positive") is not None]
        rho_v, rho_p = spearman(v, lrpy), spearman([a for a, _ in pp], [b for _, b in pp])
        res["features"].append(dict(feature=f, n=len(v), p25=round(quantile(v, .25), 2), median=round(quantile(v, .5), 2), p75=round(quantile(v, .75), 2),
                                    median_top=round(statistics.median(tv), 2) if tv else None, median_rest=round(statistics.median(rv), 2) if rv else None,
                                    rho_reviews_per_year=rho_v, strength_reviews=strength(rho_v, len(v)), rho_pct_positive=rho_p, strength_pct=strength(rho_p, len(pp))))
    return res


def md(res: dict, rows: list[dict], today: str) -> str:
    L = ["# Benchmark di pagina store e trailer (calcolato da `store_bench.py`)", "",
         f"**{res['n_games']} giochi** analizzati il {today}. Gruppo migliore = {res.get('top_group', {}).get('definition', 'n/d')} "
         f"({', '.join(res.get('top_group', {}).get('games', []))}). Esito = recensioni Steam per anno dall'uscita (proxy delle vendite, corretto per l'età).", ""]
    if res["note"]:
        L += [f"**{res['note']}**", ""]
    L += ["## Distribuzione e confronto migliori vs resto", "", "| Caratteristica | n | p25 | mediana | p75 | Mediana migliori | Mediana resto |", "|---|---|---|---|---|---|---|"]
    L += [f"| {f['feature']} | {f['n']} | {f['p25']} | {f['median']} | {f['p75']} | {f['median_top']} | {f['median_rest']} |" for f in res["features"]]
    L += ["", "## Correlazione di rango (Spearman) con i risultati", "", "| Caratteristica | ρ con recensioni/anno | Forza | ρ con % positive | Forza |", "|---|---|---|---|---|"]
    L += [f"| {f['feature']} | {f['rho_reviews_per_year']} | {f['strength_reviews']} | {f['rho_pct_positive']} | {f['strength_pct']} |" for f in res["features"]]
    L += ["", "## Giochi", "", "| Gioco | Recensioni | % pos. | Trailer (s) | 1° taglio (s) | Short desc | GIF | Screenshot |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['name']} | {r.get('reviews_total')} | {r.get('pct_positive')} | {r.get('trailer_s')} | {r.get('time_to_first_cut_s')} | {r.get('short_desc_chars')} | {r.get('gifs')} | {r.get('screenshots')} |"
          for r in sorted(rows, key=lambda r: -(r.get("reviews_per_year") or 0))]
    L += ["", "## Come usarlo e limiti", "",
          "- Usa mediane e quartili dei migliori come **punto di partenza** per i testi della Fase 6B, non come regola.",
          "- Una correlazione forte con pochi giochi è un indizio da verificare; non dimostra che cambiare quella caratteristica faccia vendere. Budget, genere, tempismo e fortuna confondono.",
          "- Il tool misura il ritmo del trailer (durata, tagli); l'**hook** vero si giudica guardando i fotogrammi in `hook_frames` (0, 2, 5, 10, 20, 30 s).",
          "- Senza `ffmpeg` mancano tagli e fotogrammi: durata e pagina restano disponibili."]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- cli
def do_fetch(a) -> list[dict]:
    ids = [int(x) for x in read_list(a.appids, a.ids_file)]
    if not ids:
        raise SystemExit("no app ids given")
    rows = []
    for i in ids:
        o = page_features(i, a.cc, a.lang)
        if a.no_trailer:
            o.pop("_movies", None)
            o.pop("_movie", None)
        else:
            trailer_features(o, a.frames_dir)
        rows.append(o)
        log(f"{i} | {o['name']} | reviews {o['reviews_total']} | trailer {o.get('trailer_s')}s | gifs {o['gifs']} | desc {o['desc_chars']} chars")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=float, default=1.2)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "run"):
        s = sub.add_parser(name)
        s.add_argument("appids", nargs="*"); s.add_argument("--ids-file"); s.add_argument("--cc", default="us"); s.add_argument("--lang", default="english")
        s.add_argument("--frames-dir"); s.add_argument("--no-trailer", action="store_true"); s.add_argument("-o", "--out", default="-")
        if name == "run":
            s.add_argument("--md"); s.add_argument("--analysis-out")
        s.set_defaults(fn=name)
    s = sub.add_parser("analyze"); s.add_argument("pages"); s.add_argument("--md"); s.add_argument("-o", "--out"); s.set_defaults(fn="analyze")
    a = ap.parse_args()
    set_rate(a.rate)
    today = datetime.date.today().isoformat()
    if a.fn == "fetch":
        write_output(do_fetch(a), a.out)
        return
    rows = do_fetch(a) if a.fn == "run" else load_json(a.pages)
    if a.fn == "run":
        write_output(rows, a.out)
    res = analyze(rows)
    out_md = md(res, rows, today)
    if a.md:
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(out_md)
        log(f"wrote {a.md}")
    else:
        print(out_md)
    path = a.out if a.fn == "analyze" else getattr(a, "analysis_out", None)
    if path and path != "-":
        write_json(res, path)


if __name__ == "__main__":
    main()
