# ALGOGENE Crypto strategy project

Active research design: **2021–2023 Development, 2024 Validation, 2025 Final Test**. V1.0–V1.4 are iterative strategy versions. See the controlling [research protocol](docs/research_protocol.md) and [machine-readable windows](configs/research_windows.json). V1.0 is being rerun on January 2021 with effective-date verification.

Current status: **January 2021 V1.0 Development cloud run in progress** (2026-11-16 HKT). Only effective-period-verified runs qualify for the research result tables.

The controlling deliverable is the user's current ALGOGENE official scoring template. Older repository plans, dates, candidate-team divisions, and research-stage assignments are retained as historical context only; they do not constrain current execution.

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
