# -*- coding: utf-8 -*-
"""J1(2026-27跨年正式赛季) 第2轮 9场 重分析 v3
盘口时效纪律(第三类):
  - ML / Totals: 用 j1_odds_today_20260815.json 最新快照(Bet365 8/15 02:16 UTC), 剔除8/13旧价Unibet
  - 亚盘: 沿用8/14整理 Bet365盘口(已验证格式; odds-api.io Spread市场数据不可靠 orr<1 已弃用)
模型层: 沿用8/14整理 攻防+伤停/疲劳修正+大球漂移(无新赛果/情报)
真值:   j1_odds_zones.json
"""
import json, io, os, sys
ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
sys.stdout.reconfigure(encoding="utf-8")
from prob_calibration import dc_score_grid

EV_TIER_INTEL = 0.08
ODDS_FLOOR = 1.60
EV_TIERS = [("高价值", 0.20, 1.0), ("标准", 0.08, 0.7), ("观察", 0.05, 0.3), ("垃圾", 0.0, 0.0)]
FRESH_AFTER = "2026-08-14T00:00:00Z"

CN = {
    "Kashima Antlers": ("鹿岛鹿角", "鹿岛"), "Nagoya Grampus": ("名古屋鲸", "名古屋"),
    "Mito Hollyhock": ("水户蜀葵", "水户"), "Gamba Osaka": ("大阪钢巴", "钢巴"),
    "Shimizu S-Pulse": ("清水鼓动", "清水"), "Yokohama F Marinos": ("横滨水手", "横滨"),
    "Fagiano Okayama": ("冈山绿雉", "冈山"), "V-Varen Nagasaki": ("长崎航海", "长崎"),
    "Urawa Red Diamonds": ("浦和红钻", "浦和"), "Sanfrecce Hiroshima": ("广岛三箭", "广岛"),
    "JEF United Chiba": ("千叶市原", "千叶"), "Machida Zelvia": ("町田泽维亚", "町田"),
    "Kawasaki Frontale": ("川崎前锋", "川崎"), "Kyoto Sanga FC": ("京都不死鸟", "京都"),
    "Vissel Kobe": ("神户胜利船", "神户"), "FC Tokyo": ("FC东京", "东京FC"),
    "Avispa Fukuoka": ("福冈黄蜂", "福冈"), "Cerezo Osaka": ("大阪樱花", "樱花"),
}

def _fresh(bookmakers):
    out = {}
    for bk, mks in bookmakers.items():
        ts = max((mk.get("updatedAt") or "") for mk in mks if isinstance(mk, dict))
        if ts >= FRESH_AFTER:
            out[bk] = mks
    return out

def extract_ml_totals(o):
    ml = tt = None
    for bk, mks in _fresh(o["bookmakers"]).items():
        for mk in mks:
            name = mk.get("name")
            if name == "ML" and ml is None and mk.get("odds"):
                r = mk["odds"][0]
                try:
                    p = {"home": float(r["home"]), "draw": float(r["draw"]), "away": float(r["away"])}
                except Exception:
                    continue
                orr = sum(1.0 / v for v in p.values())
                ml = (orr, p, bk, mk.get("updatedAt"))
            elif name == "Totals":
                for row in mk.get("odds", []):
                    if row.get("over") is None or row.get("under") is None:
                        continue
                    try:
                        hdp = float(row["hdp"]); ov = float(row["over"]); un = float(row["under"])
                    except Exception:
                        continue
                    orr = 1.0 / ov + 1.0 / un
                    cand = (abs(hdp - 2.5), orr, hdp, ov, un, bk, mk.get("updatedAt"))
                    if tt is None or (cand[0], cand[1]) < (tt[0], tt[1]):
                        tt = cand
    return ml, tt

def load_old_model(path):
    d = json.load(io.open(path, encoding="utf-8"))
    out = {}
    for m in d["matches"]:
        h, a = [x.strip() for x in m["match"].split(" vs ")]
        out[(h, a)] = m
    return out

