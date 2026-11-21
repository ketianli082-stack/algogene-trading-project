# V1.4-S4 — Combined cost-aware sizing and exit
## Hypothesis and controls
Combine the unchanged S2 sizing mechanism with the unchanged S3 exit hysteresis. Exclude S1's minimum relative ATR entry gate; prior analysis found it missed important trend winners. Primary comparison S4 vs S2 isolates incremental exit effect under cost-aware sizing; secondary comparisons A and S3 assess interaction. No parameter retuning. Prior results are documented in [cost-aware ablation results](BTC-V1.4-S_cost_aware_results.md).
## Mechanism
Same V1.4-A EMA20/50 crossover, prior price above EMA200, ADX14 > 25, ATR14 calculation from completed historical observations. S2 estimated per-BTC round-trip friction C=2P(0.0005+0.0001+0.02*ATR/P). Size contracts using the minimum of 0.5 NAV/95% available cash cap and 0.005 NAV/((3 ATR+C)*contractSize), floored to four decimals; allocation cap also includes P*contractSize as denominator. Confirm native fill, set fixed 3 ATR stop. S3 checks ATR stop first at each eligible observation; death cross arms timer, compare previous EMA50−EMA20 to cost band using entry ATR and current quote. Exit if gap >= band, invalid data, or still bearish after 6 elapsed hours; cancel timer on recovery. Time cap evaluated on observed quotes, not guaranteed wall-clock execution. Pending order and halt handling unchanged. No cost entry filter. Fees/slippage are hypothetical decision inputs only, not actual costs or changed fills.
```mermaid
flowchart TD
 A[EMA crossover + EMA200 + ADX25] --> B[ATR and estimated friction]
 B --> C[S2 cost-aware risk sizing]
 C --> D[Native market buy and fill-anchored ATR stop]
 D --> E{ATR stop breached?}
 E -- Yes --> F[Native close]
 E -- No --> G{Death cross or armed timer?}
 G -- No --> H[Hold]
 G -- Yes --> I{Trend recovered?}
 I -- Yes --> H
 I -- No --> J{Band reached or timeout or invalid?}
 J -- Yes --> F
 J -- No --> H
 H --> E
```
## Fixed settings and evidence
BTCUSD, 60min, January 2021–December 2024, USD 10000, 1x, long/flat, 0.5% risk budget, 50% NAV allocation cap, 95% cash cap, no TradeCost field, 2025 excluded. Independent native cloud run; offline regression tests before submission. Preserve RISK_SIZE, COST_RISK_SIZE, COST_EXIT_CHECK, ATR_STOP_SET, EXIT_SIGNAL, stats, trades and daily PnL. Native metrics gross of assumed extra friction. Evaluate Score, PnL, Sharpe, Sortino, drawdown magnitude/duration, full matched trades, holding time, exit reasons, risk budget compliance, yearly PnL. If S4 fails to improve materially, retain simpler A/S2 rather than force combination. No claim of net cost savings.
