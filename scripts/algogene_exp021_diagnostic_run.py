"""EXP-021-DIAGNOSTIC: two independent date-scoped runs, exact frozen EXP020 source, omitted native TradeCost.

Only uses the backtest REST endpoints; never calls live order APIs.
Records the unmodified native Score_Total and performance as evidence.
An ambiguous submission or collection failure stops further candidates.
"""
import ast
import re
import hashlib
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/exp021_diagnostic"
API = "https://algogene.com/rest/v1"
INSTRUMENTS = ["BTCUSD", "BTCUSDM", "ETHUSD", "ETHUSDM"]
PARAM_LINE = "PARAMS = {\"lookback_h4\": 42, \"entry_z\": 2.0, \"exit_z\": 0.4, \"stop_basis\": 0.0075, \"max_hold_hours\": 36, \"max_abs_basis\": 0.025, \"max_h1_divergence\": 0.006, \"max_daily_move\": 0.06, \"min_edge\": 0.002, \"gross_pair\": 0.10, \"min_pair_notional\": 1000, \"min_half_life\": 0.75, \"max_half_life\": 24.0, \"use_ou_gate\": False, \"cooldown_hours\": 18, \"stop_cooldown_hours\": 48, \"max_h1_leg_move\": 0.03, \"fee_rate\": 0.0005, \"min_net_expected_profit_usd\": 50, \"max_recent_h1_basis_jump\": 0.006, \"max_recent_4h_basis_range\": 0.012}"
FIELDS = ("Score_Total", "score_AnnualSharpe", "score_AvgDrawdownDuration",
          "score_Rsquare", "score_TradePerDay", "score_WinRate",
          "score_maxDrawdown_pct", "TotalPnL", "AnnualSharpe",
          "maxDrawdown_pct", "TradeCnt", "profit_factor", "WinRate",
          "AvgDrawdownDuration", "maxDrawdownDuration", "TradeCntPerMonth")


def scrub(data, secrets):
    if isinstance(data, dict):
        return {k: ("[REDACTED]" if str(k).lower() in
                    ("user", "user_id", "api_key", "password", "token", "email")
                    else scrub(v, secrets)) for k, v in data.items()}
    if isinstance(data, list):
        return [scrub(v, secrets) for v in data]
    if isinstance(data, str):
        for secret in secrets:
            if secret:
                data = data.replace(secret, "[REDACTED]")
    return data


def native_metrics(payload):
    perf = payload.get("performance", {}) if isinstance(payload, dict) else {}
    return {k: perf[k] for k in FIELDS if isinstance(perf, dict) and k in perf}


