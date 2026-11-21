"""V1.5-D: V1.3-A plus 0.5% NAV ATR risk-budget position sizing.
Hourly long/flat BTCUSD, allocation capped at 50% NAV and 95% available cash.
The planned loss at 3 ATR is a sizing target, not a guaranteed realized loss.
2021-2024 development; 2025 reserved.
"""
from collections import deque
from datetime import datetime, timezone
from math import floor, isfinite
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest

SYMBOL = "BTCUSD"
FAST = 20
SLOW = 50
ALLOCATION = 0.50
RISK_FRACTION = 0.005
ADX_PERIOD = 14
ADX_THRESHOLD = 25
ATR_PERIOD = 14
ATR_MULT = 3.0
VOLUME_DECIMALS = 4
WINDOW = 240
TREND_PERIOD = 200
FEE_RATE = 0.0005
BASE_SLIPPAGE = 0.0001
VOL_SLIPPAGE_COEFF = 0.02
ALLOW_SHORT = True
ALLOW_REENTRY = True
COOLDOWN_HOURS = 12
MAX_REENTRIES = 2


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



def history_ohlc(history, before):
    """Return sorted, completed hourly OHLC from ALGOGENE getHistoricalBar."""
    if not isinstance(history, dict):
        return []
    observations = {}
    for k, data in history.items():
        if not isinstance(data, dict):
            continue
        try:
            t = timestamp(data.get("t", k))
        except (TypeError, ValueError, OverflowError):
            continue
        if t >= before:
            continue
        h, l, c = positive(data.get("h")), positive(data.get("l")), positive(data.get("c"))
        if h is None or l is None or c is None or not l <= c <= h:
            continue
        observations[t] = (h, l, c)
    return sorted(observations.items())

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

def atr_value(bars, period=ATR_PERIOD):
    if len(bars) < period + 1:
        return None
    ranges = [max(h-l, abs(h-pc), abs(l-pc))
              for (_, _, pc), (h,l,_) in zip(bars, bars[1:])]
    atr = sum(ranges[:period])/period
    for tr in ranges[period:]:
        atr = (atr*(period-1)+tr)/period
    return positive(atr)


def fixed_stop(fill, atr, side=1):
    return max(0.0, fill - side * ATR_MULT * atr)


def round_trip_cost(price, atr):
    """Hypothetical incremental friction per BTC; decision input only."""
    slip = BASE_SLIPPAGE + VOL_SLIPPAGE_COEFF * atr / price
    return 2 * (FEE_RATE + slip) * price


def risk_sized_volume(nav, available, price, contract_size, atr):
    """Contracts, floored to platform volume precision. ATR is price per BTC."""
    if any(positive(x) is None for x in (nav, available, price, contract_size, atr)):
        return 0.0
    allocation_cap = min(ALLOCATION * nav, 0.95 * available) / (price * contract_size)
    risk_cap = RISK_FRACTION * nav / ((ATR_MULT * atr + round_trip_cost(price, atr)) * contract_size)
    scale = 10 ** VOLUME_DECIMALS
    return floor(min(allocation_cap, risk_cap) * scale) / scale


class LongTrend:
    def __init__(self, period=TREND_PERIOD):
        self.period = period
        self.seed = []
        self.value = None
        self.last_price = None

    def permits_entry(self, side=1):
        return self.value is not None and side * (self.last_price - self.value) > 0

    def update(self, price):
        self.last_price = price
        if self.value is None:
            self.seed.append(price)
            if len(self.seed) == self.period:
                self.value = sum(self.seed) / self.period
                self.seed.clear()
        else:
            alpha = 2.0 / (self.period + 1)
            self.value += alpha * (price - self.value)


def recovery_cross(values, side):
    if len(values) < SLOW + 2:
        return False
    fast, slow = ema_series(values, FAST), ema_series(values, SLOW)
    return (side * (fast[-1]-slow[-1]) > 0 and
            side * (values[-2]-fast[-2]) <= 0 and
            side * (values[-1]-fast[-1]) > 0)


