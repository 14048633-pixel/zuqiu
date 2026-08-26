# -*- coding: utf-8 -*-
import json, io, hashlib, datetime
ROOT = r"D:\足球分析"
norm_fp = ROOT + r"\data\raw\football_data\bsd_team_stats_norm_20260818.json"
d = json.load(io.open(norm_fp, encoding="utf-8"))
stats = d["stats"]
fields = ["home_gf","home_ga","away_gf","away_ga"]
up = down = zero = 0
big = []
lvl_deltas = {f: [] for f in fields}
for name, s in stats.items():
    for f in fields:
        dd = s["norm_"+f] - s["raw_"+f]
        lvl_deltas[f].append(dd)
        if abs(dd) < 0.005: zero += 1
        elif dd > 0: up += 1
        else: down += 1
        if abs(dd) >= 0.05:
            big.append({"team": name, "field": f, "raw": s["raw_"+f], "norm": s["norm_"+f], "delta": round(dd,3), "league": s["league"]})
big.sort(key=lambda x: -abs(x["delta"]))
summary = {
    "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    "data_file": "data/raw/football_data/bsd_team_stats_norm_20260818.json",
    "n_teams": len(stats),
    "excluded_events": d.get("excluded_events"),
    "field_level_change": {"up": up, "down": down, "zero": zero},
    "teams_unchanged": sum(1 for s in stats.values() if all(abs(s["norm_"+f]-s["raw_"+f])<0.005 for f in fields)),
    "fields_delta_ge_0_05": len(big),
    "max_abs_delta": max((abs(lvl_deltas[f][i]) for f in fields for i in range(len(lvl_deltas[f]))), default=0),
    "mean_abs_delta": round(sum(abs(x) for f in fields for x in lvl_deltas[f])/(len(stats)*4), 4),
    "top_changes": big[:15],
    "v1_limitations": [
        "同联赛同tier赛程时 coef 在分子分母抵消, 归一=原值 (50/92队零变化)",
        "跨联赛水平(等级)失真未修复: Levski 保加利亚0.303 vs AEK 希腊0.694 依旧不可比",
        "防御方向对弱队刷失球无收缩, 单系数只做重要性加权, 不做level平移",
    ],
    "v2_proposal": "按赛事图做迭代逐队攻防rating(欧洲赛事为跨联赛桥梁) + 联赛环境level调整 + 样本收缩",
}
fp = ROOT + r"\analysis_records\opp_strength_norm_20260818_summary.json"
io.open(fp, "w", encoding="utf-8").write(json.dumps(summary, ensure_ascii=False, indent=1))
print("saved", fp)
print("字段级: up=%d down=%d zero=%d | 队零变化=%d | max_delta=%.3f" % (up, down, zero, summary["teams_unchanged"], summary["max_abs_delta"]))
for r in big[:10]:
    print("  %-24s %-8s %+0.3f" % (r["team"], r["field"], r["delta"]))
