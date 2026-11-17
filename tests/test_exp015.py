"""EXP015 H1-only Score_Total research guards; all tests offline."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
batch = importlib.import_module("algogene_combination_batch_exp015")
previous = importlib.import_module("algogene_combination_batch_exp014")


class EXP015ScoreTests(unittest.TestCase):
    def setUp(self):
        self.config, self.rows = batch.plan()

    def test_score_reference_is_source_identical_to_exp014_eight_percent(self):
        _, old = previous.plan()
        self.assertEqual(
            self.rows[0]["submitted_source"].replace(
                "EXP015: H1-only Score_Total research, with native fee/risk evidence.",
                "EXP014: hourly BTCUSD cost-aware breakout quality experiments. Backtest only."),
            old[1]["submitted_source"])
        self.assertEqual(self.rows[0]["params"]["max_cost_ratio"], 0.08)

    def test_five_registered_one_factor_h1_development_models(self):
        self.assertEqual([x["name"] for x in self.rows],
                         ["score-reference-08", "gate-relax-09", "gate-tighten-07",
                          "gate08-trend-slope-005", "gate08-breakout-005"])
        self.assertEqual(len({x["source_sha256"] for x in self.rows}), 5)
        ref = self.rows[0]["params"]
        for index, item in enumerate(self.rows):
            s = item["settings"]
            self.assertEqual((s["StartDate"], s["EndDate"], s["dataset"], s["TradeCost"]),
                             ("2021-01", "2023-12", 60, 1))
            self.assertEqual(s["InitialCapital"], 10000)
            self.assertEqual(s["Leverage"], 1)
            self.assertFalse(s["allowShortSell"])
            self.assertIn('interval="H"', item["submitted_source"])
            self.assertNotIn('"H4"', item["submitted_source"])
            differences = [k for k in ref if item["params"][k] != ref[k]]
            self.assertEqual(differences, [] if index == 0 else [
                "max_cost_ratio", "max_cost_ratio", "min_slope_atr", "min_breakout_atr"][index - 1])

    def test_score_ranking_excludes_empty_trade_and_excessive_loss(self):
        def row(name, score, count, dd, pnl):
            return {"name": name, "status": "COLLECTED", "evidence": {"backtest_id": "unit-test"},
                    "native_comparison": {"Score_Total": score, "TradeCnt": count,
                                          "maxDrawdown_pct": dd, "TotalPnL": pnl}}
        ranking = batch.score_leaderboard([
            row("zero-trade-high-score", 50, 0, 0, 0),
            row("large-loss-high-score", 52, 100, 0.02, -200),
            row("valid-score", 41.4, 100, 0.016, -68),
            row("bad-dd", 50, 100, 0.09, 20)])
        self.assertEqual(ranking["top_eligible_candidate"], "valid-score")
        self.assertEqual(ranking["native_score_ranking"][0]["name"], "large-loss-high-score")
        self.assertTrue(all(not r["eligible"] for r in ranking["native_score_ranking"][:3]))

    def test_holdout_and_unregistered_candidate_blocked_before_network(self):
        config = json.loads(json.dumps(self.config))
        config["settings"]["EndDate"] = "2025-12"
        original = Path.read_text
        def changed(path, *args, **kwargs):
            return json.dumps(config) if path.name == "exp015_h1_score.json" else original(path,*args,**kwargs)
        with patch.object(Path, "read_text", changed), self.assertRaises(ValueError):
            batch.plan()
        config["settings"]["EndDate"] = "2023-12"
        config["candidates"][0]["params"]["max_cost_ratio"] = 0.01
        with patch.object(Path, "read_text", changed), self.assertRaises(ValueError):
            batch.plan()

    def test_retry_is_never_a_new_cloud_submission(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(batch, "OUT", Path(tmp)), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "2"}), patch.object(batch, "run_cloud") as network:
            self.assertEqual(batch.main(), 1)
            network.assert_not_called()

    def test_pending_task_halts_remaining_five_candidate_batch(self):
        def pending(**kwargs):
            Path(kwargs["output_override"]).write_text(json.dumps({
                "status":"PENDING", "platform_responses": {}, "errors":[]}))
            return 1
        with tempfile.TemporaryDirectory() as tmp, patch.object(batch,"OUT",Path(tmp)), \
             patch.dict("os.environ",{"GITHUB_RUN_ATTEMPT":"1"}), \
             patch.object(batch,"archive"), patch.object(batch,"run_cloud",side_effect=pending) as network:
            self.assertEqual(batch.main(), 1)
            network.assert_called_once()
            payload=json.loads((Path(tmp)/"platform-responses.json").read_text())
            self.assertTrue(all(x["status"] == "NOT RUN" for x in payload["runs"][1:]))

if __name__ == "__main__":
    unittest.main()
