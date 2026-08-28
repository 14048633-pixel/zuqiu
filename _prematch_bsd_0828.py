# -*- coding: utf-8 -*-
"""27号47场 - BSD 临盘重拉 + 注入重跑 (2026-08-28)"""
import io, sys, os, json, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
import bsd_extra
BJT = timezone(timedelta(hours=8))

def bsd_consensus(eid):
    """BSD 最新共识盘 (1X2 + 大小球), 免费端点; comparison 需付费跳过."""
    try:
        j = bsd_extra._get("/api/v2/events/%d/odds/" % eid)
    except Exception:
        return None
    if not j:
        return None
    cons = j.get("odds") or {}
    return cons or None
LG_MAP = {
    "Emperor Cup": "天皇杯", "Carabao Cup": "英联杯", "Copa do Brasil": "巴西杯",
    "Copa Libertadores": "解放者杯", "Champions League": "欧冠", "Saudi Pro League": "沙超",
    "K League 1": "K联赛", "Brasileirao Serie B": "巴乙", "Brasileirao Serie A": "巴甲",
    "La Liga": "西甲", "Categoria Primera A": "哥甲", "Club Friendlies": "友谊赛",
    "Europa League": "欧联杯", "Conference League": "欧协联", "Copa Sudamericana": "南美杯", "NWSL": "NWSL",
    "USL Championship": "USL", "Chinese Super League": "中超", "J1 League": "J1",
    "Premier League": "英超", "Championship": "英冠", "League One": "英甲",
    "League Two": "英乙", "Ligue 1": "法甲", "Ligue 2": "法乙", "Bundesliga": "德甲",
    "Serie A": "意甲", "Eredivisie": "荷甲", "Liga Portugal Betclic": "葡超",
    "Pro League": "比甲", "Trendyol Super Lig": "土超", "Ekstraklasa": "波甲",
    "MLS": "美职", "Liga MX Apertura": "墨超", "Liga Profesional de Futbol": "阿甲",
    "Copa del Rey": "国王杯", "Coppa Italia": "意大利杯", "DFB Pokal": "德国杯",
    "Segunda Division": "西乙", "Liga Portugal 2": "葡乙", "Super League": "瑞超",
    "National League": "英议联",
}
def pkg_league(mid):
    fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % mid)
    try:
        return json.load(io.open(fp, encoding="utf-8")).get("league")
    except Exception:
        return None
