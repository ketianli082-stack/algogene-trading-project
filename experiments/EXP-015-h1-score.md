# EXP-015 — Optimize ALGOGENE Score_Total using H1 signals only

Registered 2026-11-17; **not yet run when registered**. Only 2021-01 to 2023-12 Development is eligible for candidate search. Both 2024 Validation and 2025 Final Test remain sealed. H4, 240-minute data, and synthetic H4 are categorically excluded.

## Prior native evidence
EXP014 returned four registered candidates, all with native COLLECTED status. H1 cost gate ratio .10: Score_Total 33.0151, after-cost TotalPnL +34.2432 USD, Sharpe +0.1201, TradeCnt 150, max drawdown 1.576%. Ratio .08: **Score_Total 41.4143**, TotalPnL -68.7341 USD, Sharpe -0.2912, TradeCnt 100, max drawdown 1.611%. The .08 score increase came largely from score_Rsquare 66.6080 versus .10 score_Rsquare 0.2770, despite losing money in each of the three years. The ratio .10 trend slope addition yielded Score 33.6538, and breakout buffer .10 yielded Score 33.7837. **No claim of profitability or deployment suitability follows from Score_Total alone.**

## Priority: platform-native Score_Total
The user explicitly selected platform native Score_Total as the primary ranking target. ALGOGENE's exact score aggregation is not assumed or reconstructed. Read six native subscore fields unchanged and report native after-cost P/L, Sharpe, native drawdown, transaction count, and profit factor alongside score.

Pre-registered *research eligibility* criteria (not edits to ALGOGENE's score): collected valid metrics, at least 40 native transaction events, drawdown <= 3%, and TotalPnL >= -100 USD (no more than -1% of original $10k). A high-score/no-trade or high-score/high-loss candidate is **reported** in the native score ranking but **cannot** be labeled top eligible. The algorithm does not send live orders; these eligibility guards only control reporting and avoid misleading selection. Never alter native metrics to boost scores.

## EXP015 H1-only single-factor candidates
0. **score-reference-08**: unchanged EXP014 cost-gate-08 strategy, same source logic, 0.08 ratio, no extra slope or breakout gate (expected native score 41.4143, subject to reproducibility).
1. **gate-relax-09**: 0.09 cost ratio only, all other parameters unchanged.
2. **gate-tighten-07**: 0.07 cost ratio only, all other parameters unchanged.
3. **gate08-trend-slope-005**: retain cost ratio 0.08; 24-bar EMA change / ATR >= 0.05 only added gate.
4. **gate08-breakout-005**: retain cost ratio 0.08; close above previous Donchian20 by 0.05 ATR only added gate.

Every candidate uses BTCUSD, native dataset 60 / historical interval H, order-based, initial capital $10,000, leverage 1, native fixed TradeCost=1.0. The $1 native entry cost is an experimental stress setting, not verified broker commission. No change to EMA200, Donchian20/10, slope window 24 bars, ATR14 sizing, 2ATR native stop, 0.01 model size increments, notional exposure cap, or long-only source. No synthetic returns, no automatic tuning using 2024/2025 data.

## Execution and records
Single config push triggers Actions after offline tests. Submit sequentially only when account has no task, then wait for native DONE; a timeout/ambiguous POST must halt further submissions. Archive submitted exact strategy source SHA, backtest/task IDs, settings, native statistics and raw platform data under immutable EXP-015 paths. Output native-score-leaderboard.json with sorted original platform scores and separately labeled eligibility flags. No workflow rerun is allowed to duplicate platform requests. A strategy or configuration error invalidates a candidate. The platform transactions endpoint may be truncated; native TradeCnt is authoritative.

## Research decision
Select highest *eligible* platform-native score only as a **development candidate**, not a final or live strategy. The score may favor steady loss profiles, so disclose every deterioration in TotalPnL, profitability, Sharpe and annual subperiods. Historical tests can overfit: first freeze candidate, then run 2024 Validation and finally 2025 Final only on the teacher's prescribed release schedule.
