"""store_bench: page features from a canned Steam appdetails/appreviews answer, then analyze on several games."""
import os, sys, json, datetime as dt, io, contextlib, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import store_bench as sb

today = dt.date.today(); rel = today - dt.timedelta(days=730)
def fake_safe_json(url, **kw):
    aid = url.split("appids=")[1].split("&")[0] if "appdetails" in url else url.split("/appreviews/")[1].split("?")[0]
    n = int(aid)
    if "appdetails" in url:
        html = '<h2 class="bb_tag">Feat</h2><img class="bb_img" src="https://x/a.gif">' * (n % 4) + "<p>" + "word " * (50 + 20 * n) + "</p>"
        return {aid: {"data": dict(name=f"G{n}", short_description="s" * (100 + 10 * n), about_the_game=html, screenshots=[{}] * (4 + n), is_free=False,
                 movies=[dict(name="Trailer", highlight=True, hls_h264="https://v.x/t/hls_264_master.m3u8?t=1", dash_h264="https://v.x/t/dash_h264.mpd?t=1")], supported_languages="English<strong>*</strong>, French, German<br><strong>*</strong>languages with full audio support",
                 achievements={"total": 10 * n}, categories=[{"description": "Steam Cloud"}, {"description": "Single-player"}], genres=[{"description": "Action"}],
                 demos=[{"appid": 1}] if n % 2 else None, price_overview={"initial": 1499, "final": 1499}, release_date={"coming_soon": False, "date": rel.strftime("%b %d, %Y").replace(" 0", " ")})}}
    return {"query_summary": {"total_reviews": 200 * 2 ** n, "total_positive": int(200 * 2 ** n * .9)}}
sb.safe_json = fake_safe_json; sb.set_rate(0)
o = sb.page_features(3, "us", "english")
assert o["name"] == "G3" and o["short_desc_chars"] == 130 and o["screenshots"] == 7 and o["languages"] == 3 and o["achievements"] == 30 and o["gifs"] == 3 and o["has_demo"] == 1
assert o["price"] == 14.99 and 1.9 < o["years_since_release"] < 2.1 and o["reviews_total"] == 1600 and o["pct_positive"] == 90.0 and abs(o["reviews_per_year"] - 1600 / o["years_since_release"]) < 1
assert [k for k, _ in o["_movies"]] == ["hls", "dash"], o["_movies"]   # Steam trailers without any MP4 are found
print("page_features ok:", {k: o[k] for k in ("short_desc_chars", "desc_words", "gifs", "screenshots", "languages", "reviews_per_year")})
d = tempfile.mkdtemp(); out, md = os.path.join(d, "p.json"), os.path.join(d, "b.md")
sys.argv = ["x", "--rate", "0", "run", "--no-trailer", "-o", out, "--md", md] + [str(i) for i in range(1, 11)]
with contextlib.redirect_stderr(io.StringIO()): sb.main()
rows = json.load(open(out)); assert len(rows) == 10 and rows[0]["trailer_s"] is None if "trailer_s" in rows[0] else True
txt = open(md, encoding="utf-8").read(); assert "10 giochi" in txt and "Spearman" in txt and "short_desc_chars" in txt
res = sb.analyze(rows); f = {x["feature"]: x for x in res["features"]}; assert f["short_desc_chars"]["rho_reviews_per_year"] is not None
print("ALL STORE_PAGES TESTS PASSED")
