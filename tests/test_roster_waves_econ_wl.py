"""Offline tests: roster determinism and jury, focus-group waves (metrics, delta, timeline), economic plan,
wishlist tracker alerts and the status page (escaping, audiences)."""
import os, sys, json, random, tempfile, datetime as dt, csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
os.environ["GLS_HOME"] = tempfile.mkdtemp()  # never read the user's real calibration or keys
import roster, fg_waves, calc_econ, wl_track, status_page

# ---- roster: deterministic, append-only, stable jury, mandatory dissent
CA, CB = ["veterani", "min-maxer", "critici"], ["casual", "scroller", "valore"]
def make(n): return [roster.build_tester(g, i, c, "seed", roster.parse_langs(roster.LANGS)) for g, c in (("A", CA), ("B", CB)) for i in range(1, n + 1)]
a, b = make(12), make(40)
assert {t["id"]: t for t in b}.items() >= {t["id"]: t for t in a}.items(), "existing testers changed when appending"
assert make(12) == a, "roster not deterministic"
ja, jb = roster.pick_jury(a), roster.pick_jury(b)
assert ja == jb and len(ja) == 10 and {"principiante", "scettico", "impaziente", "accessibilità", "bastian contrario"} <= {j["role"] for j in ja}
for g, cohorts in (("A", CA), ("B", CB)):
    for c in cohorts:
        m = [t for t in b if t["group"] == g and t["cohort"] == c]; assert sum(t["contrarian"] for t in m) / len(m) >= 0.20
print("roster ok: deterministic, append-only, jury stable")

# ---- waves
rnd = random.Random(3)
def wave(n, date, p, issue_p, fixes=None):
    ts = [dict(id=t["id"], verdict=rnd.choices(["WISHLIST", "SALDI", "IGNORO", "REFUND"], p)[0], click=rnd.random() < .4, pitch_ok=rnd.random() < .6,
               issues=[k for k, q in issue_p.items() if rnd.random() < q]) for t in a]
    w = dict(wave=n, date=date, build=f"v0.{n}", testers=ts, issues=[dict(key="slow", label="Apertura lenta", severity="alta", recommendation="x"), dict(key="ui", label="UI", severity="media")])
    if fixes: w["fixes"] = fixes
    return w
d = tempfile.mkdtemp(); wd = os.path.join(d, "waves"); os.makedirs(wd)
for n, (date, p, ip, fx) in enumerate([("2026-10-06", [.15, .3, .45, .1], {"slow": .6, "ui": .3}, None), ("2026-10-27", [.3, .3, .35, .05], {"slow": 0.0, "ui": .3}, [dict(issue="slow", what="shorter tutorial")])], 1):
    json.dump(wave(n, date, p, ip, fx), open(os.path.join(wd, f"w{n:02d}-{date}.json"), "w"))
rost = {"testers": a}; json.dump(rost, open(os.path.join(d, "roster.json"), "w"))
w1, w2 = (fg_waves.load_wave(os.path.join(wd, f), rost) for f in sorted(os.listdir(wd)))
m1, m2 = fg_waves.metrics(w1), fg_waves.metrics(w2)
exp = round((sum(1 for t in w1["testers"] if t["verdict"] == "WISHLIST") * 1 + sum(1 for t in w1["testers"] if t["verdict"] == "SALDI") * .4
             - sum(1 for t in w1["testers"] if t["verdict"] == "IGNORO") * .2 - sum(1 for t in w1["testers"] if t["verdict"] == "REFUND") * .8) / 24 * 100, 1)
assert m1["score"] == exp and m1["gate"]["threshold"] == 35.0
assert m1["buy"]["n"] == 0 and "Pagherebbe" not in fg_waves.md_metrics(m1)   # optional field: absent unless the panel was asked
wb = dict(w1, testers=[dict(t, would_buy=(i % 4 == 0)) for i, t in enumerate(w1["testers"])], stage="beta")
mb = fg_waves.metrics(wb); assert mb["buy"] == dict(n=24, yes=6, pct=25.0), mb["buy"]
assert "Pagherebbe il prezzo previsto: 6 su 24 (25%)" in fg_waves.md_metrics(mb) and "· beta" in fg_waves.md_metrics(mb).splitlines()[0]
assert "Wishlist score" not in fg_waves.md_metrics(mb) and "Punteggio wishlist" in fg_waves.md_metrics(mb)   # plain Italian in what the owner reads
# stage inferred from the file name (-beta / -full) or the label when the key is missing
assert fg_waves.infer_stage({}, "w03-2026-10-07-full.json") == "full" and fg_waves.infer_stage({"label": "beta gratuita"}) == "beta" and fg_waves.infer_stage({"label": "proiezione gioco completo"}) == "full" and fg_waves.infer_stage({"label": "baseline"}) == ""
txt = fg_waves.md_delta(w1, w2, m1, m2, 10.0); assert "RISOLTO" in txt and "shorter tutorial" in txt and "Cosa è cambiato" in txt
bad = dict(w1); bad["testers"] = [dict(t) for t in w1["testers"]]; bad["testers"][0]["verdict"] = "boh"; json.dump(bad, open(os.path.join(d, "bad.json"), "w"))
try: fg_waves.load_wave(os.path.join(d, "bad.json")); raise AssertionError("invalid verdict accepted")
except SystemExit as e: assert "verdict" in str(e)
sys.argv = ["x", "timeline", wd, "--roster", os.path.join(d, "roster.json"), "--csv", os.path.join(d, "tl.csv"), "-o", os.path.join(d, "tl.md")]; fg_waves.main()
assert "Focus group: andamento delle ondate" in open(os.path.join(d, "tl.md"), encoding="utf-8").read(); print("waves ok: score", m1["score"], "->", m2["score"])

