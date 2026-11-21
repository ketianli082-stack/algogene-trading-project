# V1.4-S Pilot — Native ALGOGENE fixed-cost diagnostic

Purpose: determine whether the native backtest API correctly accepts a fractional fixed transaction cost, whether actual platform fees/PnL reflect it, and whether the returned NAV used by V1.4-A position sizing changes. Do not interpret this as a true slippage execution model.

Official reference: https://algogene.com/community/post/117 (admin, 2023-06-12, confirms fixed-cost setup and turnover-based cost proxy).

## Matched design
Two sequential ALGOGENE native backtests, each using unchanged V1.4-A code, BTCUSD, 60min, January–December 2024, USD 10,000, 1x leverage, 0.5% ATR risk budget, 50% allocation cap. No 2025 data. Baseline omits TradeCost completely. Diagnostic explicitly submits TradeCost=0.37 in API settings only. USD 0.37 is deliberately a noninteger test value, not a calibrated estimate of market costs. Existing research configurations and strategies remain unchanged. No live orders.

## Verification
Collect independent runtime IDs, effective settings, native performance, transaction records, daily PnL and logs (including RISK_SIZE). Verify nonzero trade count and effective period. A fractional-cost diagnostic passes the settings check only if the fee remains 0.37 instead of becoming 1.0, and omitted baseline is 0.0. A settings match is necessary but insufficient: compare platform trade-level fee fields, total fees versus actual charged orders, PnL and subsequent NAV/volume. Where trade paths change, do not attribute the entire PnL difference to fees. If the fee is rounded, ignored or ambiguous, do not start cost sensitivity runs; investigate before proceeding.

## Later calibration
If the native fee mechanism is verified, derive version-specific fixed-cost approximations from actual average single-side executed notional times the selected combined percentage fee/slippage cost rate, adjusted for the platform charging unit. Run native cost scenarios for A/B/C. This approximates economic friction only; it does not change order execution prices or reproduce slippage-induced stop changes.
