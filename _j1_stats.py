import io, csv, sys
sys.stdout.reconfigure(encoding="utf-8")
rows = []
with io.open(r"D:\足球分析\data\raw\football_data\j1_2026_results.csv", encoding="utf-8-sig") as f:
    for r in csv.reader(f):
        if r and len(r)>=7 and r[0]=="JP1":
            rows.append(r)
n = len(rows)
total = sum(int(r[4])+int(r[5]) for r in rows)
hg = sum(int(r[4]) for r in rows); ag = sum(int(r[5]) for r in rows)
o25 = sum(1 for r in rows if int(r[4])+int(r[5]) > 2.5)
o35 = sum(1 for r in rows if int(r[4])+int(r[5]) > 3.5)
btts = sum(1 for r in rows if int(r[4])>0 and int(r[5])>0)
hw = sum(1 for r in rows if int(r[4])>int(r[5]))
dr = sum(1 for r in rows if int(r[4])==int(r[5]))
aw = sum(1 for r in rows if int(r[4])<int(r[5]))
# 按轮次分
from collections import defaultdict
by_round = defaultdict(list)
for r in rows:
    d = r[1]
    if d <= "2026/08/09": k = "R1(8/7-9)"
    elif d <= "2026/08/15": k = "R2(8/14-15)"
    elif d <= "2026/08/23": k = "R3(8/21-23)"
    else: k = d
    by_round[k].append(r)
print("总场次:", n, "| 总进球:", total, "| 场均: %.2f" % (total/n))
print("主队场均: %.2f | 客队场均: %.2f" % (hg/n, ag/n))
print("大2.5: %d 场 %.1f%% | 大3.5: %.1f%% | 双方进球: %.1f%%" % (o25, o25/n*100, o35/n*100, btts/n*100))
print("主胜 %d (%.1f%%) | 平 %d (%.1f%%) | 客胜 %d (%.1f%%)" % (hw, hw/n*100, dr, dr/n*100, aw, aw/n*100))
print()
print("分轮:")
for k in sorted(by_round):
    rs = by_round[k]
    t = sum(int(x[4])+int(x[5]) for x in rs)
    o = sum(1 for x in rs if int(x[4])+int(x[5])>2.5)
    h2 = sum(1 for x in rs if int(x[4])>int(x[5])); d2 = sum(1 for x in rs if int(x[4])==int(x[5])); a2 = sum(1 for x in rs if int(x[4])<int(x[5]))
    print("  %s: %d场 场均%.2f 大2.5=%.0f%% 主%d/平%d/客%d" % (k, len(rs), t/len(rs), o/len(rs)*100, h2, d2, a2))
# 比分分布 top
from collections import Counter
sc = Counter((int(r[4]), int(r[5])) for r in rows)
print()
print("比分Top10:", sc.most_common(10))
