"""Live state of STATUS.html: the owner's decisions (issue_status.json) everywhere issues appear, beta and full-game waves kept apart,
tabs (offline, remembered), pillars by name with credible hours only, real-review themes with "il tuo gioco" and tester shares,
TODO.md kept alive by todo_track.py (done / reopen / add, open vs done per section, stale warning)."""
import os, sys, json, tempfile, datetime as dt, re, time, subprocess
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("must not use the network")
common.http_get = no_net
import criticita as cr, report_charts as rc, status_page as sp, theme_labels as TL, todo_track as tt, qa

HOSTILE = "<img src=x onerror=alert(1)>"
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "fg", "waves")); os.makedirs(os.path.join(d, "_raw"))
W = lambda n, t: open(os.path.join(d, n), "w", encoding="utf-8").write(t)
IDS = [f"{g}-{i:02d}" for g in "AB" for i in range(1, 11)]
DEFS = {"run-variety": dict(label="Run troppo simili", severity="alta"), "tray-feel": dict(label="Dubbi sul vassoio", severity="media"),
        "no-coop": dict(label="Niente co-op", severity="media"), "perf-unknown": dict(label="Prestazioni non note " + HOSTILE, severity="bassa")}
def wave(n, date, counts, suffix="", label="x", ceiling=False):
    ts = [dict(id=tid, verdict=["WISHLIST", "SALDI", "IGNORO", "REFUND"][k % 4], issues=[key for key, c in counts.items() if k < c]) for k, tid in enumerate(IDS)]
    w = dict(wave=n, date=date, label=label, testers=ts, issues=[dict(key=k, **v) for k, v in DEFS.items()])
    if ceiling:
        w["ceiling"] = {"testers": [dict(id=tid, verdict="WISHLIST" if k < 15 else "SALDI", reason="risolvibile: x" if k < 15 else "gusto/genere: y") for k, tid in enumerate(IDS)]}
    json.dump(w, open(os.path.join(d, "fg", "waves", f"w{n:02d}-{date}{suffix}.json"), "w"))
# no "stage" key: it must be inferred from the file name (-beta / -full)
wave(1, "2026-10-06", {"run-variety": 8, "tray-feel": 4, "no-coop": 2}, "-beta")
wave(2, "2026-10-06", {"run-variety": 2, "no-coop": 6}, "-full")
wave(3, "2026-10-20", {"run-variety": 6, "tray-feel": 3, "perf-unknown": 4}, "-beta", ceiling=True)
wave(4, "2026-10-20", {"run-variety": 1, "no-coop": 5}, "-full")
json.dump({"_note": "decisioni", "run-variety": {"status": "pianificato", "note": "3 mappe nel gioco completo " + HOSTILE, "aliases": ["run ripetitive"]},
           "no-coop": {"status": "accettato", "note": "co-op dopo"}, "tray-feel": {"status": "da_verificare", "note": "test reale"}, "perf-unknown": "risolto", "x": 5},
          open(os.path.join(d, "issue_status.json"), "w"))

# ---- two ceilings: version (margin) and full game; a legacy single block is the full-game ceiling
import fg_waves
lw3 = fg_waves.load_wave(os.path.join(d, "fg", "waves", "w03-2026-10-20-beta.json"))
m3 = fg_waves.metrics(lw3)
assert m3["ceiling"] is None and m3["ceiling_full"]["score"] > m3["score"] and m3["ceiling_estimate"] is None   # legacy block -> full game, no margin claimed
v = dict(lw3, ceiling={"version": {"testers": [dict(id=t, verdict="SALDI") for t in IDS]}, "full": lw3["ceiling"]})
mv = fg_waves.metrics(v)
assert mv["ceiling"]["score"] == 40.0 and mv["ceiling"]["headroom"] == round(40.0 - mv["score"], 1) and mv["ceiling_full"]["score"] == m3["ceiling_full"]["score"]
me = fg_waves.metrics(dict(lw3, ceiling={"version": {"estimate": "55-58", "note": "non misurato"}, "full": lw3["ceiling"]}))
assert me["ceiling"] is None and me["ceiling_estimate"] == {"value": "55-58", "note": "non misurato"}
txt = fg_waves.md_metrics(me); assert "Tetto di questa versione: non misurato · stima 55-58 [STIMA]" in txt and "Tetto del gioco completo" in txt and "margine ancora" not in txt
assert "Tetto di questa versione: 40" in fg_waves.md_metrics(mv) and "margine ancora da prendere" in fg_waves.md_metrics(mv)

