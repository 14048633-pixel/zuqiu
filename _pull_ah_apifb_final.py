# -*- coding: utf-8 -*-
import os
"""补拉 3 场(布莱顿/利勒斯特罗姆/圣加仑) 亚盘 + 修复 norm 转写"""
import sys, io, os, json, re, time, unicodedata, urllib.request
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE = "https://v3.football.api-sports.io"
_GEN = {"fc","afc","cf","sc","ac","as","us","cd","de","sd","ud","ssc","jk","sk","bk","sporting","club","fk","kf","if","il","idrottsforening","dn","ks","ts"}
_TRANS = {"ø":"o","Ø":"o","æ":"ae","Æ":"ae","å":"a","Å":"a","đ":"d","Đ":"d","ł":"l","Ł":"l","ß":"ss","ı":"i","İ":"i","ş":"s","Ş":"s","ș":"s","ț":"t","ð":"d"}
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(_TRANS.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(w for w in s.split() if w not in _GEN)
def dice(a, b):
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb: return 0.0
    return 2.0*len(wa & wb)/(len(wa)+len(wb))
def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                time.sleep(8*(i+2)); continue
            time.sleep(7)
    return {"errors": {"failed": True}}
fp = os.path.join(ROOT, "analysis_records", "ah_spread_20260827_1947.json")
ah = json.load(io.open(fp, encoding="utf-8")); spreads = ah["spreads"]
scan = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260827_1947.json"), encoding="utf-8"))
tgt = {}
for m in scan["matches"]:
    if str(m["id"]) not in spreads:
        tgt[str(m["id"])] = m
print("target missing:", len(tgt))
fixtures = []
for date in ("2026-08-27", "2026-08-28"):
    j = get("%s/fixtures?date=%s" % (BASE, date))
    for f in (j.get("response") or []):
        fixtures.append({"id": f["fixture"]["id"], "date": f["fixture"]["date"],
                         "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"]})
    time.sleep(6.5)
for mid, m in tgt.items():
    ct = datetime.fromisoformat(str(m["ct"]).replace("Z", "+00:00"))
    nh, na = norm(m["home"]), norm(m["away"])
    best, bs = None, 0.0
    for f in fixtures:
        fd = datetime.fromisoformat(f["date"].replace("Z", "+00:00"))
        if abs((fd-ct).total_seconds()) > 7200: continue
        s = 0.5*(dice(nh, norm(f["home"])) + dice(na, norm(f["away"])))
        if s > bs: bs, best = s, f
    if not best or bs < 0.5:
        print("NOMATCH", m["home"], "vs", m["away"]); continue
    od = get("%s/odds?fixture=%d" % (BASE, best["id"])); time.sleep(6.5)
    if od.get("errors"):
        print("ERR", best["id"], od.get("errors")); continue
    lines = {}
    for r0 in (od.get("response") or []):
        for bk in (r0.get("bookmakers") or []):
            bname = bk.get("name") or str(bk.get("id"))
            for b in bk.get("bets") or []:
                if (b.get("name") or "") != "Asian Handicap": continue
                rec = {}
                for v in (b.get("values") or []):
                    mm = re.match(r"^\s*(Home|Away)\s*([+-]?\d+(?:\.\d+)?)\s*$", v.get("value") or "", re.I)
                    if not mm: continue
                    side = "home" if mm.group(1).lower() == "home" else "away"
                    try: pr = float(v.get("odd"))
                    except Exception: continue
                    rec[(float(mm.group(2)), side)] = pr
                for (line, side), pr in rec.items():
                    lines.setdefault(line, {}).setdefault(bname, {})[side] = pr
    cands = []
    for line, byb in lines.items():
        for bk, prices in byb.items():
            if not prices.get("home") or not prices.get("away"): continue
            orr = 1.0/prices["home"] + 1.0/prices["away"]
            imb = max(abs(1.0/prices["home"]-0.5), abs(1.0/prices["away"]-0.5))
            cands.append((line, bk, orr, imb))
    if not cands:
        print("NOAH", m["home"], "vs", m["away"]); continue
    cands.sort(key=lambda c: (c[3], c[2]))
    line, bk, orr, imb = cands[0]; prices = lines[line][bk]
    spreads[mid] = {"fixture_id": best["id"], "home": m["home"], "away": m["away"],
                    "line": line, "home_price": prices["home"], "away_price": prices["away"],
                    "book": bk, "orr": round(orr, 4), "n_lines": len(lines)}
    print("AH", m["home"][:24], "vs", m["away"][:24], "| line %+.2f | @%.2f/@%.2f | %s" % (line, prices["home"], prices["away"], bk))
ah["n"] = len(spreads)
json.dump(ah, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total AH:", len(spreads))
