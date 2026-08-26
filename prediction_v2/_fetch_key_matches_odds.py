# -*- coding: utf-8 -*-
"""临时工具v5: 按 parse_snapshots 同款逻辑(同庄同线最低抽水)生成12场盘口overlay。"""
import json, os, sys, io, unicodedata, collections
from datetime import datetime, timezone
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
from live_odds import fetch_league_odds, flatten_events
from api_router import OddsApiRouter

LEAGUE_SPORT = {
    "Coppa Italia": ("意杯", "soccer_italy_coppa_italia"),
    "Liga Portugal Betclic": ("葡超", "soccer_portugal_primeira_liga"),
    "Liga Profesional de Fútbol": ("阿甲", "soccer_argentina_primera_division"),
    "Champions League": ("欧冠", "soccer_uefa_champs_league_qualification"),
}
GEN = {"fc", "afc", "cf", "sc", "ac", "as", "us", "cd", "de", "sd", "ud", "ssc", "gnk", "ca", "esg"}
TOKEN_ALIAS = {"lyon": "lyonnais"}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).lower()
    return " ".join(TOKEN_ALIAS.get(w, w) for w in s.split() if w not in GEN)

def side_ok(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return False
    return a == b or sa <= sb or sb <= sa or len(sa & sb) / len(sa | sb) >= 0.6

def lowest_orr(prices, need):
    """同一庄同一条线: 计算抽水, 缺腿跳过。"""
    if any(prices.get(k) is None for k in need):
        return None
    try:
        return sum(1.0 / float(prices[k]) for k in need)
    except Exception:
        return None

def main():
    router = OddsApiRouter(project_root=ROOT)
    key = router.keys[0][0]
    v2 = json.load(io.open(os.path.join(ROOT, "analysis_records", "bsd_v2_2026-08-17.json"), encoding="utf-8"))
    targets = []
    for eid, d in (v2.get("data") or {}).items():
        ev = (d.get("prediction") or {}).get("event") or {}
        targets.append({"eid": str(eid), "league_raw": ev.get("league_name"), "home": ev.get("home_team"),
                        "away": ev.get("away_team"), "ct": ev.get("event_date")})
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    overlay = {}
    for league_raw, (lg_cn, sport) in LEAGUE_SPORT.items():
        try:
            events, quota = fetch_league_odds(key, sport, markets="h2h,spreads,totals",
                                              regions="eu,uk,us", timeout=40)
        except Exception as e:
            print("抓取失败", league_raw, e)
            continue
        rows = flatten_events(events, lg_cn, ts)
        by_event = collections.defaultdict(list)
        for r in rows:
            by_event[r["event_id"]].append(r)
        for eid, rs in by_event.items():
            r0 = rs[0]
            # 按 (book, market, line) 分组
            groups = collections.defaultdict(dict)
            for r in rs:
                gk = (r["bookmaker"], r["market"], r["point"])
                groups[gk][r["side"]] = float(r["price"])
                if r["market"] == "spreads":
                    groups[gk]["_line_" + r["side"]] = r["point"]
            h2h = None
            cands = []
            for (bk, mk, pt), prices in groups.items():
                if mk != "h2h":
                    continue
                o = lowest_orr(prices, ["home", "draw", "away"])
                if o is not None:
                    cands.append((o, bk, prices))
            if cands:
                cands.sort(key=lambda c: c[0])
                _o, _bk, prices = cands[0]
                h2h = {"home": prices["home"], "draw": prices["draw"], "away": prices["away"], "bk": _bk, "orr": _o}
            tt = None
            cands = []
            for (bk, mk, pt), prices in groups.items():
                if mk != "totals" or pt != 2.5:
                    continue
                o = lowest_orr(prices, ["over", "under"])
                if o is not None:
                    cands.append((o, bk, prices))
            if cands:
                cands.sort(key=lambda c: c[0])
                _o, _bk, prices = cands[0]
                tt = {"line": 2.5, "over": prices["over"], "under": prices["under"], "bk": _bk, "orr": _o}
            sp = None
            cands = []
            for (bk, mk, pt), prices in groups.items():
                if mk != "spreads":
                    continue
                o = lowest_orr(prices, ["home", "away"])
                if o is None:
                    continue
                line = abs(float(prices.get("_line_home", pt))) if pt is not None else 0.0
                cands.append((abs(line - 0.5), o, bk, prices, line))
            if cands:
                cands.sort(key=lambda c: (c[0], c[1]))
                _d, _o, _bk, prices, line = cands[0]
                hdp_home = prices.get("_line_home")
                if hdp_home is None:
                    hdp_home = -prices.get("_line_away", line)
                sp = {"hdp_home": hdp_home, "home_price": prices["home"], "away_price": prices["away"],
                      "bk": _bk, "orr": _o}
            m = {"eid": None, "h2h": h2h, "totals": tt, "spread": sp,
                 "home_team": r0["home_team"], "away_team": r0["away_team"],
                 "commence_time": r0["commence_time"], "snap_iso": ts, "source": "the-odds-api"}
            for t in targets:
                if t["league_raw"] != league_raw:
                    continue
                try:
                    td = datetime.fromisoformat(str(t["ct"]).replace("Z", "+00:00"))
                    ed = datetime.fromisoformat(str(r0["commence_time"]).replace("Z", "+00:00"))
                except Exception:
                    continue
                if abs((td - ed).total_seconds()) > 2700:
                    continue
                nh, na, neh, nea = norm(t["home"]), norm(t["away"]), norm(r0["home_team"]), norm(r0["away_team"])
                if side_ok(nh, neh) and side_ok(na, nea):
                    m["eid"] = t["eid"]; m["league"] = lg_cn
                    m["target_home"], m["target_away"] = t["home"], t["away"]
                    break
            if m["eid"]:
                overlay[m["eid"]] = m
    out = os.path.join(ROOT, "analysis_records", "key_matches_odds_20260817.json")
    json.dump({"ts": ts, "overlay": overlay}, io.open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("覆盖", len(overlay), "场 ->", out)
    for eid, m in overlay.items():
        h, t, s = m["h2h"], m["totals"], m["spread"]
        hs = ("%s/%s/%s[%s]" % (h["home"], h["draw"], h["away"], h["bk"])) if h else "无"
        ts_ = ("大%.2f@%.2f/小%.2f[%s]" % (t["line"], t["over"], t["under"], t["bk"])) if t else "无"
        ss = ("主%.1f@%.2f/客%.1f@%.2f[%s]" % (s["hdp_home"], s["home_price"], -s["hdp_home"], s["away_price"], s["bk"])) if s else "无"
        print(eid, m["target_home"], "vs", m["target_away"], "|", hs, "|", ts_, "|", ss)

if __name__ == "__main__":
    main()
