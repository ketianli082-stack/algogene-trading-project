# EXP-003 — V1.0 real ALGOGENE cloud result

Date: 2026-11-16 HKT. Submitted code commit: `43a130b3f1ffa3b43777e0f7692cceab51832b00`.

Backtest ID: `20261116_101506_803491`. Task ID: `1794824106803491`.

## Verified evidence

- [Cloud submission, attempt 2](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/43846452183/attempts/2): both credentials available; submission accepted; task status DONE. Subsequent stats query hit HTTP 400 rate limit.
- [Platform log retrieval](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/43847595092): real log confirmed history read and buy/close round trip. Stats query returned `Exceed maximum access count! Please retry after 60 seconds!`.
- [Separate performance retrieval](https://github.com/ketianli082-stack/algogene-trading-project/actions/runs/43847804683): platform performance and settings returned successfully.

## Actual outcome

| Item | Platform evidence |
| --- | --- |
| Historical query | 3 bars; latest 2025-12-01 00:00:00; close 90386.0 |
| Buy | trade_ID 1; 2025-12-01 00:00:00; BTCUSD 0.01 lot; fill 90408.0 |
| Close/sell | trade_ID 1; 2025-12-01 01:00:00; fill 86997.0 |
| Completion | `V1.0_ROUND_TRIP_COMPLETE`, followed by `Backtest finished!` |
| TotalPnL | -34.11000000000058 USD |
| TradeCnt | 2 platform trade events; one opening and one closing transaction |
| maxDrawdown_amt | 34.11000000000058 USD |
| maxDrawdown_pct | 0.003411000000000053 (approximately 0.3411%) |
| Initial capital / leverage | 10000 USD / 1.0 |
| Actual period / interval | 2025-12 through 2025-12 / 60 minutes |

## Qualifications and failures retained

The API request specified 2026-10; the platform returned settings and logs for 2025-12. Reason remains unverified. Treat the actual 2025-12 window as controlling this result. Do not label it an October 2026 backtest.

The opening script attached a 2% stop loss, but the next-hour exit was about 3.77% below entry. Log evidence identifies the timed close; it does not prove stop-loss protection or intra-bar execution. V1.1 must investigate stop behavior and the large hourly price move before relying on any loss cap.

Platform `simpleReturn` is 0.0 despite negative TotalPnL. The arithmetic P/L-to-initial-capital ratio is -0.3411%; that calculation is distinct from the platform's `simpleReturn` field.

Result: PASS for history/API/one-round-trip compatibility; LOSS for this trade. This single compatibility experiment does not validate a profitable trading hypothesis.

Next: investigate requested-versus-effective dates and stop execution; respect at least 60 seconds between REST calls. Keep the existing backtest ID when retrieving evidence; do not resubmit merely because a result query fails.
