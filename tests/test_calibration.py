"""Calibration with REAL anchors, genre-weighted rubric, full evaluation + focus theme (04-focus-group.md 7.0b-7.0e).
anchor_band from real reviews; drift (outside band / moved from the previous wave) flagged loudly; anchor-normalized score
(piecewise-linear, exact at the anchors, slope 1 beyond them, offset when anchors are out of order); harshness guard;
genre weights (prior + real review themes, sum 1); delta with normalized scores and the focus-theme caveat; timeline
columns; wave_kit check: full-evaluation section, anchors, rubric dims are REQUIRED; metrics --strict exit 3. Offline."""
import os, sys, json, tempfile, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import fg_waves as fw
import wave_kit as wk

# ---- bands from real Steam reviews (data of 2026-10-19)
assert fw.anchor_band(97.8, 200163) == [80.7, 94.7]          # Balatro
assert fw.anchor_band(95.1, 84187) == [69.1, 83.1]           # How to Fish
assert fw.anchor_band(90.1, 26497) == [66.1, 80.1]           # CloverPit
assert fw.anchor_band(80.2, 86) == [5.1, 19.1]               # The Way of the Tray: few reviews = weak reach
assert fw.anchor_band(40, 50)[0] >= -27 and fw.anchor_band(100, 10**7)[1] <= 99.0

def tester(i, v, dims=None):
    t = {"id": i, "verdict": v, "issues": []}
    if dims is not None:
        t["dims"] = dims
    return t

D = dict(gameplay=7, art=6, content=6, clarity=7, value=7, social=7)
W = dict(gameplay=0.38, art=0.13, content=0.18, clarity=0.08, value=0.10, social=0.13)
def wave(n, verdicts, anchors, **kw):
    ts = [tester(f"{'A' if k % 2 == 0 else 'B'}-{k + 1:02d}", v, dict(D)) for k, v in enumerate(verdicts)]
    w = {"wave": n, "date": "2026-10-19", "testers": ts, "issues": [], "anchors": anchors, "rubric": {"genre": "physics_comedy_roguelite", "weights": W, "source": "test"}}
    w.update(kw)
    w["_defined"] = {}
    return w

# ---- anchors inside their bands: no drift, map exact at the anchors, piecewise between, slope 1 beyond
anchors = [{"name": "Balatro", "kind": "hit", "band": [80.7, 94.7], "score": 85.0},
           {"name": "CloverPit", "kind": "hit", "band": [66.1, 80.1], "score": 70.0},
           {"name": "Tray", "kind": "weak", "band": [5.1, 19.1], "score": 10.0}]
c = fw.calibration({"anchors": anchors})
assert not c["drift"] and c["enough"] and c["direction"] == "in linea", c
f = c["map"]
assert f(85.0) == 87.7 and f(70.0) == 73.1 and f(10.0) == 12.1        # exact at the anchors (band centres)
assert f(40.0) == round(12.1 + 30 * (73.1 - 12.1) / 60, 1)            # between anchors
assert f(95.0) == 97.7 and f(0.0) == 2.1 and f(200) == 100.0          # slope 1 beyond, clamped

# ---- a harsh panel: hits far below their bands -> drift, "troppo severo", the normalization lifts the score
harsh = [{"name": "Balatro", "kind": "hit", "band": [80.7, 94.7], "score": 55.0, "prev": 70.0},
         {"name": "CloverPit", "kind": "hit", "band": [66.1, 80.1], "score": 41.1, "prev": 51.1},
         {"name": "Tray", "kind": "weak", "band": [5.1, 19.1], "verdicts": {"WISHLIST": 1, "SALDI": 4, "IGNORO": 21, "REFUND": 1}}]
c = fw.calibration({"anchors": harsh})
assert c["drift"] and c["direction"] == "troppo severo" and c["hit_gap"] < -8
rows = {a["name"]: a for a in c["anchors"]}
assert rows["CloverPit"]["flag"] and "sotto la fascia" in rows["CloverPit"]["why"] and "spostata di -10" in rows["CloverPit"]["why"]
assert rows["Tray"]["raw"] == fw.score([{"verdict": "WISHLIST"}] + [{"verdict": "SALDI"}] * 4 + [{"verdict": "IGNORO"}] * 21 + [{"verdict": "REFUND"}])
assert c["map"](37.8) > 37.8                                          # a harsh panel's raw score is lifted
assert fw.calibration({"anchors": [{"name": "x", "band": [1, 2], "score": 1.5}]})["enough"] is False   # 1 anchor is not enough
off = fw.calibration({"anchors": [{"name": "h", "kind": "hit", "band": [70, 80], "score": 10}, {"name": "w", "kind": "weak", "band": [5, 15], "score": 40}]})
assert "spostamento medio" in off["method"]                           # out of order: offset only, never an inverted map
assert fw.calibration({}) is None
pav = fw.calibration({"anchors": [{"name": "a", "kind": "hit", "band": [80, 90], "score": 100}, {"name": "b", "kind": "hit", "band": [70, 80], "score": 99},
                                    {"name": "c", "kind": "hit", "band": [73, 83], "score": 96}, {"name": "w", "kind": "weak", "band": [5, 15], "score": -18}]})
