"""Offline tests for the Reddit backend chain (reddit_backends.py) and its use in reddit_rules, reddit_trends and case_studies:
fake HTTP, no network. Order and fallbacks (403 / 429 / HTML block page take a backend out), Arctic Shift thread with nested
comments, RSS thread, rules from the archive sidebar, ThreadSnoop only with its key (never printed), listings sorted by score,
"new" preferring RSS over the archive, and the backend named in every result."""
import os, sys, json, tempfile, urllib.error, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(HERE, "..", "scripts", "research")
sys.path.insert(0, R)
TMP = tempfile.mkdtemp()
os.environ["GLS_HOME"] = os.path.join(TMP, "home")
os.environ["GLS_REACH"] = "off"
for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "THREADSNOOP_API_KEY", "GLS_REDDIT_BACKENDS", "GLS_ARCTIC", "GLS_ENV_FILE"):
    os.environ.pop(k, None)
import common
import reddit_backends as rb

CALLS = []
ROUTES = {}


def http(url, **kw):
    CALLS.append((url, dict(kw.get("headers") or {})))
    for k in sorted(ROUTES, key=len, reverse=True):
        if k in url:
            v = ROUTES[k]
            if isinstance(v, int):
                raise urllib.error.HTTPError(url, v, "err", {}, None)
            return (v if isinstance(v, str) else json.dumps(v)).encode("utf-8")
    raise urllib.error.HTTPError(url, 404, "no route", {}, None)


common.http_get = http


def reset(**routes):
    rb.reset()
    rb.configure(rate=0, backends=None)
    ROUTES.clear()
    ROUTES.update(routes)
    CALLS.clear()


POST = dict(id="1xkwrxr", title="Continue my wishlist journey 3400->7400", author="dev", subreddit="IndieGameWishlist", score=12, num_comments=3,
            created_utc=1793000000, permalink="/r/IndieGameWishlist/comments/1xkwrxr/continue/", selftext="We went from 3,400 to 7,400 wishlists after Next Fest.",
            is_self=True)
TREE = dict(data=[dict(kind="t1", data=dict(id="c1", author="a", score=2, body="How?", created_utc=1793000100,
                                            replies=dict(data=dict(children=[dict(kind="t1", data=dict(id="c2", author="dev", score=3, body="Reddit and a small YT channel", created_utc=1793000200, replies=""))])))),
                  dict(kind="t1", data=dict(id="c3", author="b", score_hidden=True, score=1, body="nice", created_utc=1793000300, replies=""))])
URL = "https://www.reddit.com/r/IndieGameWishlist/comments/1xkwrxr/"

# ---- thread: JSON blocked (403 then old.reddit HTML login page) -> Arctic Shift with nested comments
reset(**{"www.reddit.com/comments/1xkwrxr/.json": 403, "old.reddit.com/comments/1xkwrxr/.json": "<html><body>login</body></html>",
         "arctic-shift.photon-reddit.com/api/posts/ids": dict(data=[POST]), "arctic-shift.photon-reddit.com/api/comments/tree": TREE})
t = rb.thread(URL)
assert t["ok"] and t["backend"] == "arctic" and t["scores"] == "archive" and t["label"] == "[FATTO]", t["attempts"]
assert [c["depth"] for c in t["comments"]] == [0, 1, 0] and t["comments"][2]["score"] is None          # hidden score = unknown, not 1
assert t["post"]["url"].startswith("https://www.reddit.com/r/IndieGameWishlist/comments/1xkwrxr") and t["post"]["published"]
assert "\n@dev: Reddit and a small YT channel" in t["text"] and [b for b, _ in t["attempts"]][:3] == ["reach", "oauth", "json"]
assert "json" in rb._DOWN                                                                             # blocked: not retried this run
print("thread ok: json blocked -> arctic, nested comments, hidden score unknown")

