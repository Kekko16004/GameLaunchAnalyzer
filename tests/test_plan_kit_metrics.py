"""plan_steps (calendar steps), store_kit (copy-ready pages) and metrics_track (if... then scenarios)."""
import os, sys, json, tempfile, datetime as dt, io, contextlib, csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import plan_steps as ps, store_kit as sk, metrics_track as mt
D = dt.date

# ---------------------------------------------------------------- plan_steps
CAL = """# Calendario
| Quando | Cosa |
|---|---|
| 6 ott | giro |

## ✅ Passi in ordine
🤖 le faccio io (Claude). Quelle segnate 👤 le fai tu
### FASE 1 — Adesso (ottobre)
1. [ ] 👤 **Crea il modulo**: apri `tools/form.md` (~20 min). · 📅 2026-10-20
2. [ ] 👤 **Mandami il link**.
3. [x] 🤖 Lo collego al pulsante Feedback.
### FASE 2 — Novembre
4. [ ] 🤖 Build v0.2 privata (solo con il tuo ok). · 📅 2026-11-10
   nota: serve il passo 1
5. [ ] 👤+🤖 **Pagina itch** in bozza. · 📅 2026-11-12

## Piano B
- altro
"""
plan = ps.parse(CAL); steps = ps.all_steps(plan)
assert [s["n"] for s in steps] == [1, 2, 3, 4, 5] and [s["owner"] for s in steps] == ["me", "me", "claude", "claude", "both"]
assert steps[0]["due"] == "2026-10-20" and "📅" not in steps[0]["text"] and steps[3]["notes"] == ["nota: serve il passo 1"] and steps[2]["done"]
assert plan["before"].startswith("# Calendario") and plan["after"].lstrip().startswith("## Piano B") and len(plan["phases"]) == 2
today = D(2026, 11, 11)
assert ps.status_of(steps[0], today) == "overdue" and ps.status_of(steps[2], today) == "done" and ps.status_of(steps[1], today) == "open"
sm = ps.summary(plan, today); assert (sm["total"], sm["done"], sm["overdue"], sm["me_open"], sm["claude_open"]) == (5, 1, 2, 3, 2), sm
nx = ps.next_steps(plan, "me", 3, today); assert [s["n"] for s in nx][0] == 1 and 5 in [s["n"] for s in nx]
assert any("no date" in p or "without a date" in p for p in ps.check(plan))
d = tempfile.mkdtemp(); p = os.path.join(d, "calendar.md"); open(p, "w", encoding="utf-8").write(CAL)
assert ps.set_done(p, [2, 4], True) == [2, 4] and ps.set_done(p, [2], True) == [] and ps.set_done(p, [2], False) == [2]
assert "[x] 🤖 Build v0.2" in open(p, encoding="utf-8").read() and open(p, encoding="utf-8").read().count("[x]") == 2
print("plan_steps ok")

# ---------------------------------------------------------------- store_kit
kit = {"game": "G", "language": "en", "verified_on": "2026-10-06",
       "steam": {"limits": {"short_description": 60, "tags": 3},
                 "fields": [{"key": "title", "label": "Name", "value": "Buffet Panic"}, {"key": "short_description", "label": "Short", "value": "Cook, panic, survive the dinner rush with friends."}],
                 "long_description": {"format": "bbcode", "blocks": [{"type": "media", "slot": "GIF 1", "what": "the buffet collapses", "file": "launch/media/g1.gif"},
                                                                     {"type": "text", "value": "[h2]About[/h2] text"}]},
                 "tags": [{"tag": "Roguelite", "why": "comps"}, {"tag": "Co-op", "why": "x"}, {"tag": "Cooking", "why": "y"}],
                 "screenshots": [{"order": 1, "what": "gameplay"}, {"order": 2, "what": "boss"}], "capsules": [{"name": "Header", "size": "920x430", "what": "logo + chaos"}],
                 "trailer": {"duration_s": 60}, "settings": [{"label": "Languages", "value": "EN, IT"}], "checklist": ["AI disclosure"]},
       "itch": {"fields": [{"key": "title", "value": "Buffet Panic"}, {"key": "tagline", "value": "A cooking panic"}],
                "long_description": {"format": "markdown", "blocks": [{"type": "text", "value": "# Hi"}]}, "tags": [{"tag": "cooking"}], "screenshots": [], "capsules": [{"name": "Cover", "size": "630x500", "what": "x"}]}}
