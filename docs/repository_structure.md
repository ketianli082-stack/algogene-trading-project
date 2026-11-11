# 目录与阶段

```text
algogene-trading-project/
├── README.md
├── CONTRIBUTING.md
├── docs/
│   ├── meeting_2026-11-11.md    # 今晚议程与待填写决定
│   ├── candidate_protocol.md   # 统一候选交付、比较和测试纪律
│   ├── team_roles.md           # 前期各自完整，后期重新分工
│   ├── execution_plan.md
│   ├── teacher_questions.md    # 28 题
│   ├── platform_capabilities.md
│   ├── strategy_spec.md        # 后期 S
│   ├── risk_capital_spec.md    # 后期 R
│   └── decisions.md
├── candidates/
│   ├── member_a/               # A 的完整基础版本
│   ├── member_b/               # B 的完整基础版本
│   └── member_c/               # C 的完整基础版本
├── src/                        # 选型后主策略，S 整合，R 做 risk/
├── configs/                    # 选型后正式配置
├── analysis/                   # 主策略绩效与风险资金分析
├── experiments/               # 主策略及共同实验索引
├── results_summary/            # 可公开汇总
└── report/                     # 选型后六章正文，S/R/E 各两章
```

每个候选作者保存说明、真实实现后加入的脚本和配置、实验登记和开发结果。初始没有伪造策略或输出。正式运行记录运行前代码提交编号，结果上传后的编号不能替代它。

公开仓库不放身份、密码、私密账户、未经授权行情、完整大型日志或私人分享链接；这些存团队受限空间。平台不能导出数据时先试记录，不补造。

选型后保留原候选版本，集中完善一套主策略。S/R/E 是后期职责而非固定 A/B/C。代码整合与报告整合均不代替其他人的研究。
