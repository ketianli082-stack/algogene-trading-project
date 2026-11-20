"""Sequential V1.1 ADX threshold backtest runner, strictly 2021-2024.
Uses the same ALGOGENE REST endpoints as the validated BTC V1.0.
Never retries an ambiguous submission. No live-trading endpoints.
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://algogene.com/rest/v1"
OUT = ROOT / "outputs" / "btc_v1_1_a" / "evidence.json"
PARAM_LINE = "ADX_THRESHOLD = 25"
THRESHOLDS = (20,)


def build_plan():
    settings = json.loads((ROOT/"config/btc_v1_1_cloud.json").read_text())
    required = {"subscribeList":["BTCUSD"], "StartDate":"2021-01",
                "EndDate":"2024-12", "InitialCapital":10000, "dataset":60,
                "Leverage":1, "allowShortSell":False}
    if any(settings.get(k) != value for k, value in required.items()):
        raise ValueError("Fixed research settings mismatch")
    if "TradeCost" in settings:
        raise ValueError("Unexpected fixed-cost configuration")
    template = (ROOT/"strategy/btc_v1_1_ema_adx60.py").read_text()
    if template.count(PARAM_LINE) != 1:
        raise ValueError("Unexpected parameter declaration")
    result = []
    for threshold in THRESHOLDS:
        code = template.replace(PARAM_LINE, "ADX_THRESHOLD = "+str(threshold), 1)
        compile(code, "btc-v1.1-"+str(threshold), "exec")
        if any(line.strip().startswith("TradeCost") for line in code.splitlines()):
            raise ValueError("Fixed-cost assignment found")
        result.append({"name":"V1.1-"+str(threshold), "adx_threshold":threshold,
            "source":code, "settings":dict(settings,strategyName=
                "BTC V1.1 ADX"+str(threshold)+" 2021-2024")})
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
    report={"study":"BTC V1.1-A EMA20/50 + ADX14 threshold 20", "status":"NOT_RUN",
            "commit":os.getenv("GITHUB_SHA"),"run_id":os.getenv("GITHUB_RUN_ID"),
            "period":"2021-2024 development; 2025 excluded",
            "costs":"Fixed-cost field omitted. Platform effective costs must be checked.",
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
        row={"name":case["name"],"threshold":case["adx_threshold"],
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
            row["metrics"]={k:perf[k] for k in keys if isinstance(perf,dict) and k in perf}
            for path,label,arg in (("/strategy_logs","logs",params),
                ("/strategy_trade","trades",dict(params,acdate="")),
                ("/strategy_pl","daily_pl",dict(params,acdate=""))):
                row[label]=scrub(call(path,arg),secrets)
                save()
            valid=isinstance(settings,dict) and all(
                str(settings.get(k))==str(case["settings"][k]) for k in
                ("StartDate","EndDate","dataset"))
            row["status"]="COLLECTED" if valid else "INVALID_PERIOD"
            save()
            if row["status"]!="COLLECTED":
                break
        except Exception as exc:
            row.update(status="ERROR",error_type=type(exc).__name__)
            save()
            break
    report["status"]=("COLLECTED" if len(report["experiments"])==len(THRESHOLDS)
                      and all(x["status"]=="COLLECTED" for x in report["experiments"])
                      else "STOPPED")
    save()
    return 0 if report["status"]=="COLLECTED" else 1


if __name__=="__main__":
    raise SystemExit(main())
