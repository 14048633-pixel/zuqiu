# 2) 构造 scan24h 比赛列表 (从 _bsd_next24h.json, 过滤 postponed)
import json, io, sys, os
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BJT = timezone(timedelta(hours=8))
evs = json.load(io.open(r"D:\足球分析\_bsd_next24h.json", encoding="utf-8"))
matches = []
skipped = 0
for e in evs:
    if e.get("status") not in ("notstarted", "scheduled", ""):
        skipped += 1
        continue
    ct = e.get("event_date")
    try:
        dt = datetime.fromisoformat(ct.replace("Z", "+00:00"))
    except Exception:
        continue
    matches.append({
        "id": e["id"],
        "league": None,
        "kickoff": dt.astimezone(BJT).strftime("%m-%d %H:%M"),
        "kickoff_iso": ct,
        "ct": ct,
        "home": e.get("home_team"),
        "away": e.get("away_team"),
        "home_id": e.get("home_team_id"),
        "away_id": e.get("away_team_id"),
    })
matches.sort(key=lambda x: x["ct"])
out = {"window": "2026-08-25 23:00 BJT -> 08-26 23:00 BJT", "matches": matches}
fp = r"D:\足球分析\analysis_records\scan24h_20260826_0000.json"
json.dump(out, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("过滤 postponed:", skipped, "| 待建包:", len(matches))
print("保存:", fp)
for m in matches[:60]:
    print(m["kickoff"], m.get("home"), "vs", m.get("away"), "id", m["id"])
