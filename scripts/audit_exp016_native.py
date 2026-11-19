"""Audit EXP-016 completed ALGOGENE evidence without re-submitting a backtest.

The platform returned TradeCost=1.0 after receiving TradeCost=0.0005.
ALGOGENE supports fixed transaction charges, not native proportional
commission on each fill. Reconstruct 0.05% cost ONLY as a fixed-fills
counterfactual, never as the native Score_Total.
"""
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/EXP-016/runs/44476933626-attempt-1-final.json"
PATTERN = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}\] INFO: order "
    r"(opened|closed) with trade_ID: (\d+), (buy|sell) (\d+(?:\.\d+)?) lot "
    r"for (BTCUSD|BTCUSDM|ETHUSD|ETHUSDM) at (\d+(?:\.\d+)?)$"
)


def audit(evidence, proportional_cost="0.0005"):
    if evidence.get("experiment") != "EXP-016":
        raise ValueError("Wrong experiment evidence")
    fast = evidence["runs"][0]
    stats = fast["platform"]["stats"][-1]
    perf = stats["performance"]
    setting = stats["setting"]
    if fast["status"] != "INVALID_REVIEW":
        raise ValueError("Expected fixed frozen invalid-review result")
    if fast["backtest_id"] != "20261119_071235_471828":
        raise ValueError("Source Backtest ID differs")
    if str(fast["settings"]["TradeCost"]) != "0.0005" or \
            str(setting["TradeCost"]) != "1.0":
        raise ValueError("Platform fee mismatch is not the expected one")
    if any(not v for k, v in fast["setting_checks"].items() if k != "TradeCost"):
        raise ValueError("A second effective configuration setting differs")
    if any(Decimal(str(meta.get("contractSize"))) != Decimal("1")
           for meta in fast["contract_metadata"].values()):
        raise ValueError("Cannot value fills with an unverified contract multiplier")
    rate = Decimal(str(proportional_cost))
    if rate < 0 or rate > Decimal("0.1"):
        raise ValueError("Invalid rate")
    lines = fast["platform"]["logs"][-1]["res"].splitlines()
    if not any("Backtest finished!" in line for line in lines):
        raise ValueError("Incomplete platform log")
    if any("FOUR_ASSET, HALT" in line for line in lines):
        raise ValueError("Cannot audit a strategy with emergency halt as ordinary fills")

    fills = []
    for line in lines:
        m = PATTERN.match(line)
        if not m:
            continue
        date, kind, trade_id, side, lot, instrument, price = m.groups()
        volume = Decimal(lot)
        price = Decimal(price)
        fills.append({
            "date": date, "kind": kind, "id": int(trade_id), "side": side,
            "volume": volume, "instrument": instrument, "price": price,
            "notional": price * volume,
        })
    if len(fills) != perf["TradeCnt"]:
        raise ValueError("API TradeCnt does not match all log fills: incomplete audit")

    opens = {}
    realized_by_asset = defaultdict(Decimal)
    native_open_count = 0
    for fill in fills:
        key = fill["id"]
        if fill["kind"] == "opened":
            if key in opens:
                raise ValueError("Duplicate open tradeID")
            opens[key] = fill
            native_open_count += 1
        else:
            opened = opens.pop(key, None)
            if opened is None or opened["instrument"] != fill["instrument"] or \
                    opened["side"] == fill["side"] or opened["volume"] != fill["volume"]:
                raise ValueError("Unmatched close, asset, direction or lot size")
            signed = Decimal("1") if opened["side"] == "buy" else Decimal("-1")
            realized_by_asset[fill["instrument"]] += (
                fill["price"] - opened["price"]) * opened["volume"] * signed
    if opens:
        raise ValueError("Naked or unclosed positions exist")
    total_gross = sum(realized_by_asset.values(), Decimal("0"))
    native_net = Decimal(str(perf["TotalPnL"]))
    native_deduction = total_gross - native_net
    # Frozen evidence shows a fixed $1 cost per opening trade (not per fill).
    if abs(native_deduction - native_open_count) > Decimal("0.02"):
        raise ValueError("Gross P/L does not reconcile to native fixed cost")
    total_notional = sum((r["notional"] for r in fills), Decimal("0"))
    percent_fee = total_notional * rate
    net_fixed_fill_scenario = total_gross - percent_fee
    daily = fast["platform"]["daily_pl"][-1]["res"]
    last_per_year = {}
    for row in daily:
        last_per_year[row["Acdate"][:4]] = row

    out = {
        "source_backtest_id": fast["backtest_id"],
        "native_platform_status": fast["status"],
        "meaning": "Backtest executed; rejected by research harness for TradeCost mismatch",
        "settings_different": {"TradeCost": {
            "requested": fast["settings"]["TradeCost"],
            "effective": setting["TradeCost"]}},
        "native_score_total_not_at_requested_fee": perf["Score_Total"],
        "native_trade_count": perf["TradeCnt"],
        "fully_reconciled_log_fills": len(fills),
        "native_total_pnl_usd": float(native_net),
        "native_sharpe": perf["AnnualSharpe"],
        "native_max_drawdown_fraction": perf["maxDrawdown_pct"],
        "gross_pnl_before_native_trade_charges_usd": float(total_gross),
        "native_fixed_charge_inferred_usd": float(native_deduction),
        "native_open_trade_count": native_open_count,
        "gross_by_asset_usd": {k: float(v) for k, v in realized_by_asset.items()},
        "total_traded_notional_usd": float(total_notional),
        "counterfactual_assumed_rate": float(rate),
        "counterfactual_proportional_charges_usd": float(percent_fee),
        "counterfactual_net_pnl_if_fills_unchanged_usd": float(net_fixed_fill_scenario),
        "counterfactual_net_return_on_1m_initial": float(
            net_fixed_fill_scenario / Decimal("1000000")),
        "counterfactual_native_score_at_rate": None,
        "counterfactual_native_sharpe_at_rate": None,
        "counterfactual_native_max_drawdown_at_rate": None,
        "annual_native_cumulative_pnl": {
            year: {"through": row["Acdate"], "usd": row["TotalPL"]}
            for year, row in last_per_year.items()},
        "limitations": [
            "0.05% is applied offline to logged execution notional on all 136 fills; "
            "ALGOGENE did NOT natively run with these proportional fees",
            "Counterfactual keeps the 68 opened/68 closed fills unchanged; "
            "different fees might change available margin and actual fills",
            "Does not include funding/swap, carry, tax or additional slippage "
            "unless already explicitly booked by the platform",
            "Exact native Score_Total under 0.05% is unknown and must not be invented",
            "The trades REST endpoint returns only 100 records, whereas the "
            "full console log and native TradeCnt reconcile 136 execution events",
        ],
    }
    return out


def main():
    result = audit(json.loads(SOURCE.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
