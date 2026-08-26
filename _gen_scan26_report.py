# -*- coding: utf-8 -*-
import json, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r"D:\足球分析"
d = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan_next24h_20260825_1551.json"), encoding="utf-8"))
L = []
L.append("# 2026-08-26 未来24h 扫描报告（70 场）")
L.append("")
L.append("- 扫描时间: 2026-08-25 23:51 BJT | 窗口: 08-26 00:00 ~ 23:30")
L.append("- 数据: BSD 事件 70 场 + match_package 建包（含伤停/阵型/攻防） + BSD consensus 盘口覆盖 30 场")
L.append("- 无盘 40 场（BSD 免费档无盘口）: 天皇杯 32 / 友谊赛 5 / 巴西杯 1 / 巴乙 1 / 哥甲 1")
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
L.append("## 否决（4 场）")
for o in sorted(d, key=lambda x: x["ko_bjt"]):
    if o.get("vetoed"):
        L.append("- %s %s %s vs %s: %s" % (o["ko_bjt"], o["league"], o["home"], o["away"], o["veto_reason"]))
L.append("")
L.append("## 有方向参考（有盘非BEST, 22 场）")
L.append("| 时间 | 联赛 | 对阵 | 方向 | EV | 一致性 |")
L.append("|---|---|---|---|---|---|")
for o in sorted(d, key=lambda x: x["ko_bjt"]):
    if not o.get("best_bet") and not o.get("vetoed") and o.get("dir_odds"):
        dc = (o.get("dir_consistency") or {}).get("level")
        L.append("| %s | %s | %s vs %s | %s | %+.1f%% | %s |" % (o["ko_bjt"], o["league"], o["home"], o["away"], o["direction"], o["dir_ev"]*100, dc))
L.append("")
L.append("## 无盘口场次（40 场, 无法算EV）")
from collections import Counter
c = Counter(o["league"] for o in d if not o.get("dir_odds") and not o.get("error"))
for lg, n in c.most_common():
    L.append("- %s: %d 场" % (lg, n))
L.append("")
L.append("## 提示")
L.append("- 8 BEST 中 7 场为小2.50（清一色小），集中在英联杯第一轮（跨联赛 E2/E3/E0 数据+30%收缩）；Stevenage vs Reading λ3.17 唯一推大")
L.append("- 英联杯 6 场 BEST 全部标注「缺亚盘」（BSD 无让球盘）；杯赛参数走国内杯兜底 3.28，但球队实际 λ 2.3~2.65，模型与市场 2.5 线接近")
L.append("- 天皇杯 32 场 BSD 免费档无盘口：需 API-Football 补盘才能出方向，已标注缺盘")
txt = "\n".join(L)
fp = os.path.join(ROOT, "analysis_records", "scan_next24h_20260826_report.md")
io.open(fp, "w", encoding="utf-8").write(txt)
print("saved", fp)
