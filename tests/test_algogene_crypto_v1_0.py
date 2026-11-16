import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "algogene_crypto_v1_0.py"


class FakeOrder:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeHandler:
    history_response = {}

    def __init__(self, owner, event):
        self.owner = owner
        self.event = event
        self.orders = []
        self.logs = []
        self.started = False
        self.history_calls = []

    def start(self):
        self.started = True

    def consoleLog(self, *items):
        self.logs.append(items)

    def getHistoricalBar(self, **kwargs):
        self.history_calls.append(kwargs)
        return self.history_response

    def sendOrder(self, order):
        self.orders.append(order)


def load_strategy_module():
    algo_api = types.ModuleType("AlgoAPI")
    algo_api.AlgoAPIUtil = types.SimpleNamespace(OrderObject=FakeOrder)
    algo_api.AlgoAPI_Backtest = types.SimpleNamespace(AlgoEvtHandler=FakeHandler)
    sys.modules["AlgoAPI"] = algo_api
    spec = importlib.util.spec_from_file_location("algogene_crypto_v1_0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StrategySmokeTest(unittest.TestCase):
    def setUp(self):
        self.module = load_strategy_module()
        FakeHandler.history_response = {
            datetime(2024, 1, 1, 0): {"o": 90, "h": 101, "l": 89, "c": 100},
            datetime(2024, 1, 1, 1): {"o": 100, "h": 102, "l": 98, "c": 101},
            datetime(2024, 1, 1, 2): {"o": 101, "h": 103, "l": 99, "c": 102},
        }
        self.strategy = self.module.AlgoEvent()
        self.strategy.start({"subscribeList": ["BTCUSD"]})

    @staticmethod
    def market_event(timestamp):
        return types.SimpleNamespace(
            instrument="BTCUSD",
            timestamp=timestamp,
            askPrice=100.0,
            lastPrice=99.5,
        )

    def test_reads_history_and_submits_exactly_one_round_trip(self):
        first = datetime(2024, 1, 1, 3)
        self.strategy.on_marketdatafeed(self.market_event(first), {})

        self.assertEqual(len(self.strategy.evt.history_calls), 1)
        self.assertEqual(len(self.strategy.evt.orders), 1)
        opening_order = self.strategy.evt.orders[0]
        self.assertEqual(opening_order.instrument, "BTCUSD")
        self.assertEqual(opening_order.openclose, "open")
        self.assertEqual(opening_order.buysell, 1)
        self.assertEqual(opening_order.ordertype, 0)
        self.assertEqual(opening_order.volume, 0.01)
        self.assertAlmostEqual(opening_order.stopLossLevel, 98.0)

        self.strategy.on_orderfeed(
            types.SimpleNamespace(
                status="success",
                openclose="open",
                tradeID="test-trade-1",
                fill_price=100.0,
            )
        )
        self.strategy.on_marketdatafeed(
            self.market_event(first + timedelta(hours=1)), {}
        )
        self.assertEqual(len(self.strategy.evt.orders), 2)
        closing_order = self.strategy.evt.orders[1]
        self.assertEqual(closing_order.tradeID, "test-trade-1")
        self.assertEqual(closing_order.openclose, "close")

        self.strategy.on_orderfeed(
            types.SimpleNamespace(
                status="success",
                openclose="close",
                tradeID="test-trade-1",
                fill_price=101.0,
            )
        )
        self.strategy.on_marketdatafeed(
            self.market_event(first + timedelta(hours=2)), {}
        )
        self.assertTrue(self.strategy.completed)
        self.assertEqual(len(self.strategy.evt.orders), 2)

    def test_does_not_trade_when_history_is_incomplete(self):
        FakeHandler.history_response = {
            datetime(2024, 1, 1, 0): {"o": 90, "h": 101, "l": 89, "c": 100}
        }
        self.strategy.on_marketdatafeed(
            self.market_event(datetime(2024, 1, 1, 1)), {}
        )
        self.assertTrue(self.strategy.history_attempted)
        self.assertFalse(self.strategy.history_ok)
        self.assertEqual(self.strategy.evt.orders, [])

    def test_disables_itself_without_btcusd_subscription(self):
        strategy = self.module.AlgoEvent()
        strategy.start({"subscribeList": ["ETHUSD"]})
        strategy.on_marketdatafeed(
            self.market_event(datetime(2024, 1, 1, 1)), {}
        )
        self.assertTrue(strategy.disabled)
        self.assertEqual(strategy.evt.orders, [])


if __name__ == "__main__":
    unittest.main()
