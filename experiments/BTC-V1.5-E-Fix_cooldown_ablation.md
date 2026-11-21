# V1.5 E-Fix — Re-entry cooldown ablation (2026-11-21)

## Status at registration

Queued as three independent native ALGOGENE backtests. The queue order is fixed at
6 hours, then 4 hours, then 2 hours. A downstream backtest job executes only after
an explicit gate verifies that the preceding workflow concluded successfully; a
failed predecessor makes the downstream workflow fail without an ALGOGENE call.
All three backtests share the
`btc-algogene-cloud-exclusive` concurrency group.

## Single isolated change

The submitted source is the completed V1.5-E diagnostic source with exactly one
replacement: `COOLDOWN_HOURS = 12` becomes 6, 4, or 2. V1.5-C/E with 12 hours and
native `Score_Total` 57.354357 remains the control. A shorter cooldown is a
mechanism-reachability hypothesis, not a declared improvement.

## Frozen controls

- BTCUSD only; native dataset 60; hourly decisions.
- January 2021 through December 2024 development interval. 2025 is excluded.
- Initial capital USD 10,000; leverage 1; long only.
- 0.5% NAV risk budget, 3 ATR stop, 50% NAV allocation cap, 95% available-cash cap.
- S2 hypothetical cost-aware sizing remains unchanged.
- `TradeCost` is omitted from submitted settings. Platform-returned effective
  settings are preserved verbatim in evidence and are not treated as a requested
  fixed cost.
- ADX25, EMA20/50, EMA200 direction gate, two-reentry limit, order handling, fatal
  safety markers, and all diagnostic logging remain unchanged.

## Evidence and acceptance

Each run writes a separate redacted `evidence.json` artifact containing the Git
commit and Actions run ID, submitted-source SHA-256, ALGOGENE backtest/task IDs,
effective settings, complete native statistics and score fields, strategy logs,
transactions, and daily P/L. Credentials are redacted. A run succeeds only when
the platform reports the fixed period/settings, has nonzero trades, and contains
no fatal strategy marker. Failure stops the serial chain; no ambiguous submission
is retried automatically.

Compare each result with the unchanged 12-hour V1.5-C/E control on native score,
PnL, Sharpe, drawdown, trade count, actual re-entry count and contribution,
repeated-stop behavior, and diagnostic rejection reasons. Do not select a winner
from activity alone.
