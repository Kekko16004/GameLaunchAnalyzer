"""Offline tests: Reddit cases (references/09-reddit-casi.md) in the case DB and in the social tools: anecdotal cases out of the
benchmarks, case benchmarks / factor weights / flop checklist in social_patterns.json, social_content.py flopcheck,
learn vs the cases, evidence, the kit section and the top_moves 'cases' source."""
import os as _os
_os.environ["GLS_REACH"] = "off"   # offline: never the real Agent Reach
import os, sys, json, tempfile, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
os.environ["GLS_HOME"] = tempfile.mkdtemp()
import social_content as sc, social_kit as sk, case_studies as cs, top_moves, common

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
db = sc.load_db()

# ---- case DB: stable ids, tiers, labels; anecdotal never in the benchmarks
cdb = common.load_json(os.path.join(ROOT, "scripts", "research", "data", "case_studies.json"))
recs = cdb["records"] if isinstance(cdb, dict) else cdb
rd = [r for r in recs if str(r.get("id", "")).startswith("rd-")]
assert len(rd) >= 200, len(rd)
assert len({r["id"] for r in recs}) == len(recs), "duplicate ids"
fac = [r for r in rd if r.get("tier") == "factored"]
ane = [r for r in rd if r.get("tier") == "anecdotal"]
assert len(fac) >= 50 and ane, (len(fac), len(ane))
assert {r.get("outcome") for r in fac} >= {"success", "flop"}
for r in fac:
    assert len(r.get("evidence") or []) >= 2, r["id"]            # at least 2 of the 4 criteria
    assert r.get("source_url", "").startswith("https://www.reddit.com/"), r["id"]
    assert "DA VERIFICARE" in (r.get("numbers_label") or ""), r["id"]
seed = {r["id"]: r for r in rd}
assert seed["rd-pennants-of-glory-2026-11"].get("appid") in (5087810, "5087810")
bench_ids = {r["id"] for r in recs if r.get("tier") != "anecdotal"}
assert not (bench_ids & {r["id"] for r in ane})
fake = [dict(id="a", game="ANEC_X", tier="anecdotal", event="next_fest", wishlists_before=500, wishlists_after=9000, source_url="u", source_date="2026-10-01"),
        dict(id="b", game="FACT_Y", tier="factored", event="next_fest", wishlists_before=500, wishlists_after=900, source_url="u", source_date="2026-10-01")]
tab = " ".join(cs.stage_table(fake, None))
assert "FACT_Y" in tab and "ANEC_X" not in tab

# ---- social_patterns.json: case benchmarks, factor weights, flop checklist
cb, fw, fl = db["case_benchmarks"], db["factor_weights"], db["flop_checklist"]
cv = cb["wishlists_per_1k_views"]
assert cv["youtube"]["median"] > 5 * cv["tiktok"]["median"]          # YouTube converts much better than TikTok in the cases
assert cv["reddit"]["median"] < 2 and cv["youtube_shorts"]["median"] < 3
assert all(v["n"] >= 3 and v["examples"] for v in cv.values())
assert all(1 <= f["weight_flop"] <= 5 and 1 <= f["weight_success"] <= 5 for f in fw["factors"].values())
assert fw["factors"]["creators_press"]["weight_success"] == 5           # the most credited factor in the success threads
assert max(f["weight_flop"] for f in fw["factors"].values()) == 5
ws = [i["weight"] for i in fl["items"]]
assert ws == sorted(ws, reverse=True) and len(fl["items"]) >= 12
assert {i["code"] for i in fl["items"]} <= set(fw["factors"])
idv = next(s for s in db["subreddits"] if s["sub"] == "r/IndieDev")
assert idv["fit_for_physics_comedy_roguelite"] == "low" and "cases_note" in idv
assert "r/IndieDev" not in [s["sub"] for s in sc.subreddit_queue(db)]
for p in ("reddit", "tiktok", "instagram", "youtube_shorts", "x"):
    v = db["platforms"][p]
    assert any(x["id"].startswith(("rd-cases", "tt-cases", "ig-cases", "ys-cases", "x-cases")) for x in v["patterns"]), p
    assert any(c.get("id") == f"cases-{p}" for c in v.get("conversion", [])), p
    for x in v["patterns"]:
        for s_ in x.get("sources", []):
            assert s_.get("url") and s_.get("date"), (p, x["id"])

