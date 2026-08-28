# -*- coding: utf-8 -*-
import os
"""API-Football 亚盘拉取(配额友好版) -> analysis_records/ah_spread_latest.json
用法:
  python prediction_v2/pull_ah_quota.py                 # 默认: 只拉12h内未开赛, TTL 3h, 自动预算
  python prediction_v2/pull_ah_quota.py --window 6      # 只拉6h内(更省)
  python prediction_v2/pull_ah_quota.py --force         # 忽略TTL强制重拉
  python prediction_v2/pull_ah_quota.py --budget 20     # 今日AH最多20次(硬上限)
  python prediction_v2/pull_ah_quota.py --infer-only  # 只用InferSports免费亚盘(6家亚庄), 0消耗API-Football
省额度设计:
  - 逐响应读 x-ratelimit-requests-remaining(日额度) 与 x-ratelimit-remaining(分钟额度)
  - 日剩余<=reserve 或 分钟剩余<=2 立即硬停; 每场间 sleep>=6s 满足10次/分钟
  - fixture 映射按日期缓存(每天仅1次 /fixtures?date=), 不重复拉
  - 优先 InferSports 免费亚盘(6家亚庄 crown/macau/nova88/sbobet/hkjc/m8bet), 拉不到才走 API-Football; --infer-only 完全0消耗
  - 同场 TTL(默认3h)内不重复拉
输出字段: {fixture, home, away, home_line(主队让球线, 负=主让), home_price, away_price,
          books, pulled_at, src="apifb_mainline"}
"""
import io, os, sys, json, re, time, glob, argparse, unicodedata
from datetime import datetime, timezone, timedelta
import urllib.request
import http.cookiejar

ROOT = r"D:\足球分析"
BJT = timezone(timedelta(hours=8))
KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE = "https://v3.football.api-sports.io"
MAP_FP = os.path.join(ROOT, "analysis_records", "apifb_fixture_map_quota.json")
STATE_FP = os.path.join(ROOT, "analysis_records", "ah_quota_state.json")
OUT_FP = os.path.join(ROOT, "analysis_records", "ah_spread_latest.json")
SCAN_GLOB = ("scan48h_*.json", "scan24h_*.json")

# 已知队名别名 (BSD/扫描名 -> API-Football 名), 缺失则靠模糊匹配
ALIAS = {
    "shandong taishan": "shandong luneng",
    "dalian yingbo fc": "dalian zhixing",
    "dalian yingbo": "dalian zhixing",
    "shenzhen peng city": "sichuan jiuniu",
    "shanghai port": "shanghai sipg",
    "sichuan jiuniu": "shenzhen peng city",
}
_GEN = {"fc", "afc", "cf", "sc", "ac", "as", "us", "cd", "de", "sd", "ud", "ssc", "jk", "sk", "bk",
        "sporting", "club", "fk", "kf", "if", "il", "dn", "ks", "ts"}
_TRANS = {"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "å": "a", "Å": "A", "đ": "d", "Đ": "D",
          "ł": "l", "Ł": "L", "ß": "ss", "ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ș": "s", "ț": "t", "ð": "d"}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(_TRANS.get(c, c) for c in s)
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return " ".join(w for w in s.split() if w not in _GEN)


def dice(a, b):
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return 0.0
    return 2.0 * len(wa & wb) / (len(wa) + len(wb))


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
            with urllib.request.urlopen(req, timeout=40) as r:
                hdr = dict(r.headers)
                body = json.loads(r.read().decode("utf-8", "replace"))
                return body, hdr
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(8 * (i + 2))
                continue
            return {"errors": {"http": e.code}}, {}
        except Exception:
            time.sleep(6)
    return {"errors": {"failed": True}}, {}


def load_state():
    try:
        d = json.load(io.open(STATE_FP, encoding="utf-8"))
    except Exception:
        d = {}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if d.get("date") != today:
        d = {"date": today, "calls": 0, "stopped": None}
    return d


