"""Offline: private keys loading (never printed), cohort dataset update / re-checks / calibrate, calc_econ base-rate scenarios,
market_tracker snapshots, estimates, manual checks file, RSS parsing, social collection with entity matching, marketing patterns."""
import os as _os
_os.environ["GLS_REACH"] = "off"   # offline: never the real Agent Reach
import os, sys, json, csv, io, contextlib, tempfile, datetime as dt, urllib.parse, shutil
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "scripts", "research"))
home = tempfile.mkdtemp()
os.environ["GLS_HOME"] = home
for k in ("YOUTUBE_API_KEY", "STEAM_WEB_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET", "GLS_ENV_FILE", "REDDIT_USER_AGENT"):
    os.environ.pop(k, None)
import common

# ---- private keys: loaded by name, existing env wins, values never printed anywhere
SECRET = "FAKEKEY_do_not_print_123"
with open(os.path.join(home, ".env"), "w", encoding="utf-8") as f:
    f.write(f"# comment\nYOUTUBE_API_KEY={SECRET}\nSTEAM_WEB_API_KEY='{SECRET}2'\nexport REDDIT_USER_AGENT=test-agent\n")
os.environ["STEAM_WEB_API_KEY"] = "from-environment"
names = common.load_env()
assert set(names) == {"YOUTUBE_API_KEY", "REDDIT_USER_AGENT"} and os.environ["YOUTUBE_API_KEY"] == SECRET and os.environ["STEAM_WEB_API_KEY"] == "from-environment"
os.environ.pop("STEAM_WEB_API_KEY")

