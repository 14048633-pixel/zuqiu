# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\regression_test.py"
s = io.open(P, encoding="utf-8").read()
old = ("        # 2026-08-24 比甲/荷甲/葡超补全2024-2026+2026/27后: Casa Pia小2.50 EV由22.1%降至15.7%(数据不足假信号消失),\n"
       "        #   不再触发⑥B禁出; 临时降阈值0.10验证\"EV>=阈值物理禁出\"机制仍生效")
new = ("        # 2026-08-24 葡超基准对齐2.84->2.63后: Casa Pia小2.50 EV再降至4.7%,\n"
       "        #   不再触发⑥B默认阈值; 临时降阈值0.03验证\"EV>=阈值物理禁出\"机制仍生效")
if old in s:
    s = s.replace(old, new); print("注释已更新")
else:
    print("注释未找到(可能已改)")
io.open(P, "w", encoding="utf-8").write(s)
