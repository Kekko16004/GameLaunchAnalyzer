"""weblinks (every URL clickable, short labels, no injection), calendar_view (items from calendar.md / TODO.md / events / waves,
dedupe, overdue, roadmap from status.json or guessed, month grids, JSON payload safe), step notes as chips, hero "cosa manca",
metro heading with the scoring date, STATUS.html header date = generation date. No network."""
import os, sys, json, re, html, tempfile, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "research"))
os.environ["GLS_HOME"] = tempfile.mkdtemp()
import weblinks as wl, calendar_view as cv, plan_steps as ps, todo_track as tt, status_page as sp, market_page as mp, cohort_bench as cb
D = dt.date

# ---- weblinks
assert wl.short_url("https://docs.google.com/forms/d/e/1FAIpQLSclblIMMQJo5Z8HOuKZqS3lQBsdJS0pW78Vdhhv0sBnHmRgjA/viewform").startswith("docs.google.com/forms/d/e/")
assert len(wl.short_url("https://docs.google.com/forms/d/e/1FAIpQLSclblIMMQJo5Z8HOuKZqS3lQBsdJS0pW78Vdhhv0sBnHmRgjA/viewform")) <= 40
assert wl.short_url("https://www.reddit.com/r/indiegames/") == "reddit.com/r/indiegames"
t = wl.linkify_text(html.escape("scadenza 2026-10-23 [FATTO https://docs.google.com/forms/d/e/X/viewform?a=1&b=2, letto 2026-10-17] · https://x.com/Steam."))
assert t.count("<a ") == 2 and 'href="https://docs.google.com/forms/d/e/X/viewform?a=1&amp;b=2"' in t and ", letto 2026-10-17]" in t and t.endswith("</a>.")
assert 'target="_blank"' in t and 'rel="noopener noreferrer"' in t
evil = html.escape('see https://evil.com/"><script>alert(1)</script> and javascript:alert(2)')
o = wl.linkify_text(evil)
assert "<script" not in o and 'href="https://evil.com/"' in o and "javascript:" not in re.sub(r"&[a-z]+;", "", "".join(re.findall(r'href="([^"]*)"', o)))
doc = ('<p>a https://a.com/x</p><a href="https://b.com/very/long/path/that/goes/on/and/on/forever">https://b.com/very/long/path/that/goes/on/and/on/forever</a>'
       '<code>https://c.com</code><p title="https://d.com">t</p><script>var u="https://e.com";</script><a href="#sec1">int</a>')
o = wl.linkify_html(doc)
assert '<a class="ext" href="https://a.com/x"' in o and 'title="https://d.com"' in o and "<code>https://c.com</code>" in o and 'var u="https://e.com"' in o
assert re.search(r'<a href="https://b.com/[^"]+" target="_blank" rel="noopener noreferrer">b.com/very/long', o) and '<a href="#sec1">int</a>' in o
# inline markdown: bare URL + markdown link + code all handled, bold still works
i = sp.inline("**Vai** a https://store.steampowered.com/app/1/ e [qui](https://x.org) `https://code.io`")
assert "<strong>Vai</strong>" in i and i.count("<a ") == 2 and 'target="_blank"' in i and "<code>https://code.io</code>" in i
assert "<a" not in sp.inline("[x](javascript:alert(1))") and "<img" not in sp.inline("<img src=x onerror=1> https://a.com/<b>")

# ---- step notes -> chips
p = sp.note_parts("- scadenza 2026-11-15 [FATTO https://howtomarketagame.com/festivals/, letto 2026-10-17] · serve: pagina Steam · prossimo passo: manda il modulo · https://forms.x/y [id promo:k]")
assert p["next"] == "manda il modulo" and ("serve", "pagina Steam") in p["chips"] and p["chips"][0][0] == "scadenza" and p["links"] == ["https://forms.x/y"]
li = sp.step_li(dict(n=78, done=False, owner="me", due="2026-10-18", notes=["- scadenza 2026-10-23 · serve: trailer · prossimo passo: manda il modulo · https://forms.x/y [id promo:a]"],
                     text="**Candidati a BIG** entro il 2026-10-23 (showcase digitale, valore 4/18)."), D(2026, 10, 18))
