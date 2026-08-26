# -*- coding: utf-8 -*-
import json, io, datetime
ROOT = r"D:\足球分析"
# 归档 JSON
fp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.json"
d = json.load(io.open(fp, encoding="utf-8"))
d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
d["v3_lambda_validate"] = {
    "report": "analysis_records/key46_v3_lambda_validate_20260818.md",
    "data": "analysis_records/key46_v3_lambda_20260818_2357.json",
    "conclusion": "v3接入46/46覆盖; 但跨联赛λ压缩失真(Getafe/Partizan客胜EV+285%等10场EV>50%假正,多数逆市场); v3暂不替换raw λ做EV主引擎, 保留数据覆盖+交叉验证; 中期需跨联赛level-gap校准+放开收缩K"
}
io.open(fp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
# 归档 MD 追加
mdfp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.md"
txt = io.open(mdfp, encoding="utf-8").read()
if "v3 λ 集成验证" not in txt:
    txt += """

## v3 λ 集成验证（2026-08-18 深夜 → 08-19）
- 接入：v3 final_* 全量接入 λ 链路，46/46 覆盖
- 结果：1X2 EV>5% 旧14→v3 22，但 10 场 EV>50% 多为逆市场假正（Getafe/Partizan 客胜EV+285%、Motherwell/Freiburg 主胜EV+109%）
- 根因：v2收缩拉平精英防守（Getafe 主场失球0.72→0.96）+ 融合数据压缩强度差（Partizan 客防1.52→0.92）+ 跨联赛相对评级无法正确复合
- 结论：**v3 暂不替换 raw λ 作 EV 主引擎**，保留覆盖+交叉验证；中期需跨联赛 level-gap 校准 + 放开收缩K
- 报告：`analysis_records/key46_v3_lambda_validate_20260818.md`
"""
    io.open(mdfp, "w", encoding="utf-8").write(txt)
print("archive updated")
