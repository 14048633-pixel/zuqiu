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
eid = 587841
for path in ("/events/%d/odds/" % eid, "/events/%d/prediction/" % eid):
    try:
        j = get(path)
        s = json.dumps(j, ensure_ascii=False)
        print("==== %s ==== len=%d" % (path, len(s)))
        print(s[:1800])
    except Exception as e:
        print("ERR", path, type(e).__name__, e)
