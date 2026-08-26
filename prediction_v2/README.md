# prediction_v2 —— 无泄漏足球竞猜新方案
> ⚠️ **研究用途声明**：本项目仅用于足球预测的**研究与本地离线分析**，不提供任何投注建议，不参与任何赌博/博彩资金操作，不接入任何真实交易或下注渠道。所有回测均为历史数据的离线模拟，结果不代表未来收益。


基于本项目现有数据源（football-data.co.uk 9 大联赛原始数据）重写的预测与回测方案。
> 📍 整体升级路线（数据→特征→建模→回测→推理→风控→迭代 差距矩阵 + P0/P1/P2 行动）见 `prediction_v2/ROADMAP.md`。
核心原则：**无未来函数、开/收盘双口径、结果诚实**。任何结论都必须能由 `run_backtest.py` 复现。

---

## 一、为什么要重写

原系统（`auto_sop.py` 等）存在三个致命问题：

1. **回测假象**：`archive/value_strategy.py` 的"+240% ROI"用 Pinnacle **收盘**赔率加随机噪声冒充"模型概率"，再对比**开盘**价——本质是"收盘价打败开盘价"的漂移假象，不可交易。
2. **训练数据泄漏**：`train_all.py` 删了 `pinnacle_*` 原始赔率列，却漏删 `pinnacle_*_prob` 概率列。实测：保留该列模型 53.35%，删除后 52.19%；宣称的 53.8% 基本等于"抄 Pinnacle 收盘赔率"（收盘赔率自身命中率 53.87%）。
3. **手调系数校准失控**：λ 靠正则提取文本 × 手调系数（×0.7/×1.2/×0.85…），实战概率与市场严重脱节（如金浦场模型给出客队 83% 胜率而市场主队 1.77 热门）。

本方案全部重做：特征只使用开赛前可得数据；训练/测试按时间严格切分；下注价 = 开盘赔率（同时报告收盘价）；指标含 ROI/LogLoss/Brier/校准/基准对比。

## 二、数据源

| 数据 | 位置 | 覆盖 |
|------|------|------|
| 9 大联赛原始赛果+赔率 | `data/raw/football_data/matches_2015_2025.csv` + `football_data_recent.csv` | 37,575 场，2015–2026，含 Pinnacle/Bet365 开收盘 1X2、大小球(固定2.5)、亚盘 |
| 逐场 xG | `data/raw/soccer-dataset/fixtures.parquet`+`match_stats.parquet` → `prediction_v2/xg_cache.csv` | 32,497 场已对齐（86.5%），2015-2026；滚动 xG 特征已入模型（`xg_blend` 混合） |

字段口径：`PSH/PSD/PSA`=Pinnacle 开盘 1X2；`PSCH/PSCD/PSCA`=收盘；`P>2.5/P<2.5`=Pinnacle 大小球(2.5)；`AHh`+`PAHH/PAHA`=亚盘。

## 三、架构

```
prediction_v2/
├─ config.yaml            # 全部参数（特征/模型/回测/市场）
├─ teams_map.json         # 多源球队映射字典（build_teams_map.py 生成，98.5% 匹配）
├─ xg_cache.csv           # 逐场 xG 缓存（build_xg_cache.py 生成，86.5% 覆盖）
├─ build_xg_cache.py      # football-data ↔ soccer-dataset 逐场 xG 匹配
├─ run_backtest.py        # 回测 CLI: python run_backtest.py [--model poisson|xgb|lgb] [--xg-blend 0.25]
├─ run_predict.py         # 单场预测 CLI
├─ retrain.py             # 增量训练/重跑（多模型矩阵 + 归档 + 对比表）
├─ settle_live.py         # 实盘账本结算 CLI
├─ settle_report.py       # 50 注 ROI 报表 + 停用告警
├─ src/
│  ├─ data_loader.py      # 唯一数据入口（清洗/去重/日期兼容 + xG 合并）
│  ├─ features.py         # 无泄漏特征（Elo/攻防强度/滚动xG/滚动战绩/联赛基准/交锋）
│  ├─ models.py           # 泊松(主, xg_blend 混合) + XGBoost/LightGBM(对照)
│  ├─ markets.py          # 去水/结算(含1/4盘)/凯利/EV
│  ├─ predict_api.py      # 单场预测 API（CLI 与旧系统桥接共用）
│  ├─ backtest.py         # walk-forward 回测（无泄漏、开收盘双价）
│  └─ evaluate.py         # LogLoss/Brier/ECE/ROI/资金曲线/基准对比
└─ tests/test_pipeline.py # 38 项断言（含无泄漏构造性验证）
```

