# -*- coding: utf-8 -*-
import sys, io, json, os, unicodedata
sys.path.insert(0, r"D:\足球分析\prediction_v2")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import scan_upcoming as su

team_stats, lavg, index = su.load_team_stats()
events, future_skipped = su.parse_snapshots(path=r"D:\足球分析\analysis_records\snapshots_live7_20260823.csv")
ev_list = list(events.values()) if isinstance(events, dict) else events

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).lower()
    return " ".join(s.split())

targets = [
    ("西甲", "Atletico Madrid", "Villarreal"),
    ("法甲", "Le Havre", "AS Monaco"),
    ("智利甲", "La Serena", "Cobresal"),
    ("波甲", "Pogon Szczecin", "Wisla Krakow"),
    ("意乙", "Palermo", "Juve Stabia"),
    ("巴甲", "Chapecoense", "Sao Paulo"),
    ("墨超", "Pumas UNAM", "Necaxa"),
]
info_map = su._load_match_info_map()
coach_cache = su.cq.load_cache()

out = []
for lg, th, ta in targets:
    m = None
    for ev in ev_list:
        if str(ev.get("league")) != lg:
            continue
        hh, aa = norm(ev.get("home", "")), norm(ev.get("away", ""))
        nth, nta = norm(th), norm(ta)
        if nth in hh and nta in aa:
            m = ev
            break
    if m is None:
        print("!! 未找到:", lg, th, ta)
        for ev in ev_list:
            if str(ev.get("league")) == lg:
                print("   候选:", ev.get("home"), "vs", ev.get("away"))
        continue
    _info = info_map.get((m["league"], m["home"], m["away"]))
    _cm = su.cq.match_mods(coach_cache, _info, m["league"]) if (_info and coach_cache) else {}
    m["coach_mods"] = _cm
    r = su.analyze_match(m, team_stats, lavg, index)
    if _info:
        r["info"] = _info; r["coach"] = _cm
        r["bsd"] = su._bsd_cross_check(r, _info)
        r["formation"] = su._formation_check(r, _info)
        r["injury_pos"] = su._injury_pos_check(r, _info)
    m["result"] = r
    bb = r.get("best_bet")
    di = r.get("direction") or {}
    print("="*80)
    print("[%s] %s vs %s | %s" % (m["league"], m["home"], m["away"], m.get("ct")))
    print("  λ:", r["lambda"], "| 模型WDL:", r["wdl"], "| 市场WDL:", r["market_fair"])
    print("  snap_age_h:", r.get("snap_age_h"), "| 否决:", di.get("vetoed"), di.get("veto_reason"))
    print("  BEST:", json.dumps(bb, ensure_ascii=False) if bb else None)
    print("  方向组:", r.get("dir_consistency", {}).get("level"), "| 风险:", r.get("risk_tags"))
    for b in r.get("bets", []):
        print("     ", b["name"], "p%.1f%%" % (b["prob"]*100), "@", b["odds"], "EV%+.1f%%" % (b["ev"]*100), b.get("star",""), b.get("ev_tier",""))
    out.append({"league": m["league"], "home": m["home"], "away": m["away"], "ct": m["ct"].isoformat(), "result": r})

with io.open(r"D:\足球分析\analysis_records\rescan_live7_20260823.json", "w", encoding="utf-8") as f:
    json.dump({"matches": out}, f, ensure_ascii=False, indent=1)
print("\nsaved rescan_live7_20260823.json, 场次:", len(out))
