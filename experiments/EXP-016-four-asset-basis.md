# EXP-016 | Four-asset BTC/ETH spot–futures research (2023–2025)

## Scope and fixed environment

This is a NEW research stream. The uploaded v7 BTC/ETH pairs code is conceptual background, not a dependency. Results from EXP-001–015 on other dates/capital must not be treated as matched controls.

| Setting | Value |
|---|---|
| Assets | BTCUSD spot, BTCUSDM futures/perpetual, ETHUSD spot, ETHUSDM futures/perpetual |
| Start/End | 2023-01-01 / 2025-12-31; API month strings 2023-01 and 2025-12 |
| Interval | 1 day; API dataset 1440; indicator history D |
| Initial Capital | USD 1,000,000 |
| Leverage | 1 |
| Native TradeCost | 0.0005 |
| Short selling | allowShortSell=true |
| Net position mode | isPositionBaseEnv=false |
| Objective | Actual ALGOGENE native Score_Total; report net return, native drawdown and Sharpe |

No 2024 freeze or mandatory train/test split. Each signal uses historical completed daily bars strictly before the execution date. Comparing variants on the full 2023–2025 period constitutes **in-sample optimization**, not independent out-of-sample evidence.

## Model and literature

- Same-underlying spot/perpetual basis: basis(t) = ln(futures(t)/spot(t)). Estimate prior rolling mean and volatility; calculate signal z from last completed day.
- When basis z > entry threshold: long spot, short futures. For z < -entry threshold: short spot, long futures. Exit after convergence or risk/time limit.
- Literature: [Crypto futures basis/momentum risk factors](https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22425); [Fundamentals of Perpetual Futures](https://arxiv.org/abs/2212.06888); [Perpetual Futures and Basis Risk](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5036933).
- Official ALGOGENE marketplace displays all four symbols in a spot/futures spread strategy: https://algogene.com/marketplace/algo/63
- These papers motivate evaluating basis convergence and funding. They do NOT establish any profits or scores for this implementation.

## Registered candidates

- dual-basis-fast: rolling 60 days; entry 1.8; exit 0.15; extreme-z stop 3.5; max holding 20 days; min log-basis gap 0.0025; max rolling basis volatility 0.04.
- dual-basis-selective: rolling 90 days; entry 2.2; exit 0.15; extreme-z stop 3.5; max holding 15 days; min log-basis gap 0.0030; max rolling basis volatility 0.03.
- Both: two independent BTC and ETH spot/perpetual pairs; up to 35% gross NAV per pair, max 70% total target gross; integer contracts conservatively rounded; mismatch cap 5%; two-leg execution confirmation; no second pair entry in same event; account 12% observed peak-to-current drawdown circuit breaker.

## Execution integrity

- Strict timestamp sorting and exact date intersection. No current-day history, stale leg forward fill, or look-ahead.
- Only create a confirmed position after both success callbacks; log ambiguous order state and halt new entries.
- Verify all contract sizes from actual platform metadata and inspect log for unmatched fills, order errors and basis trading skips.
- The run archives platform-native Score_Total, PnL, Sharpe, Max DD, number of trades, setting match checks, source hash and Backtest ID.
- Source: src/four_asset_basis_exp016.py; runner: scripts/algogene_four_asset_run.py; manifest: configs/exp016_four_asset_basis.json.
- Artifact paths: experiments/EXP-016/runs/<run>-attempt-<attempt>-<candidate>.json after workflow execution.
- There are NO legitimate EXP-016 performance results before a collected native response.

## Limitations

Spot/futures listing is not proof that these particular contracts have complete compatible 2023–2025 bar data. Metadata, quantity unit, order execution/callback fields and access permissions require actual checking. Platform TradeCost=0.0005 unit and funding-rate treatment must be verified. If funding is not included in native PnL, the implemented model is spread mean reversion, NOT a fully modeled cash-and-carry strategy. A score selected from this same full-period sample is not an untouched holdout result.
