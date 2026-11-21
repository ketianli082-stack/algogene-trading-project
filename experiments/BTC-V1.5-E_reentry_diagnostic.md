# V1.5-E — Re-entry diagnostic (2026-11-21)

## Objective

C/D showed 9/15 RECOVERY_ARMED and zero RECOVERY_CANDIDATE or actual REENTRY. Diagnose state/condition failures before any rule changes.

## Mechanism and controls

Instrumented V1.5-C clone: long only; 12-hour cooldown; 2 reentries per trend; EMA20 recross; ADX25; EMA200; S2 cost-aware sizing; 3 ATR stop. No order, signal or risk decision changes. Hypothetical costs enter sizing only; TradeCost omitted.

New Recovery.explain diagnostic reports NOT_ARMED, LIMIT, NO_PRIOR_TIME, COOLDOWN, NOT_READY, TREND_LOST, ALREADY_ABOVE_EMA20, NO_RECROSS_EMA20, ELIGIBLE. Additional logs: RECOVERY_DIAG, RECOVERY_TREND_RESET, RECOVERY_CLOSE_CLASSIFY. Eligibility for actual trades still uses original predicate.

## Code and execution

- [Strategy](../strategy/btc_v1_5_e_reentry_diagnostic60.py)

- [Runner](../tools/btc_v1_5_e_cloud_run.py)

- [Tests](../tests/test_btc_v1_5_e.py)

- [Workflow](../../actions/workflows/btc-v1-5-e-cloud.yml)

- [Run 44902721758](../../actions/runs/44902721758), initial status queued. Result unverified.

## Acceptance and next steps

First verify native run success, COLLECTED evidence, effective dates/settings, and the same transactions/Score as C; any difference requires diagnosis. Attribute eligibility failures by stop event and observed hour. Only then consider a separate E-fix mechanism and run. F sideways filtering remains a separate experiment and is not started.

## 原生回测结果与根因（2026-11-21，已验证）
- [正式运行 44902721758](../../actions/runs/44902721758)：GitHub Action success；artifact 14706628578；evidence.json 顶层与实验 status 都为 COLLECTED；ALGOGENE runtime 20261121_121336_928818。
- E 的 Score 57.35435712141972、PnL USD 2789.7827369999995、AnnualSharpe 1.1599299725846333、maxDrawdown_pct 0.031942494758422924、TradeCnt 127，均与先前 C 完全一致；说明仅加日志未改变策略结果。
- 实际 63 次 EXIT_SIGNAL，RECOVERY_CLOSE_CLASSIFY 63 次，其中 ATR 9、EMA 54；RECOVERY_ARMED **9 次**；RECOVERY_CANDIDATE 0，REENTRY 0。
- RECOVERY_DIAG 共 26 条，诊断原因全部为 **COOLDOWN**（注意是逐小时日志数量，不是26次独立止损）。
- 9 次 RECOVERY_ARMED 在反向 EMA 信号引发 RECOVERY_TREND_RESET 之前存续小时依次为 **3、1、2、1、4、1、3、9、11**，均严格小于预设的12小时冷却期。因此没有任何已激活恢复资格存续至首次有效允许时间，EMA20重穿、ADX与EMA200的后续门槛没有机会成为实际主要阻断项。
- 典型例子：2024-08-20 16:00 触发 ARMED，同年8月21日 03:00（11小时后）出现反向 EMA 交叉并 reset，尚未达到12小时。

### 关键机制冲突
原始 C 要求停止交易后冷却至少12小时，且反向 EMA20/50 交叉即永久取消当前趋势恢复资格；在本次样本中两者组合使重新入场成为**不可达路径**。即便延长资格有效期，若仍要求重新入场时原方向 EMA20/50 保持成立，则反向交叉后的重新形成可能本身产生普通新金叉，需区分“新趋势初始入场”和“止损后恢复入场”，避免重复计数与数据泄露。

### 后续研究决定（尚未提交新回测）
不在诊断版本中直接缩短冷却期或放宽强制止损。下一组 E-fix 应当预注册并隔离修改：可先验证2、4、6小时冷却的纯机制可达性（不是认定最优），或将恢复识别改为止损后仍具方向性的回调反弹结构；限制只有在原 EMA 趋势有效时才可 re-enter，且任何反向交叉立即取消资格。需要逐条件日志与完整交易贡献，防止简单为增加交易数而过拟合。2025 不参与选择。
