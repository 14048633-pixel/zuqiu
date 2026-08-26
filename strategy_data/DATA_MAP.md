# 数据地图 DATA_MAP（找什么去哪里）
> 2026-08-19 建立。原则：**文件=采集层，SQLite=查询层**。前端/复盘优先查 db/football.db。

## 一、快速定位表
| 想找什么 | 去哪找 |
|---|---|
| 某场预测+结果 | db/football.db → matches+predictions+settlements，或 analysis_records/pred_library/by_league/ |
| 方向命中率（联赛×方向） | `python db/query.py dirs` 或 strategy_data/direction_stats.csv |
| 平局预警分组命中率 | `python db/query.py dwarn` |
| 联赛参数/状态 | strategy_data/league_calib.json + db 的 leagues 表 |
| 各方向修复进度 | strategy_data/fix_tracker.json |
| 近期扫描报告 | analysis_records/scans/ |
| 结算报告 | analysis_records/settles/ |
| 赛前30分钟快照 | analysis_records/prematch/ |
| 历史盘口快照 | prediction_v2/output/odds_snapshots/snapshots.csv |
| 历史赛果/特征 | data/processed/*.csv, data/xg/*.parquet |
| 失误与经验 | strategy_data/mistake_log.json |
| 盘口区间真值 | strategy_data/*_odds_zones.json |
| 所有旧分析文件索引 | analysis_records/index_files.json |

## 二、目录职责
- `db/` — SQLite 库 + schema.sql + sync.py(同步) + query.py(查询)
- `analysis_records/` — 分析产物（新文件按子目录落：scans/settles/prematch/research）
- `analysis_records/pred_library/` — 预测库唯一真相源（by_league/*.json + index.json）
- `strategy_data/` — 策略参数与经验（league_calib/mistake_log/odds_zones/alias/catalog/fix_tracker）
- `prediction_v2/output/` — 快照历史 + 回测输出（大文件）
- `data/` — 原始与加工数据

## 三、常用命令
```
python db/sync.py --rebuild   # 重建数据库(文件->SQLite)
python db/query.py overview   # 总览+各方向命中率
python db/query.py dirs       # 联赛x方向透视
python db/query.py dwarn      # 平局预警分组
python db/query.py league 美职
python db/query.py search 海港
python db/query.py csv        # 导出 direction_stats.csv
python db/fix_tracker.py     # 更新方向修复验证组状态表
```

## 四、方向分类口径
direction ∈ {大球, 小球, 1X2主, 1X2客, 1X2平, 让球主, 让球客}
- draw_warn=1 → 市场去水平局概率≥26%（平局预警）
- phase ∈ {test, phaseB, phaseC}
