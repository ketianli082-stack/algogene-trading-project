import unittest
from datetime import datetime, timedelta, timezone
from tools.bas002a_mean_reversion import normalize, aligned_basis, evaluate, summarize

class MeanReversionTests(unittest.TestCase):
    def test_reject_missing_prices(self):
        with self.assertRaises(ValueError):
            normalize({"res":[{"timestamp":"2024-01-01","volume":3}]})
    def test_explicit_close_proxy(self):
        data, fields=normalize({"res":[{"timestamp":"2024-01-01T00:00:00Z","close":100}]})
        self.assertEqual(next(iter(data.values()))["mode"], "close_proxy")
    def test_bidask_mid(self):
        data,_=normalize({"res":[{"timestamp":"2024-01-01T00:00:00Z","bidPrice":99,"askPrice":101}]})
        self.assertEqual(next(iter(data.values()))["value"],100)
    def test_pair_alignment_and_positive_basis(self):
        a,_=normalize({"res":[{"timestamp":"2024-01-01","close":100}]})
        b,_=normalize({"res":[{"timestamp":"2024-01-01","close":101}]})
        out,_=aligned_basis(a,b)
        self.assertAlmostEqual(out[0][1],100)
    def test_future_signal_avoids_lookahead(self):
        base=datetime(2024,1,1,tzinfo=timezone.utc)
        s=[]
        for i in range(260):
            v=50+ (20 if i==168 else 0)
            s.append(((base+timedelta(hours=i)).isoformat(),v))
        rows=evaluate(s)
        subset=[x for x in rows if x["signal_timestamp_utc"]==s[168][0]]
        self.assertEqual(set(x["horizon_hours"] for x in subset),{24,48,72})
        self.assertTrue(all(x["basis_change_bp"]<0 for x in subset))
    def test_no_signal_no_undefined_ratio(self):
        s=[((datetime(2024,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat(), 10.0) for i in range(260)]
        self.assertEqual(summarize(evaluate(s))["24"]["signals"],0)

if __name__=="__main__":
    unittest.main()
