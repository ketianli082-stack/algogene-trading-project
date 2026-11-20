"""EXP020Z: API string-zero encoding test. No reimbursing any native fee."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("exp020z",ROOT/"scripts/algogene_exp020z_run.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class StrictNativeZero(unittest.TestCase):
    def test_post_payload_exact_zero_string_and_unchanged_strategy(self):
        rows=m.build_plan()
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row["settings"]["TradeCost"],"0.0")
        self.assertEqual(row["settings"]["StartDate"],"2025-01")
        self.assertEqual(row["settings"]["EndDate"],"2025-12")
        self.assertEqual(row["params"]["fee_rate"],0.0005)
        self.assertEqual(row["settings"]["InitialCapital"],1000000)
        self.assertEqual(row["settings"]["Leverage"],1)
        self.assertEqual(row["source_sha256"],
                         "4c2ff67079b9a2feb3d96df7d6ca05c5c30e67fb4ea914deed5b55036a330b6a")
    def test_runner_strict_native_result_and_no_reimbursement(self):
        s=(ROOT/"scripts/algogene_exp020z_run.py").read_text()
        self.assertIn('checks[key] = math.isclose(float(actual), float(value)',s)
        self.assertIn('row["status"] = ("COLLECTED" if all(checks.values())',s)
        self.assertIn('"percent_fee_audit" in row',s)
        self.assertIn('if post or not retryable or attempt != 0:',s)
        self.assertNotIn("native_paid",s)
        self.assertNotIn("native_fee_override",s)
        self.assertNotIn("COLLECTED_WITH_NATIVE_FEE_FLOOR",s)
    def test_archive_destination(self):
        s=(ROOT/"scripts/archive_exp020z.py").read_text()
        self.assertIn("experiments/EXP-020Z/runs/",s)
        self.assertIn("outputs/exp020z/platform-responses.json",s)

if __name__=="__main__":
    unittest.main()
