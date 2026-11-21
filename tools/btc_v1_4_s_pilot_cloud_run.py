"""Matched 2024 native fee diagnostic: omitted cost versus explicit USD 0.37.
No 2025, no live trading, no ambiguous submission retry.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://algogene.com/rest/v1"
OUT = ROOT / "outputs" / "btc_v1_4_s_pilot" / "evidence.json"
PARAM_LINE = "ADX_THRESHOLD = 25"
FEES = (None, 0.37)


def build_plan():
    settings = json.loads((ROOT/"config/btc_v1_1_cloud.json").read_text())
    required = {"subscribeList":["BTCUSD"], "StartDate":"2021-01",
                "EndDate":"2024-12", "InitialCapital":10000, "dataset":60,
                "Leverage":1, "allowShortSell":False}
    if any(settings.get(k) != value for k, value in required.items()):
        raise ValueError("Fixed research settings mismatch")
    if "TradeCost" in settings:
        raise ValueError("Unexpected fixed-cost configuration")
    template = (ROOT/"strategy/btc_v1_4_a_risk60.py").read_text()
    if template.count(PARAM_LINE) != 1:
        raise ValueError("Unexpected parameter declaration")
    result = []
    for fee in FEES:
        label = "omitted" if fee is None else "fixed-0.37"
        cfg = dict(settings, StartDate="2024-01", EndDate="2024-12",
                   strategyName="BTC V1.4-S pilot "+label+" 2024")
        if fee is not None:
            cfg["TradeCost"] = fee
        compile(template, "btc-v1.4-s-"+label, "exec")
        result.append({"name":label, "fee":fee, "source":template, "settings":cfg})
    return result


def scrub(obj, credentials):
    if isinstance(obj, dict):
        return {k:("[REDACTED]" if k.lower() in
                ("user", "api_key", "password", "token", "authorization")
                else scrub(v, credentials)) for k,v in obj.items()}
    if isinstance(obj, list):
        return [scrub(x, credentials) for x in obj]
    if isinstance(obj, str):
        for c in credentials:
            if c:
                obj=obj.replace(c, "[REDACTED]")
    return obj


def main():
    user=(os.getenv("ALGOGENE_USER_ID") or "").strip()
    key=(os.getenv("ALGOGENE_API_KEY") or "").strip()
    secrets=(user,key)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    report={"study":"BTC V1.4-S matched native fee pilot", "status":"NOT_RUN",
            "commit":os.getenv("GITHUB_SHA"),"run_id":os.getenv("GITHUB_RUN_ID"),
            "period":"2024 development subset; 2025 excluded",
            "costs":"Matched omitted versus explicit USD 0.37 diagnostic; no claim of slippage simulation.",
            "experiments":[]}
    def save():
        OUT.write_text(json.dumps(scrub(report,secrets),indent=2,
                                  ensure_ascii=False,default=str)+"\n")
    save()
    if not user or not key:
        report.update(status="NO_CREDENTIALS")
        save()
        return 1
    if os.getenv("GITHUB_RUN_ATTEMPT","1") != "1":
        report.update(status="RERUN_BLOCKED")
        save()
        return 1
    try:
        plan=build_plan()
    except Exception as exc:
        report.update(status="PLAN_ERROR",error_type=type(exc).__name__)
        save()
        return 1
    last=[0.]
    def call(path, data, post=False):
        if last[0]:
            wait=75-(time.monotonic()-last[0])
            if wait>0:
                time.sleep(wait)
        payload=dict(data,user=user,api_key=key)
        req=urllib.request.Request(
            API+path+("" if post else "?"+urllib.parse.urlencode(payload)),
            data=json.dumps(payload).encode() if post else None,
            headers={"Content-Type":"application/json","Accept":"application/json"},
            method="POST" if post else "GET")
        try:
            with urllib.request.urlopen(req,timeout=60) as res:
                return json.load(res)
        finally:
            last[0]=time.monotonic()
    report["status"]="RUNNING"
    save()
    for case in plan:
        row={"name":case["name"],"requested_fee":case["fee"],
             "status":"PREFLIGHT","observations":[]}
        report["experiments"].append(row)
        save()
        try:
            tasks=call("/get_current_tasks",{})
            if tasks.get("status") is not True or tasks.get("res") != []:
                row.update(status="BLOCKED",reason="Outstanding task or preflight failed")
                save()
                break
            row["status"]="SUBMITTING"
            save()
            submission=call("/run_backtest",
                {"code":case["source"],"settings":case["settings"]},post=True)
            if submission.get("status") is not True:
                row.update(status="REJECTED",response=scrub(submission,secrets))
                save()
                break
            runid,taskid=submission.get("runtime_id"),submission.get("task_id")
            if not all(isinstance(x,str) and x and
                       all(c in "0123456789_" for c in x) for x in (runid,taskid)):
                row.update(status="AMBIGUOUS",response=scrub(submission,secrets))
                save()
                break
            row.update(status="SUBMITTED",backtest_id=runid,task_id=taskid)
            save()
            print("Submitted",case["name"],runid,flush=True)
            deadline=time.monotonic()+45*60
            while time.monotonic()<deadline:
                time.sleep(110)
                state=call("/task_status",{"task":"backtest","task_id":taskid})
                phase=state.get("res")
                row["observations"].append(phase if phase in
                    ("DONE","IN PROGRESS","NOT FOUND") else "UNKNOWN")
                save()
                if state.get("status") is True and phase=="DONE":
                    break
                if state.get("status") is True and phase=="NOT FOUND":
                    row["status"]="TASK_NOT_FOUND"
                    save()
                    break
            if row["status"]=="TASK_NOT_FOUND":
                break
            if not row["observations"] or row["observations"][-1]!="DONE":
                row["status"]="PENDING"
                save()
                break
            row["status"]="COLLECTING"
            save()
            params={"runmode":"backtest","runtime_id":runid}
            stats=call("/strategy_stats",dict(params,acdate=""))
            row["stats"]=scrub(stats,secrets)
            settings=stats.get("setting",stats.get("settings",{}))
            row["effective_settings"]=scrub(settings,secrets)
            perf=stats.get("performance",{})
            keys=("Score_Total","TotalPnL","AnnualSharpe","maxDrawdown_pct",
                  "TradeCnt","WinRate","profit_factor","simpleReturn")
            row["requested_settings"]=case["settings"]
            row["metrics"]={k:perf[k] for k in keys if isinstance(perf,dict) and k in perf}
            for path,label,arg in (("/strategy_logs","logs",params),
                ("/strategy_trade","trades",dict(params,acdate="")),
                ("/strategy_pl","daily_pl",dict(params,acdate=""))):
                row[label]=scrub(call(path,arg),secrets)
                save()
            valid=isinstance(settings,dict) and all(
                str(settings.get(k))==str(case["settings"][k]) for k in
                ("StartDate","EndDate","dataset"))
            logs = json.dumps(row.get("logs", {}), ensure_ascii=False)
            if not valid:
                row["status"]="INVALID_PERIOD"
            elif "STOP_ANCHOR_MISSING_HALT" in logs or "Traceback" in logs:
                row["status"]="STRATEGY_ERROR"
            elif not isinstance(perf,dict) or float(perf.get("TradeCnt",0)) <= 0:
                row["status"]="NO_TRADES"
            else:
                row["status"]="COLLECTED"
            row["effective_fee"]=settings.get("TradeCost") if isinstance(settings,dict) else None
            row["fee_matches_request"]=(row["effective_fee"] is not None and float(row["effective_fee"]) == (0.0 if case["fee"] is None else case["fee"]))
            save()
            if row["status"]!="COLLECTED":
                break
        except Exception as exc:
            row.update(status="ERROR",error_type=type(exc).__name__)
            save()
            break
    report["status"]=("COLLECTED" if len(report["experiments"])==len(FEES)
                      and all(x["status"]=="COLLECTED" for x in report["experiments"])
                      else "STOPPED")
    report["fee_diagnostic_pass"]=report["status"]=="COLLECTED" and all(x.get("fee_matches_request") for x in report["experiments"])
    save()
    return 0 if report["fee_diagnostic_pass"] else 1


if __name__=="__main__":
    raise SystemExit(main())
