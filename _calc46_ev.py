# -*- coding: utf-8 -*-
"""46场重点联赛 模型λ/EV 独立计算
数据: bsd_team_stats_20260818.json(92队, 本次拉取) + scan_upcoming旧池(17队补充)
公式: 与scan_upcoming一致 (effective_rate收缩 / λ=gf*ga'/avg_atk*home*fatigue / dc_grid / shrink校准)
市场: key46 JSON的BSD共识赔率去水
"""
import sys, io, os, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
from prob_calibration import dc_score_grid, apply_prob_calibration
import scan_upcoming as SU

# ---- 数据 ----
bsd = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_20260818.json", encoding="utf-8"))["stats"]
team_stats, lavg, index = SU.load_team_stats()
# 合并: BSD新数据优先
merged = {}
for k, v in bsd.items():
    merged[k] = {"bsd": v}
for k, v in team_stats.items():
    if k not in merged:
        merged[k] = {}
    merged[k]["old"] = v

def find_team(name):
    if name in merged:
        return merged[name]
    n = "".join(c.lower() for c in name if c.isalnum())
    # 旧池 index 匹配
    for k in merged:
        if "".join(c.lower() for c in k if c.isalnum()) == n:
            return merged[k]
    return None

# ---- 配置 ----
calib = json.load(io.open(ROOT + r"\strategy_data\league_calib.json", encoding="utf-8"))
cc = calib.get("cup_coeffs", {})
CAL_MAP = {
    "欧冠": cc.get("欧冠") or {},
    "欧联": cc.get("欧联杯") or {},
    "欧协联": cc.get("欧协联杯") or {},
    "中超": calib["leagues"].get("中超") or {},
    "西甲": calib["leagues"].get("西甲") or {},
}

def effective_rate(x, avg, n):
    v = x
    low = False
    if n is not None:
        if n < 4:
            v, low = avg, True
        elif n < 8:
            v, low = avg + (v - avg) * 0.7, True
    return v, low

key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))["matches"]
KEY_LG = {"欧冠", "欧联", "欧协联", "中超", "西甲"}
targets = [m for m in scan if m["league"] in KEY_LG]

def bsd_odds_for(r):
    o = r.get("bsd_odds") or {}
    return o

