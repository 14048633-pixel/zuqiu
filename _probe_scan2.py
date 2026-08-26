# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\足球分析\analysis_records\scans\scan_window_20260820_2220.json"
d = json.load(io.open(p, encoding="utf-8"))
ms = d["matches"]
print("场次数:", len(ms))
m = ms[0]
print("单场键:", list(m.keys()))
print(json.dumps(m, ensure_ascii=False, indent=1)[:3000])
