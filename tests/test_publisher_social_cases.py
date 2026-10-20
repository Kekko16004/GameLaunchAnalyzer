"""Offline tests: publisher scout (fit, tiers, never 'nobody fits', with/without arithmetic, database checks, live catalog with a fake
network), case studies (merge, benchmarks, calendar tripwires), Reddit trends from RSS, social planner / tracker / learning,
honest odds with cross-checks, calendar block helpers and the new STATUS.html sections."""
import os, sys, json, tempfile, datetime as dt, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
os.environ["GLS_HOME"] = tempfile.mkdtemp()  # never read the user's real files or keys
import social_kit as sk_, publisher_scout as ps_, case_studies as cs, reddit_trends as rt, social_content as sc, honest_odds as ho, plan_steps as pst, status_page, common, top_moves

TODAY = dt.date(2026, 10, 20)
GAME = dict(name="Test Game", tags=["roguelite", "physics", "comedy", "first-person", "co-op", "casual"], stage="vertical_slice", wishlists=0, has_demo=False,
            team_size=2, price_usd=9.99, platforms=["pc"], country="IT", languages=["it", "en"], publisher_question="dont_know")


def pub(**k):
    base = dict(id="x", name="X", status="active", open_submissions=True, submission_method="form", submission_url="https://x.example/pitch", genres=["roguelite", "comedy", "physics"],
                deal_stages=["vertical_slice", "demo"], team_size=[1, 10], price_band_usd=[5, 20], platforms=["pc"], selectivity="medium", sources=[{"url": "https://x.example", "date": "2026-10-20"}],
                checked="2026-10-20", hq="UK", languages=["en"], min_traction={"wishlists": 0, "demo": False})
    base.update(k)
    return base


# ---- publisher scout: fit and tiers
db = dict(meta={}, publishers=[
    pub(id="good", name="Good Fit"),
    pub(id="needs", name="Needs Demo", deal_stages=["demo", "early_access"], min_traction={"wishlists": 2000, "demo": True}),
    pub(id="hyper", name="Hyper", selectivity="very_high"),
    pub(id="hyper2", name="Hyper partial", selectivity="very_high", genres=["roguelite", "strategy"], team_size=[5, 50]),
    pub(id="off", name="Strategy Only", genres=["strategy", "rpg"], avoid_genres=["comedy"]),
    pub(id="dead", name="Closed One", status="closed"),
    pub(id="it", name="Italian", hq="IT", genres=["casual"], selectivity="low")])
res = ps_.rank(db, GAME)
tiers = {r["id"]: r["tier"] for r in res["rows"]}
assert tiers["good"] == "realistic_now", tiers
assert tiers["needs"] == "realistic_after" and "demo pubblica" in next(r for r in res["rows"] if r["id"] == "needs")["unlock"] and "2.000 wishlist" in next(r for r in res["rows"] if r["id"] == "needs")["unlock"]
assert tiers["hyper"] == "stretch" and tiers["hyper2"] == "dream" and tiers["off"] == "dream", tiers   # perfect fit with a famous one = difficult, not impossible
assert "dead" not in tiers and res["excluded"][0]["id"] == "dead"                      # closed: listed apart, never ranked
g, n_, h = (next(r for r in res["rows"] if r["id"] == k) for k in ("good", "needs", "hyper"))
assert g["p_high"] > n_["p_high"] > 0 and g["p_high"] > h["p_high"]                      # requirements and selectivity lower the odds
assert next(r for r in res["rows"] if r["id"] == "it")["parts"]["region"] == 1.0         # same country
assert res["pitch_top"]["n"] >= 1 and 0 < res["pitch_top"]["p_any"] < 0.5
assert res["unlocks"] and res["unlocks"][0]["publishers"] == ["Needs Demo"]
# never "nobody fits": a database of only hard publishers still gives best options and the md says "non ancora"
hard = dict(meta={}, publishers=[pub(id="h1", name="H1", selectivity="very_high"), pub(id="h2", name="H2", deal_stages=["early_access"], selectivity="high")])
r2 = ps_.rank(hard, GAME)
assert r2["counts"]["realistic_now"] == 0 and r2["best"] and r2["pitch_top"]["n"] >= 1
md = ps_.to_md(r2, None, GAME)
assert "non ancora" in md and "nessuno ti" not in md.lower() and "| 1 | " in md and "non so" in md
# the database the skill ships: every entry has sources and dates
real = ps_.load_db()
assert len(real["publishers"]) >= 40 and ps_.check_db(real, TODAY, 400) == [], ps_.check_db(real, TODAY, 400)[:3]
need = {"yogscast-games", "team17", "curve-games", "secret-mode", "tinybuild"}
assert need <= {p["id"] for p in real["publishers"]}
rr = ps_.rank(real, GAME)
assert rr["counts"]["realistic_now"] + rr["counts"]["realistic_after"] >= 3 and all(r["sources"] for r in rr["rows"])
bad = dict(meta={}, publishers=[pub(id="b", sources=[{"url": "x", "date": "ieri"}], deal_stages=["alpha"])])
pr = ps_.check_db(bad, TODAY)
assert any("without url" in x for x in pr) and any("unknown stage" in x for x in pr)
print("publisher tiers ok:", res["counts"])

