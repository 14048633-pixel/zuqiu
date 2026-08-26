# -*- coding: utf-8 -*-
import io, csv, sys, os, collections
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
for lg, div in [("美职","ML"), ("法乙","F2"), ("瑞超","SW"), ("巴甲","BR")]:
    teams = [t for t, divs in ts.items() if div in divs]
    homes = [ts[t][div]["home_gf"][1] for t in teams]
    print("%s(%s): %d队 | 主场样本 平均%.1f 最少%d 最多%d" % (lg, div, len(teams), sum(homes)/len(homes), min(homes), max(homes)))
