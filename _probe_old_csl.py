# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
from datetime import datetime, timezone

ts, lavg, index = su.load_team_stats()
_orig_avg = su.recent_league_avg
_orig_cal = su.CAL["中超"]["league_avg"]
su.CAL["中超"]["league_avg"] = 3.518   # 回退旧值
su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.518, 30), "英超": (2.8719, 30)}
_oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
for _c in su.CAL.values():
    _c["ou_strength_adj"] = {}

def _mk(home, away, league, h2h, sp, tt):
    return {"id": "t", "league": league, "home": home, "away": away,
            "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
            "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}

H2H_DW = {"home": 2.5, "draw": 3.4, "away": 3.0}
m5 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW, None,
         {"line": 2.5, "over_price": 2.05, "under_price": 1.78})
r5 = su.analyze_match(m5, ts, lavg, index)
print("== m5 旧中超3.518")
for b in r5.get("bets") or []:
    print("   %-12s prob=%.4f raw=%s ev=%+.4f" % (b.get("name"), b.get("prob",0), b.get("prob_raw"), b.get("ev",0)))
print("   best:", (r5.get("best_bet") or {}).get("name"))
print("   direction:", (r5.get("direction") or {}).get("name"))
print("   risk_tags:", r5.get("risk_tags"))

su.CAL["中超"]["league_avg"] = _orig_cal
su.recent_league_avg = _orig_avg
for _k, _v in _oua_save.items():
    su.CAL[_k]["ou_strength_adj"] = _v
