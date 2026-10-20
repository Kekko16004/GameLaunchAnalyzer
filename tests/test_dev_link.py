"""Strategist side of the game-developer contract (references/dev-link.md, gdl-v2): wave_kit init from docs/design-review
(brief "Da ricontrollare" from changes-since, map / screens / runs copied, shared ```screens block, shared run tags), the
changes-since parser and `fixes` (as-is, never removing a fix), the contract warnings of `check` (not cited, fixes missing,
orphans, run tags, P-wNN-n IDs and keys, reopenings in the §4.3 format, "nato col gate" / "ricomparso dopo il gate"),
fg_waves from_gate_dev / gate_dev, STATUS.html "nato col gate NN", todo_track approve and sync-decisions, project_scan dev_link.
If game-developer's gate_link.py is installed, its real `since` output is parsed too (skipped otherwise). Offline, temp dirs."""
import os, sys, json, shutil, tempfile, subprocess, hashlib, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("no network in tests")
common.http_get = no_net
import wave_kit as wk, fg_waves, todo_track as tt, project_scan as ps

d = tempfile.mkdtemp()
L = os.path.join(d, "launch"); W = os.path.join(L, "fg", "waves"); DR = os.path.join(d, "docs", "design-review")
def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
def read(path):
    return open(path, encoding="utf-8").read()
def status(res, file, label_start):
    hits = [i for i in res["items"] if i["file"] == file and i["label"].startswith(label_start)]
    return hits[0]["status"] if hits else None
def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(R, script), *args], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

# ---- a project with wave 9 done and game-developer's files after gate 57 (exact gate_link.py since format)
write(os.path.join(W, "w09-sintesi.md"), "# Ondata 9 — Sintesi (2026-10-18)\nDopo il gate 56.\n")
write(os.path.join(W, "w09-2026-10-18-beta.json"), json.dumps({"wave": 9, "date": "2026-10-18", "testers": [{"id": "A-01", "verdict": "WISHLIST", "issues": ["ui-chaos"]}],
                                                                "issues": [{"key": "ui-chaos", "label": "Troppe schede", "severity": "alta"}]}))
CS = """# Cambiato dal gioco dopo l'ondata 9 (generato 2026-10-19 da gate_link.py since)

> Regola: after wave w09 (2026-10-18); same-day gates only if the wave does not cite them. Questo è lo **stato attuale** che la prossima ondata legge (launch-link.md §6.2). Le voci `da_verificare` restano aperte finché non le confermano persone vere.

- **Gate 57** (2026-10-19, PASS): Scheda Stasera — `docs/gates/57-stasera.md`

## Criticità toccate
| Chiave | Esito | Gate | Cosa |
|---|---|---|---|
| `ui-chaos` | risolto | 57 | gate 57: Scheda Stasera |
| `rules-hidden` | da_verificare | 57 | gate 57 (da verificare con persone vere): Scheda Stasera |

## Rischi introdotti da ricontrollare nell'ondata (loop di regressione)
- gate 57: la scheda copre il timer a 150 %

## Scelte di design cambiate dall'implementazione
- gate 57: avviso al 40 % | perché: tardi | decided_by: implementer

## Da provare (proprietario)
- gate 57: inizia il piano 1

## `fixes` per il JSON dell'ondata
```json
[
 {
  "issue": "ui-chaos",
  "what": "gate 57: Scheda Stasera"
 },
 {
  "issue": "rules-hidden",
  "what": "gate 57 (da verificare con persone vere): Scheda Stasera"
 }
]
```
"""
write(os.path.join(DR, "changes-since-w09.md"), CS)
write(os.path.join(DR, "game-map.md"), "# Mappa del gioco\naggiornata al gate 57 (2026-10-19)\n\n## 1. Il giro del gioco\n- menu → piano `Assets/Run.cs:10` [FATTO]\n")
write(os.path.join(DR, "screen-map.md"), "# Schermate\n| # | Schermata | Come ci arrivi | Quando | Il gioco te lo dice? | Voto |\n|---|---|---|---|---|---|\n| 1 | Menu | avvio | sempre | — | evidente |\n")
write(os.path.join(DR, "runs.md"), "# Run\nSIMULATO, gate 57\n\n## Run 1 — Giocatore nuovo\n| Tempo | Dove | Azione | Numeri | A schermo |\n|---|---|---|---|---|\n| 0:00 | Menu | avvio | — | — |\n| 0:12 | Piano 1 | scheda | — | [TROPPA-UI:2] |\n")