## 四、使用

```bash
python -m tests.test_pipeline               # 38 项自检
python run_backtest.py --model poisson      # 泊松主模型回测（默认 xg_blend=0.25, ~20s）
python run_backtest.py --model lgb          # LightGBM 对照（~2min）
python run_backtest.py --model xgb          # XGB 对照（~100s）
python run_backtest.py --xg-blend 0.5 --only-xg --market ou --edge 0.05  # xG 权重扫描实验
python build_xg_cache.py                    # 重建逐场 xG 缓存（football-data↔soccer-dataset）
python retrain.py                           # 增量训练：拉新数据→重跑 walk-forward→归档
python settle_report.py                     # 账本 50 注 ROI 报表
python run_predict.py "英超" "曼城" "阿森纳" 2026-08-15 \
    --odds 1.75 3.60 4.50 --ou-over 1.90 --ou-under 1.92 \
    --ah -0.5 --ah-home 2.05 --ah-away 1.80
```

输出在 `output/`：`report_*.json`、`bets_*.csv`（逐注明细）、`preds_*.csv`（全量概率）。

### 临场赔率抓取（the-odds-api，策略层）
生成"初盘→临场变化"特征，只进**策略/推理层**，禁止进训练特征（历史赔率流不可得，会泄漏）。

```bash
python fetch_live_odds.py --test          # 验证 key + 配额（免费 500 请求/月）
python fetch_live_odds.py                 # 抓全部 9 联赛并追加快照（9 请求/轮，建议 1 轮/天）
python fetch_live_odds.py --league 英超    # 单联赛
python build_odds_movement.py             # 生成 output/odds_snapshots/movement.csv
python run_predict.py "英超" "曼城" "阿森纳" 2026-08-15 --odds ...   # 自动读快照, 输出[临场]变化
```
- key 解析顺序：环境变量 `ODDS_API_KEY` → `config.json` → 项目根 `.env`（`FOOTBALL_API_KEY` 兜底，可能是 API-Football key，需 `--test` 验证）。
- 术语：「初盘」= 我方对该场的第一份快照；「临场」= 开赛前最近一份快照；变化 = 临场价 − 初盘价。
- 配额（按天安排）：免费档 500 请求/月 ≈ 16 请求/天 → **每天 1 轮全量（9 请求）+ 赛日补抓重点联赛 1-3 请求**，每月约 300-360 请求，留 140-200 余量；脚本带 `--min-remaining 40` 自动保护，剩余低于 40 停止本轮。
- 英冠/德乙 sport key：`soccer_efl_champ` / `soccer_germany_bundesliga2`（已核对 sports 列表）。

## 五、回测结果（泊松，walk-forward，2015–2026，30,671 测试场）

### 总览
| 指标 | 数值 |
|------|------|
| 全市场投注 | 59,816 注，ROI@开盘 **-2.85%** |
| 模型 LogLoss (1X2) | 1.0242（市场 0.9930，市场更准） |
| 市场基准（押热门@开盘 1 单位） | **-2.62%** |

