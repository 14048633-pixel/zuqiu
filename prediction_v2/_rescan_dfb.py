# -*- coding: utf-8 -*-
"""德国杯基准校准(3.28->3.55)后重扫9场: 仅德国杯, 输出对比
输出: analysis_records/scan24h_dfb_rescan_20260823.json + 终端摘要
"""
import os, sys, io, json, collections
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
os.chdir(ROOT)

import scan_upcoming as su
import coach_quant as cq

BJT = timezone(timedelta(hours=8))
FROM = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
TO = datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)

scan = json.load(io.open("analysis_records/scan24h_analysis_20260823_1824.json", encoding="utf-8"))
id_map = {}
for m in scan["matches"]:
    id_map[(m["league"], m["home"], m["away"])] = m["id"]

events, future_skipped = su.parse_snapshots()
evs = []
for m in events:
    if m["league"] != "德国杯":
        continue
    ct = m["ct"]
    if not (FROM <= ct < TO):
        continue
    bsd_id = id_map.get((m["league"], m["home"], m["away"]))
    if bsd_id is not None:
        m["id"] = bsd_id
    m["_to_id"] = m.get("id")
    evs.append(m)
print("德国杯窗口事件:", len(evs))

su.set_live_avg_leagues({"德国杯"})
team_stats, lavg, index = su.load_team_stats()
info_map = su._load_match_info_map()
_coach_cache = cq.load_cache()

# 旧分析(3.28基准)对比
old = {m["home"]+"|"+m["away"]: m["result"] for m in scan["matches"] if m["league"]=="德国杯"}
print("旧基准场次:", len(old))

rows = []
for m in evs:
    _info = info_map.get((m["league"], m["home"], m["away"]))
    _cm = cq.match_mods(_coach_cache, _info, m["league"]) if (_info and _coach_cache) else {}
    m["coach_mods"] = _cm
    r = su.analyze_match(m, team_stats, lavg, index)
    if _info:
        r["info"] = _info
        r["coach"] = _cm
        r["bsd"] = su._bsd_cross_check(r, _info)
        r["formation"] = su._formation_check(r, _info)
        r["injury_pos"] = su._injury_pos_check(r, _info)
    m["result"] = r
    rows.append(m)
    bj = m["ct"].astimezone(BJT)
    bb = r["best_bet"]
    bb_s = ("%s %.0f%% EV%+.1f%% ★%d" % (bb["name"], bb["prob"]*100, bb["ev"]*100, bb.get("star",0))) if bb else "-无正EV-"
    di = r.get("direction")
    dir_s = ("%s%s" % (di["name"], " ⛔否决" if di.get("vetoed") else "")) if di else "-无盘口-"
    key = m["home"]+"|"+m["away"]
    o = old.get(key)
    ol = ("λ%.2f/%.2f" % (o["lambda"]["home"], o["lambda"]["away"])) if o else "-"
    ob = o.get("best_bet")
    obs = ("%s EV%+.1f%%★%d" % (ob["name"], ob["ev"]*100, ob.get("star",0))) if ob else "-无-"
    print("%s %s vs %s | 新λ%.2f/%.2f(旧%s) | 方向[%s] | BEST[%s] 旧BEST[%s]" % (
        bj.strftime("%m-%d %H:%M"), m["home"], m["away"],
        r["lambda"]["home"], r["lambda"]["away"], ol, dir_s, bb_s, obs))

out_path = "analysis_records/scan24h_dfb_rescan_20260823.json"
with io.open(out_path, "w", encoding="utf-8") as f:
    json.dump({"timestamp": "2026-08-23T18:10:00+08:00", "type": "德国杯基准3.55重扫9场",
               "window": {"from": FROM.isoformat(), "to": TO.isoformat()},
               "matches": [{k: (m[k].isoformat() if k == "ct" else m[k]) for k in ("id", "league", "home", "away", "ct", "snap", "result")} for m in rows]},
              f, ensure_ascii=False, indent=1)
print("\nsaved:", out_path)
n_bet = sum(1 for m in rows if m["result"]["best_bet"])
print("可出best_bet:", n_bet, "/", len(rows))
