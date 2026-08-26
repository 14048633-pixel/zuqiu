# -*- coding: utf-8 -*-
import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
os.chdir(r"D:\足球分析\prediction_v2")
from bsd_extra import fetch_odds
ids = [212167, 212165, 210441, 209535, 213538, 214783, 215962, 212144]
for eid in ids:
    r = fetch_odds(eid)
    c = (r or {}).get("consensus") or {}
    has = {k: v for k, v in c.items() if v is not None}
    print(eid, "n_nonnull=", len(has), list(has.keys())[:8])
    time.sleep(0.8)