# ---- parser: gates, touched keys, risks, changes, tries, fixes as-is + gate_dev from the same file's table
cs = wk.parse_changes_since(CS)
assert cs["gates"] == [{"gate": 57, "date": "2026-10-19", "status": "PASS", "title": "Scheda Stasera", "path": "docs/gates/57-stasera.md"}], cs["gates"]
assert [t["issue"] for t in cs["touched"]] == ["ui-chaos", "rules-hidden"] and cs["risks"] == [{"gate_dev": 57, "risk": "la scheda copre il timer a 150 %"}]
assert cs["changes"][0]["change"].startswith("avviso al 40 %") and cs["tries"][0]["try"] == "inizia il piano 1"
assert cs["fixes"] == [{"issue": "ui-chaos", "what": "gate 57: Scheda Stasera", "gate_dev": 57},
                       {"issue": "rules-hidden", "what": "gate 57 (da verificare con persone vere): Scheda Stasera", "gate_dev": 57}], cs["fixes"]
assert wk.find_changes_since(d, 10, L).endswith("changes-since-w09.md") and wk.find_changes_since(d, 9, L) is None

# ---- init w10: brief "Da ricontrollare" from changes-since; map, screens, runs start from docs/design-review
res = wk.init(L, 10, "2026-10-19", "Gioco")
assert res["changes_since"] == "docs/design-review/changes-since-w09.md" and len(res["from_dev"]) == 3, res
brief = read(os.path.join(W, "w10-brief.md"))
assert "## Da ricontrollare" in brief and "changes-since-w09.md" in brief and "- [gate 57] la scheda copre il timer a 150 %" in brief
assert "[gate 57, scelta di design cambiata] avviso al 40 %" in brief and "from_gate_dev" in brief and "P-w10-n" in brief
mappa = read(os.path.join(W, "w10-mappa-gioco.md"))
assert mappa.startswith("# Ondata 10 — Mappa totale del gioco (2026-10-19)") and "docs/design-review/game-map.md" in mappa and "aggiornata al gate 57, 2026-10-19" in mappa
assert "`Assets/Run.cs:10`" in mappa and "# Mappa del gioco" not in mappa
scr = read(os.path.join(W, "w10-schermate.md"))
assert "| 1 | Menu | avvio |" in scr and "```screens" in scr                          # the dev file had no block: the shared one is appended
assert "[TROPPA-UI:2]" in read(os.path.join(W, "w10-runs.md"))
prop = read(os.path.join(W, "w10-proposte-gameplay.md"))
assert "| ID | Chiave |" in prop and "Riapre la decisione: <D-NNN o testo> — prove:" in prop
sint = read(os.path.join(W, "w10-sintesi.md"))
assert "| # | Chiave |" in sint and "nato col gate NN" in sint and "| ID | Chiave |" in sint

# without game-developer: the plain templates, runs with the shared tags legend, screens block skeleton, placeholder recheck
d2 = tempfile.mkdtemp(); L2 = os.path.join(d2, "launch")
wk.init(L2, 1, "2026-10-19")
b2 = read(os.path.join(L2, "fg", "waves", "w01-brief.md")); r2 = read(os.path.join(L2, "fg", "waves", "w01-runs.md"))
assert "## Da ricontrollare" in b2 and "(da compilare)" in b2.split("## Da ricontrollare")[1].split("## ")[0]
assert all(f"[{t}]" in r2 for t in ("MORTO", "TOP", "FRUSTRA", "ABBANDONO", "CONFUSO", "SPIRALE")) and "[TROPPA-UI:n]" in r2 and "dall'inizio della run" in r2
assert "```screens" in read(os.path.join(L2, "fg", "waves", "w01-schermate.md"))
r_ = wk.check(L2, 1)
assert status(r_, "w01-brief.md", "\"Da ricontrollare\"") is None                 # no changes-since: nothing to cite
assert status(r_, "w01-schermate.md", "blocco ```screens") == "warn"               # template block has no root

