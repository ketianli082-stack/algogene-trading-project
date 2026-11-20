# EXP020O 2021–2025 — completed platform run, failed workflow status guard

- Original GitHub Actions run: https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44696342943
- Backtest ID: `20261120_074452_631404`
- Platform row status: `COLLECTED`; all effective-setting checks passed, including native `TradeCost=0.0`.
- Strategy: original frozen EXP020 0.05% fill-notional fee, unchanged; API `TradeCost` key omitted.
- Native Score_Total: `79.44612089352381` (before internal percentage-fee adjustment).
- Native TotalPnL: `11812.457644519978` USD.
- Fill-level simulated fees: `4998.823588` USD; adjusted net PnL `6813.634056519978` USD.
- Native AnnualSharpe: `2.268311457241186`; TradeCnt: `200`.
- The 2021–2025 trading totals match the 2023–2025 totals. Fee ledger years are 2023–2025 only; further diagnosis is needed to distinguish missing historical data from insufficient signals in 2021–2022.

## Root cause of red GitHub Action

The recovery intentionally selected a single date window using `EXP020O_ONLY_WINDOW`, but the runner's final guard still required `len(plan) == 2`, even if every selected row was `COLLECTED`. This incorrectly set bundle status to `STOPPED` and exit code 1. It was a workflow logic bug, not a backtest execution failure.

The guard has since been fixed to require a nonempty plan with all selected rows collected, without requiring exactly two rows. **The historical action remains red and is not rerun**: rerunning would risk duplicate ALGOGENE submission, and the runner explicitly blocks repeat attempts. The immutable original evidence remains in `runs/44696342943-attempt-1-final.json` and its collected snapshot.
