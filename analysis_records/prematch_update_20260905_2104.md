# 赛前伤停首发更新 · 2026-09-05 21:04 轮

- 轮询时间: 2026-09-05 21:04:21 Saturday (UTC+8)
- 数据源降级链: BSD(429额度耗尽) → **the-odds-api 赔率 ✅ + apifootball 伤停 ✅ + batch_predict 本地预测 ✅**
- 窗口(未来0-30分钟): **命中 1 场**

## 本轮窗口场次（临场更新）

| 开赛 | 联赛 | 主队 | 客队 | 主胜 | 平 | 客胜 | 大2.5 | 伤停(主/客) | 预测 |
|---|---|---|---|---|---|---|---|---|---|---|
| 21:30 | Bundesliga | Bayer Leverkusen | Union Berlin | - | 4.8 | - | 1.37 | 0/0人 | 无本地数据(未跑) |

## batch_predict 结果（有本地数据的场次）

- 09-05 20:45 | Ekstraklasa | Widzew Łódź vs Radomiak Radom | 模型[45.0, 27.6, 27.4] 市场[56.7, 25.1, 18.2] | BEST: 客胜 p27.4% @4.6887 EV+28.3% ★1
- 09-05 21:00 | Serie A | Fiorentina vs Torino | 模型[53.0, 25.9, 21.1] 市场[46.6, 28.6, 24.8] | BEST: 无正EV

## 数据源状态
- ⚠️ BSD: 429 taster_exhausted（免费档日额度耗尽，北京08:00重置）→ lineups/首发XI 本轮缺失，伤停以 apifootball 当日记录替代
- ✅ the-odds-api: 赔率正常（h2h+totals，composite 源）
- ✅ apifootball: 伤停正常（Free 100次/日）

## 防重记录
- updated_events.json 已登记本轮窗口场次（BSD恢复后如需补拉lineups可强制重跑）