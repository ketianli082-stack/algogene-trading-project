# -*- coding: utf-8 -*-
"""EXP-017: H1 execution, H4 signal and H24 regime, all from H1 history.

Research backtest only. Never request the ALGOGENE H4 interval or dataset 240.
ALGOGENE historical bar timestamps are CLOSE times; at decision time T only
bars with timestamp < T are eligible. H4 ends at UTC 00/04/08/12/16/20,
H24 ends at UTC 00. Four/six-hour frames are composed from complete H1 bars.
Pair data validation is independent for BTC and ETH; no stale leg fill-forward.
"""
import math
from datetime import datetime, timedelta
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest

# Exact substitution line for registered EXP-017 cloud candidates.
PARAMS = {"lookback_h4": 42, "entry_z": 2.0, "exit_z": 0.4, "stop_basis": 0.012, "max_hold_hours": 48, "max_abs_basis": 0.035, "max_h1_divergence": 0.025, "max_daily_move": 0.10, "min_edge": 0.002, "gross_pair": 0.15, "min_pair_notional": 1000, "min_half_life": 0.75, "max_half_life": 24.0, "use_ou_gate": False, "cooldown_hours": 12}

SYMBOLS = ("BTCUSD", "BTCUSDM", "ETHUSD", "ETHUSDM")
PAIRS = {"BTC": ("BTCUSD", "BTCUSDM"), "ETH": ("ETHUSD", "ETHUSDM")}
END = datetime(2025, 12, 31, 22, 0, 0)
HISTORY_BARS = 440


def _get(x, k, default=None):
    if isinstance(x, dict):
        return x.get(k, default)
    return getattr(x, k, default)


def _num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) and v > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _time(x):
    if isinstance(x, datetime):
        return datetime(x.year, x.month, x.day, x.hour, x.minute, x.second)
    if x is None:
        return None
    try:
        s = str(x)
        if s[-1:] == "Z":
            s = s[:-1] + "+00:00"
        t = datetime.fromisoformat(s)
        # ALGOGENE backtest timestamps use a consistent timezone.
        return datetime(t.year, t.month, t.day, t.hour, t.minute, t.second)
    except (ValueError, TypeError):
        return None


def _valid_bar(bar):
    o, h, l, c = [_num(_get(bar, k)) for k in ("o", "h", "l", "c")]
    if None in (o, h, l, c):
        return None
    if not (l <= min(o, c) <= max(o, c) <= h):
        return None
    return {"o": o, "h": h, "l": l, "c": c}


def _read_hours(raw, now):
    """Only prior complete H1 closes; never use the live execution candle."""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for ts, bar in raw.items():
        t = _time(ts)
        if t is None or t >= now or t.minute != 0 or t.second != 0:
            continue
        b = _valid_bar(bar)
        if b is not None:
            out[t] = b
    return out


def _resample(hours, period):
    """Build contiguous UTC close-time candles (4 or 24 completed H1 bars)."""
    if period not in (4, 24):
        return {}
    result = {}
    for end in sorted(hours):
        if end.hour % period != 0:
            continue
        times = [end - timedelta(hours=i) for i in range(period - 1, -1, -1)]
        if any(t not in hours for t in times):
            continue
        bars = [hours[t] for t in times]
        result[end] = {"o": bars[0]["o"], "h": max(b["h"] for b in bars),
                       "l": min(b["l"] for b in bars), "c": bars[-1]["c"]}
    return result


def _median(xs):
    ys = sorted(xs)
    mid = len(ys) // 2
    return ys[mid] if len(ys) % 2 else (ys[mid - 1] + ys[mid]) / 2.0


def _signal(sbar, fbar):
    """Robust H4 basis z and estimated OU half-life using completed bars only."""
    common = sorted(set(sbar) & set(fbar))
    n = PARAMS["lookback_h4"]
    if len(common) < n + 1:
        return None
    keys = common[-n - 1:]
    if any(keys[i] - keys[i - 1] != timedelta(hours=4)
           for i in range(1, len(keys))):
        return None
    series = [math.log(fbar[t]["c"] / sbar[t]["c"]) for t in keys]
    training, last = series[:-1], series[-1]
    center = _median(training)
    mad = _median([abs(v - center) for v in training]) * 1.4826
    mean = sum(training) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in training) / (n - 1))
    scale = mad if mad > 0.00002 else sd
    if scale <= 0.00002:
        return None
    x = [v - mean for v in training[:-1]]
    y = [v - mean for v in training[1:]]
    denom = sum(a * a for a in x)
    phi = sum(a * b for a, b in zip(x, y)) / denom if denom > 1e-12 else -1
    half_life = (-math.log(2) / math.log(phi)
                 if 0 < phi < 1 else None)
    return {"z": (last - center) / scale,
            "basis": last, "mean": center, "edge": abs(last - center),
            "half_life": half_life, "scale": scale, "end": keys[-1]}


