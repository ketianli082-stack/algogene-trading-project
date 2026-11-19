# -*- coding: utf-8 -*-
"""EXP-016: BTC/ETH spot-perpetual dual-basis mean reversion (research only).

Instruments: BTCUSD, BTCUSDM, ETHUSD, ETHUSDM.
Each trade is an equal-dollar spot/perpetual pair, not a four-leg basket.
Signals use completed historical daily bars strictly BEFORE the execution date.
No funding-rate cash flow is simulated in the source code. ALGOGENE native
statistics (not this script) determine realised results and Score_Total.
"""
import math
from datetime import datetime

from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest

# EXACT line replaced by the registered cloud experiment runner.
PARAMS = {"lookback": 60, "entry_z": 1.8, "exit_z": 0.15, "stop_z": 3.5, "max_hold_days": 20, "min_basis_edge": 0.0025, "max_basis_vol": 0.04, "gross_per_pair": 0.35}

SYMBOLS = ("BTCUSD", "BTCUSDM", "ETHUSD", "ETHUSDM")
PAIRS = {"BTC": ("BTCUSD", "BTCUSDM"), "ETH": ("ETHUSD", "ETHUSDM")}
FINAL_DATE = datetime(2025, 12, 31)


def _finite_pos(x):
    try:
        v = float(x)
        return v if math.isfinite(v) and v > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _get(obj, key, default=None):
    try:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
    except Exception:
        return default


def _dt(value):
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _basis_stats(spot, perp, lookback):
    """spot/perp are aligned oldest->newest historical closes; no future bars."""
    if len(spot) != len(perp) or len(spot) < lookback + 1:
        return None
    if any(_finite_pos(x) is None for x in spot[-lookback-1:]):
        return None
    if any(_finite_pos(x) is None for x in perp[-lookback-1:]):
        return None
    basis = [math.log(f / s) for s, f in zip(spot[-lookback-1:], perp[-lookback-1:])]
    training, current = basis[:-1], basis[-1]
    mean = sum(training) / len(training)
    sd = math.sqrt(sum((v - mean)**2 for v in training) / (len(training) - 1))
    if sd < 1e-8 or not math.isfinite(sd):
        return None
    return {"z": (current - mean) / sd, "basis": current, "mean": mean, "sd": sd,
            "edge": abs(current - mean)}


def _volume(price, contract_size, budget):
    if any(_finite_pos(v) is None for v in (price, contract_size, budget)):
        return 0
    return max(0, int(float(budget) / (float(price) * float(contract_size))))


