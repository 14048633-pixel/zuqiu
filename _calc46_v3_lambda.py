# -*- coding: utf-8 -*-
"""46场 v3 λ 验证: 用 v3 final_* (对手强度归一后) 重算 λ/概率/EV, 对照原模型EV
公式: λ_H = final_home_gf × final_away_ga × avg_atk × home_c × fatigue  (final已含水平+收缩)
"""
import sys, io, os, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
from prob_calibration import dc_score_grid, apply_prob_calibration

# ---- 数据 ----
v3 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json", encoding="utf-8"))["teams"]
key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
model_ev = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
mev_by = {r["id"]: r for r in model_ev}
# 名字归一
def norm(n):
    return "".join(c.lower() for c in n if c.isalnum())
v3_norm = {norm(k): v for k, v in v3.items()}
def find(name):
    if name in v3: return v3[name]
    return v3_norm.get(norm(name))

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

def ev_for(prob, price, others):
    if not price or prob is None: return None
    orr = 1.0/price + sum(1.0/x for x in others if x)
    return round((prob/orr)*price - 1.0, 4)

missing = []
out = []
for t in key46:
    cal = CAL_MAP.get(t["league"]) or {}
    league_avg = cal.get("league_avg", 2.7); home_c = cal.get("home", 1.05)
    away_c = cal.get("away", 0.95); fatigue = cal.get("fatigue", 1.0)
    rho = cal.get("rho", 0.0); shrink = cal.get("shrink", 1.0)
    avg_atk = league_avg / 2.0
    h = find(t["home"]); a = find(t["away"])
    row = {"id": t["id"], "league": t["league"], "kickoff": t["kickoff"],
           "home": t["home"], "away": t["away"]}
    if h is None: missing.append(t["home"])
    if a is None: missing.append(t["away"])
    if h is None or a is None:
        row["lam"] = [None, None]; row["note"] = "缺v3数据"; out.append(row); continue
    lam_h = max(0.2, min(4.5, h["final_home_gf"] * a["final_away_ga"] * avg_atk * home_c * fatigue))
    lam_a = max(0.2, min(4.5, a["final_away_gf"] * h["final_home_ga"] * avg_atk * away_c * fatigue))
    row["lam"] = [round(lam_h,2), round(lam_a,2)]
    row["src_bias"] = "%s/%s" % (h["src_bias"], a["src_bias"])
    row["final_home_gf"] = h["final_home_gf"]; row["final_away_ga"] = a["final_away_ga"]
    row["final_away_gf"] = a["final_away_gf"]; row["final_home_ga"] = h["final_home_ga"]
    grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
    def P(cond): return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    raw = [P(lambda i,j: i>j), P(lambda i,j: i==j), P(lambda i,j: i<j)]
    calp = apply_prob_calibration(list(raw), shrink=shrink) if shrink != 1.0 else list(raw)
    over25 = P(lambda i,j: i+j > 2.5)
    row["model_1x2"] = [round(x*100,1) for x in calp]
    row["model_over25"] = round(over25*100,1)
    nm = ["主胜","平局","客胜"]
    mx = max(calp); row["model_dir"] = nm[calp.index(mx)]
    row["model_dir_prob"] = round(mx*100,1)
    row["model_ou"] = "大2.5" if over25 > 0.5 else "小2.5"
    row["model_ou_prob"] = round(max(over25, 1-over25)*100, 1)
    o = t.get("bsd_odds") or {}
    hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
    if row["model_dir"]=="主胜" and hw: row["ev_1x2"] = ev_for(mx, hw, [dw, aw]); row["odds_dir"]=hw
    elif row["model_dir"]=="平局" and dw: row["ev_1x2"] = ev_for(mx, dw, [hw, aw]); row["odds_dir"]=dw
    elif row["model_dir"]=="客胜" and aw: row["ev_1x2"] = ev_for(mx, aw, [hw, dw]); row["odds_dir"]=aw
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if ov and un:
        if row["model_ou"]=="大2.5": row["ev_ou"] = ev_for(over25, ov, [un])
        else: row["ev_ou"] = ev_for(1-over25, un, [ov])
    old = mev_by.get(t["id"]) or {}
    row["old_lam"] = old.get("lam"); row["old_dir"] = old.get("model_dir")
    row["old_ev_1x2"] = old.get("ev_1x2"); row["old_ev_ou"] = old.get("ev_ou")
    row["old_dir_prob"] = old.get("model_dir_prob"); row["old_ou"] = old.get("model_ou")
    out.append(row)

fn = "key46_v3_lambda_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fn, "| missing:", set(missing) or "无")

# ---- 汇总 ----
pos_old = pos_new = 0
flip = []
for r in out:
    if r.get("old_ev_1x2") and r["old_ev_1x2"] > 0.05: pos_old += 1
    if r.get("ev_1x2") and r["ev_1x2"] > 0.05: pos_new += 1
    if r.get("old_dir") and r.get("model_dir") and r["old_dir"] != r["model_dir"]:
        flip.append((r["kickoff"], r["home"]+"/"+r["away"], r["old_dir"], r["model_dir"], r["old_ev_1x2"], r["ev_1x2"]))
print("\n1X2 EV>5%%: 旧模型 %d 场 -> v3 %d 场" % (pos_old, pos_new))
print("\n== 方向翻转 (旧->v3) %d 场 ==" % len(flip))
for f in flip:
    print("  %s %-30s %s(ev%s) -> %s(ev%s)" % (f[0], f[1], f[2], f[4], f[3], f[5]))
print("\n== 46场 v3 λ/方向/EV ==")
for r in sorted(out, key=lambda x: x["kickoff"]):
    lam = "%s/%s" % (r["lam"][0], r["lam"][1]) if r["lam"][0] else "—"
    d1 = r.get("model_dir","—") + (" %.0f%%" % r["model_dir_prob"]) if r.get("model_dir") else "—"
    e1 = ("%+.1f%%" % (r["ev_1x2"]*100)) if r.get("ev_1x2") is not None else "—"
    ou = r.get("model_ou","—") + (" %.0f%%" % r["model_ou_prob"]) if r.get("model_ou") else "—"
    e2 = ("%+.1f%%" % (r["ev_ou"]*100)) if r.get("ev_ou") is not None else "—"
    chg = ""
    if r.get("old_dir") and r.get("model_dir") and r["old_dir"] != r["model_dir"]: chg = " ⚠翻转"
    print("%s | %-4s | %-30s | λ %-9s | %-14s EV%-8s | %-12s EV%-8s | %s%s" % (
        r["kickoff"], r["league"], r["home"]+"/"+r["away"], lam, d1, e1, ou, e2, r["src_bias"], chg))
