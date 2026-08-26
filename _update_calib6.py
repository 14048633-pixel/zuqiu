# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\strategy_data\league_calib.json"
d = json.load(io.open(P, encoding="utf-8"))
fixes = {
    "中超": {"new": 3.04, "old": 3.518, "cal": "近2季全量(2026 181场)=3.044"},
    "葡超": {"new": 2.63, "old": 2.84,  "cal": "近2季全量(24/25+25/26 612场)=2.626"},
    "英冠": {"new": 2.51, "old": 2.692, "cal": "近2季全量(E1 24/25+25/26 2760场)=2.513"},
    "意甲": {"new": 2.51, "old": 2.6968,"cal": "近2季全量(24/25+25/26 1900场)=2.507"},
    "美职": {"new": 3.08, "old": 3.016, "cal": "近2季全量(2024+2025 1047场)=3.082; 2026当前半季3.211偏热"},
    "阿甲": {"new": 2.04, "old": 1.885, "cal": "近2季全量(2026 321场)=2.044"},
}
for lg, f in fixes.items():
    c = d["leagues"].get(lg)
    if not c:
        print("缺联赛:", lg); continue
    old = c["league_avg"]
    c["league_avg"] = f["new"]
    c["note"] = ("%s | 2026-08-24 基准对齐(近2季全量口径): %s, 配置 %.3f -> %.2f" % (c.get("note","").split(" | 2026-08-24 基准对齐")[0].rstrip(" |"), f["cal"], f["old"], f["new"]))
    hist = c.setdefault("history", [])
    hist.append({
        "season": c.get("season", "?"),
        "league_avg": f["old"],
        "rho": c.get("rho", 0), "home": c.get("home", 1.0), "away": c.get("away", 0.95),
        "shrink": c.get("shrink", 0.8), "fatigue": c.get("fatigue", 0.9),
        "note": "2026-08-24 基准对齐: %s -> %.2f" % (f["cal"], f["new"])
    })
    print("更新 %s: %.4f -> %.2f" % (lg, old, f["new"]))
io.open(P, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
print("已保存 league_calib.json")
