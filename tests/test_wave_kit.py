"""wave_kit.py: init writes the seven templates and never overwrites, templates alone fail the check (template-only
sections are empty), a filled wave passes, each required item fails on its own (runs without timestamps, screens without
grades, no "Riapre la decisione", map without file references, missing extra questions), extra questions found in the
wave JSON keys too, limite-beta only warns, --json output, exit codes, cp1252 console. Offline, temp dirs only."""
import os, sys, json, shutil, tempfile, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import wave_kit as wk

d = tempfile.mkdtemp()
L = os.path.join(d, "launch")
W = os.path.join(L, "fg", "waves")

def run(*args, enc="cp1252"):
    r = subprocess.run([sys.executable, os.path.join(R, "wave_kit.py"), *args], capture_output=True, env=dict(os.environ, PYTHONIOENCODING=enc))
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

def write(name, text):
    with open(os.path.join(W, name), "w", encoding="utf-8") as f:
        f.write(text)

def status(res, file, label_start):
    hits = [i["status"] for i in res["items"] if i["file"] == file and i["label"].startswith(label_start)]
    assert hits, (file, label_start, [i["label"] for i in res["items"] if i["file"] == file])
    return hits[0]

# ---- init: seven files, Italian headings, never overwrite
code, out, err = run("init", "--launch-dir", L, "--wave", "3", "--date", "2026-11-02", "--game", "Gioco Prova")
assert code == 0, err
names = sorted(os.listdir(W))
assert names == sorted(f"w03-{k}.md" for k, _ in wk.TEMPLATES + wk.OUTPUTS), names
brief = open(os.path.join(W, "w03-brief.md"), encoding="utf-8").read()
assert "# Ondata 3 — Brief (2026-11-02)" in brief and "Gioco Prova" in brief and "## Domande ai tester" in brief
assert "## Riapre la decisione" in open(os.path.join(W, "w03-proposte-gameplay.md"), encoding="utf-8").read().replace("## 3. Riapre", "## Riapre")
assert "## RUN 3" in open(os.path.join(W, "w03-runs.md"), encoding="utf-8").read()
write("w03-runs.md", "# mio testo\n")                       # an edited file is never overwritten
code, out, _ = run("init", "--launch-dir", L, "--wave", "3")
assert code == 0 and out.count("saltato") == 8 and open(os.path.join(W, "w03-runs.md"), encoding="utf-8").read() == "# mio testo\n", out
code, _, _ = run("init", "--launch-dir", L, "--wave", "3", "--date", "02/11/2026")
assert code == 2                                             # bad date refused by argparse
shutil.rmtree(W)

# ---- templates alone: the brief already holds the 9 extra questions, everything else is template-only -> fail
wk.init(L, 3, "2026-11-02")
res = wk.check(L, 3)
assert not res["ok"]
assert status(res, "w03-brief.md", "domande extra") == "ok"   # the default question set is in the template
for f, lab in [("w03-mappa-gioco.md", "riferimenti ai file"), ("w03-mappa-gioco.md", "sezione: audio"), ("w03-schermate.md", "schermate con voto"),
               ("w03-runs.md", "almeno 3 run"), ("w03-mercato.md", "recensioni vere"), ("w03-mercato.md", "dati sulla durata"),
               ("w03-proposte-gameplay.md", "sezione \"Riapre"), ("w03-proposte-gameplay.md", "proposte con ore"), ("w03-brief.md", "cosa si valuta")]:
    assert status(res, f, lab) == "fail", (f, lab)
assert status(res, "w03-limite-beta.md", "proposta del limite") == "warn"     # optional: warns, never fails
assert all(i["status"] != "fail" for i in res["items"] if i["file"] == "w03-limite-beta.md")