errs, warns, stats = sk.validate(kit)
assert errs == [] and stats["steam"]["short_description"] == 50 and stats["steam"]["tags"] == 3 and any("placeholders" in w for w in warns), (errs, warns)
bad = json.loads(json.dumps(kit)); bad["steam"]["fields"][1]["value"] = "x" * 61; bad["steam"]["tags"].append({"tag": "Co-op"}); bad["steam"]["screenshots"][1]["order"] = 1
bad["steam"]["long_description"]["blocks"][0]["what"] = ""; e2, _, _ = sk.validate(bad)
assert any("61 characters" in e for e in e2) and any("4 tags" in e for e in e2) and any("duplicated tags" in e for e in e2) and any("duplicated screenshot" in e for e in e2) and any("does not say what" in e for e in e2), e2
asm = sk.assemble(kit["steam"]["long_description"]); assert asm.startswith("<<< GIF 1 · the buffet collapses · file: launch/media/g1.gif >>>") and "[h2]About[/h2]" in asm
md = sk.to_md(kit); assert "## Pagina Steam" in md and "## Pagina itch.io" in md and "Roguelite, Co-op, Cooking" in md and "- [ ] AI disclosure" in md
files = sk.export(kit, os.path.join(d, "kit")); assert any(f.endswith("steam_long_description.bbcode.txt") for f in files) and any(f.endswith("itch_long_description.md") for f in files)
print("store_kit ok:", len(files), "files exported")

# ---------------------------------------------------------------- metrics_track
today = D(2026, 11, 20)
def day(n): return (today - dt.timedelta(days=n)).isoformat()
rows = []
for off, v, dl in ((10, 100, 20), (7, 140, 25), (3, 200, 30), (0, 250, 32)):
    rows += [dict(date=day(off), metric="itch_views", value=v, note=""), dict(date=day(off), metric="itch_downloads", value=dl, note="")]
cont = {"scenarios": [
    {"id": "low-views", "area": "itch", "title": "Few visits in a week", "severity": "ATTENZIONE", "when": "any", "signals": [{"metric": "itch_views", "kind": "gain", "days": 7, "op": "<", "value": 150, "label": "views in 7 days"}],
     "actions": [{"text": "rewrite cover", "owner": "both", "cost": "basso"}], "diagnosis": ["traffic or page?"], "decision": "d", "evidence": "opinion: 20 visits a day is the minimum to read anything"},
    {"id": "no-conversion", "area": "itch", "title": "They arrive but do not download", "severity": "ALARM", "when": "all",
     "signals": [{"metric": "itch_downloads", "kind": "ratio", "of": "itch_views", "op": "<", "value": 0.15, "label": "downloads / views"}, {"metric": "itch_views", "kind": "level", "op": ">=", "value": 200}],
     "actions": [{"text": "fix the page", "owner": "me", "cost": "basso"}], "evidence": "opinion"},
    {"id": "future", "title": "later", "start": "2027-01-01", "signals": [{"metric": "wishlists", "kind": "level", "op": "<", "value": 1}], "actions": [{"text": "x"}], "evidence": "e"},
    {"id": "nodata", "title": "no data", "signals": [{"metric": "demo_players", "kind": "level", "op": "<", "value": 5}], "actions": [{"text": "x"}], "evidence": "e"}]}
res = {r["id"]: r for r in mt.evaluate(cont, rows, today)}
assert res["low-views"]["status"] == "SCATTATO" and res["low-views"]["signals_eval"][0]["value"] == 110, res["low-views"]["signals_eval"]    # 250 - 140 (7 days ago) = 110 < 150
assert res["no-conversion"]["status"] == "SCATTATO" and abs(res["no-conversion"]["signals_eval"][0]["value"] - 0.128) < 0.001
assert res["future"]["status"] == "NON ANCORA" and res["nodata"]["status"] == "SENZA DATI"
text = mt.to_md(list(res.values()), today); assert "SCATTATO · itch · They arrive" in text and "fix the page" in text
assert mt.check(cont, rows) == [] or all("catalog" not in x for x in mt.check(cont, rows))
cont["scenarios"][0]["signals"][0]["metric"] = "itch_vews"; assert any("itch_vews" in x for x in mt.check(cont, rows))
# wishlists csv merged as a metric; CLI add + status exit code 2 on ALARM
wl = os.path.join(d, "wishlists.csv"); open(wl, "w", encoding="utf-8").write("date,wishlists,followers,note\n2026-11-01,100,10,\n2026-11-20,400,40,\n")
assert [r["value"] for r in mt.read_metrics(os.path.join(d, "none.csv"), wl) if r["metric"] == "wishlists"] == [100.0, 400.0]
cj = os.path.join(d, "c.json"); json.dump({"scenarios": cont["scenarios"][1:2]}, open(cj, "w")); mc = os.path.join(d, "m.csv")
def run(argv):
    sys.argv = ["x", "--csv", mc, "--wishlists-csv", os.path.join(d, "none.csv"), "--contingencies", cj, "--today", today.isoformat()] + argv
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()): mt.main()
for off, v, dl in ((10, 100, 20), (0, 250, 32)):
    run(["add", "--metric", "itch_views", "--value", str(v), "--date", day(off)]); run(["add", "--metric", "itch_downloads", "--value", str(dl), "--date", day(off)])
run(["add", "--metric", "itch_views", "--value", "260", "--date", day(0)])   # same day replaces
assert len(list(csv.DictReader(open(mc, encoding="utf-8-sig")))) == 4
try: run(["status"]); raise AssertionError("ALARM scenario must exit with code 2")
except SystemExit as e: assert e.code == 2, e.code
print("metrics_track ok: ALARM scenario exits with code 2")
print("ALL PLAN/KIT/METRICS TESTS PASSED")
