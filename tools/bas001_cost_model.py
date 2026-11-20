"""BAS-001 百分比成本核算：线性 USD 合约、成交价含 Bid/Ask。

费率均为小数（0.0005 = 0.05%）；Funding 使用 BTC/ETH 各年度历史平均年化费率（包括跨年分段）；融资仍使用年化利率。
价格为实际/明确标为模拟的成交价格；若真实成交已含滑点，额外滑点设零。
"""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tools.annual_funding import annual_funding

HOURS_PER_YEAR = Decimal("8760")
LEGS = ("spot_open", "spot_close", "perp_open", "perp_close")


def dec(v, field):
    try:
        x = Decimal(str(v))
        if not x.is_finite():
            raise ValueError
        return x
    except (ValueError, InvalidOperation):
        raise ValueError(f"{field} 必须为有限数值") from None


def calculate(r):
    q = dec(r["quantity"], "quantity")
    p = {k: dec(r[k], k) for k in (
        "spot_open_ask", "spot_close_bid", "perp_open_bid", "perp_close_ask")}
    if q <= 0 or any(v <= 0 for v in p.values()):
        raise ValueError("数量和成交价必须为正数")
    gross_spot = q * (p["spot_close_bid"] - p["spot_open_ask"])
    gross_perp = q * (p["perp_open_bid"] - p["perp_close_ask"])
    gross = gross_spot + gross_perp
    notional = {
        "spot_open": q * p["spot_open_ask"],
        "spot_close": q * p["spot_close_bid"],
        "perp_open": q * p["perp_open_bid"],
        "perp_close": q * p["perp_close_ask"],
    }

    def per_leg_cost(field):
        rates = r.get(field, {})
        if set(rates).difference(LEGS):
            raise ValueError(f"{field} 包含未知交易腿")
        vals = {leg: dec(rates.get(leg, 0), field + "." + leg) for leg in LEGS}
        if any(v < 0 for v in vals.values()):
            raise ValueError(field + " 费率不能为负")
        return sum((notional[leg] * vals[leg] for leg in LEGS), Decimal(0))

    commission_model = per_leg_cost("commission_rates")
    slippage_model = per_leg_cost("slippage_rates")
    # 若平台已对账户净值扣手续费，需要避免从账户 NAV 再次扣除。
    # 此工具计算“基于毛交易 PnL 的净额”，不可用它再扣一次平台已扣成本。
    if "platform_commission_usd" in r:
        raise ValueError("百分比成本模式不接受平台美元手续费；请先确定毛/净收益口径")

    if "funding_rate_annual_pct" in r or "funding_history_csv" in r:
        raise ValueError("请使用带出处的逐年历史均值 CSV，而非统一平均或逐次结算配置")
    funding_data = annual_funding(
        r["annual_funding_csv"], r["perp_symbol"],
        r["open_time_utc"], r["close_time_utc"], q,
        notional["perp_open"])
    from tools.annual_funding import _dt
    start, end = _dt(r["open_time_utc"]), _dt(r["close_time_utc"])
    h = Decimal(str((end-start).total_seconds())) / Decimal("3600")
    annual_financing_pct = dec(r.get("financing_rate_annual_pct", 0), "financing_rate_annual_pct")
    borrowed = dec(r.get("borrowed_usd", 0), "borrowed_usd")
    if h < 0 or annual_financing_pct < 0 or borrowed < 0:
        raise ValueError("持仓时长、融资年化利率、借款额不能为负")

    # 永续空头：年化 Funding 正数代表空头收款；负数代表空头付款。
    funding = funding_data["funding_usd"]
    financing = borrowed * (annual_financing_pct / 100) * h / HOURS_PER_YEAR
    net_ex = gross - commission_model - slippage_model - financing
    net = net_ex + funding
    out = {k: str(v) for k, v in {
        "spot_gross_pnl_usd": gross_spot,
        "perp_gross_pnl_usd": gross_perp,
        "gross_pnl_usd": gross,
        "commission_usd": commission_model,
        "extra_slippage_usd": slippage_model,
        "net_funding_usd": funding,
        "financing_usd": financing,
        "net_pnl_ex_funding_usd": net_ex,
        "estimated_funding_usd": funding,
        "net_pnl_including_estimated_funding_usd": net,
        "net_pnl_usd": net,
    }.items()}
    out["funding_method"] = funding_data["method"]
    out["funding_year_segments"] = funding_data["segments"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", type=Path)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    d = calculate(json.loads(args.input_json.read_text(encoding="utf-8")))
    output = json.dumps(d, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
