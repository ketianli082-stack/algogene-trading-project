"""Run one pre-registered V1.5 E-Fix cooldown ablation on ALGOGENE.

The workflow selects exactly one of 6, 4, or 2 hours.  Everything else is
copied from the completed V1.5-E diagnostic: BTCUSD, native 60-minute data,
2021-2024, USD 10,000, 1x, long only, 0.5% NAV S2 cost-aware sizing, and no
TradeCost setting.  The runner never retries an ambiguous submission.
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://algogene.com/rest/v1"
SOURCE_PATH = ROOT / "strategy" / "btc_v1_5_e_reentry_diagnostic60.py"
SETTINGS_PATH = ROOT / "config" / "btc_v1_1_cloud.json"
PARAM_LINE = "COOLDOWN_HOURS = 12"
VARIANTS = {
    6: ("V1.5-E-Fix-6h", "btc_v1_5_e_fix_6h"),
    4: ("V1.5-E-Fix-4h", "btc_v1_5_e_fix_4h"),
    2: ("V1.5-E-Fix-2h", "btc_v1_5_e_fix_2h"),
}


def selected_variant(environ=None):
    env = os.environ if environ is None else environ
    raw = str(env.get("E_FIX_COOLDOWN_HOURS", "")).strip()
    try:
        hours = int(raw)
    except ValueError as exc:
        raise ValueError("E_FIX_COOLDOWN_HOURS must be one of 6, 4, 2") from exc
    if hours not in VARIANTS:
        raise ValueError("E_FIX_COOLDOWN_HOURS must be one of 6, 4, 2")
    label, slug = VARIANTS[hours]
    return hours, label, slug


def build_case(hours):
    if hours not in VARIANTS:
        raise ValueError("Unregistered cooldown")
    label, slug = VARIANTS[hours]
    settings = json.loads(SETTINGS_PATH.read_text())
    required = {
        "subscribeList": ["BTCUSD"],
        "StartDate": "2021-01",
        "EndDate": "2024-12",
        "InitialCapital": 10000,
        "dataset": 60,
        "Leverage": 1,
        "allowShortSell": False,
    }
    if any(settings.get(key) != value for key, value in required.items()):
        raise ValueError("Fixed research settings mismatch")
    if "TradeCost" in settings:
        raise ValueError("Unexpected fixed-cost configuration")

    template = SOURCE_PATH.read_text()
    if template.count(PARAM_LINE) != 1:
        raise ValueError("Unexpected cooldown declaration")
    source = template.replace(PARAM_LINE, f"COOLDOWN_HOURS = {hours}", 1)
    compile(source, f"btc-v1-5-e-fix-{hours}h", "exec")
    if any(line.strip().startswith("TradeCost") for line in source.splitlines()):
        raise ValueError("Fixed-cost assignment found")
    settings = dict(
        settings,
        allowShortSell=False,
        strategyName=(
            f"BTC V1.5 E-Fix {hours}h ADX25 ATR3 EMA200 "
            "COSTRISK05pct 2021-2024"
        ),
    )
    return {
        "name": label,
        "slug": slug,
        "cooldown_hours": hours,
        "source": source,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "settings": settings,
    }


def scrub(obj, credentials):
    if isinstance(obj, dict):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in ("user", "api_key", "password", "token", "authorization")
                else scrub(value, credentials)
            )
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [scrub(value, credentials) for value in obj]
    if isinstance(obj, str):
        for credential in credentials:
            if credential:
                obj = obj.replace(credential, "[REDACTED]")
    return obj


def main():
    try:
        hours, label, slug = selected_variant()
    except ValueError:
        return 1
    out = ROOT / "outputs" / slug / "evidence.json"
    user = (os.getenv("ALGOGENE_USER_ID") or "").strip()
    key = (os.getenv("ALGOGENE_API_KEY") or "").strip()
    credentials = (user, key)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "study": label,
        "status": "NOT_RUN",
        "commit": os.getenv("GITHUB_SHA"),
        "run_id": os.getenv("GITHUB_RUN_ID"),
        "period": "2021-2024 development; 2025 excluded",
        "instrument": "BTCUSD",
        "dataset_minutes": 60,
        "initial_capital_usd": 10000,
        "leverage": 1,
        "risk_fraction_nav": 0.005,
        "cooldown_hours": hours,
        "baseline": "V1.5-C/E 12-hour cooldown; native Score_Total 57.354357",
        "costs": "TradeCost omitted. Estimated friction affects S2 sizing only; native results gross.",
        "experiments": [],
    }

    def save():
        out.write_text(
            json.dumps(scrub(report, credentials), indent=2, ensure_ascii=False, default=str) + "\n"
        )

    save()
    if not user or not key:
        report["status"] = "NO_CREDENTIALS"
        save()
        return 1
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        report["status"] = "RERUN_BLOCKED"
        save()
        return 1
    try:
        case = build_case(hours)
    except Exception as exc:
        report.update(status="PLAN_ERROR", error_type=type(exc).__name__)
        save()
        return 1

    report["submitted_source_sha256"] = case["source_sha256"]
    last_call = [0.0]

    def call(path, data, post=False):
        if last_call[0]:
            wait = 75 - (time.monotonic() - last_call[0])
            if wait > 0:
                time.sleep(wait)
        payload = dict(data, user=user, api_key=key)
        request = urllib.request.Request(
            API + path + ("" if post else "?" + urllib.parse.urlencode(payload)),
            data=json.dumps(payload).encode() if post else None,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST" if post else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        finally:
            last_call[0] = time.monotonic()

    row = {
        "name": case["name"],
        "cooldown_hours": hours,
        "source_sha256": case["source_sha256"],
        "status": "PREFLIGHT",
        "observations": [],
    }
    report["experiments"].append(row)
    report["status"] = "RUNNING"
    save()
    try:
        tasks = call("/get_current_tasks", {})
        if tasks.get("status") is not True or tasks.get("res") != []:
            row.update(status="BLOCKED", reason="Outstanding task or preflight failed")
            report["status"] = "STOPPED"
            save()
            return 1
        row["status"] = "SUBMITTING"
        save()
        submission = call(
            "/run_backtest",
            {"code": case["source"], "settings": case["settings"]},
            post=True,
        )
        if submission.get("status") is not True:
            row.update(status="REJECTED", response=scrub(submission, credentials))
            report["status"] = "STOPPED"
            save()
            return 1
        runtime_id, task_id = submission.get("runtime_id"), submission.get("task_id")
        if not all(
            isinstance(value, str)
            and value
            and all(char in "0123456789_" for char in value)
            for value in (runtime_id, task_id)
        ):
            row.update(status="AMBIGUOUS", response=scrub(submission, credentials))
            report["status"] = "STOPPED"
            save()
            return 1
        row.update(status="SUBMITTED", backtest_id=runtime_id, task_id=task_id)
        save()
        print("Submitted", label, runtime_id, flush=True)
        deadline = time.monotonic() + 45 * 60
        while time.monotonic() < deadline:
            time.sleep(110)
            state = call("/task_status", {"task": "backtest", "task_id": task_id})
            phase = state.get("res")
            row["observations"].append(
                phase if phase in ("DONE", "IN PROGRESS", "NOT FOUND") else "UNKNOWN"
            )
            save()
            if state.get("status") is True and phase == "DONE":
                break
            if state.get("status") is True and phase == "NOT FOUND":
                row["status"] = "TASK_NOT_FOUND"
                report["status"] = "STOPPED"
                save()
                return 1
        if not row["observations"] or row["observations"][-1] != "DONE":
            row["status"] = "PENDING"
            report["status"] = "STOPPED"
            save()
            return 1

        row["status"] = "COLLECTING"
        save()
        params = {"runmode": "backtest", "runtime_id": runtime_id}
        stats = call("/strategy_stats", dict(params, acdate=""))
        row["stats"] = scrub(stats, credentials)
        settings = stats.get("setting", stats.get("settings", {}))
        row["effective_settings"] = scrub(settings, credentials)
        performance = stats.get("performance", {})
        metric_keys = (
            "Score_Total",
            "TotalPnL",
            "AnnualSharpe",
            "maxDrawdown_pct",
            "TradeCnt",
            "WinRate",
            "profit_factor",
            "simpleReturn",
        )
        row["metrics"] = {
            key: performance[key]
            for key in metric_keys
            if isinstance(performance, dict) and key in performance
        }
        for path, field, arguments in (
            ("/strategy_logs", "logs", params),
            ("/strategy_trade", "trades", dict(params, acdate="")),
            ("/strategy_pl", "daily_pl", dict(params, acdate="")),
        ):
            row[field] = scrub(call(path, arguments), credentials)
            save()

        valid = isinstance(settings, dict) and all(
            str(settings.get(key)) == str(case["settings"][key])
            for key in ("StartDate", "EndDate", "dataset", "InitialCapital", "Leverage")
        )
        logs = json.dumps(row.get("logs", {}), ensure_ascii=False)
        fatal_markers = (
            "STOP_ANCHOR_MISSING_HALT",
            "DIRECTION_MISMATCH_HALT",
            "ORDER_OUTCOME_UNKNOWN_HALT",
            "CLOSE_OUTCOME_UNKNOWN_HALT",
            "PARTIAL_FILL_HALT",
            "UNKNOWN_TRADE_ID_HALT",
            "INVALID_FILL_HALT",
            "Traceback",
        )
        if not valid:
            row["status"] = "INVALID_SETTINGS"
        elif any(marker in logs for marker in fatal_markers):
            row["status"] = "STRATEGY_ERROR"
        elif not isinstance(performance, dict) or float(performance.get("TradeCnt", 0)) <= 0:
            row["status"] = "NO_TRADES"
        else:
            row["status"] = "COLLECTED"
    except Exception as exc:
        row.update(status="ERROR", error_type=type(exc).__name__)
    report["status"] = "COLLECTED" if row["status"] == "COLLECTED" else "STOPPED"
    save()
    return 0 if report["status"] == "COLLECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
