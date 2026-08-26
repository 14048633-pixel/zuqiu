# -*- coding: utf-8 -*-
import io, os, json, urllib.request
ROOT = r"D:\足球分析"
env = {}
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        env["TOK"] = line.split("=",1)[1].strip().strip('"').strip("'")
tok = env["TOK"]
d = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
print("key46 n=", len(d), "| first id:", d[0]["id"], d[0]["home"], "vs", d[0]["away"])
eid = d[0]["id"]
req = urllib.request.Request("https://sports.bzzoiro.com/api/v2/events/%d/odds/" % eid,
                             headers={"User-Agent":"Mozilla/5.0","Authorization":"Token "+tok})
try:
    j = json.load(urllib.request.urlopen(req, timeout=30))
    o = j.get("odds") or {}
    print("odds keys:", list(o.keys())[:15])
    print("sample:", {k: o[k] for k in ["home_win","draw","away_win","over_25_goals","under_25_goals"] if k in o})
    print("ts:", j.get("last_update_at"))
except Exception as e:
    print("ERR", type(e).__name__, str(e)[:120])
