"""status_page with every section: steps, store kit with copy buttons, contingencies, watchlist, intentions; escaping; audiences."""
import os, sys, json, tempfile, datetime as dt, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
os.environ["GLS_HOME"] = tempfile.mkdtemp()  # never read the user's real calibration or keys
import status_page as sp

L = tempfile.mkdtemp(); os.makedirs(os.path.join(L, "_raw"))
W = lambda name, text: open(os.path.join(L, name), "w", encoding="utf-8").write(text)
HOSTILE = "<img src=x onerror=alert(1)>"
W("calendar.md", f"""# Calendar
| Quando | Cosa |
|---|---|
| 6 ott | giro {HOSTILE} |

## ✅ Passi in ordine
🤖 le faccio io (Claude). Quelle segnate 👤 le fai tu
### FASE 1 — Adesso
1. [x] 👤 **Crea il modulo**: apri `tools/form.md`. · 📅 2026-10-20
2. [ ] 👤 **Manda il link**. · 📅 2026-10-22
3. [ ] 🤖 Lo collego al pulsante (solo con il tuo ok).
### FASE 2 — Dopo
4. [ ] 👤+🤖 **Pagina itch** in bozza {HOSTILE} · 📅 2026-12-10

## Piano B
- altro
""")
json.dump({"game": HOSTILE, "verdict": {"color": "giallo", "summary": "s", "risks": ["r"]}, "gates": {"A": {"state": "fail", "note": "n"}},
           "intentions": {"summary": f"obiettivo {HOSTILE}", "decisions": [{"topic": "Budget", "choice": "100", "why": "x"}]}}, open(os.path.join(L, "status.json"), "w"))
json.dump({"game": "G", "verified_on": "2026-10-06",
           "steam": {"limits": {"short_description": 20}, "fields": [{"key": "title", "label": "Nome", "value": "Buffet"}, {"key": "short_description", "label": "Breve", "value": "x" * 25 + "</textarea>\"'"}],
                     "long_description": {"format": "bbcode", "blocks": [{"type": "media", "slot": "GIF 1", "what": "il crollo", "file": "a.gif"}, {"type": "text", "value": "[h2]About[/h2]"}]},
                     "tags": [{"tag": "Roguelite", "why": "w"}], "screenshots": [{"order": 1, "what": "gameplay"}], "capsules": [{"name": "Header", "size": "920x430", "what": "x"}], "checklist": ["AI"]},
           "itch": {"fields": [{"key": "title", "value": "Buffet"}, {"key": "tagline", "value": "t"}], "long_description": {"format": "markdown", "blocks": [{"type": "text", "value": "# Hi"}]}, "tags": [{"tag": "co-op"}]}}, open(os.path.join(L, "store_kit.json"), "w"))
json.dump({"scenarios": [{"id": "a", "area": "itch beta", "title": "Pochi arrivi", "severity": "ALARM", "signals": [{"metric": "itch_views", "kind": "level", "op": "<", "value": 100, "label": "visite"}],
           "diagnosis": ["d"], "actions": [{"text": "cover", "owner": "both", "cost": "basso"}], "decision": "dec", "evidence": "opinione"}]}, open(os.path.join(L, "_raw", "contingencies.json"), "w"))
W("metrics.csv", "date,metric,value,note\n2026-11-20,itch_views,40,\n")
W("watchlist.csv", "date,appid,name,role,reviews_total,reviews_positive,pct_positive,price_cents,discount_pct,players,coming_soon,release_date\n2026-11-20,1,Rival,competitor,0,0,,1499,0,,1,2027-03-05\n")
json.dump({"launch": "2027-03-01", "targets": {}, "tripwires": [], "events": []}, open(os.path.join(L, "_raw", "wl_plan.json"), "w"))