# ---- thread via RSS when the archive is rate limited (429 takes arctic out)
ATOM = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>t3_1xkwrxr</id><title>Continue my wishlist journey</title><author><name>/u/dev</name></author><link href="https://www.reddit.com/r/IndieGameWishlist/comments/1xkwrxr/x/"/>
<published>2026-10-20T10:00:00+00:00</published><content type="html">&lt;p&gt;From 3,400 to 7,400 wishlists&lt;/p&gt;</content></entry>
<entry><id>t1_c1</id><title>/u/a on Continue</title><author><name>/u/a</name></author><link href="https://www.reddit.com/r/x/comments/1xkwrxr/x/c1/"/>
<published>2026-10-20T11:00:00+00:00</published><content type="html">&lt;p&gt;How did you do it?&lt;/p&gt;</content></entry></feed>"""
reset(**{"reddit.com/comments/1xkwrxr/.json": 403, "arctic-shift": 429, "www.reddit.com/comments/1xkwrxr/.rss": ATOM})
t = rb.thread("1xkwrxr")
assert t["ok"] and t["backend"] == "rss" and t["scores"] == "none" and t["comments"][0]["author"] == "a" and "How did you do it?" in t["text"]
assert "arctic" in rb._DOWN and any(o == "HTTP 429" for b, o in t["attempts"] if b == "arctic")
print("thread ok: arctic 429 -> rss with comments")

# ---- nothing answers: [DA VERIFICARE] with every attempt listed; not a Reddit link
reset(**{"reddit.com": 403, "arctic-shift": 429})
t = rb.thread(URL)
assert not t["ok"] and t["label"] == "[DA VERIFICARE]" and {b for b, _ in t["attempts"]} >= {"json", "arctic", "rss", "threadsnoop"}
assert not rb.thread("https://example.com/blog")["ok"]
print("thread ok: all blocked -> [DA VERIFICARE] with attempts")

# ---- rules: archive has no rules -> sidebar sections; subscribers kept
SIDEBAR = "# Subreddit Guidelines\nGIFs and images are preferred. [Links](https://x) to Steam don't get attention.\n\n---\n\n###Recommended Communities:\n/r/gamedev\n\n1. No spam\n2. Self-promotion only on Saturday"
reset(**{"reddit.com/r/IndieDev/about/rules.json": 403, "api/subreddits/rules": dict(data=[]),
         "api/subreddits/search": dict(data=[dict(subscribers=249287, public_description="indie devs", description=SIDEBAR, retrieved_on=1739577600)])})
r = rb.rules("r/IndieDev")
titles = [x["title"] for x in r["rules"]]
assert r["ok"] and r["backend"] == "arctic" and r["subscribers"] == 249287 and "Subreddit Guidelines" in titles and "Self-promotion only on Saturday" in titles, titles
assert "Links to Steam" in r["rules"][0]["text"] and "sidebar" in r["completeness"] and "2025-02-15" in r["completeness"]
assert not any(x.startswith("/r/") for x in titles)
print("rules ok: archive sidebar -> rules, link text kept, completeness dated")

# ---- ThreadSnoop only with its key; the key travels in the header and never in the result
reset(**{"reddit.com": 403, "arctic-shift": 429, "api.threadsnoop.com/v1/subreddits/IndieDev/rules": dict(rules=[dict(short_name="No spam", description="One link a week")])})
assert not rb.rules("IndieDev")["ok"]
os.environ["THREADSNOOP_API_KEY"] = "ts_secret_123"
reset(**{"reddit.com": 403, "arctic-shift": 429, "api.threadsnoop.com/v1/subreddits/IndieDev/rules": dict(rules=[dict(short_name="No spam", description="One link a week")])})
r = rb.rules("IndieDev")
assert r["ok"] and r["backend"] == "threadsnoop" and r["rules"][0]["title"] == "No spam" and "ts_secret_123" not in json.dumps(r)
assert any(h.get("x-api-key") == "ts_secret_123" for u, h in CALLS if "threadsnoop" in u)
os.environ.pop("THREADSNOOP_API_KEY")
print("rules ok: threadsnoop only with the key, key never in the output")

# ---- listings: top by archive score; new prefers RSS (the archive lags)
posts = [dict(POST, id=f"p{i}", title=f"post {i}", score=s, permalink=f"/r/IndieGameWishlist/comments/p{i}/x/") for i, s in enumerate([3, 40, 12])]
reset(**{"reddit.com/r/IndieGameWishlist/top/.json": 403, "reddit.com/r/IndieGameWishlist/new/.json": 403, "api/posts/search": dict(data=posts),
         "www.reddit.com/r/IndieGameWishlist/new/.rss": ATOM})
top = rb.listing("IndieGameWishlist", "top", "month", 10)
assert top["ok"] and top["backend"] == "arctic" and [p["score"] for p in top["posts"]] == [40, 12, 3] and "archivio" in top["note"]
new = rb.listing("IndieGameWishlist", "new", "month", 10)
assert new["ok"] and new["backend"] == "rss"
print("listing ok: top sorted by archive score, new via rss first")

# ---- explicit order (env) and doctor
reset(**{"api/posts/search": dict(data=posts)})
os.environ["GLS_REDDIT_BACKENDS"] = "arctic"
assert rb.order() == ["arctic"] and rb.listing("x", "new", "week", 3)["backend"] == "arctic"
os.environ.pop("GLS_REDDIT_BACKENDS")
reset(**{"reddit.com": 403, "api/posts/search": dict(data=posts)})
d = rb.doctor("IndieDev")
w = {r["backend"]: r["works"] for r in d["rows"]}
assert w["arctic"] and not w["json"] and not w["oauth"] and d["first"] == "arctic"
print("order and doctor ok:", d["first"])

# ---- search needs a subreddit for the archive
reset(**{"reddit.com": 403, "api/posts/search": dict(data=posts[:1])})
assert not rb.search("Wobble", None, 5)["ok"]
s = rb.search("Wobble", "IndieGameWishlist", 5)
assert s["ok"] and s["backend"] == "arctic" and "query=Wobble" in CALLS[-1][0]
print("search ok")

# ---- reddit_rules: anonymous JSON blocked -> chain, backend and completeness in the row
import reddit_rules as rr
reset(**{"reddit.com": 403, "api/subreddits/rules": dict(data=[dict(rules=[dict(short_name="Self-promotion on Saturday only", description="Screenshot Saturday")])]),
         "api/subreddits/search": dict(data=[dict(subscribers=10)])})
o = rr.fetch("IndieDev", None)
assert o["backend"] == "arctic" and o["label"] == "[FATTO]" and o["promo_related_rules"] == [1] and o["subscribers"] == 10 and "error" not in o and o["anonymous_error"]
assert "via arctic" in rr.to_md([o])
print("reddit_rules ok: chain row")

# ---- reddit_trends: RSS blocked -> chain with formats and archive scores
import reddit_trends as rt
reset(**{"reddit.com": 403, "api/posts/search": dict(data=[dict(p, is_self=False, is_video=(i == 1), url="https://v.redd.it/x" if i == 1 else "https://i.redd.it/a.png")
                                                          for i, p in enumerate(posts)])})
top, new, backend, note = rt.fetch_chain("IndieGameWishlist", "month", 50)
assert backend == "arctic" and top[0]["score"] == 40 and top[0]["format"] == "video" and top[1]["format"] == "image" and top[0]["url"].startswith("https://www.reddit.com/r/")
an = rt.analyse(top, new)
assert an["n_top"] == 3
print("reddit_trends ok: fetch_chain via arctic")

# ---- case_studies: a Reddit post-mortem through the chain, numbers from post + comments
import case_studies as cs
reset(**{"reddit.com": 403, "api/posts/ids": dict(data=[POST]), "api/comments/tree": TREE})
dr = cs.fetch_drafts([URL])[0]
assert dr["ok"] and dr["backend"] == "arctic" and dr["has_comments"] and dr["comments_read"] == 3 and "next fest" in dr["events"]
assert any(x["value"] == 7400 for x in dr["numbers"]) and dr["draft"]["source_kind"] == "reddit"
print("case_studies ok: reddit draft via arctic")

print("ALL REDDIT_BACKENDS TESTS PASSED")
