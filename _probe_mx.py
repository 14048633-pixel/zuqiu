# -*- coding: utf-8 -*-
import io, csv, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\足球分析\data\raw\football_data\espn_墨超_2024_2025_results.csv"
rows = list(csv.DictReader(io.open(p, encoding="utf-8-sig")))
print("列:", list(rows[0].keys()))
print("场次:", len(rows))
print("赛季:", collections.Counter(r["Season"] for r in rows))
dates = sorted(r["Date"] for r in rows)
print("日期:", dates[0], "->", dates[-1])
print("队名样例:", sorted(set(r["HomeTeam"] for r in rows))[:5])
