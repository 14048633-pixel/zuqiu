# 48h 23场 form 数据补齐（BSD 覆盖）

日期: 2026-08-18 | 数据源: BSD /api/v2/events/{id}/stats/ (射门/射正/xG)
覆盖范围: 23场涉及44队 + 墨超Necaxa/León，每队最近10场正式比赛
覆盖统计: 425场去重；更新730行、新建371行、清重复3243行

| # | 联赛 | 比赛 | 旧主/客form | 新主/客form | 旧差 | 新差 | 变化 |
|---|---|---|---|---|---|---|---|
| 1 | 意杯 | Pisa vs Empoli | 0.274/0.369 | 0.346/0.449 | -0.095 | -0.103 | ~-0.01 |
| 2 | 意杯 | Sassuolo vs Cesena | 0.411/0.36 | 0.511/0.444 | 0.051 | 0.067 | ~0.02 |
| 3 | 丹超 | Brøndby IF vs Sønderjyske Fodbold | 0.413/0.341 | 0.559/0.514 | 0.072 | 0.045 | ~-0.03 |
| 4 | 瑞超 | BK Häcken vs Halmstads BK | 0.352/0.268 | 0.455/0.382 | 0.084 | 0.073 | ~-0.01 |
| 5 | 西乙 | Sporting Gijón vs CE Sabadell | 0.463/0.446 | 0.582/0.324 | 0.017 | 0.258 | ▲0.24 |
| 6 | 阿甲 | Estudiantes de Río Cuarto vs Atlético Tucumán | 0.281/0.3 | 0.422/0.534 | -0.019 | -0.112 | ▲-0.09 |
| 7 | 土超 | Samsunspor vs Göztepe | 0.625/0.532 | 0.708/0.562 | 0.093 | 0.146 | ▲0.05 |
| 8 | 意杯 | Cremonese vs Sampdoria | 0.316/0.346 | 0.442/0.495 | -0.03 | -0.053 | ~-0.02 |
| 9 | 英冠 | Cardiff City vs Wrexham | 0.576/0.38 | 0.773/0.512 | 0.196 | 0.261 | ▲0.07 |
| 10 | 西甲 | Deportivo de A Coruña vs Elche | 0.563/0.348 | 0.563/0.541 | 0.215 | 0.022 | ▲-0.19 |
| 11 | 意杯 | Palermo vs Lecce | 0.388/0.395 | 0.492/0.549 | -0.007 | -0.057 | ▲-0.05 |
| 12 | 葡超 | Casa Pia vs Benfica | 0.328/0.427 | 0.481/0.456 | -0.099 | 0.025 | ▲0.12 |
| 13 | 西乙 | Almería vs CD Eldense | 0.356/0.447 | 0.606/0.483 | -0.091 | 0.123 | ▲0.21 |
| 14 | 阿甲 | CA Lanús vs CA Independiente | 0.306/0.315 | 0.553/0.616 | -0.009 | -0.063 | ▲-0.05 |
| 15 | 阿甲 | Vélez Sarsfield vs Defensa y Justicia | 0.347/0.311 | 0.613/0.455 | 0.036 | 0.158 | ▲0.12 |
| 16 | 巴甲 | Internacional vs Remo | 0.28/0.351 | 0.548/0.559 | -0.071 | -0.011 | ▲0.06 |
| 17 | 智利甲 | Palestino vs Huachipato | 0.327/0.301 | 0.37/0.318 | 0.026 | 0.052 | ~0.03 |
| 18 | 阿甲 | Gimnasia y Esgrima Mendoza vs CA Talleres | 0.398/0.389 | 0.565/0.553 | 0.009 | 0.012 | ~0.0 |
| 19 | 墨超 | Club Necaxa vs Club León | 0.333/0.608 | 0.355/0.71 | -0.275 | -0.355 | ▲-0.08 |
| 20 | 墨超 | CF Pachuca vs Club Puebla | 0.356/0.348 | 0.551/0.469 | 0.008 | 0.082 | ▲0.07 |
| 21 | 欧冠资格 | GNK Dinamo Zagreb vs Viking FK | None/0.394 | 0.595/0.567 | None | 0.028 | 首次出分 |
| 22 | 欧冠资格 | Fenerbahçe vs Olympique Lyonnais | 0.443/0.545 | 0.614/0.546 | -0.102 | 0.068 | ▲0.17 |
| 23 | 欧冠资格 | Levski Sofia vs AEK Athens | None/None | 0.487/0.674 | None | -0.187 | 首次出分 |

## 关键变化
- 欧冠3场（Dinamo/Levski/AEK）此前本地池无历史 → 首次出分
- 方向翻转: 葡超 Casa Pia、西乙 Almería、欧冠 Fenerbahçe
- 差距拉大: 西乙 Sporting Gijón(+0.017→+0.258)、英冠 Cardiff(+0.196→+0.261)
- 差距收窄: 西甲 Deportivo(+0.215→+0.022)

## 注意
- 智利甲 BSD 无正式联赛覆盖，Palestino/Huachipato 用洲际杯赛数据
- 意杯/西乙/土超等 8月未开赛队伍，最近正式比赛为上赛季+季前友谊赛混合
- 去重3243行来自历史池双源重复（train_pool+espn），属数据修正
- 文件: form_phase0/bsd_48h_teams.json / bsd_48h_events.json / bsd_48h_stats.json / bsd_48h_overrides.json / _recompute_48h_form.py / analyze_48h_v2_bsd.json