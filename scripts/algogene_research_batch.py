"""Pre-registered, sequential cloud experiments. Never calculate financial results."""
import hashlib
import json
import math
import os
from pathlib import Path

from algogene_v1_3_pipeline import main as run_cloud, redact
from archive_v1_4_results import archive

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/v1_4"


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Baseline source drift; research transformation must be reviewed")
    return source.replace(old, new, 1)


def strategy_source(year=2023, stop=2.0, slope=False):
    if year not in (2021, 2022, 2023) or stop not in (1.5, 2.0, 2.5):
        raise ValueError("Unregistered strategy variant")
    source = (ROOT / "src/algogene_crypto_v1_3.py").read_text()
    source = replace_once(source, "datetime(2023, 12, 31, 22)", "datetime(%d, 12, 31, 22)" % year)
    source = replace_once(source, "stop_loss = price - 2.0 * atr", "stop_loss = price - %s * atr" % stop)
    if slope:
        # A one-bar EMA increase is implied by close > EMA already. Use a
        # pre-registered 24-hour slope so this is a distinct additional condition.
        source = replace_once(source, "self.ema = None", "self.ema = None\n        self.ema_history = deque(maxlen=25)")
        source = replace_once(source, "        signal = None", "        if self.ema is not None:\n            self.ema_history.append(self.ema)\n        signal = None")
        source = replace_once(source, '"entry": c > upper and c > self.ema,',
                              '"entry": c > upper and c > self.ema and len(self.ema_history) == 25 and self.ema > self.ema_history[0],')
    compile(source, "submitted-strategy.py", "exec")
    return source


def plan():
    config = json.loads((ROOT / "configs/v1_4_research.json").read_text())
    if (config["annual_years"] != [2021, 2022, 2023]
            or config["stop_atr_multiples"] != [1.5, 2.0, 2.5]
            or config["sizing_atr_multiple"] != 2.0
            or config["ema_slope_lookback_hours"] != 24
            or config["fee_probe"]["TradeCost"] != 1.0):
        raise ValueError("Research plan changed; review runner before submission")
    rows = [("fee-probe", "2021-01", "2021-01", None, False, 1.0)]
    rows += [("annual-%s" % year, "%s-01" % year, "%s-12" % year, 2.0, False, None)
             for year in config["annual_years"]]
    rows += [("stop-%s" % stop, "2021-01", "2023-12", stop, False, None) for stop in (1.5, 2.5)]
    rows += [("ema-slope-24h", "2021-01", "2023-12", 2.0, True, None)]
    if config["conditional_fee_stress"]:
        rows += [("fee-stress", "2021-01", "2023-12", 2.0, False, 1.0)]
    base = json.loads((ROOT / "configs/v1_3_cloud.json").read_text())
    result = []
    for name, start, end, stop, slope, fee in rows:
        settings = dict(base, strategyName="EXP009 H1 " + name, StartDate=start, EndDate=end)
        if fee is not None:
            settings["TradeCost"] = fee
        source = ((ROOT / "src/algogene_crypto_v1_0.py").read_text() if stop is None
                  else strategy_source(int(end[:4]), stop, slope))
        result.append({"name": name, "status": "NOT RUN", "settings": settings,
                       "stop_atr_multiple": stop, "sizing_atr_multiple": 2.0 if stop else None,
                       "ema_slope_lookback_hours": 24 if slope else None,
                       "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                       "submitted_source": source})
    return config, result


def effective_fee(result):
    try:
        return float(result["platform_responses"]["statistics"][-1]["setting"]["TradeCost"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def fee_verified(result):
    if result.get("status") != "COLLECTED" or effective_fee(result) != 1.0:
        return False
    try:
        records = result["platform_responses"]["transactions"][-1]["res"]
        return isinstance(records, list) and any(math.isfinite(float(row.get("TradeCost", 0)))
                                                and float(row.get("TradeCost", 0)) != 0 for row in records)
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    config, rows = plan()
    bundle = {"experiment": "EXP-009", "version": "V1.4 research candidates",
              "data_role": "Development", "code_commit": os.getenv("GITHUB_SHA"),
              "workflow_run_id": os.getenv("GITHUB_RUN_ID"), "workflow_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
              "status": "NOT RUN", "plan": config, "native_fee_verified": False, "runs": rows,
              "limitations": ["Platform statistics are authoritative; no reconstructed financial metrics.",
                              "Zero-cost comparisons cannot establish profitability after trading costs.",
                              "No validation/final holdout use or automatic candidate selection.",
                              "Console API may return only the latest 2000 records; no claim of complete error coverage."]}
    secrets = (os.getenv("ALGOGENE_API_KEY", ""), os.getenv("ALGOGENE_USER_ID", ""))

    def save():
        (OUT / "platform-responses.json").write_text(json.dumps(redact(bundle, secrets), indent=2, ensure_ascii=False))

    save()
    # Re-running a workflow is an additional experiment, never an implicit retry.
    if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
        bundle.update(status="NOT RUN", reason="Workflow retry disabled to avoid duplicate cloud submissions; review recorded IDs first")
        save()
        return 1
    bundle["status"] = "RUNNING"
    save()
    for row in rows:
        if row["name"] == "fee-stress" and not bundle["native_fee_verified"]:
            row.update(status="NOT RUN", reason="Fixed cost API not verified; no invented fee adjustment")
            save()
            continue
        path = OUT / (row["name"] + ".json")
        row["status"] = "STARTING"
        save()
        exit_code = run_cloud(settings_override=row["settings"], source_override=row["submitted_source"],
                              output_override=path, experiment="EXP-009/" + row["name"], version="V1.4 research",
                              on_submission=lambda submitted: archive(submitted, row["name"] + "-submitted"))
        evidence = json.loads(path.read_text())
        evidence.update(source_sha256=row["source_sha256"], submitted_source=row["submitted_source"])
        path.write_text(json.dumps(redact(evidence, secrets), indent=2, ensure_ascii=False))
        row.update(status=evidence["status"], evidence=evidence, exit_code=exit_code,
                   effective_trade_cost=effective_fee(evidence))
        if row["name"] == "fee-probe":
            bundle["native_fee_verified"] = fee_verified(evidence)
        save()
        print(row["name"] + ": " + row["status"], flush=True)
        try:
            archive(path, row["name"])
        except Exception as exc:
            bundle.update(status="STOPPED", reason="Checkpoint archive failed; retain artifact before continuing",
                          archive_error_type=type(exc).__name__)
            save()
            return 1
        # Explicit platform rejection creates no task. All other uncertain states
        # halt the batch; never reset account tasks or re-submit a timed-out POST.
        if row["status"] not in ("COLLECTED", "SUBMISSION_REJECTED"):
            bundle.update(status="STOPPED", reason="Review existing cloud IDs/errors before further submissions")
            save()
            return 1
        if row["name"] != "fee-probe" and row["status"] == "COLLECTED":
            expected = 1.0 if row["name"] == "fee-stress" else 0.0
            if row["effective_trade_cost"] != expected:
                bundle.update(status="STOPPED", reason="Effective native fee differs from registered comparison; do not pool results")
                save()
                return 1
    bundle["status"] = "COLLECTED" if all(row["status"] == "COLLECTED" for row in rows) else "FINISHED_WITH_LIMITATIONS"
    save()
    return 0 if all(row["status"] in ("COLLECTED", "NOT RUN") for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