def save_state(st):
    io.open(STATE_FP, "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))


def load_fixture_map():
    try:
        return json.load(io.open(MAP_FP, encoding="utf-8"))
    except Exception:
        return {"dates": {}}


def save_fixture_map(m):
    io.open(MAP_FP, "w", encoding="utf-8").write(json.dumps(m, ensure_ascii=False, indent=1))


def latest_scan():
    fs = [f for pat in SCAN_GLOB for f in glob.glob(os.path.join(ROOT, "analysis_records", pat))
          if "finished" not in f]
    if not fs:
        return []
    fs.sort(key=os.path.getmtime, reverse=True)
    for fp in fs[:5]:
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
            ms = d.get("matches") or []
            if ms:
                return ms
        except Exception:
            continue
    return []


def fixtures_for_date(fmap, date_utc, st):
    """按日期拉 /fixtures?date= 并缓存(每天1次). 返回 list[(fixture_id, home, away, date)]"""
    if date_utc in fmap.get("dates", {}):
        return fmap["dates"][date_utc]
    body, hdr = get("%s/fixtures?date=%s" % (BASE, date_utc))
    st["calls"] += 1
    out = []
    if not body.get("errors"):
        for f in (body.get("response") or []):
            out.append({"id": f["fixture"]["id"], "date": f["fixture"]["date"],
                        "home": f["teams"]["home"]["name"], "away": f["teams"]["away"]["name"]})
    fmap.setdefault("dates", {})[date_utc] = out
    save_fixture_map(fmap)
    return out


def match_fixture(fixs, m, window_ok):
    """BSD事件 -> API-Football fixture (队名归一+别名+±2h窗口, 相似度>=0.55)"""
    ct = None
    try:
        ct = datetime.fromisoformat(str(m["ct"]).replace("Z", "+00:00"))
    except Exception:
        return None
    nh, na = norm(m["home"]), norm(m["away"])
    if nh in ALIAS:
        nh = ALIAS[nh]
    if na in ALIAS:
        na = ALIAS[na]
    best, bs = None, 0.0
    for f in fixs:
        try:
            fd = datetime.fromisoformat(f["date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if abs((fd - ct).total_seconds()) > 7200:
            continue
        s = 0.5 * (dice(nh, norm(f["home"])) + dice(na, norm(f["away"])))
        if s > bs:
            bs, best = s, f
    if not best or bs < 0.55:
        return None
    return best


def main_line_from_odds(od):
    """主盘共识: 每机构取主客水位最接近的线(平衡线, 范围[-2,2]), 再取众数线+平均水位.
    返回 {line(主队视角), home_price, away_price, books} 或 None"""
    per_book = {}
    for r0 in (od.get("response") or []):
        for bk in (r0.get("bookmakers") or []):
            bname = bk.get("name") or str(bk.get("id"))
            vals = {}
            for b in (bk.get("bets") or []):
                if (b.get("name") or "") != "Asian Handicap":
                    continue
                for v in (b.get("values") or []):
                    mm = re.match(r"^\s*(Home|Away)\s*([+-]?\d+(?:\.\d+)?)\s*$", v.get("value") or "", re.I)
                    if not mm:
                        continue
                    try:
                        price = float(v.get("odd") or 0)
                    except Exception:
                        continue
                    vals[(mm.group(1), float(mm.group(2)))] = price
            cands = []
            for (side, line) in vals:
                if not (-2.0 <= line <= 2.0):
                    continue
                hp = vals.get(("Home", line))
                ap = vals.get(("Away", line))
                if hp and ap:
                    cands.append((abs(hp - ap), line, hp, ap))
            if cands:
                cands.sort()
                per_book[bname] = cands[0]
    if not per_book:
        return None
    from collections import Counter
    cnt = Counter(c[1] for c in per_book.values())
    ml = cnt.most_common(1)[0][0]
    prs = [(c[2], c[3]) for c in per_book.values() if c[1] == ml]
    return {"line": ml,
            "home_price": round(sum(x[0] for x in prs) / len(prs), 2),
            "away_price": round(sum(x[1] for x in prs) / len(prs), 2),
            "books": len(prs)}


class _InferMCP:
    """InferSports MCP (streamable HTTP, 免费无key). 纯标准库实现, 不依赖requests."""
    BASE = "https://api.infersports.dev/mcp"

    def __init__(self):
        self._cj = http.cookiejar.CookieJar()
        self._op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cj))
        self._ready = False

    def _post(self, payload):
        req = urllib.request.Request(self.BASE, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        with self._op.open(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def _ensure(self):
        if self._ready:
            return
        self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "football-scan", "version": "1.0"}}})
        self._ready = True

    def call(self, name, args):
        self._ensure()
        try:
            j = self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": name, "arguments": args}})
            return json.loads(j["result"]["content"][0]["text"])
        except Exception:
            return {"status": "error"}


