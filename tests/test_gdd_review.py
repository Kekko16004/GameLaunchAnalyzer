"""gdd_review.py (mode Revisione GDD): self-test, init never overwrites and reads the GDD sections, an empty skeleton fails
the check, a filled review passes, the owner's dial and untouchables are enforced, decide records dates and refuses a proposal
above the dial, pending reads DECISIONI.md, render is plain Markdown, cp1252 console; the heart and keeps_heart, mid-development
basis and kind, score_delta and the STATUS chart, flop look-alikes, panel with real anchors, predictions, compare after the slice.
Offline, temp dirs only."""
import os, sys, json, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import gdd_review as gr

def run(*args, enc="cp1252"):
    r = subprocess.run([sys.executable, os.path.join(R, "gdd_review.py"), *args], capture_output=True, env=dict(os.environ, PYTHONIOENCODING=enc))
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

code, out, err = run("self-test")
assert code == 0 and "self-test OK" in out, out + err

d = tempfile.mkdtemp()
L = os.path.join(d, "launch")
with open(os.path.join(d, "GDD.md"), "w", encoding="utf-8") as f:
    f.write("---\nstatus: locked\nengine: unity\ngenre: roguelite\n---\n# GDD\n## Pitch\nUn cuoco in un dungeon.\n## Core loop\nCucina, combatti.\n## Progressione\nRicette.\n")
code, out, _ = run("init", "--launch-dir", L, "--gdd", os.path.join(d, "GDD.md"), "--date", "2026-11-07")
assert code == 0
raw = os.path.join(L, "_raw", "gdd_review.json")
data = json.load(open(raw, encoding="utf-8"))
assert data["gdd_status"] == "locked" and data["gdd_sections"] == ["Pitch", "Core loop", "Progressione"] and data["dial"]["untouchable"] == ["engine"]
assert len(data["scorecard"]) == 10
data["sources"] = ["mia nota"]
json.dump(data, open(raw, "w", encoding="utf-8"))
code, out, _ = run("init", "--launch-dir", L, "--gdd", "GDD.md")
assert code == 0 and "non lo tocco" in out and json.load(open(raw, encoding="utf-8"))["sources"] == ["mia nota"]   # never overwrites

code, out, _ = run("check", "--launch-dir", L)
assert code == 1 and "dial.level mancante" in out                                  # an empty skeleton is not a review
code, out, _ = run("check", "--launch-dir", L, "--json")
res = json.loads(out)
assert res["ok"] is False and any("pagella" in e for e in res["errors"])

# a filled review at level 2 with "stile" untouchable passes
full = gr._sample(2)
full["gdd_sections"] = data["gdd_sections"]
json.dump(full, open(raw, "w", encoding="utf-8"))
code, out, _ = run("check", "--launch-dir", L)
assert code == 0 and "revisione completa" in out, out

# the dial and the untouchables are the owner's: above the level or on an untouchable = error
over = json.loads(json.dumps(full)); over["proposals"][0]["level"] = 3
assert any("sopra quello scelto" in e for e in gr.check(over)[0])
touch = json.loads(json.dumps(full)); touch["proposals"][0]["touches"] = ["pitch", "stile"]
assert any("intoccabile" in e and "stile grafico" in e for e in gr.check(touch)[0])
low = json.loads(json.dumps(full)); low["dial"]["level"] = 1
assert sum("sopra quello scelto" in e for e in gr.check(low)[0]) == 2               # both structural ones
lazy = json.loads(json.dumps(full)); lazy["proposals"][0]["proposed"] = ""
assert any("`proposed` vuoto" in e for e in gr.check(lazy)[0])                      # no proposal without text ready to paste
op = json.loads(json.dumps(full)); op["proposals"][1]["evidence"] = [{"label": "[OPINIONE]", "text": "secondo me"}]
assert any("solo da opinioni" in w for w in gr.check(op)[1])

# decide: dates, unknown ids, nothing above the dial
code, out, _ = run("decide", "--launch-dir", L, "P-GDD-1", "P-GDD-3", "accettata", "--date", "2026-11-08")
assert code == 0 and "accettata" in out
code, out, _ = run("decide", "--launch-dir", L, "P-GDD-2", "rifiutata", "--date", "2026-11-08", "--note", "resta così")
cur = json.load(open(raw, encoding="utf-8"))
assert [(p["id"], p["status"], p["decided"]) for p in cur["proposals"]] == [("P-GDD-1", "accettata", "2026-11-08"), ("P-GDD-2", "rifiutata", "2026-11-08"), ("P-GDD-3", "accettata", "2026-11-08")]
assert cur["proposals"][1]["note"] == "resta così"
code, _, err = run("decide", "--launch-dir", L, "P-GDD-99", "accettata")
assert code != 0
cur["dial"]["level"] = 1
json.dump(cur, open(raw, "w", encoding="utf-8"))
code, _, err = run("decide", "--launch-dir", L, "P-GDD-2", "accettata")
assert code != 0 and "sopra il livello scelto" in err
cur["dial"]["level"] = 2
json.dump(cur, open(raw, "w", encoding="utf-8"))

