# V1.4-B — ATR risk-budget sizing (1% NAV)

## Comparator selection
V1.3-A remains the development comparator. Previous project analysis reported Score 54.8116, PnL USD 6271.63, Sharpe 0.9896, max drawdown 8.80%, 127 native records and 63 closed round trips. [V1.3-A run](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44862020026).

V1.3-D added the EMA200 24-observation upward-slope recovery branch. The previous analysis reported matching performance and 0 RECOVERY entry checks among 325 checks (189 UPTREND, 136 BLOCKED). Retain the simpler A implementation. [V1.3-D run](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44868514356). These figures transcribe the preceding project analysis; linked native artifacts remain the primary evidence.

## Hypothesis and mechanism
The fixed 50% target allocation does not equalize planned downside risk under different BTC volatility levels. Test a 1% NAV planned risk cap using the same pre-entry ATR14 and fixed 3 ATR stop. Only sizing changes. EMA20/50, hourly EMA200 gate, ADX14 > 25, fill-anchored fixed stop, and exit rules remain identical to A.

For NAV N, cash available A, observed quote P, contract BTC units C, ATR a, risk r=0.01, volume in contracts:
q = floor_to_4_decimals(min(0.5*N/(P*C), 0.95*A/(P*C), r*N/(3*a*C))).
Invalid or nonpositive inputs produce no order. The observed-quote notional cap is a target rather than a guaranteed execution cap; slippage and hourly exit checks mean realized loss may exceed 1% NAV. No shorting or leverage increase. Record RISK_SIZE including intended allocation and intended stop risk. No fixed fee field sent.

## Evaluation protocol
BTCUSD, 60min, Jan 2021–Dec 2024, initial USD 10,000, leverage 1, long/flat. 2025 reserved. Native separate Action. Compare score, PnL, Sharpe, max drawdown, drawdown duration, 2022 PnL, closed trade count, allocation distribution, estimated versus realized loss as NAV percentage, and concentration of winning trades. Inspect stop and size logs, validate effective settings and positive trade count before accepting results. Fixed 50% V1.3-A remains control. 0.5% and 1.5% risk candidates are NOT RUN. This is a development experiment, not a live recommendation.

Result pending.
