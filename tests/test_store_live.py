"""Live store pages: Steam Early Access questionnaire (all six answers, readability limit, promise warnings), accessibility block,
freshness against decisions / waves / gates, and how STATUS.html shows them (escaped, with Copy buttons and an alert when stale)."""
import os, sys, json, tempfile, time, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "research"))
import common
def no_net(*a, **k): raise AssertionError("must not use the network")
common.http_get = no_net
import store_kit as sk, status_page as sp

HOSTILE = "<img src=x onerror=alert(1)>"
root = tempfile.mkdtemp(); L = os.path.join(root, "launch"); os.makedirs(os.path.join(L, "fg", "waves")); os.makedirs(os.path.join(root, "docs", "gates"))
Q = {k: f"Answer for {k}." for k, _ in sk.EA_QUESTIONS}
kit = {"game": "G", "verified_on": "2026-10-09", "updated": "2026-10-09",
       "steam": {"limits": {"short_description": 300, "tags": 20}, "fields": [{"key": "title", "value": "G"}, {"key": "short_description", "value": "A game."}],
                 "long_description": {"format": "bbcode", "blocks": [{"type": "text", "value": "[b]Early Access[/b] single-player today."}]}, "tags": [{"tag": "Roguelite"}],
                 "early_access": {"verified_on": "2026-10-09", "source": "https://partner.steamgames.com/doc/store/earlyaccess",
                                  "questions": [{"key": k, "label": lab, "value": Q[k]} for k, lab in sk.EA_QUESTIONS]},
                 "accessibility": {"intro": "Options:", "features": [{"label": "Reduce motion " + HOSTILE, "value": "no head bob"}, {"label": "Text size", "value": "larger"}]}},
       "itch": {"limits": {"tagline": 120, "tags": 10}, "fields": [{"key": "title", "value": "G"}, {"key": "tagline", "value": "t"}], "long_description": {"format": "markdown", "blocks": [{"type": "text", "value": "# G"}]}, "tags": [{"tag": "x"}],
                "accessibility": {"features": [{"label": "Text size", "value": "larger"}]}}}
errs, warns, stats = sk.validate(kit)
assert not errs, errs
assert stats["steam"]["ea_why"] == len(Q["why"]) and stats["steam"]["accessibility_features"] == 2 and stats["itch"]["accessibility_features"] == 1
assert [k for k, _ in sk.EA_QUESTIONS] == ["why", "duration", "full_vs_ea", "current_state", "pricing", "community"]
# missing answer -> error; too long -> warning (no Valve limit) or error (declared limit); promises -> warning; no "Early Access" in the description -> warning
k2 = json.loads(json.dumps(kit)); k2["steam"]["early_access"]["questions"] = k2["steam"]["early_access"]["questions"][1:]
assert any("Why Early Access?" in e for e in sk.validate(k2)[0])
k3 = json.loads(json.dumps(kit)); k3["steam"]["early_access"]["questions"][1]["value"] = "x" * 1300
assert any("'duration' has 1300 characters" in w for w in sk.validate(k3)[1]) and not sk.validate(k3)[0]
k3["steam"]["early_access"]["limits"] = {"duration": 500}; assert any("'duration' has 1300" in e for e in sk.validate(k3)[0])
k4 = json.loads(json.dumps(kit)); k4["steam"]["early_access"]["questions"][2]["value"] = "Co-op is guaranteed and the game will be released in March 2027."
assert sum("sounds like a promise" in w for w in sk.validate(k4)[1]) == 1
k5 = json.loads(json.dumps(kit)); k5["steam"]["long_description"]["blocks"][0]["value"] = "Single-player."; assert any("does not say the game is in Early Access" in w for w in sk.validate(k5)[1])
k6 = json.loads(json.dumps(kit)); k6["itch"]["accessibility"]["features"] = []; assert any("accessibility block without features" in e for e in sk.validate(k6)[0])
# rendering and export
md = sk.to_md(kit)
assert "### Early Access: le domande di Steam" in md and "#### Why Early Access?" in md and "### Accessibilità (da copiare)" in md and "[list]" in md and "[*][b]Text size[/b]: larger" in md
files = sk.export(kit, os.path.join(root, "kit"))
assert sum("steam_early_access_" in f for f in files) == 6 and any(f.endswith("steam_accessibility.txt") for f in files) and any(f.endswith("itch_accessibility.txt") for f in files)
assert open(next(f for f in files if f.endswith("itch_accessibility.txt")), encoding="utf-8").read().startswith("- **Text size**: larger")

# freshness: the kit against decisions (00-intenzioni.md headings), waves and gate docs
json.dump(kit, open(os.path.join(L, "store_kit.json"), "w"))
open(os.path.join(L, "00-intenzioni.md"), "w", encoding="utf-8").write("# Intenzioni\n## 2026-10-07 · prima\n## 2026-10-09 · Early Access\n")
fr = sk.freshness(L); assert fr == {"kit_date": "2026-10-09", "stale": False, "newer": []}, fr
open(os.path.join(L, "00-intenzioni.md"), "a", encoding="utf-8").write("## 2026-10-12 · lingue\n")
json.dump({"wave": 6, "date": "2026-10-11", "testers": []}, open(os.path.join(L, "fg", "waves", "w06-2026-10-11.json"), "w"))
fr = sk.freshness(L); assert fr["stale"] and ("ultima decisione in 00-intenzioni.md", "2026-10-12") in fr["newer"] and ("ultima ondata del focus group", "2026-10-11") in fr["newer"]
g = os.path.join(root, "docs", "gates", "48-x.md"); open(g, "w").write("x"); future = time.mktime((2026, 10, 15, 12, 0, 0, 0, 0, -1)); os.utime(g, (future, future))
assert any(w.startswith("ultimo gate (48-x.md)") for w, _ in sk.freshness(L)["newer"])
kit_no_date = dict(kit); kit_no_date.pop("updated"); json.dump(kit_no_date, open(os.path.join(L, "store_kit.json"), "w"))
assert sk.freshness(L)["kit_date"] == dt.date.today().isoformat()                       # no "updated": the file date

# STATUS.html: Marketing tab shows the questionnaire and accessibility (escaped, copyable) and says the pages are stale; Riepilogo alert
json.dump(kit, open(os.path.join(L, "store_kit.json"), "w"))
json.dump({"game": "G"}, open(os.path.join(L, "status.json"), "w"))
page = sp.build(L, "private", [], [], set(), dt.date(2026, 10, 15))
body = page.split("<script>")[0]
assert "Early Access: le domande di Steam" in page and "Approximately how long will this game be in Early Access?" in page and page.count('class="copy"') >= 9
assert "Accessibilità" in page and "Reduce motion &lt;img" in page and "<img src=x" not in body
assert "Pagine store da aggiornare" in page and "Il kit è del 15 ott 2026" not in page and "Il kit è del 9 ott 2026" in page
alerts = page[page.index("<h2", page.index('id="p-riepilogo"')):page.index('id="p-gioco"')]
assert "Pagine store da aggiornare: il kit è del 2026-10-09" in alerts
kit["updated"] = "2026-10-15"; json.dump(kit, open(os.path.join(L, "store_kit.json"), "w"))
page = sp.build(L, "private", [], [], set(), dt.date(2026, 10, 15))
assert "Pagine store aggiornate" in page and "Pagine store da aggiornare" not in page
print("ALL STORE_LIVE TESTS PASSED")
