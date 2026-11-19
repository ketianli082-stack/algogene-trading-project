"""Offline guards for the four-asset strategy (no ALGOGENE credentials needed)."""
import importlib.util
import math
from datetime import datetime, timedelta
from pathlib import Path
import sys
import types
import unittest

algo = types.ModuleType("AlgoAPI")
algo.AlgoAPIUtil = types.SimpleNamespace(
    OrderObject=lambda **kwargs: types.SimpleNamespace(**kwargs))
algo.AlgoAPI_Backtest = types.SimpleNamespace()
sys.modules.setdefault("AlgoAPI", algo)
path = Path(__file__).resolve().parents[1] / "src/four_asset_basis_exp016.py"
spec = importlib.util.spec_from_file_location("exp016_strategy", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeHandler:
    def __init__(self):
        self.calls = []
        self.logs = []
        self.histories = {}

    def getHistoricalBar(self, contract, numOfBar, interval):
        assert interval == "D"
        return self.histories[contract["instrument"]]

    def sendOrder(self, order):
        self.calls.append(order)

    def consoleLog(self, *args):
        self.logs.append(args)


class FourAssetGuards(unittest.TestCase):
    def test_positive_basis_and_no_future_in_training(self):
        spot = [100.0] * 62
        futures = [100.0 * math.exp((i % 6) * 0.001) for i in range(61)]
        futures += [110.0]
        x = mod._basis_stats(spot, futures, 60)
        self.assertIsNotNone(x)
        self.assertGreater(x["z"], 2.0)
        # Shift the last observation but not the training window: normalizer fixed.
        futures[-1] = 111.0
        y = mod._basis_stats(spot, futures, 60)
        self.assertAlmostEqual(x["mean"], y["mean"], places=12)
        self.assertAlmostEqual(x["sd"], y["sd"], places=12)

    def test_four_instruments_and_pre_execution_day_history(self):
        e = mod.AlgoEvent()
        e.evt = FakeHandler()
        start = datetime(2023, 1, 1)
        now = start + timedelta(days=65)
        for sym in mod.SYMBOLS:
            is_fut = sym.endswith("M")
            e.evt.histories[sym] = {
                start + timedelta(days=i): {"c": (
                    120.0 if i == 65 else 100.0 * math.exp(
                        ((i % 6) * 0.001) if is_fut else 0))}
                for i in range(66)}
        data = e._history(now)
        self.assertEqual(set(data), {"BTC", "ETH"})
        self.assertLess(abs(data["BTC"][0]["z"]), 5.0)
        # The extreme future price on execution day must be ignored.
        self.assertLess(data["BTC"][2], 105.0)

    def test_volumes_rounded_down_and_positive(self):
        self.assertEqual(mod._volume(100, 1, 255), 2)
        self.assertEqual(mod._volume(100, 1, 95), 0)
        self.assertEqual(mod._volume(-1, 1, 255), 0)

    def test_fill_confirmation_and_exit_two_legs(self):
        e = mod.AlgoEvent()
        e.evt = FakeHandler()
        e._send_open("BTC", 1, 1, -1, datetime(2023, 5, 1), 2.3)
        self.assertEqual(e.states["BTC"]["phase"], "OPENING")
        self.assertEqual(len(e.evt.calls), 2)
        self.assertEqual([o.buysell for o in e.evt.calls], [1, -1])
        for sym in mod.PAIRS["BTC"]:
            e.on_orderfeed(types.SimpleNamespace(
                instrument=sym, status="success", openclose="open",
                tradeID="id-" + sym))
        self.assertEqual(e.states["BTC"]["phase"], "OPEN")
        e._send_close("BTC", "z_reverted", datetime(2023, 5, 2))
        self.assertEqual(e.states["BTC"]["phase"], "CLOSING")
        for sym in mod.PAIRS["BTC"]:
            e.on_orderfeed(types.SimpleNamespace(
                instrument=sym, status="success", openclose="close",
                tradeID="id-" + sym))
        self.assertEqual(e.states["BTC"]["phase"], "FLAT")

    def test_missing_fill_halts_pair(self):
        e = mod.AlgoEvent()
        e.evt = FakeHandler()
        e._send_open("ETH", 20, 20, -1, datetime(2023, 7, 1), 2.0)
        e.on_orderfeed(types.SimpleNamespace(
            instrument="ETHUSD", status="rejected", openclose="open"))
        self.assertTrue(e.halted)
        self.assertEqual(e.states["ETH"]["phase"], "HALT")


if __name__ == "__main__":
    unittest.main()
