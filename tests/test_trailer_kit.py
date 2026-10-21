"""trailer_kit.py offline tests: knowledge base, storyboard checks, build outputs, status tab, measuring (ffmpeg if present),
tempo estimate, code-made audio, QA of a render and the blind panel."""
import copy, csv, json, math, os, shutil, struct, subprocess, sys, tempfile, wave
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import trailer_kit as tk

TMP = tempfile.mkdtemp()

# ---------------------------------------------------------------- knowledge base
C = tk.craft()
ids = [r["id"] for r in C["rules"]]
assert len(ids) == len(set(ids)) and len(ids) >= 25, "unique rule ids"
for r in C["rules"]:
    for k in ("id", "topic", "rule", "rule_it", "strength", "applies_to", "sources"):
        assert r.get(k), (r.get("id"), k)
    assert r["strength"] in ("platform_doc", "measured", "expert_opinion", "third_party", "internal"), r["id"]
    for s in r["sources"]:
        assert s.get("url") and s.get("date") and s.get("what"), (r["id"], s)
assert any(r["id"] == "ai-disclosure" and "DA VERIFICARE" in r["sources"][0]["what"] for r in C["rules"]), "AI disclosure flagged [DA VERIFICARE]"
assert len(C["negative_base"]) >= 15 and any("AI" in x for x in C["negative_base"]) and any("voice" in x for x in C["negative_base"])
assert C["specs"]["loudness"]["integrated_lufs"] == -14 and C["specs"]["vertical"]["safe_px"]["bottom"] == 484
assert all(s.get("licence") and s.get("url") for s in C["asset_sources"])
print("craft json ok:", len(ids), "rules,", len(C["negative_base"]), "negative items")

# ---------------------------------------------------------------- a minimal valid spec
def shot(i, fmt, t0, t1, source="gameplay", text="-", **kw):
    d = dict(id=i, format=fmt, t0=t0, t1=t1, section="S", source=source, screen="something happens", camera="still", text=text, audio="a sound",
             record={"scene": "hall", "take": f"take_{i}"} if source != "card" else {"scene": "card"})
    d.update(kw); return d

SPEC = {
    "game": "Test Game", "version": "v1", "date": "2026-10-21", "status": "prompt",
    "brand": {"credit": "StudioX", "forbidden_names": ["Alice"]},
    "formats": [{"id": "main", "aspect": "16:9", "res": "1920x1080", "target_s": 12, "platforms": ["Steam"]},
                {"id": "vertical30", "aspect": "9:16", "res": "1080x1920", "target_s": 6, "platforms": ["TikTok"]},
                {"id": "gif", "aspect": "16:9", "derive_from": "main"}],
    "shots": [shot("M1", "main", 0, 2.5), shot("M2", "main", 2.5, 5, text="Stack higher. Earn more.", similar_group="t"),
              shot("M3", "main", 5, 8.5, source="ui", action="a card is bought", text="Buy perks"), shot("END", "main", 8.5, 12, source="card", text="Wishlist · StudioX"),
              shot("V1", "vertical30", 0, 1.8), shot("VEND", "vertical30", 1.8, 6, source="card", text="Wishlist · StudioX", text_box=[100, 400, 700, 600], text_cap_px=70)],
    "music": {"voice": False, "rules": ["one bed"], "sync": [{"t": 1.0, "what": "impact"}]},
    "assets": [{"id": "A1", "kind": "music", "what": "track", "plan": "game", "licence": "CC0", "status": "ok"}],
    "open_questions": [{"q": "Which CTA?", "default": "Wishlist", "why": "one CTA"}],
    "concept": {"five_lines": ["one", "two", "three", "four", "five"]},
    "panel": {"anchors": [{"name": "A", "src": "a", "band": [70, 80]}, {"name": "B", "src": "b", "band": [60, 70]}, {"name": "C", "src": "c", "band": [20, 30]}]},
    "prompt": {"intro": ["Intro paragraph."], "story": ["Act one."], "rules_applied": ["hook-gameplay-5s", "steam-microtrailer"], "negative_extra": ["no clipping"],
               "owner_notes": ["note"], "edit_rules": ["hard cuts"]},
}
iss = tk.check_spec(SPEC)
assert not [x for x in iss if x[0] == "ERROR"], iss
print("valid spec: no errors", [m for _, m in iss])

def errors_after(mut):
    s = copy.deepcopy(SPEC); mut(s)
    return [m for lv, m in tk.check_spec(s) if lv == "ERROR"]

def first(s, i):
    return next(x for x in s["shots"] if x["id"] == i)

