"""Tag resolution: 'Roguelite' makes SteamSpy return another tag's list, 'Rogue-lite' is the right one; variants and typos."""
import os, sys, json, urllib.parse, io, contextlib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import common
GAMES = {}                                   # appid -> tags it really carries
for i in range(1, 31): GAMES[i] = {"Rogue-lite": 100, "Action": 50}
for i in range(31, 61): GAMES[i] = {"Roguelike": 100}
for i in range(61, 71): GAMES[i] = {"Rogue-like": 100}
for i in range(101, 131): GAMES[i] = {"Strategy": 100}
state = {"live_tags": True, "appdetails": True}
def listing(tag):
    ids = [i for i, t in GAMES.items() if tag in t]                          # exact, case-sensitive: what a correct list looks like
    if not ids and tag.lower().replace("-", "") == "roguelite": ids = list(range(101, 131))   # the reported bug: wrong list for the unhyphenated spelling
    return {str(i): {"name": f"G{i}", "positive": 1000 - i, "negative": 10} for i in ids}
def fake(url, **kw):
    u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if "populartags" in u.path:
        if not state["live_tags"]: raise OSError("blocked")
        return json.dumps([{"tagid": 1, "name": "Rogue-lite"}, {"tagid": 2, "name": "Roguelike"}, {"tagid": 3, "name": "Action"}, {"tagid": 4, "name": "Strategy"}]).encode()
    if "steamspy" in u.netloc and qs["request"][0] == "tag": return json.dumps(listing(qs["tag"][0])).encode()
    if "steamspy" in u.netloc and qs["request"][0] == "appdetails":
        if not state["appdetails"]: return b"{}"
        return json.dumps({"tags": GAMES.get(int(qs["appid"][0]), {})}).encode()
    raise AssertionError(url)
common.http_get = fake; common.set_rate(0)
import steam_tags as st, steam_discover as sd
def quiet(fn, *a, **k):
    with contextlib.redirect_stderr(io.StringIO()): return fn(*a, **k)

assert st.norm("Rogue-lite") == st.norm("ROGUE LITE") == st.norm("roguelite") == "roguelite"
# 1) the reported case
games, rep = quiet(st.collect, "Roguelite")
ids = {int(a) for a in games}; assert ids == set(range(1, 31)), sorted(ids)[:5]
assert "Rogue-lite" in rep["accepted"] and "Roguelite" in rep["rejected"] and "exact" in rep["understood"]
# without the check the wrong list leaks in: this is what the verification protects against
leak, _ = quiet(st.collect, "Roguelite", validate=False); assert 101 in {int(a) for a in leak}
# literal spelling only (--exact-tags): the wrong list is discarded and nothing wrong is returned
only, rep2 = quiet(st.collect, "Roguelite", variants=False); assert only == {} and rep2["rejected"] == ["Roguelite"]
print("reported case ok: Roguelite -> Rogue-lite, wrong list discarded")
# 2) variants of the same family are merged: Roguelike + Rogue-like (the second only exists in the built-in list)
games, rep = quiet(st.collect, "roguelike"); ids = {int(a) for a in games}
assert ids == set(range(31, 71)) and set(rep["accepted"]) == {"Roguelike", "Rogue-like"}, rep
# 3) typos and separators
for typo in ("rogueliek", "Rogue Like", "ROGUELIKE", "roguelik"):
    g, r = quiet(st.collect, typo); assert {int(a) for a in g} >= set(range(31, 61)), (typo, r["understood"])
assert "corrected" in quiet(st.collect, "rogueliek")[1]["understood"]
g, r = quiet(st.collect, "rogue lite"); assert {int(a) for a in g} == set(range(1, 31))
assert quiet(st.collect, "zzzzzz")[0] == {}
print("variants and typos ok")
# 4) live tag list unavailable: built-in list is enough
st._official = None; state["live_tags"] = False
g, r = quiet(st.collect, "Roguelite"); assert {int(a) for a in g} == set(range(1, 31)); state["live_tags"] = True; st._official = None
# 5) SteamSpy appdetails unavailable: lists cannot be verified, they are used as they are (with a note) instead of returning nothing
state["appdetails"] = False; g, r = quiet(st.collect, "Rogue-lite"); assert {int(a) for a in g} >= set(range(1, 31)) and r["unverified"], r; state["appdetails"] = True
# 6) candidates(): ranking, matched tags, require_all
rows = quiet(sd.candidates, ["Roguelite", "Action"], require_all=True)
assert rows and all(r["n_tags"] == 2 for r in rows) and {r["appid"] for r in rows} == set(range(1, 31)) and rows[0]["matched_tags"] == ["Roguelite", "Action"]
rows = quiet(sd.candidates, ["Roguelite"], variants=False); assert rows == []
print("ALL STEAM_TAGS TESTS PASSED")
