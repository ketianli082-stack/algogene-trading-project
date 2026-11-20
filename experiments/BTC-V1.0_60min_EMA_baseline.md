# BTC V1.0 — 60min EMA baseline (NOT RUN)

## Purpose
One BTC instrument only (BTCUSD). Establish a transparent non-LLM baseline before exploring market regimes or LLM signals. No cross-asset or spot–perpetual basis trade.

## Data split
- **Development/training:** 2021-01-01 to 2024-12-31, hourly bars.
- **Held-out evaluation:** 2025-01-01 to 2025-12-31. Do **not** access this period for parameter tuning; earlier project research may already have exposed 2025 results, so describe the hold-out limitation accurately.
- EMA20 and EMA50 are initially fixed, not chosen by optimizing 2025.

## Initial ALGOGENE settings
| Parameter | Setting |
|---|---|
| Subscribe | BTCUSD only |
| Interval | 60 min |
| Start/end | 2021-01-01 / 2024-12-31 |
| Initial capital | USD 10,000 |
| Base currency | USD |
| Leverage | 1 |
| Trade cost | 0 (fixed platform setting; deliberate *gross-of-cost* baseline) |
| Risk-free rate | 0% |
| Short selling | Disabled |
| News/weather/economic feeds | Disabled |
| Target entry allocation | Up to 50% of equity, constrained by available balance |

## Rule
On each new timestamp T, use only observations prior to T. Buy on EMA20 crossing *above* EMA50; close long on downward cross. Stay flat otherwise. Maximum one logical long position. Submit market orders, log order fills and rejects. Internal synthetic bar price for signals is bid/ask mid if available, otherwise close; do not treat this as an executable fill.

## Critical limitations and verification
- **NOT RUN** on ALGOGENE and **NOT PROFIT VALIDATED**. Confirm contractSize, instrument, minimum quantity, bar timestamp conventions, whether quote price matches chosen feed, and success/partial/reject callbacks.
- Market orders execute at platform prices, not at the signal's reference price.
- Zero transaction fees ignore commission, bid/ask spread impact, slippage, and (if a perpetual instrument is substituted) funding.
- This version does not implement a stop loss, dynamic sizing, or the LLM. It is a *baseline*, not a deployable live strategy.
- In the first ALGOGENE run, verify both entry and exits, and that no duplicate orders or hanging pending states occur. The next version may incorporate additional risk controls without changing the held-out window.

## Evidence to capture
Backtest ID / Actions run, actual period, number of trades, gross PnL, Sharpe (with 0% benchmark), maximum drawdown, NAV curve, year/month returns, order rejection log. No values are claimed until a successful verified run.

Script: [strategy/btc_v1_0_ema60.py](../strategy/btc_v1_0_ema60.py).
