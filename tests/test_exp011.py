from datetime import datetime, timedelta
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_v1_4_research import source_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
batch = importlib.import_module("algogene_combination_batch")


class CombinationResearchTest(unittest.TestCase):
    def setUp(self):
        self.config, self.rows = batch.plan()

    def module(self, index=0):
        return source_module(self.rows[index]["submitted_source"])

    def ready_state(self, index=0, rising=True):
        module = self.module(index)
        state = module.TrendState()
        state.ema, state.mid, state.fast = 100, (110 if rising else 90), 112
        state.ema_history.extend([90] * 24)
        state.previous_close = 111
        state.bars.extend([(114, 108)] * 40)
        return module, state

    def test_four_distinct_sources_share_native_cost_and_closed_holdouts(self):
        self.assertEqual(len(self.rows), 4)
        self.assertEqual(len({r["source_sha256"] for r in self.rows}), 4)
        for row in self.rows:
            settings = row["settings"]
            self.assertEqual((settings["StartDate"], settings["EndDate"], settings["dataset"], settings["TradeCost"]),
                             ("2021-01", "2023-12", 60, 1.0))
            self.assertFalse(settings["allowShortSell"])
            self.assertIn("volume=volume, stopLossLevel=stop_loss", row["submitted_source"])

    def test_breakout_requires_mid_above_slow_and_excludes_current_high(self):
        _, bullish = self.ready_state()
        _, bearish = self.ready_state(rising=False)
        bar = {"o": 120, "h": 130, "l": 119, "c": 120}
        self.assertTrue(bullish.add(datetime(2021, 2, 1), bar)["entry"])
        self.assertFalse(bearish.add(datetime(2021, 2, 1), bar)["entry"])

    def test_pullback_cross_can_enter_without_a_donchian_breakout(self):
        _, pullback = self.ready_state(2)
        _, breakout = self.ready_state(0)
        bar = {"o": 113, "h": 113.5, "l": 112.5, "c": 113}
        self.assertTrue(pullback.add(datetime(2021, 2, 1), bar)["entry"])
        self.assertFalse(breakout.add(datetime(2021, 2, 1), bar)["entry"])

    def test_size_uses_actual_stop_distance_and_never_increases_caps(self):
        fast, patient = self.module(0), self.module(1)
        self.assertEqual(fast.position_volume(10000, 20000, 200), 0.02)
        self.assertEqual(patient.position_volume(10000, 20000, 200), 0.01)
        self.assertLessEqual(patient.position_volume(10000, 20000, 300), fast.position_volume(10000, 20000, 300))
        for module in (fast, patient):
            self.assertLessEqual(module.position_volume(10000, 1000, 1), 0.02)

    def test_close_callback_starts_cooldown_without_blocking_existing_position_exit(self):
        module = self.module(0)
        algo = module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        now = datetime(2021, 2, 1)
        algo.last_event = now
        algo.on_orderfeed(types.SimpleNamespace(status="success", openclose="close", tradeID="mock-only"))
        self.assertEqual(algo.cooldown_until, now + timedelta(hours=6))
        history = {now - timedelta(hours=i): {"o": 100, "h": 101, "l": 99, "c": 100}
                   for i in range(1, 261)}
        algo.evt.history_response = history
        # FakeHandler uses its class-level fixture for history lookup.
        type(algo.evt).history_response = history
        algo.trend.add = lambda t, b: {"entry": True, "exit": True, "time": t, "close": 100}
        algo.trade_id = "mock-position"
        algo.on_marketdatafeed(types.SimpleNamespace(instrument="BTCUSD", timestamp=now + timedelta(hours=1), askPrice=100),
                               {"availableBalance": 10000})
        self.assertEqual(algo.evt.orders[-1].openclose, "close")
        algo.on_orderfeed(types.SimpleNamespace(status="success", openclose="close", tradeID="mock-position"))
        orders_before = len(algo.evt.orders)
        algo.on_marketdatafeed(types.SimpleNamespace(instrument="BTCUSD", timestamp=now + timedelta(hours=2), askPrice=100),
                               {"availableBalance": 10000})
        self.assertEqual(len(algo.evt.orders), orders_before)

    def test_native_score_values_are_copied_not_recalculated_or_filled(self):
        evidence = {"platform_responses": {"statistics": [{"performance": {"Score_Total": 36.0, "TotalPnL": -34.0}}]}}
        self.assertEqual(batch.native_fields(evidence), {"Score_Total": 36.0, "TotalPnL": -34.0})
        self.assertNotIn("score_Rsquare", batch.native_fields(evidence))

    def test_pending_stops_batch_after_one_submission_and_preserves_evidence(self):
        def pending(**kwargs):
            Path(kwargs["output_override"]).write_text(json.dumps({"status": "PENDING", "platform_responses": {}, "task_id": "mock-only"}))
            return 1
        with tempfile.TemporaryDirectory() as directory, patch.object(batch, "OUT", Path(directory)), \
             patch.object(batch, "run_cloud", side_effect=pending) as cloud, \
             patch.object(batch, "archive"), patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "1"}):
            self.assertEqual(batch.main(), 1)
            cloud.assert_called_once()
            result = json.loads((Path(directory) / "platform-responses.json").read_text())
            self.assertEqual(result["status"], "STOPPED")
            self.assertTrue(all(row["status"] == "NOT RUN" for row in result["runs"][1:]))


if __name__ == "__main__":
    unittest.main()
