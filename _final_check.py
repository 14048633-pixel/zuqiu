# -*- coding: utf-8 -*-
import io, json, os, sys, csv
sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\足球分析\data\raw\football_data"
# 1) backfill 文件
for fn in ["espn_美职_2024_2025_results.csv","espn_法乙_2024_2025_results.csv","espn_瑞超_2024_2025_results.csv","espn_巴甲_2024_2025_results.csv"]:
    p = os.path.join(D, fn)
    n = sum(1 for _ in io.open(p, encoding="utf-8-sig")) - 1
    print("backfill %-34s %4d场" % (fn, n))
# 2) league_calib 校验
c = json.load(io.open(r"D:\足球分析\strategy_data\league_calib.json", encoding="utf-8"))
for lg in ["中超","葡超","英冠","意甲","美职","阿甲","法甲"]:
    cc = c["leagues"][lg]
    print("calib %-4s avg=%.3f %s" % (lg, cc["league_avg"], cc.get("ou_strength_adj")))
# 3) SESSION_STATE
s = io.open(r"D:\足球分析\SESSION_STATE.md", encoding="utf-8").read()
print("SESSION 更新行:", [l for l in s.split(chr(10)) if l.startswith("> 最近更新")][0][:90])
print("包含三个新节:", all(k in s for k in ["4联赛 2024/2025 历史补拉", "6联赛基准对齐", "法甲方案A 负校准"]))
# 4) 备份文件存在
for b in ["league_calib.json.bak_20260824_leagueavg_6", "league_calib.json.bak_20260824_fra_ou"]:
    print("备份", b, os.path.exists(os.path.join(r"D:\足球分析\strategy_data", b)))
