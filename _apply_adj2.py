import json, io, shutil
fp = "strategy_data/league_calib.json"
shutil.copy(fp, fp + ".bak_20260824_ou_strength_ext")
d = json.load(io.open(fp, encoding="utf-8"))
L = d["leagues"]

# 1) 荷甲基准固化 3.15 -> 3.50 (实测3.567, 自动平移3.36临时值, 固化治本λ低估)
old_avg = L["荷甲"]["league_avg"]
L["荷甲"]["league_avg"] = 3.50
L["荷甲"]["note"] = (L["荷甲"]["note"] + " | 2026-08-24 基准固化 3.15->3.50(实测3.567, 防每场靠自动平移)").strip(" |")
print(f"荷甲 league_avg {old_avg} -> 3.50")

# 2) 方案A扩展 (总偏移>=3pp, 小样本档收缩)
ADJ = {
 "中超": {"混合": 0.09, "弱弱": 0.06},          # +8.5pp总; 强强仅5场不配
 "英冠": {"强强": 0.12, "混合": 0.05, "弱弱": 0.04},  # +6.0pp, 1115场大样本
 "比甲": {"混合": 0.04, "弱弱": 0.10},          # +5.6pp; 强强10场不配, 弱弱65场14.9收缩
 "意甲": {"混合": 0.04, "弱弱": 0.07},          # +4.0pp; 强强-7.1负向不配
 "德甲": {"强强": 0.09, "弱弱": 0.05},          # +3.4pp; 混合+0.7不配, 强强56场11.9收缩
}
for lg, adj in ADJ.items():
    L[lg]["ou_strength_adj"] = adj
    L[lg]["note"] = (L[lg]["note"] + " | 2026-08-24 方案A扩展: ou_strength_adj=%s(per-match拟合总偏移%+.1fpp)" % (json.dumps(adj, ensure_ascii=False), {"中超":8.5,"英冠":6.0,"比甲":5.6,"意甲":4.0,"德甲":3.4}[lg])).strip(" |")
    print(f"{lg} ou_strength_adj={adj}")
json.dump(d, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved")
