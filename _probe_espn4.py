# -*- coding: utf-8 -*-
import io, csv, sys, os
sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\足球分析\data\raw\football_data"
for fn in ["espn_美职_results.csv","espn_法乙_results.csv","espn_瑞超_results.csv","espn_巴甲_results.csv"]:
    p = os.path.join(D, fn)
    rows = list(csv.DictReader(io.open(p, encoding="utf-8-sig")))
    if not rows:
        print(fn, "空"); continue
    cols = list(rows[0].keys())
    dates = sorted(r.get("Date","") for r in rows)
    seas = sorted(set((r.get("Season") or r.get("season") or "?").strip() for r in rows))
    print("==", fn, "| 列:", cols)
    print("   场次:", len(rows), "| 赛季:", seas)
    print("   日期范围:", dates[0], "->", dates[-1])
    teams = sorted(set(r.get("HomeTeam","") for r in rows))
    print("   队伍数:", len(teams), "| 样例:", teams[:6])
