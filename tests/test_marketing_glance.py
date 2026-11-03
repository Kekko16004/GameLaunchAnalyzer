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
assert re.search(r"TikTok</span><span class=\"spill prog\"><i aria-hidden=\"true\"></i>Da collegare", mk) and "Non usare per ora" in mk and "Pagina Steam" in mk
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
print("ALL MARKETING_GLANCE TESTS PASSED")
