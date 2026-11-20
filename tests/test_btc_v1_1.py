"""V1.1 offline signal tests. No platform credentials or API required."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

pkg=types.ModuleType("AlgoAPI")
pkg.AlgoAPIUtil=types.SimpleNamespace(OrderObject=object)
pkg.AlgoAPI_Backtest=types.SimpleNamespace(AlgoEvtHandler=object)
sys.modules["AlgoAPI"]=pkg
path=Path(__file__).resolve().parents[1]/"strategy"/"btc_v1_1_ema_adx60.py"
spec=importlib.util.spec_from_file_location("btc_v11",path)
btc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(btc)


class V11Tests(unittest.TestCase):
    def test_adx_constant_no_trend(self):
        values=[(101.,99.,100.)]*80
        self.assertEqual(btc.adx_series(values)[-1],0)

    def test_adx_strong_trend(self):
        bars=[(i+1., i-1., float(i)) for i in range(100,180)]
        self.assertGreater(btc.adx_series(bars)[-1],90)

    def test_missing_history(self):
        self.assertEqual(btc.adx_series([(2.,1.,1.5)]*27),[])

    def test_history_filters_current_and_invalid_candles(self):
        now=btc.timestamp("2021-02-01T12:00:00")
        history={
            "2021-02-01 10:00:00":{"h":110,"l":90,"c":100},
            "2021-02-01 11:00:00":{"h":120,"l":99,"c":115},
            "2021-02-01 12:00:00":{"h":130,"l":98,"c":120},
            "2021-02-01 09:00:00":{"h":91,"l":100,"c":95},
        }
        completed=btc.history_ohlc(history,now)
        self.assertEqual(len(completed),2)
        self.assertEqual(completed[-1][1],(120,99,115))
        self.assertTrue(all(t<now for t,_ in completed))

    def test_quote_only_still_updates_ema(self):
        class FakeEvt:
            def __init__(self): self.calls=[];self.logs=[]
            def getHistoricalBar(self,*args):
                self.calls.append(args)
                return {}
            def consoleLog(self,*args): self.logs.append(args)
        bot=btc.AlgoEvent()
        bot.evt=FakeEvt()
        bot.contract_size=1
        bot.prices.extend([100.]*80)
        bot.on_bulkdatafeed(True,{"BTCUSD":{
            "timestamp":"2021-02-01T12:00:00","lastPrice":101
        }},{"NAV":10000,"availableBalance":10000})
        self.assertEqual(len(bot.prices),81)
        self.assertEqual(bot.adx_queries,0)

    def test_threshold_applied_on_buy_only(self):
        prices=[100.]*80+[101.,102.,103.,104.]
        bars=[(100.2,99.8,100.)]*len(prices)
        self.assertIn(1,[btc.cross_signal(prices[:i]) for i in range(52,len(prices)+1)])
        self.assertTrue(all(btc.v11_signal(prices[:i],bars[:i],20)!=1
                            for i in range(52,len(prices)+1)))
        falling=[150.]*80+[149.,148.,147.,146.]
        sell=[btc.v11_signal(falling[:i],bars[:i],99)
              for i in range(52,len(falling)+1)]
        self.assertIn(-1,sell)


if __name__=="__main__":
    unittest.main()
