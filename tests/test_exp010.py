import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
runner = importlib.import_module("algogene_ema_fee")


class ControlledCostTest(unittest.TestCase):
    def test_pinned_source_and_only_fee_settings_change(self):
        config, source = runner.load_plan()
        self.assertIn("self.ema > self.ema_history[0]", source)
        self.assertIn("stop_loss = price - 2.0 * atr", source)
        base = json.loads((runner.ROOT / "configs/v1_3_cloud.json").read_text())
        settings = dict(config["settings"])
        self.assertEqual(settings.pop("TradeCost"), 1.0)
        settings.pop("strategyName")
        base.pop("strategyName")
        self.assertEqual(settings, base)

    def test_holdout_change_is_rejected(self):
        config, _ = runner.load_plan()
        config["settings"]["EndDate"] = "2025-12"
        original = Path.read_text

        def changed(path, *args, **kwargs):
            return json.dumps(config) if path.name == "exp010_ema_fee.json" else original(path, *args, **kwargs)

        with patch.object(Path, "read_text", changed), self.assertRaises(ValueError):
            runner.load_plan()

    def test_retry_cannot_submit(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(runner, "OUTPUT", Path(directory) / "result.json"), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "2"}), \
             patch.object(runner, "run_cloud") as cloud:
            self.assertEqual(runner.main(), 1)
            cloud.assert_not_called()

    def run_mock_collection(self, effective_fee):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(runner, "OUTPUT", Path(directory) / "result.json"), \
             patch.dict("os.environ", {"GITHUB_RUN_ATTEMPT": "1"}), \
             patch.object(runner, "archive") as archive:
            def cloud(**kwargs):
                path = Path(kwargs["output_override"])
                value = {"status": "SUBMITTED", "task_id": "mock-only", "errors": [], "platform_responses": {}}
                path.write_text(json.dumps(value))
                kwargs["on_submission"](path)
                value.update(status="COLLECTED", platform_responses={
                    "statistics": [{"setting": {"TradeCost": effective_fee}}],
                    "transactions": [{"res": [{"TradeCost": -1 if effective_fee == 1 else 0}]}]})
                path.write_text(json.dumps(value))
                return 0

            with patch.object(runner, "run_cloud", side_effect=cloud):
                code = runner.main()
            archive.assert_called_once_with(runner.OUTPUT, "submitted", experiment="EXP-010")
            return code, json.loads(runner.OUTPUT.read_text())

    def test_native_negative_charge_is_preserved_and_verified(self):
        code, result = self.run_mock_collection(1)
        self.assertEqual(code, 0)
        self.assertTrue(result["native_fee_verified"])
        self.assertEqual(result["platform_responses"]["transactions"][-1]["res"][0]["TradeCost"], -1)
        self.assertEqual(result["source_sha256"], runner.PINNED_SOURCE_SHA256)

    def test_ignored_native_fee_cannot_be_called_valid_cost_result(self):
        code, result = self.run_mock_collection(0)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "COLLECTED_WITH_ERRORS")
        self.assertFalse(result["native_fee_verified"])


if __name__ == "__main__":
    unittest.main()
