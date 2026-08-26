# -*- coding: utf-8 -*-
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
from api_router import OddsApiRouter
from live_odds import fetch_league_odds
import urllib.request, urllib.error

router = OddsApiRouter(project_root=ROOT)
for i, (k, src) in enumerate(router.keys):
    url = "https://api.the-odds-api.com/v4/sports/?apiKey=" + k
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            used = resp.headers.get("x-requests-used")
            rem = resp.headers.get("x-requests-remaining")
            print(f"{i} {src} {k[:8]} OK used={used} rem={rem}")
    except urllib.error.HTTPError as e:
        print(f"{i} {src} {k[:8]} HTTP {e.code}")
    except Exception as e:
        print(f"{i} {src} {k[:8]} ERR {type(e).__name__}")
