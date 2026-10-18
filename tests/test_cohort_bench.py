"""cohort_bench offline: volume, fetch (resumable), junk filter, sheets (HTML fallback), grades and report, with fixture JSON."""
import os, sys, json, csv, urllib.parse, io, contextlib, tempfile, shutil
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "scripts", "research"))
import common
FX = json.load(open(os.path.join(here, "fixtures", "cohort_bench.json"), encoding="utf-8"))
calls = {"details": 0}


def row_html(r):
    return (f'<a href="https://store.steampowered.com/app/{r["appid"]}/x/"\n data-ds-appid="{r["appid"]}" data-ds-itemkey="App_{r["appid"]}" '
            f'data-ds-tagids="[{",".join(map(str, r["tagids"]))}]" data-ds-descids="[{",".join(map(str, r["descids"]))}]" data-ds-crtrids="[7]" class="search_result_row">'
            f'<span class="title">{r["name"]}</span><div class="search_released responsive_secondrow">\n {r["date"]} </div>'
            f'<div class="search_price_discount_combined responsive_secondrow" data-price-final="{r["price"]}"></div></a>')


def fake(url, **kw):
    u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if u.path.startswith("/search/results"):
        st, ct = int(qs["start"][0]), int(qs["count"][0])
        rows = FX["search"][st:st + ct]
        return json.dumps({"success": 1, "results_html": "".join(map(row_html, rows)), "total_count": len(FX["search"]), "start": st}).encode()
    if "populartags" in u.path:
        return json.dumps(FX["tags"]).encode()
    if "appdetails" in u.path:
        calls["details"] += 1
        aid = qs["appids"][0]; d = FX["details"].get(aid)
        if d:
            d = dict(d, about_the_game=("x" * 400) if d["about_the_game"] == "LONG" else d["about_the_game"], type="game")
        return json.dumps({aid: {"success": True, "data": d} if d else {"success": False}}).encode()
    if "appreviewhistogram" in u.path:
        aid = u.path.split("/")[-1]; n = FX["reviews"].get(aid, 0)
        if aid == "1009":   # free game that was in Early Access since 2024: 30 old reviews, 10 after its 1.0 in July 2026
            return json.dumps({"success": 1, "results": {"start_date": 1704067200, "rollup_type": "month", "rollups": [
                {"date": 1704067200, "recommendations_up": 25, "recommendations_down": 5}, {"date": 1782864000, "recommendations_up": 8, "recommendations_down": 2}]}}).encode()
        return json.dumps({"success": 1, "results": {"start_date": 1784160000, "rollup_type": "week", "rollups": [{"date": 1784160000, "recommendations_up": n, "recommendations_down": 0}]}}).encode()
    if "appreviews" in u.path:
        n = FX["reviews"].get(u.path.split("/")[-1], 0)
        return json.dumps({"success": 1, "query_summary": {"total_reviews": n, "total_positive": int(n * .8), "review_score_desc": "x"}}).encode()
    if "example.invalid" in u.netloc or "steamstatic" in u.netloc:
        return b"\xff\xd8" + b"0" * 900
    raise AssertionError(url)


common.http_get = fake; common.set_rate(0)
import cohort_bench as cb
import time as _time
_real_sleep = _time.sleep
cb.have_pil = lambda: False          # force the stdlib HTML fallback for sheets
cb.shutil.which = lambda name: None
d = tempfile.mkdtemp()


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(out):
        cb.main(["--dir", d, "--today", "2026-07-21"] + list(argv))
    return out.getvalue()


# ---- volume: 7 full days before "today", past-the-end page is a normal end (no backoff sleep)
cb.time.sleep = lambda s: (_ for _ in ()).throw(AssertionError("unexpected backoff"))
txt = run("volume", "--days", "7", "--rate", "0")
v = json.load(open(os.path.join(d, "volume.json"), encoding="utf-8"))
per = {x["date"]: x["games"] for x in v["per_day"]}
assert per["2026-07-20"] == 2 and per["2026-07-16"] == 4 and per["2026-07-15"] == 6 and per["2026-07-14"] == 0 and v["summary"]["total"] == 12, per
assert v["incomplete_offsets"] == [] and "mediana" in txt
cb.time.sleep = _real_sleep

