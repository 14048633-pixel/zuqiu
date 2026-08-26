# -*- coding: utf-8 -*-
import io, os, json, urllib.request, time
from datetime import datetime, timezone
env = {}
for line in io.open(r".env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1); env[k.strip()] = v.split("#")[0].strip().strip(chr(34)).strip(chr(39))
tok = env["BZZOIRO_API_KEY"]
def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
    return json.load(urllib.request.urlopen(req, timeout=40))
F = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
T = datetime(2026, 8, 26, 15, 0, tzinfo=timezone.utc)
events = []
for date in ("2026-08-25", "2026-08-26"):
    u = "https://sports.bzzoiro.com/api/v2/events/?date=%s&page_size=200" % date
    while u:
        try:
            d = get(u)
        except Exception as e:
            print("ERR", date, repr(e)[:120]); break
        for ev in d.get("results", []):
            try:
                ed = datetime.fromisoformat(ev["event_date"].replace("Z", "+00:00"))
            except Exception:
                continue
            if F <= ed <= T:
                events.append(ev)
        u = d.get("next")
        if u: time.sleep(0.15)
print("BSD window events:", len(events))
from collections import Counter
print(Counter(e.get("league", "?") for e in events).most_common())
with io.open("_bsd_next24h.json", "w", encoding="utf-8") as f:
    json.dump(events, f, ensure_ascii=False, indent=1)
# 打印含伤停/教练的行
for e in sorted(events, key=lambda x: x.get("event_date", "")):
    up = e.get("unavailable_players") or []
    print(e["event_date"][11:16], "|", e.get("league"), "|", e["home_team"], "vs", e["away_team"],
          "| 伤停%d" % len(up), "| 教练:", (e.get("home_coach") or {}).get("name", "?") if isinstance(e.get("home_coach"), dict) else e.get("home_coach"),
          "vs", (e.get("away_coach") or {}).get("name", "?") if isinstance(e.get("away_coach"), dict) else e.get("away_coach"))