def main():
    su.recent_league_avg = lambda: {}
    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260827_1947.json"), encoding="utf-8"))["matches"]
    ahd = {}
    try:
        ahd = json.load(io.open(os.path.join(ROOT, "analysis_records", "ah_spread_20260827_1947.json"), encoding="utf-8")).get("spreads") or {}
    except Exception:
        pass
    team_stats, lavg, index = su.load_team_stats()
    now = datetime.now(timezone.utc)
    pend = []
    for m in lst:
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        if ct <= now:
            continue
        pend.append({"m": m, "ct": ct})
    print("未开赛场次:", len(pend))
    fresh = {}
    ok = fail = 0
    for i, p in enumerate(pend):
        eid = p["m"]["id"]
        try:
            cons = bsd_consensus(eid)
        except Exception as e:
            cons = None
            print("  [%d/%d] ERR %s: %s" % (i+1, len(pend), p["m"]["home"], repr(e)[:100]))
        if cons and cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
            ok += 1
        else:
            fail += 1
            print("  [%d/%d] 无BSD共识: %s vs %s" % (i+1, len(pend), p["m"]["home"], p["m"]["away"]))
        fresh[str(eid)] = {"home": p["m"]["home"], "away": p["m"]["away"], "consensus": cons}
        time.sleep(0.35)
    print("BSD临盘: 有1X2共识 %d / 失败 %d" % (ok, fail))
    ts = now.strftime("%Y%m%d_%H%M")
    fp0 = os.path.join(ROOT, "analysis_records", "prematch_bsd_%s.json" % ts)
    json.dump({"generated": datetime.now(BJT).isoformat(), "n": len(pend), "odds": fresh},
              io.open(fp0, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", fp0)
    events = []
    for p in pend:
        m = p["m"]
        lg = LG_MAP.get(pkg_league(m["id"])) or LG_MAP.get(m.get("league")) or m.get("league") or "未知"
        ev = {"id": m["id"], "lg": lg, "league": lg, "ct": p["ct"], "home": m["home"], "away": m["away"],
              "snap": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "odds": collections.defaultdict(list)}
        _ah = ahd.get(str(m["id"]))
        if _ah:
            ev["spread"] = {"hdp_home": _ah["line"], "home_price": _ah["home_price"], "away_price": _ah["away_price"]}
            ev["ah_src"] = "apifb(%s)" % (_ah.get("book") or "?")
        f = fresh.get(str(m["id"]))
        cons = (f or {}).get("consensus") or {}
        if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
            ev["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
            ev["h2h_src"] = "bsd_live"
        if cons.get("over_25_goals") and cons.get("under_25_goals"):
            ev["totals"] = {"line": 2.5, "over_price": cons["over_25_goals"], "under_price": cons["under_25_goals"]}
            ev["totals_src"] = "bsd_live"
        events.append(ev)
    rows = []
    for m in events:
        try:
            r = su.analyze_match(m, team_stats, lavg, index)
        except Exception as e:
            r = {"error": str(e)}
        rows.append({"match": m, "result": r})
    rows.sort(key=lambda x: x["match"]["ct"])
    out = []
    for x in rows:
        m = x["match"]; r = x["result"]
        if isinstance(r, dict) and r.get("error"):
            out.append({"ko_bjt": m["ct"].astimezone(BJT).strftime("%m-%d %H:%M"), "ko_utc": m["ct"].isoformat(),
                        "league": m["league"], "home": m["home"], "away": m["away"], "error": r["error"]})
            continue
        di = r.get("direction") or {}
        bb = r.get("best_bet")
        out.append({
            "ko_bjt": m["ct"].astimezone(BJT).strftime("%m-%d %H:%M"),
            "ko_utc": m["ct"].isoformat(),
            "league": m["league"], "home": m["home"], "away": m["away"],
            "h2h_src": m.get("h2h_src"), "ah_src": m.get("ah_src"), "totals_src": m.get("totals_src"),
            "lambda": r.get("lambda"), "wdl": r.get("wdl"), "market_fair": r.get("market_fair"),
            "direction": di.get("name"), "dir_prob": di.get("prob"), "dir_odds": di.get("odds"),
            "dir_ev": di.get("ev"), "vetoed": di.get("vetoed"), "veto_reason": di.get("veto_reason"),
            "draw_warn": r.get("draw_warn"), "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "risk_tags": r.get("risk_tags") or [], "dir_consistency": r.get("dir_consistency"),
            "best_bet": bb, "bets": r.get("bets"), "notes": r.get("notes") or [], "error": None,
        })
    res_fp = os.path.join(ROOT, "analysis_records", "scan_next24h_%s_bsd.json" % ts)
    json.dump(out, io.open(res_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", res_fp, "| 场次:", len(out))
    from collections import Counter
    bb_cnt = Counter(); veto = 0; err = 0
    for o in out:
        if o.get("best_bet"):
            bb_cnt[o["best_bet"].get("star")] += 1
        if o.get("vetoed"):
            veto += 1
        if o.get("error"):
            err += 1
    print("BEST 星级分布:", dict(bb_cnt), "| 否决:", veto, "| error:", err,
          "| 有1X2:", sum(1 for o in out if o.get("h2h_src")),
          "| 有亚盘:", sum(1 for o in out if o.get("ah_src")),
          "| 有大小球:", sum(1 for o in out if o.get("totals_src")))
if __name__ == "__main__":
    main()
