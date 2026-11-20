"""V1.1 BTCUSD EMA20/50 + ADX14 entry filter. 60min, long/flat.
Only bars preceding the execution timestamp influence decisions.
2021-2024 development set; 2025 reserved, no LLM or cost override.
"""
from collections import deque
from datetime import datetime, timezone
from math import floor, isfinite
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest

SYMBOL = "BTCUSD"
FAST = 20
SLOW = 50
ALLOCATION = 0.50
ADX_PERIOD = 14
ADX_THRESHOLD = 25
VOLUME_DECIMALS = 4
WINDOW = 240


def timestamp(value):
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return result.replace(tzinfo=None) if result.tzinfo is None else result.astimezone(timezone.utc).replace(tzinfo=None)


def positive(value):
    try:
        number = float(value)
        return number if isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def ema_series(values, n):
    if len(values) < n:
        return []
    e = sum(values[:n]) / n
    result = [e]
    alpha = 2.0 / (n + 1)
    for x in values[n:]:
        e = alpha * x + (1 - alpha) * e
        result.append(e)
    return result


def cross_signal(values):
    """Return +1 buy, -1 flatten, or 0. Exactly prior completed candles."""
    if len(values) < SLOW + 2:
        return 0
    fast = ema_series(values, FAST)
    slow = ema_series(values, SLOW)
    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        return 1
    if fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        return -1
    return 0


def quote_price(item):
    if not isinstance(item, dict):
        return None
    bid, ask = positive(item.get("bidPrice")), positive(item.get("askPrice"))
    if bid is not None and ask is not None and bid <= ask:
        return (bid + ask) / 2
    return positive(item.get("c")) or positive(item.get("lastPrice"))



def valid_ohlc(item):
    if not isinstance(item, dict):
        return None
    h = positive(item.get("h", item.get("highPrice")))
    l = positive(item.get("l", item.get("lowPrice")))
    c = positive(item.get("c", item.get("closePrice")))
    if h is None or l is None or c is None or l > h or not l <= c <= h:
        return None
    return h, l, c


def adx_series(bars, period=14):
    """Wilder ADX14 from historical high/low/close, no external libraries."""
    if len(bars) < 2 * period:
        return []
    tr, plus, minus = [], [], []
    for (ph, pl, pc), (h, l, c) in zip(bars, bars[1:]):
        up, down = h - ph, pl - l
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
        plus.append(up if up > down and up > 0 else 0.0)
        minus.append(down if down > up and down > 0 else 0.0)
    atr, sp, sm = sum(tr[:period]), sum(plus[:period]), sum(minus[:period])
    dx = []
    for i in range(period-1, len(tr)):
        if i >= period:
            atr += tr[i] - atr / period
            sp += plus[i] - sp / period
            sm += minus[i] - sm / period
        pdi = 100 * sp / atr if atr > 0 else 0
        mdi = 100 * sm / atr if atr > 0 else 0
        den = pdi + mdi
        dx.append(100 * abs(pdi-mdi) / den if den > 0 else 0)
    if len(dx) < period:
        return []
    adx = sum(dx[:period]) / period
    out = [adx]
    for value in dx[period:]:
        adx = (adx * (period - 1) + value) / period
        out.append(adx)
    return out


def v11_signal(prices, bars, threshold=ADX_THRESHOLD):
    cross = cross_signal(prices)
    if cross != 1:
        return cross
    adx = adx_series(bars, ADX_PERIOD)
    return 1 if adx and adx[-1] > threshold else 0

