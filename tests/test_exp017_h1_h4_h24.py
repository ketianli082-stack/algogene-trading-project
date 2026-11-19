"""Offline unit tests for H1 -> H4/H24 crypto strategy; no cloud access."""
import ast
import importlib.util
import math
from datetime import datetime, timedelta
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/four_asset_h1_exp017.py"
algo = types.ModuleType("AlgoAPI")
algo.AlgoAPIUtil = types.SimpleNamespace(
    OrderObject=lambda **kwargs: types.SimpleNamespace(**kwargs))
algo.AlgoAPI_Backtest = types.SimpleNamespace()
sys.modules.setdefault("AlgoAPI", algo)
spec = importlib.util.spec_from_file_location("exp017_strategy", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DummyHandler:
    def __init__(self):
        self.calls, self.logs, self.histories = [], [], {}

    def getHistoricalBar(self, contract, numOfBar, interval):
        assert interval == "H", "Never ask ALGOGENE for H4 directly"
        assert numOfBar == 440
        return self.histories[contract["instrument"]]

    def sendOrder(self, order):
        self.calls.append(order)

    def consoleLog(self, *parts):
        self.logs.append(parts)


class H1H4H24Guards(unittest.TestCase):
    def test_no_unsupported_methods_or_native_h4_query(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        banned = {"remove", "pop", "replace", "update", "endswith"}
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)}
        self.assertFalse(called & banned)
        self.assertIn('interval="H"', SOURCE.read_text())
        self.assertNotIn('interval="H4"', SOURCE.read_text())
        self.assertNotIn('interval="D"', SOURCE.read_text())
        self.assertEqual(m.HISTORY_BARS, 440)

    def test_exact_four_h1_bars_make_h4_with_wicks(self):
        end = datetime(2023, 5, 20, 4)
        raw = {end - timedelta(hours=3): {"o": 100, "h": 102, "l": 98, "c": 101},
               end - timedelta(hours=2): {"o": 101, "h": 105, "l": 100, "c": 103},
               end - timedelta(hours=1): {"o": 103, "h": 104, "l": 95, "c": 99},
               end: {"o": 99, "h": 101, "l": 97, "c": 100}}
        candles = m._resample(raw, 4)
        self.assertEqual(list(candles), [end])
        self.assertEqual(candles[end], {"o": 100, "h": 105, "l": 95, "c": 100})
        del raw[end - timedelta(hours=2)]
        self.assertNotIn(end, m._resample(raw, 4))

    def test_h24_only_after_complete_day_and_utc_end(self):
        end = datetime(2023, 6, 2, 0)
        raw = {end - timedelta(hours=i): {"o": 100, "h": 101,
                "l": 99, "c": 100} for i in range(24)}
        self.assertEqual(set(m._resample(raw, 24)), {end})
        del raw[end - timedelta(hours=20)]
        self.assertEqual(m._resample(raw, 24), {})

    def test_future_hour_is_excluded_and_invalid_ohlc_is_excluded(self):
        now = datetime(2023, 6, 2, 5)
        raw = {now - timedelta(hours=1): {"o": 101, "h": 102, "l": 100, "c": 101},
               now: {"o": 1000, "h": 2000, "l": 900, "c": 1500},
               now + timedelta(hours=1): {"o": 2000, "h": 2100, "l": 1900, "c": 2000},
               now - timedelta(hours=2): {"o": 100, "h": 99, "l": 98, "c": 101}}
        selected = m._read_hours(raw, now)
        self.assertEqual(set(selected), {now - timedelta(hours=1)})

    def test_robust_ou_signal_excludes_next_bar_and_detects_gaps(self):
        end = datetime(2023, 6, 2, 0)
        s = {}
        f = {}
        for i in range(44):
            t = end - timedelta(hours=4 * (43 - i))
            s[t] = {"c": 100}
            f[t] = {"c": 100 * math.exp(0.004 * math.sin(i / 5))}
        a = m._signal(s, f)
        self.assertIsNotNone(a)
        f[end + timedelta(hours=4)] = {"c": 500}
        b = m._signal(s, f)
        self.assertEqual(a, b)
        del s[end - timedelta(hours=16)]
        self.assertIsNone(m._signal(s, f))

    def test_position_sizing_fractional_and_no_round_up(self):
        self.assertEqual(m._quantity(100000, 1, 75000), 0.75)
        self.assertEqual(m._quantity(2000, 1, 75000), 37.5)
        self.assertEqual(m._quantity(90000, 1, 100), 0)
        self.assertEqual(m._quantity(-1, 1, 75000), 0)

    def test_pair_history_fails_independently_not_as_global_four_asset(self):
        now = datetime(2023, 6, 2, 1)
        handler = DummyHandler()
        start = now - timedelta(hours=440)
        for symbol in m.SYMBOLS:
            is_fut = symbol[-1:] == "M"
            handler.histories[symbol] = {
                start + timedelta(hours=i): {
                    "o": 100 + (0.005 * i if not is_fut else 0),
                    "h": 101 + (0.005 * i if not is_fut else 0),
                    "l": 99 + (0.005 * i if not is_fut else 0),
                    "c": 100 + (0.005 * i if not is_fut else 0)}
                for i in range(441)}
        # All four initially good. The execution-hour future price is excluded.
        handler.histories["BTCUSDM"][now] = {"o": 200, "h": 201, "l": 199, "c": 200}
        e = m.AlgoEvent()
        e.evt = handler
        self.assertIsNotNone(e._history_pair("BTC", now))
        del handler.histories["ETHUSDM"][now - timedelta(hours=1)]
        with self.assertRaisesRegex(ValueError, "H1_NOT_ALIGNED"):
            e._history_pair("ETH", now)
        self.assertIsNotNone(e._history_pair("BTC", now))

    def test_confirm_two_legs_and_close(self):
        e = m.AlgoEvent()
        e.evt = DummyHandler()
        t = datetime(2023, 6, 1, 5)
        e.last_hour = t
        e._open("BTC", 0.75, 0.75, -1, t, 0.004)
        self.assertEqual(e.states["BTC"]["phase"], "OPENING")
        self.assertEqual(len(e.evt.calls), 2)
        self.assertEqual((e.evt.calls[0].buysell,
                          e.evt.calls[1].buysell), (1, -1))
        for sym in m.PAIRS["BTC"]:
            e.on_orderfeed(types.SimpleNamespace(instrument=sym,
                status="success", openclose="open", tradeID="trade-" + sym))
        self.assertEqual(e.states["BTC"]["phase"], "OPEN")
        e._close("BTC", "unit_test", t + timedelta(hours=1))
        self.assertEqual(e.states["BTC"]["phase"], "CLOSING")
        for sym in m.PAIRS["BTC"]:
            e.on_orderfeed(types.SimpleNamespace(instrument=sym,
                status="success", openclose="close", tradeID="trade-" + sym))
        self.assertEqual(e.states["BTC"]["phase"], "FLAT")
        self.assertEqual(len(e.evt.calls), 4)
        self.assertEqual(e.states["BTC"]["cooldown_until"], t + timedelta(hours=12))

    def test_rejected_second_leg_halts_new_orders(self):
        e = m.AlgoEvent()
        e.evt = DummyHandler()
        t = datetime(2023, 6, 1, 5)
        e._open("ETH", 20, 20, 1, t, -0.004)
        e.on_orderfeed(types.SimpleNamespace(
            instrument="ETHUSD", status="success", openclose="open", tradeID=10))
        e.on_orderfeed(types.SimpleNamespace(
            instrument="ETHUSDM", status="failed", openclose="open"))
        self.assertTrue(e.halted)
        self.assertEqual(e.states["ETH"]["phase"], "HALT")
        self.assertTrue(any(getattr(o, "openclose", None) == "close"
                            for o in e.evt.calls))


if __name__ == "__main__":
    unittest.main()
