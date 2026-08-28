# -*- coding: utf-8 -*-
"""中超(CSL)即将开赛批量扫描 v1
数据源: strategy_data/csl_odds_tonight_<date>.json (the-odds-api多机构快照)
        strategy_data/csl_odds_zones.json (2026主客攻防 + 真值区间)
        strategy_data/league_calib.json (分联赛泊松校准, 第五类)
模型:   calc_lambdas(主客攻防标准化) + dc_score_grid(Dixon-Coles比分网格)
EV:     各市场独立Overround去水 (1X2/亚盘/大小球分别取最低抽水机构)
输出:   完整链条 Step0.5数据提取 -> Step7.5风险信号 -> Step8模型 -> Step30战术 -> Step31 EV打星
"""
import glob, json, io, os, re, sys
from datetime import datetime, timezone, timedelta

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
sys.stdout.reconfigure(encoding="utf-8")

from poisson_lambda import calc_lambdas
from prob_calibration import dc_score_grid

# ===== 盘口时效阈值(复盘中超统一规则): 过期/隔日快照一律否决 =====
SNAPSHOT_STALE_HOURS = float(os.environ.get("ODDS_SNAPSHOT_STALE_HOURS", "12") or 12)

# ===== 第一类: EV分层阈值(与批量扫描一致) =====
EV_TIER_BATCH = 0.05
EV_TIER_INTEL = 0.08
ODDS_FLOOR = 1.40
EV_TIERS = [("高价值", 0.20, 1.0), ("标准", 0.08, 0.7), ("观察", 0.05, 0.3), ("垃圾", 0.0, 0.0)]
HAS_INTEL = False  # 无伤停/轮换情报批量扫描

# ===== 队名映射: 盘口英文官方名 -> 数据源中文标准名(与 csl_results_2026 / baseline 唯一匹配) =====
CN_MAP = {
    "Liaoning Tieren FC": "辽宁铁人",
    "Shenzhen Peng City FC": "深圳新鹏城",
    "Tianjin Jinmen Tiger FC": "天津津门虎",
    "Beijing FC": "北京国安",
    "Zhejiang": "浙江队",
    "Chengdu Rongcheng FC": "成都蓉城",
    "Yunnan Yukun": "云南玉昆",
    "Dalian Yingbo": "大连英博",
    "Shanghai Shenhua FC": "上海申花",
    "Henan FC": "河南队",
    "Shanghai Port": "上海海港",
    "Shandong Taishan": "山东泰山",
    "Wuhan Three Towns": "武汉三镇",
    "Qingdao West Coast": "青岛西海岸",
    "Qingdao Hainiu": "青岛海牛",
    "Chongqing Tonglianglong": "重庆铜梁龙",
}

def _load_cal():
    p = os.path.join(ROOT, "strategy_data", "league_calib.json")
    try:
        d = json.load(io.open(p, encoding="utf-8")).get("leagues", {})
        return d.get("中超")
    except Exception:
        return None

CAL = _load_cal() or {
    "league_avg": 3.035, "rho": -0.04, "shrink": 0.8,
    "home": 1.13, "away": 0.93, "fatigue": 1.0,
}

def load_odds(path):
    d = json.load(io.open(path, encoding="utf-8"))
    return [m for m in d if m["commence_time"] >= "2026-08-15T00:00:00Z"]

def load_att_def():
    """从 csl_odds_zones.baseline_2026_ytd_web.home_away_split_verified 解析16队主客攻防."""
    zones = json.load(io.open(os.path.join(ROOT, "strategy_data", "csl_odds_zones.json"), encoding="utf-8"))
    rows = zones["baseline_2026_ytd_web"]["home_away_split_verified"]["teams"]
    out = {}
    for name, hs, as_ in rows:
        def _p(s):
            m = re.match(r"(主|客)\((\d+)场(\d+)分(\d+)-(\d+)-(\d+),(\d+):(\d+)\)", s)
            n = int(m.group(2))
            return {"n": n, "gf": int(m.group(7)) / n, "ga": int(m.group(8)) / n}
        out[name] = {"home": _p(hs), "away": _p(as_)}
    return out, zones

