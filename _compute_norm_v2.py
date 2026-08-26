# -*- coding: utf-8 -*-
"""v2 计算: 从边表 -> 联赛上下文 -> level归一+收缩 (v2) 与 迭代对手强度 (v2i) 对照"""
import sys, io, json
from datetime import datetime, timezone
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
def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2
def age_w(dtstr):
    try:
        d = datetime.fromisoformat(dtstr.replace("Z", "+00:00"))
    except Exception:
        return 0.2
    age = (datetime.now(timezone.utc) - d).days
    if age < 180: return 1.0
    if age < 365: return 0.7
    if age < 730: return 0.4
    return 0.2

# ---- 载入 ----
b = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_edges_20260818.json", encoding="utf-8"))
edges = b["edges"]
te_map = b.get("team_edges", {})
print("edges:", len(edges))

# 全部队伍 -> 主导联赛
dom = {}
for e in edges:
    for t in (e["ht"], e["at"]):
        dom[t] = dom.get(t, {})
        dom[t][e["lid"]] = dom[t].get(e["lid"], 0) + 1
dom_league = {t: max(c, key=c.get) for t, c in dom.items()}
def lvl(tid):
    return LEAGUE_COEF.get(dom_league.get(tid), 0.85)

# ---- 联赛上下文 (按日期衰减) ----
lg = {}
for e in edges:
    L = e["lid"]; w = age_w(e["date"])
    d = lg.setdefault(L, {"hgf":[0.0,0.0],"agf":[0.0,0.0],"n":0})
    d["hgf"][0] += e["hs"]*w; d["hgf"][1] += w
    d["agf"][0] += e["as"]*w; d["agf"][1] += w
    d["n"] += 1
lg_avg = {}
for L, d in lg.items():
    h = d["hgf"][0]/d["hgf"][1] if d["hgf"][1] else 1.4
    a = d["agf"][0]/d["agf"][1] if d["agf"][1] else 1.2
    if d["n"] < 10:  # 小样本回退: 用水平系数估计
        c = LEAGUE_COEF.get(L, 0.85)
        h = 1.42*c; a = 1.18*c
    lg_avg[L] = (round(h,3), round(a,3))
print("联赛上下文数:", len(lg_avg))

# ---- 队伍 raw (按队内rank时间衰减) ----
def team_raw(edges_list):
    edges_list = sorted(edges_list, key=lambda e: e["date"], reverse=True)
    r = {"home_gf":[0.0,0.0],"home_ga":[0.0,0.0],"away_gf":[0.0,0.0],"away_ga":[0.0,0.0]}
    n = {"home":0.0,"away":0.0}
    for idx, e in enumerate(edges_list):
        w = w_of(idx)
        if e["ht"] == tid or True:
            pass
    return r, n

