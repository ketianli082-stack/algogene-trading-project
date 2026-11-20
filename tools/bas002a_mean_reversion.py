"""BAS-002A: read-only historical spot-perpetual basis mean reversion pilot.
Fetch 4 independent hourly price series from ALGOGENE, align timestamps, verify
that prices are usable, and evaluate forward basis changes WITHOUT placing orders.
If bid/ask are unavailable, close-price results are proxies, not executable PnL.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "bas002a"
ENDPOINT = "https://algogene.com/rest/v1/history_price"
SYMBOLS = ("BTCUSD", "BTCUSDM", "ETHUSD", "ETHUSDM")
PAIRS = (("BTC", "BTCUSD", "BTCUSDM"), ("ETH", "ETHUSD", "ETHUSDM"))
ANCHORS = ("2024-12-31",)
COUNT = 720
WINDOW = 168
HORIZONS = (24, 48, 72)
Z_THRESHOLD = 2.0
SD_FLOOR_BPS = 2.0


def timestamp(v):
    if isinstance(v, (int, float)):
        if v > 1e11:
            v = v / 1000
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    if v is None:
        raise ValueError("missing timestamp")
    x = str(v).strip().replace("Z", "+00:00")
    if x.isdigit():
        return timestamp(int(x))
    d = datetime.fromisoformat(x)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat()


def numeric(x):
    try:
        n = float(x)
        return n if math.isfinite(n) and n > 0 else None
    except (ValueError, TypeError):
        return None


def normalize(payload):
    """Require an actual series, no fabricated OHLC or inferred bid/ask."""
    if not isinstance(payload, dict) or payload.get("status") is False:
        raise ValueError("API returned no successful data object")
    raw = payload.get("res")
    if isinstance(raw, dict):
        raw = [{**v, "timestamp": v.get("timestamp", k)}
               for k, v in raw.items() if isinstance(v, dict)]
    if not isinstance(raw, list) or not raw:
        raise ValueError("history res is not a nonempty list/dict")
    result = {}
    observed_fields = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        observed_fields.update(row)
        tval = next((row[k] for k in ("timestamp", "time", "date", "datetime")
                     if k in row), None)
        try:
            t = timestamp(tval)
        except (ValueError, TypeError, OverflowError):
            continue
        bid, ask = numeric(row.get("bidPrice")), numeric(row.get("askPrice"))
        if bid is not None and ask is not None and bid <= ask:
            result[t] = {"value": (bid + ask)/2, "mode": "bidask_mid"}
            continue
        c = next((numeric(row.get(k)) for k in ("close", "Close", "closePrice", "c")
                  if numeric(row.get(k)) is not None), None)
        if c is not None:
            result[t] = {"value": c, "mode": "close_proxy"}
    if not result:
        raise ValueError("no usable timestamped prices; fields=" + repr(sorted(observed_fields)))
    return result, sorted(observed_fields)


def aligned_basis(spot, perp):
    dates = sorted(set(spot) & set(perp))
    out = []
    modes = set()
    for t in dates:
        s, f = spot[t], perp[t]
        modes.update((s["mode"], f["mode"]))
        out.append((t, 10000 * (f["value"] - s["value"]) / s["value"]))
    return out, sorted(modes)


def evaluate(series):
    """Calculate future basis change strictly after a 168-observation lookback.
    Requiring exact horizon timestamps avoids mislabelling missing bars as 24h/48h/72h.
    """
    by_time = {t: b for t, b in series}
    moments = [(datetime.fromisoformat(t), t, b) for t, b in series]
    rows = []
    for i in range(WINDOW, len(moments)):
        dt, t, now = moments[i]
        hist = [b for _, _, b in moments[i-WINDOW:i]]
        last_dt = moments[i-1][0]
        first_dt = moments[i-WINDOW][0]
        if (dt-last_dt).total_seconds() > 6*3600:
            continue
        if (dt-first_dt).total_seconds() > 210*3600:
            continue
        mu = statistics.mean(hist)
        sigma = statistics.pstdev(hist)
        z = (now-mu)/max(sigma, SD_FLOOR_BPS)
        if z < Z_THRESHOLD or now <= 0:
            continue
        for h in HORIZONS:
            future = (dt.timestamp()+h*3600)
            future_t = datetime.fromtimestamp(future, tz=timezone.utc).isoformat()
            if future_t not in by_time:
                continue
            future_basis = by_time[future_t]
            rows.append({"signal_timestamp_utc": t, "horizon_hours": h,
                         "entry_basis_bp": now, "mean_prior_bp": mu,
                         "prior_sd_bp": sigma, "zscore": z,
                         "future_basis_bp": future_basis,
                         "basis_change_bp": future_basis-now,
                         "converged": future_basis < now})
    return rows


def summarize(rows):
    summary = {}
    for h in HORIZONS:
        x = [r for r in rows if r["horizon_hours"] == h]
        summary[str(h)] = {
            "signals": len(x),
            "average_change_bp": statistics.mean(r["basis_change_bp"] for r in x) if x else None,
            "median_change_bp": statistics.median(r["basis_change_bp"] for r in x) if x else None,
            "convergence_share": sum(r["converged"] for r in x)/len(x) if x else None,
        }
    return summary


def fetch(user, key, symbol, anchor, wait):
    if wait[0]:
        remaining = 75-(time.monotonic()-wait[0])
        if remaining > 0:
            time.sleep(remaining)
    params = urllib.parse.urlencode({
        "instrument": symbol, "user": user, "api_key": key,
        "count": COUNT, "interval": "H", "timestamp": anchor})
    req = urllib.request.Request(ENDPOINT+"?"+params, method="GET",
                                 headers={"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.load(resp)
    finally:
        wait[0] = time.monotonic()
    return normalize(payload)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "experiment":"BAS-002A", "status":"NOT_RUN", "phase":"PILOT",
        "source_commit":os.getenv("GITHUB_SHA"), "github_run":os.getenv("GITHUB_RUN_ID"),
        "settings":{"symbols":SYMBOLS, "anchors":ANCHORS, "requested_bar_count":COUNT,
                    "interval":"H", "lookback":WINDOW, "z_threshold":Z_THRESHOLD,
                    "horizons_hours":HORIZONS},
        "results":{}, "limitations":["Not a trading backtest. Gross basis move is not PnL.",
                                    "2024-only pilot, not a 2021-2024 study.",
                                    "Overlapping signals imply non-independent observations.",
                                    "Historical data schema and coverage must be verified."]}
    def save():
        (OUTPUT/"summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n",
                                          encoding="utf-8")
    save()
    user, key = (os.getenv("ALGOGENE_USER_ID") or "").strip(), (os.getenv("ALGOGENE_API_KEY") or "").strip()
    if not user or not key:
        report.update(status="NOT_RUN", reason="Missing ALGOGENE GitHub Actions secrets")
        save()
        return 2
    try:
        report["status"] = "RUNNING"
        save()
        wait = [0.0]
        for anchor in ANCHORS:
            prices = {}
            for symbol in SYMBOLS:
                data, fields = fetch(user, key, symbol, anchor, wait)
                prices[symbol] = data
                report.setdefault("coverage", {})[symbol] = {
                    "bars":len(data), "first":min(data), "last":max(data),
                    "source_fields": fields}
                save()
            for group, spot, perp in PAIRS:
                series, modes = aligned_basis(prices[spot], prices[perp])
                rows = evaluate(series)
                for r in rows:
                    r["asset"] = group
                    r["anchor"] = anchor
                file = OUTPUT/(group.lower()+"_signals.csv")
                with file.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["asset","anchor","signal_timestamp_utc",
                        "horizon_hours","entry_basis_bp","mean_prior_bp","prior_sd_bp",
                        "zscore","future_basis_bp","basis_change_bp","converged"])
                    writer.writeheader()
                    writer.writerows(rows)
                report["results"][group] = {
                    "aligned_bars":len(series),
                    "first":series[0][0] if series else None,
                    "last":series[-1][0] if series else None,
                    "price_modes":modes,
                    "by_horizon":summarize(rows),
                    "status":"PILOT_RESULT" if rows else "INSUFFICIENT_SIGNAL_OR_HISTORY"}
                save()
        report["status"]="COLLECTED_PILOT"
        save()
        print("BAS-002A pilot collected; inspect artifacts for price modes and results")
        return 0
    except urllib.error.HTTPError as exc:
        report["status"]="API_HTTP_ERROR"
        report["http_status"]=exc.code
        report["retry_after_present"]=bool(exc.headers.get("Retry-After"))
        report["error_type"]="HTTPError"
        report["reason_category"]=("RATE_LIMIT" if exc.code in (429, 403) else
                                   "BAD_REQUEST_OR_DATE_RANGE" if exc.code == 400 else
                                   "HTTP_ERROR")
        save()
        print("BAS-002A API HTTP",exc.code,report["reason_category"])
        return 1
    except Exception as exc:
        report["status"]="ERROR"
        report["error_type"]=type(exc).__name__
        report["error_message"]=str(exc)[:230] if isinstance(exc, (ValueError, KeyError)) else "non-data error"
        save()
        print("BAS-002A stopped:",type(exc).__name__)
        return 1


if __name__=="__main__":
    sys.exit(main())
