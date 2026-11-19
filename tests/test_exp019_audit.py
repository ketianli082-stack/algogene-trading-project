"""Verify independent audit uses archived observations and reconstructs 25 pairs."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "audit_exp018",ROOT/"scripts/audit_exp018_independent.py")
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class AuditNativeEvidence(unittest.TestCase):
    def test_first_25_pairs_reconstruct_native_after_fee_pl(self):
        r=a.run()
        self.assertAlmostEqual(r["sample_first_25_pair_net"],
                               r["sample_platform_cumulative"],places=2)
        self.assertEqual(r["independently_rebuilt_trade_legs"],50)
        self.assertEqual(r["observed_first_50_open_fee_total"],-50)

    def test_full_daily_equity_and_ethereum_anomaly(self):
        r=a.run()
        self.assertEqual(r["daily_observation_count"],1095)
        self.assertAlmostEqual(r["daily_max_drawdown"]["pct"],
                               r["platform_max_drawdown"],places=5)
        self.assertEqual(r["daily_max_drawdown"]["trough"],"2024-05-20")
        self.assertLess(r["EXP018_2024_05_20_leg_daily_change"]["ETHUSDM"],-4800)
        self.assertAlmostEqual(r["EXP016_eth_2024_05_20_gross_pair_loss"],
                               -32150.843464,places=2)


if __name__=="__main__":
    unittest.main()
