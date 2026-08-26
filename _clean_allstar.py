# -*- coding: utf-8 -*-
import io, csv, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\data\raw\football_data\espn_美职_2024_2025_results.csv"
rows = list(csv.DictReader(io.open(P, encoding="utf-8-sig")))
junk = [r for r in rows if "All-Star" in r["HomeTeam"] or "All-Star" in r["AwayTeam"] or "All Stars" in r["HomeTeam"] or "All Stars" in r["AwayTeam"]]
print("All-Star 行数:", len(junk))
for r in junk:
    print("  ", r["Date"], r["HomeTeam"], r["AwayTeam"], r["FTHG"], r["FTAG"])
if junk:
    clean = [r for r in rows if r not in junk]
    with io.open(P, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in clean:
            w.writerow(r)
    print("已清理, 剩余:", len(clean))
