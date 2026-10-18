"""steam_events.py: parsing Valve's events page and an edition page (synthetic fixtures), fallback when the page fails or
changes layout, merge with the curated data, window.csv export without duplicates (hand rows kept), launch_window auto
feed, deadlines (Next Fest choice, matching themed fests, estimated deadlines, sale warnings), calendar.md / TODO.md
written once with valid formats, top_moves 'fest' move, cp1252 console. No network."""
import os, sys, csv, json, shutil, tempfile, subprocess, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import common
FX = os.path.join(HERE, "fixtures")
PAGES = {"https://partner.steamgames.com/doc/marketing/upcoming_events": open(os.path.join(FX, "steam_events_upcoming.html"), encoding="utf-8").read(),
         "https://partner.steamgames.com/doc/marketing/upcoming_events/nextfest/feb_2027": open(os.path.join(FX, "steam_events_nextfest.html"), encoding="utf-8").read()}
calls = []
def fake_get(url, **k):
    calls.append(url)
    if url in PAGES:
        return PAGES[url].encode("utf-8")
    raise OSError("offline test: " + url)
common.http_get = fake_get
import steam_events as se, plan_steps as ps, todo_track as tt, top_moves as tm, launch_window as lw
D = dt.date

# ---- parsing
live = se.parse_page(PAGES["https://partner.steamgames.com/doc/marketing/upcoming_events"])
by = {e["key"]: e for e in live}
assert by["winter_sale_2026"]["start"] == "2026-12-17" and by["winter_sale_2026"]["end"] == "2027-01-04" and by["winter_sale_2026"]["kind"] == "seasonal_sale"
assert by["autumn_sale_2027"]["start"] is None and by["autumn_sale_2027"]["status"] == "DA VERIFICARE"          # TBD never becomes a date
assert by["physics_party_2026"]["start"] == "2026-12-28" and by["physics_party_2026"]["end"] == "2027-01-03"     # across the new year
assert "<b>" in by["physics_party_2026"]["matters_for"] and by["physics_party_2026"]["match"] == ["physics party"]  # text unescaped as data, theme words
assert by["couch_coop_2027"]["start"] == "2027-02-08" and by["racing_2027"]["optin"].endswith("racing_2027")
nf = [e for e in live if e["kind"] == "next_fest"]
assert [(e["start"], e["end"]) for e in nf] == [("2026-10-19", "2026-10-26"), ("2027-02-22", "2027-03-01"), ("2027-06-14", "2027-06-21")], nf
ed = se.parse_nextfest_edition(PAGES["https://partner.steamgames.com/doc/marketing/upcoming_events/nextfest/feb_2027"])
assert ed["registration_deadline"] == "2027-01-10" and ["2027-01-18", "Steam pulls trailers for the official Next Fest trailer."] in ed["milestones"]
assert any(d == "2027-03-01" for d, _ in ed["milestones"]) and any(d == "2026-12-08" for d, _ in ed["milestones"])

# ---- merge with the curated fallback
fb = se.load_fallback()
assert all(e["kind"] in se.KINDS for e in fb["events"]) and fb["read_on"]
for e in fb["events"]:
    assert (e["start"] is None) == (e["status"] == "DA VERIFICARE"), e["key"]          # no invented days
    if e["start"] is None:
        assert e.get("pattern"), e["key"]
m = {e["key"]: e for e in se.merge(live, fb["events"])}
assert "local co-op" in m["couch_coop_2027"]["match"] and m["nextfest_june_2027"]["registration_deadline"] == "2027-04-25"   # curated details added
assert m["winter_sale_2027"].get("origin") == "fallback" and m["winter_sale_2027"]["start"] is None                       # pattern items kept
assert "di solito" in m["autumn_sale_2027"]["pattern"]

# ---- fetch: live, then broken page -> fallback
data = se.fetch(rate=0, today=D(2026, 10, 17))
assert data["parser"] == "live" and data["read_on"] == "2026-10-17"
f = {e["key"]: e for e in data["events"]}
assert f["nextfest_feb_2027"]["registration_deadline"] == "2027-01-10" and f["nextfest_feb_2027"]["milestones"][0][0] == "2027-01-10"   # curated Italian wording kept
assert any("nextfest/feb_2027" in c for c in calls)
saved = PAGES["https://partner.steamgames.com/doc/marketing/upcoming_events"]
PAGES["https://partner.steamgames.com/doc/marketing/upcoming_events"] = "<html>new layout</html>"
assert se.fetch(rate=0)["parser"] == "fallback"
del PAGES["https://partner.steamgames.com/doc/marketing/upcoming_events"]
assert se.fetch(rate=0)["parser"] == "fallback"
PAGES["https://partner.steamgames.com/doc/marketing/upcoming_events"] = saved
assert se.diff(dict(events=[dict(key="summer_sale_2027", start="2027-06-25", end="2027-07-08", registration_deadline=None)]), data) and any(x.startswith("cambiato: Steam Summer") for x in se.diff(dict(events=[dict(key="summer_sale_2027", start="2027-06-25", end="2027-07-08", registration_deadline=None)]), data))

