# -*- coding: utf-8 -*-
# 修复锚定: 原地归一每个指标到池均值=1.0
import sys, io, json
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
LEAGUE_COEF = {
    1:1.0,3:1.0,5:1.0,4:1.0,6:1.0,7:1.0,8:1.0,83:1.0,90:1.0,
    10:0.92,2:0.92,14:0.92,11:0.92,13:0.92,15:0.92,24:0.92,9:0.92,
    12:0.85,38:0.85,89:0.85,25:0.85,17:0.85,19:0.85,20:0.85,18:0.85,
    85:0.85,34:0.85,84:0.85,54:0.85,26:0.85,32:0.85,33:0.85,49:0.85,
    52:0.80,50:0.80,80:0.75,86:0.80,87:0.75,55:0.70,23:0.72,22:0.70,
    88:0.70,82:0.60,47:0.60,53:0.60,28:0.55,70:0.50,
    42:0.95,41:0.95,39:0.95,43:0.95,44:0.95,40:0.95,
    35:0.90,81:0.75,56:0.70,46:0.80,51:0.80,
    27:0.85,58:0.85,60:0.85,61:0.85,62:0.85,63:0.85,64:0.85,65:0.85,66:0.85,67:0.85,68:0.85,69:0.85,
    29:0.80,30:0.80,
}
EURO_IDS = {7, 8, 83, 90}
def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2
b = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_edges_20260818.json", encoding="utf-8"))
v2 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", encoding="utf-8"))
edges = b["edges"]; name_of = v2["name_of"]
core = {int(k) for k in v2["stats"]}
dom = {}
for e in edges:
    for t in (e["ht"], e["at"]):
        dom.setdefault(t, {})
        dom[t][e["lid"]] = dom[t].get(e["lid"], 0) + 1
dom_league = {t: max(c, key=c.get) for t, c in dom.items()}
covered_lg = {L for L in LEAGUE_COEF if L not in EURO_IDS}
def lvl(tid):
    L = dom_league.get(tid)
    if L in EURO_IDS: return 1.0
    return LEAGUE_COEF.get(L, 0.85)
atk_h = {int(k): s["v2_home_gf"] for k, s in v2["stats"].items()}
def_h = {int(k): s["v2_home_ga"] for k, s in v2["stats"].items()}
atk_a = {int(k): s["v2_away_gf"] for k, s in v2["stats"].items()}
def_a = {int(k): s["v2_away_ga"] for k, s in v2["stats"].items()}
def R(tid, m):
    return m[tid] if tid in core else lvl(tid)
team_ev = defaultdict(list)
for e in edges:
    team_ev[e["ht"]].append(e); team_ev[e["at"]].append(e)
for rnd in range(3):
    n_atk_h, n_def_h, n_atk_a, n_def_a = {}, {}, {}, {}
    for tid in core:
        el = sorted(team_ev.get(tid, []), key=lambda e: e["date"], reverse=True)
        a_h=[0.0,0.0]; d_h=[0.0,0.0]; a_a=[0.0,0.0]; d_a=[0.0,0.0]
        for idx, e in enumerate(el):
            w = w_of(idx)
            opp = e["at"] if e["ht"] == tid else e["ht"]
            if e["ht"] == tid:
                a_h[0] += e["hs"]*R(opp, def_a)*w; a_h[1] += R(opp, def_a)*w
                d_h[0] += e["as"]*R(opp, atk_a)*w; d_h[1] += R(opp, atk_a)*w
            else:
                a_a[0] += e["as"]*R(opp, def_h)*w; a_a[1] += R(opp, def_h)*w
                d_a[0] += e["hs"]*R(opp, atk_h)*w; d_a[1] += R(opp, atk_h)*w
        n_atk_h[tid] = a_h[0]/a_h[1] if a_h[1] else lvl(tid)
        n_def_h[tid] = d_h[0]/d_h[1] if d_h[1] else lvl(tid)
        n_atk_a[tid] = a_a[0]/a_a[1] if a_a[1] else lvl(tid)
        n_def_a[tid] = d_a[0]/d_a[1] if d_a[1] else lvl(tid)
    # 原地锚定
    for m in (n_atk_h, n_def_h, n_atk_a, n_def_a):
        mean = sum(m.values())/len(m)
        for t in m: m[t] /= mean
    atk_h, def_h, atk_a, def_a = n_atk_h, n_def_h, n_atk_a, n_def_a
    print("round %d: 均值 %.3f/%.3f/%.3f/%.3f" % (rnd+1, sum(atk_h.values())/len(atk_h), sum(def_h.values())/len(def_h), sum(atk_a.values())/len(atk_a), sum(def_a.values())/len(def_a)))
for k, s in v2["stats"].items():
    tid = int(k)
    s["v2i_home_gf"] = round(atk_h[tid], 3); s["v2i_home_ga"] = round(def_h[tid], 3)
    s["v2i_away_gf"] = round(atk_a[tid], 3); s["v2i_away_ga"] = round(def_a[tid], 3)
    L = dom_league.get(tid)
    s["src_bias"] = "uncovered" if (L in EURO_IDS or L not in covered_lg) else "covered"
v2["v2i_note"] = "3轮迭代(对手攻防加权, 全局均值锚定1.0); 实验性质"
io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", "w", encoding="utf-8").write(json.dumps(v2, ensure_ascii=False, indent=1))
print("\n== 对照 (raw/v2/v2i) ==")
for nm in ["Levski Sofia","AEK Athens","AS Monaco","Benfica","Celtic","Kuopion Palloseura","Inter Club d'Escaldes","Red Bull Salzburg","FK Crvena Zvezda","Górnik Zabrze"]:
    tid = next((int(k) for k, vv in name_of.items() if vv == nm), None)
    if tid is None or str(tid) not in v2["stats"]: continue
    s = v2["stats"][str(tid)]
    print("%-24s 主ga %s/%s/%s  客ga %s/%s/%s  %s lvl=%s" % (nm, s["raw_home_ga"], s["v2_home_ga"], s["v2i_home_ga"], s["raw_away_ga"], s["v2_away_ga"], s["v2i_away_ga"], s["src_bias"], s["level"]))
