import sys, json, time, urllib.parse, io, contextlib, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import common
NOW = int(time.time()); calls = []
NEG = ["so repetitive and boring, got old fast", "tutorial is confusing, crashes and bugs everywhere", "the cooking is tedious, too short for the price",
       "co-op is broken, desync all the time", "meh, refund", "controls are clunky, fps stutter"]
POS = ["great fun and addictive, one more run!", "beautiful art style and the music is amazing", "love the cooking, so relaxing and cozy",
       "co-op with my friends is a blast", "worth every penny, replayability is endless", "tight controls and very polished"]
def fake(url, **kw):
    calls.append(url); u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if "appdetails" in u.path:
        aid = qs["appids"][0]; return json.dumps({aid: {"data": {"name": f"Game{aid}"}}}).encode()
    if "appreviews" in u.path:
        aid = int(u.path.split("/")[-1]); neg = qs["review_type"][0] == "negative"; pool = NEG if neg else POS
        revs = [{"recommendationid": f"{aid}-{neg}-{i}", "author": {"steamid": f"7656{aid:06d}{i:07d}", "playtime_at_review": 300, "playtime_forever": 400},
                 "language": "english", "review": pool[(i + aid) % len(pool)], "timestamp_created": NOW - 86400 * (i % 300), "voted_up": not neg,
                 "votes_up": i % 9, "votes_funny": 0, "weighted_vote_score": "0.5"} for i in range(100)]
        return json.dumps({"success": 1, "query_summary": {}, "reviews": revs, "cursor": "AoJ=" + str(len(calls))}).encode()
    if "steamspy" in u.netloc:
        return json.dumps({str(i): {"name": f"Game{i}", "positive": 900 + i, "negative": 100, "owners": "x", "price": "999"} for i in (11, 12, 13, 14)}).encode()
    raise AssertionError(url)
common.http_get = fake
import review_corpus as rc
d = tempfile.mkdtemp(); feats = os.path.join(d, "f.json"); json.dump({"cooking": "cook|recipe", "co-op": ["co-op", "coop"], "permadeath": "permadeath"}, open(feats, "w"))
def run(extra):
    sys.argv = ["x", "--comps", "1", "2", "--genre-tag", "Roguelike", "--max-genre-games", "3", "--neg-per-game", "60", "--pos-per-game", "40", "--my-features", feats,
                "--cache-dir", os.path.join(d, "c"), "--rate", "0", "-o", os.path.join(d, "o.json"), "--md", os.path.join(d, "o.md"), "--csv", os.path.join(d, "r.csv")] + extra
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()): rc.main()
run([]); n1 = sum("appreviews" in c for c in calls)
res = json.load(open(os.path.join(d, "o.json")))
assert [g["group"] for g in res["games"]] == ["comps", "comps", "genre", "genre", "genre"], res["games"]
assert all(g["negative"] == 60 and g["positive"] == 40 for g in res["games"])
assert set(res["groups"]) == {"comps", "genre", "all"}
pun = {r["theme"]: r for r in res["groups"]["all"]["punished"]}; rew = {r["theme"]: r for r in res["groups"]["all"]["rewarded"]}
assert pun["repetitive_shallow"]["macro_pct"] > 0 and "fun_addictive" in rew and rew["fun_addictive"]["breadth"] >= 1, (list(pun), list(rew))
ft = {f["feature"]: f for f in res["features"]["all"]}
assert ft["cooking"]["pos_n"] > 0 and ft["cooking"]["neg_n"] > 0 and ft["permadeath"]["verdict"] == "rarely discussed" and ft["permadeath"]["neg_n"] == 0, ft["permadeath"]
assert ft["co-op"]["pos_examples"] and ft["co-op"]["pos_examples"][0]["url"].startswith("https://steamcommunity.com/profiles/")
print("run 1 ok:", n1, "review requests;", {k: (v["verdict"], v["neg_share"], v["pos_share"]) for k, v in ft.items()})
calls.clear(); run([]); assert sum("appreviews" in c for c in calls) == 0, "cache must prevent refetching"; print("run 2 ok: fully served from cache")
txt = open(os.path.join(d, "o.md"), encoding="utf-8").read(); assert "5 giochi" in txt and "Cosa il pubblico punisce" in txt; print("ALL REVIEW_CORPUS TESTS PASSED")
