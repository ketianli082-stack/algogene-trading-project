"""Independent, offline native-evidence audit for the unchanged EXP018 strategy.

Uses immutable GitHub-archived JSON. Never calls ALGOGENE and never guesses
missing trade rows from a truncated transaction endpoint.
Run: python scripts/audit_exp018_independent.py
"""
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP018 = ROOT / "experiments/EXP-018/runs/44511783153-attempt-1-final.json"
EXP016 = ROOT / "experiments/EXP-016/runs/44476933626-attempt-1-final.json"
SYMS = ("BTCUSD", "BTCUSDM", "ETHUSD", "ETHUSDM")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def roundtrips(trades):
    by_id = defaultdict(dict)
    for tr in trades:
        by_id[tr["trade_ID"]][tr["openclose"]] = tr
    result = []
    for trade_id, pair in sorted(by_id.items()):
        if set(pair) != {"open", "close"}:
            continue
        op, cl = pair["open"], pair["close"]
        if (op["symbol"] != cl["symbol"]
                or not math.isclose(float(op["volume"]), float(cl["volume"]),
                                    rel_tol=0, abs_tol=1e-9)):
            raise AssertionError("Mismatched native order leg: %s" % trade_id)
        signed_qty = float(op["volume"]) * int(op["buysell"])
        gross = signed_qty * (float(cl["price"]) - float(op["price"]))
        fees = float(op["TradeCost"]) + float(cl["TradeCost"])
        result.append({"id": trade_id, "symbol": op["symbol"],
                       "open": op["timestamp"], "close": cl["timestamp"],
                       "gross": gross, "fees": fees, "net": gross + fees})
    return result


def run():
    d = read(EXP018)
    prev = read(EXP016)
    row = d["runs"][0]
    p = row["native_metrics"]
    assert d["status"] == row["status"] == "COLLECTED"
    assert all(row["setting_checks"].values())
    assert float(row["effective_settings"]["TradeCost"]) == 1
    assert row["effective_settings"]["dataset"] == "60"
    assert row["source_sha256"] == "6088dbe6abb48892d7e6de8bafdeb01b65a0e3f08178eb27927d5eb3cfed8b0f"

    daily = row["platform"]["daily_pl"][0]["res"]
    assert len(daily) == 1095 and daily[0]["Acdate"] == "2023-01-01"
    assert daily[-1]["Acdate"] == "2025-12-30"
    assert all(daily[i]["Acdate"] < daily[i+1]["Acdate"] for i in range(len(daily)-1))
    assert math.isclose(daily[-1]["TotalPL"], p["TotalPnL"], abs_tol=0.01)

    # Full 1095-day records, not the limited trade endpoint.
    last = daily[-1]
    by_symbol = {k: last[k] for k in SYMS}
    assert math.isclose(sum(by_symbol.values()), last["TotalPL"], abs_tol=0.01)
    yearly = {}
    prev_end = 0
    for year in ("2023","2024","2025"):
        year_end = [x for x in daily if x["Acdate"].startswith(year)][-1]["TotalPL"]
        yearly[year] = round(year_end - prev_end, 2)
        prev_end = year_end
    assert math.isclose(sum(yearly.values()), p["TotalPnL"], abs_tol=0.01)

    by_day = []
    highest_equity = 1_000_000.0
    highest_date = None
    ddmax = {"pct": 0}
    for idx, record in enumerate(daily):
        equity = 1_000_000 + record["TotalPL"]
        if equity > highest_equity:
            highest_equity, highest_date = equity, record["Acdate"]
        drawdown = (highest_equity - equity) / highest_equity
        if drawdown > ddmax["pct"]:
            ddmax = {"pct": drawdown, "trough": record["Acdate"],
                     "peak": highest_date, "loss_usd": highest_equity - equity}
        prev_total = daily[idx-1]["TotalPL"] if idx else 0
        item = {"date": record["Acdate"],
                "change": round(record["TotalPL"] - prev_total, 2)}
        by_day.append(item)
    assert math.isclose(ddmax["pct"], p["maxDrawdown_pct"], abs_tol=1e-6)

    native_trades = row["platform"]["trades"][0]["res"]
    legs = roundtrips(native_trades)
    assert len(native_trades) == 100
    assert len(legs) == 50
    assert sum(x["fees"] for x in legs) == -50
    assert all(x["fees"] == -1 for x in legs)
    assert all(x["symbol"] in SYMS for x in legs)
    # 50 round-trip legs correspond to the first 25 fully matched BTC pairs.
    sample_last_close = max(x["close"] for x in legs)[:10]
    sample_native_pnl = next(x["TotalPL"] for x in daily
                             if x["Acdate"] == sample_last_close)
    sample_independent_pnl = sum(x["net"] for x in legs)
    assert math.isclose(sample_independent_pnl,sample_native_pnl,abs_tol=0.01)
    assert p["TradeCnt"] == 1704 and len(native_trades) < p["TradeCnt"]

    # Historical EXP016 is a separate dated native transaction observation,
    # not proof of what EXP018 executed on the same date.
    old = prev["runs"][0]["platform"]["trades"][0]["res"]
    bad_legs = roundtrips([x for x in old if x["trade_ID"] in (39,40)])
    assert len(bad_legs) == 2
    assert {x["symbol"] for x in bad_legs} == {"ETHUSD","ETHUSDM"}
    bad_gross = sum(x["gross"] for x in bad_legs)
    assert math.isclose(bad_gross, -32150.843464, abs_tol=0.01)
    eth_date = next(x for x in daily if x["Acdate"] == "2024-05-20")
    eth_prev = next(x for x in daily if x["Acdate"] == "2024-05-19")
    diff = {k: round(eth_date[k] - eth_prev[k], 2) for k in SYMS}

    return {
        "experiment": "EXP-018",
        "native_backtest_id": row["backtest_id"],
        "strategy_sha256": row["source_sha256"],
        "native_score": p["Score_Total"],
        "net_pnl": p["TotalPnL"],
        "annual_pnl": yearly,
        "asset_pnl": by_symbol,
        "daily_observation_count": len(daily),
        "daily_last_date": daily[-1]["Acdate"],
        "daily_max_drawdown": ddmax,
        "platform_max_drawdown": p["maxDrawdown_pct"],
        "worst_daily": sorted(by_day,key=lambda r:r["change"])[:5],
        "trade_api_returned": len(native_trades),
        "native_trade_events": p["TradeCnt"],
        "independently_rebuilt_trade_legs": len(legs),
        "sample_first_25_pair_net": round(sample_independent_pnl, 8),
        "sample_platform_cumulative": sample_native_pnl,
        "observed_first_50_open_fee_total": -50,
        "EXP016_eth_2024_05_20_gross_pair_loss": round(bad_gross, 8),
        "EXP018_2024_05_20_leg_daily_change": diff,
        "EXP018_2024_05_20_day_pnl": round(eth_date["TotalPL"]-eth_prev["TotalPL"],2),
        "console_truncated": "trimmed" in row["platform"]["logs"][0]["res"].splitlines()[0],
        "audit_limit": "No historical 2024 H1 close quotes and no complete EXP018 per-trade ledger. Cannot prove venue/time misalignment or recover 2024's worst exact pair."
    }


if __name__=="__main__":
    print(json.dumps(run(),indent=2,ensure_ascii=False))
