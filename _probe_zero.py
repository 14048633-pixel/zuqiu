# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
for lg, div in [("美职","ML"), ("法乙","F2"), ("瑞超","SW"), ("巴甲","BR")]:
    zero = []
    for t, divs in ts.items():
        d = divs.get(div)
        if isinstance(d, dict) and int(d.get("n_home") or 0) == 0:
            zero.append((t, d.get("n_away"), d.get("src_season"), d.get("src_tag")))
    print(lg, "n_home=0 的队:", zero[:10])
