# Historical review after EXP-011 — 2026-11-17

All 15 strategy records below were read from saved platform evidence. Numbers are native fields rounded for display, never reconstructed. Different years and fee assumptions are labeled and are not pooled. V1.0 account/API smoke tests are functional checks rather than comparable trading-strategy performance.

| Record | Period | Native TradeCost | Score_Total | TotalPnL USD | AnnualSharpe | TradeCnt |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| [V1.1 fixed-size EMA/Donchian](EXP-006-result.json) | 2021-01 to 2023-12 | 0.0 | unavailable | -120.4837 | -0.2520 | 518 |
| [V1.2 ATR sizing](EXP-007/runs/43883914291-attempt-1.json) | 2021-01 to 2023-12 | 0.0 | 35.2988 | 16.8750 | 0.0513 | 326 |
| [V1.3 native 2ATR stop](EXP-008/runs/43890469995-attempt-1.json) | 2021-01 to 2023-12 | 0.0 | 34.3770 | 51.5489 | 0.1538 | 326 |
| [annual-2021](EXP-009/runs/43903526601-attempt-1-annual-2021.json) | 2021-01 to 2021-12 | 0.0 | 39.7134 | 56.7279 | 0.3963 | 104 |
| [annual-2022](EXP-009/runs/43903526601-attempt-1-annual-2022.json) | 2022-01 to 2022-12 | 0.0 | 45.3523 | -91.9164 | -0.8978 | 152 |
| [annual-2023](EXP-009/runs/43903526601-attempt-1-annual-2023.json) | 2023-01 to 2023-12 | 0.0 | 41.9746 | 86.7374 | 1.0068 | 70 |
| [ema-slope-24h](EXP-009/runs/43903526601-attempt-1-ema-slope-24h.json) | 2021-01 to 2023-12 | 0.0 | 33.6451 | 70.9968 | 0.2385 | 208 |
| [fee-stress](EXP-009/runs/43903526601-attempt-1-fee-stress.json) | 2021-01 to 2023-12 | 1.0 | 41.6652 | -109.0575 | -0.3133 | 322 |
| [stop-1.5](EXP-009/runs/43903526601-attempt-1-stop-1.5.json) | 2021-01 to 2023-12 | 0.0 | 34.1617 | 46.2367 | 0.1388 | 332 |
| [stop-2.5](EXP-009/runs/43903526601-attempt-1-stop-2.5.json) | 2021-01 to 2023-12 | 0.0 | 34.9864 | 23.3504 | 0.0695 | 326 |
| [EMA candidate with native fee](EXP-010/runs/44015443252-attempt-1-bundle.json) | 2021-01 to 2023-12 | 1.0 | 36.0853 | -34.0512 | -0.1099 | 206 |
| [breakout-patient](EXP-011/runs/44018479397-attempt-1-breakout-patient.json) | 2021-01 to 2023-12 | 1.0 | 31.0345 | -51.6847 | -0.3582 | 68 |
| [breakout-responsive](EXP-011/runs/44018479397-attempt-1-breakout-responsive.json) | 2021-01 to 2023-12 | 1.0 | 41.3526 | -124.8512 | -0.4783 | 194 |
| [pullback-patient](EXP-011/runs/44018479397-attempt-1-pullback-patient.json) | 2021-01 to 2023-12 | 1.0 | 32.9222 | -60.7696 | -0.4027 | 172 |
| [pullback-responsive](EXP-011/runs/44018479397-attempt-1-pullback-responsive.json) | 2021-01 to 2023-12 | 1.0 | 38.2718 | -417.9573 | -1.5585 | 360 |

## What the evidence supports

- All four EXP011 full-period native-cost candidates are negative; none is promoted.
- Among EXP011 rows, the highest Score_Total is associated with greater loss than EXP010. Native R-square score is high on several losing results, so score alone is not a profitability criterion.
- Maximum-drawdown subscores are already high; recovery duration, activity and return quality remain weaknesses. Inactivity and smaller drawdown alone are not success.
- Native console contains SKIP_SIZE with ATR 885.2221176540762 on 2023-10-02. The source floors size to .01 model increments; this can suppress otherwise risk-budgeted orders. That increment was never verified as a universal DMA platform minimum.
- Broker-specific metadata contain differing min volumes and increments. They are not proof of the user's DMA backtest rule. EXP012 therefore probes actual .001 execution and retains a registered coarse fallback.
- EXP010 remains a least-loss full-period cost comparator, not a profitable or validated strategy.
- Multi-change EXP011 results do not establish which individual change caused losses. No fabricated per-change contribution.
- Independent annual records have different capital resets and must not be summed into a continuous PnL. Zero-cost and fixed-cost results remain separate.
- V1.1 stored summary lacks Score_Total; no score is imputed.
- 2024 and 2025 remain unused; accumulated Development selection is not out-of-sample proof.

Full native performance dictionaries and all six score fields are copied in [the review JSON](history-through-EXP-011.json). Original responses remain authoritative; no formula for Score_Total is inferred or substituted.

The observed SKIP_SIZE example is in [EXP010 native console](EXP-010/runs/44015443252-attempt-1-bundle.json), 2023-10-02 00:00:00. It is a concrete diagnostic, not a count of all missed trades or an estimate of foregone returns. The console API may be truncated.

[EXP012 registration](EXP-012-history-research.md) responds to these findings. New strategy results remain NOT RUN until native evidence arrives. No profitable claim or higher-score promise is made.
