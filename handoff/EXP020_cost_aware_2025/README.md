# EXP-020 cost-aware-2025 | Developer handoff

**Purpose.** Frozen, exact submitted ALGOGENE strategy for iterative research, not EXP-020Z. Full Chinese documentation: `README_中文交接说明.md` in the source folder.

**Read first:** `strategy_exp020_submitted.py` is exactly what was uploaded to ALGOGENE (SHA-256 `4c2ff67079b9a2feb3d96df7d6ca05c5c30e67fb4ea914deed5b55036a330b6a`). `src/four_asset_h1_exp020.py` is the original source template; `scripts/algogene_exp020_run.py` substitutes the parameter dict before cloud submission.

## Strategy

Four instruments: BTCUSD (spot), BTCUSDM (future), ETHUSD (spot), ETHUSDM (future). Use H1 completed bars to synthesize continuous H4 and H24 frames; never read future bars. Trade log futures/spot basis mean reversion, robust historical H4 median/MAD z-score 2.0, 42-candle lookback. Expensive future -> long spot/short future, cheap future -> short spot/long future. Gross pair 10% NAV, each leg ~5%, 1x leverage. Dynamic exit at H1 reversion, adverse basis 0.75% log threshold or maximum 36 hours. 18-hour normal cooldown; 48-hour stop cooldown. H24 regime, recent 5-hour H1 basis shocks, live-vs-closed-H1 divergence and individual leg jumps veto new entries.

## Model fees and real execution limit

`fee_rate=0.0005` means **0.05% of actual filled notional at every open and close**. The strategy books `price * volume * contractSize * 0.0005` on each success fill, deducts shadow fees from its sizing/risk NAV and estimates all four round-trip fill costs in the entry filter. This DOES NOT change native ALGOGENE `TradeCost`. Original submission requested native `TradeCost=0`, but the platform returned **effective 1.0 USD per opening leg**, invalidating the zero-native-fee research assumption. No fee reimbursement was implemented in this version. A handoff engineer must not present the native Score_Total as percent-fee-adjusted.

### Verified 2025 historical result

- Run: https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44672882148
- Backtest ID: `20261120_042009_619119`; platform evaluation status `INVALID_REVIEW` due exclusively to fee mismatch.
- Native platform score **76.866265**; native PnL **+$3,413.7961** (already deducting native fixed USD1 opening fees). These are NOT economically fee-adjusted figures.
- 84 native fill events = 21 two-leg pairs; 19 H1_REVERT and 2 BASIS_STOP exits.
- Independent actual-fill gross PnL **+$3,455.7961**; accumulated 0.05% modeled commission **$2,087.971601**; **gross minus only percentage fees = +$1,367.824499**. This is an offline economic sensitivity number, NOT an ALGOGENE official score.
- The native PnL - 0.05% = $1,325.824499 shown in original audit JSON DOUBLE-COUNTS the forced USD1 native opening fees. Do not use it as the economic profit figure.
- With native fees >0, the shadow risk NAV does not reflect a pure 0.05% model; treat the run as experimental evidence only.

## Layout and reproduction

`strategy_exp020_submitted.py`: exact submitted version. For unit tests and runner use the `src/`, `configs/`, `scripts/`, `tests/`, `.github/workflows/` folder layout preserved in this bundle.

Locally: `python -m compileall -q src scripts tests` and `python -m unittest discover -s tests -v`. Strategy runtime imports ALGOGENE's `AlgoAPI`, unavailable outside the platform; tests use a stub.

To run cloud backtests in your OWN repo, configure GitHub Secrets `ALGOGENE_USER_ID`, `ALGOGENE_API_KEY`, `GITHUB_TOKEN`; update `scripts/archive_exp020.py`'s hard-coded `REPO`/`BRANCH`, workflow branch, experiment labels/output and trigger. Never commit credentials. Do NOT resubmit the frozen original experiment automatically.

## Suggested isolated iterations

1. Validate synchronized price sources and times (notably 2024-05-20 ETH, 2025-01-20 ETH, 2025-04-21 BTC).
2. Resolve actual platform fee constraints or switch to a backtester with native percentage fees; do not silently "refund" or disguise native fixed fees.
3. Ablate recent-basis jump/range filters independently, as the cost-aware 2025 model traded only 21 pairs and its trading-frequency score was 1.70/100.
4. Separate BTC and ETH risk/edge thresholds with explicit holdout data and native-vs-economic reconciliation.
5. Add slippage, borrow, funding, execution latency and independent time alignment tests; always persist SHA, params, effective settings and actual matched fills.

Historical archive: `evidence/algogene_exp020_native_final.json`. Strategy is academic research; no claim of profitable live execution.
