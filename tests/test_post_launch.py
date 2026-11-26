"""CLI locale: preservazione del tracker, dati mancanti e limiti del confronto."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "research"
INPUT = "start,end,source,segment,metric,value\n"
ROW = "2026-10-08,2026-10-14,steamworks,all,units_sold,20\n"
OLD = b'date,metric,value,note\n2026-10-14,units_sold,2.5,"nota mia, non cambiare"'


class PostLaunchTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), USERPROFILE=str(self.home),
                        GLS_HOME=str(self.home / "gls"), GLS_REACH="off", PYTHONIOENCODING="cp1252",
                        PYTHONDONTWRITEBYTECODE="1")
        self.folder = self.root / "gioco" / "launch"
        self.folder.mkdir(parents=True)
        self.metrics = self.folder / "metrics.csv"
        self.src = self.root / "privato.csv"
        self.report = self.folder / "post-launch.md"
        self.addCleanup(lambda: self.assertEqual(list(self.home.iterdir()), []))

    def cli(self, *args, success=True, script="post_launch.py", dest=True):
        cmd = [sys.executable, "-B", str(SCRIPTS / script)]
        if dest:
            cmd.extend(["--launch-dir", str(self.folder)])
        proc = subprocess.run([*cmd, *map(str, args)], cwd=self.root, env=self.env,
                              capture_output=True, encoding="utf-8")
        self.assertEqual(proc.returncode == 0, success, proc.stderr or proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)
        return proc

    def import_data(self, text, success=True):
        self.src.write_text(INPUT + text, encoding="utf-8-sig")
        return self.cli("import", self.src, success=success)

    def diagnosis(self, previous=False):
        args = ("--compare-end", "2026-10-07") if previous else ()
        self.cli("diagnose", "--end", "2026-10-14", *args)
        return self.report.read_text(encoding="utf-8")

    def test_repeat_and_tracker_compatibility(self):
        self.metrics.write_bytes(OLD)
        self.import_data(ROW + ROW)
        first = self.metrics.read_bytes()
        self.assertTrue(first.startswith(OLD + b"\r\n"))
        self.assertIn("1 già presenti", self.import_data(ROW).stdout)
        self.assertEqual(first, self.metrics.read_bytes())
        with self.metrics.open(encoding="utf-8-sig", newline="") as f:
            self.assertEqual(list(csv.DictReader(f))[-1], dict(date="2026-10-14", metric="post_units_sold",
                              value="20", note="post-launch/v1|2026-10-08|steamworks|all"))
        scenarios = self.root / "scenari.json"
        scenarios.write_text(json.dumps({"scenarios": [dict(id="copie", area="store", title="Monitoraggio",
            signals=[dict(metric="post_units_sold", kind="level", op="<", value=10)])]}), encoding="utf-8")
        out = self.root / "check.json"
        self.cli("--csv", self.metrics, "--contingencies", scenarios, "--today", "2026-10-14",
                 "status", "--json", out, script="metrics_track.py", dest=False)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["scenarios"][0]["status"], "OK")
        self.assertEqual(set(x.name for x in self.folder.iterdir()), {"metrics.csv"})

    def test_invalid_input_never_partially_updates(self):
        self.metrics.write_bytes(OLD)
        for bad in (ROW.replace("10-14", "02-30"), ROW.replace("10-08", "10-15"), ROW.replace("20\n", "\n"),
                    ROW.replace("20\n", "-1\n"), ROW.replace("20\n", "NaN\n"), ROW.replace("20\n", "3.5\n"),
                    ROW.replace("units_sold", "secret_note"), ROW.replace("steamworks", "web"),
                    ROW.replace("all", "private@example.com"), ROW.replace("units_sold", "itch_views"),
                    ROW.rstrip() + ",extra", ROW.replace("all", "other"), ROW.replace("20\n", "21\n")):
            with self.subTest(bad=bad):
                self.import_data(ROW + bad, success=False)
                self.assertEqual(self.metrics.read_bytes(), OLD)
        for text in ("", INPUT, INPUT + '"incompleta', "e-mail,amount\nprivate@example.com,20\n"):
            self.src.write_text(text, encoding="utf-8")
            err = self.cli("import", self.src, success=False).stderr
            self.assertNotIn("private@example.com", err)
            self.assertEqual(self.metrics.read_bytes(), OLD)

    def test_conflict_and_damaged_existing_tracker(self):
        self.import_data(ROW)
        before = self.metrics.read_bytes()
        self.import_data(ROW.replace("20\n", "22\n") + ROW.replace("units_sold", "impressions"), success=False)
        self.assertEqual(self.metrics.read_bytes(), before)
        self.import_data(ROW.replace("10-08", "10-07"), success=False)
        self.assertEqual(self.metrics.read_bytes(), before)
        damaged = b"date,metric,value,note,custom\n2026-10-14,visits,42,my note,custom"
        self.metrics.write_bytes(damaged)
        self.import_data(ROW, success=False)
        self.assertEqual(self.metrics.read_bytes(), damaged)

    def test_observed_counts_and_direction(self):
        self.import_data(ROW + ROW.replace("units_sold,20", "store_visits,100") +
                         "2026-10-01,2026-10-07,steamworks,all,store_visits,120\n"
                         "2026-10-01,2026-10-07,steamworks,all,units_sold,30\n")
        text = self.diagnosis(previous=True)
        for piece in ("20.00** (20/100)", "25.00 (30/120)", "-5.00 per 100", "prima riga",
                      "non una prova di effetto", "Continua", "Cambia", "Stop", "Meno esposizione"):
            self.assertIn(piece, text)

    def test_empty_zero_and_mismatched_cohorts(self):
        self.metrics.write_bytes(OLD)
        self.assertIn("Nessuna finestra", self.diagnosis())
        self.import_data(ROW.replace("units_sold,20", "returned_d7,0") +
                         ROW.replace("units_sold,20", "eligible_d7,12") +
                         ROW.replace("units_sold,20", "store_visits,0") +
                         ROW.replace("units_sold,20", "impressions,0") +
                         ROW.replace("units_sold,20", "refunds,50") +
                         ROW.replace("units_sold,20", "refund_eligible,20") +
                         ROW.replace("units_sold,20", "reviews,4").replace("steamworks,all", "steamworks,other") +
                         ROW.replace("units_sold,20", "positive_reviews,3"))
        text = self.diagnosis()
        for piece in ("0.00** (0/12)", "0/0: denominatore zero", "50/20: il numeratore supera",
                      "manca reviews", "manca positive_reviews"):
            self.assertIn(piece, text)
        self.assertNotIn("75.00", text)

    def test_before_after_guards(self):
        for start, end, scope in (("2026-10-01", "2026-10-07", "different"),
                                  ("2026-10-02", "2026-10-07", "all"),
                                  ("2026-10-06", "2026-10-12", "all")):
            with self.subTest(start=start, scope=scope):
                old = f"{start},{end},steamworks,{scope},store_visits,10\n"
                self.import_data(ROW + ROW.replace("units_sold", "store_visits") + old +
                                 old.replace("store_visits", "units_sold"))
                self.cli("diagnose", "--end", "2026-10-14", "--compare-end", end)
                text = self.report.read_text(encoding="utf-8")
                self.assertIn("Nessuna finestra precedente comparabile", text)
                self.assertNotIn("differenza +", text)
                self.metrics.unlink()
        self.cli("diagnose", "--end", "2026-10-14", "--compare-end", "2026-10-15", success=False)

    def test_destination_required_and_tool_folder_protected(self):
        self.cli("diagnose", "--end", "2026-10-14", success=False, dest=False)
        self.cli("--launch-dir", SCRIPTS / "launch", "diagnose", "--end", "2026-10-14",
                 dest=False, success=False)
        self.assertFalse((self.root / "launch").exists())


if __name__ == "__main__":
    unittest.main()