def _regime(daily_spot, daily_future):
    """H24 regime filter: compare four complete matched daily candles."""
    keys = sorted(set(daily_spot) & set(daily_future))
    if len(keys) < 4:
        return None
    keys = keys[-4:]
    if any(keys[i] - keys[i - 1] != timedelta(hours=24)
           for i in range(1, len(keys))):
        return None
    c = [daily_spot[t]["c"] for t in keys]
    f = [daily_future[t]["c"] for t in keys]
    daily_return = abs(math.log(c[-1] / c[-2]))
    prev_basis = [abs(math.log(ff / ss)) for ss, ff in zip(c, f)]
    return {"safe": daily_return <= PARAMS["max_daily_move"]
            and max(prev_basis[-2:]) <= PARAMS["max_abs_basis"],
            "daily_move": daily_return, "daily_basis": prev_basis[-1]}


def _quantity(price, spec, target_notional):
    if None in (_num(price), _num(spec), _num(target_notional)):
        return 0.0
    # Native historical experiment confirmed 0.01 lots are permissible on BTC.
    # Never round up. Futures fractional fill support remains to be verified.
    raw = target_notional / (price * spec)
    return math.floor(raw * 100.0) / 100.0


def _snapshot(bd, pair):
    s, f = PAIRS[pair]
    ps = _num(_get(bd[s], "lastPrice"))
    pf = _num(_get(bd[f], "lastPrice"))
    if ps is None or pf is None:
        return None
    return {"spot": ps, "future": pf, "basis": math.log(pf / ps)}