cases = {
    "first cut": lambda s: (first(s, "M1").update(t1=4.0), first(s, "M2").update(t0=4.0)),
    "before the first gameplay": lambda s: (first(s, "M1").update(source="card")),
    "needs": lambda s: first(s, "M2").update(text="Stack higher earn more tips and never ever drop the tower okay"),
    "forbidden word": lambda s: first(s, "M2").update(text="Made with AI"),
    "name": lambda s: first(s, "M2").update(text="By Alice"),
    "voice-over": lambda s: s["music"].update(voice=True),
    "non-commercial": lambda s: s["assets"].append({"id": "A2", "licence": "CC-BY-NC 4.0"}),
    "safe zone": lambda s: first(s, "VEND").update(text_box=[0, 1700, 900, 200]),
    "phone legibility": lambda s: first(s, "VEND").update(text_cap_px=30),
    "credit line": lambda s: first(s, "END").update(text="Wishlist now"),
    "without an action": lambda s: first(s, "M3").pop("action"),
    "gap/overlap": lambda s: first(s, "M2").update(t0=2.7),
    "still UI": lambda s: first(s, "M3").update(static_s=1.6),
    "length": lambda s: first(s, "END").update(t1=20),
    "record.scene": lambda s: first(s, "M2").update(record={}),
}
for needle, mut in cases.items():
    e = errors_after(mut)
    assert any(needle in m for m in e), (needle, e)
print("check catches:", ", ".join(cases))
# oner beats allow a long first shot when the decisive beat is early
e = errors_after(lambda s: (first(s, "M1").update(t1=4.0, oner_beats=[1.0, 2.5]), first(s, "M2").update(t0=4.0)))
assert not any("first cut" in m for m in e), e
# threes rule is a warning
s4 = copy.deepcopy(SPEC)
s4["shots"] = [shot(f"M{i}", "main", i * 2.0, i * 2.0 + 2, similar_group="crash") for i in range(5)] + [shot("END", "main", 10, 12, source="card", text="Wishlist · StudioX")] + SPEC["shots"][4:]
assert any("similar shots" in m for lv, m in tk.check_spec(s4) if lv == "WARN")
print("oner beats and threes rule ok")

# ---------------------------------------------------------------- build outputs
out = os.path.join(TMP, "launch", "trailer", "v1")
os.makedirs(out)
with open(os.path.join(out, "credits-ledger.csv"), "w", encoding="utf-8", newline="") as f:      # an older line must survive the rebuild
    w = csv.DictWriter(f, fieldnames=tk.LEDGER_FIELDS); w.writeheader(); w.writerow({"id": "SYN-whoosh-1", "file": "a.wav", "licence": "own"})
bench = [dict(name="Rival", appid=1, reviews=100, pct=90, trailer_s=60.0, first_cut_s=2.0, cuts_first_5s=2, avg_shot_s=2.0, avg_shot_by_third=[2, 2, 2],
              lufs_i=-14.0, true_peak=-1.2, bpm=120.0, frozen_n=0, role="", hook_0_3s="crash", text_cards="", music="", structure="", ending="", lesson="open on the payoff")]
k = tk.build(SPEC, out, bench)
for fn in ("PROMPT.md", "storyboard.md", "storyboard.json", "assets-plan.md", "credits-ledger.csv", "recording-brief.md", "recording-brief.json", "qa-checklist.md", "kit.json"):
    assert os.path.getsize(os.path.join(out, fn)) > 50, fn
P = open(os.path.join(out, "PROMPT.md"), encoding="utf-8").read()
for needle in ("Domande aperte", "Which CTA?", "MASTER PROMPT", "NEGATIVE PROMPT", "no clipping", "[hook-gameplay-5s]", "Shot list: main", "M2 [02.50-05.00]", "Rival", "open on the payoff", "StudioX"):
    assert needle in P, needle
assert P.count("````") == 4, "both prompts in fenced blocks"
assert len(tk.negative_list(SPEC)) == len(C["negative_base"]) + 1
rows = list(csv.DictReader(open(os.path.join(out, "credits-ledger.csv"), encoding="utf-8")))
assert {r["id"] for r in rows} == {"SYN-whoosh-1", "A1"}, rows
b = json.load(open(os.path.join(out, "recording-brief.json"), encoding="utf-8"))
assert {t["take"] for t in b["takes"]} == {"take_M1", "take_M2", "take_M3", "take_V1"} and all(t["used_by"] for t in b["takes"])
kit = json.load(open(os.path.join(out, "kit.json"), encoding="utf-8"))
assert kit["prompt"].startswith("# MASTER TRAILER PROMPT") and kit["negative"].startswith("NEGATIVE PROMPT") and len(kit["qa"]) >= 15
print("build ok:", len(P.split()), "words in PROMPT.md")