# ---- check: cited -> ok; a brief that does not cite changes-since -> warning (never a failure)
r_ = wk.check(L, 10)
assert status(r_, "w10-brief.md", "\"Da ricontrollare\"") == "ok"
write(os.path.join(W, "w10-brief.md"), brief.split("## Da ricontrollare")[0] + "## Preparazione\n- x\n")
r_ = wk.check(L, 10)
it = [i for i in r_["items"] if i["label"].startswith("\"Da ricontrollare\"")][0]
assert it["status"] == "warn" and "changes-since-w09.md" in it["detail"], it
write(os.path.join(W, "w10-brief.md"), brief)

# ---- fixes: printed as-is, merged into the wave JSON without removing or editing, idempotent; from gate_link --json
WJ = os.path.join(W, "w10-2026-10-19-beta.json")
write(WJ, json.dumps({"wave": 10, "date": "2026-10-19", "testers": [{"id": "A-01", "verdict": "SALDI", "issues": ["timer-hidden"]}],
                      "issues": [{"key": "timer-hidden", "label": "Timer coperto", "severity": "media", "from_gate_dev": 57}],
                      "fixes": [{"issue": "old", "what": "a mano"}]}, ensure_ascii=False, indent=1))
r_ = wk.check(L, 10)
assert status(r_, "w10-2026-10-19-beta.json", "`fixes` dal file changes-since") == "warn"
code, out, err = run("wave_kit.py", "fixes", "--launch-dir", L, "--wave", "10")
assert code == 0 and json.loads(out) == cs["fixes"], (out, err)
code, out, _ = run("wave_kit.py", "fixes", "--launch-dir", L, "--wave", "10", "--write", WJ)
assert code == 0 and "2 fix aggiunti" in out, out
w = json.load(open(WJ, encoding="utf-8"))
assert w["fixes"][0] == {"issue": "old", "what": "a mano"} and w["fixes"][1:] == cs["fixes"]
code, out, _ = run("wave_kit.py", "fixes", "--launch-dir", L, "--wave", "10", "--write", WJ)
assert "0 fix aggiunti" in out and len(json.load(open(WJ, encoding="utf-8"))["fixes"]) == 3
assert status(wk.check(L, 10), "w10-2026-10-19-beta.json", "`fixes` dal file changes-since") == "ok"
GJ = os.path.join(d, "since.json")
write(GJ, json.dumps({"fixes": [{"issue": "ui-chaos", "what": "gate 57: Scheda Stasera", "gate_dev": 57, "status": "risolto"}]}))
src, fx = wk.fixes_from(d, 10, L, GJ)
assert fx == [{"issue": "ui-chaos", "what": "gate 57: Scheda Stasera", "gate_dev": 57, "status": "risolto"}]

