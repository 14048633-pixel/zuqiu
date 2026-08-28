# -*- coding: utf-8 -*-
import os
import sys, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
url = "https://v3.football.api-sports.io/status"
req = urllib.request.Request(url, headers={"x-apisports-key": os.environ.get("FOOTBALL_API_KEY", "")})
with urllib.request.urlopen(req, timeout=30) as r:
    body = json.loads(r.read().decode("utf-8", "replace"))
    print("remaining:", r.headers.get("x-ratelimit-remaining"), "| plan:", body.get("response", {}).get("account", {}).get("plan"))
