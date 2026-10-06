"""genre_bench and watchlist with canned Steam/SteamSpy answers."""
import os, sys, json, urllib.parse, datetime as dt, io, contextlib, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import common
today = dt.date.today()
state = {"day": 0}
def rel(years): d = today - dt.timedelta(days=int(365.25 * years)); return d.strftime("%b %d, %Y").replace(" 0", " ")
def fake(url, **kw):
    u = urllib.parse.urlparse(url); qs = urllib.parse.parse_qs(u.query)
    if "steamspy" in u.netloc:
        return json.dumps({str(i): {"name": f"G{i}", "positive": 900 * i, "negative": 100 * i, "owners": "x", "price": str(999 + 100 * (i % 5))} for i in range(1, 41)}).encode()
    if "appdetails" in u.path:
        aid = int(qs["appids"][0])
        if aid >= 900:   # competitor releasing soon
            return json.dumps({str(aid): {"data": {"name": "Rival", "release_date": {"coming_soon": True, "date": "1 Mar, 2027"}, "price_overview": {"initial": 1499, "discount_percent": 0}}}}).encode()
        disc = 30 if state["day"] >= 14 and aid == 7 else 0
        return json.dumps({str(aid): {"data": {"name": f"G{aid}", "release_date": {"coming_soon": False, "date": rel(0.5 + (aid % 4))}, "price_overview": {"initial": 999 + 100 * (aid % 5), "discount_percent": disc},
                                      "demos": [{"appid": 1}] if aid % 2 else None, "is_free": False}}}).encode()
    if "appreviews" in u.path:
        aid = int(u.path.split("/")[-1]); gain = 1000 * state["day"] // 7 * (5 if (aid == 7 and state["day"] >= 35) else 1)
        return json.dumps({"query_summary": {"total_reviews": 1000 * aid + gain, "total_positive": int((1000 * aid + gain) * (0.9 if state["day"] < 28 else 0.85))}}).encode()
    if "GetNumberOfCurrentPlayers" in u.path:
        return json.dumps({"response": {"player_count": 100 + state["day"], "result": 1}}).encode()
    raise AssertionError(url)
common.http_get = fake; common.set_rate(0)
import genre_bench as gb, watchlist as wl

# ---- genre_bench
d = tempfile.mkdtemp(); out, md = os.path.join(d, "g.json"), os.path.join(d, "g.md")
sys.argv = ["x", "--rate", "0", "--tag", "Roguelike", "--enrich", "30", "--mine", "price=14.99", "--mine", "reviews_per_year=500", "--md", md, "-o", out]
with contextlib.redirect_stderr(io.StringIO()): gb.main()
r = json.load(open(out)); a = r["analysis"]
assert a["n_listed"] == 40 and a["n_with_age"] == 30 and a["distributions"]["price"]["n"] >= 30 and a["cohorts"] and a["price_bands"] and len(a["demo"]) == 2
assert {m["feature"] for m in a["mine"]} == {"price", "reviews_per_year"} and all(0 <= m["percentile"] <= 100 for m in a["mine"])
txt = open(md, encoding="utf-8").read(); assert "coda alta" in txt and "non il gioco mediano" in txt and "Per anno di uscita" in txt
print("genre_bench ok:", a["distributions"]["reviews_per_year"]["median"], "median reviews/year;", len(a["cohorts"]), "cohorts")

# ---- watchlist over three weeks of snapshots
csvp = os.path.join(d, "wl.csv")
def run(argv):
    sys.argv = ["x", "--rate", "0"] + argv
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()): wl.main()
base = today - dt.timedelta(days=35)
real_today = dt.date
def snap_on(offset, cmd):
    class FakeDate(dt.date):
        @classmethod
        def today(cls): return base + dt.timedelta(days=offset)
    wl.dt.date = FakeDate
    try: state["day"] = offset; run(cmd)
    finally: wl.dt.date = real_today
snap_on(0, ["add", "7", "8", "--role", "comp", "--csv", csvp]); snap_on(0, ["add", "900", "--role", "competitor", "--csv", csvp])
for off in (7, 14, 21, 28, 35): snap_on(off, ["snap", "--csv", csvp])
rows = wl.read(csvp); assert len(rows) == 3 * 6, len(rows)
snap_on(35, ["snap", "--csv", csvp]); assert len(wl.read(csvp)) == 18, "same-day snapshot must replace, not duplicate"
o = wl.analyse(rows, today, dt.date(2027, 3, 10), 30, 3.0); texts = " | ".join(f"{x['level']} {x['game']} {x['text']}" for x in o["alerts"])
assert any(x["level"] == "ALARM" and "Rival" in x["game"] and "COLLISIONE" in x["text"] for x in o["alerts"]), texts
assert any("Impennata" in x["text"] for x in o["alerts"]) and any("In saldo del 30%" in x["text"] and "rilevato dal" in x["text"] for x in o["alerts"]) and any("% positive scese" in x["text"] for x in o["alerts"]), texts
g7 = next(g for g in o["games"] if g["appid"] == 7); assert g7["gain_7d"] is not None and g7["gain_30d"] is not None and g7["snapshots"] == 6
o2 = wl.analyse(rows, today, dt.date(2028, 1, 1), 30, 3.0); assert not any("COLLISIONE" in x["text"] for x in o2["alerts"])
print("watchlist ok:", sorted({x["text"][:22] for x in o["alerts"]}))
print("ALL GENRE/WATCHLIST TESTS PASSED")