# ---- check: screens block with an orphan, run rows with tags, proposal IDs and keys, reopenings, sintesi regression notes
write(os.path.join(W, "w10-schermate.md"), "# S\n| 1 | Menu | avvio | sempre | sì | evidente |\n```screens\nroot: Menu\nMenu -> Opzioni : clic\nscreen: Negozio | UI/Shop.uxml\nscreen: Roulette | R.uxml | hidden-ok: spenta (D-014)\n```\n")
r_ = wk.check(L, 10)
assert status(r_, "w10-schermate.md", "blocco ```screens") == "ok" and status(r_, "w10-schermate.md", "nessun orfano") == "warn"
assert "Negozio" in [i for i in r_["items"] if i["label"].startswith("nessun orfano")][0]["detail"]
assert wk.parse_screens_block("```screens\nMenu -> A\n```") == {"error": "manca la riga `root:`"}
rows = "\n".join(f"| {m}:{s:02d} | sala | azione | — | {tag} |" for m, s, tag in [(0, 0, ""), (0, 10, "[TROPPA-UI:5] [CONFUSO]"), (0, 40, "[MORTO]"), (1, 0, "[TOP]"), (2, 0, "[SPIRALE] [FRUSTRA]")])
write(os.path.join(W, "w10-runs.md"), "# R\n" + "\n".join(f"## RUN {k} — x\n| Tempo | Dove | Azione | Numeri | A schermo |\n|---|---|---|---|---|\n{rows}\n" for k in (1, 2, 3)))
r_ = wk.check(L, 10)
assert status(r_, "w10-runs.md", "righe che iniziano con il tempo") == "ok" and status(r_, "w10-runs.md", "almeno 3 run") == "ok"
write(os.path.join(W, "w10-runs.md"), read(os.path.join(W, "w10-runs.md")).replace("[MORTO]", "").replace("[TOP]", "").replace("[SPIRALE] [FRUSTRA]", "").replace("[TROPPA-UI:5] [CONFUSO]", ""))
assert status(wk.check(L, 10), "w10-runs.md", "righe che iniziano con il tempo") == "warn"
write(os.path.join(W, "w10-proposte-gameplay.md"), "# P\n## 1. Proposte\n| ID | Chiave | Proposta | Ore | Rischio |\n|---|---|---|---|---|\n| P-w10-1 | `timer-hidden` | scheda più piccola | 2 h | basso |\n"
      "## 3. Riapre la decisione\n- Riapre la decisione: D-002 — prove: 40 % delle recensioni — proposta: 5 lingue — costo: 10 h\n")
r_ = wk.check(L, 10)
assert status(r_, "w10-proposte-gameplay.md", "proposte con ID") == "ok" and status(r_, "w10-proposte-gameplay.md", "riaperture nel formato") == "ok"
write(os.path.join(W, "w10-proposte-gameplay.md"), "# P\n## 1. Proposte\n- scheda più piccola, 2 ore, rischio basso\n## 3. Riapre la decisione\n- riaprire le lingue? forse\n")
r_ = wk.check(L, 10)
assert status(r_, "w10-proposte-gameplay.md", "proposte con ID") == "warn" and status(r_, "w10-proposte-gameplay.md", "riaperture nel formato") == "warn"
write(os.path.join(L, "issue_status.json"), json.dumps({"ui-chaos": {"status": "risolto", "gate": "docs/gates/57-stasera.md", "resolved": "2026-10-19"}}))
w = json.load(open(WJ, encoding="utf-8")); w["issues"].append({"key": "ui-chaos", "label": "Troppe schede", "severity": "alta"}); w["testers"][0]["issues"].append("ui-chaos")
write(WJ, json.dumps(w, ensure_ascii=False, indent=1))
write(os.path.join(W, "w10-sintesi.md"), "# S\n| # | Chiave | Problema |\n|---|---|---|\n| 1 | `timer-hidden` | Timer coperto (P-w10-1) |\n| 2 | `ui-chaos` | Troppe schede |\n- uno\n- due\n")
r_ = wk.check(L, 10)
assert status(r_, "w10-sintesi.md", "problemi nati da un gate") == "warn" and status(r_, "w10-sintesi.md", "chiavi risolte che tornano") == "warn"
write(os.path.join(W, "w10-sintesi.md"), read(os.path.join(W, "w10-sintesi.md")) + "Timer coperto: nato col gate 57. Troppe schede: ricomparso dopo il gate 57.\n")
r_ = wk.check(L, 10)
assert status(r_, "w10-sintesi.md", "problemi nati da un gate") == "ok" and status(r_, "w10-sintesi.md", "chiavi risolte che tornano") == "ok"
assert status(r_, "w10-sintesi.md", "righe con chiave e ID") == "ok"
assert all(i["status"] != "fail" for i in r_["items"] if i["file"] in ("w10-sintesi.md", "w10-2026-10-19-beta.json") and not __import__("re").search(r"ancore|rubrica|valutazione completa", i["label"]))   # contract items only warn (calibration items are required: test_calibration.py)

