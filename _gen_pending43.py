# -*- coding: utf-8 -*-
import json, io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
with open(r"D:\足球分析\analysis_records\pending_43_20260823.json", encoding="utf-8") as f:
    d = json.load(f)
ms = d["matches"]

L = []
L.append("# 📋 待结算 43 场跟踪清单（2026-08-23 00:15 记录）")
L.append("")
L.append("> 来源：scan24h_analysis_20260822_2136.json（20:45 临场盘）｜规则调整待 43 场全部结束后进行")
L.append("> 口径：⛔=被否决（只记方向不出单）｜★=出单星级｜EV=模型去水公平EV")
L.append("")

buckets = [("今晚已开踢 22:30~23:15", "08-22 22:30", "08-22 23:59"),
           ("凌晨 00:00~03:30", "08-23 00:00", "08-23 03:30"),
           ("早间 05:30~07:30", "08-23 05:30", "08-23 23:59")]
for title, lo, hi in buckets:
    grp = [m for m in ms if lo <= m["ct"] <= hi]
    if not grp:
        continue
    L.append("## %s（%d 场）" % (title, len(grp)))
    L.append("")
    L.append("| 开赛 | 联赛 | 对阵 | 主方向 | 赔率 | EV | 星级 | 结果 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m in grp:
        dirn = m["direction"]; bb = m["best_bet"]
        veto = "⛔" if dirn.get("vetoed") else ""
        star = ("★%d" % bb["star"]) if bb else ""
        evp = "%.1f%%" % (dirn["ev"]*100)
        L.append("| %s | %s | %s vs %s | %s %s | %.2f | %s | %s | 待结算 |" % (
            m["ct"], m["league"], m["home"], m["away"], dirn["name"], veto,
            dirn["odds"], evp, star))
    L.append("")

L.append("## 附：出单（非否决）场次合计")
out = [m for m in ms if not m["direction"].get("vetoed")]
L.append("- 待结算共 **%d** 场，其中出单方向 **%d** 场，被否决（仅记方向）**%d** 场" % (len(ms), len(out), len(ms)-len(out)))
L.append("")
L.append("> 生成时间：2026-08-23 00:15｜源：pending_43_20260823.json")
L.append("")

out_md = r"D:\足球分析\analysis_records\pending_43_20260823.md"
with open(out_md, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("MD saved:", out_md)
print("出单:", len(out), "| 否决:", len(ms)-len(out))
