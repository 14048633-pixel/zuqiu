# -*- coding: utf-8 -*-
import os
"""补齐 7 场: the-odds-api(Al-Hazem/Al-Faisaly/Aldosivi/Estudiantes/Betis) + API-Football(Petrolul/Jaguares)"""
import sys, os, json, io, time, urllib.request
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
from live_odds import fetch_league_odds

OUT = os.path.join(ROOT, "analysis_records", "research")
f = json.load(io.open(os.path.join(OUT, "odds_live_0822_matched_v2.json"), encoding="utf-8"))
results = {str(k): v for k, v in f["matches"].items()}

KEY = "8365acfd25968d4917f29474c2df5b2c"
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---- the-odds-api 补 5 场 ----
todo = [
    ("soccer_saudi_arabia_pro_league", "222619", "Al-Hazem", "Diriyah Club", "2026-08-21T16:15:00Z"),
    ("soccer_saudi_arabia_pro_league", "222620", "Al-Faisaly KSA FC", "Neom", "2026-08-21T18:00:00Z"),
    ("soccer_argentina_primera_division", "223596", "Aldosivi Mar del Plata", "Union Santa Fe", "2026-08-21T17:30:00Z"),
    ("soccer_argentina_primera_division", "223603", "Estudiantes de Río Cuarto", "San Lorenzo", "2026-08-21T23:00:00Z"),
    ("soccer_spain_la_liga", "213538", "Real Betis", "Real Sociedad", "2026-08-21T19:00:00Z"),
]
from collections import defaultdict
by_sport = defaultdict(list)
for sp, eid, h, a, ko in todo:
    by_sport[sp].append((eid, h, a, ko))
for sp, lst in by_sport.items():
    events, quota = fetch_league_odds(KEY, sp, markets="h2h,spreads,totals", regions="eu,uk,us", timeout=60)
    print("sport", sp, "n:", len(events), "quota_rem:", quota.get("remaining"))
    for eid, h, a, ko in lst:
        ev = None
        for e in events:
            if e.get("home_team") == h and e.get("away_team") == a and e.get("commence_time") == ko:
                ev = e; break
        if ev is None:
            print("  STILL NO MATCH:", eid, h, "vs", a)
        else:
            results[eid] = {"source": "the-odds-api", "sport": sp, "pulled_at": ts,
                            "home_team": ev["home_team"], "away_team": ev["away_team"],
                            "commence_time": ev.get("commence_time"),
                            "bookmakers": ev.get("bookmakers") or []}
            print("  OK:", eid, h, "vs", a, "bk:", len(ev.get("bookmakers") or []))
    time.sleep(1.0)

# ---- API-Football 补 2 场 ----
AFB_KEY = os.environ.get("FOOTBALL_API_KEY", "")
for eid, fid, h, a in [("214569", 1565227, "Petrolul Ploiesti", "Rapid"), ("220055", 1549740, "Jaguares", "Chico")]:
    url = "https://v3.football.api-sports.io/odds?fixture=%d" % fid
    req = urllib.request.Request(url, headers={"x-apisports-key": AFB_KEY})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
            rem = r.headers.get("x-ratelimit-remaining")
            print("AFB ok", fid, h, "quota_rem:", rem)
            results[eid] = {"source": "api-football", "sport": "apifb", "pulled_at": ts,
                            "home_team": h, "away_team": a, "commence_time": "",
                            "bookmakers": body.get("response") or []}
    except Exception as e:
        print("AFB ERR", fid, h, repr(e))
    time.sleep(2.0)

out_fn = os.path.join(OUT, "odds_live_0822_matched_final.json")
json.dump({"pulled_at": ts, "n_matched": len(results), "matches": results},
          io.open(out_fn, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", out_fn, "n_matched:", len(results))
for eid in sorted(results, key=lambda x: int(x)):
    print(eid, results[eid]["home_team"], "vs", results[eid]["away_team"], results[eid]["source"])
