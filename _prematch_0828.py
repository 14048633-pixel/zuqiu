# -*- coding: utf-8 -*-
"""27号47场 - 临盘重拉(API-Football) + 注入重跑 (2026-08-28)"""
import io, sys, os, json, urllib.request, time, statistics, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
BJT = timezone(timedelta(hours=8))
def load_env(path):
    out = {}
    try:
        for ln in open(path, encoding="utf-8", errors="replace").read().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out
ENV = load_env(os.path.join(ROOT, ".env"))
KEY = ENV.get("FOOTBALL_API_KEY", "").strip()
BASE = "https://v3.football.api-sports.io"
def get(url):
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))
def median(xs):
    return round(statistics.median(xs), 4) if xs else None
def parse_odds(resp):
    aggr = {"h2h": {}, "ah": {}, "ou": {}}
    for r0 in (resp.get("response") or []):
        for bk in (r0.get("bookmakers") or []):
            for b in (bk.get("bets") or []):
                bn = b.get("name") or ""
                vals = {}
                for v in (b.get("values") or []):
                    key = str(v.get("value") or "").strip()
                    odd = v.get("odd")
                    if key and odd:
                        vals[key] = float(odd)
                if bn == "Match Winner" and vals.get("Home") and vals.get("Draw") and vals.get("Away"):
                    aggr["h2h"].setdefault("home", []).append(vals["Home"])
                    aggr["h2h"].setdefault("draw", []).append(vals["Draw"])
                    aggr["h2h"].setdefault("away", []).append(vals["Away"])
                elif bn == "Asian Handicap":
                    for k, odd in vals.items():
                        try:
                            line = float(k)
                        except Exception:
                            continue
                        d = aggr["ah"].setdefault(line, {"home": [], "away": []})
                        if k.startswith("-"):
                            d["home"].append(odd)
                        elif k.startswith("+"):
                            d["away"].append(odd)
                elif bn == "Goals Over/Under":
                    for k, odd in vals.items():
                        low = k.lower()
                        if low.startswith("over"):
                            try:
                                line = float(low.replace("over", "").strip())
                            except Exception:
                                continue
                            aggr["ou"].setdefault(line, {"over": [], "under": []})["over"].append(odd)
                        elif low.startswith("under"):
                            try:
                                line = float(low.replace("under", "").strip())
                            except Exception:
                                continue
                            aggr["ou"].setdefault(line, {"over": [], "under": []})["under"].append(odd)
    out = {}
    if aggr["h2h"].get("home"):
        out["h2h"] = {"home": median(aggr["h2h"]["home"]), "draw": median(aggr["h2h"]["draw"]),
                      "away": median(aggr["h2h"]["away"]), "n_bk": len(aggr["h2h"]["home"])}
    if aggr["ah"]:
        best_line, best_n = None, -1
        for line, d in aggr["ah"].items():
            n = min(len(d["home"]), len(d["away"]))
            if n > best_n:
                best_n, best_line = n, line
        if best_line is not None:
            d = aggr["ah"][best_line]
            hp, ap = median(d["home"]), median(d["away"])
            if hp and ap:
                out["spread"] = {"line": best_line, "home_price": hp, "away_price": ap, "n_lines": best_n}
    if aggr["ou"]:
        line = 2.5 if 2.5 in aggr["ou"] else max(aggr["ou"], key=lambda k: len(aggr["ou"][k]["over"]) + len(aggr["ou"][k]["under"]))
        d = aggr["ou"][line]
        op, up = median(d["over"]), median(d["under"])
        if op and up:
            out["totals"] = {"line": line, "over_price": op, "under_price": up,
                             "n_lines": min(len(d["over"]), len(d["under"]))}
    return out
