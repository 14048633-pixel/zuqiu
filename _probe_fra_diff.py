# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
from datetime import datetime, timezone
ts, lavg, index = su.load_team_stats()
_orig_avg = su.recent_league_avg
su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
def _mk(home, away):
    return {"id": "t", "league": "法甲", "home": home, "away": away,
            "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
            "snap": "2026-08-16T10:00:00Z", "h2h": {"home": 2.0, "draw": 3.4, "away": 3.6},
            "spread": {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
            "totals": {"line": 2.5, "over_price": 1.95, "under_price": 1.95}}
_save = su.CAL["法甲"].get("ou_strength_adj")
for h, a, tag in [("Nantes", "Auxerre", "弱弱"), ("Lorient", "Troyes", "混合")]:
    r_on = su.analyze_match(_mk(h, a), ts, lavg, index)
    su.CAL["法甲"]["ou_strength_adj"] = {}
    r_off = su.analyze_match(_mk(h, a), ts, lavg, index)
    su.CAL["法甲"]["ou_strength_adj"] = _save
    on = next(b for b in r_on["bets"] if b["name"] == "大2.50")
    off = next(b for b in r_off["bets"] if b["name"] == "大2.50")
    print("%s %s: on=%.4f off=%.4f diff=%.4f (<=-0.03: %s)" % (tag, h, on["prob"], off["prob"], on["prob"]-off["prob"], on["prob"]-off["prob"] <= -0.03))
su.recent_league_avg = _orig_avg
