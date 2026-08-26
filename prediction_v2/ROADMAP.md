# prediction_v2 升级路线图（对齐"数据→特征→建模→回测→推理→风控→迭代"框架）

> 整体思路：数据采集 → 数据清洗与特征工程 → 标签定义 → 模型选型与训练 → 回测校验 → 实盘推理系统 → 风控与迭代。
> 状态标记：✅ 已落地 / 🟡 部分 / ❌ 缺失。
> 本文件是"方案升级"的工作底稿：每项行动都有明确落点，改代码后必须 `python regression_test.py` 全绿。

---

## 0. 当前架构总览（现状映射）

| 层 | 现状 | 落点 |
|----|------|------|
| 数据源层 | ✅ football-data.co.uk 9 大联赛 37,575 场（2015–2026，含 Pinnacle/Bet365 开收盘 1X2/大小球/亚盘） | `data/raw/football_data/` |
| | ✅ soccer-dataset 逐场 xG 已接入（86.5% 匹配率，滚动特征实验完成） | `data/raw/soccer-dataset/` + `prediction_v2/xg_cache.csv` |
| | 🟡 赔率流（初→临场变化）CSV 未接入 | `data/processed/matches_with_odds_flow.csv` |
| | ✅ 小联赛真值（K2/中乙/J1）+ 用户情报 | `strategy_data/*.json` |
| 数据仓储 | ✅ CSV 文件（raw/processed + `prediction_v2/output`） | — |
| 特征工程 | ✅ 无泄漏单遍时间扫描（Elo/攻防强度/滚动5场/休息天数/联赛均值/交锋） | `prediction_v2/src/features.py` |
| 建模 | ✅ 泊松（基线）+ XGBoost（1X2 对照） | `prediction_v2/src/models.py` |
| 回测 | ✅ walk-forward、开收盘双价、ROI/LogLoss/Brier/ECE/回撤/分年/市场基准/bootstrap CI | `prediction_v2/src/backtest.py` `evaluate.py` |
| 推理 | ✅ CLI + 原系统 Step 8.5 桥接（`predict_api` + `predict_v2_bridge`） | `prediction_v2/src/predict_api.py` |
| 风控 | ✅ 只推小球2.5（边际≥5% 且赔率≥2.00）、1/4 凯利、单注≤5%、串关用 best_bet、逐注账本 | 桥接器 + `auto_sop.py` |
| 监控迭代 | 🟡 账本结算 P&L；❌ 无自动漂移监控/增量训练/实时抓取 | `prediction_v2/output/live_bets.jsonl` |

---

## 1. 两条路线定位

**统计机器学习路线（入门首选，本项目主线，已基本落地）**
- 泊松（基线，含 `penaltyblog 1.11` 可升级 Dixon-Coles）→ XGBoost（✅ 已回测）→ LightGBM（✅ 已接入 `--model lgb`）→ **CatBoost（✅ 已接入 `--model cat`，08-16 对照回测）**。
- CatBoost 对照（2017-2026 walk-forward, 1X2, 同口径带tech特征）: 21471注/命中26.9%/LogLoss 1.0134/Brier 0.6064/ECE(home) 0.0243/凯利ROI@开 -8.49%; XGB -12.19%, LGB -12.71% → **三者均跑输市场, 但 CatBoost 校准最优(LogLoss/ECE 三项最小)**; 不改变"唯一正期望=大小球2.5小球"结论, 仅作对照.
- ⚠️ 结论已修正（08-16 settle bug 修复后）：**不存在"小球2.5 +30.9%正期望"**——该数字是回测 OU 结算 bug 假象（under 腿未乘 -1，把大球结果当小球赢）。修正后全市场均跑输：泊松 OU 平注 -7.5%/凯利 -5.7%，CatBoost OU -6.2%/-9.1%，1X2/亚盘亦负。当前回测口径下**无正期望市场**；后续方向=增强特征(伤停/轮换/临场盘)或真实临场盘口套利，勿依赖历史回测放大。

