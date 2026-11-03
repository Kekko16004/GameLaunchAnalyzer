"""Offline: the objective pre-launch metric (fit, out-of-time backtest, levers, score), the 3 moves written into TODO.md and
calendar.md without duplicates, the predictions log, the marketing dossier, comparables vs tiers, and the real-market parts
of STATUS.html (header summary, Mercato reale tab, cards)."""
import os as _os
_os.environ["GLS_REACH"] = "off"   # offline: never the real Agent Reach
import os, sys, json, csv, io, contextlib, tempfile, datetime as dt, urllib.parse, random, shutil
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "scripts", "research"))
home = tempfile.mkdtemp()
os.environ["GLS_HOME"] = home
for k in ("YOUTUBE_API_KEY", "STEAM_WEB_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET", "GLS_ENV_FILE"):
    os.environ.pop(k, None)
import common
common.set_rate(0)
import cohort_bench as cb

def quiet(fn, *a, **kw):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        r = fn(*a, **kw)
    return r, out.getvalue()

# ---------------------------------------------------------------- metro on two synthetic release weeks with a planted signal
rnd = random.Random(7)
ds = os.path.join(home, "cohorts"); os.makedirs(ds)
for wk, (d0, d1) in enumerate((("2026-06-01", "2026-06-07"), ("2026-06-08", "2026-06-14"))):
    name = f"cohort_{d0}_{d1}"
    work = os.path.join(ds, "_work", name); os.makedirs(os.path.join(work, "apps"))
    games, rows = [], []
    for i in range(140):
        aid = 10000 * (wk + 1) + i
        demo, trailer = rnd.random() < 0.4, rnd.random() < 0.7
        grade = "A" if i % 15 == 0 else ("C" if i % 3 == 0 else "B")
        rel = (dt.date.fromisoformat(d0) + dt.timedelta(days=i % 7)).isoformat()
        rev = max(0, int(rnd.lognormvariate(1.0 + 2.2 * demo + 0.8 * trailer + 1.5 * (grade == "A") - 1.0 * (grade == "C"), 0.8)))
        g = dict(appid=aid, name=f"G{aid}", search_date=rel, release_date=rel, price=rnd.choice([4.99, 7.99, 9.99, 14.99]), is_free=False, genres=["Casual"] if i % 2 else ["Action"],
                 n_movies=2 if trailer else 0, n_screenshots=rnd.randint(5, 14), about_len=rnd.randint(300, 3000), n_languages=rnd.choice([1, 2, 8]),
                 developers=[f"D{aid}"], publishers=[f"D{aid}"], early_access=False, has_demo=False)
        games.append(g)
        news = [dict(date=(dt.date.fromisoformat(rel) - dt.timedelta(days=90)).isoformat(), title="Demo out now", official=True, kinds=["demo"])] if demo else []
        json.dump(dict(details=dict(about_the_game="text"), news=news), open(os.path.join(work, "apps", f"{aid}.json"), "w"))
        rows.append(dict(appid=aid, name=g["name"], release_date=rel, price=g["price"], status="keep", grade=grade, reviews_d30=rev, week=name))
    json.dump(dict(read_on="2026-10-01", window=[d0, d1], games=games), open(os.path.join(work, "cohort.json"), "w"))
    cb.write_week(rows, os.path.join(ds, name + ".csv"))
    open(os.path.join(ds, name + ".source"), "w").write(work)
