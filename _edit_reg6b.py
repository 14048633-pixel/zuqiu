# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\regression_test.py"
s = io.open(P, encoding="utf-8").read()
c = 0
n1 = s.count("        su.SMALL_250_HIGH_EV = 0.10")
s = s.replace("        su.SMALL_250_HIGH_EV = 0.10", "        su.SMALL_250_HIGH_EV = 0.03")
c += n1
n2 = s.count('check("规则6小2.50高EV移除(阈值0.10)"')
s = s.replace('check("规则6小2.50高EV移除(阈值0.10)"', 'check("规则6小2.50高EV移除(阈值0.03)"')
c += n2
io.open(P, "w", encoding="utf-8").write(s)
print("阈值0.10->0.03:", n1, "处; 检查名替换:", n2, "处")
