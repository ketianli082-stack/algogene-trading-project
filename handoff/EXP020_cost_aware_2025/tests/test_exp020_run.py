"""EXP020 runner checks before placing a single real ALGOGENE cloud request."""
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=ROOT/"scripts/algogene_exp020_run.py"
spec=importlib.util.spec_from_file_location("exp020runner",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EXP020RunGuards(unittest.TestCase):
    def test_registered_code_and_percentage_fee(self):
        rows=m.build_plan()
        self.assertEqual(len(rows),1)
        r=rows[0]
        self.assertEqual(r["settings"]["StartDate"],"2025-01")
        self.assertEqual(r["settings"]["EndDate"],"2025-12")
        self.assertEqual(r["settings"]["TradeCost"],0)
        self.assertEqual(r["settings"]["InitialCapital"],1000000)
        self.assertEqual(r["settings"]["Leverage"],1)
        self.assertEqual(r["params"]["fee_rate"],0.0005)
        self.assertIn("COST_FINAL",r["source"])
        self.assertIn('self.evt.consoleLog("EXP020", *args)',r["source"])

    def test_safe_native_submission_and_both_fee_accounts(self):
        s=p.read_text()
        self.assertIn('for attempt in range(1 if post else 2):',s)
        self.assertIn('ast.literal_eval(annual)',s)
        self.assertIn('"cost_adjusted_native_net_pnl_usd"',s)
        self.assertIn('native_score_is_before_internal_fee',s)
        self.assertIn('"COST_FINAL" in logs',s)
        self.assertIn('from archive_exp020 import archive',s)


if __name__=="__main__":
    unittest.main()