stats = {}
for tid_str, eid_list in te_map.items():
    tid = int(tid_str)
    el = [e for e in edges if e["id"] in {x["id"] for x in eid_list}]
    el = sorted(el, key=lambda e: e["date"], reverse=True)
    raw = {"home_gf":[0.0,0.0],"home_ga":[0.0,0.0],"away_gf":[0.0,0.0],"away_ga":[0.0,0.0]}
    nw = {"home":0.0,"away":0.0}
    for idx, e in enumerate(el):
        w = w_of(idx)
        if e["ht"] == tid:
            raw["home_gf"][0] += e["hs"]*w; raw["home_gf"][1] += w; nw["home"] += w
            raw["home_ga"][0] += e["as"]*w; raw["home_ga"][1] += w
        else:
            raw["away_gf"][0] += e["as"]*w; raw["away_gf"][1] += w; nw["away"] += w
            raw["away_ga"][0] += e["hs"]*w; raw["away_ga"][1] += w
    def avg(v): return round(v[0]/v[1],3) if v[1] > 0 else 0.0
    own_lg = dom_league.get(tid, 0)
    lvl_own = LEAGUE_COEF.get(own_lg, 0.85)
    Lh, La = lg_avg.get(own_lg, (1.42*lvl_own, 1.18*lvl_own))
    # v2: 相对本联赛均值 x 水平
    a_h = avg(raw["home_gf"])/Lh*lvl_own if avg(raw["home_gf"])>0 else lvl_own
    d_h = avg(raw["home_ga"])/La*lvl_own if avg(raw["home_ga"])>0 else lvl_own
    a_a = avg(raw["away_gf"])/La*lvl_own if avg(raw["away_gf"])>0 else lvl_own
    d_a = avg(raw["away_ga"])/Lh*lvl_own if avg(raw["away_ga"])>0 else lvl_own
    def shrink(v, n, prior):
        s = n/(n+6.0)
        return v*s + prior*(1-s)
    stats[tid] = {
        "raw_home_gf": avg(raw["home_gf"]), "raw_home_ga": avg(raw["home_ga"]),
        "raw_away_gf": avg(raw["away_gf"]), "raw_away_ga": avg(raw["away_ga"]),
        "n_home": round(nw["home"],1), "n_away": round(nw["away"],1),
        "own_league_id": own_lg, "level": lvl_own,
        "v2_home_gf": round(shrink(a_h, nw["home"], lvl_own),3),
        "v2_home_ga": round(shrink(d_h, nw["home"], lvl_own),3),
        "v2_away_gf": round(shrink(a_a, nw["away"], lvl_own),3),
        "v2_away_ga": round(shrink(d_a, nw["away"], lvl_own),3),
    }
# 名字映射 (从edges取队名 -> 由fetch脚本没存名字, 用scan对照)
scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
name_of = {}
for m in scan["matches"]:
    if m.get("home_id"): name_of[m["home_id"]] = m["home"]
    if m.get("away_id"): name_of[m["away_id"]] = m["away"]

print("\n== v2 关键球队对照 ==")
for nm in ["Levski Sofia","AEK Athens","AS Monaco","Kuopion Palloseura","FC Nordsjælland","CSKA Sofia","Benfica","Celtic","Red Bull Salzburg","Górnik Zabrze"]:
    tid = next((k for k,v in name_of.items() if v==nm), None)
    if tid is None or tid not in stats: continue
    s = stats[tid]
    print("%-22s raw主 %s/%s v2主 %s/%s | raw客 %s/%s v2客 %s/%s lvl=%s n=%s/%s" % (
        nm, s["raw_home_gf"], s["raw_home_ga"], s["v2_home_gf"], s["v2_home_ga"],
        s["raw_away_gf"], s["raw_away_ga"], s["v2_away_gf"], s["v2_away_ga"],
        s["level"], s["n_home"], s["n_away"]))

# ---- 联赛水平均值验证 ----
print("\n== 各联赛 v2 攻击均值 vs 水平系数 ==")
from collections import defaultdict
agg = defaultdict(lambda: [0.0,0.0,0])
for tid, s in stats.items():
    L = s["own_league_id"]
    agg[L][0] += s["v2_home_gf"]; agg[L][1] += s["v2_home_ga"]; agg[L][2] += 1
for L in sorted(agg, key=lambda x: -LEAGUE_COEF.get(x,0.85)):
    a, d, n = agg[L]
    if n >= 1:
        print("  lid=%s coef=%.2f n=%d  mean_atk_home=%.3f mean_def_home=%.3f" % (L, LEAGUE_COEF.get(L,0.85), n, a/n, d/n))

out = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "formula": "v2 = 相对本联赛均值(主客分列) x 联赛水平coef, 样本收缩K=6向水平系数; raw保留",
       "stats": {str(k): v for k, v in stats.items()},
       "league_context": lg_avg,
       "name_of": {str(k): v for k, v in name_of.items()}}
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json"
io.open(fp, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("\nsaved", fp, "| teams:", len(stats))
