"""EXP020: actual fill percentage fees and paired-H1 risk, offline only."""
import ast
import importlib.util
import math
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"src/four_asset_h1_exp020.py"
algo=types.ModuleType("AlgoAPI")
algo.AlgoAPIUtil=types.SimpleNamespace(OrderObject=lambda **kwargs:types.SimpleNamespace(**kwargs))
algo.AlgoAPI_Backtest=types.SimpleNamespace()
sys.modules.setdefault("AlgoAPI",algo)
spec=importlib.util.spec_from_file_location("exp020_strategy", SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Handler:
    def __init__(self):
        self.calls=[]
        self.logs=[]
    def sendOrder(self,obj):
        self.calls.append(obj)
    def consoleLog(self,*args):
        self.logs.append(args)


class PercentFeeAndShockTests(unittest.TestCase):
    def test_optimistic_fee_is_actual_fill_not_fixed(self):
        self.assertAlmostEqual(m._percent_fee(50000,1,1),25)
        self.assertAlmostEqual(m._percent_fee(2000,25,1),25)
        self.assertAlmostEqual(m._percent_fee(50000,1,2),50)
        self.assertEqual(m.PARAMS["fee_rate"],0.0005)

    def test_actual_four_fills_and_realized_gross(self):
        e=m.AlgoEvent()
        e.evt=Handler()
        e.spec={x:1 for x in m.SYMBOLS}
        t=datetime(2025,5,19,5)
        e.pair_last_hour["BTC"]=t
        e._open("BTC",1,1,-1,t,math.log(50100/50000))
        entries=[("BTCUSD",50100,1),("BTCUSDM",50000,2)]
        for sym,price,tid in entries:
            e.on_orderfeed(types.SimpleNamespace(instrument=sym,status="success",
                openclose="open",tradeID=tid,fill_price=price,fill_volume=1))
        self.assertEqual(e.states["BTC"]["phase"],"OPEN")
        self.assertAlmostEqual(e.fee_total,(50100+50000)*0.0005)
        e._close("BTC","H1_REVERT",t)
        for sym,price,tid in [("BTCUSD",50090,1),("BTCUSDM",49900,2)]:
            e.on_orderfeed(types.SimpleNamespace(instrument=sym,status="success",
                openclose="close",tradeID=tid,fill_price=price,fill_volume=1))
        self.assertEqual(e.states["BTC"]["phase"],"FLAT")
        self.assertAlmostEqual(e.fee_total,200090*0.0005)
        self.assertEqual(e.fee_events,4)
        # long spot: -10 ; short future: +100
        self.assertAlmostEqual(e.realized_gross,90)
        self.assertAlmostEqual(e.realized_gross-e.fee_total,-10.045)
        self.assertEqual(len(e.fill_entries),0)

    def test_missing_fill_price_halts_not_fake_fee(self):
        e=m.AlgoEvent()
        e.evt=Handler()
        e.spec={x:1 for x in m.SYMBOLS}
        t=datetime(2025,6,1,5)
        e._open("BTC",1,1,-1,t,0.005)
        e.on_orderfeed(types.SimpleNamespace(instrument="BTCUSD",
           status="success",openclose="open",tradeID=1))
        self.assertTrue(e.halted)
        self.assertEqual(e.fee_total,0.0)

    def test_basis_shock_and_contiguous_h1(self):
        now=datetime(2025,6,1,4)
        s={now-timedelta(hours=i):{"c":100} for i in range(5)}
        f={t:{"c":100.1} for t in s}
        r=m._recent_basis_risk(s,f,now)
        self.assertLess(r["h4_basis_range"],0.000001)
        f[now]={"c":102}
        r=m._recent_basis_risk(s,f,now)
        self.assertGreater(r["max_h1_basis_jump"],0.006)
        del f[now-timedelta(hours=2)]
        self.assertIsNone(m._recent_basis_risk(s,f,now))

    def test_tz_offset_normalization(self):
        self.assertEqual(m._time("2025-06-01T13:00:00+09:00"),datetime(2025,6,1,4))
        self.assertEqual(m._time("2025-06-01T04:00:00Z"),datetime(2025,6,1,4))

    def test_safe_native_only_hour_history(self):
        tree=ast.parse(SOURCE.read_text())
        banned={"remove","pop","replace","update","endswith"}
        attrs={node.func.attr for node in ast.walk(tree) if isinstance(node,ast.Call) and
               isinstance(node.func,ast.Attribute)}
        self.assertFalse(attrs & banned)
        self.assertNotIn('interval="H4"',SOURCE.read_text())
        self.assertNotIn('interval="D"',SOURCE.read_text())
        self.assertIn('interval="H"',SOURCE.read_text())
        self.assertIn('"COST_FINAL"',SOURCE.read_text())


if __name__=="__main__":
    unittest.main()
