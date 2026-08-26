# -*- coding: utf-8 -*-
"""从 scan24h json 构造事件扫描未来24h(BSD盘口注入) - v2"""
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
    "Emperor Cup": "天皇杯",
    "Carabao Cup": "英联杯",
    "Copa do Brasil": "巴西杯",
    "Copa Libertadores": "解放者杯",
    "Champions League": "欧冠",
    "Saudi Pro League": "沙超",
    "K League 1": "K联赛",
    "Brasileirão Serie B": "巴乙",
    "La Liga": "西甲",
    "Categoría Primera A": "哥甲",
    "Club Friendlies": "友谊赛",
}


def _apifb_emperor_inject(events):
    """从 snapshots.csv 注入 apifb 天皇杯盘口 (h2h/totals 均值)"""
    import csv, statistics
    snap_p = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    rows = list(csv.DictReader(io.open(snap_p, encoding="utf-8-sig")))
    agg = {}   # apifb{fid} -> {h2h:{side:[price]}, totals:{side:[price]}}
    for r in rows:
        eid = r.get("event_id") or ""
        if r.get("league") != "天皇杯" or not eid.startswith("apifb"):
            continue
        d = agg.setdefault(eid, {"h2h": {}, "totals": {}})
        try:
            price = float(r["price"])
        except Exception:
            continue
        if r["market"] == "h2h":
            d["h2h"].setdefault(r["side"], []).append(price)
        elif r["market"] == "totals" and r.get("point") == "2.5":
            d["totals"].setdefault(r["side"], []).append(price)
    # fid -> BSD 队名
    fid_map = {}
    try:
        fm = json.load(io.open(os.path.join(ROOT, "analysis_records", "apifb_fixture_map_emperor_20260826.json"), encoding="utf-8"))["matches"]
        for mm in fm:
            fid_map[int(mm["fixture_id"])] = (mm["target_home"], mm["target_away"])
    except Exception:
        pass
    n = 0
    for m in events:
        fid = None
        for _fid, (_h, _a) in fid_map.items():
            if _h == m["home"] and _a == m["away"]:
                fid = _fid
                break
        if fid is None:
            continue
        d = agg.get("apifb%d" % fid)
        if not d:
            continue
        h2h = d["h2h"]
        if h2h.get("home") and h2h.get("draw") and h2h.get("away"):
            m["h2h"] = {"home": statistics.mean(h2h["home"]), "draw": statistics.mean(h2h["draw"]), "away": statistics.mean(h2h["away"])}
            m.setdefault("books_used", {})["h2h"] = "apifb_avg"
        tt = d["totals"]
        if tt.get("over") and tt.get("under"):
            m["totals"] = {"line": 2.5, "over_price": statistics.mean(tt["over"]), "under_price": statistics.mean(tt["under"])}
            m.setdefault("books_used", {})["totals"] = "apifb_avg(2.5)"
        if "h2h" in m or "totals" in m:
            n += 1
    return n


def main():
    su.recent_league_avg = lambda: {}
    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260826_0000.json"), encoding="utf-8"))["matches"]
    team_stats, lavg, index = su.load_team_stats()
    # 从 match_package 读真实联赛名(BSD detail), 映射为系统认识键
    def _pkg_league(mid):
        fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % mid)
        try:
            return json.load(io.open(fp, encoding="utf-8")).get("league")
        except Exception:
            return None
    events = []
    for m in lst:
        lg = LG_MAP.get(_pkg_league(m["id"])) or m.get("league") or "未知"
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        events.append({
            "id": m["id"], "lg": lg, "league": lg, "ct": ct, "home": m["home"], "away": m["away"],
            "snap": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "odds": collections.defaultdict(list),
        })
    print("events:", len(events))
    try:
        n = su.bsd_odds_merge(events)
        print("BSD consensus 覆盖:", n)
    except Exception as e:
        print("bsd_odds_merge skip:", repr(e)[:200])
    # 天皇杯: 注入 API-Football 盘口 (snapshots.csv apifb 行)
    try:
        n2 = _apifb_emperor_inject(events)
        print("API-FB 天皇杯盘口注入:", n2)
    except Exception as e:
        print("apifb inject skip:", repr(e)[:200])
    info_map = su._load_match_info_map()
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
    # 汇总
    from collections import Counter
    bb_cnt = Counter()
    veto = 0
    for o in out:
        if o.get("best_bet"):
            bb_cnt[o["best_bet"].get("star")] += 1
        if o.get("vetoed"):
            veto += 1
    print("BEST 星级分布:", dict(bb_cnt), "| 否决:", veto, "| 有盘(非error且非缺盘):", sum(1 for o in out if o.get("dir_odds")))

if __name__ == "__main__":
    main()
