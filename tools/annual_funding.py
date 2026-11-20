"""BAS-001 按币种及年份使用历史平均年化 Funding 估算现金流。

CSV: symbol,year,annual_rate_pct,source
annual_rate_pct 以百分数填列；正数表示永续空头收款。
不得填入未经核实的历史均值；缺少年份/币种则报错。
该模型是离线估算，不代表真实逐次结算或平台 NAV。
"""
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

YEAR_HOURS = Decimal("8760")  # 约定统一 365 天年化基数


def _dt(value):
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("持仓时间必须包含 UTC 时区")
    return d.astimezone(timezone.utc)


def _decimal(value, name):
    try:
        d = Decimal(str(value))
        if not d.is_finite():
            raise ValueError
        return d
    except (InvalidOperation, ValueError):
        raise ValueError(name + " 不是有效有限数字") from None


def annual_funding(csv_path, symbol, start, end, quantity, reference_notional_usd):
    start, end = _dt(start), _dt(end)
    if start >= end:
        raise ValueError("平仓必须晚于开仓")
    qty = _decimal(quantity, "quantity")
    notional = _decimal(reference_notional_usd, "reference_notional_usd")
    if qty <= 0 or notional <= 0:
        raise ValueError("数量/名义金额必须大于零")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError("年度历史费率不存在：" + str(path))
    rates = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        if not {"symbol", "year", "annual_rate_pct", "source"} <= set(rd.fieldnames or []):
            raise ValueError("年度 Funding CSV 缺少必需列")
        for r in rd:
            name = r["symbol"].strip()
            year = int(r["year"])
            rate_txt = r["annual_rate_pct"].strip()
            source = r["source"].strip()
            if not rate_txt or not source:
                raise ValueError(f"{name}/{year} 缺少费率或出处，禁止填 0 代替")
            rate = _decimal(rate_txt, "annual_rate_pct")
            key = (name, year)
            if key in rates:
                raise ValueError(f"重复币种/年份费率: {key}")
            rates[key] = rate

    chunks = []
    cursor = start
    total = Decimal(0)
    while cursor < end:
        boundary = datetime(cursor.year + 1, 1, 1, tzinfo=timezone.utc)
        segment_end = min(end, boundary)
        key = (symbol, cursor.year)
        if key not in rates:
            raise ValueError(f"缺少 {symbol} {cursor.year} 年历史 Funding 年均值")
        hrs = Decimal(str((segment_end-cursor).total_seconds()))/Decimal(3600)
        income = notional * rates[key]/Decimal(100) * hrs / YEAR_HOURS
        chunks.append({"year":cursor.year, "hours":str(hrs),
                       "annual_rate_pct":str(rates[key]), "funding_usd":str(income)})
        total += income
        cursor = segment_end
    return {"funding_usd":total, "segments":chunks, "method":"annual_historical_mean_estimate"}
