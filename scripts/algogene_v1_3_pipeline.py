"""One cloud submission, bounded monitoring, platform-native result collection.

No locally reconstructed P/L, trade statistics, or altered platform settings.
"""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/v1_3/platform-responses.json"
LAST_API_FINISH = [0.0]


def redact(value, secrets):
    if isinstance(value, dict):
        private = {"api_key", "user", "user_id", "userid", "email", "token", "password"}
        return {k: "[REDACTED]" if k.lower() in private else redact(v, secrets)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
    return value


def main(*, settings_override=None, source_override=None, output_override=None,
         experiment="EXP-008", version="V1.3", on_submission=None):
    output = Path(output_override) if output_override is not None else OUTPUT
    user = os.environ.get("ALGOGENE_USER_ID", "").strip()
    key = os.environ.get("ALGOGENE_API_KEY", "").strip()
    secrets = (key, user)
    result = {"experiment": experiment, "version": version, "data_role": "Development",
              "code_commit": os.environ.get("GITHUB_SHA"),
              "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
              "workflow_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
              "status": "NOT RUN", "backtest_id": None, "task_id": None,
              "platform_responses": {}, "errors": []}
    last_finish = LAST_API_FINISH

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(redact(result, secrets), indent=2, ensure_ascii=False), encoding="utf-8")

    def call(endpoint, params, label, post=False):
        result["last_endpoint"] = endpoint
        for attempt in range(3):
            remaining = 75 - (time.monotonic() - last_finish[0])
            if remaining > 0:
                time.sleep(remaining)
            data = dict(params, user=user, api_key=key)
            request = urllib.request.Request(
                "https://algogene.com/rest/v1" + endpoint
                + ("" if post else "?" + urllib.parse.urlencode(data)),
                data=json.dumps(data).encode() if post else None,
                headers={"Content-Type": "application/json"},
                method="POST" if post else "GET")
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = json.load(response)
                clean = redact(payload, secrets)
                result["platform_responses"].setdefault(label, []).append(clean)
                save()
                limited = (isinstance(payload, dict) and payload.get("status") is not True
                           and "Exceed maximum access count" in str(payload.get("res", "")))
                if limited and attempt < 2:
                    continue
                return payload
            except urllib.error.HTTPError as exc:
                message = redact(exc.read().decode("utf-8", errors="replace"), secrets)
                result["errors"].append({"endpoint": endpoint, "http_status": exc.code, "body": message})
                save()
                if exc.code == 400 and "Exceed maximum access count" in message and attempt < 2:
                    continue
                raise
            finally:
                last_finish[0] = time.monotonic()

    save()
    if not user or not key:
        result["reason"] = "Required GitHub Secrets unavailable"
        save()
        return 2
    try:
        tasks = call("/get_current_tasks", {}, "current_tasks")
        if tasks.get("status") is not True or tasks.get("res") != []:
            result["reason"] = "Account preflight failed or another task is active; no submission"
            save()
            return 1
        settings = settings_override if settings_override is not None else json.loads((ROOT / "configs/v1_3_cloud.json").read_text())
        allowed_dates = {("2021-01", "2023-12"), ("2021-01", "2021-01")}
        allowed_dates.update((str(year) + "-01", str(year) + "-12") for year in (2021, 2022, 2023))
        if ((settings["StartDate"], settings["EndDate"]) not in allowed_dates
                or settings["dataset"] != 60 or settings["subscribeList"] != ["BTCUSD"]
                or settings["InitialCapital"] != 10000 or settings["Leverage"] != 1
                or settings["allowShortSell"] is not False
                or settings["isPositionBaseEnv"] is not False):
            raise ValueError("Unexpected experiment settings")
        result["requested_settings"] = settings
        meta = call("/meta_instrument", {"instrument": "BTCUSD"}, "contract_metadata")
        if float(meta.get("res", {}).get("contractSize", 0)) != 1:
            raise ValueError("Sizing requires contractSize=1")
        submission = call("/run_backtest", {
            "code": source_override if source_override is not None else (ROOT / "src/algogene_crypto_v1_3.py").read_text(),
            "settings": settings}, "submission", post=True)
        if submission.get("status") is not True:
            result["status"] = "SUBMISSION_REJECTED"
            save()
            return 1
        for source, target in (("runtime_id", "backtest_id"), ("task_id", "task_id")):
            value = submission.get(source)
            if not isinstance(value, str) or not value or any(c not in "0123456789_" for c in value):
                raise ValueError("Unexpected platform ID format; do not resubmit")
            result[target] = value
        result["status"] = "SUBMITTED"
        save()
        print("SUBMITTED backtest_id=" + result["backtest_id"], flush=True)
        if on_submission is not None:
            on_submission(output)
        deadline = time.monotonic() + 45 * 60
        while time.monotonic() < deadline:
            time.sleep(120)
            state = call("/task_status", {"task": "backtest", "task_id": result["task_id"]}, "task_status")
            if state.get("status") is True and state.get("res") == "DONE":
                result["status"] = "PLATFORM_TASK_DONE"
                save()
                break
        else:
            result["status"] = "PENDING"
            result["reason"] = "Monitoring window expired; retain IDs and query existing task later"
            save()
            return 1
        params = {"runmode": "backtest", "runtime_id": result["backtest_id"], "acdate": ""}
        for endpoint, label in (("/strategy_stats", "statistics"),
                                ("/strategy_logs", "console"),
                                ("/strategy_trade", "transactions"),
                                ("/strategy_pl", "daily_pl")):
            try:
                request_params = {k: v for k, v in params.items() if k != "acdate" or endpoint != "/strategy_logs"}
                payload = call(endpoint, request_params, label)
                if not isinstance(payload, dict) or payload.get("status") is False or "error" in payload:
                    result["errors"].append({"endpoint": endpoint, "reason": "Platform collection rejected; see raw response"})
            except Exception as exc:
                result["errors"].append({"endpoint": endpoint, "error_type": type(exc).__name__})
                save()
        statistics = result["platform_responses"].get("statistics", [{}])[-1]
        effective = statistics.get("setting", statistics.get("settings", {}))
        result["configuration_matches_request"] = all(
            str(effective.get(k)) == str(settings[k]) for k in ("StartDate", "EndDate", "dataset"))
        console = result["platform_responses"].get("console", [{}])[-1]
        messages = str(console.get("res", ""))
        result["strategy_error_marker_seen"] = any(
            marker in messages for marker in ("V1.3_HALTED", "V1.3_ORDER_UNCONFIRMED", "V1.0_HISTORY_ERROR", "V1.0_HISTORY_REJECTED", "V1.0_ORDER_NOT_SUCCESSFUL", "Traceback", "Error:"))
        if not result["configuration_matches_request"] or result["strategy_error_marker_seen"]:
            result["errors"].append({"reason": "Configuration mismatch or strategy error marker; inspect raw evidence"})
        result["status"] = "COLLECTED" if not result["errors"] else "COLLECTED_WITH_ERRORS"
        # These are collection/consistency statuses, never profitability claims.
        save()
        return 0
    except Exception as exc:
        result["status"] = "ERROR"
        result["errors"].append({"endpoint": result.get("last_endpoint"), "error_type": type(exc).__name__})
        save()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
