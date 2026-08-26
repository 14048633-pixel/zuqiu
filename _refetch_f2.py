# -*- coding: utf-8 -*-
import csv, io, json, os, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
DATA_DIR = os.path.join(ROOT, "data", "raw", "football_data")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
WINDOWS = [("20240801", "20241231"), ("20250101", "20250630"), ("20250701", "20251231")]

def fetch(code, d0, d1):
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s-%s&limit=1000" % (code, d0, d1)
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8"))
        except Exception:
            if i == 2:
                raise
            time.sleep(3)

rows, seen = [], set()
for d0, d1 in WINDOWS:
    data = fetch("fra.2", d0, d1)
    for ev in data.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        st = (comp.get("status") or {}).get("type") or {}
        if st.get("name") != "STATUS_FULL_TIME":
            continue
        cs = comp.get("competitors") or []
        home = next((c for c in cs if c.get("homeAway") == "home"), None)
        away = next((c for c in cs if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        date = (ev.get("date") or "")[:10].replace("-", "/")
        h = (home["team"].get("displayName") or "").strip()
        a = (away["team"].get("displayName") or "").strip()
        if not h or not a:
            continue
        key = (date, h, a)
        if key in seen:
            continue
        seen.add(key)
        y, m = int(date[:4]), int(date[5:7])
        season = "2024/2025" if (y, m) < (2025, 8) else "2025/2026"
        rows.append(["F2", date, h, a, int(home.get("score") or 0), int(away.get("score") or 0), season])
    time.sleep(1.0)

from collections import Counter
out = os.path.join(DATA_DIR, "espn_法乙_2024_2025_results.csv")
with io.open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "Season"])
    for r in sorted(rows, key=lambda x: (x[6], x[1])):
        w.writerow(r)
print("法乙重拉完成: %d场 | 赛季分布 %s" % (len(rows), dict(Counter(r[6] for r in rows))))
print("日期范围:", sorted(r[1] for r in rows)[0], "->", sorted(r[1] for r in rows)[-1])
