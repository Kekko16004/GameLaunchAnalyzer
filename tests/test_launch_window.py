"""launch_window.py: crowding arithmetic, ranking, verdict, inputs (watchlist + window.csv), bad rows reported, CLI (cp1252 console), chart group."""
import os, sys, csv, json, tempfile, subprocess, datetime as dt, re
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("launch_window must not use the network")
common.http_get = no_net
import launch_window as lw, report_charts as rc
D = dt.date

# ---- arithmetic: launch Monday 2027-03-01, week midpoint = Thursday 03-04
items = [dict(date=D(2027, 3, 2), name="A", kind="competitor", weight=3.0), dict(date=D(2027, 3, 9), name="B", kind="big_release", weight=4.0), dict(date=D(2027, 3, 18), name="C", kind="sale", weight=2.0)]
s, near = lw.score_week(D(2027, 3, 1), items); assert s == 3 * 1.0 + 4 * 0.5 + 2 * 0.25 == 5.5, s       # same week / one week away / two weeks away
assert [n["name"] for n in near] == ["A", "B", "C"]
s2, _ = lw.score_week(D(2027, 3, 8), items); assert s2 == 3 * 0.5 + 4 * 1.0 + 2 * 0.5 == 6.5, s2
assert lw.score_week(D(2027, 6, 7), items)[0] == 0
assert lw.week_start(D(2027, 3, 7)) == D(2027, 3, 1) and lw.factor(3) == 1 and lw.factor(4) == 0.5 and lw.factor(18) == 0

res = lw.analyse(items, D(2027, 3, 1), D(2027, 2, 1), D(2027, 4, 30))
byw = {w["week"]: w for w in res["weeks"]}
assert byw["2027-03-01"]["chosen"] and byw["2027-03-01"]["score"] == 5.5 and sum(w["chosen"] for w in res["weeks"]) == 1
assert res["chosen"]["verdict"] == "affollata" and res["chosen"]["quieter_weeks_pct"] >= 75, res["chosen"]
assert res["best"][0]["score"] == 0 and len(res["best"]) == 5 and sum(1 for w in res["weeks"] if w.get("best")) == 3
quiet = lw.analyse(items, D(2027, 4, 19), D(2027, 2, 1), D(2027, 4, 30)); assert quiet["chosen"]["verdict"] == "libera" and quiet["chosen"]["score"] == 0
out_of_range = lw.analyse(items, D(2027, 3, 1), D(2027, 4, 5), D(2027, 4, 30)); assert any(w["chosen"] for w in out_of_range["weeks"])   # chosen week outside the range is still scored

# ---- inputs
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "_raw"))
with open(os.path.join(d, "watchlist.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow("date appid name role reviews_total reviews_positive pct_positive price_cents discount_pct players coming_soon release_date".split())
    w.writerow(["2026-10-01", 111, "Rival One", "competitor", "", "", "", "", "", "", 1, "2027-03-03"]); w.writerow(["2026-10-08", 111, "Rival One", "competitor", "", "", "", "", "", "", 1, "2027-03-02"])   # latest snapshot wins
    w.writerow(["2026-10-08", 222, "Rival Vague", "competitor", "", "", "", "", "", "", 1, "Q1 2027"]); w.writerow(["2026-10-08", 333, "My comp", "comp", "", "", "", "", "", "", 0, "2027-03-02"])
wl, bad1 = lw.read_watchlist(os.path.join(d, "watchlist.csv"))
assert [(i["name"], i["date"].isoformat()) for i in wl] == [("Rival One", "2027-03-02")] and bad1 == ["Rival Vague (release date 'Q1 2027')"], (wl, bad1)
with open(os.path.join(d, "window.csv"), "w", encoding="utf-8", newline="") as f:
    f.write("date,name,kind,weight,source,note\n2027-03-09,Big Co,big_release,5,steamdb upcoming,\n2027-03-30,Spring sale,sale,,steam,\nsoon,Nothing,festival,3,,\n2027-03-10,Odd,party,3,,\n2027-03-12,Heavy,competitor,99,,\n")
wi, bad2 = lw.read_window(os.path.join(d, "window.csv"))
assert [i["name"] for i in wi] == ["Big Co", "Spring sale", "Heavy"] and wi[1]["weight"] == 2.0 and wi[2]["weight"] == 5.0 and len(bad2) == 2, (wi, bad2)

# the same rival in watchlist.csv and window.csv counts once, with the higher weight
dup = lw.dedupe([dict(date=D(2027, 3, 2), name="Rival One", kind="competitor", weight=3.0), dict(date=D(2027, 3, 2), name="rival one", kind="competitor", weight=4.0), dict(date=D(2027, 3, 3), name="Rival One", kind="competitor", weight=3.0)])
assert len(dup) == 2 and max(i["weight"] for i in dup) == 4.0

# ---- CLI under a cp1252 console (the report uses ◀ and ★)
def run(*a):
    return subprocess.run([sys.executable, os.path.join(R, "launch_window.py")] + list(a), capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
r = run("plan", "--launch", "2027-03-01", "--from", "2027-02-01", "--to", "2027-04-30", "--watchlist", os.path.join(d, "watchlist.csv"), "--csv", os.path.join(d, "window.csv"), "--today", "2026-10-07", "--no-steam-events", "-o", os.path.join(d, "_raw", "window.json"))
assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
text = r.stdout.decode("utf-8")
assert "◀ la tua" in text and "Voci non conteggiate" in text and "Rival Vague" in text and "una settimana libera qui non è libera nel mondo" in text and "Conteggiate **4** voci" in text, text[:600]
win = json.load(open(os.path.join(d, "_raw", "window.json"))); assert win["counted"] == 4 and win["chosen"]["week"] == "2027-03-01"
assert run("add", "--date", "2027-03-05", "--name", "Added", "--kind", "festival", "--csv", os.path.join(d, "window.csv")).returncode == 0
assert run("add", "--date", "2027-03-05", "--name", "added", "--csv", os.path.join(d, "window.csv")).returncode == 0       # same date + name: not duplicated
assert open(os.path.join(d, "window.csv"), encoding="utf-8").read().count("Added") == 1
assert run("add", "--date", "5 marzo", "--name", "X", "--csv", os.path.join(d, "window.csv")).returncode != 0
assert run("plan", "--launch", "2027-03-01", "--from", "2027-05-01", "--to", "2027-04-01").returncode != 0

# ---- chart group in the reports
open(os.path.join(d, "REPORT.md"), "w", encoding="utf-8").write("# R\n\n## 9. Piano piattaforme e calendario\ntesto\n")
gs = {g["key"]: g for g in rc.groups(d, D(2026, 10, 7))}
assert "window" in gs and len(gs["window"]["charts"]) == 2, list(gs)
html = "".join(gs["window"]["charts"]); assert "Quanto è affollata ogni settimana" in html and "la tua settimana" in html and "Cosa pesa sulla tua settimana" in html and "NaN" not in html
assert "Settimana dal 2027-03-01 (la tua)" in html
print("ALL LAUNCH_WINDOW TESTS PASSED")
