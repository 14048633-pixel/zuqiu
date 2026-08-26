# 已结算实盘：模型大小球 vs 市场方向 分组命中率/ROI（74场）

> 数据：08-14~08-19 已完赛，scan 模型OU概率+市场赔率，BSD 赛果核对 | 平注模型方向@市场赔率
> 统计口径：同向=模型方向与市场一致；反向=模型逆市场；命中=方向对；ROI=平注

## 一、核心结论

| 分组 | 场次 | 命中 | 命中率 | 平注ROI |
|------|------|------|--------|---------|
| **全量** | 74 | 41 | 55.4% | +2.9% |
| 模型=市场 同向 | 46 | 26 | 56.5% | -7.4% |
| 模型逆市场 反向 | 28 | 15 | 53.6% | +19.8% |
| 模型大球 | 39 | 25 | 64.1% | +19.0% |
| 模型小球 | 35 | 16 | 45.7% | -15.1% |
| 同向大 | 23 | 15 | 65.2% | +5.8% |
| 同向小 | 23 | 11 | 47.8% | -20.7% |
| 反向大 | 16 | 10 | 62.5% | +37.9% |
| 反向小 | 12 | 5 | 41.7% | -4.5% |

**要点**：
- 跟市场同向：命中 56.5% 但 ROI **-7.4%**（赔率低，命中不够覆盖水钱）——"市场胜率高"≠赚钱
- 模型逆市场反向：命中 53.6% 但 ROI **+19.8%**（反向时拿的是高赔）
- 模型**大球**是价值方向：命中 64.1%、ROI +19.0%；模型**小球**是亏损方向：命中 45.7%、ROI -15.1%
- 之前 08-18 那批 16/20=80% 是 20 场小样本运气，且全部同向；拉长到 74 场同向只有 56.5%

## 二、按联赛

| 联赛 | 场次 | 命中 | 命中率 | ROI |
|------|------|------|--------|-----|
| 英乙 | 11 | 8 | 72.7% | +42.8% |
| 英冠 | 10 | 5 | 50.0% | -4.9% |
| 美职 | 10 | 6 | 60.0% | +8.8% |
| 巴甲 | 9 | 5 | 55.6% | +15.1% |
| J1 | 6 | 3 | 50.0% | +4.5% |
| 瑞超 | 6 | 4 | 66.7% | +20.8% |
| 荷甲 | 5 | 2 | 40.0% | -46.0% |
| 阿甲 | 5 | 3 | 60.0% | -17.0% |
| 西乙 | 3 | 2 | 66.7% | +10.7% |
| 挪超 | 2 | 2 | 100.0% | +74.0% |
| 土超 | 2 | 0 | 0.0% | -100.0% |
| 葡超 | 2 | 0 | 0.0% | -100.0% |
| 西甲 | 1 | 0 | 0.0% | -100.0% |
| 丹超 | 1 | 1 | 100.0% | +148.0% |
| 比甲 | 1 | 0 | 0.0% | -100.0% |

## 三、74 场明细（按时间）

