# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\足球分析\analysis_records\scans\scan_window_20260820_2220.json"
d = json.load(io.open(p, encoding="utf-8"))
print("顶层类型:", type(d).__name__)
if isinstance(d, dict):
    print("顶层键:", list(d.keys())[:15])
    # 找第一场比赛
    for k, v in d.items():
        if isinstance(v, dict) and ("home" in v or "h2h" in v or "bets" in v):
            print("示例键:", k)
            print(json.dumps(v, ensure_ascii=False, indent=1)[:2500])
            break
elif isinstance(d, list):
    print("长度:", len(d))
    print(json.dumps(d[0], ensure_ascii=False, indent=1)[:2500])
