"""Offline: census by release date, not success; no identifiers/metrics in the blinded roster draft."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/research"))
import demo_intake as intake

start, end = dt.date(2026, 8, 1), dt.date(2026, 8, 7)


def row(aid, date):
    return (f'<a class="search_result_row ds_collapse_flag" data-ds-appid="{aid}" '
            'data-tooltip-html="98% positive"><span class="title">Secret hit</span>'
            f'<div class="col search_released">{date}</div></a>')


def page(html, total):
    return {"results_html": html, "total_count": total}


pages = iter([page(row("1234", "Aug 3, 2026") + row("1235", "Aug 2, 2026"), 4),
              page(row("1235", "Aug 2, 2026") + row("1111", "Jul 31, 2026"), 4)])
result = intake.collect(start, end, "US", 3, lambda url: next(pages), 2)
assert result["complete"] and [c["appid"] for c in result["candidates"]] == [1235, 1234]
assert "Secret" not in str(result) and "positive" not in str(result)
for response in ({}, page(row("12", "Coming Soon"), 1), page("unrecognized markup", 5)):
    assert not intake.collect(start, end, "US", 1, lambda u: response)["complete"]
assert intake.collect(start, end, "US", 1, lambda u: page("", 0))["complete"]
assert not intake.collect(start, end, "US", 1, lambda u: page(row("1234", "Aug 3, 2026"), 3))["complete"]
with tempfile.TemporaryDirectory() as tmp:
    os.environ["GLS_HOME"] = tmp
    snap, out = Path(tmp) / "source.json", Path(tmp) / "curator.json"
    snap.write_text(json.dumps(result), encoding="utf-8")
    intake.prepare_roster(snap, out)
    records = json.loads(out.read_text(encoding="utf-8"))
    assert len(records["cases"]) == 2 and records["cases"][0]["group"] != records["cases"][1]["group"]
    assert all(c["status"] == "insufficient" and "appid" not in c for c in records["cases"])
    try:
        intake.prepare_roster(snap, out)
    except FileExistsError:
        pass
    else:
        raise AssertionError("roster editabile sovrascritto")
print("demo intake ok: ordine cronologico, completezza, assenze, alias e bozza non sovrascritta")
