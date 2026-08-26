# -*- coding: utf-8 -*-
import json, io, datetime
ROOT = r"D:\足球分析"
# 归档 JSON
fp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.json"
d = json.load(io.open(fp, encoding="utf-8"))
d["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
d["norm_v3_file"] = "data/raw/football_data/bsd_team_stats_norm_v3_20260818.json"
d["norm_v3_report"] = "analysis_records/opp_strength_norm_v3_20260818.md"
d["norm_v3_source"] = "HF soccer-dataset (本地 67.4万场) 国内联赛 + BSD 欧战"
d["norm_v3_conclusion"] = "32队国内补齐(31融合+1陈旧), 92队统一: covered=55/merged=31/no_domestic=6(阿尔巴尼亚/安道尔/法罗/冰岛/里加); 红星/迪纳摩国内优势体现, 马卡比防守软化; no_domestic 6队仅欧战样本待人工复核"
io.open(fp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
# 归档 MD 追加
mdfp = ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.md"
txt = io.open(mdfp, encoding="utf-8").read()
if "归一化 v3" not in txt:
    txt += """

## 归一化 v3：国内联赛补齐（2026-08-18 深夜）
- 数据：`data/raw/football_data/bsd_team_stats_norm_v3_20260818.json`（92队统一，final_* 主用）
- 来源：HF soccer-dataset 本地数据集（2008-2027，67.4万场）国内联赛 + BSD 欧战
- 覆盖：32队国内补齐（奥超4/克甲3/塞超2/以超3/捷甲3/匈甲1/阿塞2/塞浦2/斯洛伐克1/斯洛文尼亚1/波黑1/格鲁吉亚1/哈1/亚美尼亚1/立1/拉1/爱1/北爱1/直1/科索沃1），3个队名映射修正
- 融合：`final = (w_euro×euro_v2 + w_dom×dom_est)/(w_euro+w_dom)`，w=min(n,20)；国内日期衰减+陈旧检测
- 92队分类：covered=55 / domestic_merged=31 / no_domestic=6（阿尔巴尼亚2、安道尔、法罗、冰岛、里加陈旧）
- 报告：`analysis_records/opp_strength_norm_v3_20260818.md`
"""
    io.open(mdfp, "w", encoding="utf-8").write(txt)
print("archive updated")
