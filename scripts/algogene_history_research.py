"""Bounded precision probe and five registered strategy tests; native metrics only."""
import hashlib
import json
import math
import os
from pathlib import Path

from algogene_v1_3_pipeline import main as run_cloud, redact
from algogene_combination_batch import native_fields
from algogene_research_batch import effective_fee, fee_verified
from archive_v1_4_results import archive

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/exp012"
PARAM_LINE = 'PARAMS = {"mode": "ema", "step": 0.001, "exit": 10, "stop": 2.0, "target_atr": 0.0, "hold_hours": 0, "band": 2.0, "min_reward": 0.0}'
REGISTERED = [{"name":"ema-size-control","params":{"mode":"ema","exit":10,"stop":2,"target_atr":0,"hold_hours":0,"band":2,"min_reward":0},"requires_precision":True},{"name":"ema-bracket-3atr","params":{"mode":"ema","exit":10,"stop":2,"target_atr":3,"hold_hours":72,"band":2,"min_reward":3}},{"name":"ema-bracket-4atr","params":{"mode":"ema","exit":20,"stop":2,"target_atr":4,"hold_hours":120,"band":2,"min_reward":3}},{"name":"range-wide","params":{"mode":"range","exit":10,"stop":2,"target_atr":0,"hold_hours":48,"band":2,"min_reward":3}},{"name":"range-fast","params":{"mode":"range","exit":10,"stop":1.5,"target_atr":0,"hold_hours":24,"band":1.5,"min_reward":3}}]


def plan():
    config = json.loads((ROOT / "configs/exp012_history_research.json").read_text())
    expected = json.loads((ROOT / "configs/exp010_ema_fee.json").read_text())["settings"]
    expected["strategyName"] = "EXP012 H1 historical review"
    if (config["experiment"] != "EXP-012" or config["data_role"] != "Development"
            or config["candidates"] != REGISTERED or config["settings"] != expected
            or config["precision_probe"] != 0.001 or config["fallback_step"] != 0.01
            or expected["StartDate"] != "2021-01" or expected["EndDate"] != "2023-12"
            or expected["dataset"] != 60 or expected["TradeCost"] != 1.0
            or expected["InitialCapital"] != 10000 or expected["Leverage"] != 1
            or expected["allowShortSell"] is not False or expected["isPositionBaseEnv"] is not False):
        raise ValueError("Unregistered experiment settings")
    probe_source()
    for candidate in config["candidates"]:
        for step in (0.001, 0.01):
            source_for(candidate, step)
    return config


def source_for(candidate, step):
    if candidate not in REGISTERED or step not in (0.001, 0.01):
        raise ValueError("Unregistered model or precision")
    template = (ROOT / "src/algogene_crypto_v1_6.py").read_text()
    if template.count(PARAM_LINE) != 1:
        raise ValueError("Template drift")
    params = dict(candidate["params"], step=step)
    source = template.replace(PARAM_LINE, "PARAMS = " + json.dumps(params), 1)
    compile(source, "submitted-strategy.py", "exec")
    return source


def precision_verified(result):
    if result.get("status") != "COLLECTED":
        return False
    records = result.get("platform_responses", {}).get("transactions", [{}])[-1].get("res", [])
    if not isinstance(records, list):
        return False
    return all(any(row.get("openclose") == side and float(row.get("volume", 0)) == 0.001
                   for row in records) for side in ("open", "close"))


def probe_source():
    source = (ROOT / "src/algogene_crypto_v1_0.py").read_text()
    if source.count("VOLUME = 0.01") != 1:
        raise ValueError("Probe template drift")
    source = source.replace("VOLUME = 0.01", "VOLUME = 0.001", 1)
    compile(source, "precision-probe.py", "exec")
    return source


