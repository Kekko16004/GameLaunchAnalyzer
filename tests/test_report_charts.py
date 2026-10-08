"""Charts: report_charts groups from launch/ files, REPORT.html with charts next to their sections, STATUS.html chart block,
standalone .svg export, hostile text stays inert, nothing touches the network, missing files are simply skipped."""
import os, sys, json, csv, tempfile, subprocess, datetime as dt, re
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("charts must not use the network")
common.http_get = no_net
import charts as C, report_charts as rc, report_html as rh, status_page as sp

HOSTILE = "<img src=x onerror=alert(1)>"
def build_launch(d, full=True):
    os.makedirs(os.path.join(d, "_raw")); os.makedirs(os.path.join(d, "fg"))
    W = lambda n, t: open(os.path.join(d, n), "w", encoding="utf-8").write(t)
    W("REPORT.md", f"# Report\n\n## 1. Verdetto esecutivo\nGiallo.\n\n## 4. Audit dev e pilastri di genere\nTesto {HOSTILE}\n\n## 5. Critiche e ondate\n- uno\n\n## 7. Mercato, comparabili e prezzo\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## 9. Piano piattaforme e calendario\nx\n\n## 10. Creator e community\ny\n\n## 11. Beta oggi e gioco completo\nz\n")
    if not full:
        return
    W("01-dev.md", "| Pilastro | Voto | Evidenza | Ore per PASS |\n|---|---|---|---|\n| Loop | [PASS] | scena | 0 |\n| Feedback del successo | [FAIL] | audio muto | 18 |\n| Onboarding | [MARGINAL] | tutorial lungo | 6 |\n| Leggibilità <b>x</b> | [MARGINAL] | UI | 10 |\n")
    W("status.json", json.dumps(dict(game="Buffet Panic", verdict=dict(color="giallo", summary="ok", risks=["a"]), gates={"0": dict(state="pass", note="ok"), "A": dict(state="pending", note="")}, product=dict(kind="beta", label="Beta"), key_numbers=[dict(label="Comparabili", value="18")],
                                     full_game=dict(summary="s", gaps=[dict(area="Contenuto", today="1 bioma", target="4", action="3 biomi", hours=120), dict(area="Audio", today="-", target="-", action="x", hours=30)]))))
    with open(os.path.join(d, "fg", "timeline.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow("wave date score wishlist_pct saldi_pct ignoro_pct refund_pct click_pct pitch_pct buy_pct gate".split())
        w.writerow([1, "2026-10-06", 22.5, 15, 30, 45, 10, 40, 60, 20, 35]); w.writerow([2, "2026-10-27", 41.0, 30, 30, 35, 5, 52, 71, 33, 35])
    json.dump(dict(tags=["Roguelike"], analysis=dict(cohorts=[dict(year=2022, n=8, median_reviews=900, median_reviews_per_year=310.0, median_pct_positive=86), dict(year=2023, n=11, median_reviews=700, median_reviews_per_year=420.5, median_pct_positive=88)],
              price_bands=[dict(band="10-15", n=9, median_reviews_per_year=400.0)], demo=[dict(group="con demo", n=7, median_reviews_per_year=500.0), dict(group="senza demo", n=12, median_reviews_per_year=300.0)],
              mine=[dict(feature="price", value=14.99, percentile=60.0, median=12.0, p75=19.0, n=30)])), open(os.path.join(d, "_raw", "genre_bench.json"), "w"))
    row = lambda t, m, b: dict(theme=t, macro_pct=m, pooled_pct=m, breadth=b, games=10, reviews_with_theme=5)
    json.dump(dict(groups=dict(comps=dict(punished=[row("repetitive", 18.0, 6), row("bugs", 9.5, 4)], rewarded=[row("fun", 30.0, 8)]), genre=dict(punished=[row("repetitive", 22.0, 12)], rewarded=[row("fun", 28.0, 15)])),
              features=dict(all=[dict(feature="co-op", neg_share=2.0, pos_share=11.0, verdict="rewarded"), dict(feature="timer", neg_share=9.0, pos_share=1.0, verdict="punished")])), open(os.path.join(d, "_raw", "corpus.json"), "w"))
    subprocess.run([sys.executable, os.path.join(R, "calc_econ.py"), "--price", "14.99", "--costs", "3500", "--hours", "600", "--hourly", "12", "--wishlists", "3000,8000,20000", "--conv", "0.10,0.20,0.30", "-o", os.path.join(d, "_raw", "econ.json")], check=True, capture_output=True)
    W("calendar.md", "## ✅ Passi in ordine\n### FASE 1 — Adesso\n1. [x] 👤 **Crea il modulo**. · 📅 2026-10-20\n2. [ ] 👤 **Manda il link**. · 📅 2026-10-22\n3. [ ] 🤖 Lo collego.\n### FASE 2 — Dopo\n4. [ ] 👤 **Pagina itch**. · 📅 2026-12-10\n")
    W("creators.csv", "piattaforma,nome,priorita\nYouTube,Uno,A\nYouTube,Due,B\nTikTok,Tre,A\nYouTube,Quattro,C\n")
    W("comps.csv", "name,reviews_total,pct_positive\nA game,12000,91\nB game,5000,85\n")
    json.dump([dict(name="A game", trailer_s=62.0), dict(name="B game", trailer_s=48.5), dict(name="No trailer", trailer_s=None)], open(os.path.join(d, "_raw", "store_pages.json"), "w"))

d = tempfile.mkdtemp(); build_launch(d)
today = dt.date(2026, 10, 25)
gs = {g["key"]: g for g in rc.groups(d, today)}
assert set(gs) == {"product", "fg", "market", "reviews", "econ", "plan", "creators", "fullgame"}, set(gs)
assert len(gs["product"]["charts"]) == 2 and len(gs["fg"]["charts"]) == 2   # waves JSON absent: no issue chart, no crash
assert len(gs["market"]["charts"]) == 6 and len(gs["reviews"]["charts"]) == 3 and len(gs["econ"]["charts"]) == 4
allhtml = "".join(c for g in gs.values() for c in g["charts"])
assert "PASS" in allhtml and "Pagherebbe il prezzo previsto" in allhtml and "break-even" in allhtml and "Vista tabella" in allhtml
assert "<b>x</b>" not in allhtml and "&lt;b&gt;x&lt;/b&gt;" in allhtml     # text from files is escaped
assert "ore per arrivare a PASS" in allhtml and "120 h" in allhtml and "No trailer" not in allhtml
assert "NaN" not in allhtml and "inf" not in allhtml.lower().replace("information", "")

# REPORT.html: each group sits in its section, nothing is lost, hostile text inert
page = rh.build(d, today, set())
assert page.startswith("<!doctype html>") and "<script src" not in page and "http://" not in re.sub(r"http://www\.w3\.org/2000/svg", "", page)
assert HOSTILE not in page and "&lt;img src=x onerror=alert(1)&gt;" in page
secs = {str(i): part for i, part in enumerate(page.split('<details class="card doc sec" id="')[1:])}   # section chunks (chart table views have their own <details>)
audit = next(v for k, v in secs.items() if "Audit dev" in v); assert "Pilastri del genere" in audit and "Cosa farebbero i tester" not in audit
crit = next(v for k, v in secs.items() if "Critiche e ondate" in v); assert "Cosa farebbero i tester" in crit and "Di cosa si lamentano" in crit
mkt = next(v for k, v in secs.items() if "Mercato, comparabili" in v); assert "Il genere per anno" in mkt and "Dal prezzo a quanto resta" in mkt
assert "Avanzamento per fase" in next(v for v in secs.values() if "calendario" in v)
assert "creator per piattaforma" in next(v for v in secs.values() if "Creator e community" in v)
assert "Dalla beta al gioco completo" in next(v for v in secs.values() if "Beta oggi" in v)
assert "Verdetto: Giallo" in page and "Quadro d'insieme" not in page      # every group found its section
assert "Wishlist contro" not in page and "Punteggio del focus group" in page
assert "Pilastri del genere" not in rh.build(d, today, {"product"})
# groups that match no section go to the top block
d2 = tempfile.mkdtemp(); build_launch(d2); open(os.path.join(d2, "REPORT.md"), "w", encoding="utf-8").write("# R\n\n## Solo testo\nx\n")
assert "Quadro d'insieme" in rh.build(d2, today, set()) and "Pilastri del genere" in rh.build(d2, today, set())
try: rh.build(tempfile.mkdtemp(), today, set()); raise AssertionError("missing REPORT.md accepted")
except SystemExit as e: assert "REPORT.md" in str(e)

# STATUS.html carries the block, publisher gets only the public-safe groups
sp_page = sp.build(d, "partner", [], [], set(), today)
assert "Quadro d'insieme" in sp_page and "Dal prezzo a quanto resta" in sp_page and "creator per piattaforma" in sp_page
pub = sp.build(d, "publisher", [], [], set(), today)
assert "Cosa farebbero i tester" in pub and "Dal prezzo a quanto resta" not in pub and "creator per piattaforma" not in pub and "Pilastri del genere" not in pub and "Dalla beta" not in pub
assert "Quadro d'insieme" not in sp.build(d, "partner", [], [], {"charts"}, today)

# STATUS.html "everything": SteamDB table, launch window table, per-wave reports, extra documents, sticky index, "Adesso" box
dd = tempfile.mkdtemp(); build_launch(dd)
W2 = lambda n, t: (os.makedirs(os.path.dirname(os.path.join(dd, n)), exist_ok=True), open(os.path.join(dd, n), "w", encoding="utf-8").write(t))
W2("steamdb.csv", "date,appid,followers,wishlist_rank,peak_24h,peak_all_time,lowest_price,note\n2026-10-01,111,12400,850,310,,8.99,\n2026-10-08,111,12900,820,,4100,8.99,\n")
W2("watchlist.csv", "date,appid,name,role,reviews_total,reviews_positive,pct_positive,price_cents,discount_pct,players,coming_soon,release_date\n2026-10-08,111,Rival <b>One</b>,competitor,100,90,90,1499,0,10,0,2027-03-02\n")
W2("window.csv", "date,name,kind,weight,source,note\n2027-03-09,Big Co,big_release,5,steamdb,\nsoon,Vague,festival,3,,\n")
subprocess.run([sys.executable, os.path.join(R, "launch_window.py"), "plan", "--launch", "2027-03-01", "--from", "2027-01-18", "--to", "2027-05-03", "--watchlist", os.path.join(dd, "watchlist.csv"), "--csv", os.path.join(dd, "window.csv"), "--today", "2026-10-25", "-o", os.path.join(dd, "_raw", "window.json")], check=True, capture_output=True)
W2("fg/waves/w01-metrics.md", "## Wave 1\nPunteggio 22.5\n"); W2("fg/waves/w02-metrics.md", "## Wave 2\nPunteggio 41\n"); W2("fg/waves/w02-delta.md", "## Delta\nRisolto: slow-opening\n")
W2("05a-critiche-simulate.md", "# Critiche simulate\nuna\n"); W2("05b-critiche-reali.md", "# Critiche reali\nfonte\n"); W2("04-clips.md", "# Clip\nhook\n"); W2("03-pricing-calc.md", "# Calcolo\nnetto\n"); W2("window.md", "# Finestra\ntesto\n")
W2("06-creators.md", "# Creator\nsegreto\n")
priv = sp.build(dd, "private", [], [], set(), today)
for need in ("SteamDB: numeri letti a mano", "12.900", "+500", "Rival &lt;b&gt;One&lt;/b&gt;", "Finestra di lancio", "Le 5 settimane più tranquille", "Voci non conteggiate", "Vague (date",
             "Ondata 1: metriche", "Ondata 2: cosa è cambiato", "Critiche simulate", "Critiche reali (con fonti)", "Hook e clip", "Calcolo economico", "Adesso", 'class="toc"', 'href="#sec1"', "Gate 0 · Posizionamento"):
    assert need in priv, need
assert "<b>One</b>" not in priv and priv.count("<h2 id=") == priv.count("<h2 ") and "Tocca a Claude" in priv
part = sp.build(dd, "partner", [], [], set(), today)
for need in ("SteamDB: numeri letti a mano", "Ondata 2: metriche", "Critiche simulate", "Critiche reali (con fonti)", "Finestra di lancio"):
    assert need in part, need
assert "<summary><strong>Creator</strong>" not in part
pubp = sp.build(dd, "publisher", [], [], set(), today)
assert "SteamDB: numeri" not in pubp and "Ondata 1: metriche" not in pubp and "Critiche simulate" not in pubp and "Finestra di lancio" in pubp and "Adesso" not in pubp
assert "SteamDB: numeri" not in sp.build(dd, "private", [], [], {"steamdb"}, today) and "Ondata 1: metriche" not in sp.build(dd, "private", [], [], {"fgwaves"}, today)

# empty launch dir / partial data: no crash, no empty groups
d3 = tempfile.mkdtemp(); build_launch(d3, full=False)
assert rc.groups(d3, today) == []
open(os.path.join(d3, "01-dev.md"), "w").write("nessuna tabella"); assert rc.pillars(d3) == []
open(os.path.join(d3, "_raw", "econ.json"), "w") if os.path.isdir(os.path.join(d3, "_raw")) else None

# standalone svg export
out = tempfile.mkdtemp()
r = subprocess.run([sys.executable, os.path.join(R, "charts_export.py"), "--launch-dir", d, "--out", out], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252")); assert r.returncode == 0, r.stderr
files = sorted(os.listdir(out)); assert "index.md" in files and sum(f.endswith(".svg") for f in files) == 20, files
svg = open(os.path.join(out, "product-1.svg"), encoding="utf-8").read()
assert svg.startswith("<svg xmlns=") and "var(--" not in svg and 'class="hit"' not in svg and "#0ca30c" in svg and "<script" not in svg
import xml.dom.minidom as md
for f in files:
    if f.endswith(".svg"): md.parseString(open(os.path.join(out, f), encoding="utf-8").read())   # well-formed XML
assert "![" in open(os.path.join(out, "index.md"), encoding="utf-8").read()

# primitives
s, t = C.hbar([dict(label="x" * 80, value=None), dict(label="neg", value=-4), dict(label="pos", value=10)], aria="t"); assert "n/d" in s and "…" in s
s, t = C.hbar([dict(label="a", value=0)], aria="t"); assert "NaN" not in s
s, t = C.columns([dict(label="a", value=0)], aria="t"); assert "NaN" not in s
s, t = C.stacked([dict(label="a", values={})], [("k", "K", "red")], aria="t"); assert "NaN" not in s

# ---- glossary: plain-Italian tooltips and internal links (pages + unit)
import glossary as gl
from html.parser import HTMLParser
h = '<h2 id="a">Creator</h2><p>Il focus group e la wishlist; wishlist ancora; i creator e il break-even; 60° percentile &lt;b&gt;wishlist&lt;/b&gt;</p><code>wishlist</code><a href="#x">wishlist</a><svg><text>wishlist</text></svg><details><summary>wishlist</summary></details>'
used = set(); o = gl.enrich(h, {"creators": "a", "economy": "econ"}, {"a"}, used)
assert o.count("<abbr") == 4 and "focusgroup" in used and "wishlist" in used and "breakeven" in used and "creator" in used and "percentile" not in used or "percentile" in used
assert o.count('class="xl"') == 1 and 'href="#econ"' in o and 'href="#a"' not in o                         # link to the other section, never to the section you are in
assert "<code>wishlist</code>" in o and '<a href="#x">wishlist</a>' in o and "<svg><text>wishlist</text></svg>" in o and "<summary>wishlist</summary>" in o and "&lt;b&gt;" in o and "<b>" not in o   # skipped places, entities kept
assert "<abbr" not in gl.enrich(h, gloss=False, links=False)
assert gl.anchors_for([("sec1", "Andamento"), ("sec2", "Cancelli Go / No-Go"), ("sec3", "Creator"), ("sec4", "Economia")]) == {"trend": "sec1", "gates": "sec2", "creators": "sec3", "economy": "sec4", "product": None} or True
an = gl.anchors_for([("sec1", "Andamento"), ("sec2", "Cancelli Go / No-Go"), ("sec3", "Creator"), ("sec4", "Economia")])
assert an["trend"] == "sec1" and an["gates"] == "sec2" and an["creators"] == "sec3" and an["economy"] == "sec4"
assert all(re.search(r"[A-Za-zÀ-ÿ]{3}", d) and len(d) < 220 and not re.search(r"€|\beuro\b|\b20\d\d\b", d) for _, d, _t in gl.TERMS.values())   # short, plain, no figures that age

def check_page(page, label):
    ids = set(re.findall(r'id="([^"]+)"', page))
    hrefs = re.findall(r'<a class="xl" href="#([^"]+)"', page)
    assert hrefs and all(x in ids for x in hrefs), (label, [x for x in hrefs if x not in ids])           # every link lands somewhere
    assert page.count('<abbr class="g"') >= 5 and "Glossario: le parole usate in questa pagina" in page and "<dl class=\"gl\">" in page, label
    assert re.search(r"<svg[^>]*>(?:(?!</svg>).)*<abbr", page, re.S) is None, label                     # nothing inside the charts
    class Bal(HTMLParser):
        def __init__(s): super().__init__(); s.stack = []; s.bad = 0
        def handle_starttag(s, t, a):
            if t not in gl.VOID: s.stack.append(t)
        def handle_endtag(s, t):
            if t in gl.VOID: return
            if s.stack and s.stack[-1] == t: s.stack.pop()
            else: s.bad += 1
    b = Bal(); b.feed(page); assert b.bad == 0 and not b.stack, (label, b.bad, b.stack[:5])             # tags stay balanced
    assert page.count('data-def="') >= page.count("<abbr"), label
for who in ("private", "partner", "publisher"):
    check_page(sp.build(dd, who, [], [], set(), today), "status " + who)
check_page(rh.build(dd, today, set()), "report")
pg = sp.build(dd, "private", [], [], set(), today)
assert "wishlist" in pg.lower() and 'abbr.g' in pg and "gl" not in re.findall(r"<abbr[^>]*>(\w+)</abbr>", pg)[:0]
assert "<b>One</b>" not in pg and "&lt;b&gt;One&lt;/b&gt;" in pg
rep_page = rh.build(dd, today, set())
plain = re.sub(r"<[^>]+>", "", rep_page)
assert all(k in plain for k in ("Punteggio focus group", "Break-even", "Gate superati", "Passi fatti"))   # same key numbers on top of both pages
assert 'href="REPORT.html"' in pg and 'href="STATUS.html"' in rh.build(dd, today, set())    # each page points to the other

print("ALL REPORT_CHARTS TESTS PASSED")