assert 'id="step-78"' in li and "valore 4/18" in li and li.count("valore 4/18") == 1 and "→ manda il modulo" in li and 'class="due soon"' in li and "oggi" in li and "[id promo" not in li

# ---- calendar items
L = tempfile.mkdtemp(); os.makedirs(os.path.join(L, "_raw")); os.makedirs(os.path.join(L, "fg"))
cal_md = """# Cal
## 1. Date fisse
| Data | Evento | Tipo | Fonte |
|---|---|---|---|
| 2026-11-07 → 2026-11-13 | Test reale con 10 tester | gate | x |
| ~~2026-11-15~~ | Vecchio GO superato | gate | x |
| 2026-10-25 | Pagare Steam Direct e inviare la pagina | scadenza | x |
## ✅ Passi in ordine
### FASE 1 — Adesso
1. [x] 👤 **Rigioca la beta** (~3 h). · 📅 2026-10-11
2. [ ] 👤 **Paga Steam Direct** e invia la pagina (100 $). · 📅 2026-10-25
3. [ ] 🤖 **Ondata 2 del focus group** sulla build. · 📅 2026-10-15
4. [ ] 👤+🤖 **Pagina Coming Soon pubblica** con il trailer. · 📅 2026-10-31
5. [ ] 👤 **Beta gratuita pubblica su itch** (Atto I). · 📅 2026-11-10
6. [ ] 👤 **Demo Steam pubblica** e notifica. · 📅 2026-12-20
7. [ ] 👤 **Lancio**: build finale. · 📅 2027-05-13
### 📣 Eventi online e showcase (da promo_events.py)
8. [ ] 👤 **Candidati a Big Show** entro il 2026-10-23. · 📅 2026-10-18
   - scadenza 2026-10-23 [FATTO https://forms.example.com/a, letto 2026-10-17] · serve: trailer · prossimo passo: manda il modulo
## 3. Tripwire
| Data | Soglia | Segnale | Azione |
|---|---|---|---|
| 2026-11-14 | 100 | 2 settimane dopo la pagina | rifare le capsule |
| ogni lunedì dal 2026-10-26 | ore | ore reali < 8 | sposto le date |
"""
open(os.path.join(L, "calendar.md"), "w", encoding="utf-8").write(cal_md)
open(os.path.join(L, "TODO.md"), "w", encoding="utf-8").write("# TODO\nAggiornato: 2026-10-17\n\n## Dev\n- [ ] 👤 **Paga Steam Direct** — 2026-10-25 — 1 h\n"
                                                                "- [ ] 🤖 **Traduci la pagina** in 8 lingue — 2026-11-30 — 4 h — nessuna — 8 lingue\n- [-] 👤 **Vecchia voce** — 2026-11-01\n")
open(os.path.join(L, "fg", "timeline.csv"), "w", encoding="utf-8").write("wave,stage,date,score\n1,beta,2026-10-07,24.4\n2,full,2026-10-07,50\n")
json.dump({"launch": "2027-05-13"}, open(os.path.join(L, "_raw", "wl_plan.json"), "w"))
json.dump({"next_fests": [{"name": "Steam Next Fest feb 2027", "start": "2027-02-22", "end": "2027-03-01", "registration_deadline": "2027-01-10", "chosen": True}],
           "themed_fests": [{"name": "Cooking Fest 2027", "start": None}], "warnings": [{"event": "Summer Sale", "start": "2027-06-24", "end": "2027-07-08", "text": "saldo"}],
           "steps": [{"event": "NF", "deadline": "2027-01-10", "due": "2027-01-05", "text": "**Iscrivi la demo al Next Fest**", "note": "Valve"}]}, open(os.path.join(L, "_raw", "steam_events_deadlines.json"), "w"))
json.dump({"matches": [{"name": "Big Show", "plan": True, "deadline": "2026-10-23", "start": "2026-12-01", "url": "https://forms.example.com/a", "next_step": "manda <b>il</b> modulo", "odds": "media"},
                       {"name": "Skip me", "plan": False, "deadline": "2026-10-24"}]}, open(os.path.join(L, "_raw", "promo_events_deadlines.json"), "w"))
