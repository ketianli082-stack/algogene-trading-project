"""V1.5 pre-registered hourly trend candidates. ALGOGENE backtest only."""
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest
from collections import deque
from datetime import datetime, timedelta
import math
import numpy as np
from talib import ATR


PARAMS = {"mode": "breakout", "entry": 20, "exit": 10, "stop": 2.0, "cooldown": 6}


def position_volume(available, price, atr):
    """Volatility budget, not a guaranteed loss limit; contractSize must be 1."""
    if not all(math.isfinite(x) and x > 0 for x in (available, price, atr)):
        return 0.0
    raw = min(available * 0.001 / (PARAMS["stop"] * atr),
              available * 0.20 / price, 0.02)
    # Model discretization in .01 lot increments, not a claim about broker min lot.
    return math.floor(raw * 100.0) / 100.0


class TrendState:
    def __init__(self):
        self.seed = []
        self.ema = None
        self.ema_history = deque(maxlen=25)
        self.fast = None
        self.mid = None
        self.fast_seed = []
        self.mid_seed = []
        self.previous_close = None
        self.bars = deque(maxlen=40)
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
        prior = list(self.bars)
        upper = max((b[0] for b in prior[-PARAMS["entry"]:]), default=h)
        lower = min((b[1] for b in prior[-PARAMS["exit"]:]), default=l)
        ready = len(prior) >= max(PARAMS["entry"], PARAMS["exit"]) and self.ema is not None
        previous_fast = self.fast
        if self.fast is None:
            self.fast_seed.append(c)
            if len(self.fast_seed) == 20:
                self.fast = sum(self.fast_seed) / 20
                self.fast_seed = []
        else:
            self.fast += (2.0 / 21.0) * (c - self.fast)
        if self.mid is None:
            self.mid_seed.append(c)
            if len(self.mid_seed) == 50:
                self.mid = sum(self.mid_seed) / 50
                self.mid_seed = []
        else:
            self.mid += (2.0 / 51.0) * (c - self.mid)
        if self.ema is None:
            self.seed.append(c)
            if len(self.seed) == 200:
                self.ema = sum(self.seed) / 200
                self.seed = []
        else:
            self.ema += (2.0 / 201.0) * (c - self.ema)
        if self.ema is not None:
            self.ema_history.append(self.ema)
        signal = None
        if ready:
            trend = (self.mid is not None and self.mid > self.ema and c > self.ema
                     and len(self.ema_history) == 25 and self.ema > self.ema_history[0])
            if PARAMS["mode"] == "breakout":
                entry = trend and c > upper
            else:
                entry = (trend and self.previous_close is not None and previous_fast is not None
                         and self.previous_close <= previous_fast and c > self.fast)
            signal = {"entry": entry, "exit": c < lower or c < self.mid,
                      "time": timestamp, "close": c}
        self.previous_close = c
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
        self.cooldown_until = None
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
        # Explicit terminal liquidation before the final hourly event.
        terminal = md.timestamp >= datetime(2023, 12, 31, 22)
        if terminal:
            if self.trade_id is not None and not self.pending:
                self.send_exit()
            return
        if self.pending or self.halted:
            return
        try:
            history = self.evt.getHistoricalBar(
                contract={"instrument": "BTCUSD"}, numOfBar=260, interval="H")
            if not isinstance(history, dict):
                raise ValueError("History is not a timestamp dictionary")
            # ALGOGENE documents close-time stamps. Strictly earlier timestamps
            # deliberately impose an additional bar delay on this baseline.
            normalized = {}
            for raw_time, bar in history.items():
                timestamp = raw_time if isinstance(raw_time, datetime) else datetime.fromisoformat(str(raw_time))
                normalized[timestamp] = bar
            keys = sorted(t for t in normalized if t < md.timestamp)
            if self.first_history:
                self.evt.consoleLog("V1.3_HISTORY", "interval=H", "count=%s" % len(keys),
                                    "first=%s" % (keys[0] if keys else "none"),
                                    "last=%s" % (keys[-1] if keys else "none"))
                if len(keys) < 201:
                    raise ValueError("Insufficient 200-bar pre-start warm-up")
                self.first_history = False
            decision = None
            for t in keys:
                update = self.trend.add(t, normalized[t])
                if update is not None:
                    decision = update
            if decision is None:
                return
            month = (md.timestamp.year, md.timestamp.month)
            if month != self.month:
                self.month = month
                self.evt.consoleLog("V1.3_CHECKPOINT", str(md.timestamp),
                                    "signal_bar=%s" % decision["time"],
                                    "ema=%s" % self.trend.ema, "entries=%s" % self.signals)
            if self.trade_id is not None:
                if decision["exit"]:
                    self.send_exit()
            elif decision["entry"] and (self.cooldown_until is None or md.timestamp >= self.cooldown_until):
                price = float(md.askPrice)
                if not math.isfinite(price) or price <= 0:
                    raise ValueError("Invalid quote")
                available = float(ab["availableBalance"])
                atr = float(ATR(
                    np.array([normalized[t]["h"] for t in keys], dtype=float),
                    np.array([normalized[t]["l"] for t in keys], dtype=float),
                    np.array([normalized[t]["c"] for t in keys], dtype=float),
                    timeperiod=14)[-1])
                volume = position_volume(available, price, atr)
                if volume <= 0 or available < price * volume * 1.10:
                    self.evt.consoleLog("V1.3_SKIP_SIZE", "atr=%s" % atr)
                    return
                stop_loss = price - PARAMS["stop"] * atr
                if not math.isfinite(stop_loss) or stop_loss <= 0 or stop_loss >= price:
                    self.evt.consoleLog("V1.3_SKIP_STOP", "atr=%s" % atr)
                    return
                self.evt.consoleLog("V1.3_PROTECTION", "stopLossLevel=%s" % stop_loss)
                self.evt.consoleLog("V1.3_SIZE", "atr14=%s" % atr,
                                    "volume=%s" % volume)
                self.pending = True
                self.signals += 1
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    instrument="BTCUSD", openclose="open", buysell=1,
                    ordertype=0, volume=volume, stopLossLevel=stop_loss,
                    orderRef="v1_5_long"))
        except Exception as exc:
            self.halted = True
            self.evt.consoleLog("V1.3_HALTED", type(exc).__name__, str(exc))
            if self.trade_id is not None and not self.pending:
                self.send_exit()

    def send_exit(self):
        self.pending = True
        self.evt.sendOrder(AlgoAPIUtil.OrderObject(tradeID=self.trade_id, openclose="close"))

    def on_orderfeed(self, of):
        if getattr(of, "status", None) != "success":
            self.halted = True
            self.evt.consoleLog("V1.3_ORDER_UNCONFIRMED", str(getattr(of, "status", None)))
            return
        if of.openclose == "open":
            self.trade_id = of.tradeID
        elif of.openclose == "close":
            self.trade_id = None
            if self.last_event is not None:
                self.cooldown_until = self.last_event + timedelta(hours=PARAMS["cooldown"])
        self.pending = False
        self.evt.consoleLog("V1.3_FILL", of.openclose, "tradeID=%s" % of.tradeID,
                            "price=%s" % getattr(of, "fill_price", None))

    def on_bulkdatafeed(self, isSync, bd, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_openPositionfeed(self, op, oo, uo):
        pass