# ---- fg_waves: from_gate_dev and gate_dev accepted, shown; bad types refused
wv = fg_waves.load_wave(WJ)
m = fg_waves.metrics(wv)
assert [i for i in m["issues"] if i["key"] == "timer-hidden"][0]["from_gate_dev"] == 57
assert "Timer coperto (nato col gate 57)" in fg_waves.md_metrics(m)
w9 = fg_waves.load_wave(os.path.join(W, "w09-2026-10-18-beta.json"))
dl = fg_waves.md_delta(w9, wv, fg_waves.metrics(w9), m, 10)
assert "Timer coperto (nato col gate 57)" in dl and "gate 57: Scheda Stasera" in dl and "(gate 57) |" not in dl   # gate already in the text: not repeated
for bad in ({"issues": [{"key": "x", "label": "x", "severity": "alta", "from_gate_dev": "cinquantasette"}]}, {"fixes": [{"issue": "x", "what": "y", "gate_dev": [57]}]},
            {"fixes": [{"issue": "x", "what": "y", "status": "chiuso"}]}, {"fixes": ["solo testo"]}):
    bw = dict({"wave": 11, "date": "2026-10-20", "testers": [{"id": "A-01", "verdict": "WISHLIST", "issues": []}]}, **bad)
    p_ = os.path.join(d, "bad.json"); write(p_, json.dumps(bw))
    try:
        fg_waves.load_wave(p_); raise AssertionError(f"accepted {bad}")
    except SystemExit as e:
        assert "INVALID WAVE" in str(e)

# ---- STATUS.html: "nato col gate NN" in the wave cards and in the criticalities, gate of the fix shown
import status_page, criticita
html = status_page.waves_section(L)
assert "nato col gate 57" in html, html[:400]
waves, _ = criticita.load_waves(L)
an = criticita.analyse(waves, {})
panel = criticita.wave_panel(an["panels"][-1], [], {}, {})
assert "nato col gate 57" in panel and "gate di sviluppo 57" in panel and "da verificare con persone vere" in panel
code, out, err = run("status_page.py", "--launch-dir", L, "-o", os.path.join(d, "STATUS.html"))
assert code == 0 and "nato col gate 57" in read(os.path.join(d, "STATUS.html")), err[-800:]

# ---- todo_track approve: "ok del proprietario" in Dipendenze, keys -> in_lavorazione, decisions and gate/resolved untouched
TODO = os.path.join(L, "TODO.md")
write(TODO, "# TODO\nAggiornato: 2026-10-18\n\n## Decisioni prese\n- **Steam Deck:** funziona.\n\n## Dev e pilastri\n"
            "- [ ] 🤖 **Scheda più piccola** (P-w10-1, key:timer-hidden,ui-chaos,deck) — 2026-10-25 — 2 h — nessuna — timer visibile\n"
            "- [ ] 🤖 **Altro** (P-w10-2, key:other) — 2026-10-26 — 1 h — dopo P-w10-1 — ok\n")
write(os.path.join(L, "issue_status.json"), json.dumps({"timer-hidden": {"status": "aperto", "note": "vecchia"}, "ui-chaos": {"status": "risolto", "gate": "docs/gates/57-stasera.md", "resolved": "2026-10-19"},
                                                         "deck": {"status": "non_problema", "note": "D-001"}, "other": {"status": "aperto", "gate": "docs/gates/56-x.md"}}))
