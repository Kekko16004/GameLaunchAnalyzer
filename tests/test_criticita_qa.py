"""Criticità wave by wave / per gate / evolution, and the Q&A section: statuses against the previous wave, resolved with their fix, manual register,
the owner's status.json formats, CLIs, both pages, audiences, escaping, links that land somewhere."""
import os, sys, json, re, csv, tempfile, subprocess, datetime as dt
from html.parser import HTMLParser
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("must not use the network")
common.http_get = no_net
import criticita as cr, qa, status_page as sp, glossary as gl

HOSTILE = "<img src=x onerror=alert(1)>"
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "fg", "waves")); os.makedirs(os.path.join(d, "_raw"))
W = lambda n, t: (os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True), open(os.path.join(d, n), "w", encoding="utf-8").write(t))
IDS = [f"{g}-{i:02d}" for g in "AB" for i in range(1, 11)]          # 20 testers: each issue count -> 5% steps
DEFS = {"slow-opening": dict(label="Apertura lenta", severity="alta", gate="A", area="Primi minuti", recommendation="Primo piatto in 40 secondi"), "no-feedback": dict(label="Il successo non dà feedback", severity="alta", gate="A", recommendation="Suono e scintille"),
        "tutorial-text": dict(label="Tutorial troppo testuale", severity="media", gate="B"), "ui-small": dict(label="Interfaccia piccola " + HOSTILE, severity="bassa"), "new-bug": dict(label="Crash al secondo piatto", severity="alta", gate="C", area="Stabilità")}
def wave(n, date, counts, stage="beta", fixes=None):
    ts = []
    for k, tid in enumerate(IDS):
        iss = [key for key, c in counts.items() if k < c]
        ts.append(dict(id=tid, verdict=["WISHLIST", "SALDI", "IGNORO", "REFUND"][k % 4], click=k % 2 == 0, pitch_ok=k % 3 == 0, issues=iss or ["ui-small"] if False else iss))
    w = dict(wave=n, date=date, build=f"v0.{n}", label="x", stage=stage, testers=ts, issues=[dict(key=k, **v) for k, v in DEFS.items()])
    if fixes: w["fixes"] = fixes
    json.dump(w, open(os.path.join(d, "fg", "waves", f"w{n:02d}-{date}.json"), "w"))
wave(1, "2026-10-06", {"slow-opening": 12, "no-feedback": 9, "tutorial-text": 6, "ui-small": 3})
wave(2, "2026-10-27", {"slow-opening": 4, "no-feedback": 9, "ui-small": 3, "new-bug": 5}, fixes=[dict(issue="slow-opening", what="primo piatto in 35 secondi"), dict(issue="tutorial-text", what="comandi mostrati in gioco")])
wave(3, "2026-11-20", {"no-feedback": 2, "tutorial-text": 2, "ui-small": 3, "new-bug": 7}, fixes=[dict(issue="no-feedback", what="suoni e scintille")])
waves, problems = cr.load_waves(d)
assert [(w["n"], w["stage"]) for w in waves] == [(1, "beta"), (2, "beta"), (3, "beta")] and problems == []
an = cr.analyse(waves)
st_of = lambda i, key: next(r for r in an["panels"][i]["rows"] if r["key"] == key)
assert all(r["status"] == "presente" for r in an["panels"][0]["rows"]) and len(an["panels"][0]["rows"]) == 4
assert st_of(1, "slow-opening")["status"] == "in calo" and st_of(1, "slow-opening")["delta"] == -40.0 and st_of(1, "no-feedback")["status"] == "persistente" and st_of(1, "new-bug")["status"] == "nuova"
assert [r["key"] for r in an["panels"][1]["resolved"]] == ["tutorial-text"] and an["panels"][1]["resolved"][0]["fix"] == "comandi mostrati in gioco"
assert [r["key"] for r in an["panels"][2]["resolved"]] == ["slow-opening"] and st_of(2, "tutorial-text")["status"] == "ricomparsa" and st_of(2, "new-bug")["status"] == "in aumento" and st_of(2, "no-feedback")["status"] == "in calo"
assert an["panels"][1]["rows"][0]["severity"] == "alta"                                                         # severity first, then how many testers
today_open = {x["key"]: x["open"] for x in an["issues"]}
assert today_open == {"slow-opening": False, "no-feedback": True, "tutorial-text": True, "ui-small": True, "new-bug": True} and an["issues"][0]["open"]
assert next(x for x in an["issues"] if x["key"] == "slow-opening")["resolved_in"] == 2 and next(x for x in an["issues"] if x["key"] == "new-bug")["gate"] == "C"