class Recovery:
    def __init__(self):
        self.reset()

    def reset(self):
        self.side = 0
        self.closed_at = None
        self.count = 0

    def arm(self, side, now):
        self.side = side
        self.closed_at = now

    def eligible(self, previous_time, values):
        return (self.side != 0 and self.closed_at is not None and
                self.count < MAX_REENTRIES and previous_time is not None and
                (previous_time-self.closed_at).total_seconds() >= COOLDOWN_HOURS*3600
                and recovery_cross(values,self.side))


class AlgoEvent:
    def __init__(self):
        self.prices = deque(maxlen=WINDOW)
        self.long_trend = LongTrend()
        self.adx_queries = 0
        self.adx_errors = 0
        self.last_time = None
        self.contract_size = None
        self.lots = {}
        self.pending = None
        self.halted = False
        self.entry_atr = None
        self.stops = {}
        self.side = 0
        self.request_side = 1
        self.request_kind = 'CROSS'
        self.exit_reason = None
        self.recovery = Recovery()
        self.trend_side = 0

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        subscriptions = mEvt.get("subscribeList", [])
        if SYMBOL not in subscriptions or len(subscriptions) != 1:
            raise ValueError("V1.5-D requires exactly BTCUSD as subscribed instrument")
        spec = self.evt.getContractSpec(SYMBOL)
        self.contract_size = positive(spec.get("contractSize"))
        if self.contract_size is None:
            raise ValueError("Cannot validate BTCUSD contract size")
        self.evt.consoleLog("BTC V1.5-D EMA20/50 ADX25 ATR14 x3 hourly EMA200 gate")
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

        # Preserve the working V1.0 hourly EMA state even if OHLC is absent.
        # Evaluate using prices strictly before the current timestamp.
        prior = list(self.prices)
        signal = cross_signal(prior)
        previous_time = self.last_time
        if signal and signal != self.trend_side:
            self.trend_side = signal
            self.recovery.reset()
        candidate = signal if signal == 1 or (signal == -1 and ALLOW_SHORT) else 0
        kind = "CROSS"
        if candidate and self.lots and candidate != self.side:
            self.evt.consoleLog("OPPOSITE_SIGNAL_WHILE_HELD", now, candidate)
        if (ALLOW_REENTRY and not candidate and not self.lots and
                self.pending is None and not self.halted and
                self.recovery.eligible(previous_time, prior)):
            candidate = self.recovery.side
            kind = "REENTRY"
            self.evt.consoleLog("RECOVERY_CANDIDATE", now, candidate, self.recovery.count)
        if candidate == -1 and not ALLOW_SHORT:
            candidate = 0
        if candidate and not self.lots and self.pending is None and not self.halted:
            allowed = self.long_trend.permits_entry(candidate)
            self.evt.consoleLog('EMA200_ENTRY_CHECK', now, self.long_trend.last_price,
                                self.long_trend.value, allowed)
            if not allowed:
                candidate = 0
        self.long_trend.update(price)
        self.last_time = now
        self.prices.append(price)
        if candidate and not self.lots and self.pending is None and not self.halted:
            self.adx_queries += 1
            try:
                history = self.evt.getHistoricalBar(
                    {"instrument": SYMBOL}, 160, "H", now)
                completed = history_ohlc(history, now)
                bars = [bar for _, bar in completed]
                adx = adx_series(bars, ADX_PERIOD)
                self.entry_atr = atr_value(bars)
                if not adx or self.entry_atr is None:
                    self.evt.consoleLog("ADX_NOT_READY", now, len(completed))
                    candidate = 0
                else:
                    self.evt.consoleLog("ADX_ENTRY_CHECK", now, round(adx[-1], 3),
                                        ADX_THRESHOLD, len(completed))
                    if adx[-1] <= ADX_THRESHOLD:
                        candidate = 0
            except Exception as exc:
                self.adx_errors += 1
                self.evt.consoleLog("ADX_HISTORY_ERROR", now, type(exc).__name__)
                candidate = 0

        if self.pending is not None or self.halted:
            return
        if candidate and not self.lots:
            if not isinstance(ab, dict):
                return
            nav = positive(ab.get("NAV"))
            available = positive(ab.get("availableBalance"))
            if nav is None or available is None:
                return
            volume = risk_sized_volume(nav, available, price, self.contract_size, self.entry_atr)
            self.evt.consoleLog("RISK_SIZE", now, nav, available, price,
                                self.entry_atr, self.contract_size, volume,
                                volume * self.contract_size * price / nav,
                                volume * self.contract_size * ATR_MULT * self.entry_atr / nav)
            cost = round_trip_cost(price, self.entry_atr)
            self.evt.consoleLog("COST_RISK_SIZE", now, price, self.entry_atr,
                                cost, volume, volume * self.contract_size *
                                (ATR_MULT * self.entry_atr + cost) / nav)
            if volume <= 0:
                self.evt.consoleLog("BUY_SKIPPED_VOLUME", now, volume)
                return
            order = AlgoAPIUtil.OrderObject()
            order.instrument = SYMBOL
            order.openclose = "open"
            order.buysell = candidate
            order.ordertype = 0
            order.volume = volume
            order.orderRef = "BTC-V15D-" + ("LONG" if candidate == 1 else "SHORT") + "-" + kind
            self.request_side = candidate
            self.request_kind = kind
            self.pending = ("open", now)
            self.evt.consoleLog("ENTRY_SUBMIT", now, price, volume, candidate, kind)
            try:
                self.evt.sendOrder(order)
            except Exception as exc:
                self.halted = True
                self.evt.consoleLog("ORDER_OUTCOME_UNKNOWN_HALT", repr(exc))
        elif self.lots and (signal == -self.side or any(self.side * (price-level) <= 0 for level in self.stops.values())):
            reason = 'EMA_CROSS' if signal == -self.side else 'ATR_STOP'
            self.exit_reason = reason
            self.evt.consoleLog('EXIT_SIGNAL', reason, now, price, str(self.stops))
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
            if action == 'open':
                self.entry_atr = None
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
                fill = positive(getattr(of, 'fill_price', None))
                if fill is None or self.entry_atr is None:
                    self.halted = True
                    self.evt.consoleLog('STOP_ANCHOR_MISSING_HALT', trade_id)
                    return
                self.side = self.request_side
                observed_side = getattr(of, "buysell", None)
                if observed_side is not None and str(observed_side) in ("1","-1","1.0","-1.0") and float(observed_side) != self.side:
                    self.halted = True
                    self.evt.consoleLog("DIRECTION_MISMATCH_HALT", trade_id)
                    return
                self.stops[trade_id] = fixed_stop(fill, self.entry_atr, self.side)
                if self.request_kind == "REENTRY":
                    self.recovery.count += 1
                self.recovery.closed_at = None
                self.evt.consoleLog("ENTRY_CONFIRMED", trade_id, self.side, self.request_kind, self.recovery.count)
                self.evt.consoleLog('ATR_STOP_SET', trade_id, fill, self.entry_atr, self.stops[trade_id])
            self.pending = None
        elif action == "close":
            self.lots.pop(trade_id, None)
            self.stops.pop(trade_id, None)
            if not self.lots:
                if ALLOW_REENTRY and self.exit_reason == "ATR_STOP" and self.trend_side == self.side and self.last_time is not None:
                    self.recovery.arm(self.side, self.last_time)
                    self.evt.consoleLog("RECOVERY_ARMED", self.last_time, self.side, self.recovery.count)
                else:
                    self.recovery.reset()
                self.side = 0
                self.exit_reason = None
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