# ---------------------------------------------------------------- status page tab
import html as H
import status_page as sp
sec = tk.status_section(os.path.join(TMP, "launch"), sp.esc, sp.copy_btn)
assert sec and "Storyboard main" in sec and "Trailer dei concorrenti" in sec and "Controlli di qualità" in sec
import re
m = re.search(r'data-copy="([^"]*)"', sec)
assert H.unescape(m.group(1)) == kit["prompt"] + "\n" + kit["negative"], "one-click copy = positive + negative prompt"
assert "<script" not in sec.lower() or "&lt;script" in sec.lower()
evil = copy.deepcopy(SPEC); evil["shots"][1]["screen"] = "<script>alert(1)</script>"
tk.build(evil, out, None)
sec2 = tk.status_section(os.path.join(TMP, "launch"), sp.esc, sp.copy_btn)
assert "<script>alert(1)" not in sec2 and "&lt;script&gt;" in sec2, "file text is escaped"
json.dump({"game": "Test Game"}, open(os.path.join(TMP, "launch", "status.json"), "w"))
page = sp.build(os.path.join(TMP, "launch"), "private", [], [], set(), __import__("datetime").date(2026, 10, 21))
assert 'id="tab-trailer"' in page and 'id="p-trailer"' in page
page_pub = sp.build(os.path.join(TMP, "launch"), "publisher", [], [], set(), __import__("datetime").date(2026, 10, 21))
assert 'id="tab-trailer"' not in page_pub, "publisher version hides the trailer tab"
print("status tab ok (copy button, escaping, hidden for publisher)")

# ---------------------------------------------------------------- shot stats, tempo, synth
st = tk.shot_stats([2.0, 4.0, 6.0], 9.0)
assert st["shots"] == 4 and st["first_cut_s"] == 2.0 and st["cuts_first_5s"] == 2 and st["avg_shot_s"] == 2.25 and len(st["avg_shot_by_third"]) == 3
sr = 8000
clicks = [0.0] * (sr * 16)
for b_ in range(int(16 * 2)):                       # 120 BPM click track
    s0 = int(b_ * 0.5 * sr)
    for i in range(200):
        clicks[s0 + i] = math.sin(2 * math.pi * 1000 * i / sr) * math.exp(-i / 60)
bpm = tk.tempo_from_pcm(clicks, sr)
assert bpm and min(abs(bpm - 120), abs(bpm - 60) * 2, abs(bpm - 240) / 2) <= 3, bpm
print("tempo estimate on a 120 BPM click track:", bpm)
for kind in ("whoosh", "pop", "tick", "hit", "riser", "stinger"):
    a = tk.synth(kind, 3); b2 = tk.synth(kind, 3)
    assert a == b2 and len(a) > 1000 and max(abs(x) for x in a) > 0, kind
