# EXP-020 — Fill-notional 0.05% transaction costs + abnormal-basis pre-entry filters

## Research intent

Build on **EXP-018**, which had native `Score_Total=73.2152613595` and native `TotalPnL=+$45,220.00` on 2023–2025, but only +$5,812.90 and score 63.7402 in 2025 standalone. The original 2025 run saw large losses on 2025-01-20 (-$2,080.64 paired ETH) and 2025-04-21 (-$1,654.42 paired BTC), both from basis stops. Experiment uses a new version instead of editing the baseline.

## Transaction-cost protocol

- **Model rate: 0.0005 = 0.05% of every confirmed filled notional**.
- Spot/future; long/short; opening/closing: same fee `filled_price × filled_volume × contractSize × 0.0005` on **each** callback.
- Native ALGOGENE `TradeCost=0` (no misleading fixed fee). The platform `Score_Total` remains a **fee-unadjusted diagnostic** and must NOT be sold as 0.05% net.
- Original platform gross PnL minus strategy `COST_FINAL` cumulative fees is the **cash-adjusted net PnL**. Strategy also subtracts accrued fees from NAV/balance before sizing and 8% account drawdown control.
- The `COST_FINAL` terminal log records cumulative fees, actual fill-level reconstructed gross and net, fee event count, and fees by year, so the count remains available even when platform retains only the last 2,000 console messages.
- Pre-entry screen estimates both legs' opening and closing fees, i.e., **four fees**, and requires at least $50 estimated net room beyond those costs. This is a model expectation, not guaranteed net profit.
- This is still an **optimistic** transaction-cost assumption. Slippage, bid–ask, spot short borrow, futures funding/roll/carry are not included.

## Focused source repairs

1. Remove EXP-018's tautological H1-vs-H4 latest close comparison. Add `_recent_basis_risk` from five *contiguous completed* matched H1 close pairs; reject >0.6% maximum one-hour log-basis jump or >1.2% four-hour log-basis range before entry.
2. Tighten live-to-completed-H1 basis divergence entry veto from 1.0% to 0.6%; per-leg H1 price shock veto from 4% to 3%.
3. Ensure the directional entry edge exists at the **current event quote** rather than just at the stale H4 historical signal.
4. Normalize explicit offset-aware timestamps to UTC.
5. Preserve stop limit, 36-hour holding cap, gross pair allocation, and 18/48-hour post-exit cooldown; do not optimize all thresholds simultaneously.

## Experiment design

The first guarded native evaluation is **2025-01 to 2025-12**, four same contracts, 60-minute data, starting $1,000,000, leverage 1, `risk_free=0`, native `TradeCost=0`. The original EXP-018 2025 run is a **historical fee-$1 comparator**, not a fair fee-adjusted head-to-head until a corrected fixed strategy is re-evaluated under the same 0.05% model.

Once the 2025 native and cost-audited result is verified, compare the *same frozen EXP-020 source* over 2023–2025 and 2021–2025. It is not independent OOS; all windows were already reviewed in the research process.

## Evidence, integrity and status

- New strategy: [src/four_asset_h1_exp020.py](../src/four_asset_h1_exp020.py)
- Parameter and real fee protocol: [configs/exp020_percent_fee.json](../configs/exp020_percent_fee.json)
- Offline regression tests: [tests/test_exp020_percent_cost.py](../tests/test_exp020_percent_cost.py) and [tests/test_exp020_run.py](../tests/test_exp020_run.py)
- Guarded native runner: [scripts/algogene_exp020_run.py](../scripts/algogene_exp020_run.py)
- Actions workflow: [algogene-exp020.yml](../.github/workflows/algogene-exp020.yml)
- First CI-validated run: [Actions #44672882148](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44672882148)

**Do not fill in Score_Total or percentage-fee-adjusted PnL before the native result is collected and a terminal COST_FINAL record exists.**
