# -*- coding: utf-8 -*-
import sys, io, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tok = ""
for line in io.open(r"D:\足球分析\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")
req = urllib.request.Request("https://sports.bzzoiro.com/api/v2/leagues/?limit=200",
                             headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
j = json.load(urllib.request.urlopen(req, timeout=40))
res = j.get("results") or []
print("n:", len(res))
for x in sorted(res, key=lambda z: (z.get("country") or "", z.get("name") or "")):
    print(x["id"], "|", (x.get("name") or ""), "|", (x.get("country") or ""), "| women:", x.get("is_women"))
