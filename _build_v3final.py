# -*- coding: utf-8 -*-
"""v3 final: 92队统一输出
- covered(55): final = v2
- domestic_merged(31): final = 欧战v2 x 国内v2 融合 (w=min(n,20))
- no_domestic(6): 保留欧战v2 (阿尔巴尼亚2/安道尔/法罗/冰岛 + Riga陈旧)
"""
import pandas as pd, json, io, sys
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
f = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\fixtures.parquet")
f = f[f["is_played"] == True].copy()
f["dt"] = pd.to_datetime(f["date_utc"], errors="coerce")
NOW = pd.Timestamp.now()

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
}
DOM_COEF = {
    25: 0.92, 43: 0.92, 63: 0.88, 50: 0.88, 36: 0.88, 47: 0.88,
    59: 0.85, 44: 0.85, 54: 0.85, 55: 0.82,
    68: 0.78, 71: 0.78, 132: 0.75, 144: 0.75,
    74: 0.72, 134: 0.72, 34: 0.72, 130: 0.68, 138: 0.65, 100000758: 0.55,
}
def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2
def age_w(dt):
    age = (NOW - dt).days
    if age < 400: return 1.0
    if age < 730: return 0.6
    return 0.2

# 联赛场均
lg_avg = {}
for lid in set(DOM_COEF):
    sub = f[f["league_id"] == lid]
    if len(sub) == 0: continue
    lg_avg[lid] = (round(float(sub["goals_home"].mean()), 3), round(float(sub["goals_away"].mean()), 3))

v2 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v2_20260818.json", encoding="utf-8"))
name_of = v2["name_of"]  # bsd_id -> name
bsd_id_of = {vv: int(k) for k, vv in name_of.items()}

# ---- 国内统计(带日期衰减) ----
dom_stats = {}
for bsd_name, (hf_id, dom_lid) in TEAM_MAP.items():
    sub = f[((f["home_team_id"]==hf_id)|(f["away_team_id"]==hf_id)) & (f["league_id"]==dom_lid)]
    sub = sub.sort_values("dt", ascending=False).head(40)
    recent_cnt = int((sub["dt"] > NOW - pd.Timedelta(days=730)).sum())
    if len(sub) == 0 or recent_cnt < 5:
        dom_stats[bsd_name] = {"stale": True, "n_recent": recent_cnt}
        continue
    raw = {"home_gf":[0.0,0.0],"home_ga":[0.0,0.0],"away_gf":[0.0,0.0],"away_ga":[0.0,0.0]}
    nw = {"home":0.0,"away":0.0}
    for idx, (_, r) in enumerate(sub.iterrows()):
        w = w_of(idx) * age_w(r["dt"])
        if r["home_team_id"] == hf_id:
            raw["home_gf"][0] += r["goals_home"]*w; raw["home_gf"][1] += w
            raw["home_ga"][0] += r["goals_away"]*w; raw["home_ga"][1] += w; nw["home"] += w
        else:
            raw["away_gf"][0] += r["goals_away"]*w; raw["away_gf"][1] += w
            raw["away_ga"][0] += r["goals_home"]*w; raw["away_ga"][1] += w; nw["away"] += w
    def avg(v): return round(v[0]/v[1],3) if v[1]>0 else 0.0
    lh, la = lg_avg.get(dom_lid, (1.4,1.2)); coef = DOM_COEF.get(dom_lid, 0.80)
    def shrink(v, n, prior):
        s = n/(n+6.0); return v*s + prior*(1-s)
    dom_stats[bsd_name] = {
        "stale": False, "n_recent": recent_cnt,
        "n_dom_home": round(nw["home"],1), "n_dom_away": round(nw["away"],1),
        "dom_lg_avg": [lh, la], "dom_coef": coef,
        "dom_est_home_gf": round(shrink(avg(raw["home_gf"])/lh*coef, nw["home"], coef),3),
        "dom_est_home_ga": round(shrink(avg(raw["home_ga"])/la*coef, nw["home"], coef),3),
        "dom_est_away_gf": round(shrink(avg(raw["away_gf"])/la*coef, nw["away"], coef),3),
        "dom_est_away_ga": round(shrink(avg(raw["away_ga"])/lh*coef, nw["away"], coef),3),
    }

