import sys, json, io, contextlib, os, tempfile, csv, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import common
def fake(url, **kw):
    u = urllib.parse.urlparse(url)
    if "appdetails" in u.path: return json.dumps({"7": {"data": {"name": "G", "release_date": {"date": "1 Jan, 2024"}, "price_overview": {"initial": 1000, "final": 1000}}}}).encode()
    if "appreviews" in u.path: return json.dumps({"query_summary": {"total_reviews": 100, "total_positive": 90}}).encode()
    if "gamalytic" in u.netloc: return json.dumps({"data": {"copiesSold": 5000, "firstReleaseDate": 1704067200000, "accuracy": 0.9}}).encode()
    if "tiktok.com/oembed" in url: return json.dumps({"author_name": "Foo", "author_url": "https://www.tiktok.com/@foo", "title": "t"}).encode()
    raise AssertionError(url)
common.http_get = fake
import steam_comps, social_verify, build_creators
def run(mod, argv):
    sys.argv = ["x"] + argv; b = io.StringIO()
    with contextlib.redirect_stdout(b), contextlib.redirect_stderr(io.StringIO()): mod.main()
    return b.getvalue()
r = json.loads(run(steam_comps, ["7", "--gamalytic", "--rate", "0"]))[0]
assert r["gamalytic_first_release"] == "2024-01-01" and r["boxleiter_x30"] == 3000 and r["copies_per_review"] == 50, r
print("steam_comps ok:", r["gamalytic_first_release"], r["boxleiter_x30"], r["copies_per_review"])
t = json.loads(run(social_verify, ["https://www.tiktok.com/@foo/video/7677411131643809031", "--since", "2026-01-01", "--rate", "0"]))[0]
assert t["date"] == "2026-07-03" or t["date"].startswith("2026"), t; print("social_verify ok: tiktok id ->", t["date"], "recent", t["recent"])
d = tempfile.mkdtemp(); yt = os.path.join(d, "yt.json"); out = os.path.join(d, "c.csv")
json.dump([{"ch": "A", "url": "/@a", "subs": 5000, "country": "IT", "vids": [{"vid": "x" * 11, "title": "t", "topic": "G", "days": 3, "views": 10}]},
           {"ch": "B", "url": "/@b", "subs": None, "vids": [{"vid": "y" * 11, "title": "t", "topic": "G", "days": 3}]}], open(yt, "w"))
sys.argv = ["x", "--youtube", yt, "--priority-langs", "IT,EN", "-o", out]; err = io.StringIO()
with contextlib.redirect_stderr(err): build_creators.main()
rows = list(csv.DictReader(open(out, encoding="utf-8-sig"))); assert len(rows) == 1 and rows[0]["priorita"] == "A" and rows[0]["lingua"] == "IT"
assert "1 YouTube channels skipped" in err.getvalue(); print("build_creators ok: row A/IT, skipped-channel warning shown")

print("ALL COMPS/SOCIAL/CREATORS TESTS PASSED")