# ---- owner decisions
own = cr.load_owner(d)
assert set(own) == {"run-variety", "no-coop", "tray-feel", "perf-unknown"} and own["perf-unknown"]["status"] == "risolto"
assert cr.is_now("tray-feel", own) and not cr.is_now("run-variety", own) and cr.is_now("never-decided", own)
b = cr.owner_badge("run-variety", own); assert "Pianificato" in b and "&lt;img" in b and "<img" not in b and "<svg" in b
waves, problems = cr.load_waves(d)
assert [(w["n"], w["stage"]) for w in waves] == [(1, "beta"), (2, "full"), (3, "beta"), (4, "full")] and not problems
an = cr.analyse(waves, own)
p3 = an["panels"][2]; assert p3["prev_index"] == 0                                    # beta compared with beta, never with the full-game wave before it
assert next(r for r in p3["rows"] if r["key"] == "run-variety")["delta"] == -10.0 and next(r for r in p3["rows"] if r["key"] == "perf-unknown")["status"] == "nuova"
assert an["panels"][3]["prev_index"] == 1 and [r["key"] for r in p3["resolved"]] == ["no-coop"]
now = {x["key"] for x in an["issues"] if x["now"]}; assert now == {"tray-feel"}, now   # still raised and not decided: only the one "da verificare"
card, data = cr.build(d, {})
assert "Da fare adesso (1)" in card and "Già deciso (" in card and "Da verificare" in card and "Accettato così" in card and "issue_status.json" in card
assert card.index("Da fare adesso") < card.index("Già deciso") and "<img" not in card
dflt = re.search(r'data-p="(w\d+)" aria-pressed="true"', card).group(1); assert dflt == "w2"   # the latest BETA wave is open by default
# Q&A follows the decisions
faq = dict(((q, a) for _, q, a in qa.faq(dict(st={}, crit=data, gate_names={}, today=dt.date(2026, 10, 9), plan=dict(phases=[])))))
assert "Dubbi sul vassoio" in faq["Quali sono le criticità aperte più gravi?"] and "Run troppo simili" not in faq["Quali sono le criticità aperte più gravi?"]

# ---- real reviews: "il tuo gioco", tester shares from the latest beta and full wave
W("05b-critiche-reali.md", "| Tema | Peso | Esempio | Perché conta | Il tuo gioco |\n|---|---|---|---|---|\n"
  "| **Ripetitivo, noioso** | 15% | x | y | **[SÌ]**. I piani sono fissi |\n| **Co-op assente** | 14% | x | y | **[A RISCHIO]** (alto). Si aspetta la co-op |\n"
  "| **Prezzo / valore** | 12% | x | y | **[NO]** per la beta (gratis). **[A RISCHIO]** per il gioco a pagamento: corto |\n\n"
  "| # | Tema premiato | Peso | Esempio | Ce l'ha? | Da non tagliare |\n|---|---|---|---|---|---|\n| 1 | **Stile grafico** | 13% | x | **[SÌ, ma generico]** toon | y |\n| 2 | **Risate, giocare con altri** | 17% | x | **[PARZIALE]** caos sì, amici no | y |\n")
