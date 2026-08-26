# -*- coding: utf-8 -*-
"""BSD 按 team_id 批量拉历史赛果 -> 攻防stats (46场重点联赛 92队)
输出: data/raw/football_data/bsd_team_stats_20260818.json
聚合: 近5场w1.0 / 6-10 w0.7 / 11-20 w0.4 / >20 w0.2
"""
import sys, io, os, json, urllib.request, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\足球分析"
tok = ""
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")

def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                         headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except Exception as e:
            if i == tries - 1:
                return {"__err__": "%s: %s" % (type(e).__name__, str(e)[:80])}
            time.sleep(2)

scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
KEY_LG = {"欧冠", "欧联", "欧协联", "中超", "西甲"}
targets = [m for m in scan["matches"] if m["league"] in KEY_LG]
team_ids = {}
for t in targets:
    if t.get("home_id"): team_ids[t["home_id"]] = (t["home"], t["league"])
    if t.get("away_id"): team_ids[t["away_id"]] = (t["away"], t["league"])
print("目标队伍数(去重):", len(team_ids))

def w_of(idx):
    # idx=最近第几场(0-based)
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2

stats = {}
raw_cnt = 0
errs = []
for i, (tid, (tname, tlg)) in enumerate(sorted(team_ids.items(), key=lambda x: x[1][0])):
    j = get("/events/?team_id=%d&status=finished&limit=60" % tid)
    if "__err__" in j:
        errs.append((tname, j["__err__"]))
        print("  ERR %s: %s" % (tname, j["__err__"]), flush=True)
        continue
    res = j.get("results") or []
    if not res:
        errs.append((tname, "no finished events"))
        continue
    # 过滤有比分的场次, 按时间倒序(BSD默认?) 手动排序保险
    scored = []
    for e in res:
        hs, as_ = e.get("home_score"), e.get("away_score")
        if hs is None or as_ is None:
            continue
        try:
            scored.append((e.get("event_date") or "", e.get("home_team"), hs, as_, e.get("away_team")))
        except Exception:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)
    rec = {"home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0], "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0]}
    n = 0
    for idx, (dt, h, hs, as_, a) in enumerate(scored[:40]):
        w = w_of(idx)
        is_home = (h or "").strip().lower() == (tname or "").strip().lower()
        if is_home:
            rec["home_gf"][0] += float(hs) * w; rec["home_gf"][1] += w
            rec["home_ga"][0] += float(as_) * w; rec["home_ga"][1] += w
        else:
            rec["away_gf"][0] += float(as_) * w; rec["away_gf"][1] += w
            rec["away_ga"][0] += float(hs) * w; rec["away_ga"][1] += w
        n += 1
    def avg(v):
        return round(v[0] / v[1], 3) if v[1] > 0 else 0.0
    stats[tname] = {
        "home_gf": avg(rec["home_gf"]), "home_ga": avg(rec["home_ga"]),
        "away_gf": avg(rec["away_gf"]), "away_ga": avg(rec["away_ga"]),
        "n_home": round(rec["home_gf"][1], 1), "n_away": round(rec["away_gf"][1], 1),
        "n_scored": n, "src_season": "BSD", "src_w": 1.0, "src_tag": "bsd",
        "league": tlg, "team_id": tid,
    }
    raw_cnt += len(scored)
    if (i + 1) % 15 == 0:
        print("  ... %d/%d | 累计赛果 %d" % (i + 1, len(team_ids), raw_cnt), flush=True)
    time.sleep(0.3)

out = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "n_teams": len(stats), "n_events": raw_cnt, "stats": stats}
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_20260818.json"
io.open(fp, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fp)
print("teams:", len(stats), "| errs:", len(errs))
for t, e in errs[:10]:
    print("  ERR", t, e)
