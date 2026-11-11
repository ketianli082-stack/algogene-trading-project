# 目录及文件存放规范

```text
algogene-trading-project/
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── docs/
│   ├── execution_plan.md
│   ├── team_roles.md
│   ├── repository_structure.md
│   └── decisions.md
├── src/                 # ALGOGENE 策略代码，A 主责
├── configs/             # 参数、样本、成本及风险设置，A/B 核对
├── analysis/            # 指标计算与图表程序，B 主责
├── experiments/
│   ├── experiment_log.csv
│   └── README.md        # 单次实验规范
├── results_summary/     # 可公开的小型汇总及图表
├── report/              # 章节提纲与公开证据索引
└── .github/
    └── pull_request_template.md
```

## 仓库与共享空间的边界

| 内容 | 正式存放位置 | 规则 |
| --- | --- | --- |
| 规格、代码、配置、研究记录 | GitHub | 分支修改，复核后合并 |
| 大型原始行情及完整运行输出 | 团队受限共享空间 | 保留原始副本；遵守课程授权 |
| 共同编辑的 Word 报告 | 团队受限共享空间 | 唯一主文档，评论与修订 |
| 小型实验汇总 | GitHub | 先检查公开权限及敏感信息 |
| 最终提交文件与凭证 | 团队受限共享空间 | 冻结发布包，防止误公开 |

README 文件用于保留目录并说明职责。尚未编写的策略、参数或分析程序不创建伪实现。

## 单次实验结果包

完整结果包建议包含 notes.md、strategy.py、settings.json、daily_equity.csv、trades.csv、summary.csv、logs.txt 和 screenshots/。按平台实际输出调整，缺失内容在 notes.md 说明。

公开仓库默认只保留实验登记和经确认可公开的汇总。完整包以实验 ID 存放在受限空间，公开索引使用内部位置编号，不放公开可访问的私密分享链接。

## 追溯要求

每次正式运行记录运行前的准确代码提交编号及配置文件路径。提交编号指向运行使用的代码，不能只填写后来上传结果的提交。若平台内另行修改代码，先保存对应修改再登记，或明确说明差异。

## 命名

实验使用 EXP001、EXP002 等唯一编号。图表名称包含实验编号及内容，如 EXP007_drawdown.png。最终发布使用明确版本标记，不使用“最终版2”“最终最终版”等名称。
