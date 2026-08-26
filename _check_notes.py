# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(io.open(r"D:\足球分析\strategy_data\league_calib.json", encoding="utf-8"))
for lg in ["中超","葡超","英冠","意甲","美职","阿甲","法甲"]:
    c = d["leagues"][lg]
    print("== %s: avg=%.3f rho=%s ou=%s" % (lg, c["league_avg"], c.get("rho"), c.get("ou_strength_adj")))
    print("   note尾部:", c["note"][-120:])
