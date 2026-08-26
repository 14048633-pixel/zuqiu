# -*- coding: utf-8 -*-
import json, io
ROOT = r"D:\足球分析"
b = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_edges_20260818.json", encoding="utf-8"))
scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
name_of = {}
for m in scan["matches"]:
    if m.get("home_id"): name_of[m["home_id"]] = m["home"]
    if m.get("away_id"): name_of[m["away_id"]] = m["away"]
LEAGUE_COEF = {7:1.0, 8:1.0, 83:1.0, 90:1.0}
dom = {}
lg_n = {}
for e in b["edges"]:
    for t in (e["ht"], e["at"]):
        dom.setdefault(t, {})
        dom[t][e["lid"]] = dom[t].get(e["lid"], 0) + 1
        lg_n[e["lid"]] = lg_n.get(e["lid"], 0) + 1
# 找出主导联赛是欧战(7/8/83/90)的核心队伍
for tid_str in b["team_edges"]:
    tid = int(tid_str)
    d = dom.get(tid, {})
    if not d: continue
    top = max(d, key=d.get)
    if top in (7, 8, 83, 90):
        # 该队其它联赛分布
        others = sorted(d.items(), key=lambda x: -x[1])[:4]
        print("%-26s tid=%-5d 主导=%s n=%d 其他=%s" % (name_of.get(tid, "?"), tid, top, d[top], others))
