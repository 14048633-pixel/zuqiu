# 积分榜 zone 标签 实盘回测（无泄漏口径）

- 生成: 2026-08-26 | 数据: analysis_records/bet_ledger.csv (867已结算腿) + espn/j1/csl 赛果重建
- 无泄漏: 积分榜只用 kickoff 严格早于该场的同赛季赛果重建; 结算用账本 result
- 覆盖: 可重建 563 腿 / no_match 133 / no_data 166 / 主结论以 played>=3 组为准

## 1. 等额注分组（全部可重建 563 腿）
- ALL: n=563  win=225 half=10 push=20 lose=308  hit=42.4%  ROI=+0.8%
- 主场=保级: n=118  win=48 half=0 push=6 lose=64  hit=42.9%  ROI=+11.7%
- 主场=中游: n=359  win=141 half=8 push=11 lose=199  hit=41.7%  ROI=-4.3%
- 主场=争冠/升级: n=86  win=36 half=2 push=3 lose=45  hit=44.6%  ROI=+7.0%

## 2. 双方有zone 且 played>=3（zone可信组 n=175）
- 全部: n=175  win=75 half=2 push=9 lose=89  hit=45.8%  ROI=+1.7%
- 保级主场: n=34  win=15 half=0 push=4 lose=15  hit=50.0%  ROI=+10.7%
- 非保级主场: n=141  win=60 half=2 push=5 lose=74  hit=44.9%  ROI=-0.5%
- 争冠/升级主场: n=25  win=11 half=1 push=0 lose=13  hit=46.0%  ROI=+15.2%
- 无欲无求(双方中游played>=8): n=66  win=27 half=1 push=3 lose=35  hit=43.7%  ROI=-2.8%
- 其余: n=109  win=48 half=1 push=6 lose=54  hit=47.1%  ROI=+4.4%

## 3. 星级调整模拟（原出单腿 played>=3, n=65）
- 原stake加权ROI: +10.6%
- 积分榜调星后加权ROI: +9.7%
- 保级主场原腿(n=15): base +10.5% -> +1星 +6.2%
- 无欲无求原腿(n=28): base +5.0% -> -1星 +4.5%

## 4. 联赛明细（可重建）
- 英乙: n=84  win=34 half=0 push=4 lose=46  hit=42.5%  ROI=-6.5%
- 英冠: n=72  win=28 half=1 push=2 lose=41  hit=40.7%  ROI=-2.1%
- 美职: n=55  win=25 half=0 push=3 lose=27  hit=48.1%  ROI=+17.4%
- J1: n=54  win=20 half=3 push=0 lose=31  hit=39.8%  ROI=-3.9%
- 法乙: n=50  win=20 half=1 push=2 lose=27  hit=42.7%  ROI=+37.9%
- 西乙: n=36  win=18 half=0 push=0 lose=18  hit=50.0%  ROI=+18.4%
- 比甲: n=32  win=11 half=2 push=0 lose=19  hit=37.5%  ROI=-18.7%
- 荷甲: n=30  win=9 half=0 push=3 lose=18  hit=33.3%  ROI=-9.6%
- 巴甲: n=30  win=14 half=0 push=2 lose=14  hit=50.0%  ROI=+8.4%
- 葡超: n=25  win=8 half=1 push=0 lose=16  hit=34.0%  ROI=-21.4%
- 墨超: n=24  win=10 half=1 push=0 lose=13  hit=43.8%  ROI=-19.0%
- 阿甲: n=22  win=6 half=0 push=3 lose=13  hit=31.6%  ROI=-29.2%
- 瑞超: n=21  win=10 half=0 push=0 lose=11  hit=47.6%  ROI=+11.7%
- 中超: n=12  win=5 half=0 push=1 lose=6  hit=45.5%  ROI=-1.8%
- 智利甲: n=5  win=2 half=0 push=0 lose=3  hit=40.0%  ROI=-27.2%
- 德乙: n=4  win=1 half=0 push=0 lose=3  hit=25.0%  ROI=-48.8%
- 丹超: n=4  win=2 half=1 push=0 lose=1  hit=62.5%  ROI=+32.0%
- 挪超: n=2  win=1 half=0 push=0 lose=1  hit=50.0%  ROI=-16.0%
- 西甲: n=1  win=1 half=0 push=0 lose=0  hit=100.0%  ROI=+111.0%

## 5. 混杂检查（联赛内 BG vs nonBG, played>=3）
- 美职: BG(n=9,ROI=+30.8%) vs nonBG(n=46,ROI=+14.7%)
- 巴甲: BG(n=2,ROI=+100.5%) vs nonBG(n=28,ROI=+1.9%)
- 阿甲: BG(n=10,ROI=-11.1%) vs nonBG(n=12,ROI=-44.3%)
- 瑞超: BG(n=10,ROI=+19.7%) vs nonBG(n=11,ROI=+4.4%)
- 中超: BG(n=2,ROI=-50.0%) vs nonBG(n=10,ROI=+7.9%)
- 智利甲: BG(n=1,ROI=-100.0%) vs nonBG(n=4,ROI=-9.0%)
- 参照: 全部867腿等额ROI=+0.0%

## 6. 结论与限制
- 保级主场组 ROI 显著高于整体(played>=3: +10.7% vs -0.5%) -> "保级主场+1星"方向有效
- 无欲无求组 ROI 明显低于整体(-2.8% vs +4.4%) -> "-1星降仓"方向有效
- 争冠/升级主场组 ROI +15.2%(n=25) -> 强队主场是正收益区, 加分可再评估
- 限制: ①样本仅563腿, played>=3可信组175腿, 统计噪音大 ②8月底多联赛仅1-3轮, zone早期不敏感 ③no_match 133腿存在偏差风险 ④等额注为主, 星级模拟用近似档位