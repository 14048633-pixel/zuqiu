# -*- coding: utf-8 -*-
"""自检4: 27场 三市场覆盖矩阵"""
import json, io
d = json.load(io.open("analysis_records/research/rerun_0822_intel.json", encoding="utf-8"))
full = part = 0
for m in d["matches"]:
    books = m.get("books") or {}
    has_h = "h2h" in books; has_s = "spread" in books; has_t = "totals" in books
    mark = "✔" if (has_h and has_s and has_t) else "✘"
    if has_h and has_s and has_t: full += 1
    else: part += 1
    print("%s %-10s %-22s vs %-20s 1X2=%s 亚盘=%s 大小球=%s" % (mark, m["league"], m["home"], m["away"], "✔" if has_h else "-", "✔" if has_s else "-", "✔" if has_t else "-"))
print()
print("三市场齐全:", full, "/", full+part, "| 缺失:", part)
