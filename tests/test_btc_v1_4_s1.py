import importlib.util
import sys
import types
import unittest
from pathlib import Path
pkg=types.ModuleType("AlgoAPI")
pkg.AlgoAPIUtil=types.SimpleNamespace(OrderObject=types.SimpleNamespace)
pkg.AlgoAPI_Backtest=types.SimpleNamespace(AlgoEvtHandler=object)
sys.modules["AlgoAPI"]=pkg
p=Path(__file__).resolve().parents[1]/"strategy/btc_v1_4_s1_costfilter60.py"
spec=importlib.util.spec_from_file_location("btc_v12b",p)
botmod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(botmod)

class TestATR(unittest.TestCase):
    def test_wilder_atr(self):
        self.assertAlmostEqual(botmod.atr_value([(102,98,100)]*30),4)
        self.assertIsNone(botmod.atr_value([(102,98,100)]*10))
    def test_fixed_anchor(self):
        self.assertEqual(botmod.fixed_stop(100,4),88)
    def test_fill_and_exit(self):
        bot=botmod.AlgoEvent()
        class Fake:
            def __init__(self): self.orders=[]
            def consoleLog(self,*args): pass
            def sendOrder(self,order): self.orders.append(order)
        bot.evt=Fake()
        bot.contract_size=1
        bot.entry_atr=4
        bot.pending=("open",None)
        bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="open",tradeID="1",fill_volume=1,fill_price=100))
        self.assertEqual(bot.stops["1"],88)
        bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T00:00:00","lastPrice":90}}, {})
        self.assertEqual(len(bot.evt.orders),0)
        bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T01:00:00","lastPrice":87}}, {})
        self.assertEqual(len(bot.evt.orders),1)
        self.assertEqual(bot.evt.orders[0].tradeID,"1")
        bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="close",tradeID="1"))
        self.assertFalse(bot.stops)
    def test_missing_fill_halts(self):
        bot=botmod.AlgoEvent()
        bot.evt=types.SimpleNamespace(consoleLog=lambda *args:None)
        bot.entry_atr=4
        bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="open",tradeID="1",fill_volume=1))
        self.assertTrue(bot.halted)

class TestTrend(unittest.TestCase):
    def test_warmup_and_direction(self):
        gate=botmod.LongTrend()
        for _ in range(199):
            gate.update(100)
        self.assertFalse(gate.permits_entry())
        gate.update(100)
        self.assertEqual(gate.value,100)
        self.assertFalse(gate.permits_entry())
        gate.update(110)
        self.assertTrue(gate.permits_entry())
        gate.update(90)
        self.assertFalse(gate.permits_entry())

    def test_gate_uses_previous_quote(self):
        from unittest.mock import patch
        bot=botmod.AlgoEvent()
        for _ in range(200):
            bot.long_trend.update(100)
        bot.long_trend.update(90)
        bot.evt=types.SimpleNamespace(consoleLog=lambda *args:None)
        bot.contract_size=1
        with patch.object(botmod,"cross_signal",return_value=1):
            bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T00:00:00","lastPrice":110}}, {})
        self.assertEqual(bot.adx_queries,0)
        self.assertTrue(bot.long_trend.permits_entry())

class TestRiskSizing(unittest.TestCase):
    def test_allocation_cap(self):
        self.assertAlmostEqual(botmod.risk_sized_volume(10000,10000,60000,1,100),0.0833)
    def test_risk_cap(self):
        q=botmod.risk_sized_volume(10000,10000,60000,1,1000)
        self.assertAlmostEqual(q,0.0166)
        self.assertLessEqual(q*3000,10000*botmod.RISK_FRACTION+1e-9)
    def test_contract_size_and_cash(self):
        q=botmod.risk_sized_volume(10000,1000,10000,2,100)
        self.assertAlmostEqual(q,0.0475)
        self.assertLessEqual(q*2*10000,950)
    def test_invalid_atr(self):
        self.assertEqual(botmod.risk_sized_volume(10000,10000,60000,1,None),0)
    def test_higher_volatility_reduces_size(self):
        self.assertGreater(botmod.risk_sized_volume(10000,10000,60000,1,600),
                           botmod.risk_sized_volume(10000,10000,60000,1,1200))

class TestCostGate(unittest.TestCase):
    def test_reference(self):
        slip,cost,ratio=botmod.cost_estimate(60000,600)
        self.assertAlmostEqual(slip,0.0003)
        self.assertAlmostEqual(cost,96)
        self.assertAlmostEqual(ratio,0.16)
    def test_low_volatility_blocked(self):
        self.assertGreater(botmod.cost_estimate(60000,300)[2],botmod.COST_ATR_LIMIT)
    def test_high_volatility_passes(self):
        self.assertLess(botmod.cost_estimate(60000,1200)[2],botmod.COST_ATR_LIMIT)
    def test_invalid(self):
        self.assertIsNone(botmod.cost_estimate(60000,None))
        self.assertIsNone(botmod.cost_estimate(0,600))
    def test_gate_in_callback(self):
        from unittest.mock import patch
        for atr, expected in ((300,0),(600,1)):
            bot=botmod.AlgoEvent()
            for _ in range(200): bot.long_trend.update(59000)
            bot.long_trend.update(60000)
            orders=[]
            bot.evt=types.SimpleNamespace(consoleLog=lambda *args:None,
                getHistoricalBar=lambda *args:{}, sendOrder=orders.append)
            bot.contract_size=1
            with patch.object(botmod,"cross_signal",return_value=1), patch.object(botmod,"adx_series",return_value=[30]), patch.object(botmod,"atr_value",return_value=atr):
                bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T00:00:00","lastPrice":60000}},{"NAV":10000,"availableBalance":10000})
            self.assertEqual(len(orders),expected)

if __name__=="__main__":
    unittest.main()
