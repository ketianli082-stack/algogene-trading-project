"""Read-only ALGOGENE REST credential and BTCUSD history check.

Credentials are read from environment variables and never printed. This script
does not call account, session, or order endpoints.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


ENDPOINT = "https://algogene.com/rest/v1/history_price"


def main():
    user_id = os.environ.get("ALGOGENE_USER_ID", "").strip()
    api_key = os.environ.get("ALGOGENE_API_KEY", "").strip()
    timestamp = os.environ.get("ALGOGENE_HISTORY_TIMESTAMP", "2026-11-03").strip()
    if not user_id or not api_key:
        print("NOT RUN: ALGOGENE_USER_ID and ALGOGENE_API_KEY are required")
        return 2

    params = urllib.parse.urlencode(
        {
            "instrument": "BTCUSD",
            "user": user_id,
            "api_key": api_key,
            "count": 3,
            "interval": "H",
            "timestamp": timestamp,
        }
    )
    request = urllib.request.Request(
        "%s?%s" % (ENDPOINT, params),
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print("FAIL: ALGOGENE returned HTTP %s" % exc.code)
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print("FAIL: read-only history check failed (%s)" % type(exc).__name__)
        return 1

    bars = payload.get("res") if isinstance(payload, dict) else None
    if not isinstance(bars, list) or not bars:
        print("FAIL: response did not contain a non-empty res list")
        return 1

    fields = sorted(str(key) for key in bars[-1].keys())
    print("PASS: BTCUSD history returned %s bar(s); fields=%s" % (len(bars), fields))
    return 0


if __name__ == "__main__":
    sys.exit(main())