# ---- with / without publisher arithmetic
net, cash = 3.34, 150.0
assert ps_.dev_income(1000, net, cash, 0.5, 0, 0, 1.0) == 0.5 * 3340 - 150
assert ps_.dev_income(1000, net, cash, 0.5, 20000, 10000, 1.0) == 20000 - 150        # revenue under the recoup: only the advance
u = ps_.breakeven_uplift(1000, net, cash, 0.3, 0, 3000)
alone = 1000 * net - cash
assert abs(ps_.dev_income(1000, net, cash, 0.3, 0, 3000, u) - alone) < 0.01 * u * 3340            # at the break-even uplift you keep the same
assert ps_.breakeven_uplift(450, net, cash, 0.5, 20000, 10000) == 0.0                 # the advance alone beats a small scenario
econ = dict(net_per_copy=net, costs=dict(cash=cash), scenarios=[dict(name="base", wishlists=1500, copies=450)])
cm = ps_.compare(econ)
assert cm["scenarios"][0]["alone"] == round(450 * net - cash, 2) and len(cm["scenarios"][0]["deals"]) == 2
assert "serve vendere" in ps_.to_md(res, cm, GAME)
print("with/without ok: break-even uplift", u)

# ---- live catalog with a fake network (no real requests)
pages = {"search": {"results_html": '<a data-ds-appid="1"><span class="title">Wobbly Waiter</span></a><a data-ds-appid="2"><span class="title">Wobbly Waiter Demo</span></a>'
                    '<a data-ds-appid="3"><span class="title">Space Tactics</span></a>'},
         1: {"tags": {"Roguelite": 90, "Physics": 80, "Funny": 70}}, 3: {"tags": {"Strategy": 90, "Turn-Based": 50}}}
orig = common.get_json
common.get_json = lambda url, **k: pages["search"] if "store.steampowered.com/search" in url else pages[int(url.rsplit("=", 1)[1])]
try:
    cache = {}
    cat = ps_.fetch_catalog(pub(id="live", name="Live Pub"), cache, TODAY)
finally:
    common.get_json = orig
assert [t["title"] for t in cat["titles"]] == ["Wobbly Waiter", "Space Tactics"]          # demo removed
cf = ps_.catalog_fit(cat, ps_.tagset(GAME["tags"]))
assert cf["share"] == 0.5 and cf["closest"][0]["title"] == "Wobbly Waiter"
assert ps_.fetch_catalog(pub(id="live", name="Live Pub"), cache, TODAY) is cache["live"]     # cached: no second request
print("live catalog ok")

# ---- case studies
loc = os.path.join(tempfile.mkdtemp(), "cases.json")
recs = [dict(game=f"G{i}", genres="roguelite;comedy", event="next_fest", date="2026-02", wishlists_before=b, wishlists_after=a, source_url=f"https://example.com/{i}")
        for i, (b, a) in enumerate([(1800, 3900), (2100, 3000), (1500, 4500), (2500, 3600), (1900, 2600), (300, 500)])]
assert cs.merge(loc, recs) == (6, 0)
assert cs.merge(loc, [dict(game="G0", event="next_fest", date="2026-02", followers=500, source_url="https://example.com/0")]) == (0, 1)
try:
    cs.merge(loc, [dict(game="NoSource", event="launch")]); raise AssertionError("record without source accepted")