# ---- a filled wave (generic, Godot-like paths) passes
MAP = "# Mappa\n\n" + "\n\n".join(f"## {i}. {h}\n- voce reale `{p}` [FATTO]\n- altra voce `src/game/{i}.gd:12`" for i, (h, p) in enumerate([
    ("Il giro del gioco", "scenes/main.tscn"), ("Economia", "data/economy.json"), ("Progressione e sblocchi", "src/meta.gd"),
    ("Oggetti e potenziamenti", "data/items.tres"), ("Ostacoli e nemici", "src/enemies/"), ("Eventi", "src/events.gd"),
    ("HUD e testi a schermo", "ui/hud.tscn"), ("Comandi", "project.godot"), ("Accessibilità", "src/options.gd"), ("Audio", "audio/bus_layout.tres"),
    ("Cosa NON c'è", "docs/roadmap.md")], 1))
SCREENS = """# Schermate
> Voto: **evidente** · **trovabile** · **nascosta**.
## 1. Tabella completa
| # | Schermata | Come ci arrivi | Quando | Il gioco te lo dice? | Voto |
|---|---|---|---|---|---|
| 1 | Menu (`ui/menu.tscn`) | avvio | sempre | — | evidente |
| 2 | Negozio (`ui/shop.tscn`) | menu ▸ Shop | dopo la 1ª partita | no | trovabile |
| 3 | Statistiche | tasto F9 | sempre | no | nascosta |
## 2. Cosa resta nascosto o poco chiaro
- Le statistiche non hanno un pulsante.
"""
def run_block(k):
    rows = "\n".join(f"| {m}:{s:02d} | sala | azione {m}{s} | 10 | HUD |" for m, s in [(0, 5), (0, 18), (0, 31), (0, 40), (1, 2), (1, 30)])
    return f"## RUN {k} — tipo {k}\n| Tempo | Dove | Azione | Numeri | Schermo |\n|---|---|---|---|---|\n{rows}\n\n### Run {k} — punti segnati\n| Tipo | Quando | Cosa | Peso |\n|---|---|---|---|\n| Punto morto | 0:40 | corridoio | medio |\n| Punto divertente | 1:02 | crollo | alto |\n| Frustrazione | 1:30 | spirale | alto |\n| Abbandono probabile | 1:30 | chiude | medio |\n| Troppe UI insieme | 0:05 | 6 avvisi | alto |\n| Non si capisce cosa fare | 0:31 | quale porta? | medio |\n"
RUNS = "# Run\n## 0. I numeri veri\n- durata 150 s da `data/levels.json` e telemetria\n\n" + "\n".join(run_block(k) for k in (1, 2, 3))
MARKET = """# Mercato
## 1. Le fonti usate
- `review_corpus.py` su 8 comparabili, file `launch/_raw/corpus-w03.md`
## 2. Cosa premiano e cosa puniscono le recensioni vere
- ripetitivo 17 % delle negative [FATTO]
## 4. Durata delle demo
- mediana demo di successo 38-65 min — https://howtomarketagame.com/2022/10/26/x/
"""
PROPOSALS = """# Proposte
## 1. Proposte
### Un solo negozio
- Cosa cambia: unisce due schermate. Prova di mercato: Brotato (fonte). Ore [STIMA]: 10-14. Rischio: medio.
## 3. Riapre la decisione
### Riapre la decisione: "niente co-op"
- Prove: 19 % delle positive citano gli amici. Consiglio: non riaprire.
"""
BRIEF = brief.replace("(da compilare)", "Demo gratuita, build 0.4, pagina store e trailer.", 1)
for n, t in [("w03-brief.md", BRIEF), ("w03-mappa-gioco.md", MAP), ("w03-schermate.md", SCREENS), ("w03-runs.md", RUNS),
             ("w03-mercato.md", MARKET), ("w03-proposte-gameplay.md", PROPOSALS)]:
    write(n, t)
