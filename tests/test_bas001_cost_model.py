import unittest
from decimal import Decimal
from tools.bas001_cost_model import calculate
from tools.annual_funding import annual_funding

ANNUAL = "tests/fixtures/funding_annual_synthetic.csv"


class CostModelTests(unittest.TestCase):
    def setUp(self):
        self.trade = {
            "quantity": 1,
            "spot_open_ask": 100000,
            "spot_close_bid": 101000,
            "perp_open_bid": 100500,
            "perp_close_ask": 101100,
            "annual_funding_csv": ANNUAL,
            "perp_symbol": "BTCUSDT",
            "open_time_utc": "2024-12-31T12:00:00+00:00",
            "close_time_utc": "2025-01-01T12:00:00+00:00",
        }

    def test_two_yield_fields_and_cross_year(self):
        d = calculate(self.trade)
        self.assertEqual(Decimal(d["gross_pnl_usd"]), 400)
        self.assertEqual(Decimal(d["net_pnl_ex_funding_usd"]), 400)
        expected = Decimal("100500") * (
            Decimal("0.10")*Decimal(12)/Decimal(8760)
            - Decimal("0.05")*Decimal(12)/Decimal(8760))
        self.assertLess(abs(Decimal(d["estimated_funding_usd"]) - expected), Decimal("1e-18"))
        self.assertLess(abs(Decimal(d["net_pnl_including_estimated_funding_usd"]) - (400+expected)), Decimal("1e-18"))
        self.assertEqual(len(d["funding_year_segments"]), 2)

    def test_btc_and_eth_differ(self):
        btc = annual_funding(ANNUAL, "BTCUSDT", self.trade["open_time_utc"], self.trade["close_time_utc"], 1, 100500)
        eth = annual_funding(ANNUAL, "ETHUSDT", self.trade["open_time_utc"], self.trade["close_time_utc"], 1, 100500)
        self.assertNotEqual(btc["funding_usd"], eth["funding_usd"])

    def test_percent_cost(self):
        t = dict(self.trade)
        t["commission_rates"] = {x: "0.0005" for x in
            ("spot_open","spot_close","perp_open","perp_close")}
        t["slippage_rates"] = {x:"0.0001" for x in t["commission_rates"]}
        r = calculate(t)
        self.assertEqual(Decimal(r["commission_usd"]), Decimal("201.3000"))
        self.assertEqual(Decimal(r["extra_slippage_usd"]), Decimal("40.2600"))
        self.assertEqual(Decimal(r["net_pnl_ex_funding_usd"]), Decimal("158.4400"))

    def test_no_missing_year_rate(self):
        with self.assertRaises(ValueError):
            calculate(dict(self.trade, perp_symbol="DOGEUSDT"))

    def test_no_unsupported_constant_average(self):
        with self.assertRaises(ValueError):
            calculate(dict(self.trade, funding_rate_annual_pct=11.94))

    def test_no_double_platform_fee(self):
        with self.assertRaises(ValueError):
            calculate(dict(self.trade, platform_commission_usd=40))

    def test_leap_year_boundary_hours(self):
        r = annual_funding(ANNUAL,"BTCUSDT","2024-12-31T23:00:00+00:00",
                           "2025-01-01T01:00:00+00:00",1,100)
        self.assertEqual([Decimal(x["hours"]) for x in r["segments"]], [Decimal("1"), Decimal("1")])


if __name__ == "__main__":
    unittest.main()
