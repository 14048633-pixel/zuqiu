# -*- coding: utf-8 -*-
import io, csv, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
rows = []
with io.open(r"D:\足球分析\data\raw\football_data\j1_2026_results.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r.get("Div") == "JP1":
            rows.append(r)
hc = Counter(r["HomeTeam"] for r in rows)
ac = Counter(r["AwayTeam"] for r in rows)
allt = sorted(set(hc) | set(ac))
print("队伍数:", len(allt), "| 总场次:", len(rows))
print("每队主场区间: 最少%d 最多%d 平均%.2f" % (min(hc[t] for t in allt), max(hc[t] for t in allt), sum(hc[t] for t in allt)/len(allt)))
print("主场<2 的队:", [t for t in allt if hc[t] < 2])
