"""Marketing e social tab: at a glance on top (moves, channels, numbers vs cases, flop traffic light), the rest folded; plain words; theme saved."""
import os, sys, json, tempfile, datetime as dt, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
os.environ["GLS_HOME"] = tempfile.mkdtemp()  # never read the user's real calibration or keys
import status_page as sp
import marketing_glance as mg

L = tempfile.mkdtemp(); os.makedirs(os.path.join(L, "_raw"))
J = lambda obj, *p: json.dump(obj, open(os.path.join(L, *p), "w", encoding="utf-8"), ensure_ascii=False)
HOSTILE = "<img src=x onerror=alert(1)>"
open(os.path.join(L, "calendar.md"), "w", encoding="utf-8").write("""# Calendario
## ✅ Passi in ordine
### FASE 1 — Adesso
1. [ ] 👤 **Iscriviti al Next Fest** · 📅 2026-11-15
2. [ ] 🤖 **Prepara il trailer** · 📅 2027-01-11
3. [ ] 👤 **Registra la clip C01** · 📅 2026-11-01
""")
J({"computed_on": "2026-10-30", "moves": [
    {"key": "trailer", "title": "Trailer pubblicato (i B vincenti: circa 128 giorni prima dell'uscita)", "why": "c'è nel 84 % dei B vincenti e nel 33 % dei perdenti (n = 31 / 21, dati del 2026-10-18)",
     "hours": "10-20 h", "owner": "👤+🤖", "due": None, "match": ["trailer"]},
    {"key": "next_fest", "title": "Steam Next Fest", "why": "c'è nel 51 % dei B vincenti e nel 7 % dei perdenti", "hours": "4-8 h", "owner": "👤", "due": None, "match": ["next fest"]},
    {"key": "todo-40", "title": "Leggi a mano le regole di 5 [subreddit](07-community.md) (07-community.md §1)", "why": "scade il 2026-11-02", "hours": "0,5 h", "owner": "👤", "due": "2026-11-02", "match": []}]},
  "_raw", "top_moves.json")
J({"game": "G", "steam_url": None, "page_live": None, "itch_live": None,
   "reddit": [{"sub": "r/IndieDev", "flair": "[DA VERIFICARE nella sidebar]", "cooldown_days": 7, "rules_check": ["Titolo in prima persona " + HOSTILE]}], "clips": []}, "clips.json")
J({"generated_on": "2026-10-28", "kits": [{"week": "2026-11-02", "posts": [
    {"kind": "video", "clip": "C01", "title": "Il Runner cieco", "status": "todo", "hooks": ["Your friend is your camera " + HOSTILE, "Riserva"], "use_hook": 0, "caption": "c",
     "slots": [{"platform": "tiktok", "date": "2026-11-02", "time": "18:30"}, {"platform": "instagram", "date": "2026-11-04", "time": "19:00"}]}]}]}, "_raw", "social_kit.json")
J({"game": "G", "verified_on": "2026-10-28", "steam": {"fields": [{"key": "title", "value": "G"}],
   "long_description": {"format": "bbcode", "blocks": [{"type": "text", "value": "x" * 1800}]},
   "settings": [{"label": "Languages (interface)", "value": "English, Italian"}]}, "itch": {"fields": [{"key": "title", "value": "G"}]}}, "store_kit.json")
J({"start": "2027-01-26", "launch": "2027-09-14", "targets": {"base": 4000},
   "tripwires": [{"date": "2027-04-25", "min_wishlists": 300, "label": "iscrizione al Next Fest", "emergency": "4 settimane di clip"},
                 {"date": "2027-06-13", "min_wishlists": 700, "label": "ingresso nel Next Fest", "emergency": "creator"}], "events": []}, "_raw", "wl_plan.json")
J({"FC01": True}, "_raw", "flopcheck_answers.json")

today = dt.date(2026, 11, 3)
page = sp.build(L, "private", [], [], set(), today)
mk = re.search(r'<section role="tabpanel" id="p-marketing".*?</section>(?=<section role="tabpanel"|<footer)', page, re.S).group(0)