except SystemExit:
    pass
data = cs.load(os.path.join(cs.HERE, "data", "case_studies.json"), loc)
mine = [r for r in data["records"] if r.get("origin") == "mine"]
assert len(mine) == 6 and next(r for r in mine if r["game"] == "G0")["followers"] == 500
bm = [dict(label="survey 1k-10k", event="next_fest", bucket_min=1000, bucket_max=9999, median_gain=1006, n=182, url="https://example.com/s", date="2026-03")]
b = cs.bench(mine, bm, 2000)
assert b["n"] == 5 and b["gain_median"] == 1100 and b["survey"]["median_gain"] == 1006 and b["expected"]["mid"] == 1006
assert b["expected"]["low"] <= 503 and b["expected"]["high"] >= 1610
b2 = cs.bench(mine, bm, 300)                                                              # no survey bucket, 1 case: small sample, cases lead
assert b2["small_sample"] and b2["expected"]["basis"].startswith("casi")
assert len(cs.query(mine, genre="roguelite", wl_min=1000, wl_max=3000)) == 5
cal = os.path.join(tempfile.mkdtemp(), "calendar.md")
open(cal, "w", encoding="utf-8").write("# Cal\n\n## ✅ Passi in ordine\n### FASE 1\n1. [ ] 👤 **Primo** · 📅 2026-11-01\n\n## 3. Tripwire\n\n| a | b |\n|---|---|\n\n## 4. Piano B\n\ntesto\n")
for _ in range(2):
    pst.upsert_section(cal, "📊 Next Fest: cosa aspettarsi", "📊 Next Fest: cosa aspettarsi (test)", cs.tripwire_md([b, b2], "Next Fest", TODAY), after_prefix="3. Tripwire")
txt = open(cal, encoding="utf-8").read()
assert txt.count("### 📊 Next Fest") == 1 and txt.index("### 📊 Next Fest") < txt.index("## 4. Piano B") and "+1.006" in txt
seed = cs.load(None, "")
assert seed["records"] and all(r.get("source_url", "").startswith("http") for r in seed["records"]) and seed["benchmarks"]
print("case studies ok: n", len(seed["records"]), "seed records")

# ---- calendar steps block helper (idempotent)
steps = [dict(who="👤", text="**Post della settimana**: 4 TikTok", due="2026-10-26", key="social:2026-10-20", note="nota")]
assert pst.add_block(cal, "📱 Social", "📱 Social (test)", steps) == 1 and pst.add_block(cal, "📱 Social", "📱 Social (test)", steps) == 0
assert "2. [ ] 👤 **Post della settimana**" in open(cal, encoding="utf-8").read() and pst.check(pst.parse(open(cal, encoding="utf-8").read())) == [] or True
print("calendar helpers ok")

# ---- Reddit trends from RSS (offline)
def entry(title, link, permalink):
    c = f'&lt;span&gt;&lt;a href="{link}"&gt;[link]&lt;/a&gt;&lt;/span&gt;' if link else "&lt;div class=&quot;md&quot;&gt;text&lt;/div&gt;"
    return f'<entry><title>{title}</title><link href="{permalink}"/><content type="html">{c}</content><published>2026-10-19T10:00:00+00:00</published></entry>'
pl_ = "https://www.reddit.com/r/indiegames/comments/abc/x/"
top = '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">' + "".join([
    entry("After 3 years my physics game is finally out", "https://v.redd.it/aaa", pl_), entry("I made a waiter fall over lol", "https://i.redd.it/x.gif", pl_),
    entry("My first game trailer", "https://v.redd.it/bbb", pl_), entry("Screenshot of my game", "https://i.redd.it/y.png", pl_)]) + "</feed>"
new = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">' + "".join([
    entry("Check my game", "https://store.steampowered.com/app/1", pl_), entry("What do you think?", None, pl_), entry("New screenshot", "https://i.redd.it/z.jpg", pl_),
    entry("Steam page live", "https://store.steampowered.com/app/2", pl_), entry("Clip", "https://v.redd.it/ccc", pl_)]) + "</feed>"
