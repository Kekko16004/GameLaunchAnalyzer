"""Decisioni fail-closed prima della fee e scenari con dati parziali. Nessuna rete."""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))

with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"HOME": home, "USERPROFILE": home, "GLS_HOME": home}):
    import launch_gates
    import metrics_track as mt
    import qa
    import status_page as sp

    today = dt.date(2026, 11, 20)
    plan = {"phases": []}
    def payment(raw):
        ctx = dict(st={"gates": raw}, today=today)
        return next(a for _, q, a in qa.faq(ctx) if "Steam Direct" in q)

    def tile(raw):
        return next(t for t in sp.key_tiles({"gates": raw}, None, None, plan, None, today, set()) if t[0] == "Gate superati")

    full = {k: {"state": "pass"} for k in launch_gates.GATE_NAMES}
    full["B"].update(test_stage="collected", evidence="07-community.md#risultati-w02")
    assert "tutti superati" in payment(full) and tile(full)[1] == "4/4"
    for missing in full:
        partial = {k: v for k, v in full.items() if k != missing}
        assert "Non ancora" in payment(partial) and f"Gate {missing}" in payment(partial)
        assert tile(partial)[1] == "3/4" and "esiti non documentati 1 su 4" in tile(partial)[2]
    for bad in [None, [], {}, {"0": [], "A": 0, "B": None, "C": {"state": "?"}}]:
        assert "Non ancora" in payment(bad) and tile(bad)[1] == "n/d"
    for fields, expected in [
        ({"state": "pass"}, "unknown"),
        ({"state": "pass", "test_stage": "scheduled"}, "pending"),
        ({"state": "pass", "test_stage": "collected", "evidence": "  "}, "pending"),
        ({"state": "pending", "test_stage": "collected", "evidence": "report"}, "pending"),
        ({"state": "fail", "test_stage": "collected", "evidence": "report"}, "fail"),
    ]:
        gates = dict(full, B=fields)
        assert launch_gates.assess(gates)["B"]["state"] == expected
        assert "Non ancora" in payment(gates) and tile(gates)[1] == "3/4"
    assert "Non ancora" in payment(dict(full, extra={"state": "pending"}))
    assert "Non ancora" in payment({"extra": {"state": "pass"}})
    assert "rischio supportato" in next(a for _, q, a in qa.faq({"today": today}) if "prevede le vendite" in q)

    rows = [dict(date=str(today), metric="visite", value=10),
            dict(date=str(today - dt.timedelta(days=1)), metric="acquisti", value=2)]
    assert mt.measure({"kind": "ratio", "metric": "acquisti", "of": "visite"}, rows, today)[0] is None
    def status(when, *signals):
        return mt.evaluate({"scenarios": [dict(when=when, signals=signals)]}, rows, today)[0]["status"]
    missing = dict(metric="mancante", op="<", value=1)
    yes, no = (dict(metric="visite", op=op, value=5) for op in (">", "<"))
    assert status("any", no, missing) == status("all", yes, missing) == status("any") == "SENZA DATI"
    assert status("any", yes, missing) == "SCATTATO" and status("all", no, missing) == "OK"
print("Decisioni: gate obbligatori, test raccolto e scenari senza dati verificati.")