LG_MAP = {
    "Emperor Cup": "天皇杯", "Carabao Cup": "英联杯", "Copa do Brasil": "巴西杯",
    "Copa Libertadores": "解放者杯", "Champions League": "欧冠", "Saudi Pro League": "沙超",
    "K League 1": "K联赛", "Brasileirao Serie B": "巴乙", "Brasileirao Serie A": "巴甲",
    "La Liga": "西甲", "Categoria Primera A": "哥甲", "Club Friendlies": "友谊赛",
    "Europa League": "欧联杯", "Conference League": "欧协联", "Copa Sudamericana": "南美杯", "NWSL": "NWSL",
    "USL Championship": "USL", "Chinese Super League": "中超", "J1 League": "J1",
    "Premier League": "英超", "Championship": "英冠", "League One": "英甲",
    "League Two": "英乙", "Ligue 1": "法甲", "Ligue 2": "法乙", "Bundesliga": "德甲",
    "Serie A": "意甲", "Eredivisie": "荷甲", "Liga Portugal Betclic": "葡超",
    "Pro League": "比甲", "Trendyol Super Lig": "土超", "Ekstraklasa": "波甲",
    "MLS": "美职", "Liga MX Apertura": "墨超", "Liga Profesional de Futbol": "阿甲",
    "Copa del Rey": "国王杯", "Coppa Italia": "意大利杯", "DFB Pokal": "德国杯",
    "Segunda Division": "西乙", "Liga Portugal 2": "葡乙", "Super League": "瑞超",
    "National League": "英议联",
}
def pkg_league(mid):
    fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % mid)
    try:
        return json.load(io.open(fp, encoding="utf-8")).get("league")
    except Exception:
        return None
