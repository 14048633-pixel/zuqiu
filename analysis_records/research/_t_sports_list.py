# -*- coding: utf-8 -*-
import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
url = "https://api.the-odds-api.com/v4/sports/?apiKey=8365acfd25968d4917f29474c2df5b2c"
req = urllib.request.Request(url, headers={"Accept": "application/json"})
data = json.load(urllib.request.urlopen(req, timeout=30))
for s in data:
    k = s["key"]
    if k.startswith("soccer"):
        print(k, "|", s["title"])