t05 = TL.read_05b(d)
assert [r["tags"] for r in t05["punished"]] == [["sì"], ["a rischio (alto)"], ["no per la beta", "a rischio per il gioco a pagamento"]], t05["punished"]
assert [r["tags"] for r in t05["rewarded"]] == [["sì, ma generico"], ["in parte"]] and t05["punished"][0]["text"].startswith("I piani")
assert TL.ours("repetitive_shallow", "punished", t05)["name"].startswith("Ripetitivo") and TL.ours("coop_friends", "rewarded", t05)["name"].startswith("Risate")
lw = rc.latest_waves(d); assert lw["beta"]["wave"] == 3 and lw["full"]["wave"] == 4
assert rc.share_raising(lw["beta"], TL.theme_issues(d)["repetitive_shallow"]) == 30.0 and rc.share_raising(lw["full"], ["no-coop"]) == 25.0 and rc.share_raising(lw["beta"], []) is None
json.dump({"repetitive_shallow": ["tray-feel"]}, open(os.path.join(d, "_raw", "theme_issues.json"), "w")); assert TL.theme_issues(d)["repetitive_shallow"] == ["tray-feel"]
os.remove(os.path.join(d, "_raw", "theme_issues.json"))
row = lambda t, m: dict(theme=t, macro_pct=m, pooled_pct=m, breadth=5, games=7, reviews_with_theme=3)
json.dump(dict(groups=dict(comps=dict(punished=[row("repetitive_shallow", 20.0), row("multiplayer_netcode", 9.0)], rewarded=[row("coop_friends", 17.0), row("art_style", 13.0)]))), open(os.path.join(d, "_raw", "corpus.json"), "w"))
rv = "".join(rc.reviews(d)).replace("&#x27;", "'")
assert "Il tuo gioco ne soffre?" in rv and "Ce l'hai?" in rv and "a rischio (alto)" in rv and "sì, ma generico" in rv and "Tester beta" in rv and "30%" in rv and "25%" in rv
assert "Il tuo gioco: sì · lo pensano 30% dei tester (beta), 5% (completo)" in rv.replace("&#x27;", "'"), re.findall(r'data-tip="([^"]*)"', rv)[:2]
assert "Pianificato" in rv and "repetitive_shallow" not in re.sub(r"<[^>]+>", "", rv)        # no technical keys in what the owner reads

# ---- pillars: names, one-line reason, hours only when credible
W("01-dev.md", "| # | Pilastro | Voto | Evidenza | Ore per PASS [STIMA] |\n|---|---|---|---|---|\n"
  "| 1 | Variabilità | **[MARGINAL]** (era FAIL) | [FATTO] 18 perk (`Perk.cs`). Ma i piani sono fissi. | 14-20 (perk iniziale; eventi a caso) |\n"
  "| 2 | Feedback | **[PASS]** provvisorio | [FATTO] Suoni ok. | 1-2 (rigiocare) |\n| 3 | Tema | **[FAIL]** | Non si vede. | da capire con il test |\n| 4 | Assurdo | **[MARGINAL]** | x. | 14-201313 |\n")
pr = {r["name"]: r for r in rc.pillar_rows(d)}
assert set(pr) == {"Variabilità", "Feedback", "Tema", "Assurdo"} and pr["Variabilità"]["hours"] == (14.0, 20.0) and pr["Variabilità"]["qualifier"] == ""
assert pr["Variabilità"]["reason"] == "18 perk. Ma i piani sono fissi" and "Perk.cs" not in pr["Variabilità"]["reason"] and pr["Variabilità"]["todo"] == "perk iniziale; eventi a caso" and pr["Feedback"]["qualifier"] == "provvisorio"
assert pr["Tema"]["hours"] is None and pr["Tema"]["todo"] == "da capire con il test" and pr["Assurdo"]["hours"] is None   # absurd numbers are not shown as hours
ph = rc.pillars(d)[0]; assert "Non regge" in ph and "14-20 h" in ph and "201313" not in ph.split("<table")[0] and ph.index("Tema") < ph.index("Variabilità") < ph.index("Feedback")