def known_finished(result):
    state = result.get("platform_responses", {}).get("task_status", [{}])[-1]
    return state.get("status") is True and state.get("res") == "DONE"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bundle = {"experiment": "EXP-012", "data_role": "Development", "status": "NOT RUN",
              "code_commit": os.getenv("GITHUB_SHA"), "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
              "workflow_attempt": os.getenv("GITHUB_RUN_ATTEMPT"), "precision_verified": False, "runs": []}
    secrets = (os.getenv("ALGOGENE_API_KEY", ""), os.getenv("ALGOGENE_USER_ID", ""))

    def write(path, value):
        path.write_text(json.dumps(redact(value, secrets), indent=2, ensure_ascii=False))

    def save():
        write(OUT / "platform-responses.json", bundle)

    save()
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        bundle["reason"] = "Workflow retry cannot resubmit; review existing IDs"
        save()
        return 1
    try:
        config = plan()
    except Exception as exc:
        bundle.update(reason="Plan guard rejected; no cloud call", error_type=type(exc).__name__)
        save()
        return 1
    rows = [{"name": "precision-probe", "status": "NOT RUN"}] + [
        dict(candidate, status="NOT RUN") for candidate in config["candidates"]]
    bundle.update(plan=config, runs=rows, status="RUNNING",
                  comparison_policy="Native Score_Total plus all six subscores and after-cost PnL/risk. No automatic winner.")
    save()
    for row in rows:
        probe = row["name"] == "precision-probe"
        if row.get("requires_precision") and not bundle["precision_verified"]:
            row.update(status="NOT RUN", reason="Precision unverified; no fine-size control submission")
            save()
            continue
        settings = dict(config["settings"], strategyName="EXP012 H1 " + row["name"])
        if probe:
            settings.update(StartDate="2021-01", EndDate="2021-01")
            source = probe_source()
            step = 0.001
        else:
            step = 0.001 if bundle["precision_verified"] else 0.01
            source = source_for({k: v for k, v in row.items() if k not in ("status",)}, step)
        digest = hashlib.sha256(source.encode()).hexdigest()
        row.update(settings=settings, submitted_source=source, source_sha256=digest,
                   effective_model_step=step, status="STARTING")
        save()
        path = OUT / (row["name"] + ".json")

        def annotate():
            result = json.loads(path.read_text())
            result.update(submitted_source=source, source_sha256=digest, model_step=step,
                          candidate=row.get("params"), comparison_reference=config["reference"])
            write(path, result)
            return result

        def submitted(submitted_path):
            annotate()
            archive(submitted_path, row["name"] + "-submitted", experiment="EXP-012")

        exit_code = run_cloud(settings_override=settings, source_override=source, output_override=path,
                              experiment="EXP-012/" + row["name"], version="V1.6 history research",
                              on_submission=submitted)
        result = annotate()
        if not probe and result["status"] == "COLLECTED":
            result["native_fee_verified"] = fee_verified(result)
            native = native_fields(result)
            score = native.get("Score_Total")
            score_valid = isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score)
            no_trades = native.get("TradeCnt") == 0
            result["native_score_available"] = score_valid
            if effective_fee(result) != 1.0 or (not result["native_fee_verified"] and not no_trades) or not score_valid:
                result["status"] = "COLLECTED_WITH_ERRORS"
                result["errors"].append({"reason": "Native fee/charge or score unavailable; inspect raw response"})
            if no_trades:
                result["fee_observation"] = "No trades returned; configured fee only, no charge observable"
            write(path, result)
        if probe:
            bundle["precision_verified"] = precision_verified(result)
        row.update(status=result["status"], evidence=result, exit_code=exit_code,
                   native_comparison=native_fields(result))
        save()
        try:
            archive(path, row["name"], experiment="EXP-012")
        except Exception as exc:
            bundle.update(status="STOPPED", reason="Checkpoint archive failed", error_type=type(exc).__name__)
            save()
            return 1
        print(row["name"] + ": " + row["status"], flush=True)
        safe_probe_fallback = probe and (result["status"] == "SUBMISSION_REJECTED" or known_finished(result))
        if result["status"] != "COLLECTED" and not safe_probe_fallback and result["status"] != "SUBMISSION_REJECTED":
            bundle.update(status="STOPPED", reason="Review pending/uncertain task or evidence before more submissions")
            save()
            return 1
    bundle["status"] = "COLLECTED" if all(r["status"] == "COLLECTED" for r in rows) else "FINISHED_WITH_LIMITATIONS"
    save()
    return 0 if all(r["status"] in ("COLLECTED", "NOT RUN") for r in rows[1:]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
