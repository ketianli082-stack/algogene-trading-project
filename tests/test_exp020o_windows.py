"""EXP020O two windows: exact EXP020 strategy SHA and absent native TradeCost."""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "exp020o_windows_run",ROOT/"scripts/algogene_exp020o_windows_run.py")
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class IndependentWindows(unittest.TestCase):
    def test_exact_frozen_code_date_scopes_and_omitted_fee(self):
        rows=runner.build_plan()
        self.assertEqual(len(rows),2)
        self.assertEqual([(r["settings"]["StartDate"],r["settings"]["EndDate"])
                for r in rows],
                [("2023-01","2025-12"),("2021-01","2025-12")])
        for row in rows:
            self.assertNotIn("TradeCost",row["settings"])
            self.assertNotIn("TradeCost",json.loads(
                json.dumps({"settings":row["settings"]}))["settings"])
            self.assertEqual(row["source_sha256"],
                "4c2ff67079b9a2feb3d96df7d6ca05c5c30e67fb4ea914deed5b55036a330b6a")
            self.assertEqual(row["params"]["fee_rate"],0.0005)
            self.assertEqual(row["settings"]["allowShortSell"],True)
            self.assertEqual(row["settings"]["Leverage"],1)
            self.assertEqual(row["settings"]["dataset"],60)

    def test_fee_mismatch_does_not_abort_other_completed_window(self):
        s=(ROOT/"scripts/algogene_exp020o_windows_run.py").read_text()
        self.assertIn('checks["TradeCost"] = math.isclose(float(actual_trade_cost), 0.0',s)
        self.assertIn('INVALID_NATIVE_FEE_OR_VALIDATION',s)
        self.assertIn('all(r["status"] == "COLLECTED" for r in plan)',s)
        self.assertIn('if post or not retryable or attempt != 0:',s)
        self.assertIn('assert "TradeCost" not in row["settings"]',s)
        self.assertNotIn("native_fee_override",s)
        self.assertNotIn("native_paid",s)
        self.assertIn('from archive_exp020o_windows import archive',s)

    def test_archive_separate(self):
        s=(ROOT/"scripts/archive_exp020o_windows.py").read_text()
        self.assertIn("experiments/EXP-020O-WINDOWS/runs/",s)
        self.assertIn("outputs/exp020o_windows/platform-responses.json",s)

if __name__=="__main__":
    unittest.main()
