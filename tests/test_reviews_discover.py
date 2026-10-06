import os
"""Offline tests for steam_reviews / steam_discover with canned API-shaped responses."""
import sys, json, time, urllib.parse, io, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import common

NOW = int(time.time())
def mk(i, neg=True, days_ago=10, play=300, votes=5, text="boring and repetitive, crashes"):
    return {"recommendationid": str(i), "author": {"steamid": f"7656{i:013d}", "playtime_at_review": play, "playtime_forever": play + 10},
            "language": "english", "review": text, "timestamp_created": NOW - days_ago * 86400, "voted_up": not neg,
            "votes_up": votes, "votes_funny": 0, "weighted_vote_score": "0.55", "steam_purchase": True,
            "received_for_free": False, "written_during_early_access": False}

calls = []
def fake_get(url, **kw):
    calls.append(url)
    u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if "appdetails" in u.path:
        return json.dumps({"42": {"success": True, "data": {"name": "Test Game"}}}).encode()
    if "appreviews" in u.path:
        cur = qs["cursor"][0]; page = 0 if cur == "*" else int(cur.split("=")[0].lstrip("C"))   # cursors look like "C1="
        revs = []
        for j in range(100):
            i = page * 100 + j
            revs.append(mk(i, days_ago=i // 2, play=60 if i % 3 == 0 else 600, votes=i % 7,
                           text=("Refund. so many bugs and the tutorial is confusing" if i % 4 == 0 else
                                 "too short for the price" if i % 4 == 1 else "fun but laggy fps stutter" if i % 4 == 2 else "meh")))
        if page == 1: revs[5] = revs[4]                      # duplicate id must be dropped
        nxt = f"C{page+1}=" if page < 2 else cur             # last page returns the same cursor -> must stop
        return json.dumps({"success": 1, "query_summary": {"num_reviews": 100, "total_negative": 777}, "reviews": revs, "cursor": nxt}).encode()
    if "storesearch" in u.path:
        return json.dumps({"total": 2, "items": [{"type": "app", "name": "PlateUp!", "id": 1599600, "price": {"currency": "USD", "initial": 1999, "final": 1999}, "metascore": ""},
                                                   {"type": "bundle", "name": "X", "id": 1}]}).encode()
    if "steamspy" in u.netloc:
        tag = qs["tag"][0]
        base = {"1": {"name": "Hit", "developer": "d", "positive": 90000, "negative": 10000, "owners": "1,000,000 .. 2,000,000", "price": "1999"},
                "2": {"name": "Mid", "developer": "d", "positive": 900, "negative": 100, "owners": "20,000 .. 50,000", "price": "999"}}
        if tag == "Cooking": base = {"2": base["2"], "3": {"name": "Flop", "developer": "d", "positive": 5, "negative": 40, "owners": "0 .. 20,000", "price": "499"}}
        return json.dumps(base).encode()
    raise AssertionError(url)
common.http_get = fake_get

import steam_reviews as sr, steam_discover as sd
def run(mod, argv):
    sys.argv = ["x"] + argv; buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()): mod.main()
    return buf.getvalue()

# 1) basic paging, dedupe, stop on repeated cursor, limit
out = json.loads(run(sr, ["42", "--limit", "500", "--rate", "0"]))
g = out["games"][0]; ids = [r["recommendation_id"] for r in g["reviews"]]
assert g["name"] == "Test Game" and len(ids) == len(set(ids)) == 299, len(ids)       # 300 minus one duplicate
assert g["reviews"][0]["url"].endswith("/recommended/42/") and "name" not in g["reviews"][0]
assert g["summary"]["themes"]["bugs_crashes"]["pct"] > 0 and g["summary"]["themes"]["performance"]["count"] > 0
assert g["summary"]["themes"]["refund_mentions"]["count"] == sum("refund" in r["text"].lower() for r in g["reviews"])
print("1 ok: paging/dedupe/themes ->", len(ids), "reviews;", {k: v["pct"] for k, v in list(g["summary"]["themes"].items())[:4]})
# 2) filters
o = json.loads(run(sr, ["42", "--limit", "500", "--max-playtime-h", "2", "--min-votes-up", "3", "--rate", "0"]))["games"][0]
assert o["reviews"] and all(r["playtime_at_review_h"] <= 2 and r["votes_up"] >= 3 for r in o["reviews"]); print("2 ok: playtime/votes filters ->", len(o["reviews"]))
# 3) within-days, recent sort stops early
calls.clear()
o = json.loads(run(sr, ["42", "--sort", "recent", "--within-days", "20", "--limit", "500", "--rate", "0"]))["games"][0]
assert o["reviews"] and all(r["date"] >= time.strftime("%Y-%m-%d", time.gmtime(NOW - 21 * 86400)) for r in o["reviews"]), o["sampled"]
assert sum("appreviews" in c for c in calls) == 1, "recent sort must stop after the first page that crosses the cutoff"
print("3 ok: within-days + early stop ->", o["sampled"], "reviews,", sum("appreviews" in c for c in calls), "page")
# 4) day_range only with helpful, capped at 365; csv output
calls.clear(); run(sr, ["42", "--within-days", "900", "--limit", "5", "--rate", "0"])
assert "day_range=365" in [c for c in calls if "appreviews" in c][0]; print("4 ok: day_range capped at 365")
import tempfile, os, csv
p = os.path.join(tempfile.mkdtemp(), "r.csv"); run(sr, ["42", "--limit", "10", "--rate", "0", "-o", p])
rows = list(csv.DictReader(open(p, encoding="utf-8-sig"))); assert len(rows) == 10 and rows[0]["name"] == "Test Game"; print("5 ok: csv ->", list(rows[0])[:5])
# 6) discover
s = json.loads(run(sd, ["--rate", "0", "search", "plateup", "-o", "-"]))
assert len(s) == 1 and s[0]["appid"] == 1599600 and s[0]["price_final_cents"] == 1999; print("6 ok: search skips bundles")
t = json.loads(run(sd, ["--rate", "0", "tag", "Roguelike", "Cooking", "-o", "-"]))
assert [r["appid"] for r in t] == [2, 1, 3] and t[0]["matched_tags"] == "Roguelike; Cooking", [(r["appid"], r["matched_tags"]) for r in t]
t2 = json.loads(run(sd, ["--rate", "0", "tag", "Roguelike", "Cooking", "--require-all", "--max-reviews", "5000", "-o", "-"]))
assert [r["appid"] for r in t2] == [2]; print("7 ok: tag ranking (matches first, then reviews), --require-all, --max-reviews")
print("ALL OFFLINE TESTS PASSED")