assert "unite" in pav["method"] and pav["map"](97.5) == 76.5 and pav["map"](-18) == 10.0   # b and c out of order: pooled, never inverted
assert pav["map"](40) < pav["map"](60) < pav["map"](99.5) and pav["direction"] == "troppo generoso"

# ---- metrics: raw + normalized + DERIVA in the markdown; rubric with genre weights; harshness guard
w = wave(10, ["WISHLIST"] * 4 + ["SALDI"] * 4 + ["IGNORO"] * 2, harsh, focus={"theme": "difficoltà"})
w["testers"][0]["verdict"] = "IGNORO"; w["testers"][0]["dims"] = dict(gameplay=9, art=9, content=9, clarity=9, value=9, social=9)
m = fw.metrics(w)
assert m["normalized"]["score"] is not None and m["calibration"]["drift"] and "map" not in m["calibration"]
md = fw.md_metrics(m)
assert "DERIVA DELLE ANCORE" in md and "ricalibrare PRIMA di pubblicare" in md and "normalizzato sulle ancore" in md
assert "Rubrica pesata per genere" in md and "gameplay e feel" in md and "Ondata con tema: difficoltà" in md
assert m["rubric"]["harsh"] == ["A-01"] and "Guardia contro la severità" in md
assert fw.rubric_of({"dims": D}, W) == round(10 * sum(W[k] * D[k] for k in W), 1)
assert fw.rubric_of({"dims": {"gameplay": 7}}, W) is None and fw.expected_verdict(72) == "WISHLIST" and fw.expected_verdict(55) == "SALDI"
json.dumps({k: v for k, v in m.items()})                              # serializable (no lambdas leak out)
w["calibration_rejudged"] = True
assert "ricalibrata una volta" in fw.md_metrics(fw.metrics(w))

# ---- genre weights: prior only, then blended with real review themes; always sum to 1
g = fw.genre_weights("physics_comedy_roguelite")
assert g["weights"] == {k: round(v, 2) for k, v in g["prior"].items()} and abs(sum(g["weights"].values()) - 1) < 1e-9 and g["reviews"] is None
corpus = {"groups": {"all": {"games": 3, "reviews_negative": 10, "reviews_positive": 10,
                             "rewarded": [{"theme": "fun_addictive", "macro_pct": 50}, {"theme": "art_style", "macro_pct": 30}],
                             "punished": [{"theme": "repetitive_shallow", "macro_pct": 20}, {"theme": "unknown_theme", "macro_pct": 99}]}}}
g2 = fw.genre_weights("physics_comedy_roguelite", corpus)
assert abs(sum(g2["weights"].values()) - 1) < 1e-9 and g2["weights"]["art"] > g["weights"]["art"] and "recensioni vere" in g2["source"]
assert min(g2["weights"].values()) >= 0.05 and fw.genre_weights("does-not-exist")["label"] == "generico"

# ---- delta: normalized line, drift warning, focus caveat (themed vs general wave)
w9 = wave(9, ["WISHLIST"] * 6 + ["SALDI"] * 4, anchors)
m9 = fw.metrics(w9)
dl = fw.md_delta(w9, w, m9, m, 10.0)
assert "Normalizzato sulle ancore" in dl and "DERIVA DELLE ANCORE nell'ondata dopo" in dl and "ha il tema «difficoltà»" in dl and "è generale" in dl
w9b = dict(w9); w9b.pop("anchors")
assert "confronto resta solo sul punteggio grezzo" in fw.md_delta(w9b, w, fw.metrics(w9b), m, 10.0)

# ---- files: timeline columns, CLI --strict exit 3, weights and anchor-band commands
d = tempfile.mkdtemp()
for ww, name in ((w9, "w09-2026-10-18-beta.json"), (w, "w10-2026-10-19-beta.json")):
    json.dump({k: v for k, v in ww.items() if k != "_defined"}, open(os.path.join(d, name), "w", encoding="utf-8"))