# tab and order: at a glance before everything else
assert ">Marketing e social<" in page and ("A colpo d&#x27;occhio" in mk or "A colpo d'occhio" in mk)
for h in ("Cosa fare adesso", "Canali", "I nostri numeri contro i casi reali", "Perché i giochi floppano: il nostro controllo"):
    assert h in mk, h
i0 = mk.index("Cosa fare adesso"); assert i0 < mk.index("Pagine store: scheda copiabile", i0) < mk.index("Prove e fonti", i0)
# 3 moves with owner and deadline (taken from the matching step when the move has none), in everyday words
assert mk.count('<span class="mv-n">') == 3 and "👤+🤖 Insieme" in mk and "entro il 11 gen 2027" in mk and "entro il 15 nov 2026" in mk and "scaduta da 1 g" in mk
assert "Lo ha fatto il 84 % dei giochi simili andati bene" in mk and "circa 128 giorni prima" in mk and "07-community.md" not in mk.split("I nostri numeri")[0]
# channels
assert re.search(r"TikTok</span><span class=\"spill todo\"><i aria-hidden=\"true\"></i>Da collegare", mk) and "Non usare per ora" in mk and "Pagina Steam" in mk
# numbers against the cases, with a reading line for the meters
assert "Descrizione Steam" in mk and "1.800 caratteri" in mk and "Sopra i successi" in mk and "Lingue della pagina" in mk and "Come i flop" in mk
assert "Da misurare" in mk and "Prossima soglia" in mk and 'class="meter"' in mk and "Come si legge:" in mk
# flop traffic light: answers and facts from the plan, one action per item, no technical keys
fc = mg.flop(L, mg.__dict__.get("_db") or __import__("social_content").load_db(), today, None)
st = {x["id"]: x["status"] for x in fc["items"]}
assert st["FC01"] == "ok" and st["FC10"] == "fail" and st["FC05"] == "ok" and st["FC03"] == "ok"
assert "Da sistemare" in mk and "Superato" in mk and "Da verificare" in mk and "lingue: 2, serve almeno 5" in mk and "languages =" not in mk
assert mk.count('<li class="fl ') == len(fc["items"]) and mk.count("<strong>Azione:</strong>") == len(fc["items"])
# the rest is folded, nothing lost
for h in ("Pagine store: scheda copiabile", "Kit social della settimana", "Piano social, settimana per settimana", "Ganci: i testi dei primi 2 secondi", "Regole dei subreddit", "Prove e fonti", "Casi reali collegati"):
    assert re.search(r'<details class="fold"[^>]*><summary><h2[^>]*>' + re.escape(h), mk), h
assert "flair: da verificare" in mk and "Di riserva" in mk
# plain words: no file keys or commands in the tab
for tech in ("store_kit.json", "social_kit.py", "social_content.py", "track add", "social-kit/kit-"):
    assert tech not in mk, tech
# escaping
assert "<img src=x" not in mk and "&lt;img src=x onerror=alert(1)&gt;" in mk
# theme saved, print opens the folds, one file without external resources
assert "gls-theme" in page and "beforeprint" in page and "@media print" in page and "<script src" not in page and "<link " not in page
assert 'content:"Come si legge: "' in page
# publisher: no marketing glance
pub = sp.build(L, "publisher", [], [], set(), today)
assert "Cosa fare adesso" not in pub and "Perché i giochi floppano" not in pub
# without marketing data the tab is the old one (no glance)
E = tempfile.mkdtemp()
assert mg.glance(E, {"phases": []}, today, None) is None
# ---- one palette for the whole page: da fare grey, in corso orange, fatto green, red only for late / problems
css = page[page.index("<style"):page.index("</style>")]
assert 'stroke="var(--crit)"' not in sp.ICONS["pending"][0] and 'stroke="var(--muted)"' in sp.ICONS["pending"][0]          # "Da fare" icon is grey
assert ".spill.todo i{border:2px solid var(--muted)" in css and ".spill.todo i{border:2px solid var(--crit)" not in css
assert ".tabs .cnt{border:0;background:var(--surface2)" in css and ".tabs .cnt.late{background:var(--crit)" in css           # open count grey, late count red
assert "var(--warn)" in sp.ICONS["warn"][0] and "var(--good)" in sp.ICONS["pass"][0] and "var(--crit)" in sp.ICONS["fail"][0]
assert "--o-me:#e5732f" not in page and "--o-both:#159a6c" not in page                                                      # owner colours are not status colours
import criticita as cr_
assert cr_.OWNER["aperto"][0] == "mute" and cr_.OWNER["in_lavorazione"][0] == "warn" and cr_.UNDECIDED[0] == "mute"
mk_todo = mk[mk.index("Perché i giochi floppano"):]
assert 'spill todo' in mk_todo and 'spill bad' in mk_todo                                                                  # da verificare grey, da sistemare red

