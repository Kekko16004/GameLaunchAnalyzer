import sys, os, sqlite3, json, random, io, contextlib, datetime as dt, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import gt_corpus as gt
d = tempfile.mkdtemp(); path = os.path.join(d, "gamestracker.db"); con = sqlite3.connect(path)
con.executescript("""
create table games(id integer primary key, platform varchar(16), external_id varchar(255), title varchar(500), developer varchar(255), publisher varchar(255),
  genres json, tags json, release_date date, has_demo boolean, demo_release_date date, price float, is_free boolean, store_url varchar(1000), header_image varchar(1000),
  first_seen_at datetime, quality_score float, discarded boolean);
create table game_snapshots(id integer primary key, game_id integer, captured_at datetime, snapshot_type varchar(16), total_reviews integer, total_positive integer,
  total_negative integer, review_score_desc varchar(100), current_players integer, steamspy_owners varchar(100), steamspy_estimate integer, price float, extra json);
create table social_posts(id integer primary key, game_id integer, platform varchar(16), post_url varchar(1000), subreddit varchar(255), posted_at datetime, title varchar(1000),
  views integer, likes integer, comments integer, shares integer, captured_at datetime);
create table projects(id integer primary key, name varchar(200), description text, genre varchar(100), concept_data json, simulator_data json, discount_plan json, created_at datetime, updated_at datetime);
""")
rnd = random.Random(7); today = dt.date.today(); gid = 0
for i in range(60):
    gid += 1; rel = today - dt.timedelta(days=rnd.randint(60, 500)); shots = rnd.randint(4, 16); trailer = rnd.random() < .8; desc = rnd.randint(80, 300)
    success = shots * 25 + (150 if trailer else 0) + rnd.randint(0, 80)
    tags = ["Roguelike", "Action"] if i % 3 else ["Cozy", "Farming Sim"]
    discarded = 1 if i % 20 == 19 else 0
    con.execute("insert into games values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (gid, "STEAM", str(1000 + i), f"Game {i}", "dev", "pub", json.dumps([tags[0]]), json.dumps(tags), str(rel), int(i % 2 == 0), None,
                 9.99 + i % 10, 0, f"https://store.steampowered.com/app/{1000+i}/", None, f"{rel} 00:00:00.000000", 40 + i % 50, discarded))
    for typ, days, mult in (("H24", 1, .1), ("W1", 7, .4), ("M1", 30, 1.0)):
        tot = int(success * mult); cap = dt.datetime.combine(rel, dt.time(12)) + dt.timedelta(days=days)
        extra = json.dumps({"has_trailer": trailer, "screenshot_count": shots, "description_length": desc, "placeholder_description": False})
        con.execute("insert into game_snapshots(game_id,captured_at,snapshot_type,total_reviews,total_positive,total_negative,current_players,steamspy_estimate,extra) values(?,?,?,?,?,?,?,?,?)",
                    (gid, cap.strftime("%Y-%m-%d %H:%M:%S.%f"), typ, tot, int(tot * .9), tot - int(tot * .9), tot // 3, tot * 40, extra))
    for k in range(rnd.randint(0, 3 + shots // 3)):
        pd_ = rel + dt.timedelta(days=rnd.randint(-70, 20))
        con.execute("insert into social_posts(game_id,platform,posted_at,views) values(?,?,?,?)", (gid, rnd.choice(["REDDIT", "TIKTOK", "YOUTUBE"]), f"{pd_} 10:00:00.000000", rnd.randint(100, 50000)))
# upcoming games
for j, (name, days) in enumerate((("Soon A", 40), ("Soon B", 200), ("Far C", 700))):
    gid += 1; con.execute("insert into games(id,platform,external_id,title,genres,tags,release_date,price,discarded) values(?,?,?,?,?,?,?,?,?)",
                          (gid, "STEAM", f"9{j}", name, json.dumps(["Roguelike"]), json.dumps(["Roguelike"]), str(today + dt.timedelta(days=days)), 14.99, 0))
con.execute("insert into projects(name,description,genre,concept_data,simulator_data,discount_plan) values(?,?,?,?,?,?)", ("My Roguelite", "desc", "Roguelike", json.dumps({"title": "X", "pitch": "y"}), json.dumps({"score": 71}), json.dumps({"launch": 15})))
con.commit(); con.close()

def run(argv):
    sys.argv = ["x", "--db", path] + argv; b = io.StringIO()
    with contextlib.redirect_stdout(b), contextlib.redirect_stderr(io.StringIO()): gt.main()
    return b.getvalue()
out = run(["info"]); assert "Giochi Steam: 63" in out and "scartati dal quality filter: 3" in out and "con snapshot a +1 mese: 60" in out, out; print(out.splitlines()[3:6])
o = os.path.join(d, "g.json"); md = os.path.join(d, "g.md")
run(["genre", "--tag", "Roguelike", "--mine", "screenshot_count=8", "--mine", "price=14.99", "--md", md, "-o", o])
r = json.load(open(o)); txt = open(md, encoding="utf-8").read()
assert r["n_games"] == 38 - 0 or r["n_games"] > 30, r["n_games"]   # Roguelike tag, discarded excluded, upcoming have no snapshots
bv = {x["feature"]: x for x in r["best_vs_rest"]}
assert bv["screenshot_count"]["median_best"] > bv["screenshot_count"]["median_rest"] and bv["screenshot_count"]["rho_log_reviews_d30"] > 0.5, bv["screenshot_count"]
mine = {m["feature"]: m for m in r["mine"]}; assert 0 < mine["screenshot_count"]["percentile"] < 100 and mine["price"]["n"] > 10
assert "Il tuo gioco nella distribuzione" in txt and "sola lettura" in txt; print("genre ok: n =", r["n_games"], "| screenshots rho", bv["screenshot_count"]["rho_log_reviews_d30"], bv["screenshot_count"]["strength"], "| mine", mine["screenshot_count"]["percentile"])
assert run(["genre", "--tag", "roguelike", "--tag", "cozy", "--all", "-o", o]) is not None and json.load(open(o))["n_games"] == 0
r2 = json.load(open(os.path.join(d, "g.json"))); 
run(["genre", "--tag", "Cozy", "--include-discarded", "-o", o]); n_inc = json.load(open(o))["n_games"]; run(["genre", "--tag", "Cozy", "-o", o]); n_exc = json.load(open(o))["n_games"]; assert n_inc >= n_exc; print("discarded handling ok", n_exc, n_inc)
c = os.path.join(d, "c.json"); run(["comps", "--appids", "1000", "1001", "-o", c]); cj = json.load(open(c)); assert {x["appid"] for x in cj} == {"1000", "1001"} and cj[0]["reviews_d30"] and "_post_days" not in cj[0]
m = run(["marketing", "--tag", "Roguelike"]); assert "-30..-8" in m and "Mix di piattaforme" in m; print("marketing ok")
w = run(["window", "--tag", "Roguelike", "--days", "365"]); assert "Soon A" in w and "Soon B" in w and "Far C" not in w; print("window ok")
p = run(["project", "--name", "roguelite"]); assert "My Roguelite" in p and "71" in p; print("project ok")
try:
    ro = gt.connect(path); ro.execute("insert into projects(name) values('x')"); raise SystemExit("WRITE SUCCEEDED: not read-only!")
except sqlite3.OperationalError as e: print("read-only enforced:", e)
for bad in (["--db", os.path.join(d, "nope.db"), "info"],):
    sys.argv = ["x"] + bad
    try: gt.main()
    except SystemExit as e: assert "not found" in str(e); print("missing db -> clear error")
open(os.path.join(d, "other.db"), "w").close(); sqlite3.connect(os.path.join(d, "other.db")).execute("create table t(x)")
try: gt.connect(os.path.join(d, "other.db"))
except SystemExit as e: assert "does not look like" in str(e); print("wrong db -> clear error")
print("ALL GT_CORPUS TESTS PASSED")
