# -*- coding: utf-8 -*-
"""按主联赛 league_id 映射 div (Tondela->P1葡超, Académica->P2近似, 其余->目标联赛div)
重写 bsd_batch CSV, 确保各队数据落入正确 div, 不污染联赛均值"""
import sys, io, os, json, csv, urllib.request, time, collections
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\足球分析"
tok = ""
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    s = line.strip()
    if s.startswith("BZZOIRO_API_KEY="):
        tok = s.split("=", 1)[1].strip().strip('"').strip("'")

# league_id -> div (2026 主联赛)
LG_DIV = {22: "BG", 80: "CO", 55: "FI", 25: "PL", 23: "RO", 2: "P1", 82: "P2", 17: "SA"}
CUP_LG = {79}

def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                         headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
            return json.load(urllib.request.urlopen(req, timeout=45))
        except Exception as e:
            if i == tries - 1:
                return {"__err__": "%s: %s" % (type(e).__name__, str(e)[:90])}
            time.sleep(2)

import glob
targets = {}
for fp in glob.glob(ROOT + r"\analysis_records\match_package\*.json"):
    try:
        d = json.load(io.open(fp, encoding="utf-8"))
    except Exception:
        continue
    if (d.get("league") or "") not in {"哥甲","Parva Liga","Liga Portugal 2","Veikkausliiga","Ekstraklasa","Superliga","沙超"}:
        continue
    for side in ("home", "away"):
        t, tid = d.get(side), d.get(side + "_id")
        if t and tid and int(tid) not in targets:
            targets[int(tid)] = t
print("目标队伍:", len(targets))

main_lg = {}
for tid in targets:
    j = get("/events/?team_id=%d&status=finished&limit=60" % tid)
    if "__err__" in j:
        print("  ERR", targets[tid], j["__err__"]); continue
    res = j.get("results") or []
    cnt = collections.Counter()
    for e in res:
        dt = str(e.get("event_date") or "")
        if dt[:4] == "2026" and e.get("league_id") not in CUP_LG:
            cnt[e.get("league_id")] += 1
    if cnt:
        main_lg[tid] = cnt.most_common(1)[0][0]
    time.sleep(0.2)

HDR = ["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "Season"]
rows = []
n_ev = 0
errs = []
for i, (tid, tname) in enumerate(sorted(targets.items(), key=lambda x: x[1])):
    lid = main_lg.get(tid)
    div = LG_DIV.get(lid)
    if not div:
        print("  SKIP %s (no div for league %s)" % (tname, lid)); continue
    j = get("/events/?team_id=%d&status=finished&limit=60" % tid)
    if "__err__" in j:
        errs.append((tname, j["__err__"])); print("  ERR", tname, j["__err__"], flush=True); continue
    for e in (j.get("results") or []):
        dt = str(e.get("event_date") or "")
        if dt[:4] != "2026" or e.get("league_id") != lid:
            continue
        hs, as_ = e.get("home_score"), e.get("away_score")
        if hs is None or as_ is None:
            continue
        ht = e.get("home_team") or ""; at = e.get("away_team") or ""
        try:
            dt_fmt = datetime.strptime(dt[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            dt_fmt = "01/01/2026"
        rows.append([div, dt_fmt, ht, at, hs, as_, "2026"])
        n_ev += 1
    if (i + 1) % 10 == 0:
        print("  ... %d/%d | %d" % (i + 1, len(targets), n_ev), flush=True)
    time.sleep(0.3)

fp = ROOT + r"\data\raw\football_data\bsd_batch_20260821.csv"
with io.open(fp, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(HDR); w.writerows(rows)
print("saved", fp, "| events", n_ev, "| errs", len(errs))
