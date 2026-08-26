# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\regression_test.py"
s = io.open(P, encoding="utf-8").read()
old1 = "    # 近30场实测: J1(2026/27新规20场) 场均3.35"
new1 = "    # 近30场实测: J1(2026/27新规3轮30场) 场均3.20"
old2 = '    # 活数据: 08-21 新增完赛后近30场实测=3.41 (配置3.35, 偏差0.06<0.30, 仍不触发平移)'
new2 = '    # 活数据: 08-24 补至3轮30场后近30场实测=3.20 (配置3.35, 偏差0.15<0.30, 仍不触发平移)'
old3 = '    check("J1近场实测场均≈3.4", round(j1r[0], 2) if j1r else 0, 3.41, tol=0.06)'
new3 = '    check("J1近场实测场均≈3.2", round(j1r[0], 2) if j1r else 0, 3.20, tol=0.06)'
cnt = 0
for o, n in [(old1, new1), (old2, new2), (old3, new3)]:
    if o in s:
        s = s.replace(o, n); cnt += 1
    else:
        print("未找到:", o[:60])
io.open(P, "w", encoding="utf-8").write(s)
print("替换完成:", cnt, "/3")
