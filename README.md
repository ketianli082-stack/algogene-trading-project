# ALGOGENE BTC 单资产趋势交易研究

当前 BTC 研究：EMA20/50 → ADX 趋势过滤 → ATR 风险退出 → 市场状态 / 仓位管理 → 成本感知决策 → 多空双向与止损后重新入场 → LLM 增量实验。2021–2024 开发，2025 保留检验。

- [完整策略机制、交易流程与实验安排（统一入口）](experiments/BTC_完整策略机制与实验安排.md)
- [S1 成本感知入场](experiments/BTC-V1.4-S1_cost_aware_entry.md) / [S2 成本感知仓位](experiments/BTC-V1.4-S2_cost_aware_sizing.md)
- [V1.5 活跃度、多空双向与止损后重新入场实验设计](experiments/BTC-V1.5_activeness_long_short_reentry.md)
- [V1.5 A–D 结果、震荡期识别与 E–H 更新实验路线](experiments/BTC-V1.5_results_and_next_experiments.md)
- [完整 BTC 研究路线](experiments/BTC_research_roadmap.md)
- [V1.0–V1.1 回测比较、亏损诊断及成本敏感性](experiments/BTC-V1.1_results_and_loss_analysis.md)
- [V1.2-B 策略代码](strategy/btc_v1_2_b_atr60.py)：ADX25 + 3 倍 ATR14 固定止损
- [V1.2-B 独立 Action](../../actions/workflows/btc-v1-2-b-cloud.yml)

以下保留此前基差研究记录，不作为当前 BTC 趋势策略的绩效证据。

---

# ALGOGENE BTC/ETH 现货—永续合约基差均值回归策略

## 新研究主线
原有 EXP-001 至 EXP-016 等旧项目内容已备份至分支 [archive/pre-basis-research-2026-11-20](../../tree/archive/pre-basis-research-2026-11-20)。此主分支已重新整理为基差均值回归研究。

- **V8.1 基准策略**：[strategy/crypto_basis_v8_1.py](strategy/crypto_basis_v8_1.py)，买入现货/卖空等币数量永续合约。基差收敛并不保证套利盈利。
- **首项统计实验 BAS-002A**：[实验协议](experiments/BAS-002A_基差均值回归验证.md)，检验高Z-score正基差出现后24/48/72小时的实际变化。
- **研究总路线**：[完整实验研究方案](experiments/00_完整实验研究方案.md)，覆盖成本、参数、资金杠杆、压力测试和冻结后检验。
- **策略数学与机制**：[策略原理与参数](docs/策略原理与参数.md)；[Funding口径](docs/BAS-001_年度平均Funding方案.md)。

## 开始测试
[GitHub Actions：BAS-002A Pilot](../../actions/workflows/bas002a-mean-reversion.yml) 由对应工作流文件首次推送触发，也支持手动运行。只调用ALGOGENE的 `history_price` GET读取历史数据，不会发送订单、开实盘或提交云端回测。需要GitHub Actions secrets：`ALGOGENE_USER_ID`、`ALGOGENE_API_KEY`。

2024-12-31是第一轮采样锚点，每个品种请求720条小时数据，严格按UTC时间戳对齐；用先前168条基差记录计算z-score，观察未来24、48、72小时基差变化。若只有close没有Bid/Ask，统计值被标为**非可执行的close代理**，不得误写成收益。第一轮不是2021–2024全历史验证。

## 研究要求
- 不在代码或平台配置里硬编码固定 `TradeCost` 代替百分比成本；基差项目的费用/Funding另行研究；当前 BTC 趋势策略的预估手续费和滑点仅参与决策，不要求平台原生扣费。
- 所有实际结果必须有 GitHub Actions run、真实数据范围和原始文件支持；未验证则标记NOT RUN或UNKNOWN。
- 2025年已经可能被以往研究利用，不能自动宣称严格独立样本外。