D = lambda s: int(dt.datetime(*map(int, s.split("-")), tzinfo=dt.timezone.utc).timestamp())  # noqa: E731
REL = "2026-01-05"
def hist_for(total, weeks=30, pre=0):
    rel = dt.date.fromisoformat(REL)
    rolls = [dict(date=D((rel - dt.timedelta(days=200)).isoformat()), recommendations_up=pre, recommendations_down=0)] if pre else []
    per = max(1, total // weeks) if total else 0
    rolls += [dict(date=D((rel + dt.timedelta(days=7 * i)).isoformat()), recommendations_up=per, recommendations_down=0) for i in range(weeks)] if total else []
    return dict(rollup_type="week", start_date=rolls[0]["date"] if rolls else 0, rollups=rolls)

calls = {"yt": 0, "news": 0, "players": 0}
def fake(url, **kw):
    u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if "key" in qs:
        assert qs["key"][0] in (SECRET, SECRET + "2"), "unexpected key"
    if "appreviewhistogram" in u.path:
        aid = int(u.path.rsplit("/", 1)[1]); return json.dumps({"success": 1, "results": hist_for(aid % 1000)}).encode()
    if "appreviews" in u.path:
        aid = int(u.path.rsplit("/", 1)[1]); n = aid % 1000
        return json.dumps({"success": 1, "query_summary": {"total_reviews": n, "total_positive": int(n * .9)}}).encode()
    if "appdetails" in u.path:
        aid = qs["appids"][0]
        return json.dumps({aid: {"success": True, "data": {"name": f"Game {aid}", "is_free": False, "price_overview": {"initial": 799, "discount_percent": 20},
                                                          "release_date": {"date": "Jan 5, 2026"}, "developers": ["Duo Studio"], "publishers": [], "genres": [{"description": "Casual"}],
                                                          "supported_languages": "English, Italian"}}}).encode()
    if "GetNumberOfCurrentPlayers" in u.path:
        calls["players"] += 1; return json.dumps({"response": {"player_count": 40 + calls["players"], "result": 1}}).encode()
    if "steamspy" in u.netloc:
        return json.dumps({"owners": "20,000 .. 50,000"}).encode()
    if "GetNewsForApp" in u.path:
        calls["news"] += 1
        return json.dumps({"appnews": {"newsitems": [
            {"gid": "1", "title": "Demo out now for Steam Next Fest", "feedname": "steam_community_announcements", "date": D("2025-10-13"), "contents": "play the demo"},
            {"gid": "2", "title": "Patch 1.1 update", "feedname": "steam_community_announcements", "date": D("2026-02-01"), "contents": "fixes"},
            {"gid": "3", "title": "Press article", "feedname": "pcgamer", "date": D("2026-01-06"), "contents": ""}]}}).encode()
    if "googleapis.com" in u.netloc and u.path.endswith("/search"):
        calls["yt"] += 1
        items = [{"id": {"videoId": f"v{i}"}, "snippet": {"title": f"Tray Tumble gameplay part {i}", "description": "physics roguelite game https://store.steampowered.com/app/1001/",
                                                       "channelTitle": f"Creator {i}", "channelId": f"c{i}", "publishedAt": "2025-12-20T10:00:00Z"}} for i in range(4)]
        items += [{"id": {"videoId": "x9"}, "snippet": {"title": "Tumble dryer repair", "description": "how to fix your tumble dryer", "channelTitle": "Fixit",
                                                         "channelId": "f", "publishedAt": "2026-01-10T10:00:00Z"}}]
        return json.dumps({"items": items}).encode()
    if "googleapis.com" in u.netloc and u.path.endswith("/videos"):
        return json.dumps({"items": [{"id": f"v{i}", "statistics": {"viewCount": str(1000 * (i + 1))}} for i in range(4)]}).encode()
    if "reddit.com" in u.netloc:
        assert kw.get("headers", {}).get("User-Agent") == "test-agent"
        return ("<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'>"
                "<entry><id>t3_a</id><title>Tray Tumble - my physics roguelite demo is on Steam</title><link href='https://www.reddit.com/r/IndieDev/a'/>"
                "<category term='IndieDev'/><author><name>/u/duostudio</name></author><updated>2025-11-02T10:00:00+00:00</updated>"
                "<content type='html'>&lt;p&gt;wishlist https://store.steampowered.com/app/1001/&lt;/p&gt;</content></entry>"
                "<entry><id>t3_b</id><title>my tumble dryer broke</title><link href='https://www.reddit.com/r/appliances/b'/><category term='appliances'/>"
                "<author><name>/u/x</name></author><updated>2026-01-08T10:00:00+00:00</updated><content type='html'>help</content></entry></feed>").encode()
    raise AssertionError(url)
common.http_get = fake; common.set_rate(0)
import cohort_bench as cb, market_tracker as mt
from common import Throttle

def quiet(fn, *a, **kw):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        r = fn(*a, **kw)
    assert SECRET not in out.getvalue() + err.getvalue(), "a key value was printed"
    return r, out.getvalue()

# ---- a fetched cohort folder (what fetch/filter/sheets leave) -> dataset
work = os.path.join(home, "work"); os.makedirs(os.path.join(work, "apps"))
games, fl, gr = [], [], []
for i in range(60):
    aid = 2000 + i * 1000 + (5 + (i * 37) % 400)        # appid % 1000 = reviews in the fake
    grade = "B" if i < 40 else ("A" if i < 44 else "C")
    games.append(dict(appid=aid, name=f"G{i}", release_date=REL, price=7.99 if i % 2 else 12.99, genres=["Casual"], tags=["Physics"] if i % 3 == 0 else ["Puzzle"],
                      n_movies=2 if i % 2 else 1, n_screenshots=10, n_languages=8 if i % 2 else 1, has_demo=i % 2 == 0, early_access=False,
                      developers=[f"Dev{i}"], publishers=["Pub"] if i % 4 == 0 else [f"Dev{i}"], reviews_total=aid % 1000, header_image=f"https://x/{aid}.jpg"))
    fl.append(dict(appid=aid, status="keep", reasons=""))
    gr.append(dict(appid=aid, grade=grade if i < 50 else ""))      # 10 not graded yet
    with open(os.path.join(work, "apps", f"{aid}.json"), "w") as f:
        json.dump(dict(hist=hist_for(aid % 1000)), f)
json.dump(dict(read_on="2026-02-10", window=[REL, "2026-01-11"], games=games), open(os.path.join(work, "cohort.json"), "w"))
with contextlib.redirect_stderr(io.StringIO()):
    common.write_csv(fl, os.path.join(work, "filtered.csv")); common.write_csv(gr, os.path.join(work, "grades.csv"))
ds = os.path.join(home, "cohorts")
quiet(cb.main, ["--today", "2026-02-10", "update", "--import-dir", work, "--new-weeks", "0", "--max-requests", "0", "--no-volume"])
week = os.path.join(ds, "cohort_2026-01-05_2026-01-11.csv")
rows = list(csv.DictReader(open(week, encoding="utf-8-sig")))
assert len(rows) == 60 and all(r["reviews_d30"] != "" and r["reviews_d90"] == "" for r in rows), "only the 30-day milestone is reached on 2026-02-10"
assert sum(1 for r in rows if r["grade"]) == 50 and all(0 <= int(r["store_prior"]) <= 100 for r in rows)
# the user grades 10 more in the work folder; later re-check at 90 and 180 days (retroactive from the histogram)
for g in gr[50:]: g["grade"] = "C"
with contextlib.redirect_stderr(io.StringIO()): common.write_csv(gr, os.path.join(work, "grades.csv"))
_, out = quiet(cb.main, ["--today", "2026-07-20", "update", "--new-weeks", "0", "--rate-reviews", "0", "--no-volume"])
rows = list(csv.DictReader(open(week, encoding="utf-8-sig")))
assert sum(1 for r in rows if r["grade"]) == 60 and all(r["reviews_d90"] != "" and r["reviews_d180"] != "" for r in rows), out
r0 = rows[0]; assert int(r0["reviews_d30"]) <= int(r0["reviews_d90"]) <= int(r0["reviews_d180"]) <= int(r0["reviews_total_now"])
assert cb.last_full_week(dt.date(2026, 10, 13)) == (dt.date(2026, 10, 5), dt.date(2026, 10, 11))
assert cb.reviews_within(hist_for(0), REL, 30, 0) == 0

# ---- calibrate -> calibration.json
quiet(cb.main, ["--today", "2026-07-20", "calibrate"])
cal = json.load(open(os.path.join(home, "calibration.json"), encoding="utf-8"))
assert cal["primary"] == "d90" and cal["n_graded"] == 60 and cal["data_from"] == REL
tb = cal["milestones"]["d90"]["tiers"]["B"]
assert tb["n"] == 40 and tb["copies"]["median"][1] == 3 * tb["copies"]["median"][0] and 0 <= tb["popular"]["pct_low"] <= tb["popular"]["pct_high"] <= 100
assert sum(b["B"] for b in cal["distribution"]["buckets"]) == 40 and 0 < cal["concentration"]["top10"] <= 100
assert cal["milestones"]["d90"]["by_price"]["B"]["5-10"]["n"] == 20 and cal["b_factors"]["table"] and cal["controls"]["b_winners"]
g, label = cb.base_rate(cal, "B", 7.99, min_n=15); assert "5-10" in label and g["n"] == 20
g, label = cb.base_rate(cal, "B", 7.99, min_n=30); assert "tutti" in label and g["n"] == 40

# ---- calc_econ: base-rate scenarios next to the wishlist ones
import calc_econ
md = os.path.join(home, "econ.md")
sys.argv = ["x", "--price", "7.99", "--costs", "500", "--wishlists", "1000,3000,8000", "--conv", "0.1,0.2,0.3", "--calibration", "--tier", "B", "--md", md, "-o", os.path.join(home, "econ.json")]
quiet(calc_econ.main)
e = json.load(open(os.path.join(home, "econ.json"), encoding="utf-8"))
assert e["calibrated"]["n"] == 40 and len(e["calibrated"]["scenarios"]) == 4 and len(e["scenarios"]) == 3 and "calibration_data" not in e["inputs"]
assert "Scenari dal mercato reale" in open(md, encoding="utf-8").read()

# ---- market tracker: tracked set, snapshots on schedule, players sampling, estimates
m = os.path.join(home, "market")
quiet(mt.main, ["--market-dir", m, "add", "1001", "--role", "comp"])
assert mt.due_labels(dict(release_date="2026-01-05"), dt.datetime(2026, 1, 6, 12), set()) == ["h24"]
assert mt.due_labels(dict(release_date="2026-01-05"), dt.datetime(2026, 2, 10), {"h24", "h48", "w1"}) == ["m1"]
assert mt.due_labels(dict(release_date="2020-01-05"), dt.datetime(2026, 2, 10), set())[0].startswith("wk")
quiet(mt.main, ["--market-dir", m, "snapshot", "--now", "2026-01-12T10:00", "--steamspy"])
quiet(mt.main, ["--market-dir", m, "snapshot", "--now", "2026-01-12T11:00"])      # nothing new due
snaps = list(csv.DictReader(open(os.path.join(m, "snapshots.csv"), encoding="utf-8")))
assert len(snaps) == 1 and snaps[0]["label"] == "w1" and snaps[0]["reviews_total"] == "1" and snaps[0]["discount"] == "20" and snaps[0]["spy_owners"]
for h in ("10:00", "14:00", "20:00"):
    quiet(mt.main, ["--market-dir", m, "snapshot", "--players-only", "--now", f"2026-01-12T{h}"])
est = mt.estimates(snaps, list(csv.DictReader(open(os.path.join(m, "players.csv"), encoding="utf-8"))))
assert est[0]["methods"]["boxleiter"] == (20, 60) and est[0]["methods"]["steamspy"] == (20000, 50000) and est[0]["peak_players"] >= 43 and est[0]["combined"]

# ---- social: news + YouTube + Reddit RSS through entity matching; no key in any output file
t = json.load(open(os.path.join(m, "tracked.json"), encoding="utf-8"))
t["1001"].update(name="Tray Tumble", words=["Physics", "Roguelite"], release_date="2026-01-05")
json.dump(t, open(os.path.join(m, "tracked.json"), "w"))
quiet(mt.main, ["--market-dir", m, "social", "--yt-quota", "500"])
soc = json.load(open(os.path.join(m, "social", "1001.json"), encoding="utf-8"))
kept = {(x["platform"], x.get("title")) for x in soc["kept"]}
assert sum(1 for p, _ in kept if p == "youtube") == 4 and any(p == "reddit" for p, _ in kept)
assert {x["title"] for x in soc["rejected"]} == {"Tumble dryer repair", "my tumble dryer broke"}
assert all(x.get("views") for x in soc["kept"] if x["platform"] == "youtube") and soc["sources"]["twitch"] is False
for root, _, files in os.walk(home):
    for fn in files:
        if fn != ".env":
            assert SECRET not in open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read(), f"key leaked into {fn}"
feats = mt.marketing_features(soc, "2026-01-05")
assert feats["demo_before"] == 1 and feats["next_fest"] == 1 and feats["videos_before"] == 4 and feats["reddit_posts_before"] == 1 and feats["updates_90d"] == 1
assert mt.spikes([("a", 5), ("b", 5), ("c", 40), ("d", 6)]) == ["c"]

# ---- manual checks file: SteamDB pages + TikTok/IG/X searches, own section only; manual CSV import with dedupe
rm = os.path.join(home, "ricerche-manuali.md")
open(rm, "w", encoding="utf-8").write("# Ricerche manuali\n\nNote scritte a mano.\n")
quiet(mt.main, ["--market-dir", m, "manual", "-o", rm]); quiet(mt.main, ["--market-dir", m, "manual", "-o", rm])
txt = open(rm, encoding="utf-8").read()
assert txt.count(mt.MANUAL_START) == 1 and "Note scritte a mano." in txt and "https://steamdb.info/app/1001/charts/" in txt and "#TrayTumble" in txt and "scraping" in txt
mc = os.path.join(home, "manual.csv")
open(mc, "w", encoding="utf-8").write("platform,url,date,views,likes,appid,note\ntiktok,https://www.tiktok.com/@duo/video/1,2025-12-01,12000,800,1001,clip\nmyspace,https://x,2025-12-01,1,1,1001,\n")
_, out = quiet(mt.main, ["--market-dir", m, "manual", "--import", mc]); assert "importati 1" in out
_, out = quiet(mt.main, ["--market-dir", m, "manual", "--import", mc]); assert "importati 0" in out

# ---- marketing patterns into calibrate: B winners vs losers (here: the social file of one B game)
graded = {1001: dict(grade="B", release_date="2026-01-05", reviews_d90="80")}
pat = mt.marketing_patterns(m, graded, "d90")
assert pat["n_win"] == 1 and pat["small_sample"] and any(r["feature"] == "demo_before" and r["winners"] == 100.0 for r in pat["table"])
shutil.rmtree(home, ignore_errors=True)
print("market/calibrate ok: keys by name only, dataset re-checks 30/90/180, calibration + base rates, calc_econ, snapshots, estimates, social matching, manual checks, patterns")
