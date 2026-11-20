# -*- coding: utf-8 -*-
"""EXP-020: percent-cost-aware execution and gap/shock mean-reversion filters.

Research backtest only. Never request the ALGOGENE H4 interval or dataset 240.
ALGOGENE historical bar timestamps are CLOSE times; at decision time T only
bars with timestamp < T are eligible. H4 ends at UTC 00/04/08/12/16/20,
H24 ends at UTC 00. Four/six-hour frames are composed from complete H1 bars.
Pair data validation is independent for BTC and ETH; no stale leg fill-forward.
"""
import math
from datetime import datetime, timedelta, timezone
from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest

# Exact substitution line for registered EXP-018 cloud candidates.
PARAMS = {"lookback_h4": 42, "entry_z": 2.0, "exit_z": 0.4, "stop_basis": 0.0075, "max_hold_hours": 36, "max_abs_basis": 0.025, "max_h1_divergence": 0.006, "max_daily_move": 0.06, "min_edge": 0.002, "gross_pair": 0.10, "min_pair_notional": 1000, "min_half_life": 0.75, "max_half_life": 24.0, "use_ou_gate": False, "cooldown_hours": 18, "stop_cooldown_hours": 48, "max_h1_leg_move": 0.03, "fee_rate": 0.0005, "min_net_expected_profit_usd": 50, "max_recent_h1_basis_jump": 0.006, "max_recent_4h_basis_range": 0.012}

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
        # Normalize explicitly offset timestamps to UTC before matching.
        if t.tzinfo is not None:
            t = t.astimezone(timezone.utc)
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


def _percent_fee(price, qty, contract_size):
    """Charge fee on actual filled notional for BOTH open and close events."""
    if None in (_num(price), _num(qty), _num(contract_size)):
        raise ValueError("FILL_COST_INPUT_MISSING")
    return float(price) * float(qty) * float(contract_size) * PARAMS["fee_rate"]


def _recent_basis_risk(spot_hours, future_hours, recent):
    """Independent risk check of 5 contiguous completed paired H1 closes."""
    stamps = [recent - timedelta(hours=i) for i in range(4, -1, -1)]
    if any(t not in spot_hours or t not in future_hours for t in stamps):
        return None
    vals = [math.log(future_hours[t]["c"] / spot_hours[t]["c"]) for t in stamps]
    return {"max_h1_basis_jump": max(abs(vals[i]-vals[i-1]) for i in range(1, 5)),
            "h4_basis_range": max(vals)-min(vals)}



