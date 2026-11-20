"""EXP021 diagnosis must never change trading parameters or submit two runs."""
import ast
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "exp021_run", ROOT / "scripts/algogene_exp021_diagnostic_run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)

class DiagnosticGuards(unittest.TestCase):
    def test_same_parameters_and_no_native_fee(self):
        rows = run.build_plan()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["settings"]["StartDate"], "2021-01")
        self.assertEqual(row["settings"]["EndDate"], "2025-12")
        self.assertEqual(row["settings"]["Leverage"], 1)
        self.assertNotIn("TradeCost", row["settings"])
        self.assertEqual(row["params"]["fee_rate"], 0.0005)
        self.assertEqual(row["settings"]["subscribeList"],
                         ["BTCUSD", "BTCUSDM", "ETHUSD", "ETHUSDM"])

    def test_diagnostic_counters_and_retained_fee_model(self):
        source = (ROOT / "src/four_asset_h1_exp021_diagnostic.py").read_text()
        original = (ROOT / "src/four_asset_h1_exp020.py").read_text()
        ast.parse(source)
        self.assertIn("DIAG_FINAL", source)
        self.assertIn("SYNC_H1", source)
        self.assertIn("HISTORY_", source)
        self.assertIn("ZSCORE_SMALL", source)
        self.assertIn("PERCENT_COST_EDGE", source)
        self.assertIn("ENTRY_SENT", source)
        self.assertIn("FILL_", source)
        for phrase in ('estimated_4fill_fee = 2.0 * (ns + nf) * PARAMS["fee_rate"]',
                       'net_expected = min(ns, nf) * current_edge - estimated_4fill_fee',
                       'self._open(pair, q_s, q_f, side, now, basis)',
                       'self._close(pair, "BASIS_STOP", now)'):
            self.assertIn(phrase, original)
            self.assertIn(phrase, source)
        self.assertEqual(source.count("def _open("), 1)

    def test_no_duplicate_submission_workflow(self):
        s = (ROOT / "scripts/algogene_exp021_diagnostic_run.py").read_text()
        self.assertIn('if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":', s)
        self.assertIn('if post or not retryable or attempt != 0:', s)
        self.assertIn('"year_pair_diagnostics" in row', s)

if __name__ == "__main__":
    unittest.main()
