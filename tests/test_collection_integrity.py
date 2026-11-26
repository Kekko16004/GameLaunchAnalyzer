"""Offline regressions for resumable, evidence-dated Steam collection."""
import argparse
import contextlib
import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import common
import cohort_bench as cb
import market_page as page
import market_tracker as mt


class Integrity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.dict(os.environ, GLS_HOME=tmp.name, GLS_REACH="off"))
        stack.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("no live HTTP in tests")))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def run_update(self, n, budget=50):
        cb.main(["--today", "2026-11-26", "update", "--new-weeks", str(n),
                 "--no-volume", "--rate", "0", "--rate-reviews", "0", "--max-requests", str(budget)])

    def test_gap_repair_and_resume(self):
        searches = []
        def window(start, end, cc, **kw):
            searches.append(start)
            if len(searches) == 1:
                kw["incomplete"].append(100)
            return [dict(appid=int(start.strftime("%m%d")), name="test", date=start.isoformat(), tagids=[])]

        def steam(url, **kw):
            if "appdetails" in url:
                aid = url.split("appids=")[1].split("&")[0]
                return {aid: dict(success=True, data=dict(name="test", is_free=True))}
            if "appreviews" in url:
                return dict(success=1, query_summary=dict(total_reviews=0))
            self.fail(url)
        ds = self.root / "cohorts"
        with patch.object(cb, "collect_window", side_effect=window), patch.object(cb, "tag_names", return_value={}), \
                patch.object(common, "safe_json", side_effect=steam), patch.object(cb, "cmd_sheets"):
            self.run_update(2)
            self.assertFalse(list(ds.glob("*.csv")))
            q = json.loads(next(ds.glob("*.quality.json")).read_text())
            self.assertFalse(q["complete"])
            self.assertFalse(q["window_complete"])
            self.run_update(2)
            self.assertEqual(len(list(ds.glob("*.csv"))), 2)
            self.run_update(3)
            self.run_update(3)
            self.run_update(0)
        self.assertEqual([x.day for x in searches], [16, 16, 9, 2])
        for path in ds.glob("*.csv"):
            self.assertTrue(cb.verified_week(str(path)))

    def test_outage_never_publishes_1656_missing_as_zero(self):
        games = [dict(appid=i, reviews_total=None, has_details=True) for i in range(1656)]
        q = cb.cohort_quality(dict(games=games, window_complete=True, window=["a", "b"]), dt.date.today())
        self.assertEqual((q["n_reviews"], q["n_games"], q["complete"]), (0, 1656, False))
        self.assertFalse(cb.measured_reviews(dict(success=1, query_summary={})))
        self.assertTrue(cb.measured_reviews(dict(success=1, query_summary=dict(total_reviews=0))))
        empty_summary = cb.flatten(dict(appid=12), None, dict(success=1), None, {}, dt.date.today())
        self.assertIsNone(empty_summary["reviews_total"])

    def test_old_work_never_becomes_new_observation(self):
        work = self.root / "work"
        work.mkdir()
        ds = self.root / "ds"
        rel = "2026-01-01"
        game = dict(appid=1, name="x", release_date=rel, has_details=True, reviews_total=0)
        c = dict(window=[rel, "2026-01-07"], games=[game], read_on="2026-01-08", window_complete=True)
        common.write_json(c, str(work / "cohort.json"))
        common.write_csv([dict(appid=1, status="keep", reasons="")], str(work / "filtered.csv"))
        path = cb.import_cohort_dir(str(work), str(ds), dt.date(2026, 6, 1))
        self.assertFalse(cb.read_week(path)[0]["checked_d90"])
        # Invalidate a bad legacy D90 (checked before release + 90); request budget is exact.
        rows = cb.read_week(path)
        rows[0].update(checked_d90="2026-01-08", reviews_d90="0")
        cb.write_week(rows, path)
        args = argparse.Namespace(rate_reviews=0)
        with patch.object(common, "safe_json", return_value=dict(success=1, query_summary=dict(total_reviews=20))) as api:
            budget = [1]
            cb.recheck_week(path, dt.date(2026, 6, 1), args, budget)
            self.assertEqual((api.call_count, budget), (1, [0]))
        with patch.object(common, "safe_json", return_value=dict(success=1, query_summary=dict(total_reviews=0))):
            cb.recheck_week(path, dt.date(2026, 6, 1), args, [1])
        self.assertEqual(cb.read_week(path)[0]["checked_d90"], "2026-06-01")
        del c["window_complete"]
        common.write_json(c, str(work / "cohort.json"))
        other = self.root / "legacy"
        cb.import_cohort_dir(str(work), str(other), dt.date(2026, 6, 1))
        self.assertFalse(list(other.glob("*.csv")))
        self.assertFalse(json.loads(next(other.glob("*.quality.json")).read_text())["complete"])

    def test_partial_snapshot_retry_and_hourly_player_slots(self):
        args = argparse.Namespace(market_dir=str(self.root / "market"), now="2026-01-02T10:01",
                                  rate=0, steamspy=False, players_only=False, limit=None)
        mt.save_tracked(args, {"42": dict(appid=42, release_date="2026-01-01")})
        path = mt.mdir(args, "snapshots.csv")
        mt.append_rows(path, mt.SNAP_FIELDS, [dict(ts=args.now, appid=42, label="h24")])
        row = dict(appid=42, ts=args.now, label="h24", players_now=0, price=0, reviews_total=0)
        with patch.object(mt, "snapshot_one", return_value=row) as snap:
            mt.cmd_snapshot(args)
            mt.cmd_snapshot(args)
            self.assertEqual(snap.call_count, 1)
        self.assertTrue(mt.due_labels(dict(release_date="2026-01-01"), dt.datetime(2026, 1, 6), set())[0].startswith("wk"))
        args.players_only = True
        with patch.object(mt, "players_now", side_effect=[None, 0, 9]) as players:
            for args.now in ("2026-01-02T10:00", "2026-01-02T10:02", "2026-01-02T10:20", "2026-01-02T14:00"):
                mt.cmd_snapshot(args)
            self.assertEqual(players.call_count, 3)
        self.assertEqual([r["players"] for r in mt.read_rows(mt.mdir(args, "players.csv"))], ["0", "9"])

    def test_global_grade_only_follows_identical_asset(self):
        work = self.root / "work"
        headers = work / "headers"
        headers.mkdir(parents=True)
        image = headers / "1.jpg"
        image.write_bytes(b"first capsule")
        game = dict(appid=1, release_date="2026-01-05", has_details=True, reviews_total=0)
        common.write_json(dict(window=["2026-01-05", "2026-01-11"], games=[game], window_complete=True,
                               read_on="2026-01-13"), str(work / "cohort.json"))
        common.write_csv([dict(appid=1, status="keep", reasons="")], str(work / "filtered.csv"))
        def collect():
            return cb.import_cohort_dir(str(work), str(self.root / "ds"), dt.date(2026, 1, 14))
        path = collect()
        rows = cb.read_week(path)
        rows[0].update(global_tier="A", grade_scope="global", anchor_pack="v1", visual_batch="x")
        cb.write_week(rows, path)
        self.assertEqual(cb.read_week(collect())[0]["global_tier"], "A")
        image.write_bytes(b"different artwork at the same URL")
        self.assertEqual(cb.read_week(collect())[0]["global_tier"], "")

    def test_comparable_immature_and_zero(self):
        args = argparse.Namespace(today="2026-01-20", csv=str(self.root / "missing"), appid=[11], calibration=None,
                                  out=str(self.root / "out.json"))
        def meta(e, th):
            e["release_date"] = "2026-01-01"
        with patch.object(mt, "fetch_meta", side_effect=meta), patch.object(mt, "api_json", return_value=dict(success=1, query_summary=dict(total_reviews=0))) as api:
            for date, expected in [("2026-01-20", (None, None)), ("2026-02-20", (0, None)), ("2026-04-20", (0, 0))]:
                args.today = date
                mt.cmd_comps(args)
                g = common.load_json(args.out)["games"][0]
                self.assertEqual((g["reviews_d30"], g["reviews_d90"]), expected)
            self.assertEqual(api.call_count, 3)

    def test_dashboard_uses_observed_window_and_model_protocol(self):
        today = dt.date(2026, 11, 26)
        cp = self.root / "calibration.json"
        c = dict(generated_on=today.isoformat(), data_to="2026-11-22")
        for verified, last, fresh in [(0, "2026-11-22", False), (1, "2025-11-22", False), (1, "2026-11-22", True)]:
            c.update(quality=dict(verified_weeks=verified), data_to=last)
            common.write_json(c, str(cp))
            self.assertEqual("mfresh ok" in page.freshness(page.load(str(self.root), today)), fresh)
        self.assertIn("storico non verificato", page.metro_section(dict(available=True), {"score": {"band": "high"}}))
        d = dict(pred=dict(n=1, evaluated=0, rows=[dict(low=10000, high=None, open_high=True, date="2026-01-01",
                     source="demo", metric="copies", label="beta", status="attesa")]))
        self.assertIn("≥10000", page.predictions_section(d))


if __name__ == "__main__":
    unittest.main()
