"""Guard the forensic audit against source drift and incomplete fills."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts/audit_exp016_native.py"
spec = importlib.util.spec_from_file_location("audit_exp016_native", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EXP016AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = json.loads(mod.SOURCE.read_text())

    def test_full_136_fill_reconciliation(self):
        res = mod.audit(self.evidence)
        self.assertEqual(res["native_trade_count"], 136)
        self.assertEqual(res["fully_reconciled_log_fills"], 136)
        self.assertEqual(res["native_open_trade_count"], 68)
        self.assertAlmostEqual(res["gross_pnl_before_native_trade_charges_usd"],
                               -50090.285802, places=4)
        self.assertAlmostEqual(res["native_fixed_charge_inferred_usd"], 68, places=5)
        self.assertAlmostEqual(res["counterfactual_proportional_charges_usd"],
                               10729.765113, places=4)
        self.assertAlmostEqual(res["counterfactual_net_pnl_if_fills_unchanged_usd"],
                               -60820.050915, places=4)
        self.assertIsNone(res["counterfactual_native_score_at_rate"])
        self.assertEqual(res["native_score_total_not_at_requested_fee"],
                         44.159611865031195)

    def test_missing_history_cannot_fake_a_full_cost_audit(self):
        import copy
        bad = copy.deepcopy(self.evidence)
        bad["runs"][0]["platform"]["logs"][-1]["res"] = (
            "[2023-01-01 00:00:00] Backtest started!"
        )
        with self.assertRaisesRegex(ValueError, "Incomplete platform log"):
            mod.audit(bad)

    def test_other_settings_mismatch_is_rejected(self):
        import copy
        bad = copy.deepcopy(self.evidence)
        bad["runs"][0]["setting_checks"]["StartDate"] = False
        with self.assertRaisesRegex(ValueError, "second effective configuration"):
            mod.audit(bad)


if __name__ == "__main__":
    unittest.main()