def extract_markets(m):
    h2h = sp = tt = None
    for b in m["bookmakers"]:
        for mk in b["markets"]:
            key = mk["key"]
            if key == "h2h":
                prices = {}
                for o in mk["outcomes"]:
                    if o["name"] == "Draw":
                        prices["draw"] = float(o["price"])
                    elif o["name"] == m["home"]:
                        prices["home"] = float(o["price"])
                    elif o["name"] == m["away"]:
                        prices["away"] = float(o["price"])
                if len(prices) == 3:
                    orr = sum(1.0 / v for v in prices.values())
                    if h2h is None or orr < h2h[0]:
                        h2h = (orr, prices, b["key"])
            elif key == "spreads":
                prices, line = {}, None
                for o in mk["outcomes"]:
                    if o["name"] == m["home"]:
                        prices["home"] = float(o["price"]); line = float(o["point"])
                    elif o["name"] == m["away"]:
                        prices["away"] = float(o["price"])
                if line is not None and len(prices) == 2:
                    orr = 1.0 / prices["home"] + 1.0 / prices["away"]
                    cand = (abs(abs(line) - 0.5), orr, line, prices, b["key"])
                    if sp is None or (cand[0], cand[1]) < (sp[0], sp[1]):
                        sp = cand
            elif key == "totals":
                prices, line = {}, None
                for o in mk["outcomes"]:
                    if o["name"] == "Over":
                        prices["over"] = float(o["price"]); line = float(o["point"])
                    elif o["name"] == "Under":
                        prices["under"] = float(o["price"])
                if line is not None and len(prices) == 2:
                    orr = 1.0 / prices["over"] + 1.0 / prices["under"]
                    cand = (abs(line - 2.5), orr, line, prices, b["key"])
                    if tt is None or (cand[0], cand[1]) < (tt[0], tt[1]):
                        tt = cand
    return h2h, sp, tt

def probs_from_grid(grid, hdp=None, tt_line=None):
    P = lambda cond: sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    w = P(lambda i, j: i > j); d = P(lambda i, j: i == j); l = P(lambda i, j: i < j)
    out = {"w": w, "d": d, "l": l}
    if tt_line is not None:
        if abs(tt_line - round(tt_line)) < 0.01:
            push = P(lambda i, j: abs(i + j - tt_line) < 0.01)
            out["over"] = P(lambda i, j: i + j > tt_line) + push * 0.5
        else:
            out["over"] = P(lambda i, j: i + j > tt_line)
        out["under"] = 1.0 - out["over"]
    if hdp is not None:
        if abs(abs(hdp) - round(abs(hdp))) < 0.01:
            push = P(lambda i, j: abs((i - j) + hdp) < 0.01)
            out["hdp_home"] = P(lambda i, j: (i - j) + hdp > 0) + push * 0.5
        else:
            out["hdp_home"] = P(lambda i, j: (i - j) + hdp > 0)
        out["hdp_away"] = 1.0 - out["hdp_home"]
    return out

def ev(p, price, orr):
    # 2026-08-27审计P0-1: 模型概率无抽水, EV=prob*price-1; orr 参数保留兼容调用, 不再使用
    return p * price - 1.0

def tier_label(ev):
    for _l, _th, _s in EV_TIERS:
        if ev >= _th:
            return _l, _s
    return "垃圾", 0.0

