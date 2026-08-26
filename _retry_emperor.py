# -*- coding: utf-8 -*-
"""天皇杯缺失 27 场重试"""
import os, sys, json, io, csv, time, re, urllib.request
from datetime import datetime, timezone
ROOT = r"D:\足球分析"
env = {}
for l in io.open(os.path.join(ROOT, ".env"), encoding="utf-8-sig"):
    if "=" in l and not l.strip().startswith("#"):
        k, v = l.split("=", 1); env[k.strip()] = v.split("#")[0].strip().strip('"').strip("'")
KEY = env["FOOTBALL_API_KEY"]
BASE = "https://v3.football.api-sports.io"
SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
MAP = os.path.join(ROOT, "analysis_records", "apifb_fixture_map_emperor_20260826.json")

def get(url):
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace")), r.headers.get("x-ratelimit-remaining", "?")

# 读已覆盖
rows = list(csv.DictReader(io.open(SNAP, encoding="utf-8-sig")))
covered = set()
for r in rows:
    if r.get("league") == "天皇杯" and r.get("event_id", "").startswith("apifb"):
        covered.add(r["home_team"] + "|" + r["away_team"])

d = json.load(io.open(MAP, encoding="utf-8"))
ms = [m for m in d["matches"] if (m["target_home"] + "|" + m["target_away"]) not in covered]
print("待重试:", len(ms))
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
out_rows = []
for m in ms:
    fid = m["fixture_id"]
    try:
        od, rem = get("%s/odds?fixture=%d" % (BASE, fid))
    except Exception as e:
        print("ERR %s %s vs %s: %r" % (fid, m["target_home"], m["target_away"], e))
        time.sleep(3.0)
        continue
    resp = od.get("response") or []
    if not resp:
        print("NO ODDS | %s vs %s (rem=%s)" % (m["target_home"], m["target_away"], rem))
        time.sleep(3.0)
        continue
    eid = "apifb" + str(fid)
    h, a = m["target_home"], m["target_away"]
    ct = m.get("date") or m["target_ko"]
    for r0 in resp:
        for bk in r0.get("bookmakers") or []:
            bname = bk.get("name") or str(bk.get("id"))
            for b in bk.get("bets") or []:
                nm = b.get("name"); vals = b.get("values") or []
                if nm == "Match Winner":
                    for v in vals:
                        try: price = float(v.get("odd"))
                        except Exception: continue
                        val = v.get("value", "")
                        side = val.lower() if val in ("Home", "Draw", "Away") else None
                        if not side or price <= 1.01: continue
                        out_rows.append([ts, eid, "天皇杯", ct, h, a, "apifb:"+bname, "h2h", (h if side=="home" else a if side=="away" else "Draw"), side, side, "", price, ts])
                elif nm == "Goals Over/Under":
                    for v in vals:
                        mm = re.match(r"^\s*(Over|Under)\s+(\d+(?:\.\d+)?)\s*$", v.get("value", ""), re.I)
                        if not mm: continue
                        try: price = float(v.get("odd"))
                        except Exception: continue
                        if price <= 1.01: continue
                        out_rows.append([ts, eid, "天皇杯", ct, h, a, "apifb:"+bname, "totals", mm.group(2), ("over" if mm.group(1).lower()=="over" else "under"), mm.group(1).lower(), float(mm.group(2)), price, ts])
    print("OK | %s vs %s (rem=%s)" % (m["target_home"], m["target_away"], rem))
    time.sleep(3.0)
print("新行:", len(out_rows))
if out_rows:
    with open(SNAP, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        for row in out_rows:
            w.writerow(row)
    print("appended")
