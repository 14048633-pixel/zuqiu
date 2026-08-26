# 会话启动指令
> **每次新会话必须执行：**
> 1. 读取 `SESSION_STATE.md` — 获取上次会话状态
> 2. 读取 `OPERATION_GUIDE.md` — 实战操作手册（赛前分析/投注纪律/赛后结算/验证闭环）
> 3. 读取 `strategy_data/` 下的数据文件 — 了解当前进度
> 4. 运行 `python regression_test.py` — 回归质检，确认历史正确结论未被破坏
> 5. **修改任何分析逻辑(代码/提示词/SOP)后，必须重跑 `regression_test.py` 确认全绿**

# 联赛真值校准（分析比赛时必须查）
> **每个联赛分析前，查 `strategy_data/*_odds_zones.json` 的区间真值，用于判定方向（不反推λ）：**
> - **K2** → `k2_odds_zones.json`：区间1-5真实胜平负 + 亚盘赢盘率
> - **中乙** → `cl2_odds_zones.json`
> - **J1** → `j1_odds_zones.json`：2026跨年赛季, 含临场盘口变化规律/强队客场/保级主场/上半场/梯队/规则改动影响
> - **规则改动提醒（J1重点）**：2026新规(取消分区/外援5人/VAR点球收紧/U23取消)下, 近3赛季旧基准可能失效——外援增多(大球↑) vs VAR点球收紧(小球↑)相互抵消, 新赛季前10-15轮为校准期, 旧数据仅作参考
> - **改制对比（J1）**：`version_comparison`含旧自然年(18队2.27球)/过渡赛季(实测46.1%大球,2.62场均,规则不同不可直接套用)/新跨年正式赛季(20队, 官方预设2.40已弃用, 开季20场实测3.35/大2.5=70%/主40客40)。**过渡赛季数据完全失真禁用**；新赛季=旧基准小幅上调客胜+强队客场赢球率；下半程2月后侧重保级主场小球平局
> - **核心规律**：
>   - 深盘（主让≥1球）→ 穿盘率仅37%，受让方安全，防走盘
>   - 高赔主场（主赔>2.8）→ 客队方向（客胜50%）
>   - 中庸盘（1.76-2.25）→ 胜平负均分，平局价值最高
>   - 平局赔率3.20-3.35 → 平局概率>1/3，重点防平
>   - K2主场优势极弱（客胜33.75%≈主胜），慎推主队深盘
> - **临场盘口判定**（J1/K2通用）：同步升盘降水=可信方向；独自升盘升水/急速跳水=诱盘陷阱；深盘升盘=诱热难穿盘

# 数据格式铁律
> **遇到不认识的用户数据格式，禁止猜格式或跳过。**
> 1. 查 `strategy_data/DATA_FORMATS.md` — 系统支持的所有格式清单
> 2. 清单内有 → 正常解析
> 3. 清单外 → **停下问用户确认格式** → 加解析代码 → 写回归断言 → 跑回归全绿 → 更新清单
> 4. 提取不到的数据 → 明确标注"该字段未提取"，禁止静默填0或编造

# 输出规范（必须遵守）
> **每次比赛分析的最终结论必须展示完整链条，一步不跳、一步不漏：**
> 1. **Step 0.5 数据提取器**：主客区分 + 盘口提取 + 情报分离
> 2. **Step 7.5 Agent风险信号**：各信号值 + 方向（在模型计算前，供λ修正）
> 3. **Step 8 模型计算**：λ值 + TOP比分 + 大小球/让球概率
> 4. **Step 30 Agent战术分析**：完整输出（DeepSeek）
> 5. **Step 31 EV打星**：候选表 + best_bet + 星级
> 6. **方向组一致性（固定输出，规则 v1 不得改动）**：每组（1X2/让球/大小球）取 EV 最高的正EV腿为组方向；无正EV取EV最高腿并标注。等级写死：`三向一致`(主胜+让主+大 或 客胜+让客+大)、`主向稳胜`(主胜+让主+小)、`客向稳胜`(客胜+让客+小)、`主向分歧`(1X2与亚盘反向)、`平局主导`、`无正EV`。每场必须输出该字段，格式 `方向组一致性: [1X2=…|让球=…|大小球=…] level`。
> 禁止只给最终推荐而漏掉中间环节

# Complete Results Summary

## Best Model: XGBoost + Platt (53.8% accuracy)
Training config: `n_estimators=200, max_depth=4, lr=0.03, subsample=0.7, colsample=0.8, min_child_weight=1, reg_lambda=1.0`

