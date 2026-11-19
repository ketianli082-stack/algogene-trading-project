# EXP-009 completed review — 2026-11-17

[Actions run 43903526601](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/43903526601) completed successfully. All eight registered/conditional runs are COLLECTED with empty collector errors, matching requested dates/dataset, and no detected strategy error markers. This is not a claim that every setting was honored or that console coverage is complete. Original response files and submission checkpoints are already committed.

All rows are Development, native BTCUSD 60-minute candles/hourly decisions. Numbers below are platform fields, rounded for display; no financial metric is reconstructed. Complete values are in [the review JSON](EXP-009-review.json) and original files.

## Annual baseline stability (native TradeCost 0.0)

| Run | Native TotalPnL USD | AnnualSharpe | maxDrawdown_amt USD | TradeCnt | Backtest ID |
| --- | ---: | ---: | ---: | ---: | --- |
| [2021 annual](EXP-009/runs/43903526601-attempt-1-annual-2021.json) | 56.7279 | 0.396267 | 93.6225 | 104 | 20261116_161928_856151 |
| [2022 annual](EXP-009/runs/43903526601-attempt-1-annual-2022.json) | -91.9164 | -0.897801 | 121.4527 | 152 | 20261116_163223_055852 |
| [2023 annual](EXP-009/runs/43903526601-attempt-1-annual-2023.json) | 86.7374 | 1.006760 | 40.6500 | 70 | 20261116_164520_522805 |

2022 is negative while 2021 and 2023 are positive. The strategy is not consistently profitable across these years. Each annual run resets capital/positions and changes its terminal exit year; do not add annual results to reconstruct the continuous three-year run.

## Stop and filter comparisons (2021–2023, native TradeCost 0.0)

Reference: [EXP-008 2 ATR baseline](EXP-008/runs/43890469995-attempt-1.json), ID 20261116_145545_935050: native TotalPnL 51.5489, AnnualSharpe 0.153802, maxDrawdown_amt 165.1143, TradeCnt 326.

| Run | Native TotalPnL USD | AnnualSharpe | maxDrawdown_amt USD | TradeCnt | Backtest ID |
| --- | ---: | ---: | ---: | ---: | --- |
| [2 ATR + EMA 24h slope](EXP-009/runs/43903526601-attempt-1-ema-slope-24h.json) | 70.9968 | 0.238498 | 163.3141 | 208 | 20261116_173607_095029 |
| [1.5 ATR stop](EXP-009/runs/43903526601-attempt-1-stop-1.5.json) | 46.2367 | 0.138801 | 160.3289 | 332 | 20261116_165813_062280 |
| [2.5 ATR stop](EXP-009/runs/43903526601-attempt-1-stop-2.5.json) | 23.3504 | 0.069543 | 179.5472 | 326 | 20261116_171708_796807 |

1.5/2/2.5 ATR all have weak positive zero-cost full-period results. This is limited neighboring-parameter evidence, not proof of robustness or after-cost profitability. Keep 2 ATR for the next controlled comparison rather than expanding a parameter search.

EMA slope is a candidate: native TotalPnL/Sharpe improve and TradeCnt falls, but native maxDrawdownDuration rises from 929 to 991. Do not describe it as an improvement in every risk measure. Its after-cost result is **NOT RUN**.

## Native fee verification and stress test

| Run | Native TotalPnL USD | AnnualSharpe | maxDrawdown_amt USD | TradeCnt | Backtest ID |
| --- | ---: | ---: | ---: | ---: | --- |
| [V1.0 fee probe](EXP-009/runs/43903526601-attempt-1-fee-probe.json) | 0.2920 | 3.000000 | 0.0000 | 2 | 20261116_160837_070947 |
| [2 ATR baseline, fixed fee 1.0](EXP-009/runs/43903526601-attempt-1-fee-stress.json) | -109.0575 | -0.313290 | 269.4643 | 322 | 20261116_175304_803706 |

Both fee runs return setting TradeCost=1.0. The probe's native opening transaction returns TradeCost=-1 and closing transaction TradeCost=0. This verifies an actual platform charge; do not invent a percentage rate or assume both sides carry a charge. The value 1.0 is a pre-registered fixed-cost stress assumption, not verified real broker pricing.

The 2 ATR baseline becomes negative under this stress. Native TradeCnt also changes from 326 to 322, so manual subtraction from the zero-cost result would not reproduce this backtest. Preserve the platform-returned P/L, ledger and statistics separately without reconciling them into a replacement value.

## Settings caveat

Returned dates, dataset, leverage, capital, instrument and order-based environment agree with the intended experiment values. However requested allowShortSell=false returns native string `1.0` in all eight runs. Its encoding/meaning is not verified; the earlier date/dataset match flag does not cover it. Inspected opening transactions are all buys and the strategy code has no short-entry branch. Verify the platform setting semantics before claiming its short-selling switch is disabled. No native setting or record has been altered.

## Next step (proposed, NOT RUN)

1. Run the exact EMA-24h-slope candidate with 2 ATR stop on 2021–2023, changing only native TradeCost to 1.0. Keep the hourly feed, sizing, capital and exits unchanged.
2. If the candidate remains worth retaining under costs, run its independent annual 2021/2022/2023 tests using the same native fee, and inspect original transactions for concentration and risk behavior. A loss is recorded as a loss, not fixed by retrospectively selecting new fee assumptions.
3. Resolve native short-selling flag semantics, then freeze a small candidate set with all settings and cost assumptions recorded before 2024 Validation. Do not move directly to 2025 or retune using its result.

No additional cloud experiment was submitted during this review. 2024 and 2025 remain unused.