met = cb.build_metro(ds, dt.date(2026, 10, 13))
assert met["available"] and met["n"] == 280 and met["target"] == "y30", met.get("why")
bt = met["backtest"]
assert bt["possible"] and bt["test_week"].endswith("06-14") and bt["n_train"] == 140 and bt["n_test"] == 140
assert bt["per_threshold"]["p1k"]["auc"] >= 0.75 and bt["per_threshold"]["p1k"]["skill"] > 0 and bt["strength"] in ("utile", "debole"), bt["per_threshold"]["p1k"]
top = met["effects"][0]
assert top["feature"] in ("demo_pre", "tier_A") and top["delta_pp"] > 0, met["effects"][:3]
x = cb.features_from_json(dict(tier="B", price=7.99, n_movies=0, n_screenshots=10, n_languages=2, demo_before=False, about_len=1500, release_day_crowd=20, genres=["Casual"]))
sc = cb.score_features(met, x)
assert abs(sum(sc["bands"]) - 1) < 0.01 and 0 <= sc["p10k"] <= sc["p1k"] <= sc["p100"] <= 1
lev = {l["feature"]: l for l in sc["levers"]}
# demo, its news item and its Coming Soon period travel together in this data: they share the weight (documented limit)
assert sc["levers"][0]["feature"] in ("demo_pre", "news_pre_log", "comingsoon_log") and lev["demo_pre"]["delta_p1k_pp"] > 0
# a single week: no out-of-time check, said plainly
assert not cb.backtest([r for r in cb.metro_rows(ds) if r["week"].endswith("06-07")], "y30")["possible"]
json.dump(dict(generated_on="2026-10-10", primary="d30", metro=met), open(os.path.join(home, "calibration.json"), "w"))
pj = os.path.join(home, "pre.json"); json.dump(dict(name="Gioco", tier="B", price=7.99, n_movies=0, n_screenshots=10, n_languages=2), open(pj, "w"))
_, out = quiet(cb.main, ["score", "--features", pj, "-o", os.path.join(home, "metro_out.json")])
assert "Cosa pesa" in out and "Se aggiungiamo" in out and "[STIMA]" in out

# ---------------------------------------------------------------- 3 moves into TODO.md and calendar.md, no duplicates
L = os.path.join(home, "launch"); os.makedirs(os.path.join(L, "_raw"))
open(os.path.join(L, "TODO.md"), "w", encoding="utf-8").write(
    "# TODO\nAggiornato: 2026-10-01\n\n## Marketing\n- [ ] 👤 **Montare il trailer di 40 s** — 2026-11-20 — 12 h — nessuna — trailer online\n- [ ] 👤 **Scrivere ai creator** — 2026-10-12 — 3 h — lista — 10 email\n")
open(os.path.join(L, "calendar.md"), "w", encoding="utf-8").write(
    "# Calendario\n\n## ✅ Passi in ordine\n🤖 = io · 👤 = tu\n### FASE 1 — Adesso\n1. [ ] 👤 **Montare il trailer** per la pagina. · 📅 2026-11-20\n2. [x] 🤖 Ondata 1. · 📅 2026-10-10\n### FASE 2 — Dopo\n3. [ ] 👤 **Recluta tester**. · 📅 2026-11-05\n")
json.dump(dict(score=dict(p1k=0.2, levers=[dict(feature="trailer", label="Trailer sulla pagina", p1k_after=0.33, delta_p1k_pp=13.0, delta_p10k_pp=2.0),
                                             dict(feature="nextfest_pre", label="Steam Next Fest", p1k_after=0.31, delta_p1k_pp=11.0, delta_p10k_pp=3.0)]),
               metro=dict(strength="debole")), open(os.path.join(L, "_raw", "metro.json"), "w"))
cal = dict(generated_on="2026-10-10", marketing=dict(recipe=[dict(step="demo", label="Demo gratuita", winners=67.0, losers=22.0, n_winners=60, n_losers=54, median_days_before=165),
                                                              dict(step="trailer", label="Trailer pubblicato", winners=86.0, losers=39.0, n_winners=35, n_losers=31, median_days_before=143)]))
cp = os.path.join(home, "cal_moves.json"); json.dump(cal, open(cp, "w"))
import top_moves as tm, plan_steps as ps, todo_track as tt
today = dt.date(2026, 10, 13)
for _ in range(2):   # recomputed every run: the second run must not add anything
    moves = tm.compute(L, today, cp)
    res = tm.apply(L, today, moves)
