# -*- coding: utf-8 -*-
"""InferSports 亚盘/大小球/1X2 补拉器 -> 追加 snapshots.csv + 存档 JSON.
用法: python fetch_infersports_lines.py --matches <json> [--limit N]
数据源: https://api.infersports.dev/mcp (MCP streamable HTTP, 免费, 6家亚庄: crown/macau/nova88/sbobet/hkjc/m8bet)
"""
import os, sys, json, io, csv, re, unicodedata, time, difflib
import requests
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
BASE = "https://api.infersports.dev/mcp"
TIMEOUT = 30

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def name_sim(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if len(na) >= 6 and len(nb) >= 6 and (na in nb or nb in na):
        return 0.86
    return difflib.SequenceMatcher(None, na, nb).ratio()

class InferClient:
    def __init__(self):
        self.s = requests.Session()
        self.s.post(BASE, headers={"Accept": "application/json", "Content-Type": "application/json"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "football-scan", "version": "1.0"}}}, timeout=TIMEOUT)
    def call(self, name, args):
        r = self.s.post(BASE, headers={"Accept": "application/json", "Content-Type": "application/json"},
                        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                              "params": {"name": name, "arguments": args}}, timeout=TIMEOUT)
        j = r.json()
        try:
            txt = j["result"]["content"][0]["text"]
            return json.loads(txt)
        except Exception:
            return {"_error": j.get("error") or r.text[:300]}
    def find_match(self, query, kt=None):
        # 注意: 不能传 date (传了反而 not_found); 用开赛时间贴近度二次校验
        d = self.call("find_match", {"query": query})
        m = d.get("match") if d.get("status") in ("matched", "ambiguous") else None
        if not m:
            return None
        if kt:
            try:
                st = datetime.fromisoformat(m.get("scheduled_at", "").replace("Z", "+00:00"))
                if abs((st - kt).total_seconds()) > 8 * 3600:
                    return None
            except Exception:
                pass
        return m
    def sharp_line(self, query, market, date=None):
        args = {"query": query, "market_type": market, "period": "full_time", "format": "decimal", "verbosity": "full"}
        if date:
            args["date"] = date
        return self.call("get_sharp_line", args)

