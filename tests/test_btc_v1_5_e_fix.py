import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tools" / "btc_v1_5_e_fix_cloud_run.py"
spec = importlib.util.spec_from_file_location("btc_v1_5_e_fix_cloud_run", RUNNER_PATH)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class TestEFixPlan(unittest.TestCase):
    def test_registered_order_and_names(self):
        self.assertEqual(list(runner.VARIANTS), [6, 4, 2])
        self.assertEqual(runner.selected_variant({"E_FIX_COOLDOWN_HOURS": "6"})[:2], (6, "V1.5-E-Fix-6h"))
        self.assertEqual(runner.selected_variant({"E_FIX_COOLDOWN_HOURS": "4"})[:2], (4, "V1.5-E-Fix-4h"))
        self.assertEqual(runner.selected_variant({"E_FIX_COOLDOWN_HOURS": "2"})[:2], (2, "V1.5-E-Fix-2h"))

    def test_unregistered_cooldown_rejected(self):
        for value in ("", "12", "3", "six"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner.selected_variant({"E_FIX_COOLDOWN_HOURS": value})

    def test_only_cooldown_changes_in_submitted_source(self):
        original = runner.SOURCE_PATH.read_text()
        for hours in (6, 4, 2):
            with self.subTest(hours=hours):
                case = runner.build_case(hours)
                expected = original.replace("COOLDOWN_HOURS = 12", f"COOLDOWN_HOURS = {hours}", 1)
                self.assertEqual(case["source"], expected)
                self.assertNotIn("TradeCost", case["settings"])

    def test_fixed_native_settings(self):
        for hours in (6, 4, 2):
            settings = runner.build_case(hours)["settings"]
            self.assertEqual(settings["subscribeList"], ["BTCUSD"])
            self.assertEqual(settings["dataset"], 60)
            self.assertEqual((settings["StartDate"], settings["EndDate"]), ("2021-01", "2024-12"))
            self.assertEqual(settings["InitialCapital"], 10000)
            self.assertEqual(settings["Leverage"], 1)
            self.assertFalse(settings["allowShortSell"])


class TestWorkflowChain(unittest.TestCase):
    def test_strict_serial_chain_and_shared_lock(self):
        workflow_dir = ROOT / ".github" / "workflows"
        six = (workflow_dir / "btc-v1-5-e-fix-6h-cloud.yml").read_text()
        four = (workflow_dir / "btc-v1-5-e-fix-4h-cloud.yml").read_text()
        two = (workflow_dir / "btc-v1-5-e-fix-2h-cloud.yml").read_text()
        self.assertIn("group: btc-algogene-cloud-exclusive", six)
        self.assertIn("group: btc-algogene-cloud-exclusive", four)
        self.assertIn("group: btc-algogene-cloud-exclusive", two)
        self.assertIn("workflows: ['BTC V1.5 E-Fix-6h - Reentry Cooldown']", four)
        self.assertIn("workflows: ['BTC V1.5 E-Fix-4h - Reentry Cooldown']", two)
        self.assertIn("PREDECESSOR_CONCLUSION: ${{ github.event.workflow_run.conclusion }}", four)
        self.assertIn("PREDECESSOR_CONCLUSION: ${{ github.event.workflow_run.conclusion }}", two)
        self.assertIn("needs: predecessor-success", four)
        self.assertIn("needs: predecessor-success", two)
        self.assertNotIn("workflow_dispatch", four)
        self.assertNotIn("workflow_dispatch", two)


if __name__ == "__main__":
    unittest.main()
