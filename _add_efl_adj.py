import json, io, shutil, sys
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
fp = r"D:\足球分析\strategy_data\league_calib.json"
bak = fp.replace(".json", ".bak_20260826_ouadj.json")
shutil.copy(fp, bak)
d = json.load(io.open(fp, encoding="utf-8"))
cc = d.setdefault("cup_coeffs", {})
cc["英联杯"] = {
    "league_avg": 3.28,
    "home": 1.15,
    "away": 1.0,
    "fatigue": 0.9,
    "rho": 0,
    "shrink": 0.8,
    "season": "2026/2027",
    "note": "Carabao Cup R1 强弱悬殊, 套用国内杯基准3.28; 方案A分档: 强强+12/混合+8/弱弱+5pp(参照英冠+葡超拟合)",
    "ou_strength_adj": {"强强": 0.12, "混合": 0.08, "弱弱": 0.05},
}
json.dump(d, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("已加英联杯 cup_coeffs, 备份:", bak)
