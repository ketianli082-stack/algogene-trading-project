# EXP-013 — controlled H1 cost gate versus H4 signals

Registered 2026-11-17. **Development 2021-01 to 2023-12 only; new results NOT RUN at registration.** 2024 Validation and 2025 Final Test remain closed.

Reference EXP-010 H1 native TradeCost=1.0: TotalPnL -34.0512 USD, AnnualSharpe -0.1099, TradeCnt 206. All five EXP-012 candidates were negative after the same fixed-cost stress. The cost setting is not a real broker fee quote.

Shared: BTCUSD, H1 event dataset 60, initial USD 10000, leverage 1, long-entry-only code, order-based, native TradeCost 1.0, previous completed bars, EMA200/Donchian20 entry and Donchian10/EMA exit, 24-period EMA slope, ATR14 2x native stop and volatility sizing, 0.01 quantity model increment, 0.1% stop-distance budget, 20% notional and 0.02 lot caps.

* **h1-control:** repaired reference with no entry fee filter, hourly indicators.
* **h1-cost-gate:** ONLY additional entry permission: 1 USD fixed fee / (3*ATR14*quantity potential gross price-move proxy) must be <=0.10. This is not a prediction, stop, or take-profit order.
* **h4-control:** change only signal interval H to H4 and decisions to four-hour boundaries; native H4 historical candles queried on allowed H1 event feed. EMA200 and 24-bar slope now refer to H4 bars; no claim that dataset=240 is supported.

The 2023 terminal year is a registered code parameter. End-of-period liquidation remains 2023-12-31 22:00 (H1) or 16:00 (H4). Rejected, mismatched or overdue callbacks halt new orders and require manual verification of actual positions; never blindly retry or assume a successful close. Stops can slip.

GitHub Actions performs offline tests before serial ALGOGENE cloud submissions. Each candidate's exact source SHA, settings, native Backtest ID, task ID, platform metrics and original responses are committed immutably under experiments/EXP-013/runs, with a fallback Actions artifact. The workflow refuses retries, unknown/pending tasks, and any 2024/2025 dates; all failures retained. Transaction-history API results can be truncated and should not be described as a complete trade ledger. Score_Total is secondary to native after-cost P/L, Sharpe, drawdown and trading activity.
