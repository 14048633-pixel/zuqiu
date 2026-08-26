# -*- coding: utf-8 -*-
import io, os, json, requests
ROOT = r"D:\足球分析"
env = io.open(os.path.join(ROOT, ".env"), encoding="utf-8").read()
tok = ""
for line in env.splitlines():
    if line.strip().startswith("BZZOIRO_API_KEY="):
        tok = line.split("=",1)[1].strip().strip('"').strip("'")
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Authorization": "Token " + tok}
d = json.load(io.open(ROOT + r"\analysis_records\20260817_scan_upcoming.json", encoding="utf-8"))
for m in d["matches"][:3]:
    eid = m["id"]
    r = requests.get("https://sports.bzzoiro.com/api/v2/events/%s/" % eid, headers=H, timeout=30)
    print(eid, "->", r.status_code)
    if r.status_code == 200:
        j = r.json()
        print("   keys:", list(j.keys())[:20])
        for k in ["home_team","away_team","home_score","away_score","status","event_date"]:
            if k in j: print("   ", k, "=", str(j[k])[:60])
        break