os.remove(os.path.join(W, "w03-limite-beta.md"))
res = wk.check(L, 3)
assert res["ok"], [i for i in res["items"] if i["status"] == "fail"]
assert status(res, "w03-limite-beta.md", "file presente") == "warn" and res["warns"] >= 1
code, out, _ = run("check", "--launch-dir", L, "--wave", "3")
assert code == 0 and "✅" in out and "preparazione completa" in out, out          # cp1252 console survives the emoji
code, out, _ = run("check", "--launch-dir", L, "--wave", "3", "--json")
j = json.loads(out); assert j["ok"] and j["wave"] == 3 and j["fails"] == 0 and isinstance(j["items"], list)

# ---- each required item fails on its own
def broken(name, text, file, label):
    old = open(os.path.join(W, name), encoding="utf-8").read()
    write(name, text)
    r = wk.check(L, 3)
    write(name, old)
    assert not r["ok"] and status(r, file, label) == "fail", (name, label, [i for i in r["items"] if i["status"] == "fail"])
broken("w03-runs.md", RUNS.split("## RUN 3")[0], "w03-runs.md", "almeno 3 run")                        # only 2 runs
broken("w03-runs.md", __import__("re").sub(r"\d:\d\d", "x", RUNS), "w03-runs.md", "almeno 3 run")       # no timestamps
broken("w03-runs.md", RUNS.replace("Frustrazione", "Fastidio"), "w03-runs.md", "segnati punti morti")
broken("w03-schermate.md", SCREENS.replace("evidente", "ok").replace("trovabile", "ok").replace("nascosta", "ok"), "w03-schermate.md", "schermate con voto")
broken("w03-proposte-gameplay.md", PROPOSALS.split("## 3. Riapre")[0], "w03-proposte-gameplay.md", "sezione \"Riapre")
broken("w03-proposte-gameplay.md", PROPOSALS.replace("- Prove: 19 % delle positive citano gli amici. Consiglio: non riaprire.", "> (da compilare)"), "w03-proposte-gameplay.md", "sezione \"Riapre")
broken("w03-mappa-gioco.md", __import__("re").sub(r"`[^`]*`", "x", MAP), "w03-mappa-gioco.md", "riferimenti ai file")
broken("w03-mappa-gioco.md", MAP.replace("Audio", "Suono finto").replace("## 10. Suono finto", "## 10. Varie"), "w03-mappa-gioco.md", "sezione: audio")
broken("w03-mercato.md", MARKET.replace("review_corpus.py", "lettura").replace("recensioni vere", "opinioni"), "w03-mercato.md", "recensioni vere")
no_q = "\n".join(l for l in BRIEF.splitlines() if not l[:2] in ("4.", "9."))
broken("w03-brief.md", no_q, "w03-brief.md", "domande extra")
code, out, _ = run("check", "--launch-dir", L, "--wave", "4")
assert code == 1 and "❌" in out and "mancano" in out                                       # nothing there: non-zero exit

# ---- extra questions also found in the wave JSON tester keys (the brief alone can miss some)
write("w03-brief.md", no_q)
json.dump({"wave": 3, "date": "2026-11-02", "testers": [{"id": "A-01", "verdict": "WISHLIST", "q_memorable": "crollo", "q_lost_moment": "0:05"}]},
          open(os.path.join(W, "w03-2026-11-02-beta.json"), "w", encoding="utf-8"))
assert status(wk.check(L, 3), "w03-brief.md", "domande extra") == "ok"

# ---- the real wave-9 formats (headings "## RUN 1 — …", "evidente/trovabile/nascosta", "## 5. Riapre la decisione …") are read
assert wk.TIMESTAMP.findall("| 2:26 = 0:00 | 1:33-1:52 | 0,5 s | 10:30 |") == ["2:26", "0:00", "1:33", "1:52", "10:30"]
assert [h for h, _ in wk.sections("## RUN 1 — x\n### Run 1 — tabella\n## RUN 2\n", 2)] == ["RUN 1 — x", "RUN 2"]

shutil.rmtree(d, ignore_errors=True)
print("ALL WAVE_KIT TESTS PASSED")
