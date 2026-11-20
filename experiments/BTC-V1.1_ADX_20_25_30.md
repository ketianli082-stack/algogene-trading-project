# BTC V1.1 — Hourly EMA20/50 with ADX14 trend filter

## Objective
Test whether filtering new long entries at EMA20-up-cross signals by Wilder ADX14 reduces noise from sideways markets relative to the V1.0 EMA-only baseline. Not a prediction that higher ADX improves results.

## Data / comparability
- Single instrument: BTCUSD; hourly `dataset=60`
- Development/training: **2021-01 through 2024-12**
- Held-out evaluation: **2025**, not run or used for selection here
- Initial capital: USD 10,000; leverage: 1; long-only; target up to 50% equity
- Same signal timing as V1.0: use **only prior completed hourly bars** to decide at current timestamp
- Code and submitted settings intentionally contain **no fixed trading-cost assignment**; retrieve effective platform assumptions in evidence

## Hypothesis and exact signal
- Upward EMA20 / EMA50 crossover with ADX14 > threshold: open BTCUSD long
- Downward EMA20 / EMA50 crossover: close long **regardless of ADX**
- If ADX does not pass on the crossing bar, do not enter late. This tests a strict crossover filter, not a persistent position-state rule.
- Wilder ADX14 derives from genuine H/L/C hourly observations, not invented spreads. Missing OHLC causes safely skipped signal and clears the indicator window, so zero fills may indicate data-interface mismatch.
- Threshold experiments: **A=20**, **B=25**, **C=30**. Only the threshold changes; all other settings are held constant.

## Execution and reproducibility
- Strategy: [btc_v1_1_ema_adx60.py](../strategy/btc_v1_1_ema_adx60.py)
- Native cloud runner: [btc_v1_1_cloud_run.py](../tools/btc_v1_1_cloud_run.py)
- CI: [btc-v1-1-cloud.yml](../.github/workflows/btc-v1-1-cloud.yml)
- Tests: [test_btc_v1_1.py](../tests/test_btc_v1_1.py)
- No live trading endpoints; use only `run_backtest`, `task_status`, `strategy_stats`, `strategy_logs`, `strategy_trade`, `strategy_pl`.
- Sequential submissions stop at the first failure or unresolved task. Do not retry an ambiguous submission.

## Evidence and decision criteria
For each threshold, preserve platform effective settings, Score_Total, TotalPnL, AnnualSharpe, maxDrawdown_pct, TradeCnt, WinRate, profit_factor, order logs, trades, and daily PnL. Compare to the verified V1.0 baseline using identical time window and funding/fee caveats. A higher gross score alone is insufficient: consider drawdown, trade count, execution errors, and whether there was actual trading. Inspect 2024 separately when selecting candidate rules; 2025 remains untouched.

**Status: RUNNING** — final statistics must be read from the GitHub Action artifact, not estimated.
