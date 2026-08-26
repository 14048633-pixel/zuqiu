# -*- coding: utf-8 -*-
"""46场重点联赛 EV v2: 用BSD dc-blend expected_goals 做主λ (已对手强度归一)
我们攻防模型λ仅作交叉验证(偏差>0.5标独立观点)
"""
import sys, io, os, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
from prob_calibration import dc_score_grid, apply_prob_calibration

calib = json.load(io.open(ROOT + r"\strategy_data\league_calib.json", encoding="utf-8"))
cc = calib.get("cup_coeffs", {})
CAL_MAP = {
    "欧冠": cc.get("欧冠") or {},
    "欧联": cc.get("欧联杯") or {},
    "欧协联": cc.get("欧协联杯") or {},
    "中超": calib["leagues"].get("中超") or {},
    "西甲": calib["leagues"].get("西甲") or {},
}

key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
model = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
m_by_id = {r["id"]: r for r in model}

def bsd_odds_for(r):
    return r.get("bsd_odds") or {}

def ev_for(prob, price, others):
    if not price or prob is None:
        return None
    orr = 1.0 / price + sum(1.0 / x for x in others if x)
    return round((prob / orr) * price - 1.0, 4)

out = []
for r in key46:
    t = {"league": r["league"], "kickoff": r["kickoff"], "home": r["home"], "away": r["away"], "id": r["id"]}
    cal = CAL_MAP.get(r["league"]) or {}
    rho = cal.get("rho", 0.0); shrink = cal.get("shrink", 1.0)
    eg = ((r.get("bsd_pred") or {}).get("eg") or {})
    lam_h, lam_a = eg.get("home"), eg.get("away")
    row = dict(t)
    if lam_h is None or lam_a is None:
        row["note"] = "无BSD eg"
        out.append(row); continue
    grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
    def P(cond):
        return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    raw = [P(lambda i, j: i > j), P(lambda i, j: i == j), P(lambda i, j: i < j)]
    calp = apply_prob_calibration(list(raw), shrink=shrink) if shrink != 1.0 else list(raw)
    over25 = P(lambda i, j: i + j > 2.5)
    row["lam"] = [round(lam_h, 2), round(lam_a, 2)]
    row["model_1x2"] = [round(x * 100, 1) for x in calp]
    nm = ["主胜", "平局", "客胜"]
    mx = max(calp); row["model_dir"] = nm[calp.index(mx)]; row["model_dir_prob"] = round(mx * 100, 1)
    row["model_ou"] = "大2.5" if over25 > 0.5 else "小2.5"; row["model_ou_prob"] = round(max(over25, 1 - over25) * 100, 1)
    o = bsd_odds_for(r)
    hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
    if row["model_dir"] == "主胜" and hw:
        row["ev_1x2"] = ev_for(mx, hw, [dw, aw]); row["odds_dir"] = hw
    elif row["model_dir"] == "平局" and dw:
        row["ev_1x2"] = ev_for(mx, dw, [hw, aw]); row["odds_dir"] = dw
    elif row["model_dir"] == "客胜" and aw:
        row["ev_1x2"] = ev_for(mx, aw, [hw, dw]); row["odds_dir"] = aw
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if ov and un:
        if row["model_ou"] == "大2.5":
            row["ev_ou"] = ev_for(over25, ov, [un])
        else:
            row["ev_ou"] = ev_for(1 - over25, un, [ov])
    # 我们模型λ交叉验证
    mr = m_by_id.get(r["id"]) or {}
    our = mr.get("lam") or [None, None]
    dev = None
    if our[0] and our[1]:
        dev = max(abs(our[0] - lam_h), abs(our[1] - lam_a))
    row["our_lam"] = our
    row["lam_dev"] = round(dev, 2) if dev is not None else None
    row["independent"] = bool(dev is not None and dev > 0.5)
    out.append(row)

fn = "key46_ev_v2_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fn)

print("\n== 46场 EV v2 (λ=BSD eg, 我们λ交叉) ==")
for r in sorted(out, key=lambda x: x["kickoff"]):
    e1 = ("%+.1f%%" % (r["ev_1x2"] * 100)) if r.get("ev_1x2") is not None else "—"
    e2 = ("%+.1f%%" % (r["ev_ou"] * 100)) if r.get("ev_ou") is not None else "—"
    ind = " ⚠独立观点" if r.get("independent") else ""
    print("%s | %-4s | %-30s | λ %s/%s | 1X2 %s %s%% EV%s | OU %s %s%% EV%s | dev%.2f%s" % (
        r["kickoff"], r["league"], r["home"] + "/" + r["away"],
        r["lam"][0], r["lam"][1], r["model_dir"], r["model_dir_prob"], e1,
        r["model_ou"], r["model_ou_prob"], e2, r.get("lam_dev") or 0, ind))
