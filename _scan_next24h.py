# -*- coding: utf-8 -*-
"""未来24h窗口扫描: 当前配置 + 最新快照 -> 方向报告"""
import sys, os, io, json, collections
from datetime import datetime, timezone, timedelta
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su

BJT = timezone(timedelta(hours=8))
NOW = datetime.now(timezone.utc)
T = NOW + timedelta(hours=24)

def main():
    su.recent_league_avg = lambda: {}   # 未来场次无前视, 但关闭平移让结果=配置基准(与回测一致)
    team_stats, lavg, index = su.load_team_stats()
    recs, fs = su.parse_snapshots()
    try:
        _m = su.bsd_odds_merge(recs)
        print("BSD consensus 覆盖场次:", _m)
    except Exception as _e:
        print("bsd_odds_merge skip:", _e)
    print("events:", len(recs))
    info_map = su._load_match_info_map()
    try:
        import coach_quant as cq
        _coach_cache = cq.load_cache()
    except Exception:
        _coach_cache = {}
    rows = []
    for m in recs:
        try:
            ct = m["ct"]
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if not (NOW - timedelta(minutes=30) <= ct <= T):
            continue
        _info = info_map.get((m["league"], m["home"], m["away"]))
        _cm = {}
        if _info and _coach_cache:
            try:
                _cm = cq.match_mods(_coach_cache, _info, m["league"])
            except Exception:
                _cm = {}
        m["coach_mods"] = _cm
        try:
            r = su.analyze_match(m, team_stats, lavg, index)
        except Exception as e:
            r = {"error": str(e)}
        rows.append({"match": m, "result": r})
    rows.sort(key=lambda x: x["match"]["ct"])
    out = []
    for x in rows:
        m = x["match"]; r = x["result"]
        bj = m["ct"].astimezone(BJT)
        di = r.get("direction") or {}
        bb = r.get("best_bet")
        out.append({
            "ko_bjt": bj.strftime("%m-%d %H:%M"),
            "ko_utc": m["ct"].isoformat(),
            "league": m["league"], "home": m["home"], "away": m["away"],
            "lambda": r.get("lambda"),
            "wdl": r.get("wdl"),
            "market_fair": r.get("market_fair"),
            "direction": di.get("name"), "dir_prob": di.get("prob"), "dir_odds": di.get("odds"),
            "dir_ev": di.get("ev"), "vetoed": di.get("vetoed"), "veto_reason": di.get("veto_reason"),
            "draw_warn": r.get("draw_warn"),
            "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "risk_tags": r.get("risk_tags"),
            "dir_consistency": r.get("dir_consistency"),
            "best_bet": ({"name": bb["name"], "prob": bb.get("prob"), "odds": bb.get("odds"),
                          "ev": bb.get("ev"), "star": bb.get("star"), "ev_tier": bb.get("ev_tier")}
                         if isinstance(bb, dict) and bb.get("name") else None),
            "bets": [{"name": b["name"], "prob": b.get("prob"), "odds": b.get("odds"),
                      "ev": b.get("ev"), "star": b.get("star"), "ev_tier": b.get("ev_tier")}
                     for b in (r.get("bets") or [])],
            "error": r.get("error"),
            "notes": r.get("notes"),
        })
    ts = datetime.now(BJT).strftime("%Y%m%d_%H%M")
    with io.open(os.path.join(ROOT, "analysis_records", "scan_next24h_%s.json" % ts), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved analysis_records/scan_next24h_%s.json  n=%d" % (ts, len(out)))
    # 摘要
    n_veto = sum(1 for o in out if o["vetoed"])
    n_dir = sum(1 for o in out if o["direction"])
    n_bb = sum(1 for o in out if o["best_bet"])
    print("总场次=%d 有方向=%d 被否决=%d best_bet=%d" % (len(out), n_dir, n_veto, n_bb))
    by_league = collections.Counter(o["league"] for o in out)
    print("按联赛:", dict(by_league))

if __name__ == "__main__":
    main()
