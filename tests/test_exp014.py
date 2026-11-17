"""EXP014 offline one-factor, H1-only regression and safety guards."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_v1_4_research import source_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
batch = importlib.import_module("algogene_combination_batch_exp014")


class EXP014Tests(unittest.TestCase):
    def setUp(self):
        self.config, self.rows = batch.plan()

    def test_every_candidate_is_h1_and_each_changes_only_one_parameter(self):
        self.assertEqual([row["name"] for row in self.rows],
                         ["h1-gate-reference", "cost-gate-08",
                          "trend-slope-005", "breakout-buffer-010"])
        self.assertEqual(len({row["source_sha256"] for row in self.rows}), 4)
        reference = self.rows[0]["params"]
        allowed = ["max_cost_ratio", "min_slope_atr", "min_breakout_atr"]
        for index, row in enumerate(self.rows):
            settings = row["settings"]
            self.assertEqual((settings["StartDate"],settings["EndDate"],settings["dataset"],settings["TradeCost"]),
                             ("2021-01","2023-12",60,1))
            self.assertNotIn("H4", row["submitted_source"])
            self.assertIn('interval="H"', row["submitted_source"])
            differing = [key for key in reference if row["params"][key] != reference[key]]
            self.assertEqual(differing, [] if index == 0 else [allowed[index-1]])

    def test_baseline_same_entry_and_exit_as_exp013(self):
        original = source_module((batch.ROOT / "src/algogene_crypto_v1_7.py").read_text()).TrendState()
        updated = source_module(self.rows[0]["submitted_source"]).TrendState()
        from datetime import datetime, timedelta
        now = datetime(2021, 1, 1)
        for i in range(310):
            price = 100 + (i % 25) + i / 100
            bar = {"o":price, "h":price+1, "l":price-1, "c":price}
            a = original.add(now + timedelta(hours=i), bar)
            b = updated.add(now + timedelta(hours=i), bar)
            self.assertEqual(a, None if b is None else {
                k:b[k] for k in ("entry", "exit", "time", "close")})

    def test_stronger_slope_and_breakout_gates_are_monotone(self):
        from datetime import datetime, timedelta
        import types
        for index, decision in ((0, True), (1, False), (2, False), (3, False)):
            module = source_module(self.rows[index]["submitted_source"])
            module.ATR = lambda *args, **kwargs: [500.0]
            algo = module.AlgoEvent()
            algo.start({"subscribeList": ["BTCUSD"]})
            now = datetime(2021, 2, 1)
            type(algo.evt).history_response = {
                str(now-timedelta(hours=i)): {"o":30000, "h":30001, "l":29999, "c":30000}
                for i in range(1, 261)}
            algo.trend.add = lambda t,b: {"entry":True,"exit":False,"time":t,"close":30000,
                                         "ema_slope": 20.0, "breakout_margin": 30.0}
            algo.on_marketdatafeed(
                types.SimpleNamespace(instrument="BTCUSD", timestamp=now, askPrice=30000),
                {"availableBalance":10000})
            # Reference: volume .01; cost proxy 3*500*.01=15 => cost ratio 0.0667,
            # thus tighter .08 gate still permits it. Slope=.04*ATR and breakout=.06*ATR
            # fail the distinct slope .05 and breakout .10 gates respectively.
            self.assertEqual(len(algo.evt.orders), 1 if index in (0,1) else 0)

    def test_changes_to_2024_or_2025_are_rejected(self):
        copied = dict(self.config)
        copied["settings"] = dict(copied["settings"], EndDate="2025-12")
        original = Path.read_text
        def tamper(path,*args,**kwargs):
            return json.dumps(copied) if path.name == "exp014_h1_quality.json" else original(path,*args,**kwargs)
        with patch.object(Path, "read_text", tamper), self.assertRaises(ValueError):
            batch.plan()

    def test_retry_never_submits_and_pending_stops_batch(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(batch, "OUT", Path(folder)), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT":"2"}), \
             patch.object(batch, "run_cloud") as cloud:
            self.assertEqual(batch.main(), 1)
            cloud.assert_not_called()

        def pending(**kwargs):
            Path(kwargs["output_override"]).write_text(json.dumps({
                "status":"PENDING","platform_responses":{},"errors":[]}))
            return 1
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(batch, "OUT", Path(folder)), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT":"1"}), \
             patch.object(batch, "archive"), \
             patch.object(batch, "run_cloud", side_effect=pending) as cloud:
            self.assertEqual(batch.main(), 1)
            cloud.assert_called_once()
            saved=json.loads((Path(folder)/"platform-responses.json").read_text())
            self.assertTrue(all(row["status"] == "NOT RUN" for row in saved["runs"][1:]))


if __name__ == "__main__":
    unittest.main()