# ---- 92队统一输出 ----
merged = {}
for bsd_id, s in v2["stats"].items():
    bsd_name = name_of.get(bsd_id)
    ev = s
    out = {"team_id": int(bsd_id), "league": ev.get("league"), "level": ev["level"],
           "euro_home_gf": ev["v2_home_gf"], "euro_home_ga": ev["v2_home_ga"],
           "euro_away_gf": ev["v2_away_gf"], "euro_away_ga": ev["v2_away_ga"],
           "n_euro_home": ev["n_home"], "n_euro_away": ev["n_away"]}
    if bsd_name in dom_stats and not dom_stats[bsd_name]["stale"]:
        dom = dom_stats[bsd_name]; out["src_bias"] = "domestic_merged"
        out.update({k: dom[k] for k in ["n_dom_home","n_dom_away","dom_lg_avg","dom_coef",
                                         "dom_est_home_gf","dom_est_home_ga","dom_est_away_gf","dom_est_away_ga"]})
        for side, ek, dk, nk, nd in [("home_gf","euro_home_gf","dom_est_home_gf","n_euro_home","n_dom_home"),
                                      ("home_ga","euro_home_ga","dom_est_home_ga","n_euro_home","n_dom_home"),
                                      ("away_gf","euro_away_gf","dom_est_away_gf","n_euro_away","n_dom_away"),
                                      ("away_ga","euro_away_ga","dom_est_away_ga","n_euro_away","n_dom_away")]:
            we = min(float(out[nk]), 20.0); wd = min(float(out[nd]), 20.0)
            out["final_"+side] = round((we*out[ek] + wd*out[dk])/(we+wd), 3)
    else:
        out["src_bias"] = "no_domestic" if ev.get("src_bias") == "uncovered" else "covered"
        for side in ["home_gf","home_ga","away_gf","away_ga"]:
            out["final_"+side] = out["euro_"+side]
    merged[bsd_name] = out

n_merged = sum(1 for v in merged.values() if v["src_bias"]=="domestic_merged")
n_nod = sum(1 for v in merged.values() if v["src_bias"]=="no_domestic")
n_cov = sum(1 for v in merged.values() if v["src_bias"]=="covered")
out = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "note": "v3: 92队统一. covered=55(BSD覆盖, final=v2), domestic_merged=%d(HF国内+BSD欧战融合), no_domestic=%d(仅欧战: 阿尔巴尼亚/安道尔/法罗/冰岛+Riga陈旧)" % (n_merged, n_nod),
       "formula": "dom_est=(dom_raw/dom联赛场均)xdom_coef, 收缩K=6; final=(w_euro x euro_v2 + w_dom x dom_est)/(w_euro+w_dom), w=min(n,20); 国内场日期衰减 age<400d=1.0/<730d=0.6/>=730d=0.2, <5场近期判陈旧",
       "dom_coef": DOM_COEF, "league_avg": {str(k): v for k, v in lg_avg.items()},
       "teams": merged}
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json"
io.open(fp, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fp, "| 92 teams: covered=%d merged=%d no_domestic=%d" % (n_cov, n_merged, n_nod))
print("no_domestic:", [k for k, v in merged.items() if v["src_bias"]=="no_domestic"])
print("\n== v3 关键对照 ==")
for nm in ["Red Bull Salzburg","FK Crvena Zvezda","GNK Dinamo Zagreb","Ferencváros TC","Maccabi Tel Aviv","Qarabağ FK","Shamrock Rovers","FC Drita","Riga FC","KF Egnatia","Benfica","Levski Sofia","AS Monaco"]:
    m = merged.get(nm)
    if not m: continue
    print("%-24s %-16s 主攻%s->%s 主防%s->%s 客防%s->%s" % (nm, m["src_bias"],
        m["euro_home_gf"], m["final_home_gf"], m["euro_home_ga"], m["final_home_ga"],
        m["euro_away_ga"], m["final_away_ga"]))
