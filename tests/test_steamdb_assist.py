"""steamdb_assist.py: links, append-only manual records, show with delta; it must never touch the network."""
import os, sys, subprocess, tempfile, csv
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("steamdb_assist must not use the network")
common.http_get = no_net
import steamdb_assist as sd

t = sd.links(["1599600", "728880"])
assert "https://steamdb.info/app/1599600/charts/" in t and "https://steamdb.info/app/728880/" in t
assert "stats/mostwished" in t and "DA VERIFICARE" in t and "vieta lo scraping" in t

d = tempfile.mkdtemp(); p = os.path.join(d, "sub", "steamdb.csv")
def run(*a):
    return subprocess.run([sys.executable, os.path.join(R, "steamdb_assist.py")] + list(a), capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
r = run("add", "1599600", "--date", "2026-10-01", "--followers", "12,400", "--wishlist-rank", "850", "--peak-24h", "310", "--csv", p); assert r.returncode == 0, r.stderr
r = run("add", "1599600", "--date", "2026-10-08", "--followers", "12.9K", "--peak-all", "4,100", "--lowest-price", "8.99", "--csv", p); assert r.returncode == 0, r.stderr
rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
assert len(rows) == 2 and rows[0]["followers"] == "12400" and rows[1]["followers"] == "12900", rows   # append-only, parsed
out = run("show", "--csv", p).stdout.decode("utf-8")
assert "+500" in out and "4,100" in out and "8.99" in out, out
assert run("add", "1", "--followers", "abc", "--csv", p).returncode != 0      # not a number
assert run("add", "1", "--csv", p).returncode != 0                             # nothing to record
assert len(list(csv.DictReader(open(p, encoding="utf-8-sig")))) == 2           # failed calls wrote nothing
print("ALL STEAMDB_ASSIST TESTS PASSED")
