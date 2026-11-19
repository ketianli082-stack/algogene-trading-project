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
batch = importlib.import_module("algogene_history_research")


class HistoryResearchTest(unittest.TestCase):
    def setUp(self):
        self.config = batch.plan()

    def module(self, index=0, step=0.001):
        return source_module(batch.source_for(batch.REGISTERED[index], step))

    def test_precision_rescues_small_budget_without_increasing_risk_or_cap(self):
        fine, coarse = self.module(), self.module(step=0.01)
        self.assertEqual(fine.position_volume(10000, 30000, 885), 0.005)
        self.assertEqual(coarse.position_volume(10000, 30000, 885), 0)
        self.assertLessEqual(fine.position_volume(10000, 30000, 885) * 2 * 885, 10)
        self.assertLessEqual(fine.position_volume(10000, 1000, 1), 0.02)
        with self.assertRaises(ValueError):
            batch.source_for(batch.REGISTERED[0], 0.00001)

    def test_ema_control_preserves_baseline_signals(self):
        baseline = source_module((batch.ROOT / "src/algogene_crypto_v1_4_ema.py").read_text()).TrendState()
        control = self.module().TrendState()
        start = datetime(2021, 1, 1)
        for i in range(280):
            close = 100 + i % 9
            bar = {"o": close, "h": close + 1, "l": close - 1, "c": close}
            a = baseline.add(start + timedelta(hours=i), bar)
            b = control.add(start + timedelta(hours=i), bar)
            self.assertEqual(a, None if b is None else {key: b[key] for key in ("entry", "exit", "time", "close")})

    def test_range_recovery_requires_a_flat_regime_and_uses_past_bands(self):
        module = self.module(3)
        states = [module.TrendState(), module.TrendState()]
        for i, state in enumerate(states):
            state.ema = 100.0
            state.ema_history.extend([100.0 if i == 0 else 110.0] * 24)
            state.bars.extend([(101, 94)] * 20)
            state.closes.extend([100] * 19 + [95])
            state.previous_close, state.previous_lower = 95, 97
        bar = {"o": 98.2, "h": 98.5, "l": 98, "c": 98.2}
        self.assertTrue(states[0].add(datetime(2021, 2, 1), bar)["entry"])
        self.assertFalse(states[1].add(datetime(2021, 2, 1), bar)["entry"])

    def enter(self, atr):
        module = self.module(1)
        module.ATR = lambda *args, **kwargs: [atr]
        algo = module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        now = datetime(2021, 2, 1)
        type(algo.evt).history_response = {now - timedelta(hours=i): {"o": 1000, "h": 1001, "l": 999, "c": 1000}
                                           for i in range(1, 261)}
        algo.trend.add = lambda t, b: {"entry": True, "exit": False, "time": t, "close": 1000, "target": None}
        algo.on_marketdatafeed(types.SimpleNamespace(instrument="BTCUSD", timestamp=now, askPrice=1000),
                               {"availableBalance": 10000})
        return algo

    def test_native_bracket_and_holding_seconds_are_attached_to_order(self):
        algo = self.enter(100)
        order = algo.evt.orders[0]
        self.assertEqual(order.stopLossLevel, 800)
        self.assertEqual(order.takeProfitLevel, 1300)
        self.assertEqual(order.holdtime, 72 * 3600)
        self.assertEqual(order.buysell, 1)

    def test_small_prospective_target_is_skipped_without_reconstructing_pnl(self):
        algo = self.enter(10)
        self.assertEqual(algo.evt.orders, [])
        self.assertTrue(any(line[0] == "V1.3_SKIP_TARGET" for line in algo.evt.logs))

    def test_precision_needs_actual_native_open_and_close_at_requested_volume(self):
        result = {"status": "COLLECTED", "platform_responses": {"transactions": [{"res": [
            {"openclose": "open", "volume": 0.001}, {"openclose": "close", "volume": 0.01}]}]}}
        self.assertFalse(batch.precision_verified(result))
        result["platform_responses"]["transactions"][-1]["res"][-1]["volume"] = 0.001
        self.assertTrue(batch.precision_verified(result))

    def test_rejected_probe_uses_registered_coarse_fallback_without_fine_control(self):
        def cloud(**kwargs):
            probe = kwargs["experiment"].endswith("precision-probe")
            result = {"status": "SUBMISSION_REJECTED" if probe else "COLLECTED", "errors": [], "platform_responses": {}}
            if not probe:
                result["platform_responses"] = {"statistics": [{"setting": {"TradeCost": "1.0"},
                    "performance": {"Score_Total": 35.0, "TradeCnt": 2}}],
                    "transactions": [{"res": [{"TradeCost": -1}]}]}
            Path(kwargs["output_override"]).write_text(json.dumps(result))
            return 1 if probe else 0

        with tempfile.TemporaryDirectory() as directory, patch.object(batch, "OUT", Path(directory)), \
             patch.object(batch, "run_cloud", side_effect=cloud) as network, patch.object(batch, "archive"), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "1"}):
            self.assertEqual(batch.main(), 0)
            self.assertEqual(network.call_count, 5)
            result = json.loads((Path(directory) / "platform-responses.json").read_text())
            self.assertEqual(result["runs"][1]["status"], "NOT RUN")
            self.assertTrue(all(row["effective_model_step"] == 0.01 for row in result["runs"][2:]))

    def test_pending_probe_stops_without_fallback_submission(self):
        def pending(**kwargs):
            Path(kwargs["output_override"]).write_text(json.dumps({"status": "PENDING", "platform_responses": {}}))
            return 1
        with tempfile.TemporaryDirectory() as directory, patch.object(batch, "OUT", Path(directory)), \
             patch.object(batch, "run_cloud", side_effect=pending) as network, patch.object(batch, "archive"), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "1"}):
            self.assertEqual(batch.main(), 1)
            self.assertEqual(network.call_count, 1)


if __name__ == "__main__":
    unittest.main()