def cli(*a):
    return subprocess.run([sys.executable, os.path.join(R, "fg_waves.py"), *a], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
r = cli("timeline", d, "-o", os.path.join(d, "tl.md"), "--csv", os.path.join(d, "tl.csv"))
assert r.returncode == 0, r.stderr
tl = open(os.path.join(d, "tl.md"), encoding="utf-8").read()
assert "Normalizzato sulle ancore" in tl and "difficoltà" in tl and "generale" in tl and "⚠️" in tl
assert "normalized" in open(os.path.join(d, "tl.csv"), encoding="utf-8").readline()
wj = os.path.join(d, "w10-2026-10-19-beta.json")
j = json.load(open(wj, encoding="utf-8")); j.pop("calibration_rejudged", None); json.dump(j, open(wj, "w", encoding="utf-8"))
assert cli("metrics", wj, "--strict").returncode == 3                 # drift, not re-judged: blocked
assert cli("metrics", os.path.join(d, "w09-2026-10-18-beta.json"), "--strict").returncode == 0
r = cli("anchor-band", "--positive", "97.8", "--reviews", "200163"); assert b"80.7" in r.stdout
r = cli("weights", "--genre", "physics_comedy_roguelite"); assert r.returncode == 0 and "Pesi della rubrica" in r.stdout.decode("utf-8")

# ---- wave_kit: the full evaluation and the anchors are REQUIRED; theme-only waves fail
L = os.path.join(d, "launch"); WD = os.path.join(L, "fg", "waves")
wk.init(L, 10, "2026-10-19")
def st(res, file, label):
    h = [i["status"] for i in res["items"] if i["file"] == file and i["label"].startswith(label)]
    return h[0] if h else None
res = wk.check(L, 10)
assert st(res, "w10-brief.md", "valutazione completa del gioco") == "ok"            # the template carries the section
assert st(res, "w10-brief.md", "pesi della rubrica") == "fail" and st(res, "w10-brief.md", "ancore di calibrazione") == "fail"
b = open(os.path.join(WD, "w10-brief.md"), encoding="utf-8").read()
themed = b.split("## Valutazione completa")[0] + "## Tema dell'ondata\nSolo difficoltà.\n"   # theme only: full evaluation removed
open(os.path.join(WD, "w10-brief.md"), "w", encoding="utf-8").write(themed)
res = wk.check(L, 10)
assert st(res, "w10-brief.md", "valutazione completa del gioco") == "fail" and not res["ok"]
b = b.replace("- Pesi della rubrica (genere, pesi, fonte): (da compilare)", "- Pesi della rubrica: physics comedy roguelite, gameplay 0,38 · art 0,13 (fg_waves.py weights)", 1)
b = b.replace("(da compilare)\n\n## Tema", "- Balatro (successo) 80,7-94,7\n- CloverPit (successo) 66,1-80,1\n- The Way of the Tray (debole) 5,1-19,1\n\n## Tema", 1)
open(os.path.join(WD, "w10-brief.md"), "w", encoding="utf-8").write(b)
res = wk.check(L, 10)
assert st(res, "w10-brief.md", "pesi della rubrica") == "ok" and st(res, "w10-brief.md", "ancore di calibrazione") == "ok"
mp = open(os.path.join(WD, "w10-mappa-gioco.md"), encoding="utf-8").read().replace("Ondata 10", "Ondata 9")
open(os.path.join(WD, "w10-mappa-gioco.md"), "w", encoding="utf-8").write(mp)
assert st(wk.check(L, 10), "w10-mappa-gioco.md", "mappa rifatta per questa ondata") == "fail"   # an old map copied as it is
# wave JSON: drift fails, re-judged drift warns, missing dims fail, good JSON passes
jw = {k: v for k, v in w.items() if k != "_defined"}; jw.pop("calibration_rejudged", None)
JP = os.path.join(WD, "w10-2026-10-19-beta.json")
json.dump(jw, open(JP, "w", encoding="utf-8"))
res = wk.check(L, 10)
assert st(res, os.path.basename(JP), "ancore dentro la tolleranza") == "fail" and st(res, os.path.basename(JP), "rubrica del genere") == "ok"
jw["calibration_rejudged"] = True; json.dump(jw, open(JP, "w", encoding="utf-8"))
assert st(wk.check(L, 10), os.path.basename(JP), "ancore dentro la tolleranza") == "warn"
jw["anchors"] = anchors; jw["testers"][1].pop("dims"); json.dump(jw, open(JP, "w", encoding="utf-8"))
res = wk.check(L, 10)
assert st(res, os.path.basename(JP), "ancore dentro la tolleranza") == "ok" and st(res, os.path.basename(JP), "valutazione completa: ogni tester") == "fail"
jw["testers"][1]["dims"] = dict(D); jw["rubric"]["weights"] = {"gameplay": 1.0}; json.dump(jw, open(JP, "w", encoding="utf-8"))
assert st(wk.check(L, 10), os.path.basename(JP), "rubrica del genere") == "fail"
jw["rubric"]["weights"] = W; jw["anchors"] = anchors[:2]; json.dump(jw, open(JP, "w", encoding="utf-8"))
assert st(wk.check(L, 10), os.path.basename(JP), "ancore di calibrazione giudicate") == "fail"     # no weak anchor, only 2

shutil.rmtree(d, ignore_errors=True)
print("ALL CALIBRATION TESTS PASSED")
