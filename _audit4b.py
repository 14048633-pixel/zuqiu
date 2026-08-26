# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
for lg, div in [("美职","ML"), ("法乙","F2"), ("瑞超","SW"), ("巴甲","BR")]:
    teams = [t for t, divs in ts.items() if div in divs and isinstance(divs[div], dict)]
    nh = [int(ts[t][div]["n_home"] or 0) for t in teams]
    na = [int(ts[t][div]["n_away"] or 0) for t in teams]
    print("%s(%s): %d队 | 主场 n=%.1f(%.0f~%.0f) 客场 n=%.1f(%.0f~%.0f) | 主客场合计 平均%.0f" % (
        lg, div, len(teams), sum(nh)/len(nh), min(nh), max(nh), sum(na)/len(na), min(na), max(na), sum(nh[i]+na[i] for i in range(len(teams)))/len(teams)))
