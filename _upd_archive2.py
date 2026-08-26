# -*- coding: utf-8 -*-
import json, io, datetime
ROOT = r"D:\足球分析"
# 归档 JSON
fp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.json"
d = json.load(io.open(fp, encoding="utf-8"))
d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
d["norm_v2_file"] = "data/raw/football_data/bsd_team_stats_norm_v2_20260818.json"
d["norm_v2_report"] = "analysis_records/opp_strength_norm_v2_20260818.md"
d["norm_v2_edges"] = "data/raw/football_data/bsd_edges_20260818.json"
d["norm_v2_conclusion"] = "v2(相对本联赛均值x联赛水平+收缩K=6)修复v1抵消与跨联赛失真: Levski主ga 0.483->0.433, Monaco客ga 1.93->1.06, 联赛均值随coef单调; 关键发现BSD仅覆盖80联赛, 37/92队仅欧战样本(src_bias=uncovered标记); 迭代(rat)尺度漂移不主用"
io.open(fp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
# 归档 MD 追加
mdfp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.md"
txt = io.open(mdfp, encoding="utf-8").read()
if "归一化 v2" not in txt:
    txt += """

## 归一化 v2 追加（2026-08-18 深夜）
- 文件：`data/raw/football_data/bsd_team_stats_norm_v2_20260818.json`（raw/v2/rat 三套 + src_bias + league_context）
- 边表：`data/raw/football_data/bsd_edges_20260818.json`（6706 场去重，limit=100 重拉，0 错误）
- **关键发现：BSD 仅覆盖 80 联赛，37/92 队国内联赛 0 场（奥超/克甲/塞超/以超等），只有欧战样本 → src_bias=uncovered 标记，先验=1.0**
- v2 公式：`相对本联赛场均(主客分列) × 联赛水平coef` + 收缩 K=6，修复 v1 系数抵消缺陷
- 验证：Levski 主ga 0.483→0.433（不再0.30失真）、Monaco 客ga 1.93→1.06、联赛均值随 coef 单调
- 迭代（rat，阻尼0.5×4轮）：强弱赛程修正有效但池均值尺度漂移（def≈1.37），仅参考
- 报告：`analysis_records/opp_strength_norm_v2_20260818.md`
"""
    io.open(mdfp, "w", encoding="utf-8").write(txt)
print("archive updated")