class AlgoEvent:
    def __init__(self):
        self.specs = {}
        self.states = {p: {"phase": "FLAT", "legs": {}, "pending": set(),
                           "side": 0, "opened": None, "pending_date": None,
                           "entry_z": None, "id": 0} for p in PAIRS}
        self.last_day = None
        self.peak_equity = None
        self.halted = False
        self.halt_reason = None

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        if set(mEvt.get("subscribeList", [])) != set(SYMBOLS):
            self._halt("WRONG_SUBSCRIPTION")
        for sym in SYMBOLS:
            try:
                spec = self.evt.getContractSpec(sym)
                cs = _finite_pos(_get(spec, "contractSize"))
                if cs is None:
                    raise ValueError("Missing positive contract size")
                self.specs[sym] = cs
            except Exception:
                self._halt("UNKNOWN_CONTRACT_SPEC_" + sym)
        self.evt.start()

    def _log(self, *args):
        self.evt.consoleLog("FOUR_ASSET", *args)

    def _halt(self, reason):
        self.halted = True
        self.halt_reason = reason
        if hasattr(self, "evt"):
            self._log("HALT", reason)

    def _now(self, bd):
        ts = [_dt(_get(bd.get(sym), "timestamp")) for sym in SYMBOLS]
        if any(t is None for t in ts):
            self._log("SKIP_TIMESTAMP")
            return None
        if len(set(t.date() for t in ts)) != 1:
            self._log("SKIP_ASYNC_FEED", ts)
            return None
        return ts[0]

    def _history(self, now):
        """Use only completed bars preceding today's first decision event."""
        all_prices = {}
        all_dates = {}
        requested = max(PARAMS["lookback"] + 45, 125)
        for sym in SYMBOLS:
            raw = self.evt.getHistoricalBar(
                contract={"instrument": sym}, numOfBar=requested, interval="D")
            if not isinstance(raw, dict) or not raw:
                raise ValueError("HISTORY_EMPTY_" + sym)
            series = {}
            for ts, bar in raw.items():
                t = _dt(ts)
                price = _finite_pos(_get(bar, "c"))
                if t is not None and t.date() < now.date() and price is not None:
                    series[t.date()] = price
            if len(series) < PARAMS["lookback"] + 1:
                raise ValueError("HISTORY_SHORT_" + sym)
            all_prices[sym] = series
            all_dates[sym] = max(series)
        # No forward fill: a stale leg must not create fictitious basis changes.
        if len(set(all_dates.values())) != 1:
            raise ValueError("HISTORY_STALE_CROSS_ASSET")
        result = {}
        for pair, (spot, perp) in PAIRS.items():
            dates = sorted(set(all_prices[spot]) & set(all_prices[perp]))
            if len(dates) < PARAMS["lookback"] + 1 or dates[-1] != all_dates[spot]:
                raise ValueError("PAIR_ALIGNMENT_" + pair)
            result[pair] = (
                _basis_stats([all_prices[spot][d] for d in dates],
                             [all_prices[perp][d] for d in dates],
                             PARAMS["lookback"]),
                all_prices[spot][dates[-1]], all_prices[perp][dates[-1]])
        return result

    def _balances(self, ab):
        equity = next((_finite_pos(_get(ab, k)) for k in
                       ("nav", "equity", "capital", "balance", "accountBalance")
                       if _finite_pos(_get(ab, k)) is not None), None)
        available = _finite_pos(_get(ab, "availableBalance"))
        # ALGOGENE documents availableBalance and marginUsed in 'ab'.
        # Free cash + used margin approximates account equity when NAV absent.
        # If marginUsed itself is missing, size against free cash only and do
        # not infer a drawdown from margin-related cash movements.
        self.equity_proxy = False
        if equity is None and available is not None:
            used = _get(ab, "marginUsed")
            try:
                used = float(used)
                if not math.isfinite(used) or used < 0:
                    used = None
            except (TypeError, ValueError):
                used = None
            equity = available + (used or 0.0)
            self.equity_proxy = used is None
        if equity is None or available is None:
            self._log("NO_CONFIRMED_BALANCE", "equity=", equity, "available=", available)
            return None, None
        if not self.equity_proxy:
            self.peak_equity = max(equity, self.peak_equity or equity)
        return equity, available

    def _send_open(self, pair, spot_volume, perp_volume, direction, now, z):
        # direction +1 = long basis => buy perp / sell spot.
        s, f = PAIRS[pair]
        state = self.states[pair]
        state["id"] += 1
        state.update(phase="OPENING", legs={}, pending={s, f}, side=direction,
                     opened=now.date(), pending_date=now.date(), entry_z=z)
        for sym, vol, side in ((s, spot_volume, -direction), (f, perp_volume, direction)):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    instrument=sym, buysell=side, volume=vol, openclose="open",
                    ordertype=0, orderRef="EXP016-%s-%s-open-%s" % (pair, state["id"], sym)))
            except Exception:
                self._halt("SEND_OPEN_ERROR_" + sym)
                self._emergency_close(pair)
                return
        self._log("SENT_PAIR", pair, direction, spot_volume, perp_volume, round(z, 4))

    def _send_close(self, pair, reason, now):
        state = self.states[pair]
        if state["phase"] not in ("OPEN", "HALT") or not state["legs"]:
            return
        state["phase"] = "CLOSING"
        state["pending"] = set(state["legs"])
        state["pending_date"] = now.date()
        self._log("EXIT", pair, reason, "legs=", len(state["legs"]))
        for sym, trade_id in list(state["legs"].items()):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    tradeID=trade_id, openclose="close"))
            except Exception:
                self._halt("SEND_CLOSE_ERROR_" + sym)

    def _emergency_close(self, pair):
        state = self.states[pair]
        state["phase"] = "HALT"
        state["pending"] = set()
        # Trades for which no successful fill ID arrived cannot be safely closed.
        for sym, trade_id in list(state["legs"].items()):
            try:
                self.evt.sendOrder(AlgoAPIUtil.OrderObject(
                    tradeID=trade_id, openclose="close"))
                self._log("EMERGENCY_CLOSE_SENT", pair, sym, trade_id)
            except Exception:
                self._log("EMERGENCY_CLOSE_FAILED", pair, sym)

    def on_orderfeed(self, of):
        sym = _get(of, "instrument")
        if sym not in SYMBOLS:
            ref = str(_get(of, "orderRef", ""))
            sym = next((x for x in SYMBOLS if ref.endswith("-" + x)), None)
        if sym not in SYMBOLS:
            tid = _get(of, "tradeID")
            sym = next((x for st in self.states.values()
                        for x, known_tid in st["legs"].items() if known_tid == tid), None)
        pair = next((p for p, legs in PAIRS.items() if sym in legs), None)
        if pair is None:
            self._halt("UNMATCHED_ORDER_CALLBACK")
            return
        state = self.states[pair]
        success = _get(of, "status") == "success"
        action = _get(of, "openclose")
        if not success:
            self._halt("ORDER_NOT_SUCCESS_" + str(pair) + "_" + str(sym))
            self._emergency_close(pair)
            return
        if state["phase"] == "OPENING" and action == "open" and sym in state["pending"]:
            tid = _get(of, "tradeID")
            if tid is None:
                self._halt("MISSING_TRADE_ID_" + pair)
                self._emergency_close(pair)
                return
            state["legs"][sym] = tid
            state["pending"].remove(sym)
            if not state["pending"]:
                state["phase"] = "OPEN"
                self._log("OPEN_CONFIRMED", pair, state["id"])
        elif state["phase"] == "CLOSING" and action == "close" and sym in state["pending"]:
            state["legs"].pop(sym, None)
            state["pending"].remove(sym)
            if not state["pending"]:
                state.update(phase="FLAT", side=0, opened=None, entry_z=None)
                self._log("CLOSE_CONFIRMED", pair)
        else:
            self._halt("UNEXPECTED_ORDER_CALLBACK_" + str(pair))
            self._emergency_close(pair)

    def on_bulkdatafeed(self, isSync, bd, ab):
        if not isSync or any(sym not in bd for sym in SYMBOLS):
            return
        now = self._now(bd)
        if now is None or now.date() == self.last_day:
            return
        self.last_day = now.date()
        # Never silently carry uncertain two-leg fills forward.
        for pair, state in self.states.items():
            if state["phase"] in ("OPENING", "CLOSING") and state["pending_date"] != now.date():
                self._halt("PENDING_OVERNIGHT_" + pair)
                self._emergency_close(pair)
        if self.halted:
            return
        try:
            history = self._history(now)
        except Exception as exc:
            self._log("SKIP_HISTORY", type(exc).__name__, str(exc)[:100])
            return
        equity, available = self._balances(ab)
        if equity is None:
            return
        if not self.equity_proxy and self.peak_equity and equity < self.peak_equity * 0.88:
            self._halt("ACCOUNT_DRAWDOWN_12PCT")
            for pair, state in self.states.items():
                if state["phase"] == "OPEN":
                    self._send_close(pair, "account_drawdown", now)
            return
        for pair, (stats, spot_px, perp_px) in history.items():
            state = self.states[pair]
            if stats is None or state["phase"] not in ("OPEN", "FLAT"):
                continue
            z, vol = stats["z"], stats["sd"]
            if state["phase"] == "OPEN":
                held = (now.date() - state["opened"]).days
                closing = ((state["side"] < 0 and z <= PARAMS["exit_z"])
                           or (state["side"] > 0 and z >= -PARAMS["exit_z"])
                           or abs(z) > PARAMS["stop_z"]
                           or held >= PARAMS["max_hold_days"]
                           or now >= FINAL_DATE)
                if closing:
                    self._send_close(pair, "signal_or_risk", now)
                continue
            if now >= FINAL_DATE or abs(z) < PARAMS["entry_z"] or abs(z) > PARAMS["stop_z"]:
                continue
            if vol > PARAMS["max_basis_vol"] or stats["edge"] < PARAMS["min_basis_edge"]:
                continue
            if any(s["phase"] in ("OPENING", "CLOSING", "HALT") for s in self.states.values()):
                continue
            # Reserve only 35% gross NAV per pair; the two simultaneous pairs
            # can consume at most 70% NAV prior to contract-volume truncation.
            per_leg = min(equity * PARAMS["gross_per_pair"] / 2.0, available * 0.40)
            s, f = PAIRS[pair]
            qty_s = _volume(spot_px, self.specs[s], per_leg)
            qty_f = _volume(perp_px, self.specs[f], per_leg)
            if qty_s < 1 or qty_f < 1:
                self._log("SKIP_MIN_LOT", pair, per_leg)
                continue
            not_s = qty_s * spot_px * self.specs[s]
            not_f = qty_f * perp_px * self.specs[f]
            if abs(not_s - not_f) / max(not_s, not_f) > 0.05:
                self._log("SKIP_HEDGE_IMBALANCE", pair, not_s, not_f)
                continue
            # Basis positive -> short perp and long spot, negative -> reverse.
            self._send_open(pair, qty_s, qty_f, -1 if z > 0 else 1, now, z)
            # Account available balance may not update until fills, so only
            # open one pair per daily callback; second pair can open next day.
            break

    def on_marketdatafeed(self, md, ab):
        pass

    def on_dailyPLfeed(self, pl):
        pass

    def on_openPositionfeed(self, op, oo, uo):
        pass