### 分市场（泊松）
| 市场 | 注数 | ROI@开盘 | ROI@收盘 | 命中 |
|------|------|---------|---------|------|
| 1X2 | 26,115 | -6.94% | -6.42% | 27.5% |
| 亚盘 | 17,827 | -6.07% | -6.53% | 46.4% |
| **大小球(2.5) 小** | **8,716** | **+26.7% (平注)** | +24.8% | **55.4%** |
| 大小球(2.5) 大 | 7,158 | -4.8% | - | 48.3% |

### xG 滚动特征（P1-5，2026-08 实验，已默认启用）
`build_xg_cache.py` 把 soccer-dataset 逐场 xG 按 (日期,主客队) 对齐到 football-data（86.5% 覆盖）；`features.py` 增加 xG 攻防强度（时间衰减，无 xG 场次不推进状态）；泊松 λ 按 `xg_blend` 混合进球与 xG 强度（无 xG 自动回退纯进球）。

| 口径（全量数据, 小球+edge≥5%+赔率≥1.60） | 基线(纯进球) | xg_blend=0.25（默认） |
|------|------|------|
| 注数 | 5,903 | 5,202 |
| 平注 ROI@开盘 | +36.1% | **+55.5%** |
| 命中率 | 57.7% | 60.6% |
| 年度表现 | 2019-2026 每年为正 | 每年为正且均优于基线 |
| under-2.5 校准(全样本) | ECE 0.0506 / LL 0.6839 | ECE 0.0287 / LL 0.6807 |

- bootstrap 差值 CI [+14.5%, +24.4%]（b25 - 基线），统计显著；`--only-xg` 同口径下 0.25/0.5/0.75 扫描，0.25 最优。

### 旧特征移植：技术统计 + SoS（P1，2026-08）
- **tech（射门/射正/角球/犯规近5场滚动）默认启用**：XGB 1X2 LogLoss 1.0171→1.0134、LGB 1.0228→1.0201，**10/10 年改善**；下注集交叉分解：tech 新增注 flatROI -1.31%（基线被砍注 -7.86%），选注质量真实提升。
- **sos（对手强度调整攻防）不启用**：在 tech 之上零增量（LogLoss 相同），单独增益微弱。
- 注意：ML（XGB/LGB）仅是对照模型；1X2 仍负 ROI（-5.9%~-7.3%），生产策略仍是泊松大小球小球。开启方式：`--extra-features tech`（默认已开）。
- 机制：混合后砍掉基线中"边际刚好过线"的亏损注（ROI ≈ 0~5%），新增注为高置信价值注；交叉分解验证无幸存者偏差。
- **观察纪律**：实盘账本满 50 注后复核，若 ROI 跌破基线则 `config.model.xg_blend` 回退 0.0。


### 推荐打法口径：仅"小球 2.5"、边际 ≥ 5%、赔率 ≥ 2.00
| 指标 | 数值 |
|------|------|
| 注数 | 6,655 |
| 平注 ROI@开盘 | **+42.8%** |
| 命中率 | 54.8% |
| 年度表现 | 每年为正（+17.7% ~ +49.7%） |

> 2026-08-13 更新：`min_odds` 由 1.60 提升至 2.00（赔率分层显示 1.60–2.00 区间为负、2.00+ 转正；1.60 口径为 8,974 注 ROI +30.1%）。报告：`output/prod_scan_mo2/report_poisson_ou_edge0.05_xg0.25_tftech.json`。

### 大小球"小"方向的稳健性
- **每年为正**：2019–2026 平注 ROI +18.8% ~ +40.6%；74/78 个半期为正
- **边际单调**：模型-市场边际越大，ROI 越高（3–5%: +16%，12–20%: +80%）
- **双书商验证**：Pinnacle 定价平注 +26.7%（edge≥3%），Bet365 定价平注 +23.1%
- **统计显著**：bootstrap 95% CI [28.0%, 33.8%]，t > 20
- **市场校准检查**：全样本 Pinnacle 2.5 线去水概率偏差 ±2pp 内（市场本身有效），模型正是靠"与市场分歧处"的信息获利
- **注意**：同边际下"大球"方向为负（约 -5%），**只打小球**

