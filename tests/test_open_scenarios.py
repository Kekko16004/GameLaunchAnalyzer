"""Offline: conditional sales, market ranges without private inputs, nullable costs, audience filters."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

R = Path(__file__).resolve().parents[1] / "scripts" / "research"
sys.path.insert(0, str(R))


class OpenScenarios(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        env = patch.dict(os.environ, GLS_HOME=str(self.home), PYTHONIOENCODING="utf-8")
        env.start()
        self.addCleanup(env.stop)
        self.root = self.home / "launch"
        self.raw = self.root / "_raw"
        self.raw.mkdir(parents=True)

    def econ(self, **inputs):
        import calc_econ
        return calc_econ.compute(dict(calc_econ.DEFAULTS, **inputs))

    def calibration(self, n=40):
        from cohort_bench import group_stats
        group = group_stats([{"reviews": i} for i in range(n)], "reviews")
        return dict(quality={"verified_weeks": 4}, generated_on="2026-10-15", data_from="2026-08-01",
                    data_to="2026-10-01", primary="d30", milestones={"d30": dict(tiers={"B": group}, by_price={}, by_genre={})})

    def test_missing_and_explicit_zero(self):
        from calc_econ import md
        args = dict(price=10, wishlists=[100], conv=[20])
        unknown = self.econ(**args)
        self.assertEqual(unknown["costs"], dict(cash=None, time=None, total=None))
        row = unknown["scenarios"][0]
        self.assertEqual(row["copies"], 20)
        self.assertGreater(row["net"], 0)
        for key in ("profit_cash", "profit_with_time", "per_partner", "times_breakeven"):
            self.assertIsNone(row[key])
        self.assertIsNone(unknown["sensitivity"][0]["breakeven_copies"])
        self.assertNotIn("None", md(unknown))
        self.assertEqual(self.econ(**args, costs=0)["breakeven"], dict(copies_cash=0, copies_with_time=None, wishlists_needed={}))
        self.assertIsNone(self.econ(**args, costs=8, hours=10)["costs"]["time"])
        zero = self.econ(**args, costs=0, hours=0, hourly=5)
        self.assertEqual(zero["breakeven"]["copies_with_time"], 0)
        self.assertIsNone(zero["scenarios"][0]["per_partner"])
        self.assertEqual(self.econ(**args, costs=0, partners=2)["scenarios"][0]["per_partner"], round(row["net"] / 2, 2))
        with self.assertRaises(SystemExit):
            self.econ(**args, partners=0)

    def test_market_without_econ_or_wishlist(self):
        from calc_econ import md
        import market_page
        cal = self.calibration()
        case = dict(cal=cal, today=dt.date(2026, 10, 20))
        text = market_page.piano_card(case, None)
        self.assertIn("n = 40", text)
        self.assertIn("30 giorni", text)
        self.assertIn("20–60", text)
        self.assertIn("Nessun ricavo stimato", text)
        self.assertNotIn("Netto prima", text)
        self.assertIn("Riferimento storico", market_page.piano_card(dict(case, today=dt.date(2026, 12, 20)), None))
        for bad in (None, dict(cal, quality={}), self.calibration(8), dict(cal, primary=None)):
            self.assertIn("non stimabili", market_page.piano_card(dict(case, cal=bad), None))
        o = self.econ(calibration_data=cal, price=10)
        low = o["calibrated"]["scenarios"][0]
        self.assertEqual(low["net_low"], round(low["copies_low"] * o["net_per_copy"], 2))
        self.assertIsNone(low["profit_cash_low"])
        self.assertIn("Scenari dal mercato reale", md(o))
        expected = o["calibrated"]["scenarios"][1]
        (self.home / "calibration.json").write_text(json.dumps(cal), encoding="utf-8")
        out = self.raw / "econ.json"
        result = subprocess.run([sys.executable, str(R / "calc_econ.py"), "--calibration", "-o", str(out)],
                                capture_output=True, encoding="utf-8", check=True)
        self.assertIn("Prezzo non disponibile", result.stdout)
        calc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(calc["scenarios"], [])
        self.assertIsNone(calc["net_per_copy"])
        mid = calc["calibrated"]["scenarios"][1]
        self.assertEqual((mid["copies_low"], mid["copies_high"]), (expected["copies_low"], expected["copies_high"]))
        self.assertIsNone(mid["net_low"])

    def test_price_bands_only_compare_dollars(self):
        from market_page import game_price
        for currency, expected in (("EUR", None), (None, None), ("USD", 9.99)):
            (self.raw / "econ.json").write_text(json.dumps(dict(inputs=dict(price=9.99, currency=currency))), encoding="utf-8")
            self.assertEqual(game_price(str(self.root)), expected)

    def test_page_audiences_and_absence(self):
        from publisher_scout import compare
        import status_page
        today = dt.date(2026, 10, 20)
        def build(audience="private", hide=(), include=()):
            return status_page.build(str(self.root), audience, include, [], set(hide), today)
        self.assertIn("Vendite del gioco non stimabili", build())
        o = self.econ(wishlists=[500], conv=[10], wishlist_source="PRIVATE-FORECAST-INPUT", calibration_data=self.calibration())
        self.assertIsNone(o["scenarios"][0]["net"])
        self.assertIn("unavailable", compare(o))
        self.assertIn("unavailable", compare(self.econ(price=10, wishlists=[100])))
        (self.raw / "econ.json").write_text(json.dumps(o), encoding="utf-8")
        (self.root / "03-pricing.md").write_text("# Piano\nPRIVATE-PRICING-DOC", encoding="utf-8")
        (self.root / "metrics.csv").write_text("date,metric,value,note\n2026-10-15,PRIVATE-CASH-METRIC,123,\n", encoding="utf-8")
        (self.root / "status.json").write_text(json.dumps(dict(verdict=dict(color="giallo", probability="PRIVATE-PROBABILITY"))), encoding="utf-8")
        self.assertIn("PRIVATE-FORECAST-INPUT", build("partner"))
        private = build()
        self.assertIn("n = 40", private)
        self.assertIn("PRIVATE-FORECAST-INPUT", private)
        self.assertIn("PRIVATE-CASH-METRIC", private)
        self.assertIn("PRIVATE-PROBABILITY", private)
        self.assertNotIn("TypeError", private)
        for page in (build("publisher", include=["03-pricing"]), build(hide=["economics"])):
            self.assertNotIn("Scenari di vendita dal mercato reale", page)
            self.assertNotIn("PRIVATE-FORECAST-INPUT", page)
            self.assertNotIn("PRIVATE-PRICING-DOC", page)
            self.assertNotIn("PRIVATE-CASH-METRIC", page)
            self.assertNotIn("PRIVATE-PROBABILITY", page)
        # Even the price-only report with optional wishlist scenarios must render its charts.
        (self.raw / "econ.json").write_text(json.dumps(self.econ(price=10, wishlists=[500])), encoding="utf-8")
        page = build()
        self.assertNotIn("TypeError", page)
        self.assertNotIn("Utile di cassa per scenario", page)


if __name__ == "__main__":
    unittest.main()
