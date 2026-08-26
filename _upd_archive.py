# -*- coding: utf-8 -*-
import json, io, datetime
ROOT = r"D:\足球分析"
fp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.json"
d = json.load(io.open(fp, encoding="utf-8"))
d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
d["norm_v1_file"] = "data/raw/football_data/bsd_team_stats_norm_20260818.json"
d["norm_v1_report"] = "analysis_records/opp_strength_norm_20260818.md"
d["norm_v1_conclusion"] = "v1粗版(单系数乘除)仅对混合联赛赛程有效(50/92队零变化, 最大delta 0.121); Levski/Monaco跨联赛水平失真未修复; 不可作为修正版入库, 需v2迭代赛事图rating"
d["norm_v1_related"] = ["analysis_records/opp_strength_norm_20260818.md", "analysis_records/opp_strength_norm_20260818_summary.json"]
io.open(fp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
print("archive json updated")
# MD 追加一节
mdfp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.md"
txt = io.open(mdfp, encoding="utf-8").read()
if "归一化 v1" not in txt:
    txt += """

## 归一化 v1 追加（2026-08-18 深夜）
- 文件：`data/raw/football_data/bsd_team_stats_norm_20260818.json`（raw+norm 双字段，92队，排除511场友谊赛/女足/U19）
- 公式：`norm = Σ(值 × 对手联赛coef × 时间权重) / Σ(coef × 时间权重)`，近40场，时间衰减 1.0/0.7/0.4/0.2
- 验证结论：**仅混合赛程球队有效**（CSKA Sofia / Kuopion / Nordsjælland 方向正确，最大±0.121）；50/92 队完全零变化；Levski(保加利亚)与 Monaco/Salzburg 跨联赛水平失真未修复
- 定性：v1 为过程产物，**不入库**；待 v2 赛事图迭代 rating 通过后并入主数据池
- 报告：`analysis_records/opp_strength_norm_20260818.md` / `opp_strength_norm_20260818_summary.json`
"""
    io.open(mdfp, "w", encoding="utf-8").write(txt)
    print("archive md updated")