r = tt.approve(TODO, "P-w10-1", "2026-10-19", os.path.join(L, "issue_status.json"), dt.date(2026, 10, 19))
line = [l for l in read(TODO).splitlines() if "P-w10-1," in l][0]
assert line.endswith("— 2026-10-25 — 2 h — ok del proprietario 2026-10-19 — timer visibile"), line
st = json.load(open(os.path.join(L, "issue_status.json"), encoding="utf-8"))
assert st["timer-hidden"] == {"status": "in_lavorazione", "note": "Approvata dal proprietario il 2026-10-19 (P-w10-1). · vecchia"}, st["timer-hidden"]
assert st["ui-chaos"] == {"status": "risolto", "gate": "docs/gates/57-stasera.md", "resolved": "2026-10-19"} and st["deck"]["status"] == "non_problema"
assert len(r["skipped"]) == 2 and r["changed"] == ["timer-hidden: aperto -> in_lavorazione"]
tt.approve(TODO, "P-w10-2", "2026-10-20", os.path.join(L, "issue_status.json"), dt.date(2026, 10, 20))
assert "— dopo P-w10-1; ok del proprietario 2026-10-20 — ok" in read(TODO)
st = json.load(open(os.path.join(L, "issue_status.json"), encoding="utf-8"))
assert st["other"]["status"] == "in_lavorazione" and st["other"]["gate"] == "docs/gates/56-x.md"            # the developer's field stays
tt.approve(TODO, "P-w10-1", "2026-10-21", None, dt.date(2026, 10, 21))                                     # re-approval: one date, replaced
assert read(TODO).count("ok del proprietario") == 2 and "ok del proprietario 2026-10-21" in read(TODO)
items = {x["pid"]: x for x in tt.parse(TODO)["items"]}
assert items["P-w10-1"]["keys"] == ["timer-hidden", "ui-chaos", "deck"] and items["P-w10-1"]["approved"] == "2026-10-21"
code, out, _ = run("todo_track.py", "--file", TODO, "approve", "P-w10", "--date", "2026-10-22")
assert code != 0                                                                                          # ambiguous pattern: nothing changes
# the developer's `gate_link.py todo --run` (todo_track done "P-w10-1" --by claude --note "gate 58") still finds the line
tt.mark_done(TODO, "P-w10-1", "claude", "gate 58", dt.date(2026, 10, 22))
assert "· fatto il 2026-10-22 (da 🤖, gate 58)" in read(TODO)

# ---- sync-decisions: D-NNN missing from both registers copied with "fonte: DECISIONI.md D-NNN"; DECISIONI.md never written
DEC = os.path.join(d, "DECISIONI.md")
write(DEC, "# DECISIONI\n\n| ID | Data | Area | Decisione | Fonte | Note |\n|---|---|---|---|---|---|\n"
           "| D-001 | 2026-10-11 | piattaforme | Steam Deck: funziona | chat | |\n| D-002 | 2026-10-13 | lingue | Almeno 8 lingue | launch/00-intenzioni.md 2026-10-13 | |\n"
           "| D-014 | 2026-10-19 | beta | Roulette spenta nella beta | chat 2026-10-19 | sostituisce D-009 |\n| D-015 | 2026-10-19 | ui | Scheda Stasera unica | brief w10 | |\n")
write(os.path.join(L, "00-intenzioni.md"), "# Intenzioni\n- Roulette spenta (D-014)\n")
h0 = hashlib.sha256(open(DEC, "rb").read()).hexdigest()
new = tt.sync_decisions(TODO, DEC, os.path.join(L, "00-intenzioni.md"), write=False)
assert [x["id"] for x in new] == ["D-001", "D-015"], new                     # D-002 came from launch, D-014 already in 00-intenzioni
assert "D-001" not in read(TODO)
code, out, _ = run("todo_track.py", "--file", TODO, "sync-decisions", "--decisions", DEC, "--intents", os.path.join(L, "00-intenzioni.md"), "--write")
assert code == 0 and "IMPORTATE: 2" in out, out
t = read(TODO)
sec = t.split("## Decisioni prese")[1].split("## Dev")[0]
assert "- **Ui:** Scheda Stasera unica (fonte: DECISIONI.md D-015, 2026-10-19)" in sec and "fonte: DECISIONI.md D-001, 2026-10-11" in sec, sec
assert tt.sync_decisions(TODO, DEC, os.path.join(L, "00-intenzioni.md"), write=True) == []                # idempotent
assert hashlib.sha256(open(DEC, "rb").read()).hexdigest() == h0
assert tt.parse(TODO)["items"][0]["pid"] == "P-w10-1"                          # decision bullets are not TODO items

