# 48h 观察比赛 · 最终方向（临场盘 + LSTM v2 状态风控）

> 生成 2026-08-17 21:xx | 临场盘=the-odds-api 去水概率（主key, 剩余配额约34）| form=LSTM v2 赛前历史状态分(0~1) | 规则：form 仅作后置风控调星级，不推翻方向

| 开赛 | 联赛 | 比赛 | 临场方向(1X2) | 大/小2.5 | 主form | 客form | 差 | form支持 | 观察置信 |
|---|---|---|---|---|---|---|---|---|---|
| 08-17 23:00 | 芬超 | IF Gnistan vs Ilves | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-17 23:30 | 罗甲 | FC Universitatea Cluj vs UTA Arad | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-18 00:00 | 保甲 | FK Spartak Varna vs FK Septemvri Sofia | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-18 00:00 | 友谊赛 | Juventus vs Juventus Next Gen U23 | 无临场盘(旧参考:无(缺盘口)) | — | 0.694 |  |  | — | 低 |
| 08-18 00:00 | 意杯 | Pisa vs Empoli | 无临场盘(旧参考:主胜Pisa(共识)) | — | 0.274 | 0.369 | -0.09 | — | 低 |
| 08-18 00:30 | 意杯 | Sassuolo vs Cesena | 无临场盘(旧参考:主胜Sassuolo(共识)) | — | 0.411 | 0.36 | 0.05 | — | 低 |
| 08-18 01:00 | 丹超 | Brøndby IF vs Sønderjyske Fodbold | 主胜(66%) | 大2.5 60.5% | 0.413 | 0.341 | 0.07 | 支持 | 中 |
| 08-18 01:00 | 瑞超 | BK Häcken vs Halmstads BK | 主胜(68%) | 大2.5 66.7% | 0.352 | 0.268 | 0.08 | 支持 | 中 |
| 08-18 01:00 | 葡乙 | Felgueiras vs AVS - Futebol SAD | 无临场盘(旧参考:无(缺盘口)) | — |  | 0.48 |  | — | 低 |
| 08-18 01:00 | 西乙 | Sporting Gijón vs CE Sabadell | 主胜(51%) | 小2.5 57.2% | 0.463 | 0.446 | 0.02 | 中性 | 中 |
| 08-18 01:45 | 阿甲 | Estudiantes de Río Cuarto vs Atlético Tucumán | 客胜(36%) | 小2.5 68.0% | 0.281 | 0.3 | -0.02 | 中性 | 低 |
| 08-18 02:15 | 保甲 | Arda Kardzhali vs Lokomotiv Sofia | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-18 02:30 | 土超 | Samsunspor vs Göztepe | 主胜(42%) | 小2.5 53.3% | 0.625 | 0.532 | 0.09 | 支持 | 中 |
| 08-18 02:30 | 罗甲 | FCSB vs FC Botoșani | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-18 02:45 | 意杯 | Cremonese vs Sampdoria | 无临场盘(旧参考:主胜Cremonese(共识)) | — | 0.316 | 0.346 | -0.03 | — | 低 |
| 08-18 03:00 | 英冠 | Cardiff City vs Wrexham | 主胜(38%) | 大2.5 54.5% | 0.576 | 0.38 | 0.20 | 强支持 | 高 |
| 08-18 03:00 | 西甲 | Deportivo de A Coruña vs Elche | 主胜(43%) | 小2.5 58.3% | 0.563 | 0.348 | 0.21 | 强支持 | 高 |
| 08-18 03:15 | 意杯 | Palermo vs Lecce | 无临场盘(旧参考:主胜Palermo(弱)) | — | 0.388 | 0.395 | -0.01 | — | 低 |
| 08-18 03:15 | 葡超 | Casa Pia vs Benfica | 客胜(76%) | 大2.5 59.1% | 0.328 | 0.427 | -0.10 | 支持 | 中 |
| 08-18 03:30 | 西乙 | Almería vs CD Eldense | 主胜(69%) | 大2.5 56.2% | 0.356 | 0.447 | -0.09 | 弱冲突 | 低 |
| 08-18 04:00 | 阿甲 | CA Lanús vs CA Independiente | 主胜(40%) | 小2.5 65.6% | 0.306 | 0.315 | -0.01 | 中性 | 低 |
| 08-18 06:15 | 阿甲 | Vélez Sarsfield vs Defensa y Justicia | 主胜(52%) | 小2.5 59.1% | 0.347 | 0.311 | 0.04 | 中性 | 中 |
| 08-18 07:00 | 巴甲 | Internacional vs Remo | 主胜(60%) | 大2.5 51.6% | 0.28 | 0.351 | -0.07 | 弱冲突 | 低 |
| 08-18 08:30 | 智利甲 | Palestino vs Huachipato | 主胜(53%) | 大2.5 55.5% | 0.327 | 0.301 | 0.03 | 中性 | 中 |
| 08-18 08:30 | 阿甲 | Gimnasia y Esgrima Mendoza vs CA Talleres | 客胜(36%) | 小2.5 66.4% | 0.398 | 0.389 | 0.01 | 中性 | 低 |
| 08-18 09:00 | 墨超 | Club Necaxa vs Club León | 主胜(40%) | 大2.5 55.6% | 0.333 | 0.608 | -0.28 | 冲突 | 低 |
| 08-18 11:00 | 墨超 | CF Pachuca vs Club Puebla | 主胜(61%) | 大2.5 56.3% | 0.356 | 0.348 | 0.01 | 中性 | 高 |
| 08-19 00:00 | 友谊赛 | 1. FC Heidenheim vs FC Bayern München | 无临场盘(旧参考:无(缺盘口)) | — | 0.479 | 0.879 | -0.40 | — | 低 |
| 08-19 01:00 | 友谊赛 | SC Spelle-Venhaus vs VfL Osnabrück | 无临场盘(旧参考:无(缺盘口)) | — |  | 0.385 |  | — | 低 |
| 08-19 02:00 | 友谊赛 | CD Marchamalo vs Guadalajara | 无临场盘(旧参考:无(缺盘口)) | — |  | 0.331 |  | — | 低 |
| 08-19 03:00 | 欧冠资格 | GNK Dinamo Zagreb vs Viking FK | 无临场盘(旧参考:BSD主胜 vs 市场客胜=反向) | — |  |  |  | — | 低 |
| 08-19 03:00 | 欧冠资格 | Fenerbahçe vs Olympique Lyonnais | 无临场盘(旧参考:BSD主胜 vs 市场客胜=反向) | — |  |  |  | — | 低 |
| 08-19 03:00 | 欧冠资格 | Levski Sofia vs AEK Athens | 无临场盘(旧参考:BSD主胜 vs 市场客胜=反向) | — |  |  |  | — | 低 |
| 08-19 06:00 | 南美杯 | Recoleta FC vs Boca Juniors | 无临场盘(旧参考:无(缺盘口)) | — |  | 0.349 |  | — | 低 |
| 08-19 06:00 | 解放者杯 | Independiente Rivadavia vs Fluminense | 无临场盘(旧参考:无(缺盘口)) | — | 0.31 | 0.352 | -0.04 | — | 低 |
| 08-19 06:30 | 巴乙 | Londrina vs Atlético Goianiense | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-19 08:00 | 哥伦比亚杯 | Llaneros FC vs Deportes Quindío | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-19 08:30 | 南美杯 | São Paulo vs Bolívar | 无临场盘(旧参考:无(缺盘口)) | — | 0.31 |  |  | — | 低 |
| 08-19 08:30 | 巴乙 | Náutico vs Ceará | 无临场盘(旧参考:无(缺盘口)) | — |  | 0.395 |  | — | 低 |
| 08-19 08:30 | 解放者杯 | Universidad Católica vs Estudiantes de La Plata | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-19 08:30 | 解放者杯 | Independiente del Valle vs Deportes Tolima | 无临场盘(旧参考:无(缺盘口)) | — |  |  |  | — | 低 |
| 08-19 08:35 | 巴乙 | Goiás vs Juventude | 无临场盘(旧参考:无(缺盘口)) | — |  | 0.584 |  | — | 低 |

## 汇总
- 42 场中 16 场有临场盘（其余盘口缺或联赛无覆盖，仅保留旧参考，置信一律低）。
- 临场方向置信分布：高 3 场、中 7 场、低 6 场。
- form 支持强(方向+状态同向)场次优先观察；form 冲突场次仅记录不追方向。