def main():
    su.recent_league_avg = lambda: {}
    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260827_1947.json"), encoding="utf-8"))["matches"]
    ahd = {}
    try:
        ahd = json.load(io.open(os.path.join(ROOT, "analysis_records", "ah_spread_20260827_1947.json"), encoding="utf-8")).get("spreads") or {}
    except Exception:
        pass
    team_stats, lavg, index = su.load_team_stats()
    now = datetime.now(timezone.utc)
    pend = []
    for m in lst:
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        if ct <= now:
            continue
        fid = (ahd.get(str(m["id"])) or {}).get("fixture_id")
        pend.append({"m": m, "ct": ct, "fid": fid})
    print("未开赛场次:", len(pend))
    fresh = {}
    ok = fail = 0
    for i, p in enumerate(pend):
        fid = p["fid"]
        if not fid:
            fail += 1
            print("  [%d/%d] no fid: %s %s vs %s" % (i+1, len(pend), p["m"]["id"], p["m"]["home"], p["m"]["away"]))
            continue
        try:
            resp = get("%s/odds?fixture=%s" % (BASE, fid))
        except Exception as e:
            fail += 1
            print("  [%d/%d] ERR %s: %s" % (i+1, len(pend), p["m"]["home"], repr(e)[:120]))
            time.sleep(3)
            continue
        od = parse_odds(resp)
        if od.get("h2h"):
            ok += 1
        else:
            fail += 1
            print("  [%d/%d] 无1X2盘: %s vs %s (fid=%s)" % (i+1, len(pend), p["m"]["home"], p["m"]["away"], fid))
        fresh[str(p["m"]["id"])] = {"home": p["m"]["home"], "away": p["m"]["away"], "fixture_id": fid, "odds": od}
        time.sleep(6.5)
    print("临盘拉取: 有1X2 %d / 失败或无盘 %d" % (ok, fail))
    ts = now.strftime("%Y%m%d_%H%M")
    out_fp = os.path.join(ROOT, "analysis_records", "prematch_odds_%s.json" % ts)
    json.dump({"generated": datetime.now(BJT).isoformat(), "n": len(pend), "odds": fresh},
              io.open(out_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", out_fp)
    events = []
    for p in pend:
        m = p["m"]
        lg = LG_MAP.get(pkg_league(m["id"])) or LG_MAP.get(m.get("league")) or m.get("league") or "未知"
        ev = {"id": m["id"], "lg": lg, "league": lg, "ct": p["ct"], "home": m["home"], "away": m["away"],
              "snap": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "odds": collections.defaultdict(list)}
        _ah = ahd.get(str(m["id"]))
        if _ah:
            ev["spread"] = {"hdp_home": _ah["line"], "home_price": _ah["home_price"], "away_price": _ah["away_price"]}
            ev["ah_src"] = "apifb(%s)" % (_ah.get("book") or "?")
        f = fresh.get(str(m["id"]))
        if f and f["odds"].get("h2h"):
            ev["h2h"] = f["odds"]["h2h"]; ev["h2h_src"] = "apifb_prematch"
        if f and f["odds"].get("spread"):
            sp = f["odds"]["spread"]
            ev["spread"] = {"hdp_home": sp["line"], "home_price": sp["home_price"], "away_price": sp["away_price"]}
            ev["ah_src"] = "apifb_prematch"
        if f and f["odds"].get("totals"):
            tt = f["odds"]["totals"]
            ev["totals"] = {"line": tt["line"], "over_price": tt["over_price"], "under_price": tt["under_price"]}
            ev["totals_src"] = "apifb_prematch"
        events.append(ev)
    try:
        n = su.bsd_odds_merge(events)
        print("BSD merge 覆盖(仅补缺):", n)
    except Exception as e:
        print("bsd_odds_merge skip:", repr(e)[:150])
    rows = []
    for m in events:
        try:
            r = su.analyze_match(m, team_stats, lavg, index)
        except Exception as e:
            r = {"error": str(e)}
        rows.append({"match": m, "result": r})
    rows.sort(key=lambda x: x["match"]["ct"])
    out = []
    for x in rows:
        m = x["match"]; r = x["result"]
        if isinstance(r, dict) and r.get("error"):
            out.append({"ko_bjt": m["ct"].astimezone(BJT).strftime("%m-%d %H:%M"), "ko_utc": m["ct"].isoformat(),
                        "league": m["league"], "home": m["home"], "away": m["away"], "error": r["error"]})
            continue
        di = r.get("direction") or {}
        bb = r.get("best_bet")
        out.append({
            "ko_bjt": m["ct"].astimezone(BJT).strftime("%m-%d %H:%M"),
            "ko_utc": m["ct"].isoformat(),
            "league": m["league"], "home": m["home"], "away": m["away"],
            "h2h_src": m.get("h2h_src"), "ah_src": m.get("ah_src"), "totals_src": m.get("totals_src"),
            "lambda": r.get("lambda"), "wdl": r.get("wdl"), "market_fair": r.get("market_fair"),
            "direction": di.get("name"), "dir_prob": di.get("prob"), "dir_odds": di.get("odds"),
            "dir_ev": di.get("ev"), "vetoed": di.get("vetoed"), "veto_reason": di.get("veto_reason"),
            "draw_warn": r.get("draw_warn"), "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "risk_tags": r.get("risk_tags") or [], "dir_consistency": r.get("dir_consistency"),
            "best_bet": bb, "bets": r.get("bets"), "notes": r.get("notes") or [], "error": None,
        })
    res_fp = os.path.join(ROOT, "analysis_records", "scan_next24h_%s_prematch.json" % ts)
    json.dump(out, io.open(res_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", res_fp, "| 场次:", len(out))
    from collections import Counter
    bb_cnt = Counter(); veto = 0; err = 0
    for o in out:
        if o.get("best_bet"):
            bb_cnt[o["best_bet"].get("star")] += 1
        if o.get("vetoed"):
            veto += 1
        if o.get("error"):
            err += 1
    print("BEST 星级分布:", dict(bb_cnt), "| 否决:", veto, "| error:", err,
          "| 有1X2盘:", sum(1 for o in out if o.get("h2h_src")),
          "| 有亚盘:", sum(1 for o in out if o.get("ah_src")),
          "| 有大小球:", sum(1 for o in out if o.get("totals_src")))
if __name__ == "__main__":
    main()