# ---- project_scan: design-review, gates with header, plans, DECISIONI, mode
write(os.path.join(d, "docs", "gates", "56-old.md"), "# Gate 56 (no header)\n")
write(os.path.join(d, "docs", "gates", "57-stasera.md"), "---\ngate: 57\ntitle: Scheda Stasera\ndate: 2026-10-19\nstatus: PASS   # ok\n---\n# Gate 57\n")
write(os.path.join(d, "docs", "gates", "plan-w10.md"), "# Piano\n")
dl_ = ps.dev_link(d)
assert dl_["mode"] in ("linked", "launch-only") and dl_["launch_dir"] and dl_["dev_work"]
assert dl_["gates_with_header"] == {"count": 1, "last": 57, "last_date": "2026-10-19", "last_status": "PASS", "last_title": "Scheda Stasera", "last_file": "57-stasera.md"}, dl_
assert dl_["gate_plans"] == ["plan-w10.md"] and dl_["decisions"] == {"path": "DECISIONI.md", "count": 4, "last": "D-015"}
assert dl_["design_review"]["latest_changes_since"] == "changes-since-w09.md" and dl_["design_review"]["map_gate"] == 57 and dl_["design_review"]["runs"]
assert dl_["contract"]["ours"] == "gdl-v2"
assert ps.dev_link(tempfile.mkdtemp())["mode"] == "solo"
md = ps.to_md(ps.scan(d, 10, probe=False))
assert "Collegamento con game-developer" in md and "gate 57" in md

# ---- the contract copy is word for word the developer's (when installed), and its version is declared
ours = os.path.join(HERE, "..", "references", "dev-link.md")
assert read(ours).splitlines()[2].startswith("contract: gdl-v")
dev = next((os.path.join(b, "game-developer") for b in (os.path.expanduser("~/.claude/skills"), os.path.expanduser("~/.agents/skills"))
            if os.path.exists(os.path.join(b, "game-developer", "SKILL.md"))), None)
if dev and os.path.exists(os.path.join(dev, "references", "launch-link.md")):
    assert open(ours, "rb").read() == open(os.path.join(dev, "references", "launch-link.md"), "rb").read(), "dev-link.md differs from launch-link.md"
    gl = os.path.join(dev, "scripts", "gate_link.py")
    if os.path.exists(gl):                                                     # cross-check with the real developer script
        d3 = tempfile.mkdtemp()
        write(os.path.join(d3, "launch", "fg", "waves", "w09-sintesi.md"), "# Ondata 9 — Sintesi (2026-10-18)\n")
        write(os.path.join(d3, "docs", "gates", "57-stasera.md"), read(os.path.join(d, "docs", "gates", "57-stasera.md")).replace("status: PASS   # ok\n",
              "status: PASS\nsource: [x]\ncloses: [ui-chaos]\nverify: [rules-hidden]\nfiles: [none: x]\nscreenshots: [none: x]\nrisks: [\"copre il timer\"]\nowner_try: [prova]\ndesign_changes: [\"nessuno: x\"]\nsaves: not touched\nbuild: none\n") + "## Per il proprietario\nx\n")
        r3 = subprocess.run([sys.executable, gl, "--project", d3, "since", "--out", "docs/design-review/changes-since-w09.md"], capture_output=True)
        assert r3.returncode == 0, r3.stderr
        c3 = wk.parse_changes_since(read(os.path.join(d3, "docs", "design-review", "changes-since-w09.md")))
        assert [g["gate"] for g in c3["gates"]] == [57] and c3["risks"] == [{"gate_dev": 57, "risk": "copre il timer"}]
        assert [(f["issue"], f["gate_dev"]) for f in c3["fixes"]] == [("ui-chaos", 57), ("rules-hidden", 57)], c3["fixes"]
        shutil.rmtree(d3, ignore_errors=True)

shutil.rmtree(d, ignore_errors=True); shutil.rmtree(d2, ignore_errors=True)
print("ALL DEV_LINK TESTS PASSED")