# ---- the plan with Reels and X: they are no longer "non usare"; the plan is shown week by week with the A/B texts
J({"generated_on": "2026-11-03", "start": "2026-11-09", "weeks": 2, "per_week": {"tiktok": 1, "instagram": 2, "x": 2}, "posts": [
    {"date": "2026-11-10", "platform": "instagram", "moment": "H1", "moment_label": "Il Runner cieco", "hook_a": "Reel A " + HOSTILE, "hook_b": "Reel B", "caption": "c", "cta": "Follow", "length": "15-30 s"},
    {"date": "2026-11-11", "platform": "x", "moment": "H1", "moment_label": "Il Runner cieco", "hook_a": "X A", "hook_b": "X B", "caption": "c", "cta": "Follow", "length": "30-60 s"}]}, "_raw", "social_plan.json")
page2 = sp.build(L, "private", [], [], set(), today)
mk2 = re.search(r'<section role="tabpanel" id="p-marketing".*?</section>(?=<section role="tabpanel"|<footer)', page2, re.S).group(0)
assert not re.search(r"X \(Twitter\)</span><span class=\"spill off\"", mk2) and re.search(r"X \(Twitter\)</span><span class=\"spill off\"", mk)   # X: from \"non usare\" to planned
assert re.search(r"Instagram Reels</span><span class=\"spill todo\"><i aria-hidden=\"true\"></i>Da collegare", mk2) and re.search(r"X \(Twitter\)</span><span class=\"spill todo\"><i aria-hidden=\"true\"></i>Da collegare", mk2)
assert "Settimana del 9 nov 2026" in mk2 and "X A" in mk2 and "Reel B" in mk2 and "<img src=x" not in mk2
os.remove(os.path.join(L, "_raw", "social_plan.json"))

# ---- flop answers with a reason: ok / fail / na (not applicable yet), na is left out of the risk and never goes to top_moves
import social_content as sc_
db_ = sc_.load_db()
ans = {"FC01": {"status": "na", "why": "il trailer non esiste ancora " + HOSTILE, "proof": "launch/store_kit.json", "action": "Girarlo dopo la demo"},
       "FC02": {"status": "fail", "why": "tre giocatori esatti, nicchia nella nicchia", "proof": "launch/02-market.md", "action": "Posiziona come party co-op con amici"},
       "FC04": {"status": "ok", "why": "pitch capito da 53 su 54", "proof": "launch/fg/waves/w03-report.md"}, "FC06": False, "FC08": "na"}
