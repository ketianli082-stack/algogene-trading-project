# EXP-014 — H1-only quality gates

Registered: 2026-11-17. Backtest only. **2021–2023 Development** is the only period used; holdout 2024 Validation and 2025 Final Test remain unopened. No H4, H4 synthesis, or other time frame.

## Why
EXP013 H1 cost gate: native P/L +34.2432 USD on initial capital USD 10,000, native annual Sharpe 0.1201, maximum drawdown 1.576%, Profit Factor 1.094, 150 platform transaction events, TradeCost 1. Native cumulative daily P/L implies year-end changes approximately 2021 -24.00, 2022 -26.18, 2023 +84.42. Thus improve cross-regime robustness rather than blindly maximizing total Score. These are single uninterrupted equity-path year-end differences, **not** independent yearly backtests. The reported native transaction endpoint may cap results at 100 events.

## Fixed model and environment
BTCUSD, dataset=60 and historical interval H, EMA200 + previous Donchian20 breakout and Donchian10/EMA exit, EMA24-bar upward slope, ATR14 2x native stop and risk sizing capped to .02 lot, 20% available balance, and 0.01 lot model precision. Only completed prior hourly bars. Initial USD 10000, leverage 1, requested no shorts, native TradeCost=1.0. The latter is a fixed-cost stress assumption, not verified live broker fees.

## Registered single-factor candidates
- `h1-gate-reference`: EXP013 cost-filter rules, ratio <= .10, no extra slope or breakout buffer (must reproduce native EXP013 results).
- `cost-gate-08`: ONLY tighten cost/gross ATR-space ratio to <= .08 (versus .10).
- `trend-slope-005`: ONLY require 24-bar EMA change / ATR14 >= .05 in addition to original positive-slope signal.
- `breakout-buffer-010`: ONLY require breakout close above prior Donchian20 upper band by at least 0.10 ATR14.

All gates are ex ante, no lookahead. Thresholds are hypotheses, **not** optimized based on 2024/2025 results. An isolated negative result will be preserved rather than concealed. All three variants are compared to the identical H1 reference, not selected on the aggregate Score alone.

## Reproducibility and safety
GitHub Actions compiles and runs unit tests before sequential API submissions; unexpected config changes, unavailable API credentials, an existing account task, ambiguous submission, rejected fee evidence, or non-collected backtest prevents further runs. Every submission/source SHA, backtest ID and native platform response is saved immutably to experiments/EXP-014/runs with Actions artifact backup. A workflow retry cannot resubmit. Only native statistics are considered authoritative. The native transaction API may be truncated; check before trade-level attribution. No live trading endpoints.
