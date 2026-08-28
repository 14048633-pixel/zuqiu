# -*- coding: utf-8 -*-
"""从 scan24h json 构造事件扫描未来24h(BSD盘口注入) - v3 (2026-08-27 窗口)"""
import sys, os, io, json, collections
from datetime import datetime, timezone, timedelta
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
from bsd_extra import _get

BJT = timezone(timedelta(hours=8))
NOW = datetime.now(timezone.utc)

LG_MAP = {
    "Emperor Cup": "天皇杯", "Carabao Cup": "英联杯", "Copa do Brasil": "巴西杯",
    "Copa Libertadores": "解放者杯", "Champions League": "欧冠", "Saudi Pro League": "沙超",
    "K League 1": "K联赛", "Brasileirão Serie B": "巴乙", "Brasileirão Serie A": "巴甲",
    "La Liga": "西甲", "Categoría Primera A": "哥甲", "Club Friendlies": "友谊赛",
    "Europa League": "欧联杯", "Conference League": "欧协联", "Copa Sudamericana": "南美杯", "NWSL": "NWSL",
    "USL Championship": "USL", "Chinese Super League": "中超", "J1 League": "J1",
    "Premier League": "英超", "Championship": "英冠", "League One": "英甲",
    "League Two": "英乙", "Ligue 1": "法甲", "Ligue 2": "法乙", "Bundesliga": "德甲",
    "Serie A": "意甲", "Eredivisie": "荷甲", "Liga Portugal Betclic": "葡超",
    "Pro League": "比甲", "Trendyol Super Lig": "土超", "Ekstraklasa": "波甲",
    "MLS": "美职", "Liga MX Apertura": "墨超", "Liga Profesional de Fútbol": "阿甲",
    "Copa del Rey": "国王杯", "Coppa Italia": "意大利杯", "DFB Pokal": "德国杯",
    "Segunda División": "西乙", "Liga Portugal 2": "葡乙", "Super League": "瑞超",
}

def main():
    su.recent_league_avg = lambda: {}
    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260827_1947.json"), encoding="utf-8"))["matches"]
    team_stats, lavg, index = su.load_team_stats()
    def _pkg_league(mid):
        fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % mid)
        try:
            return json.load(io.open(fp, encoding="utf-8")).get("league")
        except Exception:
            return None
    events = []
    _ahd = {}
    try:
        _ahd = json.load(io.open(os.path.join(ROOT, "analysis_records", "ah_spread_20260827_1947.json"), encoding="utf-8")).get("spreads") or {}
    except Exception:
        pass
    for m in lst:
        lg = LG_MAP.get(_pkg_league(m["id"])) or LG_MAP.get(m.get("league")) or m.get("league") or "未知"
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        ev = {
            "id": m["id"], "lg": lg, "league": lg, "ct": ct, "home": m["home"], "away": m["away"],
            "snap": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "odds": collections.defaultdict(list),
        }
        _ah = _ahd.get(str(m["id"]))
        if _ah:
            ev["spread"] = {"hdp_home": _ah["line"], "home_price": _ah["home_price"], "away_price": _ah["away_price"]}
            ev["ah_src"] = "apifb(%s)" % (_ah.get("book") or "?")
        events.append(ev)
    print("events:", len(events))
    try:
        n = su.bsd_odds_merge(events)
        print("BSD consensus 覆盖:", n)
    except Exception as e:
        print("bsd_odds_merge skip:", repr(e)[:200])
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
            "lambda": r.get("lambda"), "wdl": r.get("wdl"), "market_fair": r.get("market_fair"),
            "direction": di.get("name"), "dir_prob": di.get("prob"), "dir_odds": di.get("odds"),
            "dir_ev": di.get("ev"), "vetoed": di.get("vetoed"), "veto_reason": di.get("veto_reason"),
            "draw_warn": r.get("draw_warn"), "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "risk_tags": r.get("risk_tags") or [], "dir_consistency": r.get("dir_consistency"),
            "best_bet": bb, "bets": r.get("bets"), "notes": r.get("notes") or [], "error": None,
        })
    fp = os.path.join(ROOT, "analysis_records", "scan_next24h_%s.json" % NOW.strftime("%Y%m%d_%H%M"))
    json.dump(out, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", fp, "| 场次:", len(out))
    from collections import Counter
    bb_cnt = Counter(); veto = 0; err = 0
    for o in out:
        if o.get("best_bet"):
            bb_cnt[o["best_bet"].get("star")] += 1
        if o.get("vetoed"):
            veto += 1
        if o.get("error"):
            err += 1
    print("BEST 星级分布:", dict(bb_cnt), "| 否决:", veto, "| error:", err, "| 有盘:", sum(1 for o in out if o.get("dir_odds")))

if __name__ == "__main__":
    main()
