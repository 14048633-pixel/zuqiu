# -*- coding: utf-8 -*-
import json, os, sys, io
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
from live_odds import fetch_league_odds
from api_router import OddsApiRouter
router = OddsApiRouter(project_root=ROOT)
key = router.keys[0][0]
for sport in ("soccer_argentina_primera_division", "soccer_uefa_champs_league_qualification"):
    events, quota = fetch_league_odds(key, sport, markets="h2h", regions="eu,uk,us", timeout=40)
    print("===", sport, "events", len(events))
    for ev in events:
        print(" ", ev.get("commence_time"), "|", repr(ev.get("home_team")), "vs", repr(ev.get("away_team")))