assert len(moves) == 3 and {m["source"] for m in moves} >= {"recipe"}
titles = " ".join(m["title"] for m in moves)
assert "Demo" in titles and "Trailer" in titles and "creator" in titles.lower(), titles   # recipe demo, trailer (merged with the metro lever), overdue TODO
todo = open(os.path.join(L, "TODO.md"), encoding="utf-8").read()
assert todo.count(tm.MARK) == 3 and todo.count("Montare il trailer di 40 s") == 1 and "## ⭐ Le 3 mosse a più impatto" in todo and todo.count("Demo gratuita") == 1
calmd = open(os.path.join(L, "calendar.md"), encoding="utf-8").read()
plan = ps.parse(calmd)
assert ps.check(plan) == [] or all("dates go backwards" in p_ for p_ in ps.check(plan)), ps.check(plan)
assert calmd.count(tm.MARK) == 3 and calmd.count("Demo gratuita") == 1 and "### ⭐ Mosse a più impatto" in calmd
merged = next(m for m in moves if m["key"] == "trailer")
assert "metro oggettivo" in merged["why"] and merged["source"] == "recipe"
assert tm.our_status(L)["trailer"] == "pianificato" and tm.our_status(L)["demo"] == "pianificato"

# ---------------------------------------------------------------- predictions log
import predictions as pr
os.makedirs(os.path.join(L, "fg"))
with open(os.path.join(L, "fg", "timeline.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["wave", "stage", "date", "score", "wishlist_pct", "buy_pct", "gate"])
    w.writerow([1, "beta", "2026-10-07", "40.0", "30.0", "25.0", "35.0"]); w.writerow([2, "full", "2026-10-08", "60", "50", "40", "35"]); w.writerow([3, "beta", "2026-10-12", "50.0", "41.0", "35.0", "35.0"])
assert pr.sync(L, today) == 4 and pr.sync(L, today) == 0   # full-game waves are not predictions of the real test; nothing duplicated
open(os.path.join(L, "metrics.csv"), "w", encoding="utf-8").write("date,metric,value,note\n2026-11-16,real_wishlist_pct,50,test reale\n")
e = pr.evaluate(L, today)
assert e["evaluated"] == 2 and e["hits"] == 1 and e["accuracy"] == 50.0, e   # real 50: wave 1 said 30 (±10 -> miss), wave 3 said 41 (hit)
rows = {r["id"]: r for r in e["rows"]}
assert rows["wave1-wishlist_pct"]["hit"] is False and rows["wave1-wishlist_pct"]["direction"] == "pessimista" and rows["wave3-wishlist_pct"]["hit"] is True
assert rows["wave1-buy_pct"]["status"] == "manca il dato reale"

# ---------------------------------------------------------------- dossier: TikTok via oEmbed of links found, accounts from the page only, no CDN assets as press
D = lambda s: int(dt.datetime(*map(int, s.split("-")), tzinfo=dt.timezone.utc).timestamp())  # noqa: E731
tt_id = (D("2026-03-02") << 32) + 12345
def fake(url, **kw):
    u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if "appdetails" in u.path:
        return json.dumps({"77": {"success": True, "data": {"name": "Tray Tumble", "release_date": {"date": "Apr 1, 2026"}, "developers": ["Duo Studio"], "publishers": [], "genres": [{"description": "Casual"}],
                          "supported_languages": "English", "website": "https://traytumble.example/", "price_overview": {"initial": 799},
                          "about_the_game": f"Follow us https://www.instagram.com/traytumble/ and https://www.tiktok.com/@duo/video/{tt_id} press https://press.example/kit https://shared.akamai.steamstatic.com/x/a.webm?t=1"}}}).encode()
    if "GetNewsForApp" in u.path:
        return json.dumps({"appnews": {"newsitems": [{"gid": "1", "title": "Demo out now", "feedname": "steam_community_announcements", "date": D("2026-01-10"), "contents": "demo"},
                                                     {"gid": "2", "title": "Out now!", "feedname": "steam_community_announcements", "date": D("2026-04-01"), "contents": "launch"}]}}).encode()
    if "appreviewhistogram" in u.path:
        return json.dumps({"success": 1, "results": {"rollup_type": "week", "start_date": D("2026-04-01"), "rollups": [dict(date=D(d), recommendations_up=n, recommendations_down=0) for d, n in
                          (("2026-04-01", 50), ("2026-04-08", 10), ("2026-04-15", 8), ("2026-04-22", 9), ("2026-04-29", 7), ("2026-05-06", 40))]}}).encode()
    if "tiktok.com/oembed" in url:
        return json.dumps({"title": "tower of plates falls", "author_name": "duo"}).encode()
    raise AssertionError(url)
common.http_get = fake
import market_tracker as mtr
mdir = os.path.join(home, "market"); os.makedirs(os.path.join(mdir, "social"))
json.dump(dict(appid=77, name="Tray Tumble", sources=dict(youtube=True, reddit=False, steam_news=True), threshold=50, rejected=[{"title": "x"}],
               news=[dict(published="2026-01-10", kinds=["demo"], official=True, title="Demo out now"), dict(published="2026-04-01", kinds=["launch"], official=True, title="Out now!")],
               kept=[dict(platform="youtube", id="v1", title="Tray Tumble is chaos", author="Big Creator", author_id="c1", published="2026-05-03", views=120000, why=["exact title"], url="https://youtu.be/v1", text="")]),
          open(os.path.join(mdir, "social", "77.json"), "w"))
ns = type("A", (), dict(market_dir=mdir, out_dir=os.path.join(L, "_raw", "dossier"), appid=["77"], name=None, yt_quota=0, no_reddit=True, threshold=50))()
_, out = quiet(mtr.cmd_dossier, ns)
dj = json.load(open(os.path.join(L, "_raw", "dossier", "dossier-77.json"), encoding="utf-8"))
assert any(x["platform"] == "tiktok" and x["date"] == "2026-03-02" and x["title"] == "tower of plates falls" for x in dj["timeline"])
assert any("instagram.com/traytumble" in u for u in dj["accounts"]) and dj["press"] == ["https://press.example/kit", "https://traytumble.example/"]
assert [s["week"] for s in dj["spikes"]] == ["2026-04-01", "2026-05-06"] and any(e["platform"] == "youtube" for e in dj["spikes"][1]["events"])
md = open(os.path.join(L, "_raw", "dossier", "dossier-77.md"), encoding="utf-8").read()
assert "correlazione, non causa" in md and "a pagamento" in md and "Business Discovery" in md
assert mtr.tiktok_date(f"https://www.tiktok.com/@a/video/{tt_id}") == "2026-03-02" and mtr.platform_of("https://x.com/a") == "x"
c30 = dict(milestones=dict(d30=dict(tiers=dict(A=dict(reviews=dict(median=300)), B=dict(reviews=dict(p75=40, p90=150))))))
assert mtr.looks_like(400, c30).startswith("esito da fascia A") and "top 10" in mtr.looks_like(200, c30) and "nella media" in mtr.looks_like(5, c30)

# ---------------------------------------------------------------- STATUS.html: header summary, Mercato reale tab, cards
calib = dict(generated_on="2026-08-01", data_from="2026-06-01", data_to="2026-06-14", n_graded=280, primary="d30", junk_share=0.02, tier_share=dict(A=0.02, B=0.28, C=0.70),
             milestones=dict(d30=dict(n=280, tiers={t: dict(n=n, reviews=dict(p25=2, median=20, p75=80, p90=300), copies=dict(p25=[40, 120], median=[400, 1200], p75=[1600, 4800], p90=[6000, 18000]),
                                                         copies100={"pct_low": 70, "pct_high": 85, "ci_low": [60, 80], "ci_high": [75, 92]}, copies1000={"pct_low": 35, "pct_high": 55, "ci_low": [1, 2], "ci_high": [1, 2]},
                                                         copies10000={"pct_low": 8, "pct_high": 15, "ci_low": [1, 2], "ci_high": [1, 2]}, popular={"pct_low": 8, "pct_high": 15, "ci_low": [1, 2], "ci_high": [1, 2]}, small_sample=n < 30)
                                                    for t, n in (("A", 11), ("B", 160), ("C", 380), ("A+B", 171), ("all_new", 560))},
                                  by_price=dict(B={"5-10": dict(n=58, copies1000={"pct_low": 30, "pct_high": 50}, copies=dict(median=[350, 1050], p25=[1, 1], p75=[1, 1], p90=[1, 1]))}), by_genre=dict(B={}))),
             distribution=dict(milestone="d30", buckets=[dict(label="0", A=0, B=5, C=80), dict(label="1-9", A=1, B=50, C=200)]), concentration=dict(top1=33, top10=87, bottom50=0.7),
             controls=dict(milestone="d30", b_winners=[dict(appid=1, name="Win", price=9.99, release_date="2026-06-02", reviews=400)], b_losers=[dict(appid=2, name="Lose", price=4.99, release_date="2026-06-03", reviews=2)]),
             marketing=cal["marketing"] | dict(milestone="d30", n_win=60, n_lose=54), metro=met, breakouts=[dict(name="Rocket", release_date="2026-09-20", reviews_per_day=80.0, curve=dict(d7=500))],
             head=[dict(appid=730, name="Counter-Strike 2", roles=["most_played"], reviews=9000000)])
json.dump(calib, open(os.path.join(home, "calibration.json"), "w"))
json.dump(dict(read_on="2026-10-13", summary=dict(days=14, total=1319, min=34, median=96.5, mean=94.2, max=156), per_day=[dict(date="2026-10-0" + str(i), games=90) for i in range(1, 8)]), open(os.path.join(home, "volume.json"), "w"))
shutil.copy(os.path.join(home, "metro_out.json"), os.path.join(L, "_raw", "metro.json"))
open(os.path.join(L, "ricerche-manuali.md"), "w", encoding="utf-8").write("# Ricerche manuali\n- [ ] SteamDB follower di Goblin Sushi\n- [x] TikTok: cerca #traytumble\n")
json.dump(dict(scenarios=[dict(id="wl", title="Wishlist lente", signals=[dict(metric="wishlists", op="<", value=500, label="wishlist")])]), open(os.path.join(L, "_raw", "contingencies.json"), "w"))
open(os.path.join(L, "metrics.csv"), "a", encoding="utf-8").write("2026-10-05,wishlists,300,\n2026-10-12,wishlists,650,\n")
json.dump(dict(game="Tray Tumble", verdict=dict(color="giallo", summary="ok")), open(os.path.join(L, "status.json"), "w"))
import calc_econ
json.dump(calc_econ.compute(dict(calc_econ.DEFAULTS, price=7.99, costs=500, wishlists=[1000, 3000, 8000])), open(os.path.join(L, "_raw", "econ.json"), "w"))
import status_page as sp
page = sp.build(L, "private", [], [], set(), today)
for s_ in ('id="p-mercato"', "Mercato reale", 'class="card hero', "SIMULATO", "[STIMA]", "vecchi di 73 giorni", "Metro oggettivo (dati veri)", "Verifica onesta",
           "Cosa hanno fatto i B vincenti, in ordine", "KPI settimana per settimana", "Previsioni contro realtà", "Controlli a mano", "Dove siamo rispetto al mercato reale",
           "Il controllo con la realtà del focus group", "La ricetta dei B vincenti", "Scenari di vendita dal mercato reale", "semaforo: Giallo", "I nuovi che decollano", "La testa del mercato"):
    assert s_ in page, s_
hero = page[page.index('class="card hero'):page.index("</section>", page.index('class="card hero'))]
assert hero.index("vecchi di 73 giorni") < hero.index("focus group"), "old data must be said first"
assert "<img" not in page.split("<main>")[1] or "src=\"http" not in page, "no external images: the page stays offline"
shutil.rmtree(home, ignore_errors=True)
print("metro/moves/page ok: backtest AUC", bt["per_threshold"]["p1k"]["auc"], "| 3 moves without duplicates | predictions | dossier | STATUS.html real-market tab and header")
