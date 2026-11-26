"""Offline: orchestration, period boundaries, evidence gaps and scheduler ownership."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "scripts" / "research"
sys.path.insert(0, str(TOOLS))
import radar
import cohort_bench


class Radar(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "private archive"
        self.env = patch.dict(os.environ, GLS_HOME=str(self.home))
        self.env.start()
        self.addCleanup(self.env.stop)
        self.today = dt.date(2026, 6, 15)
        self.calls = []

    def week(self, week, complete=True):
        csv = self.home / "cohorts" / (week + ".csv")
        q = dict(n_games=1, n_store=1, n_reviews=1, generated_on="2026-06-15",
                 complete=complete, window_complete=complete)
        radar.save(csv.with_suffix(".quality.json"), q)
        csv.write_text("status,grade,release_date\nkeep,B,2026-05-01\n", encoding="utf-8")  # a project tier is not a verified global tier
        return csv

    def fake(self, step, home):
        self.calls.append(step.key)
        self.assertEqual(home, self.home)
        self.assertTrue(Path(step.argv[1]).is_absolute())
        if step.key == "cohorts":
            for week in radar.expected_weeks(self.today, int(step.argv[-1])):
                self.week(week)
        elif step.key == "discover":
            radar.save(home / "market" / "tracked.json", {"123": {"appid": 123}})
        elif step.key == "demo_intake":
            self.assertEqual(step.argv[2:], ["--days", "1"])
        elif step.key == "players":
            p = home / "market" / "players.csv"
            p.write_text("ts,appid,players\n" + self.today.isoformat() + "T14:00,123,0\n", encoding="utf-8")

    def test_check_is_read_only_from_unrelated_cwd(self):
        result = subprocess.run([sys.executable, str(TOOLS / "radar.py"), "check"], cwd=self.base,
                                capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        self.assertEqual(info["home"], str(self.home))
        self.assertTrue(info["queue"])
        self.assertFalse(self.home.exists())

    def test_resume_daily_weekly_independent_profiles(self):
        project = self.base / "game with spaces" / "launch"
        project.mkdir(parents=True)
        (project / "comps.csv").write_text("appid\n123\n", encoding="utf-8")
        radar.configure(self.home, "add", "demo", project)
        with self.assertRaises(ValueError):
            radar.configure(self.home, "add", "alias", project)
        def partial(step, home):
            self.fake(step, home)
            if step.key == "demo_intake":
                return "comando terminato con codice 2"

        run = radar.run(self.home, self.today, 2, "auto", partial)
        self.assertFalse(run["complete"])
        self.assertEqual(run["phases"]["demo_intake"], "partial")
        self.assertEqual(run["phases"]["metro"], "ok")
        project_status = next(k for k in run["phases"] if k.endswith("/status"))
        self.assertEqual(run["phases"][project_status], "ok")
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 2, "auto", self.fake)["complete"])
        self.assertEqual(self.calls, ["demo_intake", project_status])
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 2, "auto", self.fake)["complete"])
        self.assertFalse(self.calls)
        info = radar.check(self.home, self.today, 2, project)
        self.assertFalse(info["queue"])
        self.assertEqual(info["selected_profiles"], ["demo"])
        self.assertEqual(info["cohort_backlog"][0]["capsules_to_grade"], 1)
        self.assertEqual(info["cohort_backlog"][0]["due_measurements"][30], 1)
        radar.configure(self.home, "remove", "demo")
        # Tuesday opens a new eligible release week; observations always use the real day.
        self.today += dt.timedelta(days=1)
        self.assertTrue(radar.run(self.home, self.today, 2, "daily", self.fake)["complete"])
        self.assertEqual(self.calls, ["demo_intake", "players", "snapshots"])
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 2, "weekly", self.fake)["complete"])
        self.assertIn("cohorts", self.calls)
        self.assertFalse(any("/" in k for k in self.calls))

    def test_missing_manifests_block_model_only_and_are_repaired(self):
        weeks = radar.expected_weeks(self.today, 3)
        def broken(step, home):
            if step.key != "cohorts":
                return self.fake(step, home)
            self.week(weeks[0], complete=False)
            self.week(weeks[1]).with_suffix(".quality.json").unlink()
            self.week(weeks[2]).with_suffix(".quality.json").write_text("{", encoding="utf-8")

        status = radar.run(self.home, self.today, 3, "auto", broken)
        self.assertEqual(status["phases"]["cohorts"], "partial")
        self.assertEqual(status["phases"]["metro"], "blocked")
        self.assertEqual(status["phases"]["players"], "ok")
        self.assertEqual(status["phases"]["demo_intake"], "ok")
        q = radar.check(self.home, self.today, 3)["cohorts"]
        self.assertEqual([q[w]["status"] for w in weeks], ["partial", "unverified", "invalid"])
        path = self.week(weeks[0]).with_suffix(".quality.json")
        radar.save(path, dict(radar.read_object(path), n_reviews=0))
        self.assertEqual(radar.quality(path.parent, weeks[0])["status"], "invalid")
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 3, "auto", self.fake)["complete"])
        self.assertEqual(self.calls, ["cohorts", *("news:" + w for w in weeks), "calibrate", "metro"])
        # Deletion after a successful checkpoint cannot make a hole invisible.
        self.week(weeks[1]).unlink()
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 3, "auto", self.fake)["complete"])
        self.assertEqual(self.calls, ["cohorts", "calibrate", "metro"])

    def test_busy_crash_and_bad_state(self):
        with radar.locked(self.home):
            with self.assertRaises(radar.Busy):
                radar.run(self.home, self.today, 0, "daily", self.fake)
        def crash(step, home):
            self.fake(step, home)
            if step.key == "players":
                raise KeyboardInterrupt
        radar.run(self.home, self.today, 0, "weekly", self.fake)
        with self.assertRaises(KeyboardInterrupt):
            radar.run(self.home, self.today, 0, "daily", crash)
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 0, "daily", self.fake)["complete"])
        self.assertEqual(self.calls, ["snapshots"])  # players sample survived the crash
        state = self.home / "radar" / "state.json"
        state.write_text("[", encoding="utf-8")
        with self.assertRaises(ValueError):
            radar.run(self.home, self.today, 0, "daily", self.fake)
        self.assertEqual(state.read_text(encoding="utf-8"), "[")

    def test_sample_missing_is_not_zero(self):
        radar.run(self.home, self.today, 0, "weekly", self.fake)
        def missing(step, home):
            if step.key == "players":
                (home / "market" / "players.csv").write_text(
                    "ts,appid,players\n2026-06-15T14:00,123,\n", encoding="utf-8")
            else:
                self.fake(step, home)
        self.assertFalse(radar.run(self.home, self.today, 0, "daily", missing)["complete"])
        self.calls.clear()
        self.assertTrue(radar.run(self.home, self.today, 0, "daily", self.fake)["complete"])
        self.assertEqual(self.calls, ["players"])

    def test_missing_intake_does_not_pass(self):
        with patch.object(radar, "HERE", self.base / "missing installation"):
            result = radar.run(self.home, self.today, 0, "daily")
        self.assertEqual(result["phases"]["demo_intake"], "partial")
        self.assertFalse(result["complete"])

    def test_news_budget_resumes_paid_and_failed_apps(self):
        work = self.base / "cohort"
        (work / "apps").mkdir(parents=True)
        radar.save(work / "cohort.json", {"games": [dict(appid=i, price=(0 if i == 0 else 10))
                                                      for i in range(6)]})
        radar.save(work / "apps" / "1.json", {"news": [], "details": {"x": 1}})
        radar.save(work / "apps" / "2.json", {"details": {"x": 2}})
        (work / "filtered.csv").write_text("appid,status\n1,keep\n2,keep\n3,keep\n4,keep\n5,junk\n",
                                          encoding="utf-8")
        args = SimpleNamespace(dir=str(work), rate=0, paid_only=True, max_requests=2)
        with patch.object(cohort_bench, "news_items", side_effect=[None, []]) as reader:
            with self.assertRaises(SystemExit) as exc:
                cohort_bench.cmd_news(args)
            self.assertEqual(exc.exception.code, 2)
            self.assertEqual([c.args[0] for c in reader.call_args_list], [2, 3])
        self.assertNotIn("news", radar.read_object(work / "apps" / "2.json"))
        with patch.object(cohort_bench, "news_items", return_value=[]) as reader:
            cohort_bench.cmd_news(args)
            cohort_bench.cmd_news(args)
            self.assertEqual([c.args[0] for c in reader.call_args_list], [2, 4])
        self.assertEqual(radar.read_object(work / "apps" / "2.json"), {"details": {"x": 2}, "news": []})

    def test_projects_refresh_warning_score_and_fallback(self):
        from status_page import build, radar_notice

        a, b = self.base / "a", self.base / "b"
        for name, root in (("a", a), ("b", b)):
            root.mkdir()
            radar.configure(self.home, "add", name, root)
        radar.save(a / "prelaunch.json", {"price": 9})
        raw = a / "_raw"
        radar.save(raw / "metro.json", {"old": True})
        broken_news, mode = True, "model"
        def collect(step, home):
            self.fake(step, home)
            if step.key.startswith("news:"):
                self.assertIn(str(home / "cohorts" / "_work" / step.period), step.argv)
                self.assertIn("--paid-only", step.argv)
                if broken_news:
                    return "comando terminato con codice 2"
            if step.key.endswith("/score"):
                self.assertIn(str(a / "prelaunch.json"), step.argv)
                self.assertFalse((raw / "metro.json").exists())
                if mode == "error":
                    return "comando terminato con codice 2"
                radar.save(Path(step.argv[-1]), {"scored_on": self.today.isoformat(),
                           "score": {"mode": mode, "p100": .5, "p1k": .3, "p10k": .1, "band": "<100"},
                           "metro": {"protocol": "asof-v1", "target": "y30", "validated": mode == "model"}})
        def run():
            self.calls.clear()
            return radar.run(self.home, self.today, 1, "auto", collect)
        run1 = run()
        self.assertFalse(run1["complete"])
        self.assertFalse((raw / "metro.json").exists())
        self.assertTrue((raw / "metro.previous.json").exists())
        self.assertEqual(sum(k.endswith("/status") for k in self.calls), 2)
        self.assertIn("dati parziali", radar_notice(a, "private"))
        self.assertIn("dati parziali", radar_notice(b, "private"))
        self.assertIn("Radar: dati parziali", build(str(a), "private", [], [], set(), self.today))
        self.assertFalse(any(k.startswith("b.") and k.endswith("/score") for k in run1["phases"]))
        broken_news = False
        self.assertTrue(run()["complete"])
        self.assertTrue((raw / "metro.json").exists())
        self.assertEqual(sum(k.endswith("/status") for k in self.calls), 2)
        self.assertEqual(radar_notice(a, "private"), "")
        self.assertLess(next(i for i, k in enumerate(self.calls) if k.endswith("/score")),
                        next(i for i, k in enumerate(self.calls) if k.startswith("a.") and k.endswith("/predictions")))
        # New inputs within the same release week invalidate only the changed project.
        mode = "base_rate"
        radar.save(a / "prelaunch.json", {"price": 10})
        self.assertTrue(run()["complete"])
        self.assertFalse((raw / "metro.json").exists())
        self.assertTrue((raw / "metro.fallback.json").is_file())
        self.assertIn("Solo frequenze", radar_notice(a, "private"))
        self.assertFalse(any(k.startswith("b.") for k in self.calls))
        mode = "error"
        radar.save(a / "prelaunch.json", {"price": 11})
        self.assertFalse(run()["complete"])
        self.assertFalse((raw / "metro.fallback.json").exists())
        self.assertFalse((raw / "metro.json").exists())
        self.assertTrue(any(k.endswith("/status") for k in self.calls))
        mode = "model"
        self.assertTrue(run()["complete"])
        self.assertEqual(radar_notice(a, "private"), "")
        self.assertNotIn("Radar: dati parziali", build(str(a), "private", [], [], set(), self.today))

    def test_child_failure_no_log_secrets(self):
        step = radar.Step("phase", "period", ["python", "tool.py"])
        for code, stderr in [(0, b"WARN url?key=SECRET"), (2, b"error SECRET")]:
            proc = subprocess.CompletedProcess(step.argv, code, b"", stderr)
            with patch.object(radar.subprocess, "run", return_value=proc) as call:
                result = radar.collect(step, self.home)
                self.assertTrue(result)
                self.assertNotIn("SECRET", result)
                self.assertEqual(call.call_args.kwargs["cwd"], self.home)

    def test_scheduler_dry_run_legacy_foreign_and_ownership(self):
        registered = {}
        writes = []
        legacy = []
        def backend(p, mutate=False):
            if mutate:
                writes.append(p["operation"])
                if p["operation"] == "install":
                    registered.update(p)
                else:
                    registered.clear()
            match = bool(registered) and all(p[k] == registered.get(k) for k in ("program", "marker", "arguments"))
            return dict(present=bool(registered), matches=match, legacy=legacy[:])
        def cmd(action, apply=False):
            return radar.schedule(self.home, action, apply, "09:00", backend)
        self.assertFalse(cmd("install")["applied"])
        self.assertFalse(self.home.exists())
        for name in ("\\WeeklyMarket", "\\folder\\GLS-DailyPlayers", "\\folder\\RenamedMarketWorker"):
            legacy.append(name)
            with self.assertRaises(ValueError):
                cmd("install", True)
            legacy.clear()
        registered["marker"] = "foreign"
        for op in ("install", "uninstall"):
            with self.assertRaises(ValueError):
                cmd(op, True)
        self.assertEqual(writes, [])
        registered.clear()
        self.assertTrue(cmd("install", True)["applied"])
        self.assertTrue(cmd("status")["matches"])
        self.assertFalse(cmd("install", True)["applied"])
        self.assertIn(subprocess.list2cmdline([str(self.home)]), registered["arguments"])
        legacy.append("\\WeeklyMarket")
        self.assertTrue(cmd("status")["legacy"])
        with self.assertRaises(ValueError):
            cmd("install", True)
        self.assertEqual(writes, ["install"])
        legacy.clear()
        self.assertFalse(cmd("uninstall")["applied"])
        registered["arguments"] += " --different-action"
        with self.assertRaises(ValueError):
            cmd("uninstall", True)
        registered["arguments"] = cmd("status")["registered"]["arguments"]
        self.assertTrue(cmd("uninstall", True)["applied"])
        self.assertFalse(cmd("status")["present"])
        self.assertEqual(writes, ["install", "uninstall"])

    @unittest.skipUnless(os.name == "nt", "PowerShell Windows")
    def test_legacy_detector_uses_fake_inventory_only(self):
        # The Get-ScheduledTask cmdlet is shadowed: no contact with the real scheduler.
        setup = r"""
$p = @{name='GameLaunchStrategist-Radar'}
function Get-ScheduledTask {
  @(
    [pscustomobject]@{TaskName='WeeklyMarket-copy'; TaskPath='\'; Actions=@()}
    [pscustomobject]@{TaskName='daily_players'; TaskPath='\folder\'; Actions=@()}
    [pscustomobject]@{TaskName='Renamed'; TaskPath='\'; Actions=@(
      [pscustomobject]@{Execute='python.exe'; Arguments='"D:\old copy\market_tracker.py" snapshot --players-only'})}
    [pscustomobject]@{TaskName='Check-only'; TaskPath='\'; Actions=@(
      [pscustomobject]@{Execute='python.exe'; Arguments='"D:\old copy\radar.py" check'})}
  )
}
"""
        binary = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        cp = subprocess.run([str(binary), "-NoProfile", "-NonInteractive", "-Command", setup + radar.INSPECT +
                             "\nConvertTo-Json -InputObject $legacy -Compress"], capture_output=True, check=True)
        self.assertEqual(set(json.loads(cp.stdout)), {"\\WeeklyMarket-copy", "\\folder\\daily_players", "\\Renamed"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
