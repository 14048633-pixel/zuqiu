# -*- coding: utf-8 -*-
"""v3: 国内联赛补齐 (HF soccer-dataset) + 欧战(BSD) 双源融合
- 32/37 未覆盖队有 HF 国内联赛数据, 5 队无(阿尔巴尼亚/安道尔/法罗/冰岛)
- dom_est = (dom_raw / dom_联赛场均) x dom_coef, 收缩K=6向dom_coef
- final = (w_euro x euro_v2 + w_dom x dom_est)/(w_euro+w_dom), w=min(n,20)
"""
import pandas as pd, json, io, sys
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"

# ---- HF 队伍/赛程 ----
f = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\fixtures.parquet")
f = f[f["is_played"] == True].copy()
f["dt"] = pd.to_datetime(f["date_utc"], errors="coerce")

# ---- BSD 名字 -> (HF team_id, HF domestic league_id) ----
TEAM_MAP = {
    "FC Ararat-Armenia": (1892, 144), "FC Drita": (1896, 138), "FC Hradec Králové": (1798, 36),
    "FC Iberia 1999": (1448, 71), "FC Viktoria Plzeň": (1805, 36), "FK Austria Wien": (627, 25),
    "FK Borac Banja Luka": (1418, 68), "FK Crvena Zvezda": (1305, 63), "FK Jablonec": (1800, 36),
    "FK Kauno Žalgiris": (1937, 134), "FK Partizan": (1320, 63), "Ferencváros TC": (1203, 47),
    "GNK Dinamo Zagreb": (1162, 43), "HNK Hajduk Split": (1168, 43), "HNK Rijeka": (1166, 43),
    "Hapoel Be'er Sheva": (1218, 50), "Hapoel Tel Aviv": (1225, 50), "Kairat Almaty": (1885, 132),
    "LASK": (631, 25), "Larne FC": (1849, 130), "Lincoln Red Imps": (1842, 100000758),
    "Maccabi Tel Aviv": (1224, 50), "NK Celje": (1251, 55), "Omonia Nicosia": (1182, 44),
    "Pafos FC": (1185, 44), "Qarabağ FK": (1268, 59), "Red Bull Salzburg": (619, 25),
    "Riga FC": (4738, 74), "SK Rapid Wien": (622, 25), "Sabah FK": (1275, 59),
    "Shamrock Rovers": (900, 34), "ŠK Slovan Bratislava": (1236, 54),
    # 无国内数据 (HF 未覆盖): Dinamo City, KF Egnatia, Inter Club d'Escaldes, Klaksvíkar, Víkingur Reykjavík
}
# ---- 新国内联赛水平系数 (UEFA 系数分级, 与现有表同尺度, 可配置) ----
DOM_COEF = {
    25: 0.92, 43: 0.92, 63: 0.88, 50: 0.88, 36: 0.88, 47: 0.88,  # 奥/克/塞/以/捷/匈
    59: 0.85, 44: 0.85, 54: 0.85, 55: 0.82,                       # 阿塞/塞浦/斯洛伐克/斯洛文尼亚
    68: 0.78, 71: 0.78, 132: 0.75, 144: 0.75,                     # 波黑/格鲁吉亚/哈/亚美尼亚
    74: 0.72, 134: 0.72, 34: 0.72, 130: 0.68, 138: 0.65, 100000758: 0.55,
}

def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2

# ---- 联赛场均 (主客分列, 用 HF 该联赛全部完赛场次) ----
lg_avg = {}
for lid in set(DOM_COEF):
    sub = f[f["league_id"] == lid]
    if len(sub) == 0: continue
    h = (sub["goals_home"] * 1.0).mean(); a = (sub["goals_away"] * 1.0).mean()
    lg_avg[lid] = (round(h, 3), round(a, 3))
print("新联赛场均数:", len(lg_avg), "| 样例:", dict(list(lg_avg.items())[:4]))

# ---- 每队国内统计 ----
v2 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", encoding="utf-8"))
name_of = v2["name_of"]
results = {}
for bsd_name, (hf_id, dom_lid) in TEAM_MAP.items():
    sub = f[((f["home_team_id"] == hf_id) | (f["away_team_id"] == hf_id)) & (f["league_id"] == dom_lid)]
    sub = sub.sort_values("dt", ascending=False).head(40)
    raw = {"home_gf":[0.0,0.0],"home_ga":[0.0,0.0],"away_gf":[0.0,0.0],"away_ga":[0.0,0.0]}
    nw = {"home":0.0,"away":0.0}
    for idx, (_, r) in enumerate(sub.iterrows()):
        w = w_of(idx)
        if r["home_team_id"] == hf_id:
            raw["home_gf"][0] += r["goals_home"]*w; raw["home_gf"][1] += w
            raw["home_ga"][0] += r["goals_away"]*w; raw["home_ga"][1] += w; nw["home"] += w
        else:
            raw["away_gf"][0] += r["goals_away"]*w; raw["away_gf"][1] += w
            raw["away_ga"][0] += r["goals_home"]*w; raw["away_ga"][1] += w; nw["away"] += w
    def avg(v): return round(v[0]/v[1],3) if v[1]>0 else 0.0
    lh, la = lg_avg.get(dom_lid, (1.4, 1.2)); coef = DOM_COEF.get(dom_lid, 0.80)
    def shrink(v, n, prior): 
        s = n/(n+6.0); return v*s + prior*(1-s)
    dom = {
        "dom_raw_home_gf": avg(raw["home_gf"]), "dom_raw_home_ga": avg(raw["home_ga"]),
        "dom_raw_away_gf": avg(raw["away_gf"]), "dom_raw_away_ga": avg(raw["away_ga"]),
        "n_dom_home": round(nw["home"],1), "n_dom_away": round(nw["away"],1),
        "dom_lg_avg": [lh, la], "dom_coef": coef,
        "dom_est_home_gf": round(shrink(avg(raw["home_gf"])/lh*coef, nw["home"], coef),3),
        "dom_est_home_ga": round(shrink(avg(raw["home_ga"])/la*coef, nw["home"], coef),3),
        "dom_est_away_gf": round(shrink(avg(raw["away_gf"])/la*coef, nw["away"], coef),3),
        "dom_est_away_ga": round(shrink(avg(raw["away_ga"])/lh*coef, nw["away"], coef),3),
    }
    results[bsd_name] = dom

