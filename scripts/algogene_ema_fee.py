"""One controlled EMA-candidate cost test, with unchanged pinned cloud source."""
import hashlib
import json
import os
from pathlib import Path

from algogene_v1_3_pipeline import main as run_cloud, redact
from algogene_research_batch import fee_verified
from archive_v1_4_results import archive

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs/exp010/platform-responses.json"
PINNED_SOURCE_SHA256 = "036fc0076556d59b6e0c5c764f268034310ea519926b1959769a69639be4b075"


def load_plan():
    config = json.loads((ROOT / "configs/exp010_ema_fee.json").read_text())
    source = (ROOT / "src/algogene_crypto_v1_4_ema.py").read_text()
    expected = {"strategyName": "EXP010 H1 EMA24 native fee1", "subscribeList": ["BTCUSD"],
                "StartDate": "2021-01", "EndDate": "2023-12", "InitialCapital": 10000,
                "BaseCurrency": "USD", "risk_free": 0, "Leverage": 1, "allowShortSell": False,
                "dataset": 60, "isPositionBaseEnv": False, "isNewsFeedOn": False,
                "isEconstatFeedon": False, "isWeatherFeedOn": False, "TradeCost": 1.0}
    digest = hashlib.sha256(source.encode()).hexdigest()
    if (config["experiment"] != "EXP-010" or config["data_role"] != "Development"
            or config["settings"] != expected or config["source_sha256"] != PINNED_SOURCE_SHA256
            or digest != PINNED_SOURCE_SHA256):
        raise ValueError("Unregistered source/settings change; no cloud submission")
    compile(source, "submitted-strategy.py", "exec")
    return config, source


def main():
    secrets = (os.getenv("ALGOGENE_API_KEY", ""), os.getenv("ALGOGENE_USER_ID", ""))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    def save(value):
        OUTPUT.write_text(json.dumps(redact(value, secrets), indent=2, ensure_ascii=False))

    initial = {"experiment": "EXP-010", "data_role": "Development", "status": "NOT RUN",
               "code_commit": os.getenv("GITHUB_SHA"), "workflow_run_id": os.getenv("GITHUB_RUN_ID"),
               "workflow_attempt": os.getenv("GITHUB_RUN_ATTEMPT"), "backtest_id": None,
               "task_id": None, "errors": []}
    save(initial)
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        initial["reason"] = "Workflow retry cannot submit another backtest; inspect existing IDs"
        save(initial)
        return 1
    try:
        config, source = load_plan()
    except Exception as exc:
        initial.update(reason="Experiment guard failed; no cloud submission", error_type=type(exc).__name__)
        save(initial)
        return 1

    def annotate():
        result = json.loads(OUTPUT.read_text())
        result.update(source_sha256=PINNED_SOURCE_SHA256, submitted_source=source,
                      comparison_reference=config["reference"], plan=config,
                      cost_assumption="Native fixed TradeCost 1.0 stress; not verified broker pricing",
                      short_setting_caveat="Prior native allowShortSell returned 1.0 for false; semantics unverified. Source has no short-entry branch.")
        save(result)
        return result

    def submitted(path):
        annotate()
        archive(path, "submitted", experiment="EXP-010")

    exit_code = run_cloud(settings_override=config["settings"], source_override=source,
                          output_override=OUTPUT, experiment="EXP-010", version="V1.4 EMA fee test",
                          on_submission=submitted)
    result = annotate()
    if result["status"] == "COLLECTED":
        result["native_fee_verified"] = fee_verified(result)
        if not result["native_fee_verified"]:
            result["status"] = "COLLECTED_WITH_ERRORS"
            result["errors"].append({"reason": "Native fee setting or charge unverified; no valid cost comparison"})
            exit_code = 1
        save(result)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