results = []
for t in targets:
    cal = CAL_MAP.get(t["league"]) or {}
    league_avg = cal.get("league_avg", 2.6); home_c = cal.get("home", 1.05)
    away_c = cal.get("away", 0.95); fatigue = cal.get("fatigue", 1.0)
    rho = cal.get("rho", 0.0); shrink = cal.get("shrink", 1.0)
    avg_atk = league_avg / 2.0
    h_rec = find_team(t["home"]); a_rec = find_team(t["away"])
    h_bsd = (h_rec or {}).get("bsd"); a_bsd = (a_rec or {}).get("bsd")
    h_old = (h_rec or {}).get("old"); a_old = (a_rec or {}).get("old")
    src = []
    if h_bsd: src.append("H:BSD"); 
    elif h_old: src.append("H:旧池")
    else: src.append("H:无")
    if a_bsd: src.append("A:BSD")
    elif a_old: src.append("A:旧池")
    else: src.append("A:无")
    if h_bsd:
        hgf, h_low = effective_rate(h_bsd["home_gf"], avg_atk, h_bsd.get("n_home"))
        hga, _ = effective_rate(h_bsd["home_ga"], avg_atk, h_bsd.get("n_home"))
    elif h_old:
        hgf, h_low = effective_rate(h_old["home_gf"], avg_atk, h_old.get("n_home"))
        hga, _ = effective_rate(h_old["home_ga"], avg_atk, h_old.get("n_home"))
    else:
        hgf = hga = None; h_low = False
    if a_bsd:
        agf, a_low = effective_rate(a_bsd["away_gf"], avg_atk, a_bsd.get("n_away"))
        aga, _ = effective_rate(a_bsd["away_ga"], avg_atk, a_bsd.get("n_away"))
    elif a_old:
        agf, a_low = effective_rate(a_old["away_gf"], avg_atk, a_old.get("n_away"))
        aga, _ = effective_rate(a_old["away_ga"], avg_atk, a_old.get("n_away"))
    else:
        agf = aga = None; a_low = False
    if hgf is not None and aga is not None:
        lam_h = max(0.2, min(4.5, hgf * aga / avg_atk * home_c * fatigue))
    else:
        lam_h = None
    if agf is not None and hga is not None:
        lam_a = max(0.2, min(4.5, agf * hga / avg_atk * away_c * fatigue))
    else:
        lam_a = None
    # BSD预测λ (备查)
    k46 = next((x for x in key46 if x["id"] == t["id"]), None)
    bsd_eg = ((k46 or {}).get("bsd_pred") or {}).get("eg") or {}
    row = {"id": t["id"], "league": t["league"], "kickoff": t["kickoff"],
           "home": t["home"], "away": t["away"], "src": "+".join(src),
           "lam": [round(lam_h, 2) if lam_h else None, round(lam_a, 2) if lam_a else None],
           "lam_bsd": [bsd_eg.get("home"), bsd_eg.get("away")],
           "n": [ (h_bsd or h_old or {}).get("n_home"), (a_bsd or a_old or {}).get("n_away") ]}
    if lam_h is not None and lam_a is not None:
        grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
        def P(cond):
            return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
        raw = [P(lambda i, j: i > j), P(lambda i, j: i == j), P(lambda i, j: i < j)]
        calp = apply_prob_calibration(list(raw), shrink=shrink) if shrink != 1.0 else list(raw)
        over25 = P(lambda i, j: i + j > 2.5)
        row["model_1x2"] = [round(x * 100, 1) for x in calp]
        row["model_over25"] = round(over25 * 100, 1)
        nm = ["主胜", "平局", "客胜"]
        mx = max(calp); row["model_dir"] = nm[calp.index(mx)]
        row["model_dir_prob"] = round(mx * 100, 1)
        row["model_ou"] = "大2.5" if over25 > 0.5 else "小2.5"
        row["model_ou_prob"] = round(max(over25, 1 - over25) * 100, 1)
        # EV: 对模型方向腿, 用BSD共识价
        o = bsd_odds_for(k46 or {})
        def ev_for(prob, price, others):
            if not price or prob is None: return None
            orr = 1.0 / price + sum(1.0 / x for x in others if x)
            return round((prob / orr) * price - 1.0, 4)
        hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
        if row["model_dir"] == "主胜" and hw:
            row["ev_1x2"] = ev_for(mx, hw, [dw, aw])
            row["odds_dir"] = hw
        elif row["model_dir"] == "平局" and dw:
            row["ev_1x2"] = ev_for(mx, dw, [hw, aw])
            row["odds_dir"] = dw
        elif row["model_dir"] == "客胜" and aw:
            row["ev_1x2"] = ev_for(mx, aw, [hw, dw])
            row["odds_dir"] = aw
        ov, un = o.get("over_25_goals"), o.get("under_25_goals")
        if ov and un:
            if row["model_ou"] == "大2.5":
                row["ev_ou"] = ev_for(over25, ov, [un])
            else:
                row["ev_ou"] = ev_for(1 - over25, un, [ov])
    results.append(row)

fn = "key46_model_ev_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(results, ensure_ascii=False, indent=1))
print("saved", fn)

print("\n== 46场 模型λ/EV ==")
for r in sorted(results, key=lambda x: x["kickoff"]):
    lam = "%s/%s" % (r["lam"][0], r["lam"][1]) if r["lam"][0] else "—"
    l1 = r.get("model_dir", "—") + (" " + str(r.get("model_dir_prob", "")) + "%") if r.get("model_dir") else "—"
    ev1 = ("%+.1f%%" % (r["ev_1x2"] * 100)) if r.get("ev_1x2") is not None else "—"
    ou = r.get("model_ou", "—") + (" " + str(r.get("model_ou_prob", "")) + "%") if r.get("model_ou") else "—"
    ev2 = ("%+.1f%%" % (r["ev_ou"] * 100)) if r.get("ev_ou") is not None else "—"
    print("%s | %-4s | %-30s | λ %-9s | 1X2 %-12s EV%-8s | OU %-10s EV%-8s | %s" % (
        r["kickoff"], r["league"], r["home"] + "/" + r["away"], lam, l1, ev1, ou, ev2, r["src"]))