# ---- 融合 euro_v2 + dom_est ----
merged = {}
for bsd_name in TEAM_MAP:
    tid = next((k for k, vv in name_of.items() if vv == bsd_name), None)
    if tid is None: continue
    ev = v2["stats"][str(tid)]; dom = results[bsd_name]
    out = {"team_id": int(tid)}
    for side, ek, dk, nk, n2 in [("home_gf","v2_home_gf","dom_est_home_gf","n_home","n_dom_home"),
                                  ("home_ga","v2_home_ga","dom_est_home_ga","n_home","n_dom_home"),
                                  ("away_gf","v2_away_gf","dom_est_away_gf","n_away","n_dom_away"),
                                  ("away_ga","v2_away_ga","dom_est_away_ga","n_away","n_dom_away")]:
        we = min(float(ev[nk]), 20.0); wd = min(dom[n2], 20.0)
        if we + wd == 0: final = ev[ek]
        else: final = (we*ev[ek] + wd*dom[dk]) / (we + wd)
        out["euro_"+side] = ev[ek]; out["dom_est_"+side] = dom[dk]; out["final_"+side] = round(final,3)
    out["n_euro_home"] = ev["n_home"]; out["n_euro_away"] = ev["n_away"]
    out["n_dom_home"] = dom["n_dom_home"]; out["n_dom_away"] = dom["n_dom_away"]
    out["dom_coef"] = dom["dom_coef"]
    out["src_bias"] = "domestic_merged"
    merged[bsd_name] = out

# 无数据 5 队: 保留 euro_v2, 标记 no_domestic
GAPS = ["Dinamo City","KF Egnatia","Inter Club d'Escaldes","Klaksvíkar Ítróttarfelag","Víkingur Reykjavík"]
for nm in GAPS:
    tid = next((k for k, vv in name_of.items() if vv == nm), None)
    if tid is None: continue
    ev = v2["stats"][str(tid)]
    merged[nm] = {"team_id": int(tid),
        "euro_home_gf": ev["v2_home_gf"], "euro_home_ga": ev["v2_home_ga"],
        "euro_away_gf": ev["v2_away_gf"], "euro_away_ga": ev["v2_away_ga"],
        "final_home_gf": ev["v2_home_gf"], "final_home_ga": ev["v2_home_ga"],
        "final_away_gf": ev["v2_away_gf"], "final_away_ga": ev["v2_away_ga"],
        "n_euro_home": ev["n_home"], "n_euro_away": ev["n_away"],
        "src_bias": "no_domestic"}

out = {"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
       "note": "v3 = HF国内联赛(32队) + BSD欧战 融合; 无国内数据5队保留欧战值并标记",
       "team_map": TEAM_MAP, "dom_coef": DOM_COEF, "league_avg": {str(k): v for k, v in lg_avg.items()},
       "teams": merged}
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json"
io.open(fp, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fp, "| teams:", len(merged))

print("\n== v3 融合对照 (euro -> final, 含domestic) ==")
for nm in ["Red Bull Salzburg","FK Crvena Zvezda","GNK Dinamo Zagreb","Ferencváros TC","Maccabi Tel Aviv","FK Austria Wien","Qarabağ FK","Shamrock Rovers","FC Drita","ŠK Slovan Bratislava","Víkingur Reykjavík","KF Egnatia"]:
    m = merged.get(nm)
    if not m: continue
    print("%-24s 主攻 %s->%s | 主防 %s->%s | 客防 %s->%s | %s n_e=%.1f/%.1f n_d=%.1f/%.1f" % (
        nm, m.get("euro_home_gf","-"), m["final_home_gf"], m.get("euro_home_ga","-"), m["final_home_ga"],
        m.get("euro_away_ga","-"), m["final_away_ga"], m["src_bias"],
        m.get("n_euro_home",0), m.get("n_euro_away",0), m.get("n_dom_home",0), m.get("n_dom_away",0)))