today = dt.date(2026, 11, 25)
page = sp.build(L, "partner", [], [], set(), today)
body = page.replace("<script>" + sp.JS + "</script>", "")
assert "<img src=x" not in body and "onerror=alert" not in body.replace("&lt;img src=x onerror=alert(1)&gt;", "").replace(r"\u0026lt;img src=x onerror=alert(1)\u0026gt;", ""), "hostile markup leaked"
# calendar data embedded as JSON: no "<" can close the script, and the HTML of every item is escaped
cal = json.loads(re.search(r'<script type="application/json" id="cal-data">(.*?)</script>', page, re.S).group(1))
assert all("<img" not in it["html"] and "<img" not in __import__("html").escape(it["title"]) for it in cal["items"].values()) and "2026-12-10" in cal["days"]
assert 'id="step-4"' in page and 'aria-controls="p-calendario"' in page
assert page.count('class="step"') == 4 and 'data-owner="both"' in page and "In ritardo" in page and "Tocca a te</h3>" in page and "<h2 id=\"sec" in page and "1 di 4" in page
assert page.count("button type=\"button\" class=\"copy\"") >= 5 and "Oltre il limite" in page and "📷" in page and "il crollo" in page
copy = re.findall(r'data-copy="([^"]*)"', page); assert any("&lt;&lt;&lt; GIF 1" in c or "<<< GIF 1" in html_unescaped for c in copy for html_unescaped in [__import__("html").unescape(c)])
assert any('"' in __import__("html").unescape(c) and "</textarea>" in __import__("html").unescape(c) for c in copy), "quotes and tags must survive the copy attribute"
assert "Scattato" in page and "Se… allora" in page and "Concorrenti e comparabili" in page and "COLLISIONE" in page and "Profilo decisionale" in page
assert "https://" not in body.replace("http://www.w3.org", "") and "<script src" not in page and "<link " not in page
pub = sp.build(L, "publisher", [], [], set(), today)
assert "Passi in ordine" not in pub and "Se… allora" not in pub and "Concorrenti" not in pub and "Profilo decisionale" not in pub and "Pagine store: scheda copiabile" in pub and "Date fisse" in pub
# no steps section in calendar -> whole file rendered as markdown
open(os.path.join(L, "calendar.md"), "w", encoding="utf-8").write("| Data | Evento |\n|---|---|\n| 2026-12-01 | Pagina |\n")
assert "<td>Pagina</td>" in sp.build(L, "partner", [], [], set(), today)
# ---- creators.csv: collapsible, escaped, safe links, hidden from the publisher page
W("creators.csv", "piattaforma,nome,url,lingua,iscritti_follower,segmento,priorita,gioco_coperto,titolo_video,url_video,data_pubblicazione_circa,views,perche,contatto,data_verifica\n"
  f"YouTube,Alice {HOSTILE},https://www.youtube.com/@alice,EN,5000,micro,A,PlateUp,t,https://www.youtube.com/watch?v=x,2026-10-01,100,hook {HOSTILE},alice@example.com,2026-10-06\n"
  "TikTok,Bob,javascript:alert(1),IT,,da verificare,B,Overcooked,t,javascript:alert(2),,,why,,2026-10-06\n"
  "YouTube,Carl,https://www.youtube.com/@carl,EN,900000,medio,C,x,t,,,,,,2026-10-06\n")
pg = sp.build(L, "partner", [], [], set(), today)
assert re.search(r"<h2[^>]*>Creator</h2>", pg) and "3 creator" in pg and "priorità A 1 · B 1 · C 1" in pg and "alice@example.com" in pg
assert "javascript:alert" not in pg and "<img src=x" not in pg.replace("<script>" + sp.JS + "</script>", "")
assert pg.index("Alice") < pg.index("Bob") < pg.index("Carl"), "rows must be sorted by priority"
assert 'href="https://www.youtube.com/@alice"' in pg and 'href="https://www.youtube.com/watch?v=x"' in pg
assert not re.search(r"<h2[^>]*>Creator</h2>", sp.build(L, "publisher", [], [], set(), today)) and not re.search(r"<h2[^>]*>Creator</h2>", sp.build(L, "partner", [], [], {"creators"}, today))
# ---- beta vs full game: product label in the header, quick analysis of the full game as a table
st = json.load(open(os.path.join(L, "status.json"))); st["product"] = {"kind": "beta", "label": "Beta (Atto I)", "has_full_plan": True}
st["full_game"] = {"summary": f"La beta mostra il loop; mancano Atti II-III {HOSTILE}", "gaps": [{"area": "Contenuto", "today": "1 Atto", "target": "3 Atti", "action": "tagliare le modalità extra", "hours": 120}]}
json.dump(st, open(os.path.join(L, "status.json"), "w"))
pg = sp.build(L, "partner", [], [], set(), today)
assert "valutato come: Beta (Atto I)" in pg and "Beta oggi e gioco completo" in pg and "3 Atti" in pg and "<img src=x" not in pg.replace("<script>" + sp.JS + "</script>", "")
assert "Beta oggi e gioco completo" not in sp.build(L, "publisher", [], [], set(), today)
print("ALL STATUS_PAGE_FULL TESTS PASSED")