**深度学习高阶路线（数据量不足，仅作对照，勿为主力）**
- MLP（🟡 torch 已装，可做校准对照）→ LSTM/Transformer（❌ 需按时序重组数据且数据量不足，**暂不追**）。
- 判定标准：新模型只有在**回测 ROI/LogLoss 均显著优于泊松+XGB，且分年稳定**时才替换主力；否则只作对照。

---

## 2. 分环节差距与行动

### 2.1 需求与目标定义（✅/🟡）
- 目标已收敛：主推大小球 2.5 小球；1X2/亚盘作为对照与风控输入。
- 待固化：明确"初盘下注 / 收盘复核"口径已写入 `config.yaml`，下一步把"是否剔除杯赛/友谊赛、只用主流联赛"写进配置注释。

### 2.2 数据源建设
| 数据 | 现状 | 行动 |
|------|------|------|
| 历史赛果+赔率（9 联赛） | ✅ | — |
| 开/收盘赔率 | ✅ Pinnacle/Bet365 | — |
| 赔率流（初赔→临场） | ✅ `fetch_live_odds.py`（the-odds-api 快照） | **P1 部分完成**：`output/odds_snapshots/` + `build_odds_movement.py` 变化表；只进**策略层/风控层**（不进训练特征） |
| xG/技术统计 | ✅ `build_xg_cache.py` → `xg_cache.csv`（32,497/37,575=86.5%）；滚动 xG 强度已入特征层 | **P1 已完成**：`xg_blend=0.25` 生产口径 ROI +55.5%（基线 +36.1%） |
| 伤停/战意/赛程密集度 | 🟡 原系统手工情报 + 特征提取器 | **P2**：结构化采集 |
| 实时临场赔率 | 🟡 `fetch_live_odds.py` 手动抓取已可用 | **P1**：任务计划/crontab 定时抓取（免费 500 请求/月，建议 1 轮/天） |

### 2.3 数据清洗与仓储
-- ❌ **落账前赛程/队名双校验（08-17 结算暴露）**：**P1** ① 一线队/二队黑名单（例：西乙 Cádiz 对手实为 RC Celta Fortuna（Celta B 队），曾误记为 Celta Vigo 一线队）；② 落账前用赛程快照（ESPN/BSD）确认“当日该联赛确有该对阵”，无对阵拒绝落账并标注（例：08-15 荷甲账本出现 PSV vs Ajax，实际当日荷甲无此赛）；③ 结算时无赛果注保持待结算并标注来源错误，禁止强算。
 ✅ 清洗去重/日期兼容：`data_loader.py`。
- ❌ **球队映射字典（多源译名统一）**：**P0** 建 `teams_map.json`（基于 `soccer-dataset/teams.parquet` + football-data 队名），支撑 xG/odds 接入。
- 🟡 存储：CSV 够用；赔率流规模化后再上 SQLite/PostgreSQL+TimescaleDB（**P2**）。

### 2.4 特征工程（核心）
- ✅ 基础特征已无泄漏；✅ 赔率不进入训练特征（由回测证实"模型概率≤市场"，避免抄市场），仅作策略层定价。
- ✅ **滚动 xG 特征已完成（P1-5）**：`features.py` xG 攻防强度（衰减更新，无 xG 场次不推进状态）；`models.py` 泊松 `xg_blend` 混合（无 xG 自动回退纯进球）；生产口径 ROI +36.1%→+55.5%（bootstrap 显著），已默认启用 `config.model.xg_blend=0.25`。
- ✅ **旧系统特征移植已完成（P1）**：`features.py` 增加技术统计滚动（射门/射正/角球/犯规，近5场）+ SoS（对手强度调整攻防，衰减加权、对手 Elo 用赛前快照无泄漏）；`feature_matrix(feat, extra=...)` + `run_backtest --extra-features tech,sos`。回测：tech 使 XGB LogLoss 1.0171→1.0134、LGB 1.0228→1.0201（10/10 年改善，选注新增注 -1.31% vs 被砍注 -7.86%），**已默认启用 `extra_ml_features:[tech]`**；sos 在 tech 之上零增量，不启用。ML 1X2 仍负 ROI（-5.9%~-7.3%），「1X2 打不过市场」结论不变。
- ❌ 赛程疲劳、伤停 → **P1** 实验（逐一对比，防过拟合）。
- ❌ 特征筛选管线（相关性/重要度报告）→ **P1**。

