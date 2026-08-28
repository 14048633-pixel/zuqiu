# -*- coding: utf-8 -*-
import os
"""API-Football 亚盘(AH)批量拉取 -> analysis_records/ah_spread_*.json
按 队名归一(dice) + 开球时间(±2h) 匹配 scan24h 场次, 拉 /odds 解析 Asian Handicap 主线.
主队视角带符号线(hdp_home): Home -0.5=主让0.5; Away 侧同线值(严禁翻转符号).
输出: {match_id: {fixture_id, line, home_price, away_price, books, home, away}}
"""
import sys, io, os, json, re, time, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE = "https://v3.football.api-sports.io"
BJT = timezone(timedelta(hours=8))

_GEN = {"fc","afc","cf","sc","ac","as","us","cd","de","sd","ud","ssc","jk","sk","bk",
        "sporting","club","fk","kf","if","il","idrottsforening","dn","ks","ts","sc"}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    words = [w for w in s.split() if w not in _GEN]
    return " ".join(words)

def dice(a, b):
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return 0.0
    return 2.0 * len(wa & wb) / (len(wa) + len(wb))

def get(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if i == 2:
                raise
            time.sleep(3)

def main():
    scan = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260827_1947.json"), encoding="utf-8"))
    ms = scan["matches"]
    # 1) fixtures (4天)
    fixtures = []
    for date in ("2026-08-26", "2026-08-27", "2026-08-28", "2026-08-29"):
        j = get("%s/fixtures?date=%s" % (BASE, date))
        for f in (j.get("response") or []):
            fixtures.append({
                "id": f["fixture"]["id"], "date": f["fixture"]["date"],
                "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"],
                "league": (f.get("league") or {}).get("name"),
            })
    print("fixtures:", len(fixtures), flush=True)
    # 2) 匹配
    pairs = []
    for m in ms:
        try:
            ct = datetime.fromisoformat(str(m["ct"]).replace("Z", "+00:00"))
        except Exception:
            continue
        nh, na = norm(m["home"]), norm(m["away"])
        best, bs = None, 0.0
        for f in fixtures:
            try:
                fd = datetime.fromisoformat(f["date"].replace("Z", "+00:00"))
            except Exception:
                continue
            if abs((fd - ct).total_seconds()) > 7200:
                continue
            s = 0.5 * (dice(nh, norm(f["home"])) + dice(na, norm(f["away"])))
            if s > bs:
                bs, best = s, f
        if best and bs >= 0.5:
            pairs.append((m, best, bs))
            print("OK  %.2f %-26s vs %-26s -> %s (%s vs %s) %s" % (bs, m["home"][:24], m["away"][:24], best["id"], best["home"][:20], best["away"][:20], best["date"][:16]))
        else:
            print("NOMATCH %-26s vs %-26s" % (m["home"][:24], m["away"][:24]))
    print("matched:", len(pairs), "/", len(ms), flush=True)
    # 3) 拉 AH
    out = {}
    n_ah = 0
    for m, f, bs in pairs:
        mid = str(m["id"])
        try:
            od = get("%s/odds?fixture=%d" % (BASE, f["id"]))
        except Exception as e:
            print("ERR odds %s: %r" % (f["id"], e))
            continue
        lines = {}  # line(signed) -> {book: {home: price, away: price}}
        for r0 in (od.get("response") or []):
            for bk in (r0.get("bookmakers") or []):
                bname = bk.get("name") or str(bk.get("id"))
                for b in bk.get("bets") or []:
                    if (b.get("name") or "") != "Asian Handicap":
                        continue
                    rec = {}
                    for v in (b.get("values") or []):
                        val = v.get("value") or ""
                        mm = re.match(r"^\s*(Home|Away)\s*([+-]?\d+(?:\.\d+)?)\s*$", val, re.I)
                        if not mm:
                            continue
                        side = "home" if mm.group(1).lower() == "home" else "away"
                        line = float(mm.group(2))
                        try:
                            pr = float(v.get("odd"))
                        except Exception:
                            continue
                        rec[(line, side)] = pr  # 后写覆盖=取最新
                    for (line, side), pr in rec.items():
                        d = lines.setdefault(line, {}).setdefault(bname, {})
                        d[side] = pr  # 同 book 同线同侧取最后(最新)
        # 选主线: 平衡度优先(隐含概率最接近50/50), 同平衡取抽水最低
        cands = []
        for line, byb in lines.items():
            for bk, prices in byb.items():
                if not prices.get("home") or not prices.get("away"):
                    continue
                orr = 1.0 / prices["home"] + 1.0 / prices["away"]
                imb = max(abs(1.0 / prices["home"] - 0.5), abs(1.0 / prices["away"] - 0.5))
                cands.append((line, bk, orr, imb))
        if not cands:
            print("NOAH %-26s vs %-26s" % (m["home"][:24], m["away"][:24]))
            continue
        cands.sort(key=lambda c: (c[3], c[2]))
        line, bk, orr, imb = cands[0]
        prices = lines[line][bk]
        out[mid] = {"fixture_id": f["id"], "home": m["home"], "away": m["away"],
                    "line": line, "home_price": prices["home"], "away_price": prices["away"],
                    "book": bk, "orr": round(orr, 4), "n_lines": len(lines)}
        n_ah += 1
        print("AH  %-26s vs %-26s | line %+.2f | %s @%.2f / @%.2f | bk=%s" % (m["home"][:24], m["away"][:24], line, "主", prices["home"], prices["away"], bk))
        time.sleep(0.4)
    fp = os.path.join(ROOT, "analysis_records", "ah_spread_20260827_1947.json")
    json.dump({"generated": datetime.now(BJT).isoformat(), "n": n_ah, "spreads": out},
              io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", fp, "| AH:", n_ah, "/", len(ms))

if __name__ == "__main__":
    main()
