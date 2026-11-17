# ALGOGENE Crypto strategy project

Active research design: **2021–2023 Development, 2024 Validation, 2025 Final Test**. V1.0–V1.4 are iterative strategy versions. See the controlling [research protocol](docs/research_protocol.md) and [machine-readable windows](configs/research_windows.json). V1.0 is being rerun on January 2021 with effective-date verification.

Active V1.1 setting: **60-minute BTCUSD candles and hourly decisions**, EMA200, Donchian20 entry / Donchian10 or EMA exit, fixed 0.01 lot, long-only. See [EXP-006](experiments/EXP-006-v1.1-hourly.md).

V1.2 is registered in [EXP-007](experiments/EXP-007-v1.2-hourly.md): identical hourly signals and platform settings, ATR14-based opening quantity. Its Actions workflow automatically submits, waits, collects original platform responses and commits the evidence bundle. Platform-returned statistics are authoritative; no local P/L or return reconstruction for new runs.

V1.3 is registered in [EXP-008](experiments/EXP-008-v1.3-hourly.md): keep V1.2 signals and ATR sizing; attach the platform-native stopLossLevel at ask minus 2×ATR14. The same automatic collection/archive process saves original platform outputs, without local metric recalculation.

V1.2 and V1.3 now have automatically archived native results: [V1.2 evidence](experiments/EXP-007/runs/43883914291-attempt-1.json) and [V1.3 evidence](experiments/EXP-008/runs/43890469995-attempt-1.json). Both effective native TradeCost values are 0.0. [EXP-009](experiments/EXP-009-native-fees-robustness.md) registers a native fee API probe, independent annual runs, isolated stop sensitivity, and a 24-hour EMA slope filter. Its Actions workflow saves submission IDs and each row before continuing. New results remain NOT RUN until actual platform evidence arrives; 2024/2025 stay unused.

Current status: **V1.1–V1.3 hourly Development backtests completed for 2021–2023**. V1.3 native TotalPnL is **51.5489 USD**, AnnualSharpe **0.1538017462**, maxDrawdown_pct **0.0163334286**, TradeCnt **326**, effective TradeCost **0.0**; these are platform fields, not recalculated metrics. V1.0 functional evidence remains in [EXP-004](experiments/EXP-004-v1.0-development.md). EXP-009's eight native experiments are now collected; [review and next-step proposal](experiments/EXP-009-review.md). Independent annual baseline results vary, and native fixed-cost 1.0 makes the baseline negative. EMA filtering is an unvalidated candidate: its cost test is NOT RUN. Validation and Final Test remain unused.

The controlling deliverable is the user's current ALGOGENE official scoring template. Older repository plans, dates, candidate-team divisions, and research-stage assignments are retained as historical context only; they do not constrain current execution.

EXP-010 completed: [native result review](experiments/EXP-010-review.json), Score_Total **36.08528153883827**, TotalPnL **-34.0512 USD**, native fixed TradeCost **1.0** verified. The next [EXP-011 combination batch](experiments/EXP-011-combinations.md) registers four multi-change V1.5 candidates on 2021–2023 only, with the same risk caps and fee. Native total score and six subscores are now explicit comparison fields alongside profitability/drawdown. Candidates are NOT RUN until native evidence arrives; 2024/2025 remain unused.

## V1.0

V1.0 is a minimal compatibility experiment for BTCUSD:

- read three hourly historical bars with `getHistoricalBar`;
- submit one guarded `0.01` BTC market buy in an ALGOGENE cloud backtest;
- attach a 2% stop loss;
- close once on the next market event using the returned `tradeID`;
- refuse duplicates, missing data, invalid prices, and wrong subscriptions.

Start here:

- [Executable ALGOGENE script](src/algogene_crypto_v1_0.py)
- [Runbook, API evidence, and risk controls](docs/v1_0_runbook.md)
- [Reference backtest settings](configs/v1_0_smoke_test.json)
- [EXP-001 result record](experiments/EXP-001-v1.0-smoke.md)
- [Official-template report workspace](report/README.md)

## Truth and security rules

- `PASS` means direct evidence exists. Platform work that has not run is recorded as `NOT RUN`, never as an assumed success.
- Never invent a Backtest ID, trade, fill, P/L, Sharpe ratio, drawdown, or account permission.
- Never commit API keys, user IDs, account IDs, private exports, or unredacted platform logs.
- GitHub CI tests the script with a fake documented API surface. That is not an ALGOGENE backtest.
- A separate manual workflow can perform a read-only BTCUSD history call using GitHub Secrets; it cannot place trades or submit a cloud backtest.

## Official scoring-template order

The working report follows the supplied template rather than the repository's previous planning structure:

1. ALGOGENE System Info — User ID and Backtest ID remain private/blank until a real run exists.
2. Strategy Script.
3. Executive Summary (15 points).
4. Implementation Details (20 points).
5. Risk Management (20 points).
6. Capital Management (15 points).
7. Backtest Performance.
8. Real Trading / implementation considerations.

Existing material under `docs/` and `candidates/` may be reused only when it is consistent with actual V1.x evidence and the official template.
