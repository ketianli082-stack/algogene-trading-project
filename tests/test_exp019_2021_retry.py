"""Isolated preflight guards for the EXP-019R 2021-2025 rerun."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("exp019r",ROOT/"scripts/algogene_exp019_2021_retry.py")
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class EXP019RTests(unittest.TestCase):
    def test_only_2021_2025_same_strategy_hash(self):
        plan=runner.build_plan()
        self.assertEqual(len(plan),1)
        self.assertEqual(plan[0]["name"],"full-2021-2025")
        self.assertEqual(plan[0]["source_sha256"],
                         "6088dbe6abb48892d7e6de8bafdeb01b65a0e3f08178eb27927d5eb3cfed8b0f")
        setting=plan[0]["settings"]
        self.assertEqual(setting["StartDate"],"2021-01")
        self.assertEqual(setting["EndDate"],"2025-12")
        self.assertEqual(setting["dataset"],60)
        self.assertEqual(setting["TradeCost"],1)
        self.assertEqual(setting["InitialCapital"],1000000)
        self.assertEqual(setting["Leverage"],1)

    def test_only_get_retried_and_http_error_code_archived(self):
        src=(ROOT/"scripts/algogene_exp019_2021_retry.py").read_text()
        self.assertIn("for attempt in range(1 if post else 2):",src)
        self.assertIn('"http_status": status_code',src)
        self.assertIn("if post or not retryable or attempt != 0:",src)
        self.assertIn("if os.getenv(\"GITHUB_RUN_ATTEMPT\", \"1\") != \"1\":",src)
        self.assertIn('"EXP018, HALT" not in logs',src)

    def test_archive_destination_matches_runner(self):
        runner_source=(ROOT/"scripts/algogene_exp019_2021_retry.py").read_text()
        archive=(ROOT/"scripts/archive_exp019_2021_retry.py").read_text()
        self.assertIn('OUT = ROOT / "outputs/exp019_2021_retry"',runner_source)
        self.assertIn('outputs/exp019_2021_retry/platform-responses.json',archive)
        self.assertIn('experiments/EXP-019R/runs/',archive)


if __name__=="__main__":
    unittest.main()