### 2.5 标签定义（✅）
- 方案 A 泊松：`home_goals / away_goals` ✅（λ_h/λ_a）
- 方案 B 1X2：`0=客胜 1=平 2=主胜` ✅
- 方案 C 大小球：`0=小 1=大` ✅（**唯一正期望所在**）
- 扩展：半全场/BTTS → **P2**。

### 2.6 模型选型与训练
| 模型 | 状态 | 行动 |
|------|------|------|
| 双变量泊松（基线） | ✅ | 可升级 penaltyblog Dixon-Coles（**P2**） |
| XGBoost | ✅ 已回测 | — |
| LightGBM | ✅ 已接入 `--model lgb`（P0） | 1X2 平注 ROI -6.16%，与泊松/XGB 结论一致（跑输市场） |
| MLP | 🟡 torch 已装 | **P1**：作校准对照 |
| LSTM/Transformer | ❌ | **P2**：数据量不足，暂不追 |
| 增量训练 | ❌ | **P0**：`retrain.py`（拉新数据→重跑 walk-forward→出报告→归档模型） |

### 2.7 回测校验（✅/🟡）
- ✅ walk-forward / 开收盘双价 / ROI / LogLoss / Brier / ECE / 平注最大回撤 / 分联赛分年 / 市场基准 / bootstrap CI。
- 🟡 Sharpe、盈亏比 → **P1** 补进 `evaluate.py`。
- 🟡 佣金假设 → **P1**：devig 已含水位，再加固定佣金档位（如 -5%）看 ROI 敏感性。
- ✅ 过拟合识别：分年稳定性已有；**P1** 加"新赛季测试段 ROI 转负"告警。

### 2.8 实盘推理系统
- ✅ `run_predict.py` + `predict_api` + `auto_sop` Step 8.5 桥接。
- ❌ FastAPI 服务 → **P1**：`pip install fastapi uvicorn`，`/predict` 复用 `predict_api`（无状态，天然可并发）。
- ❌ 赛前自动抓取+自动推理 → **P1**：crontab/Celery + Redis 缓存临场赔率。

### 2.9 风控系统（✅/🟡）
- ✅ EV 阈值（边际≥5%）、1/4 凯利、单注≤5%、只推小球 2.5、串关强制 best_bet。
- 🟡 连续亏损降仓 / 单日总资金上限 / 低置信过滤 → **P1** 策略规则层（纯规则，进 `config.yaml`）。
- ⚠️ 限注/流动性摩擦无法在回测完全模拟：账本按**回测 ROI 打折**预期。

### 2.10 监控、日志、持续迭代（🟡）
- ✅ 逐注账本 `live_bets.jsonl` + `settle_live.py`（每注 赢/走水/输 + 平注 P&L）。
- ❌ 50 注 ROI 报表 → **P0**：`settle_report.py`（自动汇总，超阈值告警）。
- ❌ 模型漂移监控（胜率/ROI 趋势）→ **P1**。
- ❌ 自动增量训练 → **P0**（见 2.6）。
- ✅ 回归纪律：`regression_test.py` 100 项，改逻辑必须全绿。

---

## 3. 落地实施顺序（P0 → P1 → P2）

