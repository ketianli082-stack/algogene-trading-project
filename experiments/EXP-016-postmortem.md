# EXP-016 — Forensic postmortem (no new ALGOGENE submission)

Date: 2026-11-19. Source: immutable [#44476933626 final evidence](./runs/44476933626-attempt-1-final.json) and full platform logs/daily P&L.

## Exact reason GitHub Actions is red

The third workflow **successfully** submitted and completed the ALGOGENE backtest: `backtest_id=20261119_071235_471828`, `task_status=DONE`. The research harness intentionally set `status=INVALID_REVIEW` because **the platform's effective `TradeCost=1.0` differs from the requested `TradeCost=0.0005`**. All other explicitly checked backtest settings matched, including 2023-01 through 2025-12, 1,000,000 USD, daily dataset 1440, leverage 1, and the four subscribed instruments.

There was **no Python runtime crash**, no script `HALT`, and no ambiguous unhedged position in the returned complete log. GitHub red is a validation failure, not an inability to run four symbols. **Do not make the workflow green by ignoring the cost mismatch.**

Previous runs:
- #44460660539: our client mistakenly required a top-level status on a valid `meta_instrument` response; fixed; never submitted the strategy.
- #44475122402: actual `run_backtest` rejected unauthorized `.remove`; fixed; never created a task.
- #44476933626: script accepted and 136 trade events executed, but its effective cost was 1.0 fixed, not the requested 0.0005.

## Actual platform evidence — not a compliant 0.05% result

| Indicator | Recorded platform value |
|---|---:|
| Native Score_Total | 44.1596118650 |
| TotalPnL, USD | -50,158.285802 |
| AnnualSharpe | -0.231886 |
| Native MaxDrawdown | 9.4689% |
| Native TradeCnt | 136 |
| Profit factor | 0.689642 |
| Gross realized PnL, before platform flat fee | -50,090.285802 |
| Effective flat charge | USD 1 per opening leg (68 opens, USD 68 total) |
| Cost requested | 0.0005 (user intent: 0.05% of filled notional) |
| Effective cost returned | 1.0 (fixed charge per opened leg) |

The platform's official [fixed-cost guidance](https://algogene.com/community/post/117) explains that the backtest form supports a **fixed fee**, not native proportional commission. It cannot be inferred that `TradeCost: 0.0005` implements a 0.05% trading fee. Our empirical case confirmed the value was normalized/ignored and became 1.0. It remains unknown whether other fractional fixed fees are supported: do **not** claim to have proven a general lower bound from one case.

## Full-fill 0.05% offline cost sensitivity (not native Score)

All 136 executions (68 openings + 68 closings) are present in the console log and reconcile to `TradeCnt=136`. The REST `strategy_trade` response included only 100 records, so using that endpoint by itself would undercount fees. Verified `contractSize=1` for each of the four instruments.

- Sum of absolute USD executed notional (all fills): **21,459,530.226006**
- Charge of 0.05% on every executed notional: **USD 10,729.765113**
- Gross PnL reconstructed from each of the 68 matched open/close trade IDs: **USD -50,090.285802**
- Hypothetical net PnL with the same fills and 0.05% fees: **USD -60,820.050915**, roughly **-6.0820%** of initial capital.

Formula: fixed-fills net = realized gross PnL - 0.0005 × sum of absolute filled notional. The estimate does **not** reproduce native account equity, Score_Total, funding payments, slippage changes, or trades that would be prevented by different available cash. Native Score at 0.05% fee is **UNKNOWN**. Reproduce with `python scripts/audit_exp016_native.py` (fixture-backed tests `tests/test_exp016_native_audit.py`).

## Structural trading losses and data quality

Reconstructed matched realized gross PnL from 34 closed two-leg pairs:

| Pair | Completed pair trades | Gross PnL |
|---|---:|---:|
| BTC spot–futures | 18 | +327.514984 USD |
| ETH spot–futures | 16 | -50,417.800786 USD |

The native cumulative PnL by year: 2023 **-9,059.51**; 2024 **-47,349.85**; 2025 **-50,158.29** (last daily PnL on 2025-12-30). Year-over-year increments: roughly -9.06k, -38.29k and -2.81k respectively.

Two critical ETH pairs (prices/volumes quoted directly from platform order logs):
1. Trade IDs 39–40, **2024-05-18 to 2024-05-20**: ETH spot 3100.21 → 3071.88; ETH futures 3121.70 → 3666.48. Gross **-32,150.84 USD**; futures-versus-spot basis surged to about **19.36%** at exit. This is sufficiently unusual to demand quote quality, contract, expiry and venue inspection before calling the series a valid investable basis.
2. Trade IDs 37–38, **2024-05-16 to 2024-05-17**: gross **-14,263.68 USD**, also a sharp futures-versus-spot divergence.

Together these two trades account for approximately **92% of the ETH pair gross losses**. Neither a coding exception nor a fixed-commission change can correct that structural risk.

Additional log patterns: **28** `SKIP_HISTORY / HISTORY_STALE_CROSS_ASSET` events and **24** `SKIP_HEDGE_IMBALANCE` events. The history guard currently requires *all four* symbols' latest daily date to match, so a stale ETH leg can suppress a valid BTC signal, and vice versa. The order sizing rounds down to integer units, which creates some >5% dollar hedge mismatches.

## Funding and futures model limitations

`BTCUSDM` and `ETHUSDM` were confirmed as `producttype=FUT` by platform metadata. This alone does **not** prove identical exchange source, funding settlement, contract maturity or ability to trade a perfect cash-and-carry pair. Official guidance now describes how funding and swap curves can be supplied using `setFundingCurve()`: https://algogene.com/community/post/328. None was configured in this run. Therefore this is spread mean-reversion, not a verified full carry-arbitrage PnL calculation.

## Correct next engineering sequence (without another blind cloud run)

1. **Keep this run invalid for the requested cost.** Native Score 44.1596 is diagnostic only. Do not compare it directly with the older 2021–2023 / 10k-dollar candidates.
2. **Resolve the fee mechanism**: determine native fixed-fee precision/contract assumptions and choose a documented fixed-cost proxy for native Score, plus exact 0.05% turnover-based postprocessing from complete fills. Do not substitute fixed 1 USD and label it 0.05%.
3. **Audit the two ETH May 2024 outliers and market compatibility**; require validated common venue/expiry, realistic execution, and a conservative abnormal-basis/risk-off rule.
4. **Remove the cross-asset all-or-nothing history dependency**: validate BTC and ETH legs separately, with skip reasons and data freshness checks.
5. **Use a cost-aware economic edge threshold and risk gates** before optimizing native Score. After a candidate passes offline tests, launch *one* controlled ALGOGENE experiment and validate all effective settings before further variants.

This report was produced from an existing completed result. **No additional ALGOGENE backtest was triggered** by the postmortem or test changes.