| 时间 | 联赛 | 对阵 | 比分 | 总球 | 模型 | 市场 | 赔率 | 命中 | 分组 |
|------|------|------|------|------|------|------|------|------|------|
| 2026-08-14T18:00 | 荷甲 | SC Telstar vs Sparta Rotterdam | 1-3 | 4 | 小 | 大 | 2.35 | ✘ | 反向 |
| 2026-08-14T18:30 | 西乙 | Real Sociedad B vs CD Castellón | 0-1 | 1 | 大 | 大 | 1.64 | ✘ | 同向 |
| 2026-08-15T09:00 | J1 | Mito HollyHock vs Gamba Osaka | 1-1 | 2 | 大 | 小 | 2.26 | ✘ | 反向 |
| 2026-08-15T09:00 | J1 | Kashima Antlers vs Nagoya Grampus | 2-1 | 3 | 大 | 大 | 1.93 | ✔ | 同向 |
| 2026-08-15T09:30 | J1 | Shimizu S Pulse vs Yokohama F Marinos | 0-1 | 1 | 大 | 小 | 2.12 | ✘ | 反向 |
| 2026-08-15T09:55 | J1 | Fagiano Okayama vs V-Varen Nagasaki | 1-0 | 1 | 大 | 小 | 2.12 | ✘ | 反向 |
| 2026-08-15T10:00 | J1 | Avispa Fukuoka vs Cerezo Osaka | 3-0 | 3 | 大 | 小 | 2.10 | ✔ | 反向 |
| 2026-08-15T10:00 | J1 | Vissel Kobe vs FC Tokyo | 2-2 | 4 | 大 | 小 | 2.24 | ✔ | 反向 |
| 2026-08-15T11:30 | 英冠 | Bolton Wanderers vs Preston North End | 2-1 | 3 | 小 | 小 | 1.88 | ✘ | 同向 |
| 2026-08-15T11:30 | 英乙 | Newport County vs Rochdale | 3-0 | 3 | 大 | 小 | 2.66 | ✔ | 反向 |
| 2026-08-15T11:30 | 英乙 | Oldham Athletic vs Port Vale | 2-0 | 2 | 小 | 小 | 1.01 | ✔ | 同向 |
| 2026-08-15T14:00 | 英冠 | Bristol City vs Millwall | 0-2 | 2 | 小 | 小 | 1.94 | ✔ | 同向 |
| 2026-08-15T14:00 | 英冠 | Charlton Athletic vs Derby County | 2-1 | 3 | 小 | 小 | 1.76 | ✘ | 同向 |
| 2026-08-15T14:00 | 英冠 | Middlesbrough vs Lincoln City | 2-1 | 3 | 小 | 大 | 2.12 | ✘ | 反向 |
| 2026-08-15T14:00 | 英冠 | Norwich City vs West Bromwich Albion | 1-2 | 3 | 小 | 小 | 1.89 | ✘ | 同向 |
| 2026-08-15T14:00 | 英冠 | Portsmouth vs Queens Park Rangers | 1-3 | 4 | 小 | 小 | 1.78 | ✘ | 同向 |
| 2026-08-15T14:00 | 英冠 | Stoke City vs Swansea City | 1-2 | 3 | 大 | 小 | 2.14 | ✔ | 反向 |
| 2026-08-15T14:00 | 英乙 | Accrington Stanley vs Colchester United | 2-2 | 4 | 小 | 小 | 1.79 | ✘ | 同向 |
| 2026-08-15T14:00 | 英乙 | Barnet vs Salford City | 3-1 | 4 | 大 | 大 | 1.95 | ✔ | 同向 |
| 2026-08-15T14:00 | 英乙 | York City vs Bristol Rovers | 3-2 | 5 | 小 | 小 | 1.86 | ✘ | 同向 |
| 2026-08-15T14:00 | 英乙 | Cheltenham Town vs Rotherham United | 2-1 | 3 | 大 | 小 | 2.16 | ✔ | 反向 |
| 2026-08-15T14:00 | 英乙 | Crawley Town vs Crewe Alexandra | 0-1 | 1 | 小 | 小 | 1.97 | ✔ | 同向 |
| 2026-08-15T14:00 | 英乙 | Grimsby Town vs Exeter City | 1-0 | 1 | 大 | 大 | 1.94 | ✘ | 同向 |
| 2026-08-15T14:00 | 英乙 | Gillingham vs Walsall | 0-3 | 3 | 大 | 小 | 2.22 | ✔ | 反向 |
| 2026-08-15T14:00 | 英乙 | Northampton Town vs Swindon Town | 0-0 | 0 | 小 | 小 | 1.97 | ✔ | 同向 |
| 2026-08-15T14:00 | 英乙 | Tranmere Rovers vs Shrewsbury Town | 2-0 | 2 | 小 | 小 | 1.77 | ✔ | 同向 |
| 2026-08-15T16:30 | 英冠 | Sheffield United vs Birmingham City | 0-0 | 0 | 小 | 小 | 1.92 | ✔ | 同向 |
| 2026-08-15T16:45 | 荷甲 | FC Utrecht vs AZ Alkmaar | 1-4 | 5 | 小 | 大 | 2.44 | ✘ | 反向 |
| 2026-08-15T18:00 | 荷甲 | Excelsior vs PSV Eindhoven | 1-2 | 3 | 大 | 大 | 1.36 | ✔ | 同向 |
| 2026-08-15T19:00 | 荷甲 | Fortuna Sittard vs SC Cambuur | 3-1 | 4 | 小 | 大 | 2.54 | ✘ | 反向 |
| 2026-08-15T19:30 | 西甲 | Sevilla vs Rayo Vallecano | 2-1 | 3 | 小 | 小 | 1.64 | ✘ | 同向 |
| 2026-08-15T19:30 | 巴甲 | Fluminense vs Palmeiras | 3-2 | 5 | 大 | 小 | 2.50 | ✔ | 反向 |
| 2026-08-15T22:00 | 阿甲 | Newells Old Boys vs Deportivo Riestra | 2-0 | 2 | 小 | 小 | 1.35 | ✔ | 同向 |
| 2026-08-15T23:30 | 美职 | CF Montreal vs D.C. United | 1-1 | 2 | 小 | 大 | 2.28 | ✔ | 反向 |
| 2026-08-15T23:30 | 美职 | Orlando City SC vs FC Cincinnati | 1-1 | 2 | 大 | 大 | 1.27 | ✘ | 同向 |
| 2026-08-15T23:30 | 美职 | Toronto FC vs New England Revolution | 2-1 | 3 | 大 | 大 | 1.72 | ✔ | 同向 |
| 2026-08-16T00:00 | 巴甲 | Sao Paulo vs Coritiba | 1-1 | 2 | 大 | 小 | 2.12 | ✘ | 反向 |
| 2026-08-16T00:30 | 美职 | Houston Dynamo vs LA Galaxy | 1-0 | 1 | 小 | 大 | 2.42 | ✔ | 反向 |
| 2026-08-16T00:30 | 美职 | Nashville SC vs Inter Miami CF | 4-1 | 5 | 大 | 大 | 1.46 | ✔ | 同向 |
| 2026-08-16T01:30 | 美职 | Colorado Rapids vs Sporting Kansas City | 2-0 | 2 | 大 | 大 | 1.44 | ✘ | 同向 |
| 2026-08-16T02:30 | 美职 | Los Angeles FC vs San Diego FC | 0-1 | 1 | 大 | 大 | 1.43 | ✘ | 同向 |
| 2026-08-16T12:00 | 瑞超 | Djurgardens IF vs AIK | 1-3 | 4 | 大 | 大 | 1.52 | ✔ | 同向 |
| 2026-08-16T12:00 | 瑞超 | Degerfors IF vs IFK Goteborg | 3-0 | 3 | 大 | 大 | 1.90 | ✔ | 同向 |
| 2026-08-16T12:00 | 瑞超 | IF Brommapojkarna vs Örgryte IS | 3-1 | 4 | 大 | 大 | 1.59 | ✔ | 同向 |
| 2026-08-16T12:30 | 荷甲 | Feyenoord vs Go Ahead Eagles | 2-2 | 4 | 大 | 大 | 1.34 | ✔ | 同向 |
| 2026-08-16T12:30 | 英冠 | Watford vs Southampton | 2-1 | 3 | 大 | 大 | 1.76 | ✔ | 同向 |
| 2026-08-16T14:00 | 巴甲 | Chapecoense vs Bahia | 3-3 | 6 | 大 | 小 | 1.95 | ✔ | 反向 |
| 2026-08-16T14:00 | 丹超 | Lyngby vs FC Midtjylland | 1-1 | 2 | 小 | 大 | 2.48 | ✔ | 反向 |
| 2026-08-16T14:30 | 瑞超 | GAIS vs Malmo FF | 0-1 | 1 | 小 | 大 | 2.24 | ✔ | 反向 |
| 2026-08-16T14:30 | 瑞超 | Kalmar FF vs Hammarby IF | 0-4 | 4 | 小 | 大 | 2.22 | ✘ | 反向 |
| 2026-08-16T15:00 | 英冠 | Burnley vs West Ham United | 2-2 | 4 | 大 | 大 | 1.75 | ✔ | 同向 |
| 2026-08-16T15:00 | 挪超 | SK Brann vs HamKam | 3-0 | 3 | 大 | 大 | 1.44 | ✔ | 同向 |
| 2026-08-16T16:30 | 比甲 | KV Mechelen vs Standard Liege | 3-3 | 6 | 小 | 小 | 1.88 | ✘ | 同向 |
| 2026-08-16T17:00 | 西乙 | Girona FC vs Leganés | 1-1 | 2 | 小 | 小 | 1.71 | ✔ | 同向 |
| 2026-08-16T17:15 | 挪超 | Fredrikstad FK vs Kristiansund BK | 1-0 | 1 | 小 | 大 | 2.04 | ✔ | 反向 |
| 2026-08-16T18:30 | 土超 | Besiktas JK vs Eyüpspor | 1-0 | 1 | 大 | 大 | 1.49 | ✘ | 同向 |
| 2026-08-16T19:00 | 巴甲 | Atletico Mineiro vs Grêmio | 3-0 | 3 | 小 | 小 | 1.85 | ✘ | 同向 |
| 2026-08-16T19:00 | 巴甲 | Vasco da Gama vs Santos | 0-3 | 3 | 大 | 小 | 2.06 | ✔ | 反向 |
| 2026-08-16T19:30 | 葡超 | Famalicão vs CS Maritimo | 1-2 | 3 | 小 | 小 | 1.78 | ✘ | 同向 |
| 2026-08-16T21:00 | 阿甲 | River Plate vs Argentinos Juniors | 2-0 | 2 | 大 | 小 | 2.62 | ✘ | 反向 |
| 2026-08-16T21:30 | 巴甲 | Vitoria vs Botafogo | 1-0 | 1 | 小 | 小 | 1.81 | ✔ | 同向 |
| 2026-08-16T21:30 | 巴甲 | Mirassol vs Flamengo | 1-5 | 6 | 大 | 小 | 2.04 | ✔ | 反向 |
| 2026-08-16T22:00 | 美职 | Chicago Fire vs Portland Timbers | 2-1 | 3 | 大 | 大 | 1.32 | ✔ | 同向 |
| 2026-08-16T22:00 | 美职 | New York City FC vs Philadelphia Union | 2-3 | 5 | 大 | 大 | 1.68 | ✔ | 同向 |
| 2026-08-16T22:30 | 巴甲 | Corinthians vs Cruzeiro | 1-2 | 3 | 小 | 小 | 1.63 | ✘ | 同向 |
| 2026-08-16T23:15 | 阿甲 | Barracas Central vs Rosario Central | 0-1 | 1 | 小 | 小 | 1.41 | ✔ | 同向 |
| 2026-08-16T23:15 | 阿甲 | Central Córdoba vs Instituto de Córdoba | 0-1 | 1 | 大 | 小 | 2.68 | ✘ | 反向 |
| 2026-08-17T00:30 | 美职 | Austin FC vs FC Dallas | 1-2 | 3 | 小 | 大 | 2.34 | ✘ | 反向 |
| 2026-08-17T17:00 | 瑞超 | BK Hacken vs Halmstads BK | 1-0 | 1 | 大 | 大 | 1.44 | ✘ | 同向 |
| 2026-08-17T17:45 | 阿甲 | Estudiantes de Río Cuarto vs Atlético Tucuman | 0-1 | 1 | 小 | 小 | 1.39 | ✔ | 同向 |
| 2026-08-17T18:30 | 土超 | Samsunspor vs Goztepe | 3-3 | 6 | 小 | 小 | 1.81 | ✘ | 同向 |
| 2026-08-17T19:15 | 葡超 | Casa Pia vs Benfica | 0-7 | 7 | 小 | 大 | 2.30 | ✘ | 反向 |
| 2026-08-17T19:30 | 西乙 | Almería vs CD Eldense | 3-0 | 3 | 大 | 大 | 1.61 | ✔ | 同向 |
| 2026-08-17T23:00 | 巴甲 | Internacional vs Remo | 1-1 | 2 | 大 | 大 | 1.83 | ✘ | 同向 |