# pending: accepted and not yet cited in DECISIONI.md (what the developer still has to apply)
dec = os.path.join(d, "DECISIONI.md")
open(dec, "w", encoding="utf-8").write("# Decisioni\n- D-004 · 2026-11-08 · GDD · gancio · fonte: launch/gdd-review.md P-GDD-1\n")
code, out, _ = run("pending", "--launch-dir", L, "--decisions", dec, "--json")
assert code == 0 and [p["id"] for p in json.loads(out)] == ["P-GDD-3"]
assert json.loads(out)[0]["proposed"] == "testo"
code, out, _ = run("pending", "--launch-dir", L, "--decisions", os.path.join(d, "manca.md"))
assert code == 0 and "2 accettate" in out

# render
code, out, _ = run("render", "--launch-dir", L)
md = open(os.path.join(L, "gdd-review.md"), encoding="utf-8").read()
for needle in ("# Revisione dell'idea e del GDD", "## Quanto si può cambiare", "Livello 2: Struttura", "stile grafico", "## Pagella dell'idea",
               "### Ritocchi", "### Cambi di struttura", "✓ accettata il 2026-11-08", "✗ rifiutata", "Proposto (da incollare):", "## Per lo sviluppo",
               "fonte: launch/gdd-review.md P-GDD-n"):
    assert needle in md, needle
assert "<script" not in md

# the heart of the game: required, and every concept change keeps it
noh = json.loads(json.dumps(full)); noh["dial"]["heart"] = " "
assert any("dial.heart" in e for e in gr.check(noh)[0])
c3 = json.loads(json.dumps(full)); c3["dial"]["level"] = 3
c3["proposals"] += [dict(c3["proposals"][1], id="P-GDD-4", level=3), dict(c3["proposals"][1], id="P-GDD-5", level=3, keeps_heart="resta la cucina in co-op")]
assert sum("keeps_heart" in e for e in gr.check(c3)[0]) == 1                        # only the one without it
assert "Il cuore del gioco, con le sue parole:** cucinare sotto pressione" in gr.render(full)

# mid-development: basis and kind required, basis files checked against the project
mid = json.loads(json.dumps(full)); mid["stage"] = "sviluppo"
assert any("`basis` vuoto" in e for e in gr.check(mid)[0])
os.makedirs(os.path.join(d, "docs", "design-review"), exist_ok=True)
open(os.path.join(d, "docs", "design-review", "game-map.md"), "w", encoding="utf-8").write("# mappa\n")
assert gr.detect_basis(d) == ["docs/design-review/game-map.md"]
mid["basis"] = ["docs/design-review/game-map.md", "GAME_TASKS.md"]
for p in mid["proposals"]:
    p["kind"] = "taglio"
e_, w_ = gr.check(mid, root=d)
assert not e_ and any("GAME_TASKS.md" in w for w in w_), (e_, w_)
assert "Taglio · " in gr.render(mid) and "a metà sviluppo" in gr.render(mid)

# score_delta: validated, "after" capped to 5 and only for accepted proposals
sd = json.loads(json.dumps(full)); sd["proposals"][1]["score_delta"] = {"volo": 1}
assert any("score_delta" in e for e in gr.check(sd)[0])
sd["proposals"][1]["score_delta"] = {"loop": 3, "gancio": 1}
for p in sd["proposals"]:
    p["status"], p["decided"] = "accettata", "2026-11-08"
aft = gr.after_scores(sd)
assert aft["gancio"] == 5 and aft["loop"] == 5 and aft["scope"] == 3, aft            # 2 + 2 + 1 = 5; 3 + 3 = 6 -> 5
assert "Dopo le accettate [STIMA]" in gr.render(sd)

# flop look-alikes on the real case studies
fl = json.loads(json.dumps(full)); fl["risk_factors"] = ["hook_clarity", "capsule", "trailer", "store_page", "genre_market"]
res = gr.flop_risk(fl)
assert res["flops_checked"] >= 50 and res["cases"] and all(0 < c["similarity"] <= 1 for c in res["cases"])
assert res["cases"] == sorted(res["cases"], key=lambda c: (-c["similarity"], -len(c["shared"]), c["game"] or ""))
fl["flop_risk"] = dict(res, cases=[dict(res["cases"][0], similarity=0.8, shared=["hook_clarity", "capsule"])])
fl["scorecard"][-1]["score"] = 4
assert any("somiglia al flop" in w for w in gr.check(fl)[1])
fl["scorecard"][-1]["score"] = 2
assert not any("somiglia al flop" in w for w in gr.check(fl)[1])
assert "## Somiglianza con flop reali" in gr.render(fl)
fl["risk_factors"] = ["inventato"]
assert any("fuori vocabolario" in w for w in gr.check(fl)[1])
json.dump(dict(full, risk_factors=["hook_clarity", "trailer"]), open(raw, "w", encoding="utf-8"))
code, out, _ = run("flop-risk", "--launch-dir", L, "--write")
assert code == 0 and "flop reali confrontati" in out and json.load(open(raw, encoding="utf-8"))["flop_risk"]["cases"]

