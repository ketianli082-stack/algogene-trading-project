"""EXP019 preflight: identical submitted EXP018 code, distinct native windows.

No ALGOGENE credentials or API calls. Unit-test guards prevent accidental
risk-parameter tuning or a false claim of independent OOS.
"""
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"configs/exp019_same_strategy_windows.json"
R=ROOT/"scripts/algogene_exp019_windows_run.py"
SPEC=importlib.util.spec_from_file_location("exp019",R)
runner=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class EXP019WindowsTest(unittest.TestCase):
    def test_exact_same_source_sha_as_real_exp018(self):
        plan=runner.build_plan()
        self.assertEqual(len(plan),2)
        self.assertEqual(plan[0]["source_sha256"],plan[1]["source_sha256"])
        manifest=json.loads(P.read_text())
        self.assertEqual(plan[0]["source_sha256"],manifest["exp018_source_sha256"])
        self.assertEqual(plan[0]["source"],plan[1]["source"])
        self.assertEqual([p["name"] for p in plan],
                         ["year-2025","full-2021-2025"])

    def test_windows_are_only_changed_native_settings(self):
        plan=runner.build_plan()
        self.assertEqual([p["settings"]["StartDate"] for p in plan],
                         ["2025-01","2021-01"])
        self.assertEqual([p["settings"]["EndDate"] for p in plan],
                         ["2025-12","2025-12"])
        self.assertEqual([p["settings"]["TradeCost"] for p in plan],[1,1])
        self.assertEqual([p["settings"]["dataset"] for p in plan],[60,60])
        self.assertEqual([p["settings"]["InitialCapital"] for p in plan],
                         [1000000,1000000])
        self.assertEqual([p["settings"]["Leverage"] for p in plan],[1,1])
        diffs=[k for k in plan[0]["settings"]
               if plan[0]["settings"][k]!=plan[1]["settings"][k]]
        self.assertEqual(set(diffs),{"StartDate","strategyName"})

    def test_evidence_guard_does_not_retry_and_reports_original_markers(self):
        code=R.read_text()
        self.assertIn('GITHUB_RUN_ATTEMPT',code)
        self.assertIn('get_current_tasks',code)
        self.assertIn('\"EXP018, HALT\" not in logs',code)
        self.assertIn('len(plan) == 2',code)
        self.assertIn('archive_exp019',code)
        self.assertIn('time.sleep(120)',code)


if __name__=="__main__":
    unittest.main()
