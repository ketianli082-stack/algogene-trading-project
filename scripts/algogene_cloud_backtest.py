"""Submit once to ALGOGENE cloud; never call live trading endpoints.

Contract: https://algogene.com/apidoc.yaml, /run_backtest and /task_status.
Only allowlisted response fields are published; credentials and raw responses
are never logged. An ambiguous submission failure must not be auto-retried.
"""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://algogene.com/rest/v1"


def main():
    user = os.environ.get("ALGOGENE_USER_ID", "").strip()
    key = os.environ.get("ALGOGENE_API_KEY", "").strip()
    result = {"status": "NOT RUN", "backtest_id": None, "task_id": None,
              "code_commit": os.environ.get("GITHUB_SHA"), "observations": [],
              "data_role": "Development", "version": os.environ.get("STRATEGY_VERSION", "V1.0")}

    def save():
        output = ROOT / "outputs" / "cloud-backtest.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)

    last_call = [0.0]

    def call(path, params, post=False):
        result["last_endpoint"] = path
        data = dict(params, user=user, api_key=key)
        request = urllib.request.Request(
            BASE + path if post else BASE + path + "?" + urllib.parse.urlencode(data),
            data=json.dumps(data).encode() if post else None,
            headers={"Content-Type": "application/json"},
            method="POST" if post else "GET",
        )
        for attempt in range(3):
            delay = 75 - (time.monotonic() - last_call[0])
            if delay > 0:
                time.sleep(delay)
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = json.load(response)
                # Retry only an explicit server rate-limit rejection, never an
                # ambiguous POST timeout or successful submission.
                if (payload.get("status") is not True
                        and "Exceed maximum access count" in str(payload.get("res", ""))
                        and attempt < 2):
                    result.setdefault("rate_limit_retries", []).append(path)
                    continue
                return payload
            except urllib.error.HTTPError as exc:
                message = exc.read().decode("utf-8", errors="replace")[:2000]
                for secret in (key, user):
                    if secret:
                        message = message.replace(secret, "[REDACTED]")
                result["http_error"] = {"endpoint": path, "status": exc.code, "message": message}
                if exc.code == 400 and "Exceed maximum access count" in message and attempt < 2:
                    result.setdefault("rate_limit_retries", []).append(path)
                    continue
                raise
            finally:
                last_call[0] = time.monotonic()

    if not user or not key:
        result["reason"] = "Required GitHub Secrets unavailable: ALGOGENE_USER_ID / ALGOGENE_API_KEY"
        save()
        return 2
    try:
        current = call("/get_current_tasks", {})
        if current.get("status") is not True or current.get("res") != []:
            result["reason"] = "Preflight failed or account has outstanding tasks; no submission"
            save()
            return 1
        settings = json.loads((ROOT / os.environ.get("STRATEGY_CONFIG", "configs/v1_0_cloud.json")).read_text())
        if settings["StartDate"] < "2021-01" or settings["EndDate"] > "2023-12":
            raise ValueError("Development runner refuses validation/final-test dates")
        metadata = call("/meta_instrument", {"instrument": "BTCUSD"}).get("res", {})
        result["contract"] = {k: metadata.get(k) for k in ("contractSize", "settleCurrency", "producttype")}
        if float(metadata.get("contractSize", 0)) != 1:
            raise ValueError("Fixed-volume capital check requires verified contractSize=1")
        result["settings"] = settings
        submitted = call("/run_backtest", {
            "code": (ROOT / os.environ.get("STRATEGY_SOURCE", "src/algogene_crypto_v1_0.py")).read_text(),
            "settings": settings,
        }, post=True)
        if submitted.get("status") is not True:
            message = str(submitted.get("res", submitted.get("msg", "No error detail returned")))[:2000]
            for secret in (key, user):
                if secret:
                    message = message.replace(secret, "[REDACTED]")
            result["submission_message"] = message
            result.update(status="FAIL", reason="Platform rejected backtest submission")
            save()
            return 1
        for source, target in (("runtime_id", "backtest_id"), ("task_id", "task_id")):
            value = submitted.get(source)
            if not isinstance(value, str) or not value or any(c not in "0123456789_" for c in value):
                raise ValueError("Unexpected platform ID format")
            result[target] = value
        result["status"] = "SUBMITTED"
        save()
        for _ in range(8):
            time.sleep(60)
            state = call("/task_status", {"task": "backtest", "task_id": result["task_id"]})
            phase = state.get("res")
            result["observations"].append(phase if phase in ("DONE", "IN PROGRESS", "NOT FOUND") else "UNRECOGNIZED")
            if state.get("status") is True and phase == "DONE":
                result["status"] = "DONE"
                # DONE describes task completion, not a successful trade or profit.
                stats = call("/strategy_stats", {"runmode": "backtest", "runtime_id": result["backtest_id"], "acdate": ""})
                values = stats.get("performance", {})
                if isinstance(values, dict):
                    result["metrics"] = {k: values[k] for k in ("TradeCnt", "TotalPnL", "AnnualSharpe", "DailySharpe", "maxDrawdown_pct", "maxDrawdown_amt", "simpleReturn", "WinRate") if k in values and isinstance(values[k], (int, float))}
                effective = stats.get("settings", stats.get("setting", {}))
                result["effective_settings"] = {k: effective.get(k) for k in settings}
                result["effective_cost_settings"] = {k: effective.get(k, "UNKNOWN") for k in ("TradeCost", "commission", "slippage", "funding")}
                matches = all(str(effective.get(k)) == str(settings[k]) for k in ("StartDate", "EndDate"))
                result["period_matches_request"] = matches
                result["dataset_matches_request"] = str(effective.get("dataset")) == str(settings["dataset"])
                matches = matches and result["dataset_matches_request"]
                if not matches:
                    result["status"] = "INVALID_PERIOD"
                    result["reason"] = "Platform effective dates differ from requested Development dates; exclude performance from research"
                logs = call("/strategy_logs", {"runmode": "backtest", "runtime_id": result["backtest_id"]})
                messages = str(logs.get("res", ""))
                for secret in (key, user):
                    if secret:
                        messages = messages.replace(secret, "[REDACTED]")
                result["platform_logs"] = messages
                if "V1.1_HALTED" in messages or "V1.1_ORDER_UNCONFIRMED" in messages:
                    result["status"] = "STRATEGY_ERROR"
                    matches = False
                save()
                return 0 if matches else 1
        result["status"] = "PENDING"
    except Exception as exc:
        result.update(status="ERROR", reason=type(exc).__name__)
        # Never print exception text: network errors can contain credential URLs.
    save()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
