# -*- coding: utf-8 -*-
import io, os, json, re, unicodedata, time
from datetime import datetime, timezone, timedelta
import requests
ROOT = r"D:\足球分析"
env = io.open(os.path.join(ROOT, ".env"), encoding="utf-8").read()
tok = ""
for line in env.splitlines():
    if line.strip().startswith("BZZOIRO_API_KEY="):
        tok = line.split("=",1)[1].strip().strip('"').strip("'")
BASE = "https://sports.bzzoiro.com/api/v2"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Authorization": "Token " + tok}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())
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

scans = ["20260815_scan_upcoming.json","20260815_scan_upcoming_v3_25_26.json",
         "20260816_scan_upcoming.json","20260817_scan_upcoming.json"]
scan_matches = []
for fn in scans:
    d = json.load(io.open(ROOT + r"\analysis_records\\" + fn, encoding="utf-8"))
    for m in d.get("matches", []):
        res = m.get("result") or {}
        bets = res.get("bets") or []
        ou = {b["name"]: b for b in bets if b["name"] in ("大2.50","小2.50")}
        if "大2.50" not in ou or "小2.50" not in ou: continue
        scan_matches.append({
            "league": m["league"], "ct": m["ct"], "home": m["home"], "away": m["away"],
            "p_over": ou["大2.50"]["prob"], "p_under": ou["小2.50"]["prob"], "odd_over": ou["大2.50"]["odds"], "odd_under": ou["小2.50"]["odds"],
        })

d0 = datetime(2026,8,14,0,0,tzinfo=timezone(timedelta(hours=8)))
d1 = datetime(2026,8,19,23,59,tzinfo=timezone(timedelta(hours=8)))
f = (d0-timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
t = (d1-timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
events = []
page = 1
while True:
    j = get("/events/", date_from=f, date_to=t, limit=100, page=page)
    r = (j or {}).get("results") or []
    events.extend(r)
    if not r or len(r) < 100: break
    page += 1
    time.sleep(0.5)

def match_event(ev, sm):
    eh, ea = ev.get("home_team"), ev.get("away_team")
    if not eh or not ea: return False
    return (norm(eh)==norm(sm["home"]) and norm(ea)==norm(sm["away"])) or (norm(eh)==norm(sm["away"]) and norm(ea)==norm(sm["home"]))

rows = []
for sm in scan_matches:
    cands = [e for e in events if match_event(e, sm)]
    if not cands: continue
    e = cands[0]
    hs, as_ = e.get("home_score"), e.get("away_score")
    if hs is None or as_ is None: continue
    if e.get("status") not in ("finished","FT","完结","完赛","ended"): continue
    total = hs + as_
    model_over = sm["p_over"] > sm["p_under"]
    po = (1.0/sm["odd_over"])/(1.0/sm["odd_over"]+1.0/sm["odd_under"])
    mkt_over = po > 0.5
    hit = (total > 2.5) == model_over
    odds = sm["odd_over"] if model_over else sm["odd_under"]
    rows.append({
        "league": sm["league"], "ct": sm["ct"], "home": sm["home"], "away": sm["away"],
        "score": "%d-%d" % (hs,as_), "total": total, "model": "大" if model_over else "小",
        "mkt": "大" if mkt_over else "小", "odds": odds, "hit": hit, "same": model_over==mkt_over,
    })

seen = {}
for r in rows:
    k = (norm(r["home"]), norm(r["away"]), r["ct"][:10])
    seen[k] = r
rows = list(seen.values())

def grp(rs):
    if not rs: return "n=0"
    n = len(rs); hit = sum(1 for r in rs if r["hit"])
    ret = sum(r["odds"] if r["hit"] else 0.0 for r in rs)
    roi = ret/n - 1.0
    return "n=%d 命中%d (%.1f%%) ROI %+.1f%%" % (n, hit, 100.0*hit/n, 100.0*roi)

L = []
L.append("== 全量 n=%d ==" % len(rows)); L.append("   " + grp(rows))
L.append("== 模型 vs 市场 =="); L.append("同向: " + grp([r for r in rows if r["same"]])); L.append("反向: " + grp([r for r in rows if not r["same"]]))
L.append("== 按模型方向 =="); L.append("模型大: " + grp([r for r in rows if r["model"]=="大"])); L.append("模型小: " + grp([r for r in rows if r["model"]=="小"]))
L.append("== 同向x方向 ==")
L.append("同向大: " + grp([r for r in rows if r["same"] and r["model"]=="大"]))
L.append("同向小: " + grp([r for r in rows if r["same"] and r["model"]=="小"]))
L.append("反向大: " + grp([r for r in rows if not r["same"] and r["model"]=="大"]))
L.append("反向小: " + grp([r for r in rows if not r["same"] and r["model"]=="小"]))
L.append("== 按联赛 ==")
by_league = {}
for r in rows: by_league.setdefault(r["league"], []).append(r)
for lg, rs in sorted(by_league.items(), key=lambda x: -len(x[1])):
    L.append("%-6s %s" % (lg, grp(rs)))
print("\n".join(L))

out = {"n": len(rows), "rows": rows}
io.open(ROOT + r"\analysis_records\ou_same_opp_settled_20260819.json", "w", encoding="utf-8").write(
    json.dumps(out, ensure_ascii=False, indent=1))
print("\nsaved")