def analyze(o, old, zones):
    hn, hs = CN[o["home"]]
    an, as_ = CN[o["away"]]
    oldm = old.get((hs, as_)) or old.get((hs, an)) or old.get((hn, as_))
    ml, tt = extract_ml_totals(o)
    hdp = oldm["step05_odds"]["hdp"]   # 已验证Bet365 8/14盘口: {line, home_odds, away_odds}
    lam = oldm["step8_model"]["lambda"]
    lam_h, lam_a = lam["home"], lam["away"]
    rho = -0.05
    grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
    P = lambda cond: sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    w = P(lambda i, j: i > j); d = P(lambda i, j: i == j); l = P(lambda i, j: i < j)
    tt_line = tt[2] if tt else 2.5
    if abs(tt_line - round(tt_line)) < 0.01:
        push = P(lambda i, j: abs(i + j - tt_line) < 0.01)
        over = P(lambda i, j: i + j > tt_line) + push * 0.5
    else:
        over = P(lambda i, j: i + j > tt_line)
    under = 1.0 - over
    hdp_line = float(hdp["line"])
    if abs(abs(hdp_line) - round(abs(hdp_line))) < 0.01:
        push = P(lambda i, j: abs((i - j) + hdp_line) < 0.01)
        hdp_h = P(lambda i, j: (i - j) + hdp_line > 0) + push * 0.5
    else:
        hdp_h = P(lambda i, j: (i - j) + hdp_line > 0)
    # EV
    bets = []
    sp_orr = 1.0 / hdp["home_odds"] + 1.0 / hdp["away_odds"]
    bets.append({"name": "让球主(%+.1f)" % hdp_line, "prob": hdp_h, "odds": hdp["home_odds"],
                 "ev": (hdp_h / sp_orr) * hdp["home_odds"] - 1.0})
    bets.append({"name": "让球客(%+.1f)" % (-hdp_line), "prob": 1 - hdp_h, "odds": hdp["away_odds"],
                 "ev": ((1 - hdp_h) / sp_orr) * hdp["away_odds"] - 1.0})
    if tt:
        tt_orr = tt[1]
        bets.append({"name": "大%.1f" % tt_line, "prob": over, "odds": tt[3],
                     "ev": (over / tt_orr) * tt[3] - 1.0})
        bets.append({"name": "小%.1f" % tt_line, "prob": under, "odds": tt[4],
                     "ev": (under / tt_orr) * tt[4] - 1.0})
    fair = None
    if ml:
        ml_orr = ml[0]
        fair = {"home": (1 / ml[1]["home"]) / ml_orr, "draw": (1 / ml[1]["draw"]) / ml_orr,
                "away": (1 / ml[1]["away"]) / ml_orr}
        for label, pk, price in (("主胜", "home", ml[1]["home"]), ("平局", "draw", ml[1]["draw"]),
                                 ("客胜", "away", ml[1]["away"])):
            pv = w if pk == "home" else d if pk == "draw" else l
            bets.append({"name": "1X2" + label, "prob": pv, "odds": price,
                         "ev": (pv / ml_orr) * price - 1.0, "is_1x2": True})
    valid = [b for b in bets if not b.get("is_1x2") and b["ev"] >= EV_TIER_INTEL and b["odds"] >= ODDS_FLOOR]
    best = max(valid, key=lambda b: b["prob"]) if valid else None
    risk = list(oldm.get("step75_risk_signals") or [])
    risk.append("伤停情报为8/14整理(非今日更新)")
    risk.append("亚盘沿用8/14 Bet365(odds-api.io Spread不可靠弃用); ML/大小球为8/15最新快照")
    veto = False
    if best and fair:
        mkt = None
        if best["name"].startswith("让球"):
            _opp = hdp["away_odds"] if "主" in best["name"] else hdp["home_odds"]
            _orr = 1 / best["odds"] + 1 / _opp
            mkt = (1 / best["odds"]) / _orr
        elif best["name"].startswith(("大", "小")) and tt:
            _opp = tt[4] if best["name"].startswith("大") else tt[3]
            _orr = 1 / best["odds"] + 1 / _opp
            mkt = (1 / best["odds"]) / _orr
        if mkt is not None and best["prob"] - mkt > 0.20:
            veto = True
            risk.append("模型与市场分歧>%.0fpp->否决出单" % ((best["prob"] - mkt) * 100))
        # 模型1X2 vs 市场1X2 方向冲突否决: 主队概率差>15pp 且押注与市场反向
        if not veto and ml:
            dw = w - fair["home"]
            bet_home = ("主" in best["name"] and "客" not in best["name"]) or best["name"].startswith("1X2主胜")
            bet_away = ("客" in best["name"]) or best["name"].startswith("1X2客胜")
            if abs(dw) > 0.15 and ((dw > 0 and bet_home) or (dw < 0 and bet_away)):
                veto = True
                risk.append("模型与市场1X2方向冲突(主队%.0f%% vs %.0f%%)->否决出单" % (w * 100, fair["home"] * 100))
    star = 0
    if best and not veto:
        _tier, _stake = "垃圾", 0.0
        for _l, _th, _s in EV_TIERS:
            if best["ev"] >= _th:
                _tier, _stake = _l, _s
                break
        n_risk = len([t for t in risk if "8/14" not in t and "沿用" not in t])
        star = 3 if best["ev"] >= 0.20 else 2 if best["ev"] >= 0.08 else 1
        star = max(1, star - (1 if n_risk >= 3 else 0))
        best["star"] = star
        best["ev_tier"] = _tier
        best["stake_factor"] = _stake * (0.5 if n_risk >= 3 else 1.0)
    elif best and veto:
        best = None
    truth = {}
    if ml:
        hp = ml[1]["home"]
        if hp <= 1.50:
            truth["zone"] = "深热(主<1.50): 主胜68.2%但易赢球输盘"
        elif hp <= 1.80:
            truth["zone"] = "优势局(1.51-1.80): 主胜56.7%稳定"
        elif hp <= 2.20:
            truth["zone"] = "均衡局(1.81-2.20): 平局高发25.8%"
        elif hp <= 2.70:
            truth["zone"] = "客队小幅优(2.21-2.70): 客胜43.9%"
        else:
            truth["zone"] = "主队劣势(>2.71): 客队59%方向"
    if abs(abs(hdp_line)) < 0.01:
        truth["hdp"] = "平手盘: 平局概率最高/历史大2.5=61%"
    elif abs(abs(hdp_line) - 0.25) < 0.01:
        truth["hdp"] = "平手半球: 下盘优势54.4%"
    elif abs(abs(hdp_line) - 0.5) < 0.01:
        truth["hdp"] = "半球: 上下盘均衡51.3/48.7"
    elif abs(abs(hdp_line) - 0.75) < 0.01:
        truth["hdp"] = "半一: 上盘49.8/下盘50.2, 防赢球输盘"
    else:
        truth["hdp"] = "深盘(>=1): 上盘仅37.4%, 很难穿盘"
    tops = sorted((("%d-%d" % (i, j), grid[i][j]) for i in range(9) for j in range(9)),
                  key=lambda kv: -kv[1])[:4]
    return {
        "match": "%s vs %s" % (hn, an), "en": "%s vs %s" % (o["home"], o["away"]),
        "old_lambda": oldm["step8_model"]["lambda"], "old_wdl": oldm["step8_model"]["wdl"],
        "lambda": {"home": lam_h, "away": lam_a, "sum": round(lam_h + lam_a, 2)},
        "odds": {"ml": ml[1] if ml else None, "ml_orr": round(ml[0], 4) if ml else None, "ml_book": ml[2] if ml else None,
                 "spread": {"line": hdp_line, "home": hdp["home_odds"], "away": hdp["away_odds"],
                            "orr": round(sp_orr, 4), "book": "Bet365(8/14沿用)"},
                 "totals": {"line": tt_line, "over": tt[3] if tt else None, "under": tt[4] if tt else None,
                            "orr": round(tt[1], 4) if tt else None, "book": tt[5] if tt else None}},
        "model": {"w": round(w, 4), "d": round(d, 4), "l": round(l, 4),
                  "over": round(over, 4), "under": round(under, 4), "hdp_home": round(hdp_h, 4)},
        "market_fair": {k: round(v, 4) for k, v in fair.items()} if fair else None,
        "truth": truth, "top_scores": [{"s": s, "p": round(p, 4)} for s, p in tops],
        "bets": bets, "best_bet": best, "star": star, "veto": veto, "risk": risk,
    }

