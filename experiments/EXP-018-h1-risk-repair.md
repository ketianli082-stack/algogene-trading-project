# EXP-018 — H1 risk repair from EXP-017 native score and loss attribution

Registration: 2026-11-19. **One** frozen candidate `h1-risk-repair`. The base EXP-017 source and its native response are kept unchanged. This is an H1/H4/H24 **risk-first** bundle, NOT an isolated single-factor test; do not attribute any gain to a particular change without a follow-up ablation.

## Fixed comparable setup

BTCUSD, BTCUSDM, ETHUSD, ETHUSDM; ALGOGENE `dataset=60`, historical `interval="H"` exclusively, synthesize H4/H24 from fully completed H1 OHLC; 2023-01 through 2025-12; USD 1,000,000 initial NAV; leverage 1; `allowShortSell=true`; `isPositionBaseEnv=false`; `risk_free=0`; **native fixed `TradeCost=1` USD per opening leg**. No direct H4 interval requests. Full 2023–2025 evaluation is in-sample.

## EXP-017 native baseline — confirmed completed

- GitHub Actions run: https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/44490829480
- Backtest ID: `20261119_085550_523441`
- Evidence: `experiments/EXP-017/runs/44490829480-attempt-1-final.json`
- Platform `status=COLLECTED`, all effective settings (including fixed fee $1) matched.
- Native `Score_Total=50.29294233373533`; `TotalPnL=-29691.01706793008`; `AnnualSharpe=-0.44803789506366226`; `maxDrawdown_pct=0.039939577378023894`; `TradeCnt=2700`, `profit_factor=0.94204049`.
- Six scores: `score_AnnualSharpe=38.98274`, `score_AvgDrawdownDuration=5.31402`, `score_Rsquare=60.84340`, `score_TradePerDay=54.12289`, `score_WinRate=46.48856`, `score_maxDrawdown_pct=96.00604`.
- Raw `AvgDrawdownDuration=534.5441176470588`, `maxDrawdownDuration=1078`. Score Total increased 6.13 versus the earlier daily result, but Sharpe worsened; neither result is a profitable native trading strategy.

## Full daily PnL facts and limits

From all 1,095 days of native PnL, absolute largest negative day was **2024-08-08, -$8,504.27**; other severe days: **2024-08-05, -$8,124.73**; **2024-05-20, -$5,303.16**; and **2025-10-17, -$4,507.07**. Annual PnL increments: 2023 `-$7,366.88`; 2024 `-$18,035.82`; 2025 `-$4,288.32`. Cumulative combined BTC spot/futures `-$29,185.76`; combined ETH `-$505.27`. BTC, not ETH, dominated EXP-017 losses.

**Important record limitation:** ALGOGENE console returns only the latest 2,000 lines (starting 2025-06-13 here), and REST `strategy_trade` returns 100 entries, despite `TradeCnt=2700`. Thus the complete 2024 per-pair ledger is not available from these endpoints; do not claim to know the worst trade across all years. Within the **165 complete pairs in the retained 2025 console**, the worst pair was ETH on 2025-10-17 05:00–08:00, `-$4,505.07` gross: spot 3912.40→3756.19 while futures 3915.05→3999.20, producing an exit spread of ~6.3%. Hourly stops may slip badly if venue prices diverge or have mismatched sources.

The log records include `BASIS_STOP` and `H4_REVERT`, but their totals are **not** three-year counts due to trimming. Divergent market data and execution venue / contract expiry remain unverified.

## Controlled risk improvement hypothesis

We hold the H4 robust z signal window at 42 H4 candles, entry z 2.0, exit z 0.4, H24 regime logic and single-candidate native workflow constant. Only the risk/execution layer is revised.

| Parameter / decision | EXP-017 | EXP-018 |
|---|---|---|
| Gross NAV per pair | 15% | **10%** |
| Basis adverse-stop | 1.2% log basis | **0.75%** log basis |
| Max holding | 48h | **36h** |
| Max entry absolute log basis | 3.5% | **2.5%** |
| H1 current-vs-past basis discontinuity | 2.5% | **1.0%** |
| H24 daily spot log move veto | 10% | **6%** |
| Normal post-exit cooldown | 12h | **18h** |
| Post-basis-stop cooldown | 12h | **48h** |
| Individual H1 leg jump veto | none | **4%** each spot/future |
| Minimum forecast potential gross less $2 native entry fee | none | **$75** |
| H1 reversion exit | H4-only | **evaluate every complete H1** against latest H4 median and scale |
| H4/H24 source | H1 aggregation | unchanged |
| Native fixed trade fee | $1 per opening leg | unchanged |

The basis stop is an event-based instruction, not a guaranteed fill. Narrower risk budgets can reduce loss size mechanically but may also reduce profitable trades and the trade frequency score. The `min_expected_profit_usd` filter is an **edge proxy**, not a calibrated return forecast; it cannot account for slippage, funding, borrow or unmodeled fees.

## What proves improvement?

Compare the *real* native Score_Total against **50.29294**, not a hypothetical return. Require authentic task ID, settled status, four compatible symbols, fixed `TradeCost=1`, nonzero matched pairs, and no strategy HALT. Report all six score components, total net PnL, Sharpe, max drawdown, average and max drawdown duration, executed trade count, profit factor, and 2024/2025 negative days.

A higher Score with worse Sharpe/PnL is not automatically an economically superior strategy. Next steps, if needed, should be one-variable ablations (H1 earlier exit versus entry quality gate versus exposure cap), followed by chronological rolling evaluation. No funding curve or guarantee of synchronized executable venue prices has been added.

Source: `src/four_asset_h1_exp018.py`; test: `tests/test_exp018_risk_controls.py`; runner: `scripts/algogene_h1_exp018_run.py`; archive: `scripts/archive_exp018.py`; manifest: `configs/exp018_h1_risk.json`.
