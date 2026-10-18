"""entity_match offline: precision before/after on two hand-labelled real samples (tuning set and held-out set) and unit cases."""
import os, sys, json
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "scripts", "research"))
import entity_match as em

res = {}
for name in ("entity_match_labels.json", "entity_match_heldout.json"):
    with open(os.path.join(here, "fixtures", name), encoding="utf-8") as f:
        r = em.evaluate(json.load(f))
    res[name] = r
    assert r["n"] >= 100 and r["games"] >= 12, r
    assert r["precision_after"] >= 0.95 and r["precision_after"] > r["precision_before"] + 0.3, r   # title-only search ~0.5-0.65
    assert r["recall_after"] >= 0.70, r                                                            # the filter still keeps most real coverage
h = res["entity_match_heldout.json"]
assert h["false_positives"] == 0 and h["recall_after"] >= 0.85, h

g = dict(title="Monitor", appid=4659900, developers=["Small Studio"], publishers=[], words=["Puzzle", "Exploration"], languages=["English"], announced="2024-07-01")
hw = [dict(title="If You're About to Buy a Monitor, Watch This First", text="Good monitors for gaming", published="2026-04-06"),
      dict(title="The Best Monitor At Every Price", text="monitor recommendations", published="2026-08-29")]
assert not any(c["kept"] for c in em.score_batch(hw, g)), "one-word dictionary title + hardware videos must be rejected"
ok = dict(title="Monitor - new puzzle exploration game", text="https://store.steampowered.com/app/4659900/Monitor/", published="2026-07-20")
assert em.score(ok, g)[0] >= em.THRESHOLD, "a Steam link to the app makes even a generic title certain"
old = dict(title="Monitor puzzle game", text="https://store.steampowered.com/app/4659900/", published="2019-01-01")
assert em.score(old, g)[0] == 0, "published before the game existed"
g2 = dict(title="Tidefall", appid=1, developers=["RootWaves"], words=["Action Roguelike"], languages=["English"], announced="2024-01-01")
rb = [dict(title=f"FULL GUIDE to TIDEFALL update in Fisch Roblox #{i}", text="roblox fisch gameplay guide", published="2026-01-17") for i in range(5)]
assert not any(c["kept"] for c in em.score_batch(rb, g2)), "same name on another platform"
g3 = dict(title="Denshattack!", appid=2, developers=["Undercoders"], words=["Trains"], languages=["English"], announced="2024-01-01")
batch = [dict(title=f"Denshattack! gameplay part {i}", text="train game", published="2026-07-20") for i in range(6)] + [dict(title="Denshattack goes insane", text="", published="2026-07-21")]
em.score_batch(batch, g3)
assert all(c["kept"] for c in batch[:6]), "a distinctive coined title + one gaming signal is enough"
assert not batch[6]["kept"], "a one-word title with no other evidence still needs a second signal"
assert em.is_generic("The Wanderer") and not em.is_generic("Funnel Runners") and em.is_weak("SHARKS")
print(f"entity_match ok: tuning set precision {res['entity_match_labels.json']['precision_before']} -> {res['entity_match_labels.json']['precision_after']} "
      f"(recall {res['entity_match_labels.json']['recall_after']}); held-out {h['precision_before']} -> {h['precision_after']} (recall {h['recall_after']})")