def main():
    odds = json.load(io.open(os.path.join(ROOT, "strategy_data", "j1_odds_today_20260815.json"), encoding="utf-8"))["odds"]
    old = load_old_model(os.path.join(ROOT, "analysis_records", "20260815_J1第2轮_9场_赛前分析.json"))
    results = [analyze(o, old, None) for o in odds]
    for r in results:
        ml = r["odds"]["ml"]; sp = r["odds"]["spread"]; tt = r["odds"]["totals"]
        print("=" * 78)
        print("%s | λ %.2f/%.2f(sum %.2f)" % (r["match"], r["lambda"]["home"], r["lambda"]["away"], r["lambda"]["sum"]))
        print("  盘口: 1X2 %s (orr %.3f/%s) | 亚盘 主%s @%.2f/客@%.2f (orr %.3f/%s) | 大小%.1f 大%.2f/小%.2f (orr %.3f/%s)" % (
            "%.2f/%.2f/%.2f" % (ml["home"], ml["draw"], ml["away"]) if ml else "无",
            r["odds"]["ml_orr"] or 0, r["odds"]["ml_book"] or "-",
            ("%+.1f" % sp["line"]), sp["home"], sp["away"], sp["orr"], sp["book"],
            tt["line"], tt["over"] or 0, tt["under"] or 0, tt["orr"] or 0, tt["book"] or "-"))
        m = r["model"]; mf = r["market_fair"]
        print("  模型: 主%.1f%%/平%.1f%%/客%.1f%% | 大%.1f %.1f%%/小 %.1f%% | 让主覆盖 %.1f%%" % (
            m["w"] * 100, m["d"] * 100, m["l"] * 100, tt["line"], m["over"] * 100, m["under"] * 100, m["hdp_home"] * 100))
        if mf:
            print("  市场fair(新): 主%.1f%%/平%.1f%%/客%.1f%% | 真值: %s | %s" % (
                mf["home"] * 100, mf["draw"] * 100, mf["away"] * 100, r["truth"].get("zone", "-"), r["truth"].get("hdp", "-")))
        print("  TOP比分: %s" % ", ".join("%s %.1f%%" % (t["s"], t["p"] * 100) for t in r["top_scores"]))
        print("  风险: %s" % " | ".join(r["risk"]))
        evs = [(b["name"], b["ev"] * 100, b["prob"] * 100, b["odds"]) for b in r["bets"] if not b.get("is_1x2")]
        print("  EV候选: " + " | ".join("%s EV%+.1f%%(%.0f%%@%.2f)" % e for e in evs))
        bb = r["best_bet"]
        if bb:
            print("  best_bet: %s %.0f%% @%.2f EV%+.1f%% ★%d[%s] stake×%.2f" % (
                bb["name"], bb["prob"] * 100, bb["odds"], bb["ev"] * 100, bb.get("star", 0),
                bb.get("ev_tier", "?"), bb.get("stake_factor", 0)))
        else:
            print("  best_bet: %s" % ("否决出单(模型与市场极端分歧)" if r["veto"] else "无正EV(门槛>=%.0f%%)" % (EV_TIER_INTEL * 100)))
    n_bb = sum(1 for r in results if r["best_bet"])
    print("=" * 78)
    print("汇总: %d场, best_bet %d/%d, 正EV %d/%d, 否决 %d" % (
        len(results), n_bb, len(results),
        sum(1 for r in results if any(b["ev"] > 0 for b in r["bets"])), len(results),
        sum(1 for r in results if r["veto"])))
    out_path = os.path.join(ROOT, "analysis_records", "20260815_J1第2轮_9场_重分析.json")
    io.open(out_path, "w", encoding="utf-8").write(json.dumps({
        "timestamp": "2026-08-15", "type": "J1第2轮9场重分析v3(最新盘口+时效纪律)",
        "note": "ML/大小球=Bet365 8/15最新快照(剔除8/13 Unibet); 亚盘=8/14 Bet365沿用(odds-api.io Spread orr<1不可靠弃用); 模型层=8/14攻防+伤停+大球漂移",
        "matches": results}, ensure_ascii=False, indent=1))
    print("saved: %s" % out_path)

if __name__ == "__main__":
    main()