def build_plan():
    conf = json.loads((ROOT / "configs/exp021_diagnostic.json").read_text())
    settings = conf["settings"]
    if conf.get("experiment") != "EXP-021-DIAGNOSTIC":
        raise ValueError("Wrong registered experiment")
    if "TradeCost" in settings or settings.get("subscribeList") != INSTRUMENTS:
        raise ValueError("Native TradeCost must be absent and original assets preserved")
    if any(settings.get(k) != v for k, v in {
            "StartDate": "2021-01", "EndDate": "2025-12",
            "InitialCapital": 1000000, "dataset": 60, "Leverage": 1,
            "allowShortSell": True, "isPositionBaseEnv": False}.items()):
        raise ValueError("Wrong registered diagnostic settings")
    source = (ROOT / "src/four_asset_h1_exp021_diagnostic.py").read_text()
    original = (ROOT / "src/four_asset_h1_exp020.py").read_text()
    if hashlib.sha256(original.encode()).hexdigest() != conf["original_source_sha256"]:
        raise ValueError("Original EXP020 source changed")
    if "self._log(\"DIAG_FINAL\", str(self.diag))" not in source or "def _diag_mark(" not in source:
        raise ValueError("EXP021 diagnostic instrumentation missing")
    compile(source, "exp021-diagnostic.py", "exec")
    tree = ast.parse(source)
    banned = {"remove", "pop", "update", "replace", "endswith"}
    invalid = sorted({node.func.attr for node in ast.walk(tree)
                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                      and node.func.attr in banned})
    if invalid:
        raise ValueError("ALGOGENE method not allowed: " + str(invalid))
    return [{"name": "diag-2021-2025", "params": conf["params"],
             "settings": dict(settings),
             "source": source, "source_sha256": conf["diagnostic_source_sha256"],
             "status": "NOT RUN"}]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    user = os.environ.get("ALGOGENE_USER_ID", "").strip()
    key = os.environ.get("ALGOGENE_API_KEY", "").strip()
    secrets = (user, key)
    bundle = {"experiment": "EXP-021-DIAGNOSTIC", "source_commit": os.getenv("GITHUB_SHA"),
              "run_id": os.getenv("GITHUB_RUN_ID"), "status": "NOT RUN",
              "benchmark": "ALGOGENE native Score_Total",
              "runs": [], "limitations": [
                  "No funding/swap curve is configured; basis mean reversion is not verified cash-and-carry arbitrage.",
                  "No TradeCost key is sent in native settings. Strict acceptance only when ALGOGENE effective TradeCost=0.0. The strategy internally models 0.05 percent of actual fill notional on all four fills.",
                  "H4 and H24 candles are resampled ONLY from prior complete H1 history.",
                  "EXP021 adds counters only and is not an independent market test.",
                  "Native score excludes simulated percentage fees. If server fee defaults to nonzero, entire run is INVALID_REVIEW regardless of score."]}
    last_finish = [0.0]

    def save():
        (OUT / "platform-responses.json").write_text(
            json.dumps(scrub(bundle, secrets), ensure_ascii=False, indent=2))

    def call(path, params, label, result, post=False):
        data = dict(params, user=user, api_key=key)
        request = urllib.request.Request(
            API + path + ("" if post else "?" + urllib.parse.urlencode(data)),
            data=json.dumps(data).encode() if post else None,
            headers={"Content-Type": "application/json"},
            method="POST" if post else "GET")
        # Transient GET failures may be retried once; POST is never retried.
        # A connection timeout after /run_backtest can be an ambiguous submit.
        for attempt in range(1 if post else 2):
            delay = 75 - (time.monotonic() - last_finish[0])
            if delay > 0:
                time.sleep(delay)
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    payload = json.load(response)
                result.setdefault("platform", {}).setdefault(label, []).append(
                    scrub(payload, secrets))
                save()
                return payload
            except urllib.error.HTTPError as exc:
                status_code = int(exc.code)
                result.setdefault("http_errors", []).append(
                    {"endpoint": label, "http_status": status_code,
                     "attempt": attempt + 1})
                save()
                # No response body is retained: it might expose credentials.
                # Safe bounded retry for the read-only task-status preflight only.
                # A POST submission is NEVER retried after any response or timeout.
                retryable = status_code in (408, 429, 500, 502, 503, 504) or (label == "tasks" and status_code == 400)
                if post or not retryable or attempt != 0:
                    raise
                print("GET_RETRY", label, status_code, flush=True)
            finally:
                last_finish[0] = time.monotonic()
        raise RuntimeError("Unexpected GET retries exhausted")

    save()
    if not user or not key:
        bundle.update(status="NOT RUN", reason="ALGOGENE Actions secrets missing")
        save()
        return 2
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        bundle.update(status="NOT RUN", reason="No resubmission on Actions rerun")
        save()
        return 1
    try:
        plan = build_plan()
    except Exception as exc:
        bundle.update(status="ERROR", reason="Plan validation: " + type(exc).__name__)
        save()
        return 1
    bundle["runs"] = plan
    bundle["status"] = "RUNNING"
    save()
    for row in plan:
        row["status"] = "PREFLIGHT"
        save()
        try:
            tasks = call("/get_current_tasks", {}, "tasks", row)
            if tasks.get("status") is not True or tasks.get("res") != []:
                raise ValueError("Account has an outstanding task or failed preflight")
            metadata = {}
            for sym in INSTRUMENTS:
                r = call("/meta_instrument", {"instrument": sym}, "meta_" + sym, row)
                spec = r.get("res", {})
                cs = spec.get("contractSize")
                # ALGOGENE /meta_instrument may return {"res": {...}} without
                # a top-level "status" key. Accept a valid populated res;
                # reject an explicit status=False or invalid contract size.
                if r.get("status") is False or not isinstance(spec, dict) \
                        or cs is None or not math.isfinite(float(cs)) or float(cs) <= 0:
                    raise ValueError("Instrument not verified: " + sym)
                metadata[sym] = {k: spec.get(k) for k in
                                 ("contractSize", "settleCurrency", "producttype")}
            row["contract_metadata"] = metadata
            row["status"] = "SUBMITTING"
            save()
            assert "TradeCost" not in row["settings"], "No native TradeCost may be submitted"
            result = call("/run_backtest", {"code": row["source"],
                          "settings": row["settings"]}, "submission", row, post=True)
            if result.get("status") is not True:
                row["status"] = "SUBMISSION_REJECTED"
                detail = result.get("msg", result.get("res", "No detail"))
                if isinstance(detail, str):
                    # Result already saved in redacted response; no credentials
                    # or raw submitted code in console logs.
                    row["submission_rejection_summary"] = scrub(detail[:400], secrets)
                save()
                print("SUBMISSION_REJECTED", row["name"],
                      row.get("submission_rejection_summary", ""), flush=True)
                break
            for field, dest in (("runtime_id", "backtest_id"), ("task_id", "task_id")):
                value = result.get(field)
                if not isinstance(value, str) or not value or \
                        any(c not in "0123456789_" for c in value):
                    raise ValueError("Invalid platform task ID: investigate before resubmission")
                row[dest] = value
            row["status"] = "SUBMITTED"
            save()
            print(row["name"], row["backtest_id"], "SUBMITTED", flush=True)
            from archive_exp021_diagnostic import archive
            archive(OUT / "platform-responses.json", "submitted-" + row["name"])
            deadline = time.monotonic() + 120 * 60
            while time.monotonic() < deadline:
                time.sleep(120)
                task = call("/task_status", {"task": "backtest",
                            "task_id": row["task_id"]}, "task_status", row)
                if task.get("status") is True and task.get("res") == "DONE":
                    break
            else:
                row["status"] = "PENDING"
                save()
                break
            p = {"runmode": "backtest", "runtime_id": row["backtest_id"], "acdate": ""}
            for endpoint, label in (("/strategy_stats", "stats"),
                                    ("/strategy_logs", "logs"),
                                    ("/strategy_trade", "trades"),
                                    ("/strategy_pl", "daily_pl")):
                args = dict(p)
                if label == "logs":
                    args.pop("acdate")
                call(endpoint, args, label, row)
            statistics = row["platform"]["stats"][-1]
            row["native_metrics"] = native_metrics(statistics)
            # Parse a single aggregate produced by the STRATEGY at the final
            # hour. Native score is pre-proportional-fee and must be labelled.
            raw_logs = str(row["platform"]["logs"][-1].get("res", ""))
            matches = re.findall(
                r"EXP020, COST_FINAL, ([0-9.]+), ([-0-9.]+), ([-0-9.]+), ([0-9]+), (\{[^\n]*\})",
                raw_logs)
            if matches:
                paid, gross, shadow_net, events, annual = matches[-1]
                row["percent_fee_audit"] = {
                    "fee_rate": 0.0005,
                    "actual_fill_fee_total_usd": float(paid),
                    "independent_realized_gross_usd": float(gross),
                    "internal_net_after_fee_usd": float(shadow_net),
                    "fill_events": int(events),
                    "by_year": ast.literal_eval(annual),
                    "native_score_is_before_internal_fee": True,
                    "cost_adjusted_native_net_pnl_usd":
                        row["native_metrics"]["TotalPnL"] - float(paid)}
            diag_match = re.findall(r"EXP020, DIAG_FINAL, (\\{[^\\n]*\\})", raw_logs)
            if diag_match:
                row["year_pair_diagnostics"] = ast.literal_eval(diag_match[-1])
            effective = statistics.get("setting", statistics.get("settings", {}))
            checks = {}
            for key, value in row["settings"].items():
                if key == "strategyName":
                    continue
                actual = effective.get(key) if isinstance(effective, dict) else None
                if key in ("Leverage", "TradeCost", "InitialCapital", "dataset", "risk_free"):
                    try:
                        checks[key] = math.isclose(float(actual), float(value), rel_tol=1e-8)
                    except (TypeError, ValueError):
                        checks[key] = False
                elif key == "allowShortSell":
                    # Native API serializes this flag as a numeric string.
                    # Earlier experiments showed "1.0" even for false, so
                    # success is only encoding compatibility, NOT proof shorts fill.
                    try:
                        checks[key] = float(actual) == 1.0 and value is True
                    except (TypeError, ValueError):
                        checks[key] = False
                elif isinstance(value, bool):
                    checks[key] = str(actual).lower() == str(value).lower()
                else:
                    checks[key] = actual == value
            # Omitted key is not a zero-valued key. It must explicitly be
            # confirmed from platform's effective settings. Never infer zero.
            actual_trade_cost = effective.get("TradeCost") if isinstance(effective, dict) else None
            try:
                checks["TradeCost"] = math.isclose(float(actual_trade_cost), 0.0, rel_tol=0.0, abs_tol=1e-12)
            except (TypeError, ValueError):
                checks["TradeCost"] = False
            row["effective_settings"] = effective
            row["setting_checks"] = checks
            row["native_tradecost_omitted_from_submission"] = "TradeCost" not in row["settings"]
            logs = str(row["platform"].get("logs", [{}])[-1].get("res", ""))
            trade_count = row["native_metrics"].get("TradeCnt")
            row["status"] = ("COLLECTED" if all(checks.values()) and
                             isinstance(row["native_metrics"].get("Score_Total"), (int, float))
                             and isinstance(trade_count, (int, float)) and trade_count >= 4
                             and "EXP020, HALT" not in logs and "Traceback" not in logs
                             and "PAIR_CONFIRMED" in logs and "COST_FINAL" in logs
                             and "percent_fee_audit" in row and "year_pair_diagnostics" in row
                             else "INVALID_REVIEW")
            save()
            archive(OUT / "platform-responses.json", "collected-" + row["name"])
            # Native nonzero fee invalidates the score for strict zero-cost
            # research. A fully completed backtest is nevertheless safe to
            # follow with the second independent time window.
            if row["status"] != "COLLECTED":
                print("INVALID_NATIVE_FEE_OR_VALIDATION", row["name"],
                      str(row["effective_settings"].get("TradeCost")), flush=True)
        except Exception as exc:
            row.update(status="ERROR", error_type=type(exc).__name__)
            if isinstance(exc, urllib.error.HTTPError):
                row["http_status"] = int(exc.code)
                row["http_stage"] = row.get("status_before_error", row.get("status"))
            if isinstance(exc, urllib.error.URLError):
                row["network_error_type"] = "URLError"
            # Only log safe, source-controlled validation messages.
            if isinstance(exc, ValueError):
                detail = str(exc)
                if detail.startswith(("Instrument not verified:", "Invalid platform task ID:",
                                      "Account has an outstanding task", "Backtest configuration")):
                    row["validation_error"] = detail[:180]
            save()
            print("STOPPED", row["name"], type(exc).__name__,
                  row.get("validation_error", ""), flush=True)
            break
    # Respect an explicitly selected single window as well as the original two-window plan.
    # A completed single-window retry must not be marked failed for lacking the other window.
    bundle["status"] = ("COLLECTED" if plan and
                        all(r["status"] == "COLLECTED" for r in plan)
                        else "STOPPED")
    ranked = [r for r in plan if r["status"] == "COLLECTED"]
    ranked.sort(key=lambda r: r["native_metrics"]["Score_Total"], reverse=True)
    bundle["native_score_ranking"] = [
        {"name": r["name"], "backtest_id": r["backtest_id"],
         "native_metrics": r["native_metrics"]} for r in ranked]
    save()
    return 0 if bundle["status"] == "COLLECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
