# EXP-012 — Historical review, executable precision, and exit redesign

Registered 2026-11-17. **Development only. New results: NOT RUN.**
The controlling deliverable remains the user's ALGOGENE report template.
[Review of 15 historical strategy records](history-through-EXP-011.md) and
[exact native fields](history-through-EXP-011.json) explain this registration.

## Findings driving the change

All four EXP011 combinations lost money. The highest-scoring combination returned
Score_Total 41.35262330516897 but TotalPnL -124.85119999999915; EXP010 returned
36.08528153883827 and -34.05119999999988. Thus native score improvement alone can
coexist with worse losses. High R-square subscores on losing runs cannot be used
as evidence of a profitable equity curve. No failed candidate is promoted.

The source/log audit also found an implementation constraint: .01 quantity
flooring can turn a nonzero risk-budgeted size into zero. EXP010 console explicitly
reports SKIP_SIZE with ATR 885.2221176540762 on 2023-10-02. This is not proof of
foregone profits, and .01 was a model discretization, not an established DMA
minimum. Different broker metadata have different rules; do not borrow one
broker's minimum for this account.

## Shared native platform settings

BTCUSD, dataset 60, hourly decisions, 2021-01 to 2023-12 (except the Jan-2021
functional probe), initial 10000 USD, leverage 1, order-based accounting,
requested allowShortSell=false and long-entry code only. Native TradeCost=1.0
for every run, a fixed-cost stress assumption rather than verified broker pricing.
The native short-switch string 1.0 returned previously remains semantically
unverified; no platform field is rewritten to conceal that discrepancy.

Risk budget remains availableBalance * 0.001 / actual stop distance, capped at
20% notional and .02 lot. Quantity is floored, never rounded up. Finer sizing
can increase participation versus the .01-floor baseline, but does not increase
those per-order limits. Stops do not guarantee a realized loss limit. Terminal
liquidation stays 2023-12-31 22:00. No live-account orders or leverage increase.

## Bounded quantity probe and pre-registered fallback

First run V1.0's known one-round-trip script with volume .001 over Jan 2021.
Require actual native open AND close transactions at .001 before enabling that
model increment. An echoed requested parameter is insufficient. Do not claim it
is a universal broker rule even if this backtest accepts it.

If accepted, run all five candidates below at .001 increments. If explicitly
rejected or the platform task is verifiably DONE without confirming the requested
volume, keep .01 for the four new model combinations and mark the fine-size
control NOT RUN. Do not proceed past an ambiguous/PENDING task. No made-up
minimum volume and no repeated POST after an uncertain response.

## Five strategy candidates (after probe)

| Candidate | Entry and regime | Exit/protection | Purpose |
| --- | --- | --- | --- |
| ema-size-control | Exact EXP010 EMA200/Donchian20/EMA24-slope signals | Prior Donchian10 or EMA200 exit, native 2 ATR stop; no TP/hold limit | Isolate precision effect; only if .001 accepted |
| ema-bracket-3atr | Same EXP010 entry | Original signal exit, native 2 ATR stop, 3 ATR take profit, 72-hour native holdtime | Test bounded profit capture and duration |
| ema-bracket-4atr | Same EXP010 entry | Donchian20 or EMA200 exit, native 2 ATR stop, 4 ATR take profit, 120-hour native holdtime | Test more room for winners |
| range-wide | Re-entry above 20-bar lower band at 2 population SD, after previous close below prior band; close below 20-bar mean | Native 2 ATR stop, entry-time mean as TP, native 48-hour holdtime; mean-recovery or severe-regime-failure signal exit | Distinct flat-regime mean-reversion hypothesis |
| range-fast | Same range recovery at 1.5 SD | Native 1.5 ATR stop, entry-time mean TP, 24-hour native holdtime; same signal exits | More responsive neighboring configuration |

Range entries additionally require absolute EMA200 change over 24 hourly bars
<=0.5% and close >=98% of EMA200. Signal exit is close >=current 20-bar mean or
close <96% of EMA200, in addition to native protections. These are fixed model
hypotheses, not platform dropdowns or results chosen after viewing this batch.

All four new combinations require prospective target distance * order volume
>=3 USD before entry. This is an entry-space filter under contractSize=1, not
realized profit, a replacement fee calculation, or a claim of expected return.
Actual native costs and P/L remain untouched. The control has no such new filter.
There is no added cooldown, EMA50 exit/filter, averaging down or short entry.
No future bars, artificial timeframe aggregation, or broker-specific setting is invented.

## Official support for new order fields

[ALGOGENE admin OrderObject example](https://algogene.com/community/post/85)
uses native takeProfitLevel and stopLossLevel. The
[ALGOGENE maximum-holding example](https://algogene.com/community/post/477)
sets OrderObject.holdtime in seconds and uses native TP/SL. Candidate source
uses those supported fields, not locally fabricated fills or manually updated
trade outcomes. Native TP and holdtime actual account behavior remains subject
to the returned console/trades; any rejection/error is preserved, not called a pass.

## Comparison and reporting

Record platform Score_Total and all six score_* fields, plus native P/L, Sharpe,
drawdown, drawdown duration, TradeCnt and profit factor for every candidate.
Do not derive a score formula or optimize activity by adding pointless trades.
A high-score losing strategy is reported as losing; profitable/risk-acceptable
candidates would merit annual stability checks before 2024 Validation. No automatic
winner or additional search follows these six bounded submissions (five if the
fine-size control is skipped). 2024 and 2025 stay unused.

Actions serially submits, saves exact source/hash and native IDs immediately,
collects original platform responses, and commits each result/failure plus the
final bundle under EXP-012/runs. Workflow retries cannot submit another batch.
No active-account reset or ambiguous POST retry. Native fee must match 1.0;
no-trade runs explicitly have no observable charge rather than a fabricated one.

49 unit/safety checks and Python compilation passed before submission. Checks
include preserved control signals, fine-size risk limits, flat-regime recovery,
correct native TP/hold-time order fields, target-space skipping, precision requiring
real native fills, coarse fallback after explicit rejection, and stopping on a
pending probe. These mock/guard checks are not platform backtest results.
