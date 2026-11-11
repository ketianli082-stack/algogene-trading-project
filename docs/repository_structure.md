# 目录及文件存放规范

```text
algogene-trading-project/
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── docs/
│   ├── execution_plan.md           # 全过程
│   ├── teacher_questions.md        # 28 题、负责人和证据状态
│   ├── team_roles.md               # 任务及交接
│   ├── platform_capabilities.md    # C 汇总，A/B 提供专业输入
│   ├── strategy_spec.md            # A
│   ├── risk_capital_spec.md        # B：规则及模块接口
│   └── decisions.md
├── src/                           # A：交易核心和整合；risk/ 由 B 制作
├── configs/                       # A：实现配置，采用 B 的政策和 C 的实验设置
├── analysis/                      # C：绩效程序；B：风险资金程序
├── experiments/                   # C：计划、登记、可公开实验说明
├── results_summary/               # 各人保存有来源的可公开汇总
├── report/                        # 六个章节按负责人分开
└── .github/pull_request_template.md
```

## 数据交流

平台原始数据共享字典、覆盖、获取方法和处理规则，不强制导出整套行情。完整回测包保存在团队受限空间，包含平台可提供的代码快照、配置、净值、交易、日志、ID 及说明。不能导出的项目先测试回调记录；仍不可得则说明限制。

公开仓库只放获准公开内容。不放个人身份、账户私密资料、课程受限数据及私人分享链接。报告主文档及最终提交凭证放受限共享空间。

## 交接和追溯

A 给 C 准确运行代码与配置；C 给各人统一输出、字段及口径；B 给 A 可接入风险仓位模块和规格，给 C 资金规模和杠杆结论；三人给 C 自己写完的报告章节。每份成果标明负责人、任务/问题 ID、版本、来源和未确定事项。

正式运行记录运行前准确代码提交，不能只填之后上传结果的提交。实验使用 EXP001 等唯一编号，不覆盖旧记录；最终代码、配置、报告与 Backtest ID 固定对应。
