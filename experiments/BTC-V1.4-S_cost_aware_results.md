# V1.4-S1/S2/S3 成本感知消融结果（2021–2024）
原始 ALGOGENE evidence.json 已复核：A run 44873097691 / artifact 14695151074；S1 44876693490 / 14696142412；S2 44877488082 / 14697096797；S3 44883333959 / 14698953143。均为 success、COLLECTED，平台有效 TradeCost=0。成本仅影响决策，不是成本后净收益。Trade API 对 A/S2/S3 仅返回100条记录，故完整成交配对使用 INFO opened/closed 日志，以 tradeID 匹配，contractSize=1；最后各有一笔未平仓，不计入完整交易胜率。年度数据为 daily_pl TotalPL 年末差值。
| 指标 | A | S1 | S2 | S3 |
|---|---:|---:|---:|---:|
| Score |57.347774|48.142995|57.354357|56.543643|
| PnL USD |3059.174925|1088.487771|2789.782737|3139.591457|
| Sharpe |1.165426|0.786664|1.159930|1.118056|
| Sortino |2.694734|1.743953|2.659391|2.584190|
| max DD % |3.4350|2.5784|3.1942|3.9653|
| Annual volatility % |4.0703|2.3281|3.7656|4.3491|
| PF |3.187898|2.222545|3.132287|2.970763|
| platform win rate % |49.2188|47.3958|49.2188|47.5524|
| complete trade wins/losses |23/40|16/32|23/40|23/39|
| opens/closes |64/63|49/48|64/63|63/62|
| max closed loss USD |-111.62|-69.83|-100.80|-111.80|
| avg DD days |86.85|142.46|86.85|95.69|
| max DD days |287|416|287|287|
| avg holding days (platform) |3.0358|2.9337|3.0358|3.5450|
| 2021 PnL |849.91|892.71|809.27|940.52|
| 2022 PnL |249.38|229.13|228.97|183.40|
| 2023 PnL |1278.46|214.07|1143.11|1246.43|
| 2024 PnL |681.42|-247.42|608.43|769.24|

S1: 64 COST_ENTRY_CHECK, 49 pass, 15 reject. Match by entry timestamp: 15 excluded completed A trades, 7 winners/8 losers, sum +1991.02 USD on original A sizes. Largest missed winners 2023-01-06 20:00 +1111.81; 2024-02-26 17:00 +698.15. S1 has no new completed entry timestamps relative to A. Filter is algebraically a minimum relative ATR gate; results do not validate a true cost forecast. Reject S1 at current parameters.
S2: Same completed entry timestamps as A, same 54 EMA and 9 ATR exits; 64 COST_RISK_SIZE logs, mean combined planned risk 0.497565% NAV, min 0.393533%, max 0.499990%. Score +0.006583, profit -269.39; marginal score improvement, not evidence of prediction advantage. Retain as cost-aware candidate; A remains strong comparison.
S3: 262 COST_EXIT_CHECK records, WAIT 204, RECOVERED 9, EXIT_BAND 40, EXIT_TIMEOUT 9. Actual exits 40 band/9 timeout/13 ATR, vs A 54 EMA/9 ATR. Gross PnL +80.42, Sharpe and score lower, drawdown higher; only one fewer round trip. Do not infer actual cost savings. Retain only as optional combination hypothesis, not default.
Next: do not blindly combine all three. Candidate S4 = S2+S3 without S1, isolated incremental test against S2 (and A/S3). S4 not yet submitted. If primarily maximizing development score, select S2 provisionally, compare against A and S4 before freezing; no 2025 use. 
