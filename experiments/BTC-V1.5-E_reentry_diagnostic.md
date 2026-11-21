# V1.5-E — Re-entry diagnostic (2026-11-21)

## Objective

C/D showed 9/15 RECOVERY_ARMED and zero RECOVERY_CANDIDATE or actual REENTRY. Diagnose state/condition failures before any rule changes.

## Mechanism and controls

Instrumented V1.5-C clone: long only; 12-hour cooldown; 2 reentries per trend; EMA20 recross; ADX25; EMA200; S2 cost-aware sizing; 3 ATR stop. No order, signal or risk decision changes. Hypothetical costs enter sizing only; TradeCost omitted.

New Recovery.explain diagnostic reports NOT_ARMED, LIMIT, NO_PRIOR_TIME, COOLDOWN, NOT_READY, TREND_LOST, ALREADY_ABOVE_EMA20, NO_RECROSS_EMA20, ELIGIBLE. Additional logs: RECOVERY_DIAG, RECOVERY_TREND_RESET, RECOVERY_CLOSE_CLASSIFY. Eligibility for actual trades still uses original predicate.

## Code and execution

- [Strategy](../strategy/btc_v1_5_e_reentry_diagnostic60.py)

- [Runner](../tools/btc_v1_5_e_cloud_run.py)

- [Tests](../tests/test_btc_v1_5_e.py)

- [Workflow](../../actions/workflows/btc-v1-5-e-cloud.yml)

- [Run 44902721758](../../actions/runs/44902721758), initial status queued. Result unverified.

## Acceptance and next steps

First verify native run success, COLLECTED evidence, effective dates/settings, and the same transactions/Score as C; any difference requires diagnosis. Attribute eligibility failures by stop event and observed hour. Only then consider a separate E-fix mechanism and run. F sideways filtering remains a separate experiment and is not started.