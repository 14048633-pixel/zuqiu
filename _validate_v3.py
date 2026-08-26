# -*- coding: utf-8 -*-
import json, io, sys, statistics
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json", encoding="utf-8"))
ts = d["teams"]
# 完整性
missing = [k for k, v in ts.items() if any(("final_"+s) not in v for s in ["home_gf","home_ga","away_gf","away_ga"])]
nan = [k for k, v in ts.items() if any(v.get("final_"+s) is None or v.get("final_"+s) != v.get("final_"+s) for s in ["home_gf","home_ga","away_gf","away_ga"])]
print("teams:", len(ts), "| missing final:", missing, "| NaN:", nan)
# 分布
for s in ["final_home_gf","final_home_ga","final_away_gf","final_away_ga"]:
    vals = sorted(v[s] for v in ts.values())
    print("%-14s min=%.3f p10=%.3f med=%.3f p90=%.3f max=%.3f" % (s, vals[0], vals[len(vals)//10], statistics.median(vals), vals[len(vals)*9//10], vals[-1]))
# top/bottom 攻击
srt = sorted(ts.items(), key=lambda kv: -kv[1]["final_home_gf"])
print("\ntop5 主攻:", [(k, v["final_home_gf"], v["src_bias"]) for k, v in srt[:5]])
print("bottom5 主攻:", [(k, v["final_home_gf"], v["src_bias"]) for k, v in srt[-5:]])
# merged 贡献统计
mc = [v for v in ts.values() if v["src_bias"]=="domestic_merged"]
print("\nmerged 队伍主攻 euro vs final 均值: %.3f vs %.3f" % (sum(v["euro_home_gf"] for v in mc)/len(mc), sum(v["final_home_gf"] for v in mc)/len(mc)))
