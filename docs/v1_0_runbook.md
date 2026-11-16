# ALGOGENE Crypto V1.0 runbook

Status date: 2026-11-16 (HKT)

Current execution: use `configs/v1_0_cloud.json` and `docs/research_protocol.md`. The January 2021 cloud test passed, recorded in EXP-004. The original UI procedure below is historical guidance and its old date range is superseded by the research protocol.

## Scope

V1.0 is a deliberately small platform compatibility test, not a performance strategy. It verifies that the selected ALGOGENE account can:

1. subscribe to `BTCUSD`;
2. read three hourly bars through `getHistoricalBar`;
3. submit one `0.01` BTC market buy with a 2% attached stop loss;
4. receive the successful open callback and its `tradeID`;
5. close that trade on the next market event; and
6. stop permanently after that one round trip.

The executable strategy is [`src/algogene_crypto_v1_0.py`](../src/algogene_crypto_v1_0.py). Reference UI settings are in [`configs/v1_0_smoke_test.json`](../configs/v1_0_smoke_test.json).

## API facts checked against ALGOGENE material

- ALGOGENE lists `BTCUSD` historical availability from 2016-01 and supports aggregated intervals including `H`.
- Cloud backtest scripts create `AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)` and call `self.evt.start()`.
- `getHistoricalBar({"instrument": symbol}, count, interval)` returns timestamp-keyed OHLC records using `o`, `h`, `l`, `c` fields in official examples.
- `OrderObject` uses `buysell=1` for buy, `ordertype=0` for market order, and `openclose="open"` for a new trade.
- In an order-based environment, a successful open callback provides `tradeID`; closing uses an `OrderObject` with that `tradeID` and `openclose="close"`.
- ALGOGENE has separately documented that a position-based/netting environment rejects this close form and requires an opposite open order. V1.0 therefore requires **order-based execution with position netting disabled**.

Official references:

- [Market data and BTCUSD availability](https://algogene.com/community/post/48)
- [Historical bars before an algo starts](https://algogene.com/community/post/50)
- [Market, limit and stop order fields](https://algogene.com/community/post/94)
- [Order callback and tradeID example](https://algogene.com/community/post/85)
- [Position-based close limitation](https://algogene.com/community/post/235)
- [REST historical price example](https://algogene.com/community/post/30)

## Risk isolation

- Backtest only: the script imports `AlgoAPI_Backtest`; it contains no REST credentials and no live/real-trade account identifier.
- Exactly one opening order can be created. Submission flags are set before `sendOrder` to prevent duplicate orders even if callbacks are synchronous.
- Long-only, fixed volume `0.01`, no leverage logic, no pyramiding, no retry after a rejected order.
- The opening order carries a 2% stop loss. The expected normal exit is the next market event.
- Missing history, missing OHLC fields, invalid price, or wrong subscription causes no trade.
- Do not run V1.0 in position-netting mode. If the close order is rejected, cancel the backtest and retain the failed log as evidence.

## Platform run procedure

1. In ALGOGENE Backtest, create a new strategy and paste the exact V1.0 script.
2. Use the values in `configs/v1_0_smoke_test.json`; specifically select BTCUSD, hourly data, 2026-11-01 through 2026-11-03, order-based mode, no short selling, and no position netting. If the course account exposes a different historical window, change only the two dates and record the actual values in the experiment log.
3. Confirm the account UI shows the expected contract size and that `0.01` is a valid BTCUSD volume. If either is unclear, do not submit.
4. Submit one backtest. Do not retry silently if it fails.
5. Save the Backtest ID, platform settings, console output, and result export. Remove user ID/API key before adding any artifact to GitHub.
6. Update `experiments/EXP-001-v1.0-smoke.md` and `experiments/experiment_log.csv` with the literal outcome: `PASS`, `FAIL`, or `NOT RUN`.

Expected log sequence for a valid run:

```text
V1.0_HISTORY_OK
V1.0_OPEN_SUBMITTED
V1.0_OPEN_FILLED
V1.0_CLOSE_SUBMITTED
V1.0_ROUND_TRIP_COMPLETE
```

## GitHub Actions and secrets

Normal CI never receives ALGOGENE secrets and only runs local fake-platform tests. The separate manual workflow `ALGOGENE read-only history check` calls only `/rest/v1/history_price` and expects repository or environment secrets named:

- `ALGOGENE_USER_ID`
- `ALGOGENE_API_KEY`

GitHub does not expose secret values, and the available repository connection did not expose a safe secret-name listing. Their presence is therefore **not verified in this experiment**. Missing secrets produce `NOT RUN`; no key should ever be pasted into an issue, PR, log, or tracked file.

Correction (2026-11-16): the official OpenAPI specification at https://algogene.com/apidoc.yaml does provide `POST /run_backtest`, `GET /get_current_tasks`, and `GET /task_status`. The earlier statement that no cloud submission API was established was incorrect. `scripts/algogene_cloud_backtest.py` now submits once and monitors the returned task. The cloud workflow uses GitHub Secrets and records only credential-free evidence. Its settings are `configs/v1_0_cloud.json`; API dates use YYYY-MM, unlike the earlier proposed UI day range. No live order endpoint is used.