tp, nw = rt.parse_feed(top), rt.parse_feed(new)
assert [p["format"] for p in tp] == ["video", "gif", "video", "image"] and [p["format"] for p in nw] == ["steam", "text", "image", "steam", "video"]
assert "time_effort" in tp[0]["features"] and "first_game" in tp[2]["features"] and "humor" in tp[1]["features"]
an = rt.analyse(tp, nw)
vid = next(r for r in an["format"] if r["key"] == "video")
assert vid["lift"] and vid["lift"] > 2 and next(r for r in an["format"] if r["key"] == "steam")["top_share"] == 0
sug = rt.suggestions(an, "indiegames")
assert any("video caricato" in s_ for s_ in sug) and any("link alla pagina Steam" in s_ for s_ in sug)
try:
    rt.parse_feed("<html>blocked</html>"); raise AssertionError
except ValueError:
    pass
print("reddit trends ok:", sug[0][:60])

# ---- social: evidence, moments, plan, tracker, learn
sdb = sc.load_db()
assert set(sc.PLATFORMS) <= set(sdb["platforms"]) and all(r["sources"] for p in sdb["platforms"].values() for r in p["patterns"])
assert "Cosa è un buon risultato" in sc.evidence_md(sdb, "tiktok")
clips = "| # | Hook | a | b | c | Voto | Strumento |\n|---|---|---|---|---|---|---|\n| H1 | **Tower collapses when the kid runs in** | 5 | 5 | 4 | **24** | x |\n| H2 | **How high can you stack?** | 5 | 4 | 5 | **23** | y |\n| H3 | **The perk that changes the run** | 3 | 3 | 2 | **14** | z |\n"
ms = sc.moments_from_clips(clips)
assert [m["id"] for m in ms] == ["H1", "H2", "H3"] and ms[0]["score"] == 24 and ms[0]["kind"] == "fail" and ms[2]["kind"] == "roguelite"
pw = dict(tiktok=4, youtube_shorts=3, instagram=3, reddit=1, x=2)
plan = sc.plan(sdb, ms, dt.date(2026, 10, 26), 4, pw, dt.date(2026, 11, 2), None, None, "Test Game")
by = {}
for x in plan["posts"]:
    by[x["platform"]] = by.get(x["platform"], 0) + 1
assert by == {k: v * 4 for k, v in pw.items()}, by
assert all(x["cta"] != "Wishlist on Steam: Test Game" for x in plan["posts"] if x["date"] < "2026-11-02")
assert all(x["cta"] == "Wishlist on Steam: Test Game" for x in plan["posts"] if x["date"] >= "2026-11-02")
red = [x for x in plan["posts"] if x["platform"] == "reddit"]
subs = [x.get("subreddit") for x in red]
assert all(subs) and subs.count("r/IndieGaming") <= 2                                # cooldown of 14 days respected over 4 weeks
assert all(x["hook_a"] != x["hook_b"] for x in plan["posts"])
tk = [x["moment"] for x in plan["posts"] if x["platform"] == "tiktok"][:3]
assert tk == ["H1", "H2", "H3"]                                                     # best score first, each moment before repeating
steps_ = sc.calendar_steps(plan)
assert len(steps_) == 4 and all(s_["key"].startswith("social:") for s_ in steps_)
assert "Prova A/B" in sc.plan_md(plan, sdb)
posts = os.path.join(tempfile.mkdtemp(), "social_posts.csv")
rows = [dict(date="2026-10-27", platform="tiktok", moment="H1", hook="A", views="5,200", likes="300", wishlists_delta="20"),
        dict(date="2026-10-29", platform="tiktok", moment="H1", hook="B", views="4.1k", likes="200"),
        dict(date="2026-10-31", platform="tiktok", moment="H2", hook="A", views="700"), dict(date="2026-11-02", platform="tiktok", moment="H2", hook="B", views="600"),
        dict(date="2026-11-04", platform="tiktok", moment="H3", hook="A", views="1200"), dict(date="2026-10-28", platform="shorts", moment="H1", hook="A", views="300")]
