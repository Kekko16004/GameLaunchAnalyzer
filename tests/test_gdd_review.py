"""gdd_review.py (mode Revisione GDD): self-test, init never overwrites and reads the GDD sections, an empty skeleton fails
the check, a filled review passes, the owner's dial and untouchables are enforced, decide records dates and refuses a proposal
above the dial, pending reads DECISIONI.md, render is plain Markdown, cp1252 console. Offline, temp dirs only."""
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

# the contract names the script and its read-only use by the developer
link = open(os.path.join(HERE, "..", "references", "dev-link.md"), encoding="utf-8").read()
assert "gdd_review.py pending" in link and "## 10. Revisione dell'idea e del GDD" in link
print("gdd_review OK")