# ---- window.csv: weekly rows, hand rows kept, no duplicates on re-run
d = tempfile.mkdtemp(); ev = os.path.join(d, "steam_events.json"); common.write_json(data, ev)
win = os.path.join(d, "window.csv")
with open(win, "w", encoding="utf-8", newline="") as fh:
    fh.write("date,name,kind,weight,source,note\n2027-03-09,Big Co,big_release,5,steamdb upcoming,\n2027-06-24,Steam Summer Sale 2027,sale,3,my note,\n")
r1 = se.export_window(se.load(ev), win); r2 = se.export_window(se.load(ev), win)
rows = list(csv.DictReader(open(win, encoding="utf-8-sig")))
assert r1["written"] == r2["written"] and len(rows) == r2["written"] + 2, (r1, r2, len(rows))
assert sum(1 for r in rows if r["name"] == "Steam Summer Sale 2027") == 1 and any(r["name"] == "Big Co" for r in rows)       # the hand row wins
summer = [r for r in rows if r["name"].startswith("Steam Summer Sale 2027")]
assert [r["date"] for r in summer] == ["2027-06-24", "2027-07-01", "2027-07-08"], summer                                     # one row per week, end included
assert all(r["kind"] in lw.KINDS for r in rows) and "Steam Autumn Sale 2027" in r2["not_dated"]
nfrow = next(r for r in rows if r["name"] == "Steam Next Fest febbraio 2027"); assert nfrow["kind"] == "festival" and nfrow["weight"] == "4"

