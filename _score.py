# -*- coding: utf-8 -*-
import io, os, sys
sys.path.insert(0, r"D:\足球分析\prediction_v2")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import scan_upcoming as SU

lh, la, rho = 2.09, 0.60, 0.0
g = SU.dc_score_grid(lh, la, rho=rho, max_goals=8)
# 比分概率
scores = []
for i in range(9):
    for j in range(9):
        p = g[i][j]
        if p > 0.003:
            scores.append(("%d-%d" % (i,j), p))
scores.sort(key=lambda x:-x[1])
print("比分 Top8:")
for s,p in scores[:8]:
    print("  %s %.1f%%" % (s, p*100))
# 全场胜平负
hw = sum(g[i][j] for i in range(9) for j in range(9) if i>j)
dr = sum(g[i][j] for i in range(9) for j in range(9) if i==j)
aw = sum(g[i][j] for i in range(9) for j in range(9) if i<j)
print("全场 WDL: %.1f/%.1f/%.1f" % (hw*100, dr*100, aw*100))
# 大小球
ov25 = sum(g[i][j] for i in range(9) for j in range(9) if i+j>2.5)
print("大2.5: %.1f%%" % (ov25*100))
# 半场近似 (半场λ≈全场*0.45)
import math
hl = lh*0.45; ha = la*0.45
def pois(k, lam):
    return math.exp(-lam)*lam**k/math.factorial(k)
hg = {}
for i in range(9):
    for j in range(9):
        hg[(i,j)] = pois(i,hl)*pois(j,ha)
half_hw = sum(p for (i,j),p in hg.items() if i>j)
half_dr = sum(p for (i,j),p in hg.items() if i==j)
half_aw = sum(p for (i,j),p in hg.items() if i<j)
print("半场 WDL: %.1f/%.1f/%.1f" % (half_hw*100, half_dr*100, half_aw*100))
# 半全场近似 (独立)
combos = [("胜/胜",half_hw*hw),("胜/平",half_hw*dr),("胜/负",half_hw*aw),
          ("平/胜",half_dr*hw),("平/平",half_dr*dr),("平/负",half_dr*aw),
          ("负/胜",half_aw*hw),("负/平",half_aw*dr),("负/负",half_aw*aw)]
combos.sort(key=lambda x:-x[1])
print("半全场 Top3:")
for c,p in combos[:3]:
    print("  %s %.1f%%" % (c, p*100))
