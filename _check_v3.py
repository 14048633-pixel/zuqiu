# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json", encoding="utf-8"))
print("load OK, teams:", len(d["teams"]), "| lg_avg keys:", len(d["league_avg"]))
# 检查 Riga 与各队 n_dom
for nm, m in sorted(d["teams"].items()):
    print("%-26s bias=%-16s n_e=%.0f/%.0f n_d=%.0f/%.0f final主攻=%.2f" % (
        nm, m["src_bias"], m.get("n_euro_home",0), m.get("n_euro_away",0),
        m.get("n_dom_home",0), m.get("n_dom_away",0), m["final_home_gf"]))