# ---- launch_window counts Steam's events automatically, once
items = se.window_items(ev)
assert any(i["name"] == "Steam Spring Sale 2027" and i["weight"] == 4.0 for i in items)
res = lw.analyse(lw.dedupe(lw.read_window(win)[0] + items), D(2027, 3, 18), D(2027, 2, 1), D(2027, 5, 31))
assert res["chosen"]["verdict"] in ("affollata", "nella media") and res["chosen"]["score"] >= 4, res["chosen"]
assert len(lw.dedupe(lw.read_window(win)[0] + items)) < len(lw.read_window(win)[0]) + len(items)        # same rows in window.csv: counted once
r = subprocess.run([sys.executable, os.path.join(R, "launch_window.py"), "plan", "--launch", "2027-03-22", "--from", "2027-02-01", "--to", "2027-05-31", "--watchlist", os.path.join(d, "none.csv"),
                    "--csv", os.path.join(d, "none2.csv"), "--steam-events", ev, "--today", "2026-10-17"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
assert r.returncode == 0 and "Spring Sale" in r.stdout.decode("utf-8") and "steam_events.py" in r.stdout.decode("utf-8"), r.stderr.decode("utf-8", "replace")

# ---- deadlines for a game
tags = ["Roguelite", "Physics", "Comedy", "Food", "Singleplayer"]
p = se.plan(data, D(2026, 10, 17), D(2027, 5, 13), tags, demo=True, local_coop=False, next_fest=None)
assert p["next_fest_chosen"] == "nextfest_feb_2027" and [n["key"] for n in p["next_fests"]] == ["nextfest_feb_2027"]    # Oct 2026 is running, June is after launch
reg = next(s for s in p["steps"] if s["key"] == "nextfest_feb_2027:reg"); assert reg["deadline"] == "2027-01-10" and reg["due"] == "2027-01-05" and reg["who"] == "👤"
assert not any("opt OUT" in s["text"] or "concludes" in s["text"].lower() for s in p["steps"])
keys = {f["key"] for f in p["themed_fests"]}
assert "physics_party_2026" in keys and "couch_coop_2027" not in keys and "racing_2027" not in keys, keys                  # theme match, no local co-op
pp = next(s for s in p["steps"] if s["key"] == "physics_party_2026:reg"); assert pp["estimated"] and pp["deadline"] == "2026-11-16" and "DA VERIFICARE" in pp["note"]
assert any(s["key"] == "cooking_2027:watch" for s in p["steps"])                                                            # unpublished fest: a check, not a date
assert any(w["level"] == "INFO" and "2027-05-25" in w["text"] for w in p["warnings"])                                      # 30-day rule for the Summer Sale
bad = se.plan(data, D(2026, 10, 17), D(2027, 3, 20), tags, True, False, None)
assert any(w["level"] == "ALARM" and "Spring Sale" in w["text"] for w in bad["warnings"])
late = se.plan(data, D(2026, 10, 17), D(2027, 6, 1), tags, True, False, None)
assert any(w["level"] == "WARN" and "NON puoi" in w["text"] for w in late["warnings"]) and late["next_fest_chosen"] == "nextfest_feb_2027"
coop = se.plan(data, D(2026, 10, 17), D(2027, 5, 13), tags + ["Local Co-Op"], True, True, "nextfest_feb_2027")
assert "couch_coop_2027" in {f["key"] for f in coop["themed_fests"]}

# ---- calendar.md and TODO.md: written once, formats valid
L = os.path.join(d, "launch"); os.makedirs(L)
open(os.path.join(L, "calendar.md"), "w", encoding="utf-8").write("# Cal\n\n## ✅ Passi in ordine\n🤖 = io · 👤 = tu\n### FASE 1 — Adesso\n1. [ ] 👤 **Iscrivi la demo al Next Fest** di febbraio. Scadenza Valve 2027-01-10. · 📅 2027-01-05\n2. [ ] 👤 **Carica il trailer** per il video ufficiale del fest. Scadenza Valve 2027-01-18. · 📅 2027-01-15\n\n## Altro\ntesto\n")
open(os.path.join(L, "TODO.md"), "w", encoding="utf-8").write("# TODO\nAggiornato: 2026-10-01\n\n## Burocrazia e release\n- [ ] 👤 **Iscrizione al Next Fest di febbraio** — 2027-01-05 — 1 h — demo — conferma\n")
shutil.copy(os.path.join(R, "..", "..", "tests", "fixtures", "steam_events_upcoming.html"), os.path.join(d, "x.html"))   # (fixture still readable)
def deadlines(*extra):
    return subprocess.run([sys.executable, os.path.join(R, "steam_events.py"), "deadlines", "--events", ev, "--launch-dir", L, "--launch", "2027-05-13", "--tags", ",".join(tags), "--today", "2026-10-17"] + list(extra),
                          capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
r = deadlines("--dry-run"); assert r.returncode == 0 and "dry run" in r.stdout.decode("utf-8"), r.stderr.decode("utf-8", "replace")
assert "Iscrivi la demo allo" not in open(os.path.join(L, "calendar.md"), encoding="utf-8").read()
r = deadlines(); assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
cal1 = open(os.path.join(L, "calendar.md"), encoding="utf-8").read(); todo1 = open(os.path.join(L, "TODO.md"), encoding="utf-8").read()
plan_ = ps.parse(cal1)
assert not ps.check(plan_) or all("data" not in c for c in ps.check(plan_)), ps.check(plan_)
assert "### 📆 Eventi Steam" in cal1 and cal1.index("### 📆 Eventi Steam") < cal1.index("## Altro")
assert "Iscriviti al Physics Party Fest" in cal1 and cal1.count("2027-01-10") == 1 and cal1.count("2027-01-18") == 1        # hand-written steps not duplicated
assert "Iscrizione al Next Fest di febbraio" in todo1 and todo1.count("2027-01-10") == 0 and "Physics Party Fest" in todo1
nums = [s["n"] for s in ps.all_steps(plan_)]; assert len(nums) == len(set(nums)) and nums[:2] == [1, 2]
assert tt.parse(os.path.join(L, "TODO.md"))["items"] and os.path.exists(os.path.join(L, "steam-events.md")) and os.path.exists(os.path.join(L, "_raw", "steam_events_deadlines.json"))
r = deadlines(); assert r.returncode == 0
assert open(os.path.join(L, "calendar.md"), encoding="utf-8").read() == cal1 and open(os.path.join(L, "TODO.md"), encoding="utf-8").read() == todo1   # idempotent
md = open(os.path.join(L, "steam-events.md"), encoding="utf-8").read(); assert "[DA VERIFICARE]" in md and "Steam Summer Sale 2027" in md
# undated "watch" steps get a due date relative to the run day: a run on the next day must not add a copy (bug seen on a real calendar)
watch = dict(event="Cooking Fest 2027", deadline=None, due="2026-11-15", text="**Controlla se Valve ha annunciato il Cooking Fest 2027** (tema: food)")
seen = "73. [ ] 👤+🤖 **controlla se valve ha annunciato il cooking fest 2027** (tema compatibile). · 📅 2026-11-14"
assert se._already_line(seen, watch) and se._already_line("- [ ] 👤+🤖 **controlla se valve ha annunciato il cooking fest 2027** — 2026-11-14", watch)
assert not se._already_line("controlla se valve ha annunciato il cooking fest 2027 (testo libero, non un passo)", watch)
assert not se._already_line(seen, dict(watch, deadline="2027-03-01", due="2027-02-20"))     # dated steps still need their date

# ---- top_moves proposes "register for fest X by date Y" near the deadline
c = [x for x in tm.candidates(L, D(2026, 10, 30), None) if x["source"] == "fest"]
assert c and c[0]["title"].startswith("Iscriviti a Physics Party Fest entro il 2026-11-16") and c[0]["score"] == 50, c
c2 = [x for x in tm.candidates(L, D(2026, 12, 20), None) if x["source"] == "fest"]
assert any("Next Fest" in x["title"] and x["score"] == 50 for x in c2) and not any("Physics" in x["title"] for x in c2)       # past deadlines are not proposed
assert not any(x["source"] == "todo" and "2027-01-10" in x.get("why", "") for x in tm.candidates(L, D(2027, 1, 2), None))
print("ALL STEAM_EVENTS TESTS PASSED")
