# -*- coding: utf-8 -*-
import sys, io, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tok = ""
for line in io.open(r"D:\足球分析\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")
url = "https://sports.bzzoiro.com/api/v2/events/?status=upcoming&date_from=2026-08-18&date_to=2026-08-20&limit=200"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
try:
    j = json.load(urllib.request.urlopen(req, timeout=30))
    res = j.get("results", j) if isinstance(j, dict) else j
    print("count:", j.get("count") if isinstance(j, dict) else len(j))
    print("n results:", len(res))
    for e in res[:8]:
        print(json.dumps({k: e.get(k) for k in ("id", "league_name", "home_team", "away_team", "kickoff_time", "status")}, ensure_ascii=False))
except Exception as e:
    print("ERR", type(e).__name__, e)
