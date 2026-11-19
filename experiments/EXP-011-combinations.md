# EXP-011 — Score-focused combination research (V1.5 candidates)

Registered 2026-11-17, **Development** only. New candidate status: **NOT RUN**.
The user explicitly authorized multiple simultaneous changes to accelerate research.
This batch compares four fixed combinations, not one-factor attribution or an open-ended search.

## Current baseline — actual EXP-010 results

[Native evidence](EXP-010/runs/44015443252-attempt-1-bundle.json), Backtest ID
`20261117_041507_495517`: COLLECTED, no collector errors, native fee verified.

| Platform field | Native value |
| --- | ---: |
| Score_Total | 36.08528153883827 |
| TotalPnL (USD) | -34.05119999999988 |
| AnnualSharpe | -0.10989698376169071 |
| maxDrawdown_amt (USD) | 228.3140999999996 |
| maxDrawdown_pct | 0.02261903400874299 |
| maxDrawdownDuration | 991 |
| TradeCnt | 206 |
| score_AnnualSharpe | 47.25533720384388 |
| score_AvgDrawdownDuration | 6.234565556019908 |
| score_Rsquare | 27.35703129208671 |
| score_TradePerDay | 6.241539316319224 |
| score_WinRate | 31.68511926563418 |
| score_maxDrawdown_pct | 97.7380965991257 |

These are copied platform fields, not locally reconstructed statistics. The score
is a composite platform output; its complete transformation/weight formula is
unverified. A higher score alone does not demonstrate profitability. In particular,
R-square-related scoring must not be assumed to distinguish a smoothly losing
curve from a profitable curve without checking actual P/L and Sharpe.

## Fixed platform settings and risk isolation

BTCUSD, native dataset 60 (one-hour candles/hourly decisions), Jan 2021–Dec 2023,
10000 USD capital, leverage 1, order-based accounting, requested allowShortSell=false.
Native fixed TradeCost=1.0 for every candidate; this is a stress assumption,
not verified broker pricing. Actual returned settings/charges remain authoritative.
The prior native allowShortSell response was string 1.0, whose meaning is still
unverified. Code only opens buys and closes by trade ID; no short entry or live account order.

Budget remains availableBalance * 0.001 divided by actual stop distance, capped at
20% available-balance notional and 0.02 lot, floored to .01 model increments.
Three-ATR stops therefore reduce size rather than increasing the nominal budget.
Stops and sizing are not guaranteed realized loss limits; .01 is a model increment,
not a newly claimed broker minimum. No pyramiding, no leverage or exposure increase.

## Four pre-registered combinations

All require EMA50 > EMA200, close > EMA200, and EMA200 above its value 24 hourly
bars earlier. EMAs are seeded with the corresponding past closes and updated
recursively. All signals use only bars strictly before the current market event,
as in the baseline. No new platform timeframe/dropdown/API field is introduced.

| Candidate | Entry | Exit | Native stop | Re-entry wait |
| --- | --- | --- | --- | --- |
| breakout-responsive | Close above preceding 20-bar high | Below preceding 10-bar low OR EMA50 | 2 ATR14 | 6 hours |
| breakout-patient | Close above preceding 40-bar high | Below preceding 20-bar low OR EMA50 | 3 ATR14 | 12 hours |
| pullback-responsive | Previous close <= previous EMA20, current close > EMA20, with trend filter | Below preceding 10-bar low OR EMA50 | 2 ATR14 | 6 hours |
| pullback-patient | Same EMA20 recovery entry, with trend filter | Below preceding 20-bar low OR EMA50 | 3 ATR14 | 12 hours |

The wait is strategy logic based on the latest market event at a confirmed close;
exits are still allowed during the wait. Terminal liquidation remains Dec 31 2023
22:00. Pullback entry does not use the candidate's entry-channel length; its exit,
stop and waiting parameters distinguish the two pullback variants.

Hypotheses, not conclusions: the EMA50 filter and crossover entries may avoid some
weak trends/chasing; a faster trend exit may reduce prolonged losses, while wider
channels/stops may avoid some noise; waiting may reduce churn. Costs, opportunity
loss and reduced activity can offset these effects. We do not add purposeless
trades to inflate the activity subscore, or tune to make a losing curve linear.
Official background: [costs and backtesting](https://algogene.com/community/post/11),
[ATR stop-distance sizing](https://algogene.com/community/post/41).

## Comparison and review policy

1. Record native Score_Total and all six score_* fields alongside native P/L,
   Sharpe, drawdown, duration, TradeCnt and profit factor. Missing fields stay missing.
2. Compare all four against EXP-010 under the same fee and dates. Improving total
   score is a priority, but a high-score loss is not described as a successful strategy.
3. Review profitable, risk-acceptable candidates first, using native score to help
   order them. If none qualify, retain all failures and report that finding.
4. No automatic winner, parameter expansion, 2024 test or 2025 test follows this batch.
   A small retained set must later face annual stability checks and 2024 Validation.

Actions serially submits each candidate once, archives its exact source/hash and
actual submission IDs immediately, then waits and collects the original responses.
Completed/rejected rows and final bundle are committed under EXP-011/runs, with a
partial artifact fallback. Unknown/pending tasks and missing fee/score evidence
stop the batch. Explicit platform rejection creates no task and may allow the
next registered candidate. No reset or ambiguous POST retry. Workflow retries
cannot submit another batch. This avoids rerunning the old eight experiments.

41 unit/safety checks and Python compilation passed before submission. Checks cover
bull/bear trend gating, prior-channel timing, pullback entry, stop-distance sizing,
cooldown entry blocking without blocking exits, native score copying and stopping
on pending tasks. They are mock/guard checks, not ALGOGENE performance results.
