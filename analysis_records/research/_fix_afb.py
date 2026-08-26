# -*- coding: utf-8 -*-
"""修复 AFB 场次 bookmakers 结构: response[0].bookmakers"""
import sys, json, io
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json"
f = json.load(io.open(P, encoding="utf-8"))
fixed = 0
for eid, ev in f["matches"].items():
    if ev.get("source") == "api-football":
        bks = ev.get("bookmakers") or []
        flat = []
        for e0 in bks:
            if isinstance(e0, dict) and "bookmakers" in e0:
                flat += e0.get("bookmakers") or []
            else:
                flat.append(e0)
        ev["bookmakers"] = flat
        fixed += 1
json.dump(f, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("fixed afb matches:", fixed)