# ---- economics (independent arithmetic)
o = calc_econ.compute({**calc_econ.DEFAULTS, "price": 14.99, "costs": 3500, "hours": 600, "hourly": 12, "partners": 2, "wishlists": "3000,8000,20000", "conv": "0.1,0.2,0.3"})
net = 14.99 * .85 * .90 * .94 * .70
assert abs(o["net_per_copy"] - round(net, 2)) < 1e-9 and o["breakeven"]["copies_cash"] == -(-3500 // net) and o["scenarios"][1]["copies"] == 1600
try: calc_econ.compute({**calc_econ.DEFAULTS, "price": 0}); raise AssertionError
except SystemExit: pass
print("econ ok: net per copy", o["net_per_copy"])

# ---- wishlist tracker
rows = [dict(date=x, wishlists=v, followers=None, note="") for x, v in (("2026-10-01", 200), ("2026-10-15", 520), ("2026-11-05", 1400), ("2026-11-19", 1500), ("2026-11-26", 1100))]
plan = dict(start="2026-10-01", launch="2027-03-01", targets={"pess": 3000, "base": 8000}, tripwires=[dict(date="2026-11-15", min_wishlists=2500, label="T1", emergency="cut ads"),
            dict(date="2027-01-15", min_wishlists=5000, label="T2"), dict(date="2026-09-01", min_wishlists=1, label="T0")])
r = wl_track.analyse(rows, plan, dt.date(2026, 12, 3))
st = {t["label"]: t["status"] for t in r["tripwires"]}; assert st == {"T1": "ALLARME", "T2": "IN ATTESA", "T0": "SENZA DATI"}, st
assert any(x["level"] == "ALARM" and "cut ads" in x["text"] for x in r["alerts"]) and r["pace"].startswith("sotto")
assert wl_track.at(rows, dt.date(2026, 10, 8)) == 200 + (520 - 200) * 7 / 14 and wl_track.at(rows, dt.date(2026, 9, 1)) is None
print("wishlist tracker ok:", st)

# ---- status page: escaping, audiences
L = os.path.join(d, "launch"); os.makedirs(os.path.join(L, "fg")); os.makedirs(os.path.join(L, "_raw"))
json.dump(dict(game="<script>alert(1)</script>", verdict=dict(color="rosso", summary="<img src=x onerror=alert(1)>", risks=["r"]), gates={"A": dict(state="fail", note="n")}), open(os.path.join(L, "status.json"), "w"))
open(os.path.join(L, "REPORT.md"), "w").write("# R\n[bad](javascript:alert(1)) **ok**\n"); open(os.path.join(L, "08-brand-legal.md"), "w").write("# Legal\nSECRET-TAX\n")
open(os.path.join(L, "03-pricing.md"), "w").write("# P\nPRICING-INTERNAL\n"); json.dump(o, open(os.path.join(L, "_raw", "econ.json"), "w"))
for aud, has_tax, has_econ, has_pricing in (("private", True, True, True), ("partner", False, True, True), ("publisher", False, False, False)):
    page = status_page.build(L, aud, [], [], set(), dt.date(2026, 12, 3))
    assert "<script>alert" not in page.replace("<script>" + status_page.JS, "") and "<img src=x" not in page and "javascript:alert" not in page, aud
    assert ("SECRET-TAX" in page) == has_tax and ("Economia" in page) == has_econ and ("PRICING-INTERNAL" in page) == has_pricing, aud
    assert "https://" not in page.replace("http://www.w3.org", ""), "page must not load external resources"
print("status page ok: escaping and audiences")
print("ALL ROSTER/WAVES/ECON/WL/STATUS TESTS PASSED")
