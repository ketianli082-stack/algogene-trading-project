from datetime import datetime
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_algogene_crypto_v1_0 import load_strategy_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
research = importlib.import_module("algogene_research_batch")
pipeline = importlib.import_module("algogene_v1_3_pipeline")


def source_module(source):
    load_strategy_module()
    module = types.ModuleType("research_candidate")
    with patch.dict(sys.modules, {
        "numpy": types.SimpleNamespace(array=lambda values, dtype: values),
        "talib": types.SimpleNamespace(ATR=lambda *args, **kwargs: [10.0]),
    }):
        exec(compile(source, "research_candidate.py", "exec"), module.__dict__)
    return module


class ResearchGuardsTest(unittest.TestCase):
    def test_current_pipeline_does_not_retry_ambiguous_submission(self):
        _, rows = research.plan()
        responses = [io.StringIO(json.dumps({"status": True, "res": []})),
                     io.StringIO(json.dumps({"res": {"contractSize": 1}})),
                     TimeoutError("test-only ambiguous POST")]
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict("os.environ", {"ALGOGENE_USER_ID": "dummy-user", "ALGOGENE_API_KEY": "dummy-credential"}), \
             patch.object(pipeline.urllib.request, "urlopen", side_effect=responses) as network, \
             patch.object(pipeline.time, "sleep"):
            output = Path(directory) / "evidence.json"
            code = pipeline.main(settings_override=rows[0]["settings"], source_override=rows[0]["submitted_source"], output_override=output)
            self.assertEqual(code, 1)
            self.assertEqual(network.call_count, 3)
            result = json.loads(output.read_text())
            self.assertEqual(result["status"], "ERROR")
            self.assertIsNone(result["backtest_id"])
            self.assertNotIn("dummy-credential", output.read_text())

    def test_plan_keeps_holdouts_closed_and_defaults_identical(self):
        _, rows = research.plan()
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertLessEqual(row["settings"]["EndDate"], "2023-12")
            self.assertEqual(row["settings"]["dataset"], 60)
            self.assertFalse(row["settings"]["allowShortSell"])
        baseline = (research.ROOT / "src/algogene_crypto_v1_3.py").read_text()
        self.assertEqual(research.strategy_source(), baseline)
        for year in (2021, 2022, 2023):
            self.assertIn("datetime(%d, 12, 31, 22)" % year, research.strategy_source(year))

    def test_stop_variants_change_only_native_stop_not_sizing(self):
        baseline = research.strategy_source()
        for stop in (1.5, 2.5):
            source = research.strategy_source(stop=stop)
            self.assertEqual(source.replace("stop_loss = price - %s * atr" % stop,
                                            "stop_loss = price - 2.0 * atr"), baseline)
        with self.assertRaises(ValueError):
            research.strategy_source(year=2025)
        with self.assertRaises(ValueError):
            research.strategy_source(stop=3.0)

    def test_24h_filter_blocks_entry_above_ema_when_longer_slope_falls(self):
        base = source_module(research.strategy_source()).TrendState()
        variant = source_module(research.strategy_source(slope=True)).TrendState()
        for state in (base, variant):
            state.ema = 100.0
            state.bars.extend([(98, 96)] * 20)
        variant.ema_history.extend([110.0] * 24)
        bar = {"o": 105, "h": 106, "l": 104, "c": 105}
        a, b = base.add(datetime(2021, 2, 1), bar), variant.add(datetime(2021, 2, 1), bar)
        self.assertTrue(a["entry"])
        self.assertFalse(b["entry"])
        self.assertEqual(a["exit"], b["exit"])

    def test_native_fee_needs_effective_setting_and_transaction_charge(self):
        evidence = {"status": "COLLECTED", "platform_responses": {
            "statistics": [{"setting": {"TradeCost": "1.0"}}],
            "transactions": [{"res": [{"TradeCost": 0.0}]}]}}
        self.assertFalse(research.fee_verified(evidence))
        evidence["platform_responses"]["transactions"][-1]["res"][0]["TradeCost"] = 1.0
        self.assertTrue(research.fee_verified(evidence))
        evidence["platform_responses"]["statistics"][-1]["setting"]["TradeCost"] = "0.0"
        self.assertFalse(research.fee_verified(evidence))

    def test_pending_cloud_task_stops_batch_and_preserves_not_run_rows(self):
        def pending(**kwargs):
            Path(kwargs["output_override"]).write_text(json.dumps({"status": "PENDING", "task_id": "test-only", "platform_responses": {}}))
            return 1
        with tempfile.TemporaryDirectory() as directory, patch.object(research, "OUT", Path(directory)), \
             patch.object(research, "run_cloud", side_effect=pending) as cloud, \
             patch.object(research, "archive") as archive, \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "1"}):
            self.assertEqual(research.main(), 1)
            self.assertEqual(cloud.call_count, 1)
            self.assertEqual(archive.call_count, 1)
            result = json.loads((Path(directory) / "platform-responses.json").read_text())
            self.assertEqual(result["status"], "STOPPED")
            self.assertTrue(all(row["status"] == "NOT RUN" for row in result["runs"][1:]))

    def test_workflow_retry_does_not_submit_again(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(research, "OUT", Path(directory)), \
             patch.object(research, "run_cloud") as cloud, \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "2"}):
            self.assertEqual(research.main(), 1)
            cloud.assert_not_called()


if __name__ == "__main__":
    unittest.main()