fc2 = sc_.flopcheck(db_, {}, ans)
by = {x["id"]: x for x in fc2["items"]}
assert by["FC01"]["status"] == "na" and by["FC02"]["status"] == "fail" and by["FC04"]["status"] == "ok" and by["FC06"]["status"] == "fail" and by["FC08"]["status"] == "na"
assert fc2["na"] == 2 and fc2["judged"] == 3 and fc2["todo"] == 10
w = lambda i: by[i]["weight"]
assert fc2["risk"] == round((w("FC02") + w("FC06")) / (w("FC02") + w("FC04") + w("FC06")), 2)          # na is not in the weight judged
assert fc2["top_fixes"][0]["fix"] == "Posiziona come party co-op con amici"                              # the custom action wins over the generic fix
assert "non applicabile ancora" in sc_.flopcheck_md(fc2)
assert sc_.answer_status(True) == "ok" and sc_.answer_status(False) == "fail" and sc_.answer_status("N/A") == "na" and sc_.answer_status(None) is None and sc_.answer_status({"status": "ok"}) == "ok"
J(ans, "_raw", "flopcheck_answers.json")
import time; time.sleep(1.1)
page3 = sp.build(L, "private", [], [], set(), today)
mk3 = re.search(r'<section role="tabpanel" id="p-marketing".*?</section>(?=<section role="tabpanel"|<footer)', page3, re.S).group(0)
assert "Non applicabile ancora" in mk3 and "1 non applicabili ancora" not in mk3 and "2 non applicabili ancora" in mk3
assert "<strong>Motivo:</strong> tre giocatori esatti" in mk3 and "Prova: launch/02-market.md" in mk3 and "Posiziona come party co-op con amici" in mk3
assert "il trailer non esiste ancora &lt;img src=x" in mk3 and "<img src=x" not in mk3                       # reasons are escaped
assert mk3.index("Da sistemare") < mk3.index("Superato") < mk3.index("Non applicabile ancora")             # failed first, n/a last
assert mk3.count('<li class="fl ') == len(fc2["items"])
# top_moves: only the failed items, heaviest first, with the custom action; n/a never
import top_moves as tm_
json.dump(fc2, open(os.path.join(L, "_raw", "flopcheck.json"), "w", encoding="utf-8"), ensure_ascii=False)
cand = [m for m in tm_.candidates(L, today, None) if m["key"].startswith("flopcheck-")]
assert [m["key"] for m in cand] == ["flopcheck-FC02", "flopcheck-FC06"], cand                          # failed only, FC01 / FC08 (n/a) never
assert cand[0]["title"] == "Sistema: Posiziona come party co-op con amici" and "tre giocatori esatti" in cand[0]["why"]
# ---- plan from the clip registry with Reels and X: own hooks only, X without hashtags, a clip only where it is made for
J({"game": "G", "clips": [
    {"id": "C01", "title": "Il Runner cieco", "priority": 1, "status": "todo", "platforms": ["tiktok", "youtube_shorts", "instagram", "reddit"], "hooks": ["Own A", "Own B", "Own C"], "caption": "Cap #indiegame #coop"},
    {"id": "C08", "title": "Cadere in diretta", "priority": 2, "status": "todo", "platforms": ["tiktok", "youtube_shorts", "instagram"], "hooks": ["Fall A", "Fall B"], "caption": "Fall cap"},
    {"id": "C99", "title": "Vecchia", "priority": 3, "status": "retired", "platforms": ["tiktok"], "hooks": ["x", "y"], "caption": "z"}]}, "clips_reg.json")
ms_ = sc_.moments_from_registry(os.path.join(L, "clips_reg.json"))
assert [m["id"] for m in ms_] == ["C01", "C08"] and ms_[0]["score"] > ms_[1]["score"] and ms_[0]["hooks"][0] == ["Own A", "Cap #indiegame #coop"]
pl_ = sc_.plan(db_, ms_, dt.date(2026, 11, 9), 2, {"instagram": 4, "x": 3, "tiktok": 2, "reddit": 1}, None, game="G", note="Reels e X pesano di più")
cnt_ = {p_: sum(1 for x in pl_["posts"] if x["platform"] == p_) for p_ in ("instagram", "x", "tiktok", "reddit")}
assert cnt_ == {"instagram": 8, "x": 6, "tiktok": 4, "reddit": 2} and cnt_["tiktok"] < cnt_["instagram"] and cnt_["tiktok"] < cnt_["x"]
assert all(x["hook_a"] in ("Own A", "Own B", "Own C", "Fall A", "Fall B") and x["hook_b"] in ("Own A", "Own B", "Own C", "Fall A", "Fall B") for x in pl_["posts"])   # no generic hooks
assert all("#" not in x["caption"] for x in pl_["posts"] if x["platform"] == "x") and all(x["moment"] == "C01" for x in pl_["posts"] if x["platform"] == "reddit")   # C08 is not made for Reddit
print("ALL MARKETING_GLANCE TESTS PASSED")
# facts read from the launch folder (store text, languages, release timing)
facts_, auto_ = sc_.launch_facts(L)
assert facts_["languages"] == 2 and facts_["desc_chars"] == 1800 and auto_["FC03"]["status"] == "ok"
print("ALL MARKETING_GLANCE TESTS PASSED (page + facts)")
