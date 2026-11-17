"""EXP013 offline regression and experiment-isolation tests."""
import importlib
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_v1_4_research import source_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
batch = importlib.import_module("algogene_combination_batch_exp013")


class EXP013Tests(unittest.TestCase):
    def setUp(self):
        self.config, self.rows = batch.plan()

    def test_registered_dev_windows_and_isolated_perturbations(self):
        self.assertEqual([r["name"] for r in self.rows],
                         ["h1-control", "h1-cost-gate", "h4-control"])
        self.assertEqual(len({r["source_sha256"] for r in self.rows}), 3)
        p, q, r = [item["params"] for item in self.rows]
        self.assertEqual({k:v for k,v in p.items() if k!="cost_gate"},
                         {k:v for k,v in q.items() if k!="cost_gate"})
        self.assertEqual({k:v for k,v in p.items() if k!="interval"},
                         {k:v for k,v in r.items() if k!="interval"})
        for row in self.rows:
            setting = row["settings"]
            self.assertEqual((setting["StartDate"], setting["EndDate"],
                              setting["dataset"], setting["TradeCost"]),
                             ("2021-01", "2023-12", 60, 1))
            self.assertEqual(setting["InitialCapital"],10000)

    def test_gate_blocks_low_reward_space_without_changing_signal(self):
        for idx, quantity in ((0,1),(1,0)):
            module = source_module(self.rows[idx]["submitted_source"])
            module.ATR = lambda *args, **kwargs: [100.0]
            strategy = module.AlgoEvent()
            strategy.start({"subscribeList":["BTCUSD"]})
            now = datetime(2021,2,1,0)
            type(strategy.evt).history_response = {
                str(now-timedelta(hours=i)):
                {"o":1000,"h":1001,"l":999,"c":1000} for i in range(1,261)}
            strategy.trend.add=lambda t,b: {"entry":True,"exit":False,"time":t,"close":1000}
            strategy.on_marketdatafeed(
                types.SimpleNamespace(instrument="BTCUSD",timestamp=now,askPrice=1000),
                {"availableBalance":10000})
            self.assertEqual(len(strategy.evt.orders),quantity)
            if not quantity:
                self.assertTrue(any(line[0]=="V1.3_SKIP_COST" for line in strategy.evt.logs))

    def test_h4_signals_only_use_prior_complete_candles(self):
        module = source_module(self.rows[2]["submitted_source"])
        strategy=module.AlgoEvent()
        strategy.start({"subscribeList":["BTCUSD"]})
        now=datetime(2021,2,1,4)
        strategy.on_marketdatafeed(
            types.SimpleNamespace(instrument="BTCUSD",timestamp=now-timedelta(hours=1)), {})
        self.assertEqual(strategy.evt.history_calls, [])
        type(strategy.evt).history_response = {
            str(now-timedelta(hours=4*i)):
            {"o":100,"h":101,"l":99,"c":100} for i in range(1,261)}
        strategy.on_marketdatafeed(types.SimpleNamespace(instrument="BTCUSD", timestamp=now), {})
        self.assertFalse(strategy.halted)
        self.assertEqual(strategy.evt.history_calls[0]["interval"],"H4")
        self.assertEqual(strategy.trend.last_time,now-timedelta(hours=4))

    def test_failed_close_halts_without_duplicate_exit(self):
        module=source_module(self.rows[0]["submitted_source"])
        strategy=module.AlgoEvent()
        strategy.start({"subscribeList":["BTCUSD"]})
        strategy.trade_id="test-open-position"
        strategy.pending=True
        strategy.pending_action="close"
        strategy.on_orderfeed(types.SimpleNamespace(status="rejected",openclose="close"))
        self.assertTrue(strategy.halted)
        self.assertFalse(strategy.pending)
        strategy.send_exit()
        self.assertEqual(strategy.evt.orders, [])

    def test_retry_never_submits_and_pending_halts_batch(self):
        with tempfile.TemporaryDirectory() as d, patch.object(batch,"OUT",Path(d)), \
             patch.dict("os.environ",{"GITHUB_RUN_ATTEMPT":"2"}), \
             patch.object(batch,"run_cloud") as cloud:
            self.assertEqual(batch.main(),1)
            cloud.assert_not_called()
        def pending(**kw):
            Path(kw["output_override"]).write_text(
                json.dumps({"status":"PENDING","platform_responses":{},"errors":[]}))
            return 1
        with tempfile.TemporaryDirectory() as d, patch.object(batch,"OUT",Path(d)), \
             patch.dict("os.environ",{"GITHUB_RUN_ATTEMPT":"1"}), \
             patch.object(batch,"archive"), \
             patch.object(batch,"run_cloud",side_effect=pending) as cloud:
            self.assertEqual(batch.main(),1)
            cloud.assert_called_once()
            report=json.loads((Path(d)/"platform-responses.json").read_text())
            self.assertTrue(all(x["status"]=="NOT RUN" for x in report["runs"][1:]))

    def test_holdout_date_change_rejected(self):
        config=dict(self.config)
        config["settings"]=dict(config["settings"],EndDate="2025-12")
        prior=Path.read_text
        def patch_read(path,*args,**kwargs):
            return json.dumps(config) if path.name=="exp013_cost_h4.json" else prior(path,*args,**kwargs)
        with patch.object(Path,"read_text",patch_read), self.assertRaises(ValueError):
            batch.plan()
