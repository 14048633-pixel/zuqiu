# -*- coding: utf-8 -*-
"""窗口内(18:00-24H)比赛专项分析: 过滤 parse_snapshots 到窗口 + 注入 BSD event id
输出: analysis_records/scan24h_analysis_20260823_1824.json
"""
import os, sys, io, json, glob, collections
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
os.chdir(ROOT)

import scan_upcoming as su
import coach_quant as cq

BJT = timezone(timedelta(hours=8))
FROM = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)   # 08-23 18:00 BJT
TO = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)     # 08-24 18:00 BJT

def _norm_pair(h, a):
    import re, unicodedata
    def n(t):
        t = unicodedata.normalize("NFKD", str(t)).lower().replace("-", " ").replace(".", " ")
        return " ".join(sorted(set(re.split(r"[^a-z0-9]+", t))))
    return "|".join(sorted([n(h), n(a)]))

# 1) BSD event id 映射: (league, home, away) -> bsd_id
scan = json.load(io.open("analysis_records/scan24h_20260823_1824.json", encoding="utf-8"))
id_map = {}
for m in scan["matches"]:
    id_map[(m["league"], m["home"], m["away"])] = m["id"]
print("scan24h 场次:", len(scan["matches"]))

# 2) parse_snapshots -> 过滤窗口 + 注入 BSD id
events, future_skipped = su.parse_snapshots()
evs = []
seen = {}
for m in events:
    ct = m["ct"]
    if not (FROM <= ct < TO):
        continue
    bsd_id = id_map.get((m["league"], m["home"], m["away"]))
    if bsd_id is not None:
        m["id"] = bsd_id
    m["_to_id"] = m.get("id")
    key = (m["league"], _norm_pair(m["home"], m["away"]), int(ct.timestamp() / 1800))
    # 去重: 同一场(联赛+归一化队名对+30min槽)只保留一场, 优先有 BSD id 的
    cur = seen.get(key)
    if cur is None:
        seen[key] = m
    else:
        cur_has_bsd = str(cur.get("id", "")).isdigit()
        new_has_bsd = bsd_id is not None
        if new_has_bsd and not cur_has_bsd:
            seen[key] = m   # 有 BSD id 的优先(数据包/PKG_BOOST 命中)
evs = list(seen.values())
print("窗口内事件:", len(evs))

try:
    su.set_live_avg_leagues({m["league"] for m in evs})
except Exception:
    pass

team_stats, lavg, index = su.load_team_stats()
info_map = su._load_match_info_map()
_coach_cache = cq.load_cache()

results = []
for m in evs:
    _info = info_map.get((m["league"], m["home"], m["away"]))
    _cm = cq.match_mods(_coach_cache, _info, m["league"]) if (_info and _coach_cache) else {}
    m["coach_mods"] = _cm
    if _info and not _cm and _info.get("bsd_coaches"):
        m["coach_missing"] = True
    r = su.analyze_match(m, team_stats, lavg, index)
    if _info:
        r["info"] = _info
        r["coach"] = _cm
        r["bsd"] = su._bsd_cross_check(r, _info)
        r["formation"] = su._formation_check(r, _info)
        r["injury_pos"] = su._injury_pos_check(r, _info)
    m["result"] = r
    results.append(m)
    bj = m["ct"].astimezone(BJT)
    bb = r["best_bet"]
    bb_s = ("%s %.0f%% EV%+.1f%% ★%d" % (bb["name"], bb["prob"] * 100, bb["ev"] * 100, bb.get("star", 0))) if bb else "-无正EV-"
    di = r.get("direction")
    if di:
        dir_s = "%s %s" % (di["name"], "⛔否决" if di.get("vetoed") else "")
        if di.get("draw_warn"):
            dir_s += " ⚠预警%.0f%%" % di["draw_warn"]["market_draw_prob"]
    else:
        dir_s = "-无盘口-"
    risk_s = (" 风险:" + ",".join(r["risk_tags"])) if r["risk_tags"] else ""
    print("%s %-4s %s vs %s | λ%.2f/%.2f | 方向[%s] | BEST[%s]%s" % (
        bj.strftime("%m-%d %H:%M"), m["league"], m["home"], m["away"],
        r["lambda"]["home"], r["lambda"]["away"], dir_s, bb_s, risk_s))

out_path = "analysis_records/scan24h_analysis_20260823_1824.json"
with io.open(out_path, "w", encoding="utf-8") as f:
    json.dump({"timestamp": "2026-08-23T17:55:00+08:00", "type": "scan24h(18:00-24H) 82场专项分析",
               "window": {"from": FROM.isoformat(), "to": TO.isoformat()},
               "matches": [{k: (m[k].isoformat() if k == "ct" else m[k]) for k in ("id", "league", "home", "away", "ct", "snap", "result")} for m in results]},
              f, ensure_ascii=False, indent=1)
print("\nsaved:", out_path)

n_bet = sum(1 for m in results if m["result"]["best_bet"])
print("可出best_bet:", n_bet, "/", len(results))
_veto = sum(1 for m in results if any("否决" in t for t in m["result"].get("risk_tags", [])))
print("硬否决:", _veto)
