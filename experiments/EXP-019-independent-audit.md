# EXP-019 — Independent audit of EXP-018 native evidence (frozen baseline)

Audit date: 2026-11-19. This document reviews **immutable** historical archives and original strategy source. It does not use EXP-018's displayed score as a substitute for execution evidence.

## Reproducible sources

- EXP-018 native archive: [44511783153-attempt-1-final.json](EXP-018/runs/44511783153-attempt-1-final.json), Backtest ID **20261119_111256_911463**
- Original 2023-2025 EXP-018 cloud source: [four_asset_h1_exp018.py](../src/four_asset_h1_exp018.py), submitted SHA-256 **6088dbe6abb48892d7e6de8bafdeb01b65a0e3f08178eb27927d5eb3cfed8b0f**
- Earlier EXP-016 underlying May 2024 matching trade ledger: [44476933626-attempt-1-final.json](EXP-016/runs/44476933626-attempt-1-final.json); note EXP-016 was flagged INVALID_REVIEW **only because requested native cost 0.0005 disagreed with actual cost 1.0**; the native fills/quantities and prices remain archived evidence.
- Independent reproducible Python reconciliation: [audit_exp018_independent.py](../scripts/audit_exp018_independent.py). Its assertions run from [test_exp019_audit.py](../tests/test_exp019_audit.py) as part of CI.
- Public independent ETH price references: [Trader Villa historical ETHUSDT daily May 2024](https://tradervilla.com/public/coin/ethusdt/month-summary/may-2024) and [Grayscale research May 2024](https://research.grayscale.com/market-commentary/may-2024-a-breakthrough-for-spot-ethereum-etfs).

## A. Verified native configuration and performance

EXP-018 platform-native result status **COLLECTED**, all effective settings match: 2023-01 to 2025-12; 4 instruments (BTCUSD, BTCUSDM, ETHUSD, ETHUSDM), UTC-like H1 callbacks, dataset=60, initial USD 1,000,000, leverage=1, risk_free=0, allowShortSell=true, fixed TradeCost=USD 1, not percentage.

Native Score_Total **73.21526135948776**, total net PnL **USD +45,220.00095329**, AnnualSharpe **1.9955583254**, maxDrawdown_pct **0.00589915235 (0.5899%)**, TradeCnt **1,704**, WinRate **0.6057441**, profit_factor **1.47609**, AvgDrawdownDuration **18.8143**, maxDrawdownDuration **121**.

Independent daily-PnL archive contains **1,095 daily rows**, from 2023-01-01 through **2025-12-30**, not an independently dated 2025-12-31 row (although native log runs to 2025-12-31 23:59:59). The last cumulative USD 45,220.00 matches native 45,220.000953 to cents; accumulated asset PnL sums to the same amount:

| Combined leg sources | Cumulative USD PnL |
|---|---:|
| BTCUSD | +11,140.32 |
| BTCUSDM | +13,749.93 |
| ETHUSD | -4,522.61 |
| ETHUSDM | +24,852.36 |
| **Total** | **+45,220.00** |

Annual change of daily cumulative PnL: **2023 +14,388.34**, **2024 +18,564.08**, **2025 +12,267.58**. The 2025 **incremental** figure comes from the original 2023-2025 run, not from a newly reset 2025-only backtest and is not a standalone Score_Total.

The independently reconstructed equity path from **USD 1,000,000 + daily cumulative PL** gives max observed close-to-close peak-to-trough drawdown **0.0058991488**, agreeing with native **0.0058991523** to 1e-6. Peak **2024-04-27, USD 1,026,103.97**, trough **2024-05-20, USD 1,020,050.83**, peak-to-trough loss **USD 6,053.14**. Native average drawdown duration and Sharpe themselves were not independently reconstructed from an intrahour full equity feed; they remain native estimates.

## B. Independently reconstructed real fills and fees

The first **100** returned transaction records contain **50 unique native trade IDs**, each with one opening and one closing event: **50 completed instrument legs = 25 completed two-leg BTC pairs**, spanning 2023-01-09 through 2023-05-14.

For each ID, independent signed profit = buysell × volume × (close_price − open_price) plus archived native per-event fees. Each opening charged **−$1**, each closing **$0**. The 25 pairs' **USD 4,533.76129972 gross PnL − USD 50 fees = USD 4,483.76129972 net**. Native cumulative daily PL on 2023-05-14 = **USD 4,483.76**. The match is exact to the cent. This directly validates **this 25-pair prefix**, native fee handling and signed PnL; do **not** extrapolate to unobserved fills.

Platform reports **TradeCnt=1,704** but API only returned **100** rows; console logs contain only latest 2,000 messages, starting 2025-02-25. They do not constitute a complete 2023-2025 fill ledger. A complete independent reconciliation of all 1,704 events is **not possible** with these two returned endpoints alone. TradeCnt of 1,704 is consistent with (but does not itself prove) ~426 completed two-leg pairs and ~852 native opening-leg $1 fees.

## C. Priority risk: May 20, 2024 ETH price-clock/source integrity

The native EXP-018 daily book shows **−$4,006.31** on 2024-05-20, the worst single day of the experiment. Direct component change:

| Leg | Daily PnL delta |
|---|---:|
| BTCUSD | +$93.31 |
| BTCUSDM | +$594.08 |
| ETHUSD | +$149.14 |
| ETHUSDM | **−$4,842.84** |
| **Total** | **−$4,006.31** |

This is also **the full experiment's peak-to-trough max drawdown date**.

A separate earlier native EXP-016 archive captures a complete exact May 18–20 two-leg trade, with **both closing events timestamped 2024-05-20 00:00:00**: ETHUSD spot exit **$3,071.88** (58 units), ETHUSDM future exit **$3,666.480396** (56 units). Entered May 18 at ETHUSD **$3,100.21** and ETHUSDM **$3,121.699977**. Independently signed combined gross loss **−$32,150.843464**. Apparent end-event futures-versus-spot premium **19.36%**. These are native prices and fees from EXP-016, **not** the missing EXP-018 May 2024 fill-level history.

External **May 20 2024 ETH/USDT daily OHLC** from Trader Villa: open about **$3,071.20**, high **$3,694**, low **$3,047.67**, close **$3,661.78**. In research from Grayscale, ETH jumped approximately **17% over five hours** after unexpected ETF approval expectations on that day. The EXP-016 spot exit resembles the public day's opening price while future exit resembles the public day's closing price; this is a **red flag for execution timestamps, price sampling and/or different data-source session conventions**, not proof of a true tradeable 19% arbitrage spread.

**Limit**: without the raw same-venue or normalized 1-minute/H1 bid/ask and source/exchange identifiers from both ALGOGENE contracts on that date, it is **not yet proven** that prices were timestamp-misaligned; contract type FUT and shared printed timestamp do not establish identical executable market time. A counterfactual "replace spot fill with close" would be imaginary PnL and **must not** be cited as a recovered actual strategy gain. EXP-018 uses H1 bars and risk filters, so its execution cannot be equated mechanically to EXP-016's daily trades. EXP-018 still lost $4,006.31 on the same shock date, therefore risk remains material.

## D. Source-code audit (original EXP-018, not altered by EXP-019)

**What does guard against lookahead:**
- Every history K-line is accepted only when \`timestamp < current_event_timestamp\` in \`_read_hours\`.
- H4 only from **four contiguous completed H1 closes**, and H24 from **24 contiguous H1 closes**; no platform H4 data request.
- The H4 \`_signal\` normalizer trains on the 42 H4 candles **before** the most recent completed H4 candle. At event hour UTC 01/05/09/13/17/21, \`recent=now−1h\` and signal \`end==recent\` is enforced.
- This establishes a software-level no-lookahead property **conditional on honest and correctly timestamped external price data**.

**Important weaknesses to track (do not silently fix the source before window comparison):**
1. \`_history_pair\` computes a \`quote_gap\` by comparing the recent H1 pair close ratio to the synthesized H4 pair close ratio whose final closes are *the same two H1 observations*. Therefore it is **identically ~zero by construction**, not an independent check that spot and future quotes were economically synchronized. The separate **live-vs-H1** basis and per-leg jump filters only act on *new entries*; they do not guarantee historical clock integrity.
2. \`_time\` drops explicit timezone offset information without normalizing to UTC; a future heterogeneous data feed could corrupt alignment. Source comments assume consistent ALGOGENE backtest timezone; no platform-wide proof for all feeds.
3. Pair sizing assumes contractSize=1 and target lot granularity=0.01; native contract metadata confirms contractSize=1 for the four symbols, and sampled fractional volumes were accepted, but actual venue short borrow, futures expiries and financing/funding costs remain unspecified.
4. Stops operate on H1 event snapshots and can be far exceeded by intra-hour moves/gaps. A pair has two independently executed legs, not an exchange-atomic hedge.
5. Risk-free=0 and native fee fixed USD1 are controlled **backtest conventions**, not sourced broker costs. The backtest does not establish live slippage/funding/borrow/roll behavior.

## E. What EXP-019 checks and what it cannot

EXP-019 retains the **identical submitted EXP-018 strategy SHA-256**, same four instruments, \$1 native fee, leverage=1, initial \$1,000,000; only changes native \`StartDate\` (and strategyName for audit) to obtain **2025-01→2025-12 standalone** and **2021-01→2025-12 expanded** runs, each with **fresh** NAV. The 2025 standalone run is a *reset-window robustness test*, not an untouched out-of-sample evaluation, because 2025 was already used in EXP-018 model selection. The 2021–2025 window is also an in-sample robustness extension, not a live-predictive proof. Cross-window native Score_Total may depend on horizon length, turnover and market regime; compare component scores and PnL alongside Score_Total.

**Next forensic verification** (not claimed completed): collect the **2024-05-20 H1/1min contract-level quotes for ETHUSD and ETHUSDM from ALGOGENE**, retaining source timestamp, timezone, venue, OHLC, bid/ask, order fill time and product specs. Check both synchronized calendar time and consistency against independent ETH spot OHLC data, then decide whether the 2024 event is a legitimate unhedged basis gap, a platform price-source difference or a data clock defect. Do not tune thresholds around the flagged date until data integrity is checked.
