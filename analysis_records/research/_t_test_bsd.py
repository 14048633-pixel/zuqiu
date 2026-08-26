# -*- coding: utf-8 -*-
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
os.chdir(r"D:\足球分析\prediction_v2")
from bsd_extra import fetch_odds
r = fetch_odds(222618)
print(json.dumps(r, ensure_ascii=False, indent=1)[:3000] if r else "None")
