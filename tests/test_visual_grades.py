"""Offline procedural fixtures: exercise provenance/QA; not a visual accuracy benchmark."""
import csv
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

RESEARCH = Path(__file__).resolve().parents[1] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
import visual_grades as vg


def png(color):
    def chunk(typ, data):
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">2I5B", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes([0, color]))) + chunk(b"IEND", b""))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


class VisualGradesTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.dir = Path(t.name)
        env = patch.dict(os.environ, GLS_HOME=str(self.dir / "shared"))
        env.start()
        self.addCleanup(env.stop)
        self.manifest = self.dir / "manifest.json"
        self.anchors = []
        for ix, tier in enumerate("ABC"):
            name = tier + ".png"
            (self.dir / name).write_bytes(png(ix))
            self.anchors.append(dict(tier=tier, image=name, note=f"criterio {ix}", source="fixture"))
        vg.save(self.manifest, dict(genre="puzzle", version="v1", anchors=self.anchors, curator="fixture"))
        self.headers = self.dir / "headers"
        self.headers.mkdir()
        self.week = self.dir / "cohort_2026-09-07_2026-09-13.csv"
        self.rows = []
        for ix in range(20):
            appid = str(10000 + ix)
            data = png(20 + ix)
            (self.headers / (appid + ".jpg")).write_bytes(data)
            self.rows.append(dict(appid=appid, week=self.week.stem, name="SECRETTITLE" + appid, status="keep",
                                  reviews_d30="99", genres="Adventure", tags="Story Rich; Puzzle", grade="C",
                                  header_sha256=vg.sha(data), extra="da conservare"))
        self.rows[-1]["tags"] = "Horror"
        self.rows[-2]["status"] = "junk"
        self.rows[-3]["header_sha256"] = ""
        self.rows[-4]["header_sha256"] = "2" * 64
        (self.headers / (self.rows[-5]["appid"] + ".jpg")).unlink()
        write_csv(self.week, self.rows)
        self.week.with_suffix(".source").write_text(str(self.dir), encoding="utf-8")

    def cli(self, *args):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            vg.main([str(x) for x in args])
        return json.loads(out.getvalue())

    def prepare(self):
        self.cli("freeze", "--manifest", self.manifest)
        rec = self.cli("prepare", "--pack", "puzzle/v1", "--week", self.week, "--headers", self.headers)
        self.batch = rec["batch"]
        self.base, self.key = vg.batch_data(self.batch)
        return rec

    def ballot(self, packet, values=None, similarity=False):
        cases = vg.load(packet / "packet.json")["cases"]
        rows = [dict(id=r["id"], confidence="0.88", doubt="0", note="Osservazione fixture",
                     **({"similarity": "distant"} if similarity else {"tier": "A"}),) for r in cases]
        for r in rows:
            r.update((values or {}).get(r["id"], {}))
        path = self.dir / "votes.csv"
        write_csv(path, rows)
        return path

    def votes(self, cmd, packet, rater, values=None):
        return self.cli(cmd, "--batch", self.batch, "--votes", self.ballot(packet, values), "--rater", rater)

    def review(self):
        return self.votes("qa", self.base / "initial" / "blind", "reviewer")

    def apply(self):
        return self.cli("apply", "--batch", self.batch, "--week", self.week)

    def test_global_separate_from_legacy_and_project(self):
        rec = self.prepare()
        self.assertEqual((rec["n"], len(rec["skipped"])), (15, 3))
        doc = (self.base / "blind" / "packet.json").read_text()
        for forbidden in ("SECRETTITLE", "appid", "reviews_d30", "fixture.png", "sha256", "grade", "sample", "source"):
            self.assertNotIn(forbidden, doc)
        initial = self.votes("import", self.base / "blind", "model+revision")
        self.assertEqual(initial["required"], 3)
        with self.assertRaises(SystemExit):
            self.apply()
        with self.assertRaises(SystemExit):
            self.votes("qa", Path(initial["qa"]), " Model+Revision ")
        self.review()
        self.assertEqual(self.apply()["global_verified"], 15)
        self.assertEqual(self.apply()["sample_exact"], 3)
        _, rows = vg.week_rows(self.week)
        for ix, r in enumerate(rows):
            self.assertEqual(r["grade"], "C")
            self.assertEqual(r["extra"], "da conservare")
            self.assertEqual(r["grade_scope"], "global_verified" if ix < 15 else "legacy")
            self.assertEqual(r["global_tier"], "A" if ix < 15 else "")
        before = self.week.read_bytes()
        dest = self.cli("compare", "--batch", self.batch, "--votes", self.ballot(self.base / "blind", similarity=True),
                        "--reference", self.dir / "A.png", "--launch-dir", self.dir / "launch", "--rater", "owner")
        comparison = vg.load(Path(dest))
        self.assertEqual(comparison["scope"], "project_similarity")
        self.assertEqual(comparison["cases"][0]["similarity"], "distant")
        self.assertEqual(before, self.week.read_bytes())

    def test_doubts_plus_precommitted_sample_and_escalation(self):
        self.prepare()
        extra = sorted(set(self.key["cases"]) - set(self.key["sample"]))[:3]
        values = {extra[0]: {"doubt": "1"}, extra[1]: {"confidence": ".4"}, extra[2]: {"tier": "?"}}
        initial = self.votes("import", self.base / "blind", "primary", values)
        self.assertEqual(initial["required"], 6)
        mapping = vg.load(self.base / "initial" / "mapping.json")
        self.assertEqual(set(mapping.values()), set(extra) | set(self.key["sample"]))
        self.assertFalse(set(mapping) & set(mapping.values()))
        mismatch = next(k for k, v in mapping.items() if v == self.key["sample"][0])
        doubt = next(k for k, v in mapping.items() if v == extra[0])
        extended = self.votes("qa", Path(initial["qa"]), "reviewer",
                              {mismatch: {"tier": "B"}, doubt: {"tier": "?", "doubt": "1"}})
        self.assertEqual(extended["remaining"], 9)
        before = self.week.read_bytes()
        with self.assertRaises(SystemExit):
            self.apply()
        self.assertEqual(before, self.week.read_bytes())
        self.votes("qa", Path(extended["extended_qa"]), "reviewer")
        verdict = self.apply()
        self.assertEqual((verdict["withheld"], verdict["reread"], verdict["sample_exact"]), (1, 15, 2))

    def test_hash_change_blocks_import_and_apply(self):
        self.prepare()
        self.rows[0]["header_sha256"] = ""
        write_csv(self.week, self.rows)
        with self.assertRaises(SystemExit):
            self.votes("import", self.base / "blind", "primary")
        self.rows[0]["header_sha256"] = vg.sha(png(20))
        write_csv(self.week, self.rows)
        self.votes("import", self.base / "blind", "primary")
        self.review()
        self.rows[0]["header_sha256"] = "3" * 64
        write_csv(self.week, self.rows)
        before = self.week.read_bytes()
        with self.assertRaises(SystemExit):
            self.apply()
        self.assertEqual(self.week.read_bytes(), before)

    def test_invalid_ballots_fail_atomically(self):
        self.prepare()
        path = self.ballot(self.base / "blind")
        _, rows = vg.read_csv(path, [])
        for bad in (rows[:-1], rows + rows[:1], [dict(rows[0], id="extraneous")] + rows[1:],
                    [dict(rows[0], confidence="nan")] + rows[1:], [dict(rows[0], doubt="")] + rows[1:]):
            write_csv(path, bad)
            with self.assertRaises(SystemExit):
                self.cli("import", "--batch", self.batch, "--rater", "model", "--votes", path)
            self.assertFalse((self.base / "initial").exists())
        img = self.base / "blind" / next(iter(self.key["cases"].values()))["image"]
        img.write_bytes(png(42))
        with self.assertRaises(SystemExit):
            self.votes("import", self.base / "blind", "model")

    def test_immutable_packs_and_unusable_inputs(self):
        self.prepare()
        with self.assertRaises(SystemExit):
            self.cli("freeze", "--manifest", self.manifest)
        for change in (dict(anchors=self.anchors[:2]), dict(anchors=[self.anchors[0]] * 3), dict(genre="../packs")):
            vg.save(self.manifest, dict(dict(genre="puzzle", version="v2", curator="test", anchors=self.anchors), **change))
            with self.assertRaises(SystemExit):
                self.cli("freeze", "--manifest", self.manifest)
            self.assertFalse((vg.root() / "packs" / "puzzle" / "v2").exists())
        (vg.root() / "packs" / "puzzle" / "v1" / "A-1.png").write_bytes(png(33))
        with self.assertRaises(SystemExit):
            self.cli("prepare", "--pack", "puzzle/v1", "--week", self.week)

    def test_cli_other_directory_and_chunk(self):
        self.cli("freeze", "--manifest", self.manifest)
        proc = subprocess.run([sys.executable, str(RESEARCH / "visual_grades.py"), "prepare", "--pack", "puzzle/v1",
                               "--week", str(self.week), "--size", "4", "--chunk", "2"],
                              cwd=self.dir, capture_output=True, text=True, check=True)
        result = json.loads(proc.stdout)
        self.assertEqual((result["n"], result["chunks"]), (4, 5))
        _, key = vg.batch_data(result["batch"])
        self.assertEqual({x["appid"] for x in key["cases"].values()}, {r["appid"] for r in self.rows[4:8]})


if __name__ == "__main__":
    unittest.main()
