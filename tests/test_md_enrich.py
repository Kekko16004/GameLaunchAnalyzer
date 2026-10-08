"""md_enrich.py: links between the Markdown documents, protected zones, idempotence, glossary at the end of REPORT.md, subfolder paths, CLI."""
import os, sys, tempfile, subprocess, json
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import md_enrich as me

d = tempfile.mkdtemp()
def W(n, t):
    p = os.path.join(d, *n.split("/")); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(t)
def Rd(n): return open(os.path.join(d, *n.split("/")), encoding="utf-8").read()
for f in ("06-creators.md", "calendar.md", "05c-premortem.md", "03-pricing.md", "store_kit.md", "TODO.md", "01-dev.md"): W(f, "# " + f + "\ncreator calendario a passi\n")
W("REPORT.md", """# Report

## Creator e community
I creator da contattare, vedi `calendar.md` e `store_kit.md`. Il pre-mortem e il prezzo e il prezzo ancora.
Un altro creator, la wishlist e la wishlist ancora. Pagine Steam pronte. Vedi https://example.com/creator e [già linkato](TODO.md) con TODO.
Inline `creator` non cambia. <b>creator</b> in HTML nemmeno.

```text
creator pre-mortem
```

| Voce | Note |
|---|---|
| audit | fatto |

<!-- note
creator
-->
Fine creator.
""")
W("06-creators.md", "# Creator\nIl creator e il calendario a passi. Vedi il pre-mortem.\n")
W("history/2026-10-01-delta.md", "# Delta\nI creator sono cambiati.\n")
W("notes.txt", "creator"); W("fg/timeline.md", "creator")
stats = me.run(d)
r = Rd("REPORT.md")
assert "[creator](06-creators.md)" in r and "[`calendar.md`](calendar.md)" in r and "[`store_kit.md`](store_kit.md)" in r and "[pre-mortem](05c-premortem.md)" in r and "[prezzo](03-pricing.md)" in r, r
assert r.count("](03-pricing.md)") == 1 and r.count("](06-creators.md)") == 1 and "[Pagine Steam](store_kit.md)" not in r      # first mention only; store_kit already linked through the file name
assert "## Creator e community" in r and "[Creator" not in r.split("\n")[2]                                                    # headings untouched
assert "https://example.com/creator" in r and "[già linkato](TODO.md)" in r and r.count("](TODO.md)") == 1                      # URL and existing link untouched, TODO not linked twice
assert "Inline `creator` non cambia" in r and "<b>creator</b>" in r and "```text\ncreator pre-mortem\n```" in r and "<!-- note\ncreator\n-->" in r
assert "[audit](01-dev.md)" in r                                                                                                   # table cells are text too
assert r.count("[Pagine") == 0 and "Pagine Steam pronte" in r
c = Rd("06-creators.md"); assert "](06-creators.md)" not in c and "[calendario a passi](calendar.md)" in c and "[pre-mortem](05c-premortem.md)" in c      # never to itself
assert "[creator](../06-creators.md)" in Rd("history/2026-10-01-delta.md")                                                         # relative path from a subfolder
assert Rd("notes.txt") == "creator" and Rd("fg/timeline.md") == "creator"                                                          # only .md in launch/ and launch/history
# glossary: only REPORT.md, only used terms, replaced (not duplicated) on re-run
g = r.split("<!-- glossario:inizio -->")[1]
assert "## Glossario: le parole usate" in g and "**Wishlist**" in g and "**Pre-mortem**" in g and "**Creator e outreach**" in g and "**Break-even**" not in g and r.rstrip().endswith("<!-- glossario:fine -->")
assert "glossario" not in Rd("calendar.md").lower() and "glossario" not in c.lower()
before = {n: Rd(n) for n in ("REPORT.md", "06-creators.md", "calendar.md")}
assert me.run(d) == {} and all(Rd(n) == t for n, t in before.items()) and Rd("REPORT.md").count("glossario:inizio") == 1          # idempotent
W("REPORT.md", Rd("REPORT.md").replace("wishlist", "WISHLIST") + "\nbreak-even e ICE\n"); me.run(d)
g2 = Rd("REPORT.md").split("<!-- glossario:inizio -->")[1]; assert "**Break-even**" in g2 and "**ICE**" in g2 and Rd("REPORT.md").count("glossario:inizio") == 1
# options and CLI
W("REPORT.md", "# R\ncreator\n"); st = me.run(d, dry=True); assert st and "](06-creators.md)" not in Rd("REPORT.md")
me.run(d, glossary=False); assert "glossario" not in Rd("REPORT.md").lower() and "[creator](06-creators.md)" in Rd("REPORT.md")
W("REPORT.md", "# R\nIl creator e il focus group ✅ → ok\n")
out = subprocess.run([sys.executable, os.path.join(R, "md_enrich.py"), "--launch-dir", d], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
assert out.returncode == 0 and b"REPORT.md" in out.stdout, out.stderr
assert "✅ → ok" in Rd("REPORT.md") and subprocess.run([sys.executable, os.path.join(R, "md_enrich.py"), "--launch-dir", d + "/nope"], capture_output=True).returncode != 0
print("ALL MD_ENRICH TESTS PASSED")