mus = tk.synth("music", 1, bpm=120, bars=2)
assert abs(len(mus) / tk.SR - 4.0) < 0.05, len(mus) / tk.SR
wav = os.path.join(TMP, "audio", "w.wav")
r = subprocess.run([sys.executable, tk.__file__, "synth", "whoosh", wav, "--seed", "2", "--ledger", os.path.join(out, "credits-ledger.csv"), "--credit", "StudioX"],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stderr
with wave.open(wav) as wf:
    assert wf.getframerate() == 44100 and wf.getnchannels() == 1 and 0.5 < wf.getnframes() / 44100 < 0.6
led = {x["id"]: x for x in csv.DictReader(open(os.path.join(out, "credits-ledger.csv"), encoding="utf-8"))}
assert led["SYN-whoosh-2"]["licence"] == "own" and led["SYN-whoosh-2"]["credit_line"] == "StudioX" and "no generative model" in led["SYN-whoosh-2"]["notes"]
print("synth ok (deterministic, wav written, ledger line added)")

# ---------------------------------------------------------------- QA of a render (from a measure dict) and the panel
m = dict(duration_s=12.1, first_cut_s=2.0, avg_shot_by_third=[2, 2, 3], lufs_i=-14.3, true_peak_dbtp=-1.4, frozen=[], black=[], width=1920, height=1080, fps=60.0, vcodec="h264", acodec="aac")
res = {c["id"]: c["ok"] for c in tk.qa_render(m, SPEC, "main")}
assert all(res.values()), res
bad = dict(m, first_cut_s=4.8, lufs_i=-9.0, true_peak_dbtp=0.2, frozen=[[3.0, 4.6]], black=[[0.0, 0.5]], width=1280)
res = {c["id"]: c["ok"] for c in tk.qa_render(bad, SPEC, "main")}
assert not any(res[k] for k in ("first_cut", "loudness", "true_peak", "static", "black", "spec")), res
try:
    tk.panel_init(SPEC, os.path.join(TMP, "missing.mp4"), TMP); raise AssertionError("panel must refuse without a render")
except SystemExit:
    pass
render = os.path.join(TMP, "render.mp4"); open(render, "wb").write(b"x")
key = tk.panel_init(SPEC, render, os.path.join(TMP, "panel"))
assert len(key["items"]) == 4 and sorted(i["code"] for i in key["items"]) == ["T1", "T2", "T3", "T4"]
assert os.path.exists(os.path.join(TMP, "panel", "panel-brief.md"))
code = {i["name"]: i["code"] for i in key["items"]}
sc = lambda c, v, wsh="forse": dict(tester="A1", code=c, hook=v, clarity=v, fun=v, pace=v, wishlist=wsh)
results = {"scores": [sc(code["A"], 7.8, "sì"), sc(code["B"], 6.8), sc(code["C"], 2.8, "no"), sc(code["Test Game"], 7.0)]}
r = tk.panel_score(results, key)
rows = {x["name"]: x for x in r["rows"]}
assert r["anchor_shift"] == 3.0 and rows["Test Game"]["normalised"] == 67.0 and rows["A"]["wishlist_pct"] == 100 and not r["recalibrate"], r
r2 = tk.panel_score({"scores": [sc(code["A"], 9.9), sc(code["B"], 9.9), sc(code["C"], 9.9), sc(code["Test Game"], 7.0)]}, key)
assert r2["recalibrate"], "an anchor drifting more than 8 points forces recalibration"
print("qa and panel ok")

# ---------------------------------------------------------------- real measurement with ffmpeg (skipped without it)
if shutil.which("ffmpeg") and shutil.which("ffprobe"):
    vid = os.path.join(TMP, "t.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-filter_complex",
                    "testsrc=d=2:s=320x180:r=30[a];color=c=red:d=2:s=320x180:r=30[b];testsrc2=d=2:s=320x180:r=30[c];[a][b][c]concat=n=3:v=1:a=0[v];"
                    "sine=f=440:d=6:sample_rate=48000,volume=0.3[au]", "-map", "[v]", "-map", "[au]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", vid], check=True)
    mm = tk.measure(vid)
    assert abs(mm["duration_s"] - 6.0) < 0.2 and mm["width"] == 320 and mm["vcodec"] == "h264" and mm["acodec"] == "aac", mm
    assert mm["first_cut_s"] and abs(mm["first_cut_s"] - 2.0) < 0.2 and any(abs(c - 4.0) < 0.2 for c in mm["cut_times"]), mm["cut_times"]
    assert mm["lufs_i"] is not None and -36 < mm["lufs_i"] < -28 and -31 < mm["true_peak_dbtp"] < -24, mm
    assert any(a_ <= 2.3 and b_ >= 3.7 for a_, b_ in mm["frozen"]), ("the red still 2-4 s is detected", mm["frozen"])
    print("measure on a real file ok:", {k: mm[k] for k in ("first_cut_s", "avg_shot_s", "lufs_i", "true_peak_dbtp", "frozen")})
else:
    print("SKIP measure on a real file: ffmpeg not installed")

# ---------------------------------------------------------------- CLI check exit codes
specp = os.path.join(out, "trailer.json"); json.dump(SPEC, open(specp, "w", encoding="utf-8"))
assert subprocess.run([sys.executable, tk.__file__, "check", specp], capture_output=True).returncode == 0
badp = os.path.join(out, "bad.json"); s5 = copy.deepcopy(SPEC); s5["music"]["voice"] = True; json.dump(s5, open(badp, "w", encoding="utf-8"))
assert subprocess.run([sys.executable, tk.__file__, "check", badp], capture_output=True).returncode == 1
r = subprocess.run([sys.executable, tk.__file__, "build", badp, "--strict", "--out-dir", os.path.join(TMP, "strict")], capture_output=True, text=True)
assert r.returncode != 0 and not os.path.exists(os.path.join(TMP, "strict", "PROMPT.md"))
print("CLI exit codes ok")
shutil.rmtree(TMP, ignore_errors=True)
print("ALL TRAILER_KIT TESTS PASSED")
