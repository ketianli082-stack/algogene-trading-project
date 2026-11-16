import sys
import types
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
from test_algogene_crypto_v1_0 import load_strategy_module, FakeHandler
from test_v1_2 import load


class NativeStopTest(unittest.TestCase):
    def setUp(self):
        load_strategy_module()
        self.atr = 10.0
        fake_numpy = types.SimpleNamespace(array=lambda values, dtype: values)
        fake_talib = types.SimpleNamespace(ATR=lambda *args, **kwargs: [self.atr])
        with patch.dict(sys.modules, {"numpy": fake_numpy, "talib": fake_talib}):
            self.module = load("v1_3", "src/algogene_crypto_v1_3.py")
            self.baseline = load("v1_2_stop_baseline", "src/algogene_crypto_v1_2.py")
        self.now = datetime(2021, 1, 1)
        FakeHandler.history_response = {
            str(self.now - timedelta(hours=i)): {"o": 100, "h": 101, "l": 99, "c": 100}
            for i in range(1, 202)
        }
        FakeHandler.history_response[str(self.now - timedelta(hours=1))] = {
            "o": 100, "h": 106, "l": 99, "c": 105}

    def enter(self):
        algo = self.module.AlgoEvent()
        algo.start({"subscribeList": ["BTCUSD"]})
        event = types.SimpleNamespace(instrument="BTCUSD", timestamp=self.now, askPrice=106)
        algo.on_marketdatafeed(event, {"availableBalance": 10000})
        return algo, event

    def test_native_stop_attached_without_changing_atr_quantity(self):
        algo, _ = self.enter()
        self.assertFalse(algo.halted)
        self.assertEqual(len(algo.evt.orders), 1)
        order = algo.evt.orders[0]
        self.assertEqual(order.stopLossLevel, 86)
        self.assertEqual(order.volume, self.baseline.position_volume(10000, 106, 10))
        self.assertEqual(order.buysell, 1)
        self.assertEqual(order.ordertype, 0)

    def test_nonpositive_stop_does_not_send_order(self):
        self.atr = 60
        algo, _ = self.enter()
        self.assertEqual(algo.evt.orders, [])
        self.assertTrue(any(items[0] == "V1.3_SKIP_STOP" for items in algo.evt.logs))

    def test_platform_stop_close_callback_clears_state_without_duplicate_close(self):
        algo, event = self.enter()
        algo.on_orderfeed(types.SimpleNamespace(status="success", openclose="open", tradeID="1", fill_price=106))
        algo.on_orderfeed(types.SimpleNamespace(status="success", openclose="close", tradeID="1", fill_price=85))
        self.assertIsNone(algo.trade_id)
        self.assertFalse(algo.pending)
        algo.on_marketdatafeed(event, {"availableBalance": 10000})
        self.assertEqual(len(algo.evt.orders), 1)

    def test_signal_state_is_identical_to_v1_2(self):
        a, b = self.module.TrendState(), self.baseline.TrendState()
        for i in range(220):
            close = 100 + i % 7
            bar = {"o": close, "h": close+1, "l": close-1, "c": close}
            timestamp = self.now + timedelta(hours=i)
            self.assertEqual(a.add(timestamp, bar), b.add(timestamp, bar))
