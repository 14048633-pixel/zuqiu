# -*- coding: utf-8 -*-
import sys, io, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tok = ""
for line in io.open(r"D:\足球分析\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")
def get(path):
    req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                 headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
    return json.load(urllib.request.urlopen(req, timeout=40))
for tid in (348, 71, 37):
    try:
        j = get("/events/?team_id=%d&status=finished&limit=3" % tid)
        print("==== team", tid, "count:", j.get("count"))
        res = j.get("results") or []
        for e in res[:2]:
            print("  ", e.get("event_date"), e.get("home_team"), e.get("home_score"), "-", e.get("away_score"), e.get("away_team"))
    except Exception as e:
        print("ERR team", tid, type(e).__name__, e)