class AlgoEvent:
    def __init__(self):
        self.last_hour = None
        self.peak_nav = None
        self.halted = False
        self.spec = {}
        self.cached = {"BTC": None, "ETH": None}
        self.states = {
            p: {"phase": "FLAT", "legs": {}, "pending": set(), "pending_at": None,
                "side": 0, "opened": None, "entry_basis": None,
                "cooldown_until": None, "serial": 0}
            for p in PAIRS}

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        if set(mEvt.get("subscribeList", [])) != set(SYMBOLS):
            self._halt("WRONG_SUBSCRIPTIONS")
        for sym in SYMBOLS:
            try:
                spec = self.evt.getContractSpec(sym)
                value = _num(_get(spec, "contractSize"))
                if value is None:
                    raise ValueError("contractSize unavailable")
                self.spec[sym] = value
            except Exception:
                self._halt("MISSING_CONTRACT_SPEC_" + sym)
        self.evt.start()

    def _log(self, *args):
        self.evt.consoleLog("EXP017", *args)

    def _halt(self, reason):
        self.halted = True
        if hasattr(self, "evt"):
            self._log("HALT", reason)

    def _history_pair(self, pair, now):
        """One independent H1 validation path for each spot/futures pair."""
        s, f = PAIRS[pair]
        hourly = {}
        for symbol in (s, f):
            raw = self.evt.getHistoricalBar(
                contract={"instrument": symbol}, numOfBar=HISTORY_BARS,
                interval="H")
            hourly[symbol] = _read_hours(raw, now)
        s_hours, f_hours = hourly[s], hourly[f]
        if not s_hours or not f_hours:
            raise ValueError("H1_EMPTY")
        recent = now - timedelta(hours=1)
        if recent not in s_hours or recent not in f_hours:
            raise ValueError("H1_NOT_ALIGNED")
        # Protect against a one-hour mismatch hidden inside an otherwise
        # complete four-hour candle; do not forward-fill stale quotes.
        s4, f4 = _resample(s_hours, 4), _resample(f_hours, 4)
        s24, f24 = _resample(s_hours, 24), _resample(f_hours, 24)
        sig = _signal(s4, f4)
        regime = _regime(s24, f24)
        if sig is None:
            raise ValueError("H4_INSUFFICIENT_OR_GAPPED")
        if regime is None:
            raise ValueError("H24_INSUFFICIENT_OR_GAPPED")
        if sig["end"] != recent:
            raise ValueError("H4_LAST_BAR_STALE")
        # At this moment both legs must agree with the last completed H1
        # close within a plausible one-hour basis change.
        quote_gap = abs(math.log(
            (f_hours[recent]["c"] / s_hours[recent]["c"]) /
            (f4[sig["end"]]["c"] / s4[sig["end"]]["c"])))
        if quote_gap > 0.001:
            raise ValueError("H1_H4_COHERENCE")
        return {"signal": sig, "regime": regime,
                "spot_close": s_hours[recent]["c"],
                "future_close": f_hours[recent]["c"]}

    def _equity(self, ab):
        nav = _num(_get(ab, "NAV")) or _num(_get(ab, "nav")) or _num(_get(ab, "equity"))
        free = _num(_get(ab, "availableBalance"))
        if nav is None and free is not None:
            # Fallback only for sizing, not for inference about max drawdown.
            nav = free
        return nav, free

    def _open(self, pair, quantity_s, quantity_f, side, now, basis):
        state = self.states[pair]
        s, f = PAIRS[pair]
        state["serial"] += 1
        state["phase"] = "OPENING"
        state["legs"] = {}
        state["pending"] = {s, f}
        state["pending_at"] = now
        state["side"] = side
        state["opened"] = now
        state["entry_basis"] = basis
        for symbol, qty, sign in ((s, quantity_s, -side), (f, quantity_f, side)):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    instrument=symbol, openclose="open", buysell=sign,
                    volume=qty, ordertype=0,
                    orderRef="EXP017-%s-%s-%s" % (
                        pair, state["serial"], symbol)))
            except Exception:
                self._halt("OPEN_ORDER_EXCEPTION_" + symbol)
                self._rescue(pair)
                return
        self._log("PAIR_OPEN_SENT", pair, side, quantity_s, quantity_f)

    def _close(self, pair, reason, now):
        state = self.states[pair]
        if state["phase"] != "OPEN" or len(state["legs"]) != 2:
            return
        state["phase"] = "CLOSING"
        state["pending"] = set(state["legs"])
        state["pending_at"] = now
        self._log("PAIR_EXIT", pair, reason)
        for symbol, trade_id in list(state["legs"].items()):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    tradeID=trade_id, openclose="close"))
            except Exception:
                self._halt("CLOSE_ORDER_EXCEPTION_" + symbol)
                self._rescue(pair)
                return

    def _rescue(self, pair):
        state = self.states[pair]
        state["phase"] = "HALT"
        # Do not falsely assume the two legs have been atomically matched.
        for symbol, trade_id in list(state["legs"].items()):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    tradeID=trade_id, openclose="close"))
                self._log("RESCUE_CLOSE_SUBMITTED", pair, symbol)
            except Exception:
                self._log("RESCUE_CLOSE_FAILED", pair, symbol)

    def on_orderfeed(self, of):
        symbol = _get(of, "instrument")
        ref = str(_get(of, "orderRef", ""))
        if symbol not in SYMBOLS:
            symbol = next((x for x in SYMBOLS if ref[-len(x) - 1:] == "-" + x), None)
        if symbol not in SYMBOLS:
            trade = _get(of, "tradeID")
            symbol = next((x for st in self.states.values()
                           for x, known in st["legs"].items() if known == trade), None)
        pair = next((p for p in PAIRS if symbol in PAIRS[p]), None)
        if pair is None:
            self._halt("UNMATCHED_ORDER_CALLBACK")
            return
        state = self.states[pair]
        if _get(of, "status") != "success":
            self._halt("ORDER_REJECTED_" + pair)
            self._rescue(pair)
            return
        action = _get(of, "openclose")
        if state["phase"] == "OPENING" and action == "open" and symbol in state["pending"]:
            trade = _get(of, "tradeID")
            if trade is None:
                self._halt("OPEN_TRADE_ID_MISSING_" + pair)
                self._rescue(pair)
                return
            state["legs"][symbol] = trade
            state["pending"] = {x for x in state["pending"] if x != symbol}
            if not state["pending"]:
                state["phase"] = "OPEN"
                self._log("PAIR_CONFIRMED", pair)
        elif state["phase"] == "CLOSING" and action == "close" and symbol in state["pending"]:
            del state["legs"][symbol]
            state["pending"] = {x for x in state["pending"] if x != symbol}
            if not state["pending"]:
                state["phase"] = "FLAT"
                state["cooldown_until"] = self.last_hour + timedelta(
                    hours=PARAMS["cooldown_hours"])
                state["opened"] = None
                state["entry_basis"] = None
                state["side"] = 0
                self._log("PAIR_CLOSED", pair)
        else:
            self._halt("UNEXPECTED_ORDER_CALLBACK_" + pair)
            self._rescue(pair)

    def on_bulkdatafeed(self, isSync, bd, ab):
        if not isSync or not isinstance(bd, dict) or any(x not in bd for x in SYMBOLS):
            return
        stamps = [_time(_get(bd[x], "timestamp")) for x in SYMBOLS]
        if any(t is None for t in stamps) or len(set(stamps)) != 1:
            return
        now = stamps[0]
        if now == self.last_hour or now.minute != 0 or now.second != 0:
            return
        self.last_hour = now
        for pair, state in self.states.items():
            if state["phase"] in ("OPENING", "CLOSING") and state["pending_at"] < now:
                self._halt("PENDING_ORDER_OVER_HOUR_" + pair)
                self._rescue(pair)
        if self.halted:
            return
        nav, free = self._equity(ab)
        if nav is None or free is None:
            self._log("NO_NAV_OR_BALANCE")
            return
        confirmed_nav = _num(_get(ab, "NAV")) or _num(_get(ab, "nav"))
        if confirmed_nav is not None:
            if self.peak_nav is None or confirmed_nav > self.peak_nav:
                self.peak_nav = confirmed_nav
            if confirmed_nav < 0.92 * self.peak_nav:
                self._halt("ACCOUNT_8PCT_DRAWDOWN")
                for pair, st in self.states.items():
                    if st["phase"] == "OPEN":
                        self._close(pair, "account_risk", now)
                return
        h4_event = now.hour % 4 == 1
        if h4_event and now < END:
            for pair in PAIRS:
                try:
                    self.cached[pair] = self._history_pair(pair, now)
                except Exception as exc:
                    self.cached[pair] = None
                    self._log("SIGNAL_SKIP", pair, type(exc).__name__, str(exc)[:80])

        for pair, st in self.states.items():
            snapshot = _snapshot(bd, pair)
            if snapshot is None:
                continue
            basis = snapshot["basis"]
            if st["phase"] == "OPEN":
                held = (now - st["opened"]).total_seconds() / 3600.0
                adverse = -st["side"] * (basis - st["entry_basis"])
                if adverse >= PARAMS["stop_basis"]:
                    self._close(pair, "BASIS_STOP", now)
                    continue
                if held >= PARAMS["max_hold_hours"] or now >= END:
                    self._close(pair, "TIME_OR_TERMINAL", now)
                    continue
                sig = self.cached[pair]["signal"] if self.cached[pair] else None
                if h4_event and sig is not None:
                    crossed = ((st["side"] < 0 and sig["z"] <= PARAMS["exit_z"]) or
                               (st["side"] > 0 and sig["z"] >= -PARAMS["exit_z"]))
                    if crossed:
                        self._close(pair, "H4_REVERT", now)
                continue

            if now >= END or not h4_event or st["phase"] != "FLAT":
                continue
            if st["cooldown_until"] is not None and now < st["cooldown_until"]:
                continue
            item = self.cached[pair]
            if item is None or not item["regime"]["safe"]:
                continue
            sig = item["signal"]
            if abs(sig["z"]) < PARAMS["entry_z"]:
                continue
            if sig["edge"] < PARAMS["min_edge"]:
                continue
            if abs(basis) > PARAMS["max_abs_basis"]:
                self._log("SKIP_BASIS_OUTLIER", pair, round(basis, 5))
                continue
            prev = math.log(item["future_close"] / item["spot_close"])
            if abs(basis - prev) > PARAMS["max_h1_divergence"]:
                self._log("SKIP_H1_DIVERGENCE", pair)
                continue
            hl = sig["half_life"]
            if PARAMS["use_ou_gate"] and (hl is None or hl < PARAMS["min_half_life"]
                                          or hl > PARAMS["max_half_life"]):
                continue
            s, f = PAIRS[pair]
            target_each = min(nav * PARAMS["gross_pair"] / 2, free * 0.30)
            q_s = _quantity(snapshot["spot"], self.spec[s], target_each)
            q_f = _quantity(snapshot["future"], self.spec[f], target_each)
            if q_s <= 0 or q_f <= 0:
                continue
            ns = q_s * snapshot["spot"] * self.spec[s]
            nf = q_f * snapshot["future"] * self.spec[f]
            if min(ns, nf) < PARAMS["min_pair_notional"]:
                continue
            if abs(ns - nf) / max(ns, nf) > 0.01:
                self._log("SKIP_HEDGE_IMBALANCE", pair)
                continue
            self._open(pair, q_s, q_f, -1 if sig["z"] > 0 else 1, now, basis)
            # One pair per synchronized event: available margin is not yet
            # updated until native fills are accounted for.
            break

    def on_marketdatafeed(self, md, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_openPositionfeed(self, op, oo, uo):
        pass
