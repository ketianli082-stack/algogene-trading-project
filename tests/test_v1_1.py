import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
import unittest
from test_algogene_crypto_v1_0 import load_strategy_module, FakeHandler


class TrendTest(unittest.TestCase):
    def setUp(self):
        load_strategy_module()  # Install the fake AlgoAPI, never a platform run.
        path = Path(__file__).resolve().parents[1] / "src/algogene_crypto_v1_1.py"
        spec = importlib.util.spec_from_file_location("v1_1", path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.state = self.module.TrendState()
        self.start = datetime(2020, 11, 1)
        self.bar = {"o": 100, "h": 101, "l": 99, "c": 100}
        for i in range(200):
            self.state.add(self.start + timedelta(hours=4*i), self.bar)

    def test_breakout_excludes_signal_bar_high_and_ema_is_seeded(self):
        self.assertEqual(self.state.ema, 100)
        signal = self.state.add(self.start + timedelta(hours=800),
                                {"o": 100, "h": 110, "l": 99, "c": 102})
        self.assertTrue(signal["entry"])
        self.assertFalse(signal["exit"])

    def test_duplicate_bar_does_not_update_ema_twice(self):
        last = self.state.last_time
        self.assertIsNone(self.state.add(last, {"o": 300, "h": 400, "l": 200, "c": 300}))
        self.assertEqual(self.state.ema, 100)

    def test_downside_channel_causes_exit(self):
        signal = self.state.add(self.start + timedelta(hours=800),
                                {"o": 100, "h": 100, "l": 95, "c": 97})
        self.assertTrue(signal["exit"])
        self.assertFalse(signal["entry"])

    def test_insufficient_history_halts_without_order(self):
        FakeHandler.history_response = {self.start: self.bar}
        algo = self.module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        from types import SimpleNamespace
        algo.on_marketdatafeed(SimpleNamespace(instrument="BTCUSD", timestamp=datetime(2021, 1, 1)), {})
        self.assertTrue(algo.halted)
        self.assertEqual(algo.evt.orders, [])

    def test_current_and_future_bars_are_not_used_for_signals(self):
        now = datetime(2021, 1, 1)
        FakeHandler.history_response = {
            now - timedelta(hours=4*i): self.bar for i in range(1, 202)
        }
        spike = {"o": 100, "h": 10000, "l": 100, "c": 10000}
        FakeHandler.history_response[now] = spike
        FakeHandler.history_response[now + timedelta(hours=4)] = spike
        algo = self.module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        from types import SimpleNamespace
        algo.on_marketdatafeed(SimpleNamespace(instrument="BTCUSD", timestamp=now), {})
        self.assertFalse(algo.halted)
        self.assertEqual(algo.trend.last_time, now - timedelta(hours=4))
        self.assertEqual(algo.trend.ema, 100)
        self.assertEqual(algo.evt.orders, [])

    def test_each_hourly_event_is_processed(self):
        now = datetime(2021, 1, 1, 1)
        FakeHandler.history_response = {
            str(now - timedelta(hours=i)): self.bar for i in range(1, 202)
        }
        algo = self.module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        from types import SimpleNamespace
        algo.on_marketdatafeed(SimpleNamespace(instrument="BTCUSD", timestamp=now), {})
        self.assertEqual(len(algo.evt.history_calls), 1)
        self.assertEqual(algo.evt.history_calls[0]["interval"], "H")
        self.assertFalse(algo.halted)
        self.assertEqual(algo.trend.last_time, now - timedelta(hours=1))
        self.assertEqual(algo.evt.orders, [])

    def test_platform_string_timestamps_are_normalized(self):
        now = datetime(2021, 1, 1)
        FakeHandler.history_response = {
            str(now - timedelta(hours=4*i)): self.bar for i in range(1, 202)
        }
        algo = self.module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        from types import SimpleNamespace
        algo.on_marketdatafeed(SimpleNamespace(instrument="BTCUSD", timestamp=now), {})
        self.assertFalse(algo.halted)
        self.assertEqual(algo.trend.ema, 100)
        self.assertEqual(algo.trend.last_time, now - timedelta(hours=4))
