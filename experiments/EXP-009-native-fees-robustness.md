# EXP-009 — Native fees, annual stability, and isolated robustness tests

Role: **Development** only, BTCUSD native 60-minute feed / hourly decisions.
Status at registration: **NOT RUN**. No new Backtest IDs or performance claims.
This is V1.4 research, not a frozen final strategy. 2024 and 2025 stay unused.

## Native fee evidence

Readonly inspection of the logged-in account in **Safari**, 2026-11-16, found
an editable transaction-cost field (`交易费用`), current value `0.0`.
The official [fixed transaction-cost explanation](https://algogene.com/community/post/117)
describes platform fixed costs. The REST `run_backtest` input schema does not
document `TradeCost`, although `strategy_stats.setting` returns it.
Therefore UI support does **not** establish API acceptance.

Probe: V1.0's small round trip, Jan 2021, requesting native `TradeCost: 1.0`.
This is an explicit **fixed-cost stress assumption**, not a broker fee quote or
percentage estimate. Acceptance requires BOTH native effective setting `1.0`
and nonzero native transaction `TradeCost`. Rejection/ignored/missing cost stays
unverified. No locally calculated costs, net P/L, or alternative performance.

## Pre-registered sequence

All tests use initial capital 10000 USD, leverage 1, no short-entry code,
order-based accounting, same signal timing and source V1.3 except listed change.
Holding the sizing denominator at 2 ATR isolates the stop change; the nominal
loss at the stop consequently varies with its distance and is not a fixed risk guarantee.

| Row | Period | Single change / purpose |
| --- | --- | --- |
| fee-probe | Jan 2021 | V1.0 minimum round trip, requested fixed cost 1.0 |
| annual-2021 | 2021 | V1.3 baseline; terminal exit in Dec 2021 |
| annual-2022 | 2022 | V1.3 baseline; terminal exit in Dec 2022 |
| annual-2023 | 2023 | V1.3 baseline; terminal exit in Dec 2023 |
| stop-1.5 | 2021–2023 | Stop 1.5 ATR; sizing denominator stays 2 ATR |
| stop-2.5 | 2021–2023 | Stop 2.5 ATR; sizing denominator stays 2 ATR |
| ema-slope-24h | 2021–2023 | Baseline stop 2 ATR plus EMA200 > its value 24 hourly bars earlier |
| fee-stress (conditional) | 2021–2023 | Baseline plus fixed cost 1.0, ONLY if probe verified |

Stop 2 ATR / filter off full-period reference is the existing raw
[EXP-008 response](EXP-008/runs/43890469995-attempt-1.json), Backtest ID
`20261116_145545_935050`, TradeCost `0.0`.
Other comparison rows request the same settings with no undocumented fee override;
their effective native cost must remain 0.0 or the batch stops to avoid pooling
different cost assumptions. Even when supported, stress-cost evidence is kept
separate from zero-cost ablation results.

A one-bar rising EMA condition is redundant when close > current EMA is already
required by the recursive EMA formula. The slope test therefore fixes a 24-bar
lookback before seeing results. It changes only the entry filter, not exits,
sizing, or the 2 ATR stop. Parameter choices are strategy logic, not new platform
timeframe/options. Historical EMA warm-up may use pre-year bars, never future bars.
Annual runs reset capital/positions; they cannot be added to reconstruct the
continuous three-year baseline. Terminal exit is Dec 31 22:00 in each run's end year.

## Evidence and interpretation

Actions serially submits once, monitors up to 45 minutes per task, collects native
stats, console, transactions and daily P/L. Each completed/rejected row is committed
immediately under `experiments/EXP-009/runs/`; the final bundle and partial failures
are also committed and retained as an artifact. Exact submitted source and SHA256,
requested/effective settings, code commit and native IDs are included. No resets,
live-account orders, ambiguous POST retries, or workflow rerun submissions.
Pending/unknown tasks stop the sequence. Missing/failed tasks keep NOT RUN or
their explicit failure status. Only explicit rate-limit rejections are retried.

After collection, compare only platform-reported P/L, Sharpe, drawdown,
profit factor and counts. Inspect native transactions for concentration; do not
derive a replacement P/L/statistic. Latest-console API coverage may be truncated.
Adjacent stops should show similar behavior to support robustness; one profitable
year or one best parameter does not establish stability. No automatic winner is
selected. Native costs, missing fields and failures must accompany any conclusion.

## Report mapping

- Executive Summary: existing EMA/Donchian long-only trend hypothesis.
- Implementation Details: hourly baseline, isolated stops/slope, exact archived source.
- Risk Management: capped sizing/native stops, annual drawdown and adjacent settings.
- Capital Management: identical capital reset, unchanged exposure and sizing caps.
- Backtest Performance: native annual and full-period evidence, explicit cost limitations.

## Pre-submission checks

29 unit/safety checks passed, including identical baseline source, isolated stop
changes, a nonredundant EMA slope case, holdout guards, native fee evidence checks,
pending-task stop, disabled workflow rerun submissions, ambiguous POST no-retry,
and secret redaction. These checks use mocks and are **not platform backtests**.