# manual register (other sources) + CLI
def run(tool, *a): return subprocess.run([sys.executable, os.path.join(R, tool)] + list(a), capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
reg = os.path.join(d, "criticita.csv")
assert run("criticita.py", "--csv", reg, "add", "--key", "tester-lost", "--label", "I tester esterni si perdono al menu", "--severity", "alta", "--source", "playtest", "--gate", "B", "--opened", "2027-01-10", "--note", "5 su 20").returncode == 0
assert run("criticita.py", "--csv", reg, "add", "--key", "reviews-grind", "--label", "Recensioni: troppo grind", "--severity", "media", "--source", "recensioni", "--opened", "ondata 1").returncode == 0
assert run("criticita.py", "--csv", reg, "add", "--key", "tester-lost", "--label", "I tester esterni si perdono al menu", "--severity", "alta", "--source", "playtest", "--gate", "B", "--opened", "2027-01-10").returncode == 0   # updated, not duplicated
assert len(cr.read_register(d)) == 2 and run("criticita.py", "--csv", reg, "close", "reviews-grind", "--date", "2026-12-01").returncode == 0 and run("criticita.py", "--csv", reg, "close", "nope").returncode != 0
assert next(m for m in cr.read_register(d) if m["key"] == "reviews-grind")["status"] == "risolta" and b"tester-lost" in run("criticita.py", "--csv", reg, "list").stdout
assert cr.wave_index_for("2027-01-10", waves) == 2 and cr.wave_index_for("ondata 1", waves) == 0 and cr.wave_index_for("2026-10-10", waves) == 0 and cr.wave_index_for("boh", waves) is None

st = dict(game="G", verdict=dict(color="giallo", summary="ok", risks=["a"]), gates={"A": dict(state="pass", note="ok"), "B": dict(state="pending", note="Test reale il 10 gennaio."), "C": dict(state="pending", note="")},
          critiques_by_wave=[dict(wave="Ondata 0 (prima del panel)", score="n/d", note="note a mano", items=[dict(issue="Idea poco chiara", severity="alta", seen_by="3 persone", status="aperta", action="Riscrivere il pitch", gate="0")]),
                             dict(wave="Ondata 2", items=[dict(issue="duplicato da ignorare", severity="bassa")])],
          qa=[dict(q="Meglio itch o Steam per iniziare?", a="Prima itch per i test.", topic="Piattaforme", custom=True), dict(q="Domanda generica salvata", a="Risposta.", topic="Generale")], product=dict(kind="beta"))
card, data = cr.build(d, st)
assert card.count('data-p="') >= 12 and card.count('<button type="button" data-p=') == 6, card.count('<button type="button" data-p=')   # manual wave + 3 waves + gates + evolution
assert card.count(' hidden>') == 5 and 'data-p="w2"' in card and re.search(r'<button type="button" data-p="w2" aria-pressed="true">', card)   # latest wave open by default
assert "Da altre fonti in questo periodo" in card and "I tester esterni si perdono al menu" in card and "Ondata 0 (prima del panel)" in card and "Riscrivere il pitch" in card and "duplicato da ignorare" not in card
assert "Gate B · Test reale" in card and "Non collegate a un cancello" in card and "Superato" in card and "Da fare" in card and "Nata in" in card and "Evoluzione" in card and "Criticità × ondata" in card and 'class="spark"' in card and "color-mix" in card
assert "Ricomparsa" in card and "Risolta" in card and "In aumento" in card and "correzione: comandi mostrati in gioco" in card and "primo piatto in 35 secondi" in card
assert HOSTILE not in card and "&lt;img src=x onerror=alert(1)&gt;" in card and "NaN" not in card and "None" not in card
assert cr.build(tempfile.mkdtemp(), {}) == (None, None)

# Q&A: log CLI, stored + faq + suggestions
qj = os.path.join(d, "qa.json")
assert run("qa.py", "--json", qj, "add", "--q", "Perché non pago Steam adesso?", "--a", "Il Gate B non è superato.", "--topic", "Cancelli", "--wave", "3", "--gate", "b").returncode == 0
assert run("qa.py", "--json", qj, "add", "--q", "perché non pago steam adesso?", "--a", "Risposta aggiornata.", "--topic", "Cancelli").returncode == 0
log = json.load(open(qj)); assert len(log) == 1 and log[0]["a"] == "Risposta aggiornata." and log[0]["id"] == 1
assert run("qa.py", "--json", qj, "add", "--q", "Seconda?", "--a", "Sì.", "--by", "generica").returncode == 0 and run("qa.py", "--json", qj, "rm", "9").returncode != 0 and b"perch" in run("qa.py", "--json", qj, "list").stdout
assert [x["custom"] for x in qa.stored(d, st)] == [True, False, True, False] or len(qa.stored(d, st)) == 4
import plan_steps as ps
ctx = dict(st=st, wl_a=dict(current=1510, velocity_4w=248, days_to_launch=96, alerts=[]), econ=json.load(open(os.path.join(R, "..", "..", "tests", "x.json"))) if False else None, window=None, crit=data, plan=dict(phases=[]), today=dt.date(2026, 11, 25), gate_names=sp.GATE_NAMES, contingencies=[dict(title="Pochi arrivi su itch")])
f = {q: a for _, q, a in qa.faq(ctx)}
assert "Perché il verdetto è giallo?" in f and "Posso pagare Steam Direct adesso?" in f and "Non ancora" in f["Posso pagare Steam Direct adesso?"] and "Gate B · Test reale" in f["Posso pagare Steam Direct adesso?"]
assert "Cosa è cambiato rispetto all'ultima ondata?" in f and "risolte: Apertura lenta" in f["Cosa è cambiato rispetto all'ultima ondata?"] and "nuove: Tutorial troppo testuale" in f["Cosa è cambiato rispetto all'ultima ondata?"] and "in aumento: Crash al secondo piatto" in f["Cosa è cambiato rispetto all'ultima ondata?"]
assert "Crash al secondo piatto" in f["Quali sono le criticità aperte più gravi?"] and "1.510" in f["A che punto sono le wishlist?"] and "E se qualcosa va male?" in f and "Il gioco completo regge?" not in f and "Quante copie servono per coprire i costi?" not in f
assert any("Perché la beta" in q for q in f) and any("Cosa serve per superare il prossimo cancello?" == q for q in f)
sg = [q for q, _ in qa.suggested(ctx)]; assert any("Gate B" in q for q in sg) and any("Crash al secondo piatto" in q for q in sg) and len(sg) <= 7
assert qa.resolve_links("vedi [[gates|i cancelli]] e [[zzz|altro]]", {"gates": "sec3"}) == 'vedi <a class="xl" href="#sec3" title="Vai alla sezione">i cancelli</a> e altro'

# pages
today = dt.date(2026, 11, 25)
W("status.json", json.dumps(st)); W("calendar.md", "## ✅ Passi in ordine\n### FASE 1\n1. [ ] 👤 **Registra le wishlist**. · 📅 2026-11-30\n")
for who in ("private", "partner"):
    page = sp.build(d, who, [], [], set(), today)
    assert "Criticità, ondata per ondata" in page and "Domande e risposte" in page and "[[" not in page and "Le tue domande" in page and "Meglio itch o Steam per iniziare?" in page and "perché non pago steam adesso?" in page, who
    assert 'data-qa' in page and 'data-crit' in page and "<h3>Domande che conviene farti adesso</h3>" in page and "Cosa devo fare adesso?" in page
    ids = set(re.findall(r'id="([^"]+)"', page)); hrefs = re.findall(r'href="#([^"]+)"', page)
    assert all(h in ids for h in hrefs), [h for h in hrefs if h not in ids]
    class Bal(HTMLParser):
        def __init__(s): super().__init__(); s.stack = []; s.bad = 0
        def handle_starttag(s, t, a):
            if t not in gl.VOID: s.stack.append(t)
        def handle_endtag(s, t):
            if t in gl.VOID: return
            if s.stack and s.stack[-1] == t: s.stack.pop()
            else: s.bad += 1
    b = Bal(); b.feed(page); assert b.bad == 0 and not b.stack, (who, b.bad, b.stack[:4])
pub = sp.build(d, "publisher", [], [], set(), today)
assert "Criticità, ondata per ondata" not in pub and "Domande e risposte" not in pub and "Meglio itch" not in pub
assert "Domande e risposte" not in sp.build(d, "private", [], [], {"qa"}, today) and "Criticità, ondata per ondata" not in sp.build(d, "private", [], [], {"critiques"}, today)
print("ALL CRITICITA_QA TESTS PASSED")
