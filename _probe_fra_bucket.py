# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
from datetime import datetime, timezone
ts, lavg, index = su.load_team_stats()
_orig_avg = su.recent_league_avg
su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
def _mk(home, away, h2h, sp, tt):
    return {"id": "t", "league": "法甲", "home": home, "away": away,
            "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
            "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}
pairs = [("Paris Saint-Germain", "Marseille"), ("PSG", "Lyon"), ("Lorient", "Troyes"),
         ("Nantes", "Auxerre"), ("Lens", "Monaco"), ("Saint-Etienne", "Reims"),
         ("Brest", "Clermont"), ("Angers", "Metz")]
for h, a in pairs:
    m = _mk(h, a, {"home": 2.0, "draw": 3.4, "away": 3.6},
            {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
            {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
    r = su.analyze_match(m, ts, lavg, index)
    ov = next((b for b in r["bets"] if b["name"] == "大2.50"), None)
    print("%-28s bucket=%s 大prob=%s" % (h + " vs " + a, (ov or {}).get("ou_bucket"), (ov or {}).get("prob")))
su.recent_league_avg = _orig_avg