def analyze(m, att, zones, snap_dt=None):
    hn, an = CN_MAP.get(m["home"], m["home"]), CN_MAP.get(m["away"], m["away"])
    h2h, sp, tt = extract_markets(m)
    H, A = att.get(hn), att.get(an)
    # 盘口时效: 隔日/超阈值快照一律否决出单 (复盘中超统一规则)
    snap_veto = None
    try:
        ct = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
        if snap_dt is not None:
            age_h = (ct - snap_dt).total_seconds() / 3600.0
            if age_h > SNAPSHOT_STALE_HOURS:
                snap_veto = "盘口过期(距开赛%.0fh>阈值%.0fh)" % (age_h, SNAPSHOT_STALE_HOURS)
            elif snap_dt.date() < ct.date():
                snap_veto = "盘口为隔日快照(%s)" % snap_dt.date().isoformat()
    except Exception:
        pass
    # 攻防
    hgf, hga = H["home"]["gf"], H["home"]["ga"]
    agf, aga = A["away"]["gf"], A["away"]["ga"]
    lam = calc_lambdas(home_gf=hgf, away_ga=aga, away_gf=agf, home_ga=hga,
                       league_avg=CAL["league_avg"], home_coef=CAL["home"],
                       away_coef=CAL["away"], fatigue_coef=CAL["fatigue"], rho=CAL["rho"])
    grid = dc_score_grid(lam["lam_h"], lam["lam_a"], rho=CAL["rho"], max_goals=8)
    tt_line = tt[2] if tt else 2.5
    hdp = sp[2] if sp else None
    pr = probs_from_grid(grid, hdp=hdp, tt_line=tt_line)
    # 市场 fair
    fair = None
    if h2h:
        orr = h2h[0]
        fair = {"home": (1 / h2h[1]["home"]) / orr, "draw": (1 / h2h[1]["draw"]) / orr,
                "away": (1 / h2h[1]["away"]) / orr}
    # TOP比分
    top_items = [("%d-%d" % (i, j), grid[i][j]) for i in range(9) for j in range(9)]
    tops = sorted(top_items, key=lambda kv: -kv[1])[:5]
    # EV候选
    bets = []
    if sp:
        orr = sp[1]
        bets.append({"name": "让球主(%+.1f)" % hdp, "prob": pr["hdp_home"], "odds": sp[3]["home"],
                     "ev": ev(pr["hdp_home"], sp[3]["home"], orr)})
        bets.append({"name": "让球客(%+.1f)" % (-hdp), "prob": pr["hdp_away"], "odds": sp[3]["away"],
                     "ev": ev(pr["hdp_away"], sp[3]["away"], orr)})
    if tt:
        orr = tt[1]
        bets.append({"name": "大%.1f" % tt_line, "prob": pr["over"], "odds": tt[3]["over"],
                     "ev": ev(pr["over"], tt[3]["over"], orr)})
        bets.append({"name": "小%.1f" % tt_line, "prob": pr["under"], "odds": tt[3]["under"],
                     "ev": ev(pr["under"], tt[3]["under"], orr)})
    if h2h:
        orr = h2h[0]
        for label, pk, price in (("主胜", "home", h2h[1]["home"]), ("平局", "draw", h2h[1]["draw"]),
                                 ("客胜", "away", h2h[1]["away"])):
            bets.append({"name": "1X2" + label, "prob": pr["w"] if pk == "home" else pr["d"] if pk == "draw" else pr["l"],
                         "odds": price, "ev": ev(pr["w"] if pk == "home" else pr["d"] if pk == "draw" else pr["l"], price, orr),
                         "is_1x2": True})
    ev_min = EV_TIER_INTEL if HAS_INTEL else EV_TIER_BATCH
    valid = [b for b in bets if not b.get("is_1x2") and b["ev"] >= ev_min and b["odds"] >= ODDS_FLOOR]
    best = max(valid, key=lambda b: b["prob"]) if valid else None
    # 风险信号
    risk = ["无伤停/轮换情报"]
    if not sp:
        risk.append("缺亚盘")
    if not tt:
        risk.append("缺大小球")
    if snap_veto:
        risk.append(snap_veto + "->否决出单")
    else:
        risk.append("盘口为快照(非临场, 需复核)")
    if best and fair:
        _opp = None
        if best["name"].startswith("让球") and sp:
            _opp = sp[3]["away"] if "主" in best["name"] else sp[3]["home"]
            _orr = 1 / best["odds"] + 1 / _opp
            mkt = (1 / best["odds"]) / _orr
        elif best["name"].startswith(("大", "小")) and tt:
            _opp = tt[3]["under"] if best["name"].startswith("大") else tt[3]["over"]
            _orr = 1 / best["odds"] + 1 / _opp
            mkt = (1 / best["odds"]) / _orr
        else:
            mkt = None
        if mkt is not None and best["prob"] - mkt > 0.20:
            risk.append("模型与市场分歧>%.0fpp->否决出单(纯攻防外推失真)" % ((best["prob"] - mkt) * 100))
    star = 0
    stake = 0.0
    if best and (snap_veto or any("否决出单" in t for t in risk)):
        best = None  # 极端分歧/过期盘口: 不列入可出单
    if best:
        _tier, _stake = tier_label(best["ev"])
        n_risk = len([t for t in risk if t != "无伤停/轮换情报"])
        star = 3 if best["ev"] >= 0.20 else 2 if best["ev"] >= 0.08 else 1
        star = max(1, star - (1 if n_risk >= 1 else 0) - (1 if n_risk >= 3 else 0))
        best["star"] = star
        best["ev_tier"] = _tier
        best["stake_factor"] = _stake * (0.5 if n_risk >= 1 else 1.0) * (0.5 if n_risk >= 3 else 1.0)
    return {
        "home": hn, "away": an, "home_en": m["home"], "away_en": m["away"],
        "ct": m["commence_time"], "books": len(m["bookmakers"]),
        "att": {"home": "%.2f进/%.2f失(%d场)" % (hgf, hga, H["home"]["n"]),
                "away": "%.2f进/%.2f失(%d场)" % (agf, aga, A["away"]["n"])},
        "odds": {
            "h2h": {"prices": h2h[1] if h2h else None, "orr": round(h2h[0], 4) if h2h else None, "book": h2h[2] if h2h else None},
            "spread": {"line": hdp, "prices": sp[3] if sp else None, "orr": round(sp[1], 4) if sp else None, "book": sp[4] if sp else None},
            "totals": {"line": tt_line, "prices": tt[3] if tt else None, "orr": round(tt[1], 4) if tt else None, "book": tt[4] if tt else None},
        },
        "lambda": {"home": round(lam["lam_h"], 2), "away": round(lam["lam_a"], 2), "sum": round(lam["lam_h"] + lam["lam_a"], 2)},
        "probs": {"w": round(pr["w"], 4), "d": round(pr["d"], 4), "l": round(pr["l"], 4),
                  "over": round(pr["over"], 4) if tt else None, "under": round(pr["under"], 4) if tt else None,
                  "hdp_home": round(pr["hdp_home"], 4) if sp else None},
        "market_fair": {k: round(v, 4) for k, v in fair.items()} if fair else None,
        "top_scores": [{"s": k, "p": round(v, 4)} for k, v in tops],
        "bets": bets, "best_bet": best, "star": star, "risk": risk,
    }

