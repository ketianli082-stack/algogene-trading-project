# BTC strategy research: V1.0–V1.1 results and V1.2-B rationale

Development universe: BTCUSD, native ALGOGENE 60-minute, January 2021–December 2024, USD 10,000, leverage 1, long/flat, 50% target allocation. No explicit fixed TradeCost field. The 2025 data must not enter this research iteration; prior projects may have already exposed that year, so describe it as a reserved evaluation period for this project rather than guaranteed untouched across all past research.

## 1. Native platform comparison

| Version | Score | PnL USD | Annual Sharpe | Max DD | Native WinRate | Profit factor | Trade records | Evidence |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| V1.0 EMA20/50 |42.42|6449.71|0.573|34.88%|44.58%|1.260|649|[Run 44764052586](../../actions/runs/44764052586)|
| V1.1-A ADX20 |32.01|766.03|0.1625|31.08%|44.22%|1.057|355|[Run 44770516390](../../actions/runs/44770516390)|
| V1.1-B ADX25 |54.26|6234.46|0.861|13.03%|48.66%|1.785|177|[Run 44774946361](../../actions/runs/44774946361)|
| V1.1-C ADX30 |50.88|2918.88|0.731|8.63%|48.48%|2.122|85|[Run 44776334195](../../actions/runs/44776334195)|

ADX25 is the selected development comparator, not an independently validated optimum. ADX30 is the low-drawdown comparator. These figures transcribe the preceding analysis in the project conversation; original evidence is the linked Actions artifact. No new independent data extraction is claimed in this documentation commit.

## 2. Annual PnL changes (USD)

| Year | A | B | C |
|---|---:|---:|---:|
|2021|1128.60|2575.18|315.80|
|2022|-2283.65|-172.99|364.72|
|2023|1608.62|3525.49|1952.97|
|2024|312.46|306.78|285.39|

Computed in previous analysis from year-end differences in daily cumulative PnL (2024 last available dated observation Dec 30). Rounding may cause small differences. These are dollar changes, not standalone yearly compounded returns. B gains concentrate in 2021 and 2023; 2024 improvement modest. 2024 has already influenced model selection; it is not a clean internal holdout.

## 3. V1.1-B completed-trade diagnosis

177 native records = 89 opens + 88 closes (one residual position). The preceding paired-trade analysis reported 29 winning / 59 losing round trips, 32.95% realized win rate (not the native 48.66%), winning PnL 14,173.16, losing PnL -7,938.70, net 6,234.46; average win 488.73, average loss -134.55, payoff 3.63:1.

| Holding time | Count | Losers | PnL USD |
|---|---:|---:|---:|
|0–12h|15|14|-1592.06|
|12–24h|13|13|-2328.80|
|24–48h|20|19|-2761.88|
|48–96h|18|12|-659.70|
|96h+|22|1|13576.91|

48 trades held at most 48h, including 46 losers. Mean winning duration 146.14h versus losing 31.15h. Duration is ex-post, not a permissible entry predictor; do not force all trades to last four days.

### Ten largest losses reported in prior analysis

| Entry date | Open price | Close price | Hours | PnL USD |
|---|---:|---:|---:|---:|
|2021-11-25|57858|54378|31|-390.84|
|2023-11-15|37526|35918|25|-352.81|
|2024-04-11|71032|68076|39|-352.14|
|2022-04-26|40618|38657|19|-326.46|
|2024-05-10|62867|60382|15|-322.32|
|2022-05-19|30308|28915|22|-300.07|
|2024-06-12|69644|67300|12|-278.48|
|2024-04-30|63657|61633|6|-263.52|
|2021-08-04|39889|37957|14|-262.93|
|2024-12-24|98504|95704|44|-233.76|

Total -3,083.34 (roughly 38.8% of gross losses). Observed execution-to-execution losses do not establish intrabar adverse excursion or hypothetical stop fill. The largest loss followed a roughly 6% price decline over 31h. Test whether a volatility-scaled exit reduces the losses without sacrificing long trends.

### Profit concentration
Top five trades: 2023-10-15 (290h) +1794.10; 2021-09-30 (307h) +1619.75; 2024-02-26 (199h) +1502.44; 2023-01-06 (289h) +1396.92; 2021-07-21 (217h) +1131.55. Total +7444.76 (52.5% of gross winning PnL); excluding them gives approximately -1210.30. This is a retrospective concentration stress test, not a forecast. Prefer fixed stops over overly tight take-profit/trailing rules initially.

### Drawdown and score
Reported daily peak 2022-03-29 NAV 13868.00, trough 2022-10-03 NAV 12060.98, difference -1807.02 (13.03%). 2022: 28 closed trades, 21 losing. Reported mean drawdown duration 92.995 days; longest 301 days. Component scores previously reported: R² 89.07; max DD 86.97; Sharpe 70.28; win rate 48.19; average DD duration 24.39; trades/day 6.63. Improve meaningful risk-adjusted performance and drawdown duration rather than manufacture trades to raise frequency scores.

## 4. Static percentage trading-cost sensitivity

Prior paired-trade turnover estimate USD 1,199,806.87. Holding fills and quantities fixed, single-side fee rate applied to both buy and sell notional:

| Fee | Total cost USD | Net PnL USD | Net return |
|---|---:|---:|---:|
|0%|0|6234.46|62.34%|
|0.02%|239.96|5994.50|59.95%|
|0.05%|599.90|5634.56|56.35%|
|0.10%|1199.81|5034.65|50.35%|
|0.20%|2399.61|3834.85|38.35%|

No compounding feedback, slippage or unmatched final opening leg included. Platform native metrics are gross relative to these hypothetical percentage fees. Never set fixed TradeCost as a substitute; omit the field entirely.

## 5. Selected V1.2-B hypothesis
Keep V1.1-B EMA20/50 + ADX25 and 50% sizing unchanged. Calculate Wilder ATR14 from the same completed OHLC history at entry; set fixed stop at confirmed actual fill minus 3 ATR. On hourly observed quote at/below stop, send a market close for the trade ID; bearish EMA cross also closes. No guaranteed stop-level execution or intrabar stop claim. Do not reenter until a new valid upward crossover. Log ATR anchor, stop-trigger events, order failures. Compare score, Sharpe, DD, PnL, duration, real closed-trade losses and retention of major winning trends against B. Verify nonzero fills, effective period and costs before accepting results. No 2025 data. Results pending.