**P0（本周，先闭环）——已完成 ✅**
1. ✅ 球队映射字典 `prediction_v2/teams_map.json`（生成脚本 `build_teams_map.py`；football-data 269 队 ↔ soccer-dataset 匹配 265 队 = 98.5%，未匹配 4 队已列出待手工补录）。
2. ✅ LightGBM 加入回测矩阵（`--model lgb`，`models.py` 新增 `LGBModel`，`backtest.py` 泛化 `ml` 分支）。结果：1X2 平注 ROI **-6.16%**（LogLoss 1.0228），仍跑输市场，与泊松/XGB 结论一致。
3. ✅ `retrain.py` 增量训练/重跑脚本（多模型矩阵 + 归档 `output/archive/日期/` + 横向对比表）。
4. ✅ `settle_report.py` 账本 50 注 ROI 报表（分联赛/分月 + 窗口判定 + 连续负期停用告警）。

> 回归已扩至 **106 项全绿**（P0 交付物断言：映射字典 + 账本报表；P1-5 改造后重跑确认无回归）。

**P1（2–4 周，扩展与工程化）**
5. ✅ **滚动 xG 特征实验（已完成）**：`build_xg_cache.py`（football-data↔soccer-dataset 逐场匹配 86.5%）→ `features.py` xG 强度 → `models.py` `xg_blend` 混合。扫描 0/0.25/0.5/0.75（`--only-xg --market ou --edge 0.05`）：小球口径 flatROI 30.6%→55.6%/49.7%/40.1%，**0.25 最优**；全量生产口径（小球+edge≥5%+赔率≥1.60）5,202 注 flatROI **+55.5%**（基线 5,903 注 +36.1%），bootstrap 差值 CI [+14.5%,+24.4%] 显著，2019-2026 每年为正且优于基线；under-2.5 二元校准改善（ECE 0.0506→0.0287，LogLoss 0.6839→0.6807）。已设默认 `xg_blend=0.25`（无 xG 场次自动回退）。**持续观察**：实盘账本满 50 注后复核，若 ROI 跌破基线则回退 0.0。
6. 赔率流（初→临场）接入策略/风控层（不进训练特征）。
7. FastAPI 推理服务 + crontab 赛前自动抓取/推理。
8. 风控规则层：连续亏损降仓、单日上限、低置信过滤。
9. `evaluate.py` 补 Sharpe/盈亏比/佣金敏感性；漂移告警。

**P2（视数据与效果）**
10. MLP 对照；LSTM/Transformer（需更大数据，先不做）。
11. 半全场/BTTS 标签扩展。
12. PostgreSQL + TimescaleDB 规模化赔率流。
13. 伤停/战意结构化数据采集。

---

## 4. 致命坑对照（当前方案已规避 / 仍要注意）

| 坑 | 当前状态 |
|----|---------|
| 数据泄露 | ✅ 特征单遍时间扫描 + `test_no_leakage` 构造性验证 |
| 随机划分而非时间划分 | ✅ walk-forward 按时间切分 |
| 只用准确率 | ✅ ROI/LogLoss/Brier/ECE/回撤全指标 |
| 不搭基线 | ✅ 泊松 + 市场基准双基线 |
| 过度堆特征 | ✅ 当前特征精简，新特征逐一回测对比 |
| 忽略市场水位/佣金 | 🟡 devig 去水已做；佣金敏感性 **P1** |
| 回测虚高 | ✅ 开收盘双价、bootstrap CI、双书商验证 |

---

## 5. 一句话结论

> 当前 `prediction_v2` 已把框架的"数据→特征→建模→回测→推理→风控"主链跑通并诚实得出"只有小球 2.5 正期望"；P0 与 P1-xG 已完成（LightGBM 对照、增量训练、xG 滚动特征默认启用后 ROI +36.1%→+55.5%）；下一步按 P1 剩余项补齐 **赔率流接入、FastAPI 服务化、风控规则层与漂移监控**，深度模型仅作对照不追。
