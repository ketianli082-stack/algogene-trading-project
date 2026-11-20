"""Offline BTC V1.0 tests; AlgoAPI is stubbed, no exchange or backtest calls."""
import importlib.util
import pathlib
import sys
import types
import unittest

algo_pkg = types.ModuleType("AlgoAPI")
algo_pkg.AlgoAPIUtil = types.SimpleNamespace(OrderObject=object)
algo_pkg.AlgoAPI_Backtest = types.SimpleNamespace(AlgoEvtHandler=object)
sys.modules["AlgoAPI"] = algo_pkg
path = pathlib.Path(__file__).resolve().parents[1] / "strategy" / "btc_v1_0_ema60.py"
spec = importlib.util.spec_from_file_location("btc_v1_0", path)
btc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btc)


class TestBTCEma(unittest.TestCase):
    def test_ema_constant(self):
        self.assertEqual(btc.ema_series([100.0] * 60, 20)[-1], 100.0)

    def test_no_signal_without_warmup(self):
        self.assertEqual(btc.cross_signal([100.0] * 51), 0)

    def test_upward_cross(self):
        x = [100.0] * 80 + [100.0 + i for i in range(1, 5)]
        signals = [btc.cross_signal(x[:n]) for n in range(52, len(x)+1)]
        self.assertIn(1, signals)

    def test_downward_cross(self):
        x = [150.0] * 80 + [150.0 - i for i in range(1, 5)]
        signals = [btc.cross_signal(x[:n]) for n in range(52, len(x)+1)]
        self.assertIn(-1, signals)

    def test_price_from_quote_or_close(self):
        self.assertEqual(btc.quote_price({"bidPrice": 99, "askPrice": 101}), 100.0)
        self.assertEqual(btc.quote_price({"c": 105.0}), 105.0)
        self.assertIsNone(btc.quote_price({"c": -1}))

    def test_clock(self):
        self.assertEqual(str(btc.timestamp("2024-01-01T01:00:00Z")), "2024-01-01 01:00:00")


if __name__ == "__main__":
    unittest.main()