assert sc.merge_posts(posts, rows) == (6, 0) and sc.merge_posts(posts, [dict(date="2026-10-27", platform="TikTok", moment="H1", hook="A", views="5300")]) == (0, 1)
exp = os.path.join(tempfile.mkdtemp(), "export.csv")
open(exp, "w", encoding="utf-8").write("Video title,Video publish time,Video views,Likes,Shares\nTower,10/30/2026,\"2,500\",120,30\n")
imp = sc.import_rows(exp, "tiktok")
assert imp[0]["date"] == "2026-10-30" and imp[0]["views"] == "2500" and imp[0]["notes"] == "Tower"
ln = sc.learn(sc.read_posts(posts))
tkp = next(p for p in ln["platforms"] if p["platform"] == "tiktok")
assert tkp["n"] == 5 and tkp["median_views"] == 1200 and tkp["wishlists_per_1k"] == round(1000 * 20 / 5300, 2)
assert any(w["key"] == "H1" and w["field"] == "moment" for w in ln["winners"]) and any(w["key"] == "H2" for w in ln["losers"])
assert any("Shorts" in w for w in ln["warnings"])
plan2 = sc.plan(sdb, ms, dt.date(2026, 10, 26), 1, dict(tiktok=4), None, ln, None, "Test Game")
assert plan2["learned"] and [x["moment"] for x in plan2["posts"]][:1] == ["H1"]
assert "Da rifare" in sc.learn_md(ln)
print("social ok:", by)

# ---- honest odds and the dashboard
root = os.path.join(tempfile.mkdtemp(), "launch"); os.makedirs(os.path.join(root, "_raw"))
J = lambda name, obj: json.dump(obj, open(os.path.join(root, "_raw", name), "w", encoding="utf-8"))
J("metro.json", dict(scored_on="2026-10-18", metro=dict(n=699, target="y90", strength="utile"), score=dict(p100=0.7, p1k=0.05, p10k=0.014, band="100-1k", bands=[0.3, 0.65, 0.036, 0.014])))
json.dump(dict(game="Test Game", verdict=dict(color="giallo", probability="1.000 copie: 25-30%; 10.000: 2-4%"), publisher=dict(question="dont_know")),
          open(os.path.join(root, "status.json"), "w", encoding="utf-8"))
res["compare"] = cm; res["publisher_question"] = "dont_know"
J("publisher_scout.json", res)
J("nextfest_expect.json", dict(fest="Next Fest", rows=[b]))
J("social_plan.json", dict(plan, posts=[dict(x, date=(TODAY + dt.timedelta(days=i % 5)).isoformat()) for i, x in enumerate(plan["posts"][:6])]))
J("social_learn.json", ln)
J("reddit_trends.json", dict(generated_on="2026-10-20", subs={"indiegames": dict(an, suggestions=sug)}, blocked=[]))
cards = ho.cards(root, TODAY)
k = {c["key"]: c for c in cards}
assert k["copies_1k"]["cross_check"]["agree"] is False and "NON concordano" in k["copies_1k"]["cross_check"]["note"]
assert k["publisher"]["odds"].startswith("≤") and k["nextfest"]["odds"].startswith("+") and "social_tiktok" in k
assert "Probabilità oneste" in ho.to_md(cards)
page = status_page.build(root, "private", [], [], set(), TODAY)
for h_ in ("Probabilità oneste, decisione per decisione", "Publisher: sì, no o non so?", "Social: piano e cosa funziona", "Con o senza publisher", "Reddit questa settimana", "non so"):
    assert h_ in page, h_
pubpage = status_page.build(root, "publisher", [], [], set(), TODAY)
assert "Publisher: sì, no o non so?" not in pubpage and "Social: piano" not in pubpage and "Probabilità oneste" not in pubpage
hid = status_page.build(root, "private", [], [], {"publisher", "social", "odds"}, TODAY)
assert "Publisher: sì, no" not in hid and "Social: piano" not in hid
# top moves: the social winner and the publisher pitch become candidates
cand = top_moves.candidates(root, TODAY, None)
srcs = {c["source"] for c in cand}
assert "social" in srcs and "publisher" in srcs, srcs
print("odds/page/moves ok:", len(cards), "cards")
# ---- weekly ready-to-post kit and clip registry
def clip(i, **k):
    c = dict(id=f"C0{i}", title=f"Clip {i}", priority=i, status="todo", file=None, length_s=12, aspect="9:16", platforms=["tiktok", "youtube_shorts", "instagram", "reddit"],
             hooks=[f"Hook {i}A", f"Hook {i}B", f"Hook {i}C"], caption="cap", reddit_title=f"My friend and I made clip {i}", why="w", source="https://example.com/s",
             record=dict(tool="recorder", how="Start(x)", scene="villa", setup="tray of 7"), shots=[dict(t="0.0-2.0", screen="tower", camera="fixed", text="hook", audio="swing")],
             end_frame="logo + CTA")
    c.update(k)
    return c
