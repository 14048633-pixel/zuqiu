# -*- coding: utf-8 -*-
"""通用扫描: 最新 scan24h + BSD 注入 + analyze_match (2026-08-28)"""
import io, sys, os, json, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
BJT = timezone(timedelta(hours=8))
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
    "National League": "英议联", "Danish Superliga": "丹超", "Parva Liga": "保超",
    "Nigeria Premier Football League": "尼日超", "Superliga": "罗甲",
}

def main():
    import glob
    su.recent_league_avg = lambda: {}
    fs = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "scan24h_2026*.json")))
    fp_in = fs[-1] if fs else None
    if not fp_in:
        print("no scan24h file"); return
    print("输入:", fp_in)
    lst = json.load(io.open(fp_in, encoding="utf-8"))["matches"]
    team_stats, lavg, index = su.load_team_stats()
    now = datetime.now(timezone.utc)
    events = []
    pend = 0
    for m in lst:
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        if ct <= now:
            continue
        pend += 1
        lg = LG_MAP.get(m.get("league")) or m.get("league") or "未知"
        ev = {"id": m["id"], "lg": lg, "league": lg, "ct": ct, "home": m["home"], "away": m["away"],
              "snap": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "odds": collections.defaultdict(list)}
        events.append(ev)
    print("未开赛场次:", pend, "/", len(lst))
    # 亚盘注入 (pull_ah_quota.py 产物, 按事件id匹配, 省额度: 仅在临近开赛窗口拉取)
    try:
        _ah = json.load(io.open(os.path.join(ROOT, "analysis_records", "ah_spread_latest.json"), encoding="utf-8"))
    except Exception:
        _ah = {}
    _ah_n = 0
    for ev in events:
        _r = _ah.get(str(ev["id"]))
        if _r and _r.get("home_line") is not None:
            ev["spread"] = {"hdp_home": _r["home_line"], "home_price": _r["home_price"], "away_price": _r["away_price"]}
            ev["ah_src"] = "apifb(%s,%d家)" % (_r.get("src", "mainline"), _r.get("books", 0))
            _ah_n += 1
    if _ah_n:
        print("亚盘注入:", _ah_n, "场")
    try:
        n = su.bsd_odds_merge(events)
        print("BSD 共识覆盖:", n)
    except Exception as e:
        print("bsd_odds_merge skip:", repr(e)[:150])
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
    res_fp = os.path.join(ROOT, "analysis_records", "scan_next24h_%s.json" % now.strftime("%Y%m%d_%H%M"))
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
    print("BEST 星级:", dict(bb_cnt), "| 否决:", veto, "| error:", err,
          "| 有盘:", sum(1 for o in out if o.get("dir_odds")))
    print("联赛:", dict(Counter(o.get("league") for o in out)))
if __name__ == "__main__":
    main()
