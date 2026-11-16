import importlib.util
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
import unittest
from unittest.mock import patch
from test_algogene_crypto_v1_0 import load_strategy_module, FakeHandler


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ATRSizingTest(unittest.TestCase):
    def setUp(self):
        load_strategy_module()
        self.atr_value = 10
        fake_numpy = types.SimpleNamespace(array=lambda values, dtype: values)
        fake_talib = types.SimpleNamespace(ATR=lambda *args, **kwargs: [self.atr_value])
        with patch.dict(sys.modules, {"numpy": fake_numpy, "talib": fake_talib}):
            self.module = load("v1_2", "src/algogene_crypto_v1_2.py")

    def test_size_decreases_with_volatility_and_is_capped(self):
        size = self.module.position_volume
        self.assertEqual(size(10000, 30000, 100), 0.02)
        self.assertEqual(size(10000, 30000, 400), 0.01)
        self.assertEqual(size(10000, 30000, 2000), 0)
        self.assertEqual(size(10000, 30000, float("nan")), 0)
        self.assertEqual(size(10000, 30000, 0), 0)

    def test_notional_cap_does_not_round_up_small_budget(self):
        self.assertEqual(self.module.position_volume(100, 30000, 1), 0)

    def test_entry_uses_variable_order_volume(self):
        now = datetime(2021, 1, 1)
        FakeHandler.history_response = {
            str(now - timedelta(hours=i)): {"o": 100, "h": 101, "l": 99, "c": 100}
            for i in range(1, 202)
        }
        FakeHandler.history_response[str(now - timedelta(hours=1))] = {
            "o": 100, "h": 106, "l": 99, "c": 105}
        algo = self.module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        algo.on_marketdatafeed(types.SimpleNamespace(instrument="BTCUSD", timestamp=now, askPrice=106),
                               {"availableBalance": 10000})
        self.assertFalse(algo.halted)
        self.assertEqual(len(algo.evt.orders), 1)
        self.assertEqual(algo.evt.orders[0].volume, 0.02)
        self.assertEqual(algo.evt.orders[0].buysell, 1)

    def test_ema_donchian_logic_matches_v1_1(self):
        baseline = load("v1_1_baseline", "src/algogene_crypto_v1_1.py").TrendState()
        adaptive = self.module.TrendState()
        for i in range(220):
            close = 100 + (i % 7)
            bar = {"o": close, "h": close+1, "l": close-1, "c": close}
            ts = datetime(2020, 12, 1) + timedelta(hours=i)
            self.assertEqual(baseline.add(ts, bar), adaptive.add(ts, bar))


class PlatformEvidenceTest(unittest.TestCase):
    def test_redaction_preserves_platform_metrics_and_types(self):
        module = load("v1_2_pipeline", "scripts/algogene_v1_2_pipeline.py")
        payload = {"performance": {"TotalPnL": -12.3, "simpleReturn": 0.0},
                   "user": "user-value", "res": ["key-value", "normal"]}
        scrubbed = module.redact(payload, ("key-value", "user-value"))
        self.assertEqual(scrubbed["performance"], payload["performance"])
        self.assertEqual(scrubbed["user"], "[REDACTED]")
        self.assertEqual(scrubbed["res"], ["[REDACTED]", "normal"])
