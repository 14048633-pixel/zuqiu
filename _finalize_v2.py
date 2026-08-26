# -*- coding: utf-8 -*-
import json, io
ROOT = r"D:\足球分析"
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json"
d = json.load(io.open(fp, encoding="utf-8"))
# 清理 buggy v2i 字段, 保留 raw/v2/rat
for k, s in d["stats"].items():
    for f in ["v2i_home_gf","v2i_home_ga","v2i_away_gf","v2i_away_ga"]:
        s.pop(f, None)
d.pop("v2i_note", None)
d["method"] = {
    "v2_primary": "相对本联赛场均(主客分列) x 联赛水平coef, 样本收缩K=6向水平系数; 未覆盖联赛队先验=欧战池1.0并标记src_bias=uncovered",
    "rat_experimental": "阻尼0.5比率式赛事图迭代4轮(收敛), 原始进球单位; 存在池均值尺度漂移(def_h~1.37), 仅作参考不主用",
}
io.open(fp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
# 最终验证统计
stats = d["stats"]
n_unc = sum(1 for s in stats.values() if s.get("src_bias")=="uncovered")
print("teams:", len(stats), "| uncovered:", n_unc, "| covered:", len(stats)-n_unc)
import statistics
for f in ["v2_home_gf","v2_home_ga","v2_away_gf","v2_away_ga"]:
    vals = [s[f] for s in stats.values()]
    vals.sort()
    print("%-12s min=%.3f p10=%.3f med=%.3f p90=%.3f max=%.3f" % (f, vals[0], vals[len(vals)//10], statistics.median(vals), vals[len(vals)*9//10], vals[-1]))
# 极端值名单
print("\n== v2 极端值 (top/bottom 5 主攻击) ==")
srt = sorted(stats.items(), key=lambda kv: -kv[1]["v2_home_gf"])
for k, s in srt[:5]:
    print("%-24s v2主gf=%.3f 主ga=%.3f lvl=%s %s" % (d["name_of"].get(k, k), s["v2_home_gf"], s["v2_home_ga"], s["level"], s["src_bias"]))
for k, s in srt[-5:]:
    print("%-24s v2主gf=%.3f 主ga=%.3f lvl=%s %s" % (d["name_of"].get(k, k), s["v2_home_gf"], s["v2_home_ga"], s["level"], s["src_bias"]))
