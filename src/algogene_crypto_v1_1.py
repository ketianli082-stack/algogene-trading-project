"""V1.1 fixed-size, long-only EMA200 / Donchian20 baseline. Backtest only."""
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest
from collections import deque
from datetime import datetime, timedelta
import math


class TrendState:
    def __init__(self):
        self.seed = []
        self.ema = None
        self.bars = deque(maxlen=20)
        self.last_time = None

    def add(self, timestamp, bar):
        if self.last_time is not None and timestamp <= self.last_time:
            return None
        values = [float(bar[k]) for k in ("o", "h", "l", "c")]
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError("Invalid OHLC")
        o, h, l, c = values
        if not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError("Inconsistent OHLC")
        upper = max((b[0] for b in self.bars), default=h)
        lower = min((b[1] for b in list(self.bars)[-10:]), default=l)
        ready = len(self.bars) == 20 and self.ema is not None
        if self.ema is None:
            self.seed.append(c)
            if len(self.seed) == 200:
                self.ema = sum(self.seed) / 200
                self.seed = []
        else:
            self.ema += (2.0 / 201.0) * (c - self.ema)
        signal = None
        if ready:
            signal = {"entry": c > upper and c > self.ema,
                      "exit": c < lower or c < self.ema,
                      "time": timestamp, "close": c}
        self.bars.append((h, l))
        self.last_time = timestamp
        return signal


class AlgoEvent:
    def __init__(self):
        self.trend = TrendState()
        self.trade_id = None
        self.pending = False
        self.halted = False
        self.last_event = None
        self.month = None
        self.signals = 0
        self.first_history = True

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        self.halted = mEvt.get("subscribeList") != ["BTCUSD"]
        self.evt.start()

    def on_marketdatafeed(self, md, ab):
        if md.instrument != "BTCUSD" or md.timestamp == self.last_event:
            return
        self.last_event = md.timestamp
        # Explicit terminal liquidation before the final H4 event; no new entries.
        terminal = md.timestamp >= datetime(2023, 12, 31, 16)
        if terminal:
            if self.trade_id is not None and not self.pending:
                self.close()
            return
        if self.pending or self.halted:
            return
        try:
            history = self.evt.getHistoricalBar(
                contract={"instrument": "BTCUSD"}, numOfBar=260, interval="H4")
            if not isinstance(history, dict):
                raise ValueError("History is not a timestamp dictionary")
            # ALGOGENE documents close-time stamps. Strictly earlier timestamps
            # deliberately impose an additional bar delay on this baseline.
            keys = sorted(t for t in history if t < md.timestamp)
            if self.first_history:
                self.evt.consoleLog("V1.1_HISTORY", "interval=H4", "count=%s" % len(keys),
                                    "first=%s" % (keys[0] if keys else "none"),
                                    "last=%s" % (keys[-1] if keys else "none"))
                if len(keys) < 201:
                    raise ValueError("Insufficient 200-bar pre-start warm-up")
                self.first_history = False
            decision = None
            for t in keys:
                update = self.trend.add(t, history[t])
                if update is not None:
                    decision = update
            if decision is None:
                return
            month = (md.timestamp.year, md.timestamp.month)
            if month != self.month:
                self.month = month
                self.evt.consoleLog("V1.1_CHECKPOINT", str(md.timestamp),
                                    "signal_bar=%s" % decision["time"],
                                    "ema=%s" % self.trend.ema, "entries=%s" % self.signals)
            if self.trade_id is not None:
                if decision["exit"]:
                    self.close()
            elif decision["entry"]:
                price = float(md.askPrice)
                if not math.isfinite(price) or price <= 0:
                    raise ValueError("Invalid quote")
                # Fixed .01 lot baseline; capital check assumes contractSize=1.
                # No ATR scaling, pyramiding, short opens, or leveraged sizing.
                available = float(ab["availableBalance"])
                if available < price * 0.01 * 1.10:
                    self.evt.consoleLog("V1.1_SKIP_CAPITAL")
                    return
                self.pending = True
                self.signals += 1
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    instrument="BTCUSD", openclose="open", buysell=1,
                    ordertype=0, volume=0.01, orderRef="v1_1_long"))
        except Exception as exc:
            self.halted = True
            self.evt.consoleLog("V1.1_HALTED", type(exc).__name__, str(exc))
            if self.trade_id is not None and not self.pending:
                self.close()

    def close(self):
        self.pending = True
        self.evt.sendOrder(AlgoAPIUtil.OrderObject(tradeID=self.trade_id, openclose="close"))

    def on_orderfeed(self, of):
        if getattr(of, "status", None) != "success":
            self.halted = True
            self.evt.consoleLog("V1.1_ORDER_UNCONFIRMED", str(getattr(of, "status", None)))
            return
        if of.openclose == "open":
            self.trade_id = of.tradeID
        elif of.openclose == "close":
            self.trade_id = None
        self.pending = False
        self.evt.consoleLog("V1.1_FILL", of.openclose, "tradeID=%s" % of.tradeID,
                            "price=%s" % getattr(of, "fill_price", None))

    def on_bulkdatafeed(self, isSync, bd, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_openPositionfeed(self, op, oo, uo):
        pass