def pick_prices(line, comp):
    """从 compare 段提取 (home_price, away_price) 用主盘线两侧最优价."""
    consensus = comp.get("consensus_line")
    target = consensus if consensus is not None else line
    best = {}
    for b in comp.get("books") or []:
        if b.get("status") != "open":
            continue
        try:
            bl = float(b.get("line"))
        except (TypeError, ValueError):
            continue
        if abs(bl - target) > 0.001:
            continue
        pr = b.get("prices") or {}
        for side in ("home", "away"):
            pv = pr.get(side) or 0
            if pv and pv > best.get(side, 0):
                best[side] = pv
    if best:
        return target, best.get("home"), best.get("away")
    bp = {x.get("outcome"): x.get("price") for x in (comp.get("best_prices") or [])}
    return target, bp.get("home"), bp.get("away")

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--markets", default="asian_handicap,totals,1x2")
    args = ap.parse_args()

    ms = json.load(io.open(os.path.join(ROOT, args.matches), encoding="utf-8"))
    if args.limit:
        ms = ms[:args.limit]
    markets = [m.strip() for m in args.markets.split(",") if m.strip()]

    existing = {}
    if os.path.exists(SNAP):
        for r in csv.reader(io.open(SNAP, encoding="utf-8")):
            if not r or len(r) < 13:
                continue
            try:
                ct = datetime.fromisoformat(r[3].replace("Z", "+00:00"))
            except Exception:
                continue
            k = (r[2], norm(r[4]), norm(r[5]))
            existing.setdefault(k, []).append((ct, r[1]))
    def reuse_eid(lg, h, a, kt):
        for ct, eid in existing.get((lg, norm(h), norm(a)), []):
            if abs((ct - kt).total_seconds()) <= 6 * 3600:
                return eid
        return None

    c = InferClient()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    archive = []
    ok = miss = err = 0
    for i, m in enumerate(ms, 1):
        home, away = m["home"], m["away"]
        lg = m.get("league", "")
        try:
            kt = datetime.fromisoformat(m.get("ko_utc", "").replace("Z", "+00:00"))
        except Exception:
            kt = None
        q = "%s vs %s" % (home, away)
        ev = c.find_match(q, kt=kt)
        if not ev:
            miss += 1
            archive.append({"match": q, "league": lg, "ko": m.get("ko_utc"), "status": "not_found"})
            print("MISS %2d/%-2d %-10s %s vs %s" % (i, len(ms), lg, home, away))
            continue
        eid = ev["event_id"]
        eh, ea = ev.get("home_team"), ev.get("away_team")
        s_h = name_sim(eh, home); s_a = name_sim(ea, away)
        # 时间贴近(<=8h)已校验, 单侧强匹配(>=0.7)+另一侧弱匹配(>=0.35)即接受(Hearts=Heart of Midlothian 类简称)
        if not ((s_h >= 0.7 and s_a >= 0.35) or (s_a >= 0.7 and s_h >= 0.35)):
            miss += 1
            archive.append({"match": q, "league": lg, "status": "mismatch",
                            "infer": "%s vs %s" % (eh, ea), "sim": [round(s_h, 2), round(s_a, 2)]})
            print("MISMATCH %2d %s vs %s -> %s vs %s (%.2f/%.2f)" % (i, home, away, eh, ea, s_h, s_a))
            continue
        snap_eid = reuse_eid(lg, home, away, kt) if kt else None
        out_eid = snap_eid or ("infer" + eid.replace("evt_", ""))
        per = {"match": q, "league": lg, "ko": m.get("ko_utc"), "infer_event": eid,
               "snap_eid": snap_eid, "infer_names": [eh, ea], "markets": {}}
        for mk in markets:
            d = c.sharp_line(q, mk)
            if d.get("status") != "ok":
                per["markets"][mk] = {"status": "error", "detail": str(d.get("_error") or d.get("summary") or "")[:200]}
                err += 1
                continue
            comp = d.get("comparison") or {}
            per["markets"][mk] = {
                "status": "ok", "as_of": comp.get("as_of"), "stale": comp.get("stale", False),
                "consensus_line": comp.get("consensus_line"), "fair": comp.get("fair_odds"),
                "best_prices": comp.get("best_prices"), "book_count": comp.get("book_count"),
            }
            if mk == "asian_handicap":
                line, hp, ap_ = pick_prices(comp.get("consensus_line"), comp)
                if hp and ap_ and line is not None:
                    rows.append({"event_id": out_eid, "league": lg, "ct": m.get("ko_utc") or "",
                                 "h": eh, "a": ea, "book": "infersports:sharp", "market": "asian_handicap",
                                 "outcome": "Home %+.2f" % line, "side": "home", "side_key": "home@%+.2f" % line,
                                 "point": "%+.2f" % line, "price": hp})
                    rows.append({"event_id": out_eid, "league": lg, "ct": m.get("ko_utc") or "",
                                 "h": eh, "a": ea, "book": "infersports:sharp", "market": "asian_handicap",
                                 "outcome": "Away %+.2f" % -line, "side": "away", "side_key": "away@%+.2f" % line,
                                 "point": "%+.2f" % line, "price": ap_})
                    ok += 1
                else:
                    per["markets"][mk]["status"] = "no_prices"
            elif mk == "totals":
                line = comp.get("consensus_line")
                bp = {x.get("outcome"): x.get("price") for x in (comp.get("best_prices") or [])}
                op, up = bp.get("over"), bp.get("under")
                if op and up and line is not None:
                    rows.append({"event_id": out_eid, "league": lg, "ct": m.get("ko_utc") or "",
                                 "h": eh, "a": ea, "book": "infersports:sharp", "market": "totals",
                                 "outcome": "Over %g" % line, "side": "over", "side_key": "over@%g" % line,
                                 "point": str(line), "price": op})
                    rows.append({"event_id": out_eid, "league": lg, "ct": m.get("ko_utc") or "",
                                 "h": eh, "a": ea, "book": "infersports:sharp", "market": "totals",
                                 "outcome": "Under %g" % line, "side": "under", "side_key": "under@%g" % line,
                                 "point": str(line), "price": up})
                    ok += 1
                else:
                    per["markets"][mk]["status"] = "no_prices"
            elif mk == "1x2":
                bp = {x.get("outcome"): x.get("price") for x in (comp.get("best_prices") or [])}
                for side, od in (("home", eh), ("draw", "Draw"), ("away", ea)):
                    pv = bp.get(side)
                    if pv:
                        rows.append({"event_id": out_eid, "league": lg, "ct": m.get("ko_utc") or "",
                                     "h": eh, "a": ea, "book": "infersports:sharp", "market": "h2h",
                                     "outcome": od, "side": side, "side_key": side,
                                     "point": "", "price": pv})
                ok += 1
            time.sleep(0.3)
        archive.append(per)
        print("OK   %2d/%-2d %-10s %s vs %s | %s" % (i, len(ms), lg, eh, ea, eid))

    print("== summary: ok=%d not_found=%d err=%d rows=%d" % (ok, miss, err, len(rows)))
    # 去重: 同 (event_id, book, market, side, point) 已存在则跳过, 防止重复追加污染
    seen = set()
    if os.path.exists(SNAP):
        for r in csv.reader(io.open(SNAP, encoding="utf-8")):
            if not r or len(r) < 12:
                continue
            seen.add((r[1], r[6], r[7], (r[9] or "").lower(), r[11]))
    rows = [r for r in rows if (r["event_id"], r["book"], r["market"], r["side"], r["point"]) not in seen]
    if rows:
        with io.open(SNAP, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow([ts, r["event_id"], r["league"], r["ct"], r["h"], r["a"], r["book"],
                            r["market"], r["outcome"], r["side"], r["side_key"], r["point"], r["price"], ts])
    ts2 = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    out_path = os.path.join(ROOT, "analysis_records", "infersports_lines_%s.json" % ts2)
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=1)
    print("archived ->", out_path)

if __name__ == "__main__":
    main()