# ---- fetch: window by binary search, details + reviews, resumable (second run makes no new calls)
run("fetch", "--from", "2026-07-15", "--to", "2026-07-16", "--rate", "0", "--rate-reviews", "0", "--page", "4")
c = json.load(open(os.path.join(d, "cohort.json"), encoding="utf-8"))
assert c["n"] == 10 and c["n_no_details"] == 1, (c["n"], c["n_no_details"])
g = {r["appid"]: r for r in c["games"]}
assert g[1001]["price"] == 7.99 and g[1001]["n_movies"] == 2 and g[1001]["early_access"] and g[1001]["n_languages"] == 3 and g[1001]["copies_low"] == 6000
assert g[1009]["graduate"] and g[1009]["reviews_total"] == 10 and g[1009]["reviews_total_raw"] == 40 and c["n_graduates"] == 1
assert not g[1001]["graduate"] and g[1001]["reviews_total"] == 300
assert "Physics" in g[1001]["tags"] and g[1002]["has_demo"] and g[1009]["is_free"] and g[1009]["price"] == 0.0
before = calls["details"]
run("fetch", "--from", "2026-07-15", "--to", "2026-07-16", "--rate", "0", "--rate-reviews", "0")
assert calls["details"] == before, "resume: cached apps (including success:false answers) are not fetched again"

# ---- filter: every junk rule with its reason
txt = run("filter")
f = {int(r["appid"]): r for r in csv.DictReader(open(os.path.join(d, "filtered.csv"), encoding="utf-8-sig"))}
assert f[1001]["status"] == f[1002]["status"] == f[1003]["status"] == "keep"
assert "thin_page" in f[1004]["reasons"] and "adult" in f[1005]["reasons"] and "shovel_tags" in f[1005]["reasons"]
assert all("flip_dev" in f[i]["reasons"] for i in (1006, 1007, 1008)) and "free_thin" in f[1009]["reasons"] and f[1009]["status"] == "not_new" and f[1010]["status"] == "missing"
assert "asset flip" in txt

# ---- sheets: HTML fallback without Pillow / ffmpeg, grades.csv template, existing grades kept
ref = os.path.join(d, "ref.png"); open(ref, "wb").write(b"x")
txt = run("sheets", "--reference", ref, "--rate", "0", "--per-sheet", "2")
assert os.path.exists(os.path.join(d, "sheets", "sheet_01.html")) and os.path.exists(os.path.join(d, "sheets", "sheet_02.html"))
assert "RIFERIMENTO" in open(os.path.join(d, "sheets", "sheet_01.html"), encoding="utf-8").read() and "html" in txt
gp = os.path.join(d, "grades.csv")
rows = list(csv.DictReader(open(gp, encoding="utf-8-sig")))
assert [int(r["appid"]) for r in rows] == [1001, 1002, 1003]
for r in rows:
    r["grade"] = {"1001": "B", "1002": "A", "1003": "c"}[r["appid"]]
with contextlib.redirect_stderr(io.StringIO()): common.write_csv(rows, gp)
with contextlib.redirect_stderr(io.StringIO()):
    run("sheets", "--rate", "0")
assert [r["grade"] for r in csv.DictReader(open(gp, encoding="utf-8-sig"))] == ["B", "A", "c"], "re-running sheets must keep the grades"

# ---- report: tiers, Boxleiter range, popular definition, of-20, mine, subsets
md = os.path.join(d, "r.md")
run("report", "--mine-price", "7.99", "--md", md)
r = json.load(open(os.path.join(d, "report.json"), encoding="utf-8"))
t = r["tiers"]
assert t["A"]["n"] == 1 and t["B"]["n"] == 1 and t["C"]["n"] == 1 and t["junk"]["n"] == 5 and r["n_missing"] == 1 and r["n_not_new"] == 1
assert t["A"]["popular"]["k_low"] == 1 and t["B"]["popular"]["k_low"] == 0 and t["B"]["popular"]["k_high"] == 1   # 300 reviews: x20 = 6,000, x60 = 18,000
assert t["C"]["copies100"]["k_low"] == 0 and t["C"]["copies100"]["k_high"] == 1   # 3 reviews: 60..180 copies
assert t["junk"]["gross800"]["k_low"] == 0
assert r["of20_ab"]["popular"] == (10.0, 20.0) or r["of20_ab"]["popular"] == [10.0, 20.0]
assert r["mine"]["gross_median"] == [round(6000 * 7.99), round(18000 * 7.99)]
assert r["volume"]["summary"]["total"] == 12 and "non nuovi" in open(md, encoding="utf-8").read() and r["b_split"]["n_win"] == 1
text = open(md, encoding="utf-8").read()
for s in ("Quanti giochi escono al giorno", "Su 20 giochi", "[STIMA]", "[FATTO]", "Limiti", "un solo valutatore", "Campione troppo piccolo"):
    assert s in text, s
run("report", "--price-min", "5", "--price-max", "15", "--genres", "casual,physics")
r = json.load(open(os.path.join(d, "report.json"), encoding="utf-8"))
assert r["subset"]["n"] == 2 and r["tiers"]["C"]["n"] == 0, r["subset"]   # 1003 costs 4.99
assert cb.wilson(0, 10)[0] == 0.0 and cb.wilson(10, 10)[1] == 100.0
shutil.rmtree(d, ignore_errors=True)
print("cohort_bench ok: volume, fetch with resume, histogram (Early Access graduates), 7 junk rules, sheets fallback, tiers and report")
