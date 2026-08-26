# -*- coding: utf-8 -*-
"""v2 对手强度归一: 联赛环境 level 平移 + 迭代对手强度 + 样本收缩
核心修复 v1 缺陷: 同档联赛赛程系数抵消 -> 改为「相对本联赛均值 x 联赛水平系数」
输出: data/raw/football_data/bsd_team_stats_norm_v2_20260818.json
"""
import sys, io, os, json, urllib.request, time
from datetime import datetime, timezone
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
                return {"__err__": "%s" % str(e)[:80]}
            time.sleep(2)

LEAGUE_COEF = {
    1:1.0,3:1.0,5:1.0,4:1.0,6:1.0,7:1.0,8:1.0,83:1.0,90:1.0,
    10:0.92,2:0.92,14:0.92,11:0.92,13:0.92,15:0.92,24:0.92,9:0.92,
    12:0.85,38:0.85,89:0.85,25:0.85,17:0.85,19:0.85,20:0.85,18:0.85,
    85:0.85,34:0.85,84:0.85,54:0.85,26:0.85,32:0.85,33:0.85,49:0.85,
    52:0.80,50:0.80,80:0.75,86:0.80,87:0.75,55:0.70,23:0.72,22:0.70,
    88:0.70,82:0.60,47:0.60,53:0.60,28:0.55,70:0.50,
    42:0.95,41:0.95,39:0.95,43:0.95,44:0.95,40:0.95,
    35:0.90,81:0.75,56:0.70,46:0.80,51:0.80,
    27:0.85,58:0.85,60:0.85,61:0.85,62:0.85,63:0.85,64:0.85,65:0.85,66:0.85,67:0.85,68:0.85,69:0.85,
    29:0.80,30:0.80,
}
EXCLUDE = {79, 36, 72, 71}

def w_of(idx):
    if idx < 5: return 1.0
    if idx < 10: return 0.7
    if idx < 20: return 0.4
    return 0.2

def age_w(dtstr):
    try:
        d = datetime.fromisoformat(dtstr.replace("Z", "+00:00"))
    except Exception:
        return 0.2
    age = (datetime.now(timezone.utc) - d).days
    if age < 180: return 1.0
    if age < 365: return 0.7
    if age < 730: return 0.4
    return 0.2

scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
KEY_LG = {"欧冠", "欧联", "欧协联", "中超", "西甲"}
targets = [m for m in scan["matches"] if m["league"] in KEY_LG]
team_ids = {}
for t in targets:
    if t.get("home_id"): team_ids[t["home_id"]] = (t["home"], t["league"])
    if t.get("away_id"): team_ids[t["away_id"]] = (t["away"], t["league"])
print("目标队伍数:", len(team_ids))

# ---- 1) 拉逐场边表 ----
edges = []      # 全部去重边
team_edges = {} # tid -> list
errs = []
seen = set()
for i, (tid, (tname, tlg)) in enumerate(sorted(team_ids.items(), key=lambda x: x[1][0])):
    j = get("/events/?team_id=%d&status=finished&limit=100" % tid)
    if "__err__" in j:
        errs.append((tname, j["__err__"])); continue
    res = j.get("results") or []
    team_edges[tid] = []
    for e in res:
        lid = e.get("league_id")
        if lid in EXCLUDE: continue
        hs, as_ = e.get("home_score"), e.get("away_score")
        if hs is None or as_ is None: continue
        eid = e.get("id")
        ed = {"id": eid, "date": e.get("event_date") or "", "lid": lid,
              "ht": e.get("home_team_id"), "at": e.get("away_team_id"),
              "hs": int(hs), "as": int(as_)}
        team_edges[tid].append(ed)
        if eid not in seen:
            seen.add(eid); edges.append(ed)
    if (i + 1) % 15 == 0:
        print("  fetch ... %d/%d  (edges %d)" % (i + 1, len(team_ids), len(edges)), flush=True)
    time.sleep(0.3)

print("拉取完成: edges=%d (去重), errs=%d" % (len(edges), len(errs)))
for t, e in errs[:8]:
    print("  ERR", t, e)

# 存档边表
edge_fp = ROOT + r"\data\raw\football_data\bsd_edges_20260818.json"
io.open(edge_fp, "w", encoding="utf-8").write(json.dumps(
    {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "n_edges": len(edges),
     "team_edges": {str(k): v for k, v in team_edges.items()}, "edges": edges}, ensure_ascii=False))
print("saved", edge_fp)
