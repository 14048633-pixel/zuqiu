# -*- coding: utf-8 -*-
import sys, io, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tok = ""
for line in io.open(r"D:\足球分析\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")
url = "https://sports.bzzoiro.com/api/v2/leagues/?limit=200"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
j = json.load(urllib.request.urlopen(req, timeout=30))
res = j.get("results", [])
print("count:", j.get("count"), "n:", len(res))
print(json.dumps(res[0], ensure_ascii=False, indent=1)[:1200])
