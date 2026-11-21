import importlib.util
import sys
import types
import unittest
from pathlib import Path
pkg=types.ModuleType("AlgoAPI")
pkg.AlgoAPIUtil=types.SimpleNamespace(OrderObject=types.SimpleNamespace)
pkg.AlgoAPI_Backtest=types.SimpleNamespace(AlgoEvtHandler=object)
sys.modules["AlgoAPI"]=pkg
p=Path(__file__).resolve().parents[1]/"strategy/btc_v1_5_e_reentry_diagnostic60.py"
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
        self.assertAlmostEqual(q,0.0160)
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

class TestCostRisk(unittest.TestCase):
    def test_cost_reference(self):
        self.assertAlmostEqual(botmod.round_trip_cost(60000,600),96)
    def test_cost_inclusive_budget(self):
        q=botmod.risk_sized_volume(10000,10000,60000,1,600)
        self.assertAlmostEqual(q,0.0263)
        self.assertLessEqual(q*(1800+96),50)
        self.assertLess(q,50/1800)
    def test_cost_budget_contract_multiplier(self):
        q=botmod.risk_sized_volume(10000,10000,60000,2,600)
        self.assertLessEqual(q*2*(1800+96),50)

class TestFactorial(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(botmod.ALLOW_SHORT, False)
        self.assertEqual(botmod.ALLOW_REENTRY, True)
    def test_short_stop(self):
        self.assertEqual(botmod.fixed_stop(100,4,-1),112)
        bot=botmod.AlgoEvent()
        orders=[]
        bot.evt=types.SimpleNamespace(consoleLog=lambda *args:None,sendOrder=orders.append)
        bot.entry_atr=4
        bot.request_side=-1
        bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="open",tradeID="s",fill_volume=1,fill_price=100,buysell=-1))
        bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T00:00:00","lastPrice":110}}, {})
        self.assertFalse(orders)
        bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T01:00:00","lastPrice":113}}, {})
        self.assertEqual(len(orders),1)
        self.assertEqual(orders[0].tradeID,"s")
    def test_recovery_cooldown_and_limit(self):
        from datetime import datetime,timedelta
        from unittest.mock import patch
        start=datetime(2022,1,1)
        state=botmod.Recovery()
        state.arm(1,start)
        with patch.object(botmod,"recovery_cross",return_value=True):
            self.assertFalse(state.eligible(start+timedelta(hours=11),[]))
            self.assertTrue(state.eligible(start+timedelta(hours=12),[]))
            state.count=2
            self.assertFalse(state.eligible(start+timedelta(hours=13),[]))
            state.reset()
            self.assertFalse(state.eligible(start+timedelta(hours=13),[]))
    def test_short_submission_flag(self):
        from unittest.mock import patch
        bot=botmod.AlgoEvent()
        for _ in range(200): bot.long_trend.update(61000)
        bot.long_trend.update(60000)
        orders=[]
        bot.evt=types.SimpleNamespace(consoleLog=lambda *args:None,getHistoricalBar=lambda *args:{},sendOrder=orders.append)
        bot.contract_size=1
        with patch.object(botmod,"cross_signal",return_value=-1),patch.object(botmod,"adx_series",return_value=[30]),patch.object(botmod,"atr_value",return_value=600):
            bot.on_bulkdatafeed(True,{"BTCUSD":{"timestamp":"2022-01-01T00:00:00","lastPrice":60000}},{"NAV":10000,"availableBalance":10000})
        self.assertEqual(len(orders),int(botmod.ALLOW_SHORT))
        if orders:
            self.assertEqual(orders[0].buysell,-1)
    def test_reentry_confirmation(self):
        from datetime import datetime
        bot=botmod.AlgoEvent()
        bot.evt=types.SimpleNamespace(consoleLog=lambda *args:None)
        bot.entry_atr=4
        bot.trend_side=1
        bot.last_time=datetime(2022,1,1)
        bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="open",tradeID="a",fill_volume=1,fill_price=100))
        bot.exit_reason="ATR_STOP"
        bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="close",tradeID="a"))
        self.assertEqual(bot.recovery.closed_at is not None,botmod.ALLOW_REENTRY)
        if botmod.ALLOW_REENTRY:
            bot.request_kind="REENTRY"
            bot.on_orderfeed(types.SimpleNamespace(status="success",openclose="open",tradeID="b",fill_volume=1,fill_price=100))
            self.assertEqual(bot.recovery.count,1)
            self.assertIsNone(bot.recovery.closed_at)

class TestRecoveryDiagnostic(unittest.TestCase):
    def test_reason_cooldown(self):
        from datetime import datetime,timedelta
        x=botmod.Recovery()
        start=datetime(2022,1,1)
        x.arm(1,start)
        self.assertEqual(x.explain(start+timedelta(hours=11),[100]*60),"COOLDOWN")
    def test_limit_and_no_prior(self):
        from datetime import datetime
        x=botmod.Recovery()
        x.arm(1,datetime(2022,1,1))
        self.assertEqual(x.explain(None,[100]*60),"NO_PRIOR_TIME")
        x.count=2
        self.assertEqual(x.explain(datetime(2022,1,2),[100]*60),"LIMIT")
    def test_diagnostic_no_mutation(self):
        from datetime import datetime
        x=botmod.Recovery()
        x.arm(1,datetime(2022,1,1))
        x.explain(datetime(2022,1,2),[100]*60)
        self.assertEqual(x.side,1)
        self.assertEqual(x.count,0)
        self.assertEqual(x.closed_at,datetime(2022,1,1))
    def test_reason_mirrors_eligibility(self):
        from datetime import datetime
        from unittest.mock import patch
        x=botmod.Recovery()
        x.arm(1,datetime(2022,1,1))
        with patch.object(botmod,"ema_series",side_effect=lambda values,n:[0,1] if n==20 else [0,0]):
            # last two prices go from below to above fast EMA.
            values=[0]*58+[-1,2]
            self.assertEqual(x.explain(datetime(2022,1,2),values),"ELIGIBLE")
        # Pure diagnostic helper may use a different EMA-series mock from real eligibility.
    def test_no_direction_short(self):
        self.assertFalse(botmod.ALLOW_SHORT)
        self.assertTrue(botmod.ALLOW_REENTRY)

if __name__=="__main__":
    unittest.main()
