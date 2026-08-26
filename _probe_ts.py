# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
for t, divs in ts.items():
    if "ML" in divs:
        print(t, type(divs["ML"]))
        d = divs["ML"]
        if isinstance(d, dict):
            print("   keys:", list(d.keys()))
            print("   home_gf:", d.get("home_gf"), "home_ga:", d.get("home_ga"))
        break