# ---- TODO.md live
W("TODO.md", "# TODO\nAggiornato: 2026-10-01\n\n## Dev\n- [ ] 👤 **Rigioca la beta** — 2026-10-05 — 2 h — nessuna — note\n- [x] 🤖 Fix pila — 2026-10-02 — 1 h\n- [ ] 🤖 **Varietà dei piani** — 2026-11-01 — 8-12 h — ok — run diverse\n\n## Store\n- [ ] 👤 Scegli la capsule | 2026-11-20 | 0,5 h\n")
T = os.path.join(d, "TODO.md")
t = tt.parse(T); assert [x["done"] for x in t["items"]] == [False, True, False, False] and t["items"][0]["owner"] == "me" and t["items"][2]["h"] == 10.0 and t["items"][3]["due"] == "2026-11-20"
try: tt.mark_done(T, "**", today=dt.date(2026, 10, 9)); raise AssertionError("ambiguous pattern accepted")
except SystemExit as e: assert "match" in str(e)
x = tt.mark_done(T, "rigioca beta", by="me", note="gate 48", today=dt.date(2026, 10, 9)); assert x["n"] == 1
txt = open(T, encoding="utf-8").read(); assert "- [x] 👤 **Rigioca la beta**" in txt and "· fatto il 2026-10-09 (da 👤, gate 48)" in txt and "Aggiornato: 2026-10-09" in txt
t = tt.parse(T); assert t["items"][0]["done"] and t["items"][0]["done_note"] == "fatto il 2026-10-09 (da 👤, gate 48)" and t["items"][0]["metric"] == "note"
tt.reopen(T, "#1", today=dt.date(2026, 10, 9)); assert "fatto il" not in open(T, encoding="utf-8").read().splitlines()[4] and not tt.parse(T)["items"][0]["done"]
tt.mark_done(T, "#1", today=dt.date(2026, 10, 9))
tt.drop(T, "varietà", why="decisione: nel gioco completo", today=dt.date(2026, 10, 9)); t = tt.parse(T)
assert t["items"][2]["dropped"] and not t["items"][2]["done"] and "[-]" in open(T, encoding="utf-8").read() and "superata il 2026-10-09 (decisione: nel gioco completo)" in t["items"][2]["done_note"]
tt.add(T, "Store", "🤖 Screenshot in inglese — 2026-11-25 — 2 h", today=dt.date(2026, 10, 9)); t = tt.parse(T)
assert t["items"][-1]["section"] == "Store" and t["items"][-1]["action"].startswith("Screenshot") and len(t["items"]) == 5
r = subprocess.run([sys.executable, os.path.join(R, "todo_track.py"), "--file", T, "--today", "2026-10-09", "stats"], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
assert r.returncode == 0 and "2 aperte, 2 fatte su 4; superate: 1" in r.stdout, r.stdout + r.stderr
open_, done, hours = sp.read_todos(d); assert len(open_) == 2 and done == 2 and hours == 2.5

# ---- the page: tabs, decisions everywhere, live TODO, stale warning, no network, escaped
json.dump({"game": "G", "verdict": {"color": "giallo", "summary": "s", "risks": ["Run ripetitive e vassoio mai provati", {"text": "Pochi fondi", "issues": ["no-coop"]}, "Next Fest " + HOSTILE]},
           "issue_aliases": {"tray-feel": ["vassoio"], "bad": ["("]}}, open(os.path.join(d, "status.json"), "w"))
W("05-focusgroup.md", "## Matrice di convergenza\n| Tema | Simulata | Stato |\n|---|---|---|\n| Run ripetitive / poca varietà | 12 | CONFERMATA |\n| Dubbi sul vassoio | 3 | IPOTESI |\n| Altro | 1 | - |\n")
later = time.time() + 3600; os.utime(os.path.join(d, "issue_status.json"), (later, later))
page = sp.build(d, "private", [], [], set(), dt.date(2026, 10, 9))
body = page.split("<script>")[0]
assert "<img src=x" not in body and "<script src" not in page and "<link " not in page and "https://" not in body
assert page.count('role="tab"') == 4 and 'role="tabpanel"' in page and "localStorage" in page and "try{localStorage" in page and 'aria-controls="p-gioco"' in page
for need in ("Pilastri: dove regge il gioco", "Criticità, ondata per ondata", "Ondate del focus group", "Gioco completo (proiezione)", "Beta gratuita", "Tetto del gioco completo", "non è margine di oggi",
             "Di cosa si lamentano", "Cose da fare (TODO)", "2 fatte su 4", "Superate dalle tue decisioni", "Da aggiornare", "le tue decisioni (issue_status.json)", "Run ripetitive / poca varietà", "Pianificato", "Da verificare", "Accettato così"):
    assert need in page, need
verdict = page[page.index("Verdetto:"):page.index("</section>", page.index("Verdetto:"))]
assert "Pianificato" in verdict and "Da verificare" in verdict and "Accettato così" in verdict and verdict.count('class="pill') == 3   # risk 1 -> run-variety + tray-feel, risk 2 -> no-coop, risk 3 -> none
conv = page[page.index("Run ripetitive / poca varietà") - 400:]; conv = conv[:conv.index("</table>")]
assert conv.count("own") >= 2 and "Altro</td>" in conv                                       # rows of document tables carry the owner's decision
pan = {m.group(1): m.start() for m in re.finditer(r'<section role="tabpanel" id="p-(\w+)"', page)}
assert list(pan) == ["riepilogo", "gioco", "piano", "docs"] or list(pan)[:2] == ["riepilogo", "gioco"]
assert pan["gioco"] < page.index("Pilastri: dove regge") < pan["piano"] < page.index("Cose da fare (TODO)")
print("ALL LIVE_STATUS TESTS PASSED")
