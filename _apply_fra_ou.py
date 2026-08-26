# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\strategy_data\league_calib.json"
d = json.load(io.open(P, encoding="utf-8"))
c = d["leagues"]["法甲"]
c["ou_strength_adj"] = {"混合": -0.03, "弱弱": -0.06}
c["note"] = (c["note"] + " | 2026-08-24 方案A负校准(612场拟合): 模型高估大球总-3.3pp(混合-3.9/弱弱-8.1), 负档下调大球; 强强+1.5反向不配").strip(" |")
io.open(P, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
print("法甲 ou_strength_adj 已写入:", c["ou_strength_adj"])
