import importlib.util
import sys
import types
import unittest
from pathlib import Path
pkg=types.ModuleType("AlgoAPI")
pkg.AlgoAPIUtil=types.SimpleNamespace(OrderObject=types.SimpleNamespace)
pkg.AlgoAPI_Backtest=types.SimpleNamespace(AlgoEvtHandler=object)
sys.modules["AlgoAPI"]=pkg
p=Path(__file__).resolve().parents[1]/"strategy/btc_v1_3_d_dynamic_ema200.py"
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

class TestRecovery(unittest.TestCase):
    def test_recovery_with_price_below_ema(self):
        gate=botmod.LongTrend()
        for _ in range(200):
            gate.update(100)
        for _ in range(23):
            gate.update(120)
        gate.update(99)
        self.assertLess(gate.last_price,gate.value)
        self.assertEqual(gate.regime(),"RECOVERY")
        self.assertTrue(gate.permits_entry())

    def test_declining_regime_blocked(self):
        gate=botmod.LongTrend()
        for _ in range(200):
            gate.update(100)
        for _ in range(24):
            gate.update(90)
        self.assertEqual(gate.regime(),"BLOCKED")
        self.assertFalse(gate.permits_entry())

if __name__=="__main__":
    unittest.main()
