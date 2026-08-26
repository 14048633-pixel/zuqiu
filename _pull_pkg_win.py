# -*- coding: utf-8 -*-
"""映射窗口34场 -> BSD event id 并拉 match_package"""
import io, os, sys, json, glob, unicodedata, re
from datetime import datetime, timezone
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
os.chdir(ROOT)
import pull_match_package as pmp

def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def pt(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

scans = sorted(glob.glob(r"analysis_records/scan_next24h_*.json"), key=os.path.getmtime)
d = json.load(io.open(scans[-1], encoding="utf-8"))
bsd = json.load(io.open(r"_bsd_next24h.json", encoding="utf-8"))
print("window matches:", len(d), "bsd events:", len(bsd))

idx = {}
for e in bsd:
    idx.setdefault((_norm(e["home_team"]), _norm(e["away_team"])), []).append(e)

matched = []
unmatched = []
for o in d:
    key = (_norm(o["home"]), _norm(o["away"]))
    cands = idx.get(key, [])
    if not cands:
        unmatched.append((o["ko_bjt"], o["league"], o["home"], o["away"], "no_name"))
        continue
    best = None
    t0 = pt(o["ko_utc"])
    for e in cands:
        try:
            diff = abs((pt(e["event_date"]) - t0).total_seconds())
        except Exception:
            diff = 1e9
        if best is None or diff < best[0]:
            best = (diff, e)
    if best is None or best[0] > 3600:
        unmatched.append((o["ko_bjt"], o["league"], o["home"], o["away"], "time_mismatch"))
        continue
    e = best[1]
    matched.append({
        "id": e["id"],
        "league": o["league"],
        "kickoff": o["ko_bjt"],
        "kickoff_iso": e["event_date"],
        "home": o["home"],
        "away": o["away"],
        "home_id": e.get("home_team_id"),
        "away_id": e.get("away_team_id"),
    })
print("matched:", len(matched), "unmatched:", len(unmatched))
for x in unmatched:
    print("  UNMATCH", x)

ok = skip = fail = 0
for m in matched:
    try:
        res = pmp.build_package(m)
        if res == "skip_existing":
            skip += 1
        elif res.startswith("ok"):
            ok += 1
            print("  OK %s %s %s vs %s" % (m["kickoff"], m["league"], m["home"], m["away"]))
        else:
            fail += 1
            print("  FAIL", m["league"], m["home"], m["away"], res)
    except Exception as e:
        fail += 1
        print("  ERR", m["league"], m["home"], m["away"], type(e).__name__, str(e)[:100])
print("done ok=%d skip=%d fail=%d" % (ok, skip, fail))