def infer_find_match(c, home, away, kt):
    """InferSports find_match: 队名搜索 + 开赛时间贴近(<=8h)校验. 返回 match dict 或 None."""
    d = c.call("find_match", {"query": "%s vs %s" % (home, away)})
    m = d.get("match") if d.get("status") in ("matched", "ambiguous") else None
    if not m:
        return None
    if kt:
        try:
            st = datetime.fromisoformat(str(m.get("scheduled_at", "")).replace("Z", "+00:00"))
            if abs((st - kt).total_seconds()) > 8 * 3600:
                return None
        except Exception:
            pass
    return m


def parse_infer_ah(comp):
    """InferSports comparison -> 主盘 {line, home_price, away_price, books}.
    line=主队视角(负=主让); 水位取共识线开盘机构均值; 无共识线开盘回退 best_prices. 失败返 None."""
    try:
        line = float(comp.get("consensus_line"))
    except (TypeError, ValueError):
        return None
    prs = []
    for b in (comp.get("books") or []):
        if b.get("status") != "open":
            continue
        try:
            bl = float(b.get("line"))
        except (TypeError, ValueError):
            continue
        if abs(bl - line) > 0.001:
            continue
        p = b.get("prices") or {}
        try:
            hp = float(p.get("home"))
        except (TypeError, ValueError):
            hp = None
        try:
            ap = float(p.get("away"))
        except (TypeError, ValueError):
            ap = None
        if hp and ap:
            prs.append((hp, ap))
    if not prs:
        bp = {x.get("outcome"): x.get("price") for x in (comp.get("best_prices") or [])}
        try:
            hp, ap = float(bp.get("home")), float(bp.get("away"))
        except (TypeError, ValueError):
            return None
        return {"line": line, "home_price": round(hp, 2), "away_price": round(ap, 2),
                "books": int(comp.get("book_count") or 0)}
    return {"line": line,
            "home_price": round(sum(x[0] for x in prs) / len(prs), 2),
            "away_price": round(sum(x[1] for x in prs) / len(prs), 2),
            "books": len(prs)}


