# V1.3-D — Dynamic EMA200 direction gate

## Development comparator
[V1.3-A native backtest](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44862020026). Prior conversation reported Score 54.81, PnL USD 6271.63, Annual Sharpe 0.9896, max DD 8.80%, 127 native trade records, 63 completed round trips and 2022 PnL +483.19. Compared with V1.2-B, 25 fewer completed trades, including 19 losing and 6 winning trades; the prior analysis identified a missed October 2023 winner. These are transcribed prior findings; the linked artifact is the primary evidence.

## Intervention
Keep V1.3-A long/flat EMA20/50 crossover, ADX14 > 25, fixed 3 ATR14 stop, 50% allocation, and hourly execution unchanged. Allow entry when previous observed quote exceeds EMA200 OR when EMA200 has increased over the previous 24 observed hourly intervals. The latter branch also allows below-EMA prices when the longer trend is recovering. No recovery exemption until 25 initialized EMA observations exist. All signals use data available strictly before current execution time. A 24-bar slope is a preselected research parameter, not an optimized value. An increasing EMA over 24 bars does not establish that a reversal will succeed.

## Settings and evaluation
BTCUSD, 60min, 2021-01 to 2024-12, USD 10000, 1x, long only, no fixed TradeCost field. 2025 reserved. Independent Action, no live trading. Compare actual trade count, score, Sharpe, PnL, max DD, drawdown duration, 2022 performance and recovered entries against A. Inspect EMA200_ENTRY_CHECK regime labels. Results pending.