# panel with real anchors: drift and anchor-normalized score (fg_waves arithmetic)
pn = json.load(open(raw, encoding="utf-8"))
pn["panel"] = {"size": 12, "method": "solo pitch e loop", "results": [{"version": "originale", "verdicts": {"WISHLIST": 4, "SALDI": 4, "IGNORO": 4}}]}
assert any("senza ancore vere" in w for w in gr.check(pn)[1])
pn["panel"]["anchors"] = [
    {"name": "Hit A", "appid": 1, "kind": "hit", "reviews": 30000, "positive_pct": 95, "verdicts": {"WISHLIST": 9, "SALDI": 3}},
    {"name": "Hit B", "appid": 2, "kind": "hit", "reviews": 6000, "positive_pct": 90, "verdicts": {"WISHLIST": 8, "SALDI": 3, "IGNORO": 1}},
    {"name": "Debole", "appid": 3, "kind": "weak", "reviews": 150, "positive_pct": 70, "verdicts": {"SALDI": 3, "IGNORO": 7, "REFUND": 2}}]
json.dump(pn, open(raw, "w", encoding="utf-8"))
code, out, err = run("panel-score", "--launch-dir", L)
assert code in (0, 3) and "originale: grezzo" in out and "ancora Hit A" in out, out + err
pn = json.load(open(raw, encoding="utf-8"))
r0 = pn["panel"]["results"][0]
assert r0["raw_score"] is not None and r0["norm_score"] is not None and "map" not in pn["panel"]["calibration"]
assert pn["panel"]["anchors"][0]["band"] and "Ancora vera" in gr.render(pn)
drift = json.loads(json.dumps(pn)); drift["panel"]["anchors"][0]["verdicts"] = {"REFUND": 12}
assert gr.panel_score(drift)["calibration"]["drift"] is True

# predictions: one per scored area, idempotent ids
code, out, _ = run("predictions", "--launch-dir", L)
assert code == 0 and "10 previsioni nuove" in out, out
code, out, _ = run("predictions", "--launch-dir", L)
assert "0 previsioni nuove" in out
preds = json.load(open(os.path.join(L, "predictions.json"), encoding="utf-8"))["items"]
g = [p for p in preds if p["id"] == "gdd-2026-11-07-gancio"][0]
assert (g["value"], g["low"], g["high"], g["label"], g["actual_metric"]) == (2, 1, 3, "STIMA", "idea_gancio_real")

# second review after the slice: promises against reality
before = json.load(open(raw, encoding="utf-8"))
for p in before["proposals"][:2]:
    p["status"], p["decided"] = "accettata", "2026-11-08"
after = json.loads(json.dumps(before)); after.update(stage="slice", basis=["docs/design-review/game-map.md"], date="2026-12-20")
for p in after["proposals"]:
    p["kind"] = "rinforzo"
after["promises"] = [{"promise": "co-op caotica", "from": "co-op caotica", "reality": "si vede", "evidence": "run 3"},
                     {"promise": "gancio nei 10 s", "from": "P-GDD-1", "reality": "non si vede", "evidence": "foto 12"}]
after["scorecard"][0]["score"] = 3
assert not gr.check(after)[0]
after["promises"][1]["reality"] = "forse"
assert any("reality deve essere" in e for e in gr.check(after)[0])
after["promises"][1]["reality"] = "non si vede"
bp, ap_ = os.path.join(d, "before.json"), os.path.join(d, "after.json")
json.dump(before, open(bp, "w", encoding="utf-8")); json.dump(after, open(ap_, "w", encoding="utf-8"))
code, out, _ = run("compare", "--before", bp, "--after", ap_, "--md", os.path.join(d, "cmp.md"))
cmp_md = open(os.path.join(d, "cmp.md"), encoding="utf-8").read()
assert code == 0 and "**1 su 3**" in cmp_md and "| Gancio | 2 | 3 | +1 |" in cmp_md and "✗ non si vede" in cmp_md, cmp_md

# the scorecard chart in STATUS.html (report_charts group "idea", Gioco tab)
import report_charts as rc, status_page as sp
grp = [x for x in rc.groups(L) if x["key"] == "idea"]
assert grp and "Pagella dell&#x27;idea" in grp[0]["charts"][0] and "Idea originale" in grp[0]["charts"][0]
assert sp.GROUP_TAB["idea"] == "gioco"

# the contract names the script and its read-only use by the developer
link = open(os.path.join(HERE, "..", "references", "dev-link.md"), encoding="utf-8").read()
assert "gdd_review.py pending" in link and "## 10. Revisione dell'idea e del GDD" in link
print("gdd_review OK")