class AlgoEvent:
    def __init__(self):
        self.last_hour = None
        self.pair_last_hour = {"BTC": None, "ETH": None}
        self.peak_nav = None
        self.halted = False
        self.spec = {}
        self.cached = {"BTC": None, "ETH": None}
        # Virtual cash charge: platform TradeCost=0, real fee is shadow ledger.
        self.fee_total = 0.0
        self.fee_events = 0
        self.fee_by_year = {}
        self.fill_entries = {}
        self.realized_gross = 0.0
        self.cost_final_logged = False
        self.diag = {}
        self.states = {
            p: {"phase": "FLAT", "legs": {}, "pending": set(), "pending_at": None,
                "side": 0, "opened": None, "entry_basis": None,
                "cooldown_until": None, "exit_reason": None, "serial": 0}
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

    def _diag_mark(self, pair, when, reason):
        if when is None: return
        year = str(when.year)
        if year not in self.diag: self.diag[year] = {}
        if pair not in self.diag[year]: self.diag[year][pair] = {}
        d = self.diag[year][pair]
        d[reason] = d.get(reason, 0) + 1

    def _log(self, *args):
        self.evt.consoleLog("EXP020", *args)

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
        # EXP018 H1-vs-resampled-H4 close comparison was tautological.
        # Evaluate 4 independent basis changes using 5 complete paired H1 bars.
        basis_risk = _recent_basis_risk(s_hours, f_hours, recent)
        if basis_risk is None:
            raise ValueError("RECENT_H1_PAIR_GAP")
        return {"signal": sig, "regime": regime,
                "spot_close": s_hours[recent]["c"],
                "future_close": f_hours[recent]["c"],
                "basis_risk": basis_risk}

    def _equity(self, ab):
        nav = _num(_get(ab, "NAV")) or _num(_get(ab, "nav")) or _num(_get(ab, "equity"))
        free = _num(_get(ab, "availableBalance"))
        if nav is None and free is not None:
            # Fallback only for sizing, not for inference about max drawdown.
            nav = free
        return nav, free

    def _book_fill(self, of, symbol, pair):
        """Record real confirmed fill and corresponding percent cash fee."""
        price = _num(_get(of, "fill_price"))
        qty = _num(_get(of, "fill_volume"))
        if price is None or qty is None:
            self._halt("MISSING_ACTUAL_FILL_PRICE_OR_VOLUME_" + symbol)
            return False
        fee = _percent_fee(price, qty, self.spec.get(symbol))
        self.fee_total += fee
        self.fee_events += 1
        stamp = self.pair_last_hour[pair] or self.last_hour
        year = str(stamp.year) if stamp is not None else "unknown"
        self.fee_by_year[year] = self.fee_by_year.get(year, 0.0) + fee
        action = _get(of, "openclose")
        self._diag_mark(pair, stamp, "FILL_" + str(action).upper())
        trade = _get(of, "tradeID")
        if action == "open":
            side = self.states[pair]["side"]
            sign = -side if symbol == PAIRS[pair][0] else side
            self.fill_entries[trade] = (symbol, sign, price, qty)
        elif action == "close":
            previous = self.fill_entries.get(trade)
            if (previous is None or previous[0] != symbol or
                    abs(previous[3] - qty) > 0.000001):
                self._halt("FILL_PAIR_MISMATCH_" + symbol)
                return False
            self.realized_gross += (previous[1] * qty * (price - previous[2]) *
                                    self.spec[symbol])
            del self.fill_entries[trade]
        return True

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
        state["exit_reason"] = None
        for symbol, qty, sign in ((s, quantity_s, -side), (f, quantity_f, side)):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    instrument=symbol, openclose="open", buysell=sign,
                    volume=qty, ordertype=0,
                    orderRef="EXP020-%s-%s-%s" % (
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
        state["exit_reason"] = reason
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
            if not self._book_fill(of, symbol, pair):
                self._rescue(pair)
                return
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
            if not self._book_fill(of, symbol, pair):
                self._rescue(pair)
                return
            del state["legs"][symbol]
            state["pending"] = {x for x in state["pending"] if x != symbol}
            if not state["pending"]:
                state["phase"] = "FLAT"
                when = self.pair_last_hour[pair] or self.last_hour
                delay = (PARAMS["stop_cooldown_hours"]
                         if state["exit_reason"] == "BASIS_STOP"
                         else PARAMS["cooldown_hours"])
                state["cooldown_until"] = (when + timedelta(hours=delay)
                                           if when is not None else None)
                state["opened"] = None
                state["entry_basis"] = None
                state["side"] = 0
                self._log("PAIR_CLOSED", pair)
        else:
            self._halt("UNEXPECTED_ORDER_CALLBACK_" + pair)
            self._rescue(pair)

    def on_bulkdatafeed(self, isSync, bd, ab):
        if not isinstance(bd, dict):
            return
        # isSync describes synchrony across ALL subscribed instruments.
        # BTC and ETH pairs can be synchronized independently even when
        # isSync=False because the other pair is stale; never use a stale leg.
        active = {}
        for pair, (spot, future) in PAIRS.items():
            if spot not in bd or future not in bd:
                continue
            ts = _time(_get(bd[spot], "timestamp"))
            tf = _time(_get(bd[future], "timestamp"))
            if ts is None or tf != ts or ts.minute != 0 or ts.second != 0:
                continue
            previous = self.pair_last_hour[pair]
            if previous is None or ts > previous:
                active[pair] = ts
        if not active:
            return
        now = max(active.values())
        self.last_hour = now
        for pair, ts in active.items():
            self.pair_last_hour[pair] = ts
            self._diag_mark(pair, ts, "SYNC_H1")
        for pair, state in self.states.items():
            ts = active.get(pair)
            if (ts is not None and state["phase"] in ("OPENING", "CLOSING")
                    and state["pending_at"] is not None
                    and state["pending_at"] < ts):
                self._halt("PENDING_ORDER_OVER_HOUR_" + pair)
                self._rescue(pair)
        if self.halted:
            return
        nav, free = self._equity(ab)
        if nav is None or free is None:
            for pair, ts in active.items():
                self._diag_mark(pair, ts, "NO_NAV_OR_BALANCE")
            self._log("NO_NAV_OR_BALANCE")
            return
        # Platform native fee is zero; adjust strategic risk and sizing NAV
        # by the cumulative ACTUAL proportional fill fees in this ledger.
        nav -= self.fee_total
        free -= self.fee_total
        if nav <= 0 or free <= 0:
            self._halt("COST_ADJUSTED_NAV_OR_BALANCE_NONPOSITIVE")
            return
        confirmed_nav = _num(_get(ab, "NAV")) or _num(_get(ab, "nav"))
        if confirmed_nav is not None:
            confirmed_nav -= self.fee_total
        if confirmed_nav is not None:
            if self.peak_nav is None or confirmed_nav > self.peak_nav:
                self.peak_nav = confirmed_nav
            if confirmed_nav < 0.92 * self.peak_nav:
                self._halt("ACCOUNT_8PCT_DRAWDOWN")
                for pair, st in self.states.items():
                    if st["phase"] == "OPEN":
                        self._close(pair, "account_risk", now)
                return
        for pair, ts in active.items():
            if ts.hour % 4 == 1 and ts < END:
                try:
                    self.cached[pair] = self._history_pair(pair, ts)
                    self._diag_mark(pair, ts, "HISTORY_OK")
                except Exception as exc:
                    self.cached[pair] = None
                    self._diag_mark(pair, ts, "HISTORY_" + str(exc)[:55])
                    self._log("SIGNAL_SKIP", pair, type(exc).__name__, str(exc)[:80])

        for pair, now in active.items():
            st = self.states[pair]
            h4_event = now.hour % 4 == 1
            if h4_event: self._diag_mark(pair, now, "H4_EVENT")
            snapshot = _snapshot(bd, pair)
            if snapshot is None:
                self._diag_mark(pair, now, "SNAPSHOT_INVALID")
                continue
            basis = snapshot["basis"]
            if st["phase"] == "OPEN":
                elapsed = now - st["opened"]
                held = elapsed.days * 24 + elapsed.seconds / 3600.0
                adverse = -st["side"] * (basis - st["entry_basis"])
                if adverse >= PARAMS["stop_basis"]:
                    self._close(pair, "BASIS_STOP", now)
                    continue
                if held >= PARAMS["max_hold_hours"] or now >= END:
                    self._close(pair, "TIME_OR_TERMINAL", now)
                    continue
                sig = self.cached[pair]["signal"] if self.cached[pair] else None
                # Monitor convergence at each H1 event rather than waiting
                # four hours for the next H4 signal refresh.
                if sig is not None:
                    tolerance = sig["scale"] * PARAMS["exit_z"]
                    crossed = ((st["side"] < 0 and basis <= sig["mean"] + tolerance) or
                               (st["side"] > 0 and basis >= sig["mean"] - tolerance))
                    if crossed:
                        self._close(pair, "H1_REVERT", now)
                continue

            if now >= END or not h4_event or st["phase"] != "FLAT":
                if h4_event and now < END and st["phase"] != "FLAT": self._diag_mark(pair, now, "POSITION_BUSY")
                continue
            if st["cooldown_until"] is not None and now < st["cooldown_until"]:
                self._diag_mark(pair, now, "COOLDOWN")
                continue
            item = self.cached[pair]
            if item is None or not item["regime"]["safe"]:
                self._diag_mark(pair, now, "HISTORY_UNAVAILABLE" if item is None else "REGIME_UNSAFE")
                continue
            shock = item["basis_risk"]
            if (shock["max_h1_basis_jump"] > PARAMS["max_recent_h1_basis_jump"] or
                    shock["h4_basis_range"] > PARAMS["max_recent_4h_basis_range"]):
                self._diag_mark(pair, now, "BASIS_SHOCK")
                self._log("SKIP_RECENT_BASIS_SHOCK", pair,
                          round(shock["max_h1_basis_jump"], 6))
                continue
            sig = item["signal"]
            if abs(sig["z"]) < PARAMS["entry_z"]:
                self._diag_mark(pair, now, "ZSCORE_SMALL")
                continue
            if sig["edge"] < PARAMS["min_edge"]:
                self._diag_mark(pair, now, "EDGE_SMALL")
                continue
            if abs(basis) > PARAMS["max_abs_basis"]:
                self._diag_mark(pair, now, "BASIS_OUTLIER")
                self._log("SKIP_BASIS_OUTLIER", pair, round(basis, 5))
                continue
            prev = math.log(item["future_close"] / item["spot_close"])
            if abs(basis - prev) > PARAMS["max_h1_divergence"]:
                self._diag_mark(pair, now, "H1_DIVERGENCE")
                self._log("SKIP_H1_DIVERGENCE", pair)
                continue
            # Both matched legs must be plausible independently. A near-zero
            # spread can hide an abrupt opposing move in both quote sources.
            spot_jump = abs(math.log(snapshot["spot"] / item["spot_close"]))
            future_jump = abs(math.log(snapshot["future"] / item["future_close"]))
            if max(spot_jump, future_jump) > PARAMS["max_h1_leg_move"]:
                self._diag_mark(pair, now, "H1_PRICE_SHOCK")
                self._log("SKIP_H1_PRICE_SHOCK", pair)
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
                self._diag_mark(pair, now, "ZERO_QUANTITY")
                continue
            ns = q_s * snapshot["spot"] * self.spec[s]
            nf = q_f * snapshot["future"] * self.spec[f]
            if min(ns, nf) < PARAMS["min_pair_notional"]:
                self._diag_mark(pair, now, "SMALL_NOTIONAL")
                continue
            if abs(ns - nf) / max(ns, nf) > 0.01:
                self._diag_mark(pair, now, "HEDGE_IMBALANCE")
                self._log("SKIP_HEDGE_IMBALANCE", pair)
                continue
            # Use current quote, not stale H4 basis, for directional edge.
            # Reserve the fees for 4 fills: open and close, spot and future.
            side = -1 if sig["z"] > 0 else 1
            current_edge = -side * (basis - sig["mean"])
            estimated_4fill_fee = 2.0 * (ns + nf) * PARAMS["fee_rate"]
            net_expected = min(ns, nf) * current_edge - estimated_4fill_fee
            if current_edge <= 0 or net_expected < PARAMS["min_net_expected_profit_usd"]:
                self._diag_mark(pair, now, "PERCENT_COST_EDGE")
                self._log("SKIP_PERCENT_COST_EDGE", pair, round(net_expected, 2))
                continue
            self._diag_mark(pair, now, "ENTRY_SENT")
            self._open(pair, q_s, q_f, side, now, basis)
            # One pair per synchronized event: available margin is not yet
            # updated until native fills are accounted for.
            break

        # One final cumulative ledger survives console retention truncation.
        if (self.last_hour >= END and not self.cost_final_logged and
                all(st["phase"] == "FLAT" for st in self.states.values())):
            self.cost_final_logged = True
            self._log("DIAG_FINAL", str(self.diag))
            self._log("COST_FINAL", round(self.fee_total, 6),
                      round(self.realized_gross, 6),
                      round(self.realized_gross - self.fee_total, 6),
                      self.fee_events, str(self.fee_by_year))

    def on_marketdatafeed(self, md, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_openPositionfeed(self, op, oo, uo):
        pass
