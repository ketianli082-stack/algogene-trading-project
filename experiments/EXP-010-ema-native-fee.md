# EXP-010 — EMA candidate with verified native fixed-cost setting

Registered 2026-11-17. Role: **Development**. Initial status: **NOT RUN**.

One backtest only: BTCUSD native 60-minute feed and hourly decisions,
2021-01 through 2023-12, capital 10000 USD, leverage 1, order-based environment.
Keep the 24-hour EMA200 slope entry filter, 2 ATR native stop and all sizing/exits
identical to [EXP-009 EMA candidate](EXP-009/runs/43903526601-attempt-1-ema-slope-24h.json).
The executable source is an exact copy of that run's submitted source, SHA256
`036fc0076556d59b6e0c5c764f268034310ea519926b1959769a69639be4b075`.
Only the native TradeCost changes from default/effective 0.0 to requested 1.0,
plus the experiment display name. This is a fixed-cost stress assumption, not
a verified brokerage quote or a synthetic percentage fee.

Question: does the EMA-filtered candidate remain worth retaining when the same
native fee that made the baseline negative is applied by ALGOGENE itself?
Reference native zero-cost TotalPnL: 70.9968 USD; baseline fixed-cost TotalPnL:
-109.0575 USD. These are separate platform results, not predictions or inputs
to a local fee deduction. Fee-dependent changes in balance/quantity/trades are
left to the platform.

Actions submits once after checking there are no active account tasks, saves the
actual submission IDs immediately, waits and collects original statistics,
console, trades and daily P/L. Effective TradeCost must be 1.0 with a nonzero
native transaction charge to mark the fee verified. Preserve all native fields,
including their signs and accounting differences. No reconstructed return,
P/L, transaction count, or financial statistics. Secrets stay in GitHub Secrets.

No live orders, reset, overlapping task, ambiguous POST retry or workflow rerun
submission. Failures/pending IDs are retained, never replaced by a new run.
Native allowShortSell encoding remains unverified: prior requested false returned
1.0; the exact strategy source contains only buy-side openings. Do not claim the
platform switch has been verified disabled.

Results are automatically saved under `experiments/EXP-010/runs/`. Missing fields
remain unavailable; no Backtest ID or result is assumed at registration.
After reviewing real cost results, decide whether independent annual cost runs
are warranted. No automatic candidate selection. 2024 and 2025 remain unused.

Pre-submission validation: 34 unit/safety checks passed, including pinned source,
unchanged comparison settings, closed holdout dates, no duplicate workflow retry,
native negative-charge preservation and rejection of an ignored fee. These are
mock/guard checks, not ALGOGENE backtest results.
