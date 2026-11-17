"""EXP014: H1-only one-factor Development research with native evidence."""
import hashlib
import json
import math
import os
from pathlib import Path

from algogene_v1_3_pipeline import main as run_cloud, redact
from algogene_research_batch import fee_verified, effective_fee
from archive_v1_4_results import archive

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/exp014"
PARAM_LINE = 'PARAMS = {"max_cost_ratio": 0.10, "fee_per_open": 1.0, "reward_atr": 3.0, "min_slope_atr": 0.0, "min_breakout_atr": 0.0, "terminal_year": 2023}'
REGISTERED = [
    {"name": "h1-gate-reference", "params": {"max_cost_ratio": 0.10, "fee_per_open": 1.0, "reward_atr": 3.0, "min_slope_atr": 0.0, "min_breakout_atr": 0.0, "terminal_year": 2023}},
    {"name": "cost-gate-08", "params": {"max_cost_ratio": 0.08, "fee_per_open": 1.0, "reward_atr": 3.0, "min_slope_atr": 0.0, "min_breakout_atr": 0.0, "terminal_year": 2023}},
    {"name": "trend-slope-005", "params": {"max_cost_ratio": 0.10, "fee_per_open": 1.0, "reward_atr": 3.0, "min_slope_atr": 0.05, "min_breakout_atr": 0.0, "terminal_year": 2023}},
    {"name": "breakout-buffer-010", "params": {"max_cost_ratio": 0.10, "fee_per_open": 1.0, "reward_atr": 3.0, "min_slope_atr": 0.0, "min_breakout_atr": 0.10, "terminal_year": 2023}},
]


def plan():
    config = json.loads((ROOT / "configs/exp014_h1_quality.json").read_text())
    expected = json.loads((ROOT / "configs/exp010_ema_fee.json").read_text())["settings"]
    expected["strategyName"] = "EXP014 H1 quality research"
    if (config["experiment"] != "EXP-014" or config["data_role"] != "Development" or config["trigger"] != "2026-11-17-h1-quality-01"
            or config["candidates"] != REGISTERED or config["settings"] != expected
            or expected["StartDate"] != "2021-01" or expected["EndDate"] != "2023-12"
            or expected["dataset"] != 60 or expected["TradeCost"] != 1.0
            or expected["InitialCapital"] != 10000 or expected["Leverage"] != 1
            or expected["allowShortSell"] is not False or expected["isPositionBaseEnv"] is not False):
        raise ValueError("Unregistered experiment settings or candidate set")
    template = (ROOT / "src/algogene_crypto_v1_8.py").read_text()
    if template.count(PARAM_LINE) != 1:
        raise ValueError("Candidate template drift")
    rows = []
    for candidate in config["candidates"]:
        # JSON uses only strings and numbers here, so is also a Python literal.
        source = template.replace(PARAM_LINE, "PARAMS = " + repr(candidate["params"]), 1)
        compile(source, "submitted-strategy.py", "exec")
        settings = dict(expected, strategyName="EXP014 " + candidate["name"])
        rows.append(dict(candidate, settings=settings, submitted_source=source,
                         source_sha256=hashlib.sha256(source.encode()).hexdigest(), status="NOT RUN"))
    return config, rows


def native_fields(evidence):
    stats = evidence.get("platform_responses", {}).get("statistics", [{}])[-1]
    p = stats.get("performance", {})
    keys = ("Score_Total", "score_AnnualSharpe", "score_AvgDrawdownDuration", "score_Rsquare",
            "score_TradePerDay", "score_WinRate", "score_maxDrawdown_pct", "TotalPnL", "AnnualSharpe",
            "maxDrawdown_pct", "maxDrawdown_amt", "maxDrawdownDuration", "TradeCnt", "profit_factor")
    # Copy platform values without replacing missing values or computing metrics.
    return {key: p[key] for key in keys if key in p}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = {"experiment": "EXP-014", "data_role": "Development", "status": "NOT RUN",
              "code_commit": os.getenv("GITHUB_SHA"), "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
              "workflow_attempt": os.getenv("GITHUB_RUN_ATTEMPT"), "runs": []}
    secrets = (os.getenv("ALGOGENE_API_KEY", ""), os.getenv("ALGOGENE_USER_ID", ""))

    def write(path, value):
        path.write_text(json.dumps(redact(value, secrets), indent=2, ensure_ascii=False))

    def save():
        write(OUT / "platform-responses.json", bundle)

    save()
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        bundle["reason"] = "No re-submission on workflow retry; review existing task IDs"
        save()
        return 1
    try:
        config, rows = plan()
    except Exception as exc:
        bundle.update(reason="Plan guard rejected; no cloud submission", error_type=type(exc).__name__)
        save()
        return 1
    bundle.update(plan=config, runs=rows, status="RUNNING",
                  comparison_policy="Compare H1 reference vs each one-factor H1 improvement using native fee-adjusted PnL, Sharpe and drawdown. Composite score secondary.",
                  limitations=["Every candidate uses H1; only one entry gate changes relative to the reference.",
                               "Fixed cost 1.0 is a stress assumption, not broker pricing.",
                               "Native allowShortSell encoding unverified; code contains only long entries.",
                               "2021-2023 Development only; 2024 Validation and 2025 Final remain untouched."])
    save()
    for row in rows:
        path = OUT / (row["name"] + ".json")
        row["status"] = "STARTING"
        save()

        def annotate():
            result = json.loads(path.read_text())
            result.update(source_sha256=row["source_sha256"], submitted_source=row["submitted_source"],
                          candidate=row["params"], comparison_reference=config["reference"])
            write(path, result)
            return result

        def submitted(submitted_path):
            annotate()
            archive(submitted_path, row["name"] + "-submitted", experiment="EXP-014")

        exit_code = run_cloud(settings_override=row["settings"], source_override=row["submitted_source"],
                              output_override=path, experiment="EXP-014/" + row["name"],
                              version="V1.8 H1-only research", on_submission=submitted)
        result = annotate()
        if result["status"] == "COLLECTED":
            result["native_fee_verified"] = fee_verified(result)
            score = native_fields(result).get("Score_Total")
            result["native_score_available"] = isinstance(score, (int, float)) and math.isfinite(score)
            if (not result["native_fee_verified"] and native_fields(result).get("TradeCnt") != 0) or not result["native_score_available"] or effective_fee(result) != 1.0:
                result["status"] = "COLLECTED_WITH_ERRORS"
                result["errors"].append({"reason": "Native fee or Score_Total unavailable; inspect raw evidence"})
            write(path, result)
        row.update(status=result["status"], evidence=result, exit_code=exit_code,
                   native_comparison=native_fields(result))
        save()
        try:
            archive(path, row["name"], experiment="EXP-014")
        except Exception as exc:
            bundle.update(status="STOPPED", reason="Checkpoint archive failed", error_type=type(exc).__name__)
            save()
            return 1
        print(row["name"] + ": " + row["status"], flush=True)
        if row["status"] != "COLLECTED":
            bundle.update(status="STOPPED", reason="Review current task/partial evidence before further submissions")
            save()
            return 1
    bundle["status"] = "COLLECTED" if all(row["status"] == "COLLECTED" for row in rows) else "FINISHED_WITH_FAILURES"
    save()
    return 0 if bundle["status"] == "COLLECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