# ---- flopcheck: auto checks on the page, answers, weights, risk
page = dict(appid=1, name="Fake", trailers=0, desc_chars=800, languages=12)
fc = sc.flopcheck(db, page, {"FC03": True, "wishlists": 1500})
st = {x["id"]: x["status"] for x in fc["items"]}
assert st["FC01"] == "fail" and st["FC05"] == "fail" and st["FC10"] == "ok" and st["FC09"] == "fail" and st["FC03"] == "ok", st
assert st["FC02"] == "todo"
assert fc["top_fixes"][0]["weight"] == max(x["weight"] for x in fc["items"] if x["status"] == "fail")
assert 0 < fc["risk"] < 1 and fc["level"] in ("alto", "medio", "basso")
assert sc.flopcheck(db, page, {"FC01": True})["items"][0]["status"] == "ok"      # an answer wins over the auto check
empty = sc.flopcheck(db, {}, {})
assert empty["risk"] is None and empty["todo"] == len(empty["items"])
md = sc.flopcheck_md(fc)
assert "DA SISTEMARE" in md and "Prima di tutto" in md and "09-reddit-casi" in md
assert sc.load_page(None) == {}
tmp = tempfile.mkdtemp()
pp = os.path.join(tmp, "pages.json")
json.dump([dict(appid=5, name="A"), dict(appid=7, name="B")], open(pp, "w"))
assert sc.load_page(pp, "7")["name"] == "B" and sc.load_page(pp)["name"] == "A"
out = os.path.join(tmp, "fc.json")
sc.main(["flopcheck", "--page", pp, "--appid", "7", "--answers", os.path.join(tmp, "none.json"), "-o", out, "--md", os.path.join(tmp, "fc.md")])
assert json.load(open(out, encoding="utf-8"))["game"] == "B"

# ---- evidence and plan cite the cases; learn compares with the cases
ev = sc.evidence_md(db)
assert "Casi reali" in ev and "Perché floppa" in ev and "flopcheck" in ev
assert "Casi reali" in sc.evidence_md(db, "tiktok")
mom = [dict(id="H1", label="crollo", kind="chaos", score=20)]
pl = sc.plan(db, mom, dt.date(2026, 11, 2), 2, {"reddit": 1, "tiktok": 2}, dt.date(2026, 11, 1))
pmd = sc.plan_md(pl, db)
assert "Quante wishlist portano 1.000 visualizzazioni" in pmd
assert any("sub di tema" in x["caption"] for x in pl["posts"] if x["platform"] == "reddit")
ln = sc.learn([dict(platform="tiktok", views="10000", wishlists_delta="20"), dict(platform="tiktok", views="5000", wishlists_delta="5")], db)
row = ln["platforms"][0]
assert row["cases_wishlists_per_1k"] == cv["tiktok"]["median"] and row["vs_cases"] == round(row["wishlists_per_1k"] / cv["tiktok"]["median"], 2)
assert "Casi reali" in sc.learn_md(ln)
assert sc.learn([dict(platform="x", views="100")])["platforms"][0]["vs_cases"] is None   # without db: no comparison, no crash

# ---- social kit: hooks and formats from the cases, with links
assert len(sk.CASE_HOOKS) >= 5 and all(h["url"].startswith("https://") for h in sk.CASE_HOOKS)
km = sk.kit_md(dict(game="G"), dict(week="2026-11-02", pre_page=True, posts=[]), None)
assert "Ganci e formati dai casi reali" in km and "Steel Command" in km

# ---- top_moves: aggregators after the trailer; flopcheck failures by weight
root = tempfile.mkdtemp()
os.makedirs(os.path.join(root, "_raw"))
open(os.path.join(root, "TODO.md"), "w", encoding="utf-8").write("# TODO\n\n## Adesso\n\n- [x] Montare il trailer\n")
c = [x for x in top_moves.candidates(root, dt.date(2026, 11, 3), None) if x["source"] == "cases"]
assert any(x["key"] == "cases-aggregators" and x["score"] == 32 for x in c), c
json.dump(fc, open(os.path.join(root, "_raw", "flopcheck.json"), "w", encoding="utf-8"))
open(os.path.join(root, "TODO.md"), "w", encoding="utf-8").write("# TODO\n\n## Adesso\n\n- [x] Montare il trailer\n- [x] Trailer a Indie Games Hub\n")
c = [x for x in top_moves.candidates(root, dt.date(2026, 11, 3), None) if x["source"] == "cases"]
assert not any(x["key"] == "cases-aggregators" for x in c)
fl_moves = [x for x in c if x["key"].startswith("flopcheck-")]
assert len(fl_moves) == 2 and all(x["score"] == 10 + 6 * next(i["weight"] for i in fc["items"] if f"flopcheck-{i['id']}" == x["key"]) for x in fl_moves)
assert len([x for x in top_moves.pick(c + c)]) <= 2                       # at most 2 per source

# ---- references/09 exists and is linked from 03, 05 and 07
ref = open(os.path.join(ROOT, "references", "09-reddit-casi.md"), encoding="utf-8").read()
for k in ("Pennants of Glory", "Nascor", "Susanoo", "PARAMETRI", "Anti-pattern", "Next Fest"):
    assert k in ref, k
for f in ("03-store-clips.md", "05-outreach-community-legal.md", "07-contingenze.md"):
    fp = os.path.join(ROOT, "references", f)
    if os.path.exists(fp):
        assert "09-reddit-casi.md" in open(fp, encoding="utf-8").read(), f

print("ALL REDDIT CASES TESTS PASSED")
