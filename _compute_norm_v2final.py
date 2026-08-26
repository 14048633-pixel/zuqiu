# -*- coding: utf-8 -*-
"""v2final: 比率式赛事图迭代 (atk=Σgf/Σdef_opp, def=Σga/Σatk_opp), 原始进球单位, 3轮
非核心对手初值=该队与核心队交手的raw均值; 核心队初值=自身raw
"""
import sys, io, json
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2
b = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_edges_20260818.json", encoding="utf-8"))
v2 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", encoding="utf-8"))
edges = b["edges"]; name_of = v2["name_of"]
core = {int(k) for k in v2["stats"]}

# 每队按时间排序的边
team_ev = defaultdict(list)
for e in edges:
    team_ev[e["ht"]].append(e); team_ev[e["at"]].append(e)

def raw_side(edges_list, tid):
    el = sorted(edges_list, key=lambda e: e["date"], reverse=True)
    a_h=[0.0,0.0]; d_h=[0.0,0.0]; a_a=[0.0,0.0]; d_a=[0.0,0.0]
    nh=na=0.0
    for idx, e in enumerate(el):
        w = w_of(idx)
        if e["ht"] == tid:
            a_h[0]+=e["hs"]*w; a_h[1]+=w; d_h[0]+=e["as"]*w; d_h[1]+=w; nh+=w
        else:
            a_a[0]+=e["as"]*w; a_a[1]+=w; d_a[0]+=e["hs"]*w; d_a[1]+=w; na+=w
    def av(v): return v[0]/v[1] if v[1]>0 else 1.2
    return av(a_h), av(d_h), av(a_a), av(d_a), nh, na

# 初值 (所有队伍, raw单位)
atk_h, def_h, atk_a, def_a, n_h, n_a = {}, {}, {}, {}, {}, {}
for tid in set(team_ev.keys()):
    ah, dh, aa, da, nh, na = raw_side(team_ev[tid], tid)
    atk_h[tid], def_h[tid], atk_a[tid], def_a[tid], n_h[tid], n_a[tid] = ah, dh, aa, da, nh, na

def R(tid, m):
    return m.get(tid, 1.2)

for rnd in range(4):
    n_atk_h, n_def_h, n_atk_a, n_def_a = {}, {}, {}, {}
    for tid in atk_h:
        el = sorted(team_ev.get(tid, []), key=lambda e: e["date"], reverse=True)
        a_h=[0.0,0.0]; d_h=[0.0,0.0]; a_a=[0.0,0.0]; d_a=[0.0,0.0]
        for idx, e in enumerate(el):
            w = w_of(idx); opp = e["at"] if e["ht"]==tid else e["ht"]
            if e["ht"]==tid:
                a_h[0]+=e["hs"]*w; a_h[1]+=R(opp, def_a)*w
                d_h[0]+=e["as"]*w; d_h[1]+=R(opp, atk_a)*w
            else:
                a_a[0]+=e["as"]*w; a_a[1]+=R(opp, def_h)*w
                d_a[0]+=e["hs"]*w; d_a[1]+=R(opp, atk_h)*w
        n_atk_h[tid] = a_h[0]/a_h[1] if a_h[1] else atk_h[tid]
        n_def_h[tid] = d_h[0]/d_h[1] if d_h[1] else def_h[tid]
        n_atk_a[tid] = a_a[0]/a_a[1] if a_a[1] else atk_a[tid]
        n_def_a[tid] = d_a[0]/d_a[1] if d_a[1] else def_a[tid]
    atk_h, def_h, atk_a, def_a = n_atk_h, n_def_h, n_atk_a, n_def_a
    print("round %d: 池均值 %.3f/%.3f/%.3f/%.3f" % (rnd+1,
        sum(atk_h.values())/len(atk_h), sum(def_h.values())/len(def_h),
        sum(atk_a.values())/len(atk_a), sum(def_a.values())/len(def_a)))

# 核心92队输出
for k in v2["stats"]:
    tid = int(k); s = v2["stats"][k]
    s["rat_home_gf"] = round(atk_h[tid],3); s["rat_home_ga"] = round(def_h[tid],3)
    s["rat_away_gf"] = round(atk_a[tid],3); s["rat_away_ga"] = round(def_a[tid],3)
io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", "w", encoding="utf-8").write(json.dumps(v2, ensure_ascii=False, indent=1))
print("\n== 对照 (raw / v2 / rat迭代) ==")
for nm in ["Levski Sofia","AEK Athens","AS Monaco","Benfica","Celtic","Kuopion Palloseura","Inter Club d'Escaldes","Red Bull Salzburg","FK Crvena Zvezda","Górnik Zabrze","FC Nordsjælland","Häcken"]:
    tid = next((int(k) for k, vv in name_of.items() if vv == nm), None)
    if tid is None or str(tid) not in v2["stats"]: continue
    s = v2["stats"][str(tid)]
    print("%-24s 主ga %s/%s/%s  客ga %s/%s/%s | 主gf %s/%s/%s" % (nm,
        s["raw_home_ga"], s["v2_home_ga"], s["rat_home_ga"],
        s["raw_away_ga"], s["v2_away_ga"], s["rat_away_ga"],
        s["raw_home_gf"], s["v2_home_gf"], s["rat_home_gf"]))
