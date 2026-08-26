# -*- coding: utf-8 -*-
import io, os, json, requests, sys, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
env = {}
for l in io.open(os.path.join(ROOT, ".env"), encoding="utf-8-sig"):
    if "=" in l and not l.strip().startswith("#"):
        k, v = l.split("=", 1); env[k.strip()] = v.split("#")[0].strip().strip('"').strip("'")
H = {"x-apisports-key": env["FOOTBALL_API_KEY"]}

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
def _fuzzy(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb: return 0.0
    if na == nb: return 1.0
    wa, wb = set(na.split()), set(nb.split())
    if wa and wb and (wa <= wb or wb <= wa): return 0.9
    from difflib import SequenceMatcher
    return SequenceMatcher(None, na, nb).ratio()

# 1) 拉 8/26 fixtures
fx = []
for date in ["2026-08-26"]:
    r = requests.get("https://v3.football.api-sports.io/fixtures", headers=H, params={"date": date}, timeout=30)
    d = r.json()
    fx.extend(d.get("response") or [])
    print("fixtures:", len(fx), "| errors:", d.get("errors"))
# 联赛分布
from collections import Counter
lc = Counter((f.get("league") or {}).get("name") for f in fx)
print("联赛分布:", dict(lc.most_common(15)))

# 2) 天皇杯 32 场 (从 _bsd_next24h.json)
evs = json.load(io.open(r"D:\足球分析\_bsd_next24h.json", encoding="utf-8"))
emps = [e for e in evs if e.get("league_id") == 51 or "Emperor" in str(e.get("league"))]
print("BSD 天皇杯事件:", len(emps))

# 3) 匹配
matches = []
for e in emps:
    best = None; bs = 0.0
    for f in fx:
        sh = _fuzzy(e["home_team"], (f.get("teams") or {}).get("home", {}).get("name", ""))
        sa = _fuzzy(e["away_team"], (f.get("teams") or {}).get("away", {}).get("name", ""))
        s = (sh + sa) / 2
        if s > bs:
            bs = s; best = f
    if best and bs >= 0.7:
        lg = (best.get("league") or {}).get("name")
        matches.append({
            "home": e["home_team"], "away": e["away_team"], "fixture_id": (best.get("fixture") or {}).get("id"),
            "date": e["event_date"], "league": lg,
            "target_home": e["home_team"], "target_away": e["away_team"], "target_league": "天皇杯",
            "target_ko": e["event_date"], "odds_event_id": None,
            "match_score": round(bs, 2),
        })
    else:
        print("未匹配:", e["home_team"], "vs", e["away_team"], "best", round(bs,2))
print("匹配成功:", len(matches))
out = {"n": len(matches), "matches": matches}
fp = os.path.join(ROOT, "analysis_records", "apifb_fixture_map_emperor_20260826.json")
json.dump(out, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", fp)
