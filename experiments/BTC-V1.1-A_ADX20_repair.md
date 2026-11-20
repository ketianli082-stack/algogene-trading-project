# BTC V1.1-A — EMA20/50 + Wilder ADX14 > 20

**State:** Standalone ALGOGENE cloud backtest dispatched via GitHub Actions.

## What was fixed
Earlier V1.1 tried to calculate ADX from `on_bulkdatafeed` values `h/l/c`, but its callback may provide only the latest quote. Missing OHLC caused the algorithm to clear all EMA observations, preventing signals and potentially producing zero trades.

The revised V1.1-A preserves exactly the V1.0 hourly EMA price stream. Only when a bullish EMA cross occurs and the strategy is flat, it requests 160 hourly historical bars via `getHistoricalBar({"instrument": "BTCUSD"}, 160, "H", now)`. It discards bars timestamped at or after the decision timestamp, validates each OHLC bar, sorts by time, then calculates Wilder ADX14. Entry requires ADX > 20. Bearish EMA cross always exits independently of ADX. If history is unavailable, entry is skipped and a platform diagnostic log is produced, **without destroying EMA history**.

## Fixed experiment settings
BTCUSD, hourly `dataset=60`, USD 10,000, leverage 1, no short selling, up to 50% target allocation; **2021-01 through 2024-12 development only**; 2025 untouched. **No `TradeCost` field or manual cost assignment** in the submitted settings or strategy.

## Separation from B/C
Only **threshold 20** is submitted by `.github/workflows/btc-v1-1-a-cloud.yml` calling `tools/btc_v1_1_a_cloud_run.py`. Thresholds 25 and 30 will have separate actions if requested. The previous combined A/B/C action was canceled and is not used for selection.

## Validation
Inspect backtest artifact `outputs/btc_v1_1_a/evidence.json` for the platform Backtest ID, native Score_Total, total PnL, Sharpe, maximum drawdown, and actual TradeCnt. Review platform logs for `ADX_ENTRY_CHECK`, `ADX_NOT_READY`, `ADX_HISTORY_ERROR`, `BUY_SUBMIT`, and execution errors. Success of GitHub workflow by itself is not proof of actual trading.