def main():
    zones = json.load(io.open(os.path.join(ROOT, "strategy_data", "csl_odds_zones.json"), encoding="utf-8"))
    _cands = sorted(glob.glob(os.path.join(ROOT, "strategy_data", "csl_odds_tonight_*.json")))
    if not _cands:
        print("无中超盘口文件 strategy_data/csl_odds_tonight_*.json"); return
    odds_path = _cands[-1]
    matches = load_odds(odds_path)
    _snap_dt = datetime.fromtimestamp(os.path.getmtime(odds_path), tz=timezone.utc)
    print("盘口文件: %s (快照 %s UTC, 阈值 %s 小时)" % (odds_path, _snap_dt.strftime("%Y-%m-%d %H:%M"), SNAPSHOT_STALE_HOURS))
    att, _ = load_att_def()
    # 联赛校准 sanity check
    avg = CAL["league_avg"] / 2
    lam0 = calc_lambdas(home_gf=avg, away_ga=avg, away_gf=avg, home_ga=avg,
                        league_avg=CAL["league_avg"], home_coef=CAL["home"],
                        away_coef=CAL["away"], fatigue_coef=CAL["fatigue"], rho=CAL["rho"])
    g0 = dc_score_grid(lam0["lam_h"], lam0["lam_a"], rho=CAL["rho"], max_goals=8)
    p0 = probs_from_grid(g0, tt_line=2.5)
    print("联赛校准: 模型 主%.1f%%/平%.1f%%/客%.1f%% 大2.5 %.1f%% | 真值 主48.5%%/平24.6%%/客26.9%% 大2.5 57.3%%" % (
        p0["w"] * 100, p0["d"] * 100, p0["l"] * 100, p0["over"] * 100))
    BJT = timezone(timedelta(hours=8))
    results = []
    for m in sorted(matches, key=lambda x: x["commence_time"]):
        r = analyze(m, att, zones, _snap_dt)
        results.append(r)
        bj = datetime.fromisoformat(r["ct"].replace("Z", "+00:00")).astimezone(BJT).strftime("%m-%d %H:%M")
        print("=" * 78)
        print("%s 中超  %s vs %s" % (bj, r["home"], r["away"]))
        print("  数据: 主%s 客%s | 机构%d家 | λ %.2f/%.2f(sum %.2f)" % (
            r["att"]["home"], r["att"]["away"], r["books"], r["lambda"]["home"], r["lambda"]["away"], r["lambda"]["sum"]))
        o = r["odds"]
        print("  盘口: 1X2 %s (orr %.3f/%s) | 亚盘 主%s @%s 客@%s (orr %.3f/%s) | 大小 %s 大%s/小%s (orr %.3f/%s)" % (
            ("%.2f/%.2f/%.2f" % (o["h2h"]["prices"]["home"], o["h2h"]["prices"]["draw"], o["h2h"]["prices"]["away"])) if o["h2h"]["prices"] else "无",
            o["h2h"]["orr"] or 0, o["h2h"]["book"] or "-",
            ("%+.1f" % o["spread"]["line"]) if o["spread"]["line"] is not None else "?",
            o["spread"]["prices"]["home"] if o["spread"]["prices"] else "-",
            o["spread"]["prices"]["away"] if o["spread"]["prices"] else "-",
            o["spread"]["orr"] or 0, o["spread"]["book"] or "-",
            o["totals"]["line"], o["totals"]["prices"]["over"] if o["totals"]["prices"] else "-",
            o["totals"]["prices"]["under"] if o["totals"]["prices"] else "-",
            o["totals"]["orr"] or 0, o["totals"]["book"] or "-"))
        pr = r["probs"]
        mf = r["market_fair"]
        print("  模型: 主%.1f%%/平%.1f%%/客%.1f%% | 大%.1f %.1f%% 小%.1f %.1f%% | 让球主覆盖 %.1f%%" % (
            pr["w"] * 100, pr["d"] * 100, pr["l"] * 100,
            o["totals"]["line"], (pr["over"] or 0) * 100, o["totals"]["line"], (pr["under"] or 0) * 100,
            (pr["hdp_home"] or 0) * 100))
        if mf:
            print("  市场fair: 主%.1f%%/平%.1f%%/客%.1f%% | TOP比分: %s" % (
                mf["home"] * 100, mf["draw"] * 100, mf["away"] * 100,
                ", ".join("%s %.1f%%" % (t["s"], t["p"] * 100) for t in r["top_scores"])))
        print("  风险: %s" % " | ".join(r["risk"]))
        bb = r["best_bet"]
        if bb:
            print("  EV候选: " + " | ".join("%s %.0f%% @%.2f EV%+.1f%%" % (b["name"], b["prob"] * 100, b["odds"], b["ev"] * 100) for b in r["bets"] if not b.get("is_1x2")))
            print("  best_bet: %s %.0f%% @%.2f EV%+.1f%% ★%d[%s] stake×%.2f" % (
                bb["name"], bb["prob"] * 100, bb["odds"], bb["ev"] * 100, bb.get("star", 0), bb.get("ev_tier", "?"), bb.get("stake_factor", 0)))
        else:
            print("  best_bet: %s" % ("否决出单(模型与市场极端分歧)" if any("否决出单" in t for t in r["risk"]) else "无正EV(门槛EV>=%.0f%%)" % (EV_TIER_BATCH * 100)))
    n_bb = sum(1 for r in results if r["best_bet"])
    print("=" * 78)
    print("汇总: %d场, best_bet %d/%d, 正EV场 %d/%d" % (
        len(results), n_bb, len(results), sum(1 for r in results if any(b["ev"] > 0 for b in r["bets"])), len(results)))
    out_path = os.path.join(ROOT, "analysis_records", "20260815_csl_tonight.json")
    io.open(out_path, "w", encoding="utf-8").write(json.dumps({
        "timestamp": "2026-08-15", "type": "中超今晚5场批量扫描",
        "note": "盘口源csl_odds_tonight_20260814(昨晚快照,非临场); 攻防baseline_2026_ytd(1-22轮,171场); 无伤停情报",
        "cal": CAL, "matches": results}, ensure_ascii=False, indent=1))
    print("saved: %s" % out_path)

if __name__ == "__main__":
    main()
