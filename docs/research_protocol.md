# Controlling research protocol — 2026-11-16

User-approved design: three years development, one year validation, one year final test. This supersedes earlier schedules, role assignments, and experimental date choices. The ALGOGENE official report template controls the final deliverable; this split is the user's research design, not an asserted course requirement.

| Role | Period | Permitted work |
| --- | --- | --- |
| Development | 2021-01-01 to 2023-12-31 | Develop V1.0–V1.4, compare parameters, ablations, risk rules |
| Validation | 2024-01-01 to 2024-12-31 | Evaluate a small preselected candidate set; document selection |
| Final Test | 2025-01-01 to 2025-12-31 | Run frozen selected code/configuration; no tuning from final-test returns |

## Versions are iterations, not years

| Version | Scope | Development comparison |
| --- | --- | --- |
| V1.0 | API/history/minimal buy-close compatibility | January 2021 smoke test; no alpha claim |
| V1.1 | EMA + Donchian trend breakout | Full 2021–2023 |
| V1.2 | ATR-based sizing | Same data and costs; compare against V1.1 |
| V1.3 | Stops and risk management | Same data and costs; compare against V1.2 |
| V1.4 | Integrated strategy and robustness | Same development set; then 2024 selection; then frozen 2025 test |

Before V1.1: confirm the account actually honors the requested 2021 window. Historical data availability in public marketing does not establish account entitlement. If dates are silently changed, mark the run INVALID_PERIOD and exclude it from development/validation/final comparisons. Do not substitute another date range without a recorded decision.

## Comparability and no look-ahead

- All return comparisons use identical instrument, data interval, starting equity, cost model, leverage and flat initial positions. User's latest choice on 2026-11-16: 60-minute indicator candles and decisions on every new hourly event (EXP-006). This supersedes the H4 signal / four-hour decision design; the proposed five-minute version was never launched.
- Account finding from EXP-005: native dataset=240 rejected; supported event datasets are 1, 5, 60 and 1440 minutes. The active V1.1+ baseline uses dataset=60, interval H and hourly decisions. Old H4 experiments are not matched hourly comparisons.
- The cloud API dates are month-granular: 2021-01 to 2023-12; annual windows end in December. Save requested and effective platform settings separately.
- Prior-year observations may warm up EMA200, Donchian and ATR. Indicators use only bars known as of the decision time. Exclude the signal bar from the breakout channel and verify completed-bar timestamp semantics before claiming no look-ahead.
- Annual tests reset starting equity and position to the same values. A continuous three-year development run is a separate experiment; do not splice independent annual curves into a continuous-equity curve.
- Record explicit commission, spread, slippage, funding and contract-size assumptions. Unverified costs stay UNKNOWN; no cost-adjusted profitability claim until reconciled.
- Log every run, failure, requested/effective dates, code SHA, configuration, platform ID, data role and evidence URL. Version improvements require matched comparisons, not different-year returns.

## Freeze and holdout disclosure

Before reading final-test performance, commit a freeze manifest identifying the selected code SHA, configuration hash, all parameters, costs, risk rules, selection evidence and date. Do not modify a frozen strategy based on 2025 performance and still describe the repeated test as untouched holdout.

Prior technical trials are excluded from research comparisons. Deleting a result file does not establish that data was never seen; any claim of an untouched holdout must be checked against actual experiment history. No 2025 research queries before freeze.

## Report evidence to produce

For each year: role, net return, Sharpe, maximum drawdown, Backtest ID and cost basis. Also provide equity/drawdown curves, monthly returns, matched Buy & Hold benchmark, and V1.1–V1.4 ablation results. These remain NOT RUN until real evidence exists.

| Year | Role | Net return | Sharpe | Maximum drawdown |
| --- | --- | --- | --- | --- |
| 2021 | Development | NOT RUN | NOT RUN | NOT RUN |
| 2022 | Development | NOT RUN | NOT RUN | NOT RUN |
| 2023 | Development | NOT RUN | NOT RUN | NOT RUN |
| 2024 | Validation | NOT RUN | NOT RUN | NOT RUN |
| 2025 | Final Test | NOT RUN | NOT RUN | NOT RUN |
