# -*- coding: utf-8 -*-
import io, sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
from datetime import datetime, timezone

ts, lavg, index = su.load_team_stats()
_orig_avg = su.recent_league_avg
su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30), "墨超": (2.83, 30), "荷甲": (3.15, 30), "英冠": (2.51, 30)}
_oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
for _c in su.CAL.values():
    _c["ou_strength_adj"] = {}

def _mk(home, away, league, h2h, sp, tt):
    return {"id": "t", "league": league, "home": home, "away": away,
            "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
            "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}

def dump(tag, r):
    print("== %s | best=%s star=%s" % (tag, (r.get("best_bet") or {}).get("name"), r.get("star")))
    for b in r.get("bets") or []:
        print("   %-16s prob=%.4f ev=%+.4f raw=%s" % (b.get("name"), b.get("prob",0), b.get("ev",0), b.get("prob_raw")))
    print("   notes:", [n for n in r.get("notes",[]) if "禁" in n or "封顶" in n or "预警" in n or "降星" in n][:6])

H2H = {"home": 2.0, "away": 3.4, "draw": 3.6}

# 1) 客强主受 (Casa Pia vs Benfica 葡超)
m1b = _mk("Casa Pia", "Benfica", "葡超", {"home": 16.5, "draw": 7.2, "away": 1.24},
          {"hdp_home": 1.5, "home_price": 2.14, "away_price": 1.68},
          {"line": 2.5, "over_price": 1.6, "under_price": 2.3})
r1b = su.analyze_match(m1b, ts, lavg, index)
dump("客强主受 r1b", r1b)

# 2) r1b2 with SMALL_250_HIGH_EV=0.10
_o = su.SMALL_250_HIGH_EV; su.SMALL_250_HIGH_EV = 0.10
r1b2 = su.analyze_match(m1b, ts, lavg, index)
su.SMALL_250_HIGH_EV = _o
dump("r1b2 阈值0.10", r1b2)

# 3) 概率禁带 (山东泰山 vs 青岛西海岸 中超 -1.0)
m2 = _mk("Shandong Taishan", "Qingdao West Coast", "中超", H2H,
         {"hdp_home": -1.0, "home_price": 1.95, "away_price": 1.90},
         {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
r2 = su.analyze_match(m2, ts, lavg, index)
dump("概率禁带 r2", r2)

# 4) 规则6中浅让 (申花 vs 河南 -0.5)
m3 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H,
         {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
         {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
r3 = su.analyze_match(m3, ts, lavg, index)
dump("中浅让 r3", r3)

# 5) 预警规则③ (申花 vs 河南, spread None, totals 2.5)
H2H_DW = {"home": 2.5, "draw": 3.4, "away": 3.0}
m5 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW, None,
         {"line": 2.5, "over_price": 2.05, "under_price": 1.78})
r5 = su.analyze_match(m5, ts, lavg, index)
dump("预警规则③ m5", r5)

# 6) ⑧A (申花 vs 河南 home 2.0 -0.5)
m6 = _mk("Shanghai Shenhua FC", "Henan FC", "中超",
         {"home": 2.0, "away": 3.4, "draw": 3.6},
         {"hdp_home": -0.5, "home_price": 2.05, "away_price": 2.05},
         {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
r6 = su.analyze_match(m6, ts, lavg, index)
dump("⑧A m6", r6)

su.recent_league_avg = _orig_avg
for _k, _v in _oua_save.items():
    su.CAL[_k]["ou_strength_adj"] = _v
