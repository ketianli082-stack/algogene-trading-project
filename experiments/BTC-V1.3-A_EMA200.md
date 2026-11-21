# V1.3-A — Hourly EMA200 regime direction gate

Comparator: V1.2-B (ADX25 + fixed 3 ATR14 stop), [native run 44860654523](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44860654523).

## Prior result and motivation
The preceding project analysis reported Score 54.5422 versus 54.2558, PnL $6,533.43 versus $6,234.46, Sharpe 0.8955 versus 0.8607, max drawdown 13.26% versus 13.03%, 88 completed round trips for each, and 12 ATR-triggered exits. The fixed stop improved profit modestly but did not remove the long 2022 drawdown. Prior analysis attributed $219.94 of the improvement to stop-exited trades and about $79.02 to remaining trade sizing differences; this is a transcription of that analysis, not a fresh independent audit. See original artifacts for verification.

## Exact hypothesis
A longer trend direction filter may avoid opening longs during persistent bearish regimes, whereas ADX alone measures strength rather than direction. It may also miss early recoveries; no improvement is assumed.

## Intervention
Keep EMA20/50, ADX14 > 25, 3 ATR14 fixed stop anchored at confirmed execution price, hourly market exit checks, 50% target allocation, and all platform settings unchanged. At each bullish crossover while flat, require the **previous observed hourly quote** to be strictly above its EMA200. The independent recursive EMA200 starts with the mean of the first 200 hourly observations; no entry before it is initialized. Update EMA200 with the current quote only after checking the signal. Preserve V1.2-B's original EMA20/50 window exactly. This is an hourly quote-proxy filter, not a daily timeframe indicator. No additional exit rule. No fixed fee field sent.

## Evaluation
BTCUSD, hourly, Jan 2021–Dec 2024, USD 10,000, leverage 1, long/flat. 2025 stays reserved. Compare native score, PnL, Sharpe, maximum drawdown and duration, 2022 PnL, completed trades, actual stop exits, and retention of major winners. Check EMA200_ENTRY_CHECK logs and nonzero actual trades; inspect warm-up effects. Do not select on score alone. Daily EMA50/200 are separate future experiments, not part of A.
