# 归档：92队BSD历史攻防数据（2026-08-18）

> 归档时间 2026-08-18 23:22

## 数据文件
- `data/raw/football_data/bsd_team_stats_20260818.json`（26133 字节）
- MD5 `3cc790f04505270e46eb141f22fb9b6c` ｜ SHA1 `602b0d660b81eda1d0fc3e4a5deb6caf8bc11539`
- 拉取时间 2026-08-18T15:14:43Z UTC ｜ 92 队 ｜ 5139 场赛果 ｜ 0 错误

## 覆盖
| 联赛 | 队伍数 |
|---|---|
| 欧协联 | 48 |
| 欧联 | 24 |
| 欧冠 | 14 |
| 西甲 | 4 |
| 中超 | 2 |

## 来源与口径
- 来源：BSD `GET /api/v2/events/?team_id={id}&status=finished&limit=60`
- 聚合：每队近 40 场（最多），时间衰减权重 近5场1.0 / 6-10场0.7 / 11-20场0.4 / >20场0.2，主客场分列
- 字段：`home_gf/home_ga/away_gf/away_ga/n_home/n_away/n_scored/src_tag/league/team_id`

## 已知质量问题（后续必须修复）
1. **未做对手强度归一**：弱队主场失球失真（Levski home_ga 0.32 → AEK λ 被压到 0.30）、强队客场防守被低估（Monaco away_ga 2.09 → Górnik λ 虚高）。我们 λ 仅作交叉验证，偏差>0.5 标独立观点
2. **BSD expected_goals 与 BSD 自身预测方向矛盾**（如 Inter Turku eg 主1.71/客1.22 却预测客胜63%），不能直接当 λ

## 结论（46 场 EV）
- 最终 `EV_bet = BSD预测概率 × 市场价 - 1` 全部为负（-1.3% ~ -12.9%），**0 场正 EV**
- BSD 共识赔率（多机构平均）早盘定价有效，欧联/欧协联为提前 2 天早盘，无价值腿
- 临场 30 分钟重拉后才可能出现盘口偏移

## 关联产物
- `analysis_records/scan48h_20260818_2259.json`
- `analysis_records/scan48h_20260818_2300.json`
- `analysis_records/scan48h_teams_20260818_2300.txt`
- `analysis_records/key46_20260818_2307.json`
- `analysis_records/key46_20260818_2308.md`
- `analysis_records/key46_model_ev_20260818_2316.json`
- `analysis_records/key46_ev_v2_20260818_2317.json`
- `analysis_records/key46_ev_v3_20260818_2319.json`
- `analysis_records/key46_ev_final_20260818_2319.json`
- `analysis_records/key46_ev_final2_20260818_2319.json`

## 用途
- 46 场重点联赛 λ/EV 独立计算（本次）
- 后续并入主数据池前需先做对手强度归一 + 与 load_team_stats 现有池融合验证

## 归一化 v1 追加（2026-08-18 深夜）
- 文件：`data/raw/football_data/bsd_team_stats_norm_20260818.json`（raw+norm 双字段，92队，排除511场友谊赛/女足/U19）
- 公式：`norm = Σ(值 × 对手联赛coef × 时间权重) / Σ(coef × 时间权重)`，近40场，时间衰减 1.0/0.7/0.4/0.2
- 验证结论：**仅混合赛程球队有效**（CSKA Sofia / Kuopion / Nordsjælland 方向正确，最大±0.121）；50/92 队完全零变化；Levski(保加利亚)与 Monaco/Salzburg 跨联赛水平失真未修复
- 定性：v1 为过程产物，**不入库**；待 v2 赛事图迭代 rating 通过后并入主数据池
- 报告：`analysis_records/opp_strength_norm_20260818.md` / `opp_strength_norm_20260818_summary.json`


## 归一化 v2 追加（2026-08-18 深夜）
- 文件：`data/raw/football_data/bsd_team_stats_norm_v2_20260818.json`（raw/v2/rat 三套 + src_bias + league_context）
- 边表：`data/raw/football_data/bsd_edges_20260818.json`（6706 场去重，limit=100 重拉，0 错误）
- **关键发现：BSD 仅覆盖 80 联赛，37/92 队国内联赛 0 场（奥超/克甲/塞超/以超等），只有欧战样本 → src_bias=uncovered 标记，先验=1.0**
- v2 公式：`相对本联赛场均(主客分列) × 联赛水平coef` + 收缩 K=6，修复 v1 系数抵消缺陷
- 验证：Levski 主ga 0.483→0.433（不再0.30失真）、Monaco 客ga 1.93→1.06、联赛均值随 coef 单调
- 迭代（rat，阻尼0.5×4轮）：强弱赛程修正有效但池均值尺度漂移（def≈1.37），仅参考
- 报告：`analysis_records/opp_strength_norm_v2_20260818.md`


## 归一化 v3：国内联赛补齐（2026-08-18 深夜）
- 数据：`data/raw/football_data/bsd_team_stats_norm_v3_20260818.json`（92队统一，final_* 主用）
- 来源：HF soccer-dataset 本地数据集（2008-2027，67.4万场）国内联赛 + BSD 欧战
- 覆盖：32队国内补齐（奥超4/克甲3/塞超2/以超3/捷甲3/匈甲1/阿塞2/塞浦2/斯洛伐克1/斯洛文尼亚1/波黑1/格鲁吉亚1/哈1/亚美尼亚1/立1/拉1/爱1/北爱1/直1/科索沃1），3个队名映射修正
- 融合：`final = (w_euro×euro_v2 + w_dom×dom_est)/(w_euro+w_dom)`，w=min(n,20)；国内日期衰减+陈旧检测
- 92队分类：covered=55 / domestic_merged=31 / no_domestic=6（阿尔巴尼亚2、安道尔、法罗、冰岛、里加陈旧）
- 报告：`analysis_records/opp_strength_norm_v3_20260818.md`


## v3 λ 集成验证（2026-08-18 深夜 → 08-19）
- 接入：v3 final_* 全量接入 λ 链路，46/46 覆盖
- 结果：1X2 EV>5% 旧14→v3 22，但 10 场 EV>50% 多为逆市场假正（Getafe/Partizan 客胜EV+285%、Motherwell/Freiburg 主胜EV+109%）
- 根因：v2收缩拉平精英防守（Getafe 主场失球0.72→0.96）+ 融合数据压缩强度差（Partizan 客防1.52→0.92）+ 跨联赛相对评级无法正确复合
- 结论：**v3 暂不替换 raw λ 作 EV 主引擎**，保留覆盖+交叉验证；中期需跨联赛 level-gap 校准 + 放开收缩K
- 报告：`analysis_records/key46_v3_lambda_validate_20260818.md`
