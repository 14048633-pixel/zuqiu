# -*- coding: utf-8 -*-
"""自检1: 27场风险标签分布 + 数据覆盖情况"""
import json, io
from collections import Counter
d = json.load(io.open("analysis_records/research/rerun_0822_intel.json", encoding="utf-8"))
ms = d["matches"]
tag_cnt = Counter()
data_src = Counter()
for m in ms:
    r = m["result"]
    for t in (r.get("risk_tags") or []):
        tag_cnt[t] += 1
    ds = r.get("data_src") or {}
    data_src[(ds.get("home"), ds.get("away"))] += 1
print("=== 风险标签分布 (27场) ===")
for t, n in tag_cnt.most_common(20):
    print("  %-40s %d" % (t, n))
print()
print("=== 数据源组合 ===")
for k, n in data_src.most_common():
    print("  home=%-6s away=%-6s %d" % (k[0], k[1], n))
