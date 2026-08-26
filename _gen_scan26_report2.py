# -*- coding: utf-8 -*-
import json, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r"D:\足球分析"
d = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan_next24h_20260825_1605.json"), encoding="utf-8"))
L = []
L.append("# 2026-08-26 未来24h 扫描报告 v2（70 场, 已补天皇杯盘口）")
L.append("")
L.append("- 扫描时间: 2026-08-26 00:05 BJT | 窗口: 08-26 00:00 ~ 23:30")
L.append("- 盘口来源: BSD consensus 30 场 + API-Football 天皇杯 16 场 = 有盘 46 场")
L.append("- 无盘 24 场: 天皇杯 16 / 友谊赛 5 / 巴西杯 1 / 巴乙 1 / 哥甲 1")
L.append("")
L.append("## BEST 出单（★1, 8 场）")
L.append("| 时间 | 联赛 | 对阵 | 腿 | p | 赔 | EV | 风险 |")
L.append("|---|---|---|---|---|---|---|---|")
for o in sorted(d, key=lambda x: x["ko_bjt"]):
    if o.get("best_bet"):
        bb = o["best_bet"]
        tags = "; ".join((o.get("risk_tags") or [])[:3])
        L.append("| %s | %s | %s vs %s | %s | %s | %s | +%.1f%% | %s |" % (o["ko_bjt"], o["league"], o["home"], o["away"], bb["name"], bb["prob"], bb["odds"], bb["ev"]*100, tags))
L.append("")
L.append("## 否决（6 场）")
for o in sorted(d, key=lambda x: x["ko_bjt"]):
    if o.get("vetoed"):
        L.append("- %s %s %s vs %s: %s" % (o["ko_bjt"], o["league"], o["home"], o["away"], o["veto_reason"]))
L.append("")
L.append("## 天皇杯 16 场（API-FB 补盘, 全部缺亚盘）")
L.append("| 时间 | 对阵 | 方向 | EV | 备注 |")
L.append("|---|---|---|---|---|")
for o in sorted(d, key=lambda x: x["ko_bjt"]):
    if o["league"] == "天皇杯" and o.get("dir_odds"):
        note = o.get("veto_reason") or ""
        if not note and o.get("star") == 0:
            note = "★0 参考"
        L.append("| %s | %s vs %s | %s | %+.1f%% | %s |" % (o["ko_bjt"], o["home"], o["away"], o["direction"], o["dir_ev"]*100, note))
L.append("")
L.append("## 提示")
L.append("- 8 BEST 中 7 场小2.50（清一色小），集中在英联杯第一轮；唯一推大 Stevenage vs Reading λ3.17")
L.append("- 天皇杯 2 场正 EV 方向（Montedio 大2.50 +15.2%、Jubilo 大2.50 +17.0%）因距开赛 18h>12h 被「盘口过早」否决；明天 06:00 后重拉临场盘可复出")
L.append("- 天皇杯其余有盘场次模型大球 vs 市场全部负 EV（-28%~-59%），市场给大球价更高，模型高估杯赛大球（国内杯兜底 3.28）")
txt = "\n".join(L)
fp = os.path.join(ROOT, "analysis_records", "scan_next24h_20260826_report.md")
io.open(fp, "w", encoding="utf-8").write(txt)
print("saved", fp)
