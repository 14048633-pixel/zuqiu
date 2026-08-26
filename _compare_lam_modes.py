# -*- coding: utf-8 -*-
import sys, io, os, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
from prob_calibration import dc_score_grid, apply_prob_calibration

v3 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json", encoding="utf-8"))["teams"]
key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
calib = json.load(io.open(ROOT + r"\strategy_data\league_calib.json", encoding="utf-8"))
cc = calib.get("cup_coeffs", {})
CAL_MAP = {"欧冠": cc.get("欧冠") or {}, "欧联": cc.get("欧联杯") or {}, "欧协联": cc.get("欧协联杯") or {},
           "中超": calib["leagues"].get("中超") or {}, "西甲": calib["leagues"].get("西甲") or {}}
def norm(n): return "".join(c.lower() for c in n if c.isalnum())
v3_norm = {norm(k): v for k, v in v3.items()}
def find(n): return v3.get(n) or v3_norm.get(norm(n))
def ev_for(p, price, others):
    if not price or p is None: return None
    orr = 1.0/price + sum(1.0/x for x in others if x)
    return round((p/orr)*price - 1.0, 4)

def run(mode):
    rows = []
    for t in key46:
        cal = CAL_MAP.get(t["league"]) or {}
        lg = cal.get("league_avg", 2.7); hc = cal.get("home", 1.05); ac = cal.get("away", 0.95)
        ft = cal.get("fatigue", 1.0); rho = cal.get("rho", 0.0); shr = cal.get("shrink", 1.0)
        avg = lg/2.0
        h = find(t["home"]); a = find(t["away"])
        if not h or not a: rows.append({"dir": None, "ev": None}); continue
        def val(team, k):
            if mode == "euro" and team.get("src_bias") == "domestic_merged":
                return team["euro_"+k[6:]]
            return team["final_"+k[6:]]
        lam_h = max(0.2, min(4.5, val(h,"final_home_gf")*val(a,"final_away_ga")*avg*hc*ft))
        lam_a = max(0.2, min(4.5, val(a,"final_away_gf")*val(h,"final_home_ga")*avg*ac*ft))
        g = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
        def P(c): return sum(g[i][j] for i in range(9) for j in range(9) if c(i,j))
        raw = [P(lambda i,j:i>j), P(lambda i,j:i==j), P(lambda i,j:i<j)]
        cp = apply_prob_calibration(list(raw), shrink=shr) if shr != 1.0 else list(raw)
        ov = P(lambda i,j:i+j>2.5)
        nm = ["主胜","平局","客胜"]; mx = max(cp); d = nm[cp.index(mx)]
        o = t.get("bsd_odds") or {}; hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
        ev = ev_for(mx, {"主胜":hw,"平局":dw,"客胜":aw}.get(d), [x for k,x in {"主胜":hw,"平局":dw,"客胜":aw}.items() if k!=d])
        ou_ev = None
        ov2, un = o.get("over_25_goals"), o.get("under_25_goals")
        if ov2 and un:
            ou_ev = ev_for(ov, ov2, [un]) if ov>0.5 else ev_for(1-ov, un, [ov2])
        rows.append({"dir": d, "ev": ev, "ou_ev": ou_ev, "lam":[round(lam_h,2),round(lam_a,2)],
                     "market": (hw,dw,aw), "home": t["home"], "away": t["away"], "kickoff": t["kickoff"]})
    return rows

for mode in ["final", "euro"]:
    rows = run(mode)
    pos = sum(1 for r in rows if r["ev"] and r["ev"] > 0.05)
    ext = sum(1 for r in rows if r["ev"] and r["ev"] > 0.5)
    ou_pos = sum(1 for r in rows if r["ou_ev"] and r["ou_ev"] > 0.05)
    print("%-6s | 1X2 EV>5%%: %2d | EV>50%%: %2d | OU EV>5%%: %2d" % (mode, pos, ext, ou_pos))
print("\n== 两模式方向/EV 差异大场次 ==")
for rf, re_ in zip(run("final"), run("euro")):
    if rf["ev"] and (abs(rf["ev"]) > 0.5 or rf["dir"] != re_["dir"]):
        mkt = rf["market"]
        print("%-44s 市场%s/%s/%s | final %s(ev%+.1f%%) | euro %s(ev%+.1f%%)" % (
            rf["home"]+"/"+rf["away"], mkt[0], mkt[1], mkt[2],
            rf["dir"], rf["ev"]*100, re_["dir"], (re_["ev"] or 0)*100))
