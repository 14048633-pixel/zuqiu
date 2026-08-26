# -*- coding: utf-8 -*-
import sys, os, json, io
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
from api_router import OddsApiRouter
from live_odds import fetch_league_odds

router = OddsApiRouter(project_root=ROOT)
key = router.keys[0][0]
print("key:", key[:8], "n_keys:", len(router.keys))
try:
    events, quota = fetch_league_odds(key, "soccer", markets="h2h,spreads,totals", regions="eu,uk,us", timeout=60)
except Exception as e:
    print("ERR:", repr(e)); sys.exit(1)
print("quota:", quota, "n_events:", len(events))
targets = [
    ("Al-Riyadh","Al-Nassr","2026-08-21T16:00:00Z"),
    ("SV Waldhof Mannheim","1. FC Kaiserslautern","2026-08-21T16:00:00Z"),
    ("Arsenal","Coventry City","2026-08-21T19:00:00Z"),
    ("Real Betis","Real Sociedad","2026-08-21T19:00:00Z"),
    ("Olympique de Marseille","RC Strasbourg","2026-08-21T18:45:00Z"),
]
for ev in events:
    h = ev.get("home_team",""); a = ev.get("away_team",""); ct = ev.get("commence_time","")
    for th, ta, tc in targets:
        if th.lower() in h.lower() and ta.lower() in a.lower():
            print("MATCH:", h, "vs", a, "| ct:", ct, "| n_bk:", len(ev.get("bookmakers") or []))
            break
