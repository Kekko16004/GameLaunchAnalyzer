"""Offline protocol regressions: no look-ahead, no unverified inputs/actions, no hindsight scoring."""
import csv
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
os.environ["GLS_REACH"] = "off"

with tempfile.TemporaryDirectory() as tmp:
    os.environ["GLS_HOME"] = tmp
    import cohort_bench as cb
    import predictions as pr
    import top_moves as tm

    root = Path(tmp)
    (root / "_raw").mkdir()
    D = dt.date.fromisoformat
    today = D("2026-10-01")

    def write_json(path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    g = dict(release_date="2026-07-01", has_demo=True, n_movies=2, price=7, genres=["Action"], developers=[], publishers=[])
    news = [dict(date="2026-07-02", kinds=["demo"], official=True)]
    for stamp in (None, "", "2026-07-01", "2026-07-02"):
        x = cb.prelaunch_features(dict(g, store_observed_on=stamp), {"name": "app"}, news, 100, "A")
        assert x["demo_pre"] == 0 and not {"trailer", "tier_A", "price_log", "crowd_log", "g_action"}.intersection(x)
    x = cb.prelaunch_features(dict(g, store_observed_on="2026-06-30"), {"name": "app"}, news, 100, None)
    assert x["demo_pre"] == x["trailer"] == 1 and x["g_action"]
    x = cb.prelaunch_features(g, {"name": "app"}, [dict(news[0], date="2026-06-30")], 100, None)
    assert x["demo_pre"] == 1 and "trailer" not in x
    assert cb.prelaunch_features(g, None, None, None, None) == {}
    assert cb.prelaunch_features(g, None, news * 100, None, None) == {}
    assert "tier_A" not in cb.features_from_json(dict(tier="A"))
    assert cb._global_grade(dict(global_tier="A", grade_scope="project", anchor_pack="fixed", visual_batch="x")) is None

    # Many adjacent release weeks do not make D90 outcomes observable when predicting the later week.
    rows = [dict(week=week, release_date=date, checked_d90=checked, y90=9, x={"trailer": int(i % 2)})
            for week, date, checked in (("a", "2026-01-05", "2026-04-06"), ("b", "2026-01-12", "2026-04-13"),
                                        ("c", "2026-01-19", "2026-04-20")) for i in range(50)]
    assert not cb.backtest(rows, "y90")["possible"] and cb.backtest(rows, "y90")["n_test"] == 0
    assert cb._observed_outcome(dict(g, reviews_d90=80, checked_d90="2026-09-01"), 90, today) is None
    assert cb._observed_outcome(dict(g, reviews_d90=80, checked_d90="2026-10-02"), 90, today) is None
    # Late backfill of a mature January outcome in September cannot train an August test.
    rows.extend(dict(week="d", release_date="2026-08-03", checked_d90="2026-11-03", y90=5, x={}) for _ in range(40))
    for r in rows:
        if r["week"] in ("a", "b", "c"):
            r["checked_d90"] = "2026-09-15"
    assert not cb.backtest(rows, "y90")["folds"]

    ds = root / "cohorts"
    ds.mkdir()
    manifest = dict(complete=True, window_complete=True, n_games=1, n_reviews=1, n_store=1, generated_on="2026-08-30")
    row = dict(appid=1, name="X", week="cohort_good", status="keep", grade="B", global_tier="C", grade_scope="global_verified",
               anchor_pack="action/v1@" + "0"*64, visual_batch="b", release_date="2026-07-01", checked_d30="2026-08-12", reviews_d30=9)
    for i, (week, m) in enumerate((("legacy", None), ("partial", dict(manifest, complete=False)), ("bad", {"complete":True}),
                                   ("future", dict(manifest, generated_on="2026-10-02")), ("good", manifest), ("scope", manifest))):
        data = dict(row, appid=i+1, week="cohort_" + week)
        if week == "scope":
            data["grade_scope"] = "project"
        with (ds / f"cohort_{week}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data))
            w.writeheader()
            w.writerow(data)
        if m:
            write_json(ds / f"cohort_{week}.quality.json", m)
    cal = cb.build_calibration(str(ds), today)
    assert cal["quality"] == dict(legacy_weeks=1, incomplete_weeks=3, verified_weeks=2, legacy_grades=2)
    assert cal["n_games"] == 2 and cal["n_graded"] == 1 and cal["legacy_descriptive"]["n"] == 1
    assert cal["milestones"]["d30"]["tiers"]["B"]["n"] == 0 and cal["milestones"]["d30"]["tiers"]["C"]["n"] == 1

    met = dict(protocol="asof-v1", validated=False, model={"keys":["demo_pre"]}, base_rate_bands=[.6,.3,.1,0], bands=[b[0] for b in cb.METRO_BANDS])
    assert cb.score_features(met, {"free":0})["mode"] == "base_rate" and not cb.score_features(met, {"free":0})["levers"]
    assert cb.score_features(met, {})["mode"] == "not_applicable"
    try:
        cb.score_features(dict(met, protocol="old"), {"free":0})
    except ValueError:
        pass
    else:
        raise AssertionError("unversioned/legacy model accepted")
    candidate = dict(feature="demo_pre", supported=True, delta_p1k_pp=20, p1k_after=.4, label="demo")
    meta = dict(strength="utile", validated=True, protocol="asof-v1")
    for change, scored, expected in (({},today.isoformat(), True), (dict(protocol="old"),today.isoformat(), False),
                                      (dict(validated=False),today.isoformat(), False), ({}, "2030-01-01", False)):
        write_json(root / "_raw" / "metro.json", dict(metro=dict(meta, **change), scored_on=scored,
                   score=dict(mode="model", p1k=.2, levers=[candidate])))
        assert any(x["source"] == "metro" for x in tm.candidates(tmp, today, {})) == expected

    # The calendar boundary is strict: future, past and issue-day data cannot close a forecast.
    # Two parallel scenarios may be checked independently; a revision supersedes only its own scenario.
    def item(i, date, **kw):
        return dict(dict(id=i, date=date, metric="x", actual_metric="x", low=10, high=20, series="current"), **kw)
    pr.save(tmp, dict(items=[item("late", "2026-09-11", due="2026-09-10", series="too late"),
                             item("old", "2026-08-01"), item("new", "2026-09-01", due="2026-09-20", until="2026-09-30"),
                             item("plan", "2026-09-03", series="plan", registered_on="2026-09-21")]), today)
    (root / "metrics.csv").write_text("date,metric,value,note\n2026-07-01,x,99,\n2026-08-01,x,13,\n2026-09-10,x,18,\n"
                                     "2026-09-20,x,15,\n2026-10-02,x,99,\n", encoding="utf-8")
    rr = {r["id"]: r for r in pr.evaluate(tmp, today)["rows"]}
    assert rr["old"]["hit"] is None and rr["new"]["actual_date"] == "2026-09-20" and rr["plan"]["hit"] is None and rr["late"]["hit"] is None
    assert not pr.evaluate(tmp, D("2026-09-19"))["evaluated"]
    econ = dict(group="A", n=65, generated_on="2026-09-01", scenarios=[dict(name="base (mediana)", copies_low=20, copies_high=60)])
    for milestone in ("d30", "d90", "d180", None):
        write_json(root / "_raw" / "econ.json", dict(calibrated=dict(econ, milestone=milestone)))
        n = pr.sync(tmp, today)
        assert n == int(milestone is not None)
        if n:
            last = pr.load(tmp)["items"][-1]
            assert last["metric"] == last["actual_metric"] == "copies_" + milestone[1:] + "d"

print("asof-v1: temporal embargo, provenance, fallback, version windows, horizons OK")
