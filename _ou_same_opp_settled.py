# -*- coding: utf-8 -*-
"""已结算实盘: 模型OU方向 vs 市场OU方向 分组命中率
数据: 08-15/16/17 scan (模型OU概率+市场赔率) + BSD events 赛果
"""
import io, os, sys, json, time, re, unicodedata
from datetime import datetime, timezone, timedelta
import requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
BASE = "https://sports.bzzoiro.com/api/v2"

env = io.open(os.path.join(ROOT, ".env"), encoding="utf-8").read()
tok = ""
for line in env.splitlines():
    if line.strip().startswith("BZZOIRO_API_KEY="):
        tok = line.split("=",1)[1].strip().strip('"').strip("'")
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Authorization": "Token " + tok}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())
def words(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return set(w for w in re.findall(r"[a-z]{3,}", s))
def word_ok(x, y):
    wx, wy = words(x), words(y)
    return bool(wx and wy and (wx & wy))

def get(path, **params):
    for i in range(1, 4):
        try:
            r = requests.get(BASE + path, headers=H, params=params, timeout=30)
            if r.status_code == 200: return r.json()
            if r.status_code == 429: time.sleep(20); continue
            return None
        except Exception:
            pass
        time.sleep(2)
    return None

# 1) 收集 scan 匹配(模型OU + 市场赔率)
scans = [
    ("20260815_scan_upcoming.json", "scan"),
    ("20260815_scan_upcoming_v3_25_26.json", "scan"),
    ("20260816_scan_upcoming.json", "scan"),
    ("20260817_scan_upcoming.json", "scan"),
]
scan_matches = []
for fn, src in scans:
    d = json.load(io.open(ROOT + r"\analysis_records\\" + fn, encoding="utf-8"))
    for m in d.get("matches", []):
        res = m.get("result") or {}
        bets = res.get("bets") or []
        ou = {b["name"]: b for b in bets if b["name"] in ("大2.50", "小2.50")}
        if "大2.50" not in ou or "小2.50" not in ou: continue
        scan_matches.append({
            "league": m["league"], "ct": m["ct"], "home": m["home"], "away": m["away"],
            "p_over": ou["大2.50"]["prob"], "p_under": ou["小2.50"]["prob"],
            "odd_over": ou["大2.50"]["odds"], "odd_under": ou["小2.50"]["odds"],
            "src": src,
        })
print("scan含OU盘口场次:", len(scan_matches))

# 2) 拉 BSD 赛果 (08-14 至 08-19 北京)
d0 = datetime(2026, 8, 14, 0, 0, tzinfo=timezone(timedelta(hours=8)))
d1 = datetime(2026, 8, 19, 23, 59, tzinfo=timezone(timedelta(hours=8)))
f = (d0 - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
t = (d1 - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
events = []
page = 1
while True:
    j = get("/events/", date_from=f, date_to=t, limit=100, page=page)
    r = (j or {}).get("results") or []
    events.extend(r)
    if not r or len(r) < 100: break
    page += 1
    time.sleep(0.5)
print("BSD events 拉取:", len(events))

# 3) 匹配赛果
def match_event(ev, sm):
    eh, ea = ev.get("home_team"), ev.get("away_team")
    if not eh or not ea: return False
    return (norm(eh)==norm(sm["home"]) and norm(ea)==norm(sm["away"])) or (norm(eh)==norm(sm["away"]) and norm(ea)==norm(sm["home"]))

matched = 0
rows = []
for sm in scan_matches:
    # 找同队名且已完赛的事件
    cands = [e for e in events if match_event(e, sm)]
    if not cands: continue
    e = cands[0]
    hs, as_ = e.get("home_score"), e.get("away_score")
    if hs is None or as_ is None: continue
    status = e.get("status", "")
    if status not in ("finished", "FT", "完结", "完赛", "ended"): continue
    total = hs + as_
    hit = (total > 2.5) == (sm["p_over"] > sm["p_under"])
    po = (1.0/sm["odd_over"]) / (1.0/sm["odd_over"] + 1.0/sm["odd_under"])
    mkt_over = po > 0.5
    model_over = sm["p_over"] > sm["p_under"]
    same = (model_over == mkt_over)
    rows.append({
        "league": sm["league"], "ct": sm["ct"], "home": sm["home"], "away": sm["away"],
        "score": "%d-%d" % (hs, as_), "total": total,
        "model": "大" if model_over else "小", "mkt": "大" if mkt_over else "小",
        "hit": hit, "same": same,
    })
    matched += 1

print("匹配到赛果场次:", matched)
by_key = {}
for r in rows:
    k = (norm(r["home"]), norm(r["away"]), r["ct"][:10])
    by_key[k] = r
rows = list(by_key.values())
print("去重后:", len(rows))

def stat(rs):
    if not rs: return "n=0"
    hit = sum(1 for r in rs if r["hit"])
    return "n=%d 命中%d (%.1f%%)" % (len(rs), hit, 100.0*hit/len(rs))
same = [r for r in rows if r["same"]]
opp = [r for r in rows if not r["same"]]
print("\n== 模型 vs 市场 分组 ==")
print("同向:", stat(same))
print("反向:", stat(opp))
big = [r for r in rows if r["model"]=="大"]
small = [r for r in rows if r["model"]=="小"]
print("\n== 按模型方向 ==")
print("模型大:", stat(big))
print("模型小:", stat(small))

# 保存明细
out = {"n": len(rows), "same": {"n": len(same), "hit": stat(same)}, "opp": {"n": len(opp), "hit": stat(opp)}, "rows": rows}
io.open(ROOT + r"\analysis_records\ou_same_opp_settled_20260819.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("\nsaved analysis_records/ou_same_opp_settled_20260819.json")
for r in sorted(rows, key=lambda x: x["ct"])[:40]:
    print("| %s | %s | %s vs %s | %s | 模型%s 市%s | %s | %s |" % (
        r["ct"][:16], r["league"], r["home"], r["away"], r["score"],
        r["model"], r["mkt"], "✔" if r["hit"] else "✘", "同向" if r["same"] else "反向"))