### XGBoost 对照
1X2 上 XGB LogLoss 1.0171，ROI -9.59%——同样跑输市场基准。**结论：9 大联赛的 1X2/亚盘无法靠这套特征跑赢市场；真正的（回测内）边缘集中在大小球 2.5 的小球方向。**

## 六、推荐打法（基于回测）

1. **只打"小球 2.5"**：当 `模型小2.5概率 - 去水市场小2.5概率 ≥ 5%` 且赔率 ≥ 2.00 时下注；边际越大越值得打。
2. **禁用**：1X2、亚盘方向、大球方向（回测全部为负）。
3. **仓位**：1/4 凯利、单注 ≤ 5% 本金（回测整体组合用 10% 上限会爆仓，说明要更低）。
4. **实盘验证闭环**：每注记录模型概率/市场概率/赔率/赛果 → 每 50 注结算一次 ROI → 连续 2 个周期为负即停。
5. **小联赛（K2/中乙/J1）**：无开收盘赔率历史，无法回测，沿用"先小额、后统计"原则，用 `run_predict.py` 出方向后用真实盘口结算累计。

## 七、风险与局限（必须读）

- **回测 ≠ 实盘**：回测价是历史记录价；实盘存在下注被拒、限注、临场变盘、流动性等摩擦，真实 ROI 会显著低于回测。
- **边缘可能衰减**：OU 2.5 固定线的低效若被广泛利用，庄家会收紧；需持续回测监控。
- **数据局限**：仅 9 大联赛有可靠开收盘赔率；数据集内部分 OU 赔率缺失（约 40%），回测只用有赔率的场次。
- **单一数据集**：赛果与赔率同源，若源数据存在系统性偏差，结论会被放大（已用双书商交叉验证降低该风险）。

## 八、与旧系统的关系（已接入原 30 步 SOP）

**桥接器**：`src/features/predict_v2_bridge.py` 已把新引擎接入原系统 `auto_sop.py`：
- **Step 8.5 新引擎交叉验证**：Step 8（旧泊松/ML）之后自动执行，结果存入 `analysis_record['steps']['step8_5_v2_engine']`。
  - 9 大联赛（英超/西甲/意甲/德甲/法甲/英冠/西乙/德乙/荷甲）→ 数据集特征（无泄漏，严格只用开赛前数据）。
  - 小联赛（K2/中乙/J1/丹麦杯等）→ 原系统特征提取器从用户情报算攻防强度，套同一 λ 公式；联赛基准读 `strategy_data/*.json` 真值。
  - 投注纪律内置回测结论：**只推荐大小球2.5 小球**（边际≥5% 且赔率≥2.00），1X2/亚盘/大球一律标记"不推荐"。
- **Step 31 EV 打星对齐**：`final_best_bet` 字段按 v2 纪律给出最终实盘方向；旧引擎候选表保留供对比，`_step31_best_bet`（串关/投注校验用）以 v2 推荐为准；v2 无满足条件时维持旧引擎 best_bet。
- **逐注账本**：Step 8.5 的推荐自动写入 `prediction_v2/output/live_bets.jsonl`（按 场次+联赛+方向 去重）。赛后运行：
  ```bash
  python prediction_v2/settle_live.py "金浦 vs 忠南 1-1" "温州 vs 贵州 2-0"
  ```
  按平注口径输出每注赢/输/走水与 P&L（2.5 为半球盘无走水；整数盘如 2.0 走水）。
- 环境变量 `V2_LEDGER` 可覆盖账本路径。
- **回归纪律**：新桥接器与账本逻辑已加进 `regression_test.py`（现共 106 项断言）；修改分析逻辑后必须 `python regression_test.py` 全绿。
- 旧系统的 +240% 结论请勿继续引用。
