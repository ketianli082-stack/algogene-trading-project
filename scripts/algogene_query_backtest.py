"""Read existing V1.0 results without submitting a new backtest."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

RUNTIME_ID = "20261116_101506_803491"


def main():
    user = os.environ["ALGOGENE_USER_ID"]
    key = os.environ["ALGOGENE_API_KEY"]
    result = {"backtest_id": RUNTIME_ID, "queries": {}}
    for endpoint in ("strategy_logs", "strategy_stats"):
        params = dict(user=user, api_key=key, runtime_id=RUNTIME_ID, runmode="backtest")
        if endpoint == "strategy_stats":
            params["acdate"] = ""
        request = urllib.request.Request(
            "https://algogene.com/rest/v1/" + endpoint + "?" + urllib.parse.urlencode(params),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if endpoint == "strategy_logs":
                logs = str(payload.get("res", ""))
                for secret in (key, user):
                    if secret:
                        logs = logs.replace(secret, "[REDACTED]")
                result["queries"][endpoint] = {"logs": logs}
            else:
                result["queries"][endpoint] = {
                    "performance": payload.get("performance"),
                    "response_fields": sorted(payload.keys()),
                }
        except urllib.error.HTTPError as exc:
            # Read the API error body, but redact credentials before recording it.
            body = exc.read().decode("utf-8", errors="replace")[:4000]
            for secret in (key, user):
                if secret:
                    body = body.replace(secret, "[REDACTED]")
            result["queries"][endpoint] = {"http_status": exc.code, "message": body}
        except Exception as exc:
            result["queries"][endpoint] = {"error": type(exc).__name__}
    output = Path("outputs/cloud-query.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
