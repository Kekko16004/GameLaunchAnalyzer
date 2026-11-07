"""scope_calc.py (hours needed vs available, comps' playtime from the review caches, warnings at 1.5 and 3) and genre_patterns.py
(corpus runs merged once into the user folder, suggestions with evidence). Offline, temp dirs only, GLS_HOME isolated."""
import os, sys, json, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import scope_calc as sc


def run(script, *args, env=None, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(R, script), *args], capture_output=True, cwd=cwd,
                       env=dict(os.environ, PYTHONIOENCODING="cp1252", **(env or {})))
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


for s in ("scope_calc.py", "genre_patterns.py"):
    code, out, err = run(s, "self-test", env={"GLS_HOME": tempfile.mkdtemp()})
    assert code == 0 and "self-test OK" in out, s + out + err

# ---- scope_calc: rates are opinions, every unit documented
rates = sc.load_rates()
assert rates["_label"] == "[OPINIONE]" and all(v["hours"] >= 0 and v["what"] for v in rates["units"].values())
d = tempfile.mkdtemp()
cache = os.path.join(d, "corpus")
os.makedirs(cache)
json.dump([{"playtime_forever_h": h, "playtime_at_review_h": 1} for h in (10, 20, 30)], open(os.path.join(cache, "11_negative.json"), "w"))
json.dump([{"playtime_forever_h": None, "playtime_at_review_h": 40}], open(os.path.join(cache, "11_positive.json"), "w"))
small = {"content": {"enemies": 2, "items": 4}, "capacity": {"people": 2, "hours_per_week": 20, "weeks": 30}}
r = sc.calc(small, rates, cache)
assert r["ratio"] < 1 and r["verdict"] == "ci sta" and r["scope_score"] == 5 and not r["notes"]
huge = {"content": {"levels": 40, "bosses": 10, "mechanics": 12}, "capacity": {"people": 1, "hours_per_week": 10, "weeks": 26},
        "target_hours": 25, "price_usd": 20, "comps": [{"appid": 11, "name": "Undici", "price_usd": 10}, {"appid": 99}]}
r = sc.calc(huge, rates, cache)
assert r["ratio"] >= 3 and r["verdict"] == "fuori scala" and r["scope_score"] == 1 and any("altro gioco" in n for n in r["notes"])
assert r["comps"][0]["median_h"] == 25.0 and r["comps"][0]["reviews"] == 4 and r["comps"][1]["median_h"] is None   # 10,20,30 + 40 (at review)
assert r["rows"][0]["item"] == "levels" and r["weeks_needed"] > 26
mine = os.path.join(d, "mine.json")
json.dump({"units": {"levels": 5}, "productive_share": 1.0}, open(mine, "w"))
assert sc.calc(huge, sc.load_rates(mine), cache)["needed_h"] < r["needed_h"]
inp = os.path.join(d, "scope.json")
json.dump(huge, open(inp, "w"))
code, out, err = run("scope_calc.py", "calc", "--input", inp, "--corpus-dir", cache, "--md", os.path.join(d, "scope.md"))
md = open(os.path.join(d, "scope.md"), encoding="utf-8").read()
assert code == 0 and "fuori scala" in out and "⚠⚠" in err and "Quanto si giocano i comparabili [FATTO]" in md and "| Undici | 25.0 |" in md, md
code, out, _ = run("scope_calc.py", "rates")
assert code == 0 and "[OPINIONE]" in out

# ---- genre_patterns: build from launch/_raw/corpus*.json in the project, merge once, suggest with evidence
home = tempfile.mkdtemp()
proj = tempfile.mkdtemp()
os.makedirs(os.path.join(proj, "launch", "_raw"))
corpus = {"generated": "2026-11-02", "params": {"genre_tag": ["Cozy", "Farming Sim"]},
          "groups": {"all": {"games": 12, "reviews_negative": 1000, "reviews_positive": 800,
                             "punished": [{"theme": "onboarding_tutorial", "macro_pct": 9.5, "breadth": 5, "games": 12}],
                             "rewarded": [{"theme": "relaxing_cozy", "macro_pct": 22.0, "breadth": 11, "games": 12}]}}}
json.dump(corpus, open(os.path.join(proj, "launch", "_raw", "corpus.json"), "w"))
json.dump({"generated": "2026-11-03", "groups": {"all": {"games": 3, "punished": [], "rewarded": []}}},
          open(os.path.join(proj, "launch", "_raw", "corpus-nogenre.json"), "w"))
env = {"GLS_HOME": home}
code, out, _ = run("genre_patterns.py", "build", env=env, cwd=proj)
assert code == 0 and "cozy+farming sim" in out and "nessun genere" in out, out
code, out, _ = run("genre_patterns.py", "build", env=env, cwd=proj)
assert "niente di nuovo" in out
store = json.load(open(os.path.join(home, "genre_patterns.json"), encoding="utf-8"))
assert list(store["genres"]) == ["cozy+farming sim"] and len(store["genres"]["cozy+farming sim"]["runs"]) == 1
code, out, _ = run("genre_patterns.py", "suggest", "--genre", "cozy", "--json", env=env, cwd=proj)
s = json.loads(out)
assert s["found"] and s["games"] == 12 and {c["theme"] for c in s["candidates"]} == {"onboarding_tutorial", "relaxing_cozy"}
assert all(c["label"] == "[OPINIONE]" and c["evidence"]["label"] == "[FATTO]" and "2026-11-02" in c["evidence"]["source"] for c in s["candidates"])
code, out, _ = run("genre_patterns.py", "show", env=env, cwd=proj)
assert code == 0 and "1 corpus, 12 giochi" in out
code, out, _ = run("genre_patterns.py", "suggest", "--genre", "racing", env=env, cwd=proj)
assert code == 0 and "nessun dato" in out
assert not os.path.exists(os.path.join(proj, "genre_patterns.json"))      # never inside the project / repository
print("scope_calc + genre_patterns OK")
