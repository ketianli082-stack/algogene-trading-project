"""ALGOGENE Crypto V1.0: one guarded BTCUSD backtest round trip.

Paste this file into ALGOGENE's cloud backtest editor. It deliberately uses
only the platform-provided AlgoAPI package and Python's standard library.
Required platform setting: order-based (not position-netting) execution.
"""

from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest


class AlgoEvent:
    """Read three hourly bars, buy once, then close on the next market event."""

    INSTRUMENT = "BTCUSD"
    HISTORY_INTERVAL = "H"
    HISTORY_BARS = 3
    VOLUME = 0.01
    STOP_LOSS_PCT = 0.02

    def __init__(self):
        self.evt = None
        self.disabled = False
        self.history_attempted = False
        self.history_ok = False
        self.open_submitted = False
        self.open_trade_id = None
        self.open_seen_at = None
        self.close_submitted = False
        self.completed = False
        self.last_market_timestamp = None

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        subscriptions = mEvt.get("subscribeList", [])
        if self.INSTRUMENT not in subscriptions:
            self.disabled = True
            self.evt.consoleLog(
                "V1.0_DISABLED",
                "BTCUSD must be present in subscribeList",
            )
        self.evt.start()

    def _read_history_once(self):
        self.history_attempted = True
        try:
            bars = self.evt.getHistoricalBar(
                contract={"instrument": self.INSTRUMENT},
                numOfBar=self.HISTORY_BARS,
                interval=self.HISTORY_INTERVAL,
            )
            if not isinstance(bars, dict) or len(bars) < self.HISTORY_BARS:
                self.evt.consoleLog(
                    "V1.0_HISTORY_REJECTED",
                    "expected at least %s bars" % self.HISTORY_BARS,
                )
                return

            latest_key = sorted(bars.keys())[-1]
            latest = bars[latest_key]
            required = ("o", "h", "l", "c")
            if not all(key in latest for key in required):
                self.evt.consoleLog(
                    "V1.0_HISTORY_REJECTED",
                    "latest bar is missing OHLC fields",
                )
                return

            self.history_ok = True
            self.evt.consoleLog(
                "V1.0_HISTORY_OK",
                "count=%s" % len(bars),
                "latest=%s" % latest_key,
                "close=%s" % latest["c"],
            )
        except Exception as exc:
            self.evt.consoleLog("V1.0_HISTORY_ERROR", type(exc).__name__)

    def _submit_open(self, md):
        price = getattr(md, "askPrice", None) or getattr(md, "lastPrice", None)
        if price is None or price <= 0:
            self.evt.consoleLog("V1.0_OPEN_SKIPPED", "invalid market price")
            return

        # Set before sendOrder so a synchronous callback cannot create duplicates.
        self.open_submitted = True
        order = AlgoAPIUtil.OrderObject(
            instrument=self.INSTRUMENT,
            openclose="open",
            buysell=1,
            ordertype=0,
            volume=self.VOLUME,
            stopLossLevel=price * (1.0 - self.STOP_LOSS_PCT),
            orderRef="algogene_crypto_v1_0_open",
        )
        self.evt.sendOrder(order)
        self.evt.consoleLog(
            "V1.0_OPEN_SUBMITTED",
            "instrument=%s" % self.INSTRUMENT,
            "volume=%s" % self.VOLUME,
        )

    def _submit_close(self):
        self.close_submitted = True
        order = AlgoAPIUtil.OrderObject(
            tradeID=self.open_trade_id,
            openclose="close",
        )
        self.evt.sendOrder(order)
        self.evt.consoleLog("V1.0_CLOSE_SUBMITTED")

    def on_marketdatafeed(self, md, ab):
        if self.disabled or self.completed or md.instrument != self.INSTRUMENT:
            return

        self.last_market_timestamp = md.timestamp
        if not self.history_attempted:
            self._read_history_once()

        if self.history_ok and not self.open_submitted:
            self._submit_open(md)
            return

        if (
            self.open_trade_id is not None
            and not self.close_submitted
            and self.open_seen_at is not None
            and md.timestamp > self.open_seen_at
        ):
            self._submit_close()

    def on_orderfeed(self, of):
        if getattr(of, "status", None) != "success":
            self.evt.consoleLog(
                "V1.0_ORDER_NOT_SUCCESSFUL",
                "openclose=%s" % getattr(of, "openclose", "unknown"),
                "status=%s" % getattr(of, "status", "unknown"),
            )
            return

        if getattr(of, "openclose", None) == "open":
            self.open_trade_id = of.tradeID
            self.open_seen_at = self.last_market_timestamp
            self.evt.consoleLog(
                "V1.0_OPEN_FILLED",
                "tradeID=%s" % of.tradeID,
                "fill_price=%s" % getattr(of, "fill_price", "unknown"),
            )
        elif getattr(of, "openclose", None) == "close":
            self.completed = True
            self.evt.consoleLog(
                "V1.0_ROUND_TRIP_COMPLETE",
                "tradeID=%s" % getattr(of, "tradeID", "unknown"),
                "fill_price=%s" % getattr(of, "fill_price", "unknown"),
            )

    def on_bulkdatafeed(self, isSync, bd, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_openPositionfeed(self, op, oo, uo):
        pass