def infer_ah(home, away, kt):
    """InferSports 免费亚盘入口: 返回 {line, home_price, away_price, books, infer_event} 或 None."""
    try:
        c = _InferMCP()
        m = infer_find_match(c, home, away, kt)
        if not m:
            return None
        d = c.call("get_sharp_line", {"query": "%s vs %s" % (home, away), "market_type": "asian_handicap",
                                      "period": "full_time", "format": "decimal", "verbosity": "full"})
        if d.get("status") != "ok":
            return None
        comp = d.get("comparison") or {}
        r = parse_infer_ah(comp)
        if r is None:
            return None
        r["infer_event"] = comp.get("event_id")
        return r
    except Exception:
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=float, default=12.0, help="只拉距开赛<=N小时")
    ap.add_argument("--ttl", type=float, default=3.0, help="同场N小时内不重拉")
    ap.add_argument("--budget", type=int, default=0, help="今日AH调用硬上限(0=仅靠剩余配额自动停)")
    ap.add_argument("--reserve", type=int, default=25, help="日剩余<=N立即硬停")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-infer", action="store_true", help="跳过InferSports免费亚盘, 只走API-Football")
    ap.add_argument("--infer-only", action="store_true", help="只用InferSports免费亚盘, 不耗API-Football额度")
    args = ap.parse_args()

    ms = latest_scan()
    if not ms:
        print("无赛程文件"); return
    now = datetime.now(timezone.utc)
    st = load_state()
    fmap = load_fixture_map()
    try:
        out = json.load(io.open(OUT_FP, encoding="utf-8"))
    except Exception:
        out = {}
    if not isinstance(out, dict):
        out = {}
    need_dates = set()
    pend = []
    for m in ms:
        try:
            ct = datetime.fromisoformat(str(m["ct"]).replace("Z", "+00:00"))
        except Exception:
            continue
        if ct <= now:
            continue
        mins = (ct - now).total_seconds() / 3600.0
        if mins > args.window:
            continue
        pend.append((m, ct))
        need_dates.add(ct.strftime("%Y-%m-%d"))
    print("窗口内未开赛 %d 场 | 日期 %s | 今日已用AH %d" % (len(pend), sorted(need_dates), st["calls"]))
    pulled = pulled_infer = skipped = nomatch = 0
    for m, ct in sorted(pend, key=lambda x: x[1]):
        eid = str(m["id"])
        rec = out.get(eid) or {}
        if rec.get("pulled_at") and not args.force:
            try:
                pt = datetime.fromisoformat(str(rec["pulled_at"]))
                if (now - pt.astimezone(timezone.utc)).total_seconds() < args.ttl * 3600:
                    skipped += 1
                    continue
            except Exception:
                pass
        if not args.no_infer:
            try:
                got = infer_ah(m["home"], m["away"], ct)
            except Exception:
                got = None
            if got:
                rec_out = {"fixture": "infer", "home": m["home"], "away": m["away"],
                           "home_line": got["line"], "home_price": got["home_price"],
                           "away_price": got["away_price"], "books": got["books"],
                           "pulled_at": datetime.now(timezone.utc).isoformat(), "src": "infersports"}
                if got.get("infer_event"):
                    rec_out["infer_event"] = got["infer_event"]
                out[eid] = rec_out
                pulled_infer += 1
                print("  AH(infer) %s vs %s | %+.2f @%.2f/%.2f (%d家) | src=infersports" % (
                    m["home"], m["away"], got["line"], got["home_price"], got["away_price"], got["books"]))
                continue
        if args.infer_only:
            nomatch += 1
            print("  NOINFER %s vs %s" % (m["home"], m["away"]))
            continue
        fixs = fixtures_for_date(fmap, ct.strftime("%Y-%m-%d"), st)
        f = match_fixture(fixs, m, None)
        if not f:
            nomatch += 1
            print("  NOMATCH %s vs %s" % (m["home"], m["away"]))
            continue
        body, hdr = get("%s/odds?fixture=%d" % (BASE, f["id"]))
        st["calls"] += 1
        day_rem = hdr.get("x-ratelimit-requests-remaining") or hdr.get("x-ratelimit-requests-remaining", "")
        try:
            day_rem_i = int(day_rem)
        except Exception:
            day_rem_i = 999
        min_rem = hdr.get("x-ratelimit-remaining", "?")
        try:
            min_rem_i = int(min_rem)
        except Exception:
            min_rem_i = 99
        if args.budget and st["calls"] >= args.budget:
            st["stopped"] = "budget(%d)" % args.budget
            break
        if day_rem_i <= args.reserve or min_rem_i <= 2:
            st["stopped"] = "quota(day_rem=%s,min_rem=%s)" % (day_rem_i, min_rem_i)
            print("!! 配额不足硬停: 日剩%s 分剩%s" % (day_rem_i, min_rem_i))
            break
        if body.get("errors"):
            print("  ERR fixture %s: %s" % (f["id"], body["errors"]))
            time.sleep(6)
            continue
        ml = main_line_from_odds(body)
        if ml is None:
            print("  NOAH %s vs %s" % (m["home"], m["away"]))
            time.sleep(6)
            continue
        out[eid] = {"fixture": f["id"], "home": m["home"], "away": m["away"],
                    "home_line": ml["line"], "home_price": ml["home_price"],
                    "away_price": ml["away_price"], "books": ml["books"],
                    "pulled_at": datetime.now(timezone.utc).isoformat(), "src": "apifb_mainline"}
        pulled += 1
        print("  AH %s vs %s | %+.2f @%.2f/%.2f (%d家) | 日剩%s 分剩%s" % (
            m["home"], m["away"], ml["line"], ml["home_price"], ml["away_price"], ml["books"], day_rem_i, min_rem_i))
        time.sleep(6)
    json.dump(out, io.open(OUT_FP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    save_state(st)
    print("完成: 新拉(infer) %d | 新拉(apifb) %d | 跳过(TTL) %d | 无匹配 %d | 累计今日API-Football调用 %d | 存档 ah_spread_latest.json" % (
        pulled_infer, pulled, skipped, nomatch, st["calls"]))


if __name__ == "__main__":
    main()
