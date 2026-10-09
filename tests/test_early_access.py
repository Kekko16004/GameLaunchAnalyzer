"""Early Access module: calc_econ EA scenario (independent arithmetic), Markdown in plain Italian, off by default,
and the reference docs carry the rules, numbers and interview questions."""
import os, sys, json, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
import calc_econ as ce

base = {**ce.DEFAULTS, "price": 9.99, "costs": 150, "wishlists": "1000,3000,8000", "conv": "0.1,0.2,0.3"}
o = ce.compute(base)
assert "early_access" not in o and "Accesso anticipato" not in ce.md(o)                       # off unless --ea-price is given

o = ce.compute({**base, "ea_price": 7.99})
ea = o["early_access"]
k = (1 - .15) * (1 - .10) * (1 - .06) * (1 - .30)                                             # same chain as the plan, checked by hand
assert abs(ea["net_per_copy_ea"] - round(7.99 * k, 2)) < 1e-9 and abs(ea["net_per_copy_full"] - round(9.99 * k, 2)) < 1e-9
assert ea["full_price"] == 9.99 and ea["ea_first_month"] == 0.35 and ea["full_vs_ea"] == 0.40
b = ea["scenarios"][1]                                                                         # base: 3000 x 0.2 = 600 copies
assert b["ea_month_copies"] == round(600 * 0.35) and abs(b["ea_month_net"] - round(210 * 7.99 * k, 2)) < 0.02
assert abs(b["full_month_net"] - round(210 * 7.99 * k * 0.40, 2)) < 0.02 and b["full_month_copies"] == round(210 * 7.99 * k * 0.40 / (9.99 * k))
assert ea["breakeven_copies_ea"] == -(-150 // (7.99 * k)) or ea["breakeven_copies_ea"] == int(150 / (7.99 * k)) + 1
assert all(x["full_month_net"] < x["ea_month_net"] for x in ea["scenarios"])                   # the 1.0 month is the smaller push (default 40 %)
o2 = ce.compute({**base, "ea_price": 7.99, "full_price": 12.99, "full_vs_ea": 60, "ea_first_month": 50})
assert o2["early_access"]["full_vs_ea"] == 0.60 and o2["early_access"]["ea_first_month"] == 0.50 and o2["early_access"]["full_price"] == 12.99
txt = ce.md(o)
assert "## Accesso anticipato (Early Access) e poi 1.0" in txt and "L'uscita in EA è il lancio vero" in txt and "[DA VERIFICARE]" in txt and "[OPINIONE]" in txt
try: ce.compute({**base, "ea_price": 0.0001, "full_price": -1}); raise AssertionError("negative price accepted")
except SystemExit: pass
d = tempfile.mkdtemp()
r = subprocess.run([sys.executable, os.path.join(R, "calc_econ.py"), "--price", "9.99", "--ea-price", "7.99", "--wishlists", "1000,3000,8000", "--conv", "0.1,0.2,0.3", "-o", os.path.join(d, "e.json")],
                   capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
assert r.returncode == 0 and "Accesso anticipato" in r.stdout and json.load(open(os.path.join(d, "e.json")))["early_access"]["ea_price"] == 7.99, r.stderr

# docs: the rules, sources, numbers and the interview questions are there
ref = open(os.path.join(HERE, "..", "references", "02-audit-platform-pricing.md"), encoding="utf-8").read()
for need in ("Early Access o lancio 1.0", "partner.steamgames.com/doc/store/earlyaccess", "upcoming_events/nextfest", "newsletter.gamediscover.co/p/the-state-of-steam-early-access-graduates",
             "437 giorni", "40 %", "20 %", "l'uscita in EA è IL lancio", "[DA VERIFICARE]", "Uscita in Early Access", "Uscita 1.0"):
    assert need in ref, need
iv = open(os.path.join(HERE, "..", "references", "00-intervista.md"), encoding="utf-8").read()
assert "Domande sull'Early Access" in iv and "Il mio consiglio: [EA / 1.0 diretta" in iv
assert "EA con poco contenuto" in open(os.path.join(HERE, "..", "SKILL.md"), encoding="utf-8").read() and "EA con poco contenuto" in open(os.path.join(HERE, "..", "references", "playbooks.md"), encoding="utf-8").read()
print("ALL EARLY_ACCESS TESTS PASSED")
