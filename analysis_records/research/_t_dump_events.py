# -*- coding: utf-8 -*-
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
from live_odds import fetch_league_odds
KEY = "8365acfd25968d4917f29474c2df5b2c"
for sp in ["soccer_saudi_arabia_pro_league", "soccer_argentina_primera_division", "soccer_spain_la_liga"]:
    events, quota = fetch_league_odds(KEY, sp, markets="h2h,spreads,totals", regions="eu,uk,us", timeout=60)
    print("###", sp, "n:", len(events), "quota_rem:", quota.get("remaining"))
    for ev in events:
        print("  ", ev.get("commence_time"), "|", ev.get("home_team"), "vs", ev.get("away_team"), "| bk:", len(ev.get("bookmakers") or []))
