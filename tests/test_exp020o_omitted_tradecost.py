"""EXP020O: native TradeCost must be absent from POST, and effective zero is mandatory."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "exp020o_runner",ROOT/"scripts/algogene_exp020o_run.py")
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class OmitCostTests(unittest.TestCase):
    def test_actual_submitted_nested_settings_have_no_tradecost_key(self):
        plan=runner.build_plan()
        self.assertEqual(len(plan),1)
        x=plan[0]
        self.assertNotIn("TradeCost",x["settings"])
        self.assertEqual(x["settings"]["StartDate"],"2025-01")
        self.assertEqual(x["settings"]["EndDate"],"2025-12")
        self.assertEqual(x["settings"]["InitialCapital"],1000000)
        self.assertEqual(x["settings"]["Leverage"],1)
        self.assertEqual(x["settings"]["dataset"],60)
        self.assertEqual(x["params"]["fee_rate"],0.0005)
        self.assertEqual(x["source_sha256"],
                         "4c2ff67079b9a2feb3d96df7d6ca05c5c30e67fb4ea914deed5b55036a330b6a")
        outgoing=json.loads(json.dumps({"code":x["source"],"settings":x["settings"]}))
        self.assertNotIn("TradeCost",outgoing["settings"])
        self.assertNotIn('"TradeCost"',json.dumps(outgoing["settings"]))
    def test_runner_strict_zero_acceptance_no_fake_default(self):
        text=(ROOT/"scripts/algogene_exp020o_run.py").read_text()
        self.assertIn('if "TradeCost" in settings:',text)
        self.assertIn('assert "TradeCost" not in row["settings"]',text)
        self.assertIn('checks["TradeCost"] = math.isclose(float(actual_trade_cost), 0.0',text)
        self.assertIn('row["status"] = ("COLLECTED" if all(checks.values())',text)
        self.assertIn('if post or not retryable or attempt != 0:',text)
        self.assertNotIn("native_fee_override",text)
        self.assertNotIn("native_paid",text)
    def test_archive_is_independent(self):
        s=(ROOT/"scripts/archive_exp020o.py").read_text()
        self.assertIn("experiments/EXP-020O/runs/",s)
        self.assertIn("outputs/exp020o/platform-responses.json",s)

if __name__=="__main__":
    unittest.main()