class AlgoEvent:
    def __init__(self):
        self.prices = deque(maxlen=WINDOW)
        self.bars = deque(maxlen=WINDOW)
        self.last_time = None
        self.contract_size = None
        self.lots = {}
        self.pending = None
        self.halted = False

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        subscriptions = mEvt.get("subscribeList", [])
        if SYMBOL not in subscriptions or len(subscriptions) != 1:
            raise ValueError("V1.0 requires exactly BTCUSD as subscribed instrument")
        spec = self.evt.getContractSpec(SYMBOL)
        self.contract_size = positive(spec.get("contractSize"))
        if self.contract_size is None:
            raise ValueError("Cannot validate BTCUSD contract size")
        self.evt.consoleLog("BTC V1.1 EMA20/50 plus ADX14 entry filter")
        self.evt.start()

    def on_bulkdatafeed(self, isSync, bd, ab):
        if not isSync or not isinstance(bd, dict):
            return
        item = bd.get(SYMBOL)
        if not isinstance(item, dict):
            return
        try:
            now = timestamp(item["timestamp"])
        except (KeyError, TypeError, ValueError):
            return
        if self.last_time is not None and now <= self.last_time:
            return
        price = quote_price(item)
        if price is None:
            return

        # Only prior completed observations determine the signal.
        bar = valid_ohlc(item)
        if bar is None:
            self.last_time = now
            self.prices.clear()
            self.bars.clear()
            self.evt.consoleLog('MISSING_OHLC', now)
            return
        signal = v11_signal(list(self.prices), list(self.bars))
        self.last_time = now
        self.prices.append(price)
        self.bars.append(bar)

        if self.pending is not None or self.halted:
            return
        if signal == 1 and not self.lots:
            if not isinstance(ab, dict):
                return
            nav = positive(ab.get("NAV"))
            available = positive(ab.get("availableBalance"))
            if nav is None or available is None:
                return
            budget = min(ALLOCATION * nav, 0.95 * available)
            scale = 10 ** VOLUME_DECIMALS
            volume = floor(budget / (price * self.contract_size) * scale) / scale
            if volume <= 0:
                self.evt.consoleLog("BUY_SKIPPED_VOLUME", now, volume)
                return
            order = AlgoAPIUtil.OrderObject()
            order.instrument = SYMBOL
            order.openclose = "open"
            order.buysell = 1
            order.ordertype = 0
            order.volume = volume
            order.orderRef = "BTC-V11-OPEN"
            self.pending = ("open", now)
            self.evt.consoleLog("BUY_SUBMIT", now, price, volume)
            try:
                self.evt.sendOrder(order)
            except Exception as exc:
                self.halted = True
                self.evt.consoleLog("ORDER_OUTCOME_UNKNOWN_HALT", repr(exc))
        elif signal == -1 and self.lots:
            # Close each recorded lot using its platform trade ID.
            self.pending = ("close", now)
            for trade_id in list(self.lots):
                order = AlgoAPIUtil.OrderObject()
                order.tradeID = trade_id
                order.openclose = "close"
                try:
                    self.evt.sendOrder(order)
                except Exception as exc:
                    self.halted = True
                    self.evt.consoleLog("CLOSE_OUTCOME_UNKNOWN_HALT", trade_id, repr(exc))
                    break

    def on_orderfeed(self, of):
        status = str(getattr(of, "status", "")).lower()
        action = getattr(of, "openclose", None)
        trade_id = getattr(of, "tradeID", None)
        if status in ("reject", "kill"):
            self.evt.consoleLog("ORDER_REJECTED", action, trade_id, status)
            self.pending = None
            return
        if status != "success":
            if "partial" in status:
                self.halted = True
                self.evt.consoleLog("PARTIAL_FILL_HALT", action, trade_id)
            return
        if trade_id is None:
            self.halted = True
            self.evt.consoleLog("UNKNOWN_TRADE_ID_HALT", action)
            return
        if action == "open":
            if trade_id not in self.lots:
                qty = positive(getattr(of, "fill_volume", None))
                if qty is None:
                    self.halted = True
                    self.evt.consoleLog("INVALID_FILL_HALT", trade_id)
                    return
                self.lots[trade_id] = qty
            self.pending = None
        elif action == "close":
            self.lots.pop(trade_id, None)
            if not self.lots:
                self.pending = None

    def on_openPositionfeed(self, op, oo, uo):
        pass

    def on_marketdatafeed(self, md, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_newsdatafeed(self, nd):
        pass

    def on_weatherdatafeed(self, wd):
        pass

    def on_econsdatafeed(self, ed):
        pass

    def on_corpAnnouncement(self, ca):
        pass
