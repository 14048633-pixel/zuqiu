# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
from datetime import datetime, timezone
ts, lavg, index = su.load_team_stats()
m = {"id": "t", "league": "中超", "home": "Yunnan Yukun", "away": "Dalian Yingbo",
     "ct": datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc), "snap": "2026-08-15T10:00:00Z",
     "h2h": {"home": 2.1, "away": 3.15, "draw": 4.3},
     "spread": {"hdp_home": -0.5, "home_price": 2.06, "away_price": 1.85},
     "totals": {"line": 2.5, "over_price": 1.36, "under_price": 2.9}}
r = su.analyze_match(m, ts, lavg, index)
for b in (r.get("bets") or []):
    print("  ", b.get("name"), "prob=", b.get("prob"), "prob_raw=", b.get("prob_raw"), "ev=", round(b.get("ev",0),4), "odds=", b.get("odds"))
print("best:", r["best_bet"])
print("notes封顶:", [n for n in r["notes"] if "封顶" in n])
