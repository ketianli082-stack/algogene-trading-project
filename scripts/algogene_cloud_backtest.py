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
              "code_commit": os.environ.get("GITHUB_SHA"), "observations": []}

    def save():
        output = ROOT / "outputs" / "cloud-backtest.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))

    def call(path, params, post=False):
        data = dict(params, user=user, api_key=key)
        request = urllib.request.Request(
            BASE + path if post else BASE + path + "?" + urllib.parse.urlencode(data),
            data=json.dumps(data).encode() if post else None,
            headers={"Content-Type": "application/json"},
            method="POST" if post else "GET",
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)

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
        settings = json.loads((ROOT / "configs/v1_0_cloud.json").read_text())
        result["settings"] = settings
        submitted = call("/run_backtest", {
            "code": (ROOT / "src/algogene_crypto_v1_0.py").read_text(),
            "settings": settings,
        }, post=True)
        if submitted.get("status") is not True:
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
                stats = call("/strategy_stats", {"runmode": "backtest", "runtime_id": result["backtest_id"]})
                values = stats.get("res", {})
                if isinstance(values, dict):
                    result["metrics"] = {k: values[k] for k in ("TradeCnt", "TotalPnL", "DailySharpe") if k in values and isinstance(values[k], (int, float))}
                save()
                return 0
        result["status"] = "PENDING"
    except Exception as exc:
        result.update(status="ERROR", reason=type(exc).__name__)
        # Never print exception text: network errors can contain credential URLs.
    save()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
