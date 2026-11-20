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
- 不在代码或平台配置里硬编码固定 `TradeCost` 代替百分比成本；完整交易费/滑点/Funding在独立实验处理。
- 所有实际结果必须有 GitHub Actions run、真实数据范围和原始文件支持；未验证则标记NOT RUN或UNKNOWN。
- 2025年已经可能被以往研究利用，不能自动宣称严格独立样本外。