```
Model                    Accuracy  LogLoss   Notes
─────────────────────────────────────────────────────
XGBoost+Platt  ← BEST   53.8%     0.9752    Best single model
XGBoost (raw)           53.6%     0.9749    
XGBoost + xG            53.66%    0.9766    +0.3pp acc, but ROI ↓
MLP (128,64)            53.3%     2.7052    Good acc, bad calibration
XGB+PoissonFeat         52.4%     0.9984    Poisson xG didn't help alone
LSTM (seq_len=8)        47.8%     1.0724    Needs more data/architecture work
Poisson (pure)          29.2%     1.4071    Team strengths only, too simple

Ensembles:
  XGB + Poisson avg     54.2%     0.9766    Marginal improvement only
```

## ⛔ 已废弃结论: "Pinnacle周五盘 +240% ROI"（2026-08-26 审计隔离）
> **禁止引用、禁止作为决策依据。**
> 原声称"12,997注/9年/ROI+240.90%，逐年全正"。2026-08-26 全仓审计结论：
> 1. 仓库内**无任何脚本/数据可复现**该数字；
> 2. 最接近的产出物 `data/backtests/value_bets_historical.csv`（3,865注实测）等额ROI **−8.10%**；
> 3. 实盘账本合规口径（剔除snap<0赛后盘）762注 ROI **−1.41%**；
> 4. +240%量级在统计上不可信（顶级职业投注者长期约+3%~+6%），大概率是回测泄漏
>    （赛后信息/最优价成交/注额口径错误），原回测代码已不可考。
> 若未来重做该回测，必须：逐行审计泄漏点 → 前向(walk-forward)验证 → 复现脚本入库 → 回归断言，缺一不可。

## xG Feature Experiment (2026-07-16)
Integrated xG data from `eatpizzanot/soccer-dataset` (HuggingFace, 673K+ matches, free)
- xG coverage for our 5 leagues: 93-99%
- 16 new xG features (rolling xG/xGA for windows 3/5/10 + time-decay)
- Total xG feature importance: 12.1% in model
- **Accuracy: +0.3pp** (53.36% → 53.66%)
- **Walk-forward ROI: 1.20%** (vs baseline 2.52% without xG)
- Conclusion: xG info already captured by existing shot/odds features. Not worth adding.
- Code kept in `fd_builder.py` for future use if better xG data becomes available.

## Strategy
1. Train XGBoost+Platt on all historical data (NO odds features)
2. Get Pinnacle opening odds (or use InferSports sharp odds for live matches)
3. De-vig Pinnacle odds to get fair probabilities
4. Bet when model probability > Pinnacle fair prob + 3% edge
5. Use Kelly (f=0.25) for stake sizing

## Files Created
- `src/models/poisson.py` — Poisson regression (attack/defense strength model)
- `src/models/lstm_model.py` — LSTM sequential match predictor  
- `src/models/ensemble.py` — Ensemble (weighted stacking)
- `data/backtests/model_comparison.csv` — Full comparison results (2026-08-26审计: 实际路径)
- `src/infersports.py` — InferSports API integration (fair odds, compare_prob, scan)

## Data Sources
- `data/xg/` — HuggingFace soccer-dataset (fixtures.parquet, match_stats.parquet with home_xg/away_xg, etc.)
- `data/raw/football_data/matches_with_xg.csv` — Our data enriched with matched xG (19088 matched)

## Updated
- `src/models/trainer.py` — Default XGBoost params updated to tuned config (n_estimators=200)
- `src/features/fd_builder.py` — xG feature code added + supports xG-enriched CSV (auto-detects xG columns)
- `pipeline.py` — Removed odds from training features (no data leakage)
- `src/models/poisson.py` — Replaced PyTorch Dixon-Coles with penaltyblog Cython implementation
- `src/strategies/wisdom_scanner.py` — Wisdom of Crowd strategy scanner (EV thresholds, league baselines, InferSports live integration)

## Library: penaltyblog v1.11.0 (`pip install penaltyblog`)
Production-ready football analytics library used for:
- Dixon-Coles goal model (Cython-optimized MLE, time-decay weights)
- Understat xG scraper (380 fixtures/season with xG data — bypasses anti-bot)
- Implied odds de-vig (7 methods, including Buchdahl's differential margin weighting)
- Bayesian goal models (custom MCMC sampler, hierarchical shrinkage)
- Backtesting module (strategy validation against historical data)

## 会话结束指令
> **每次会话结束前必须执行：**
> 1. 更新 `SESSION_STATE.md` — 写入当前进度、待办事项、关键发现
> 2. 确保 `strategy_data/` 下的数据文件已保存
> 3. 记录最后在做什么，方便下次会话继续

