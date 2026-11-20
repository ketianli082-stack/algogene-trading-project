"""Submit exactly one BTC V1.0 ALGOGENE cloud backtest using archived proven API paths.

No TradeCost key is submitted. Do not assume platform default means zero fees.
No live trading endpoints and no automatic submission retries.
Only the 2021-2024 development set is permitted; 2025 remains untouched.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://algogene.com/rest/v1"
OUT = ROOT / "outputs" / "btc_v1_0" / "platform-evidence.json"
SOURCE = ROOT / "strategy" / "btc_v1_0_ema60.py"
CONFIG = ROOT / "config" / "btc_v1_0_cloud.json"
PUBLIC_KEYS = ("Score_Total", "TotalPnL", "AnnualSharpe", "DailySharpe",
               "maxDrawdown_pct", "maxDrawdown_amt", "TradeCnt", "WinRate",
               "simpleReturn", "profit_factor", "score_AnnualSharpe")


def load_plan():
    settings = json.loads(CONFIG.read_text(encoding="utf-8"))
    required = {
        "subscribeList": ["BTCUSD"], "StartDate": "2021-01",
        "EndDate": "2024-12", "InitialCapital": 10000,
        "BaseCurrency": "USD", "risk_free": 0,
        "Leverage": 1, "allowShortSell": False, "dataset": 60,
    }
    if any(settings.get(k) != v for k, v in required.items()):
        raise ValueError("Fixed BTC V1.0 research settings mismatch")
    if "TradeCost" in settings:
        raise ValueError("Fixed-cost field forbidden: do not submit")
    if set(settings["subscribeList"]) != {"BTCUSD"}:
        raise ValueError("Only BTCUSD is allowed")
    source = SOURCE.read_text(encoding="utf-8")
    compile(source, str(SOURCE), "exec")
    import re
    if re.search(r"(?m)^\\s*TradeCost\\s*=", source):
        raise ValueError("Strategy must not set fixed trading cost")
    return settings, source


def redact(value, secrets):
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in
                ("user", "user_id", "api_key", "authorization", "token", "password")
                else redact(v, secrets)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for token in secrets:
            if token:
                value = value.replace(token, "[REDACTED]")
    return value


def main():
    user = os.getenv("ALGOGENE_USER_ID", "").strip()
    key = os.getenv("ALGOGENE_API_KEY", "").strip()
    secrets = (user, key)
    evidence = {
        "experiment": "BTC-V1.0", "status": "NOT_RUN",
        "commit": os.getenv("GITHUB_SHA"), "run_id": os.getenv("GITHUB_RUN_ID"),
        "role": "2021-2024 development, 2025 excluded",
        "cost_note": "TradeCost omitted entirely; effective platform default unknown",
        "observations": [],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(redact(evidence, secrets), indent=2,
                                  ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    save()
    if not user or not key:
        evidence.update(status="NOT_RUN", reason="Missing configured GitHub API credentials")
        save()
        return 2
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        evidence.update(status="NOT_RUN", reason="Reruns are intentionally blocked to prevent duplicate submission")
        save()
        return 2
    try:
        settings, code = load_plan()
    except Exception as exc:
        evidence.update(status="INVALID_CONFIG", reason=type(exc).__name__)
        save()
        return 1
    evidence["requested_settings"] = settings
    save()
    last_call = [0.]

    def call(endpoint, data, post=False):
        delay = 75 - (time.monotonic() - last_call[0]) if last_call[0] else 0
        if delay > 0:
            time.sleep(delay)
        params = dict(data, user=user, api_key=key)
        request = urllib.request.Request(
            BASE + endpoint + ("" if post else "?" + urllib.parse.urlencode(params)),
            data=json.dumps(params).encode("utf-8") if post else None,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST" if post else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        finally:
            last_call[0] = time.monotonic()

    try:
        evidence["status"] = "PREFLIGHT"
        save()
        tasks = call("/get_current_tasks", {})
        if tasks.get("status") is not True or tasks.get("res") != []:
            evidence.update(status="BLOCKED", reason="Existing task or failed preflight; no submission")
            save()
            return 1
        evidence["status"] = "SUBMITTING"
        save()
        result = call("/run_backtest", {"code": code, "settings": settings}, post=True)
        if result.get("status") is not True:
            evidence.update(status="REJECTED", reason="Platform rejected submission",
                            response=redact(result, secrets))
            save()
            return 1
        runtime_id = result.get("runtime_id")
        task_id = result.get("task_id")
        if not all(isinstance(v, str) and v and all(c in "0123456789_" for c in v)
                   for v in (runtime_id, task_id)):
            evidence.update(status="AMBIGUOUS", reason="Submission succeeded but task IDs need review",
                            response=redact(result, secrets))
            save()
            return 1
        evidence.update(status="SUBMITTED", backtest_id=runtime_id, task_id=task_id)
        save()
        print("BTC V1.0 cloud backtest SUBMITTED", runtime_id, flush=True)
        deadline = time.monotonic() + 50 * 60
        while time.monotonic() < deadline:
            time.sleep(110)
            s = call("/task_status", {"task": "backtest", "task_id": task_id})
            phase = s.get("res")
            evidence["observations"].append(phase if phase in ("DONE", "IN PROGRESS", "NOT FOUND")
                                            else "UNRECOGNIZED")
            save()
            if s.get("status") is True and phase == "DONE":
                break
            if s.get("status") is True and phase == "NOT FOUND":
                evidence.update(status="TASK_NOT_FOUND")
                save()
                return 1
        else:
            evidence.update(status="PENDING", reason="Task not done before workflow deadline")
            save()
            return 1
        evidence["status"] = "COLLECTING"
        save()
        base = {"runmode": "backtest", "runtime_id": runtime_id}
        stats = call("/strategy_stats", dict(base, acdate=""))
        evidence["stats"] = redact(stats, secrets)
        effective = stats.get("settings", stats.get("setting", {}))
        evidence["effective_settings"] = redact(effective, secrets)
        perf = stats.get("performance", {})
        evidence["metrics"] = {k: perf[k] for k in PUBLIC_KEYS if isinstance(perf, dict) and k in perf}
        for endpoint, label, params in (
            ("/strategy_logs", "logs", base),
            ("/strategy_trade", "trades", dict(base, acdate="")),
            ("/strategy_pl", "daily_pl", dict(base, acdate="")),
        ):
            response = call(endpoint, params)
            evidence[label] = redact(response, secrets)
            save()
        if not isinstance(effective, dict) or any(
            str(effective.get(k)) != str(settings[k]) for k in
            ("StartDate", "EndDate", "dataset")
        ):
            evidence.update(status="INVALID_PERIOD", reason="Platform settings differ or unavailable")
        else:
            evidence["status"] = "COLLECTED"
        save()
        return 0 if evidence["status"] == "COLLECTED" else 1
    except Exception as exc:
        evidence.update(status="ERROR", reason=type(exc).__name__)
        # Network exception bodies and URLs may contain credentials; do not print them.
        save()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