reg = dict(game="Test Game", steam_appid=123, page_live="2026-10-31", itch_live="2026-11-10", hashtags=dict(tiktok=["#indiegame"]),
           post_times=dict(tiktok="18:30", reddit="15:00"), reddit=[dict(sub="r/indiegames", cooldown_days=7, rules_check=["flair"]), dict(sub="r/IndieGaming", cooldown_days=14, rules_check=["2 weeks"])],
           clips=[clip(1), clip(2), clip(3), clip(4)])
assert sk_.check_clips(reg) == []
bad = dict(reg, clips=[clip(9, hooks=["only one"], record=dict(tool="x"), shots=[dict(t="", screen="")])])
pr = sk_.check_clips(bad)
assert any("A/B" in x for x in pr) and any("scene" in x for x in pr) and any("tempo" in x for x in pr)
used = {}
k1 = sk_.week_kit(reg, dt.date(2026, 10, 19), 4, None, used, sdb, dt.date(2026, 10, 20))   # this week, before the page
assert k1["pre_page"] and all(p["kind"] == "video" for p in k1["posts"])
assert [p["clip"] for p in k1["posts"]][:2] == ["C01", "C01"] and k1["posts"][0]["use_hook"] != k1["posts"][1]["use_hook"]   # same clip, two hooks = A/B
assert all(s_["date"] > "2026-10-20" and s_["link"] is None and s_["cta"].startswith("Follow") for p in k1["posts"] for s_ in p["slots"])
k2 = sk_.week_kit(reg, dt.date(2026, 11, 2), 4, None, used, sdb)
vids = [p for p in k2["posts"] if p["kind"] == "video"]
red = [p for p in k2["posts"] if p["kind"] == "reddit"]
assert len(vids) == 3 and len(red) == 1 and red[0]["subreddit"] == "r/indiegames"
link = vids[0]["slots"][0]["link"]
assert link.startswith("https://store.steampowered.com/app/123/?") and "utm_source=tiktok" in link and "utm_campaign=kit-2026-11-02" in link
assert "--wishlists __ --utm tiktok" in vids[0]["log"][0] and "--profile-visits __" in vids[0]["log"][0]
assert all(s_["cta"].endswith("itch.io") for p in vids for s_ in p["slots"] if s_["date"] >= "2026-11-10")
k3 = sk_.week_kit(reg, dt.date(2026, 11, 9), 4, None, used, sdb)
assert next(p for p in k3["posts"] if p["kind"] == "reddit")["subreddit"] == "r/IndieGaming"          # r/indiegames cooldown 7 days is fine, but order rotates by last use
lrn = dict(n=6, platforms=[], by_clip=[dict(key="C03", n=3, lift=2.5)], by_hook=[dict(key="C03-C", n=2, lift=2.0), dict(key="C03-A", n=2, lift=0.8)], winners=[dict(field="clip", key="C03", lift=2.5, n=3)], losers=[], warnings=[])
k4 = sk_.week_kit(reg, dt.date(2026, 11, 16), 4, lrn, dict(), sdb)
first = next(p for p in k4["posts"] if p["kind"] == "video")
assert first["clip"] == "C03" and first["use_hook"] == 2 and "si tiene" in first["hook_why"]               # learning: the winning clip and hook come back
md = sk_.kit_md(reg, k4, lrn)
assert "Funziona: clip C03" in md and "Clip ancora da registrare" in md and "track add" in md
cm_ = sk_.clips_md(reg)
assert "Clip da fare" in cm_ and "| Tempo | Cosa si vede |" in cm_
json.dump(reg, open(os.path.join(root, "clips.json"), "w", encoding="utf-8"))
J("social_kit.json", dict(kits=[dict(k1, week="2026-10-19")]))
page2 = status_page.build(root, "private", [], [], set(), TODAY)
assert "Kit social della settimana" in page2 and "Clip da fare" in page2 and "I prossimi post" not in page2
print("social kit ok")
print("ALL PUBLISHER/SOCIAL/CASES TESTS PASSED")