today = D(2026, 10, 18)
plan = ps.parse(cal_md)
items = cv.collect(L, plan, {}, today, tt.parse(os.path.join(L, "TODO.md")))
by = lambda s: [x for x in items if s in x["title"]]
assert by("Ondata 2")[0]["state"] == "overdue" and by("Ondata 2")[0]["kind"] == "ondata" and by("Rigioca")[0]["state"] == "done"
assert len(by("Paga Steam Direct")) == 1, "TODO line equal to a step must not be repeated"
assert not any("Pagare Steam Direct" in x["title"] for x in items), "a table row saying the same as a step on the same day is skipped"
assert by("Traduci la pagina")[0]["kind"] == "todo" and by("Traduci la pagina")[0]["owner"] == "claude" and not by("Vecchia voce")
tr = by("Test reale")[0]; assert tr["end"] == "2026-11-13" and tr["kind"] == "gate" and not by("Vecchio GO")
assert by("Tripwire: 100")[0]["kind"] == "tripwire" and by("Da qui ogni lunedì")
assert by("Steam Next Fest feb 2027")[0]["end"] == "2027-03-01" and by("Summer Sale")[0]["kind"] == "evento" and not by("Cooking Fest")
assert by("Scadenza Valve: Iscrivi la demo")[0]["date"] == "2027-01-10"
bs = by("Chiudono le candidature: Big Show")[0]; assert bs["links"] == ["https://forms.example.com/a"] and "&lt;b&gt;" in bs["html"] and "<b>" not in bs["html"]
assert by("In onda: Big Show")[0]["date"] == "2026-12-01" and not by("Skip me")
assert by("Focus group: ondata 1, ondata 2")[0]["state"] == "done" and by("Uscita del gioco") == [] and by("Lancio")[0]["date"] == "2027-05-13"
step8 = by("Candidati a Big Show")[0]; assert 'href="https://forms.example.com/a"' in step8["html"]
assert [x["date"] for x in items] == sorted(x["date"] for x in items)

# ---- roadmap: guessed from steps, then from status.json
rm = cv.roadmap(L, {}, plan, today)
titles = [m["title"] for m in rm["milestones"]]
assert rm["guessed"] and titles[:2] == ["Steam Direct pagato", "Pagina Coming Soon su Steam"] and "Beta gratuita" in titles and "Demo Steam pubblica" in titles and "Uscita" in titles
assert [m["state"] for m in rm["milestones"]][:2] == ["next", "later"]
st = {"roadmap": {"note": "beta itch = demo https://itch.io/x", "milestones": [
    {"date": "2026-10-11", "title": "Rigiocata", "step": 1}, {"date": "2026-10-15", "title": "Ondata", "step": 3},
    {"date": "2026-11-10", "title": "Beta itch", "what": "build corta", "needs": "pagina Steam", "step": 5},
    {"date": "2027-02-22", "end": "2027-03-01", "title": "Next Fest"}, {"title": "1.0 <b>"}]}}
rm = cv.roadmap(L, st, plan, today)
ms = {m["title"]: m for m in rm["milestones"]}
assert ms["Rigiocata"]["state"] == "done" and ms["Ondata"]["state"] == "next" and ms["Ondata"]["late"] and ms["Beta itch"]["state"] == "later" and rm["milestones"][-1]["title"] == "1.0 <b>"
h = cv.roadmap_html(rm, today)
assert "1 di 5 traguardi" in h and "in ritardo" in h and "1.0 &lt;b&gt;" in h and "data da decidere" in h and 'href="#step-5"' in h and 'href="#cal-2026-11-10"' in h and "22 feb → 1 mar 2027" in h
assert 'href="https://itch.io/x"' in h and "rm-list" in h and "rm-chips" in cv.roadmap_html(rm, today, compact=True)

