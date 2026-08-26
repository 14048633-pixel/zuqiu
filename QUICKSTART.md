# Quick Start — 快速上手

> 完整流程见 `使用流程.md`；部署说明见 `PACKAGE_README.md`；30 步 SOP 见 `SOP_30STEP.md`。

## 5 分钟启动（目标电脑）
```bat
:: 1. 解压迁移包到 D:\football_system
:: 2. 安装 Python 3.10+（勾选 Add Python to PATH）
:: 3. 一键部署验证（自动装依赖+验模块+跑回归）
python setup_verify.py
:: 看到 🎉 全部通过 即可使用
```

## 日常三件事
```bat
:: 赛前分析（30步SOP自动跑，输入比赛数据JSON）
python auto_sop.py 比赛数据.json

:: 盘口抓取（the-odds-api，先 --test 验证key）
cd prediction_v2
python fetch_live_odds.py --test
python fetch_live_odds.py --league 英超

:: 赛后结算（把比分当参数传入）
python prediction_v2/settle_live.py "主队 vs 客队 1-1"
```

## 质检（改完代码/提示词/SOP 必跑）
```bat
python regression_test.py   :: 106项全绿才算数
```

## 数据在哪
- 联赛真值/结算/复盘：`strategy_data/`（J1/K2/中乙/中超/丹麦杯/欧战）
- 分析记录：`analysis_records/`
- 训练数据：`data/`；模型：`models/`
- 实时盘口快照：`prediction_v2/output/odds_snapshots/`