# ---- month grids and JSON payload
items.append(cv.item("2026-10-20", "</script><img src=x onerror=alert(1)>", "passo", "me", today=today))
items[-1]["html"] = ""
page = cv.calendar_html(items, rm, today, D(2027, 5, 13))
months = re.findall(r'<section class="cal-month" data-m="(\d+)"', page)
assert len(months) == 8 and page.count('class="cal-month" data-m="0"') == 1, "October 2026 .. May 2027"
assert 'id="cal-2026-10-18"' in page and re.search(r'class="cal-d today[^"]*" data-d="2026-10-18"', page) and re.search(r'class="cal-d [^"]*late[^"]*" data-d="2026-10-15"', page)
payload = re.search(r'<script type="application/json" id="cal-data">(.*?)</script>', page, re.S).group(1)
assert "</script" not in payload.lower() and "<" not in payload
data = json.loads(payload)
assert data["today"] == "2026-10-18" and any(v["title"].startswith("</script>") for v in data["items"].values())
assert "&lt;/script&gt;" in page and "Prossimi 14 giorni" in page and "In ritardo (1)" in page and "Oggi" in page
assert set(data["days"]["2026-11-10"]) and len(data["days"]["2026-11-13"]) >= 1     # ranges fill every day

# ---- hero: "cosa manca per passare al livello successivo" from the same rules
d = dict(cal={"generated_on": "2026-10-18", "primary": "d90"}, vol=None, metro={"scored_on": "2026-10-18", "metro": {"strength": "utile", "target": "d90"},
         "score": {"p1k": 0.05, "levers": [{"label": "8 lingue", "delta_p1k_pp": 4.3, "p1k_after": .09}, {"label": "Playtest", "delta_p1k_pp": -0.9, "p1k_after": .04}]}},
         metro_plan={"score": {"p1k": 0.40}}, moves=None, comps=None, dossiers=[], today=today, root=L, age=0, stale=False, pred=None)
crit = {"issues": [dict(now=True, severity="alta", label=f"Problema {k}") for k in range(4)]}
hh = mp.hero(d, {}, [dict(wave="9", date="2026-10-18", score="30", _stage="beta")], crit, plan, ("warn", "Giallo"), 40.0)
assert "A rischio" in hh and "Cosa manca per passare al livello successivo" in hh and "Per passare a «Da sistemare prima di spingere»" in hh
assert "da 30,0 ad almeno 40,0 (mancano 10,0 punti)" in hh and "Chiudi almeno 2 problemi gravi su 4" in hh and "8 lingue (+4,3 punti)" in hh and "Playtest" not in hh.split("Cosa manca")[1]
assert "a 90 giorni dall&#x27;uscita" in hh and "nel primo mese" not in hh and "punteggio del 2026-10-18" in hh and "passo in ritardo" in hh
ok = mp.hero(dict(d, metro=None, metro_plan=None), {}, [], {"issues": []}, dict(phases=[]), ("pass", "Verde"), None)
assert "In linea con i dati" in ok and "Cosa manca" not in ok

# ---- metro heading: the scoring date, and the date of the game data when different
assert cb.score_heading("Buffet Panic! (oggi, 2026-10-13)", "2026-10-18") == "Buffet Panic! · punteggio del 2026-10-18 (dati del gioco del 2026-10-13)"
assert cb.score_heading("Gioco", "2026-10-18") == "Gioco · punteggio del 2026-10-18" and cb.score_heading("G (oggi, 2026-10-18)", "2026-10-18") == "G · punteggio del 2026-10-18"

# ---- STATUS.html: header date is the generation date, the analysis date is shown apart; calendar tab and roadmap present
json.dump(dict(st, game="G", updated="2026-10-13"), open(os.path.join(L, "status.json"), "w", encoding="utf-8"))
page = sp.build(L, "private", [], [], set(), today)
assert "Aggiornato il 18 ott 2026 · analisi del 13 ott 2026" in page and 'id="tab-calendario"' in page and "<h2" in page and ">Roadmap</h2>" in page and 'id="cal-data"' in page
assert 'href="https://forms.example.com/a"' in page and 'id="tab-calendario"' not in sp.build(L, "publisher", [], [], set(), today)   # the publisher page has no steps or TODO
assert 'id="tab-calendario"' not in sp.build(L, "partner", [], [], {"calendar"}, today)
print("ALL CALENDAR_LINKS TESTS PASSED")
