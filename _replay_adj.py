# -*- coding: utf-8 -*-
"""调整后回测: 快照重放 A/B (旧配置 vs 新配置), 无泄漏
旧配置 = strategy_data/league_calib.json.bak_20260824_leagueavg_6 (不含4联赛2024/25历史)
新配置 = strategy_data/league_calib.json (含4联赛2024/25历史 + 6联赛基准对齐 + 法甲方案A负校准)
"""
import sys, os, io, json, csv, re, unicodedata, collections, glob
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
import settle_batch

NEW_ESPN_2024 = {
    "espn_美职_2024_2025_results.csv", "espn_法乙_2024_2025_results.csv",
    "espn_瑞超_2024_2025_results.csv", "espn_巴甲_2024_2025_results.csv",
}
OLD_CAL = os.path.join(ROOT, "strategy_data", "league_calib.json.bak_20260824_leagueavg_6")
NEW_CAL = os.path.join(ROOT, "strategy_data", "league_calib.json")

def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def _date_of(s):
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

def build_team_stats(cutoff=None, include_espn_2024=True):
    files = [
        os.path.join(ROOT, "data", "raw", "football_data", "football_data_recent.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "matches_2015_2025.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "matches_2023_2024.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "api_supplement_2024_2025.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "api_supplement_2025_2026.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "j1_2026_results.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "csl_2026_results.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "supplement_P1_B1.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "bsd_batch_20260821.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "supplement_bsd_2026_2027_b1n1p1.csv"),
    ]
    _espn = os.path.join(ROOT, "data", "raw", "football_data")
    for _f in sorted(os.listdir(_espn)):
        if _f.startswith("espn_") and _f.endswith("_results.csv"):
            if (not include_espn_2024) and _f in NEW_ESPN_2024:
                continue
            files.append(os.path.join(_espn, _f))
        if _f.startswith("footballdata_") and _f.endswith("_results.csv"):
            files.append(os.path.join(_espn, _f))
    agg = collections.defaultdict(lambda: collections.defaultdict(dict))
    lavg_raw = collections.defaultdict(list)
    seen = set()
    for fp in files:
        if not os.path.exists(fp):
            continue
        with io.open(fp, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                season = (row.get("season") or row.get("Season") or "").strip()
                w = su.SEASON_WEIGHT.get(season)
                if not w:
                    continue
                div = (row.get("Div") or "").strip()
                if div not in su.ALL_DIVS:
                    continue
                d = _date_of(row.get("Date") or row.get("date") or row.get("Dt"))
                if cutoff is not None:
                    if d is None:
                        if season in ("2026", "2026/2027", "2025/2026"):
                            continue
                    elif d.date() > cutoff.date():
                        continue
                h, a = row["HomeTeam"], row["AwayTeam"]
                key = (season, div, h, a, row.get("Date") or "")
                if key in seen:
                    continue
                seen.add(key)
                try:
                    hg, ag = int(float(row["FTHG"])), int(float(row["FTAG"]))
                except Exception:
                    continue
                if fp.endswith("football_data_recent.csv") and season == "2025/2026":
                    lavg_raw[div].append(hg + ag)
                r = agg[h].setdefault(div, {
                    "home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0],
                    "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0],
                    "best_w": 0.0, "best_season": ""})
                r["home_gf"][0] += hg * w; r["home_gf"][1] += w
                r["home_ga"][0] += ag * w; r["home_ga"][1] += w
                if w > r["best_w"]:
                    r["best_w"] = w; r["best_season"] = season
                ra = agg[a].setdefault(div, {
                    "home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0],
                    "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0],
                    "best_w": 0.0, "best_season": ""})
                ra["away_gf"][0] += ag * w; ra["away_gf"][1] += w
                ra["away_ga"][0] += hg * w; ra["away_ga"][1] += w
                if w > ra["best_w"]:
                    ra["best_w"] = w; ra["best_season"] = season
    def avg(v):
        return round(v[0] / v[1], 3) if v[1] > 0 else 0.0
    out = {}
    for team, divs in agg.items():
        for div, r in divs.items():
            out.setdefault(team, {})[div] = {
                "home_gf": avg(r["home_gf"]), "home_ga": avg(r["home_ga"]),
                "away_gf": avg(r["away_gf"]), "away_ga": avg(r["away_ga"]),
                "n_home": round(r["home_gf"][1], 1), "n_away": round(r["away_gf"][1], 1),
                "src_w": r["best_w"], "src_season": r["best_season"],
                "src_tag": su.SRC_TAG.get(r["best_season"], "old") if r["best_w"] > 0 else None,
            }
    index = {}
    for t in out:
        index.setdefault(su._norm(t), t)
    for alias, std in su.ALIAS.items():
        index.setdefault(su._norm(alias), std)
        index.setdefault(su._norm(std), std)
        if (index.get(su._norm(alias)) == alias
                and any("\u4e00" <= ch <= "\u9fff" for ch in std)):
            index[su._norm(std)] = alias
    lavg = {d: round(sum(v) / len(v), 4) for d, v in lavg_raw.items() if v}
    return out, lavg, index

def load_scores():
    files = glob.glob(os.path.join(ROOT, "analysis_records", "*批量结算.json"))
    files += glob.glob(os.path.join(ROOT, "analysis_records", "scan24h_settle_full_*.json"))
    scores = collections.defaultdict(list)   # (lg,norm_h,norm_a) -> [(ct_str, hg, ag)]
    for p in files:
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for r in d.get("rows") or []:
            sc = r.get("score")
            if not sc or "-" not in str(sc):
                continue
            try:
                hg, ag = str(sc).split("-")
                hg, ag = int(hg), int(ag)
            except Exception:
                continue
            lg = r.get("league"); h = r.get("home"); a = r.get("away")
            ct = r.get("ct") or r.get("kickoff") or ""
            if lg and h and a:
                scores[(lg, _norm(h), _norm(a))].append((str(ct), hg, ag))
    return scores

def find_score(scores, lg, h, a, kickoff):
    lst = scores.get((lg, _norm(h), _norm(a)))
    if not lst:
        return None
    kd = kickoff.date() if isinstance(kickoff, datetime) else None
    def _d(ct_s):
        for fmt in ("%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
            try:
                return datetime.strptime(ct_s.replace("Z", "+00:00"), fmt).date()
            except Exception:
                pass
        return None
    dated = [x for x in lst if _d(x[0]) is not None]
    # 重复文件(ct为空)与唯一值直接取首条
    if len(dated) == 0 or len(lst) == 1:
        return lst[0][1], lst[0][2]
    best = None; best_d = None
    for ct_s, hg, ag in lst:
        d = _d(ct_s)
        if d is None:
            continue
        dist = abs((d - kd).days) if kd else 0
        if best_d is None or dist < best_d:
            best_d = dist; best = (hg, ag)
    if best is None:
        return lst[0][1], lst[0][2]
    return best

def patch_cal(mode):
    path = OLD_CAL if mode == "old" else NEW_CAL
    try:
        cal = json.load(io.open(path, encoding="utf-8")).get("leagues", {})
    except Exception:
        cal = {}
    def _cal(lg):
        c = dict(cal.get(lg) or {})
        if not c:
            c = dict(su.CAL.get(lg) or {"league_avg": 2.6, "rho": 0.0, "shrink": 1.0,
                                        "home": 1.0, "away": 1.0, "fatigue": 1.0})
        return c
    su._cal_for_league = _cal
    # 旧配置: 法甲方案A负校准不存在
    if mode == "old":
        pass

_TS_CACHE = {}
def get_team_stats(mode, cutoff):
    dkey = cutoff.date().isoformat()
    key = (mode, dkey)
    if key in _TS_CACHE:
        return _TS_CACHE[key]
    ts, lavg, index = build_team_stats(cutoff=cutoff, include_espn_2024=(mode == "new"))
    _TS_CACHE[key] = (ts, lavg, index)
    return ts, lavg, index

def build_prematch_snapshots():
    src_path = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    tmp = os.path.join(ROOT, "_snap_prematch.csv")
    def _pt(s):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            return None
    keep = 0; drop = 0
    with io.open(src_path, "r", encoding="utf-8") as fin, io.open(tmp, "w", encoding="utf-8", newline="") as fout:
        rd = csv.reader(fin)
        wr = csv.writer(fout)
        hdr = next(rd)
        wr.writerow(hdr)
        for x in rd:
            if not x:
                continue
            st = _pt(x[0]); ct = _pt(x[3])
            if st is not None and ct is not None and st > ct:
                drop += 1
                continue
            wr.writerow(x)
            keep += 1
    print("prematch rows kept=%d dropped=%d" % (keep, drop))
    return tmp

def run():
    su.recent_league_avg = lambda: {}   # 关闭基准偏差平移, A/B 都用配置原值
    scores = load_scores()
    _tmp = build_prematch_snapshots()
    recs, fs = su.parse_snapshots(_tmp)
    # 快照索引: (lg, norm_h, norm_a) -> [rec]
    snap_idx = collections.defaultdict(list)
    for r in recs:
        snap_idx[(r["league"], _norm(r["home"]), _norm(r["away"]))].append(r)
    # 账本匹配列表
    led = list(csv.DictReader(io.open(os.path.join(ROOT, "analysis_records", "bet_ledger.csv"), encoding="utf-8-sig")))
    matches = {}
    for r in led:
        if r.get("status") != "已结算":
            continue
        lg = r["league"]; h = r["home"]; a = r["away"]; ko = r.get("kickoff") or ""
        try:
            kt = datetime.fromisoformat(ko.replace("Z", "+00:00")) if ko else None
        except Exception:
            kt = None
        key = (lg, h, a, ko)
        if key not in matches:
            matches[key] = {"league": lg, "home": h, "away": a, "kickoff": kt, "kickoff_s": ko}
    print("ledger settled matches:", len(matches))
    # 组装可重放场次
    replay = []
    for key, mm in matches.items():
        sc = find_score(scores, mm["league"], mm["home"], mm["away"], mm["kickoff"])
        if sc is None:
            continue
        cands = snap_idx.get((mm["league"], _norm(mm["home"]), _norm(mm["away"])), [])
        rec = None
        if mm["kickoff"] is not None:
            for c in cands:
                try:
                    diff = abs((c["ct"] - mm["kickoff"]).total_seconds())
                except Exception:
                    continue
                if diff <= 12 * 3600:
                    if rec is None or diff < rec[0]:
                        rec = (diff, c)
        if rec is None and len(cands) == 1:
            rec = (0, cands[0])
        if rec is None:
            continue
        rec = rec[1]
        # 确保快照为赛前 (snap <= ct)
        try:
            if rec["snap"] and rec["snap"] > rec["ct"]:
                continue
        except Exception:
            pass
        if not (rec.get("h2h") or {}).get("home") or not (rec.get("totals") or {}).get("line"):
            continue
        replay.append({
            "league": mm["league"], "home": rec["home"], "away": rec["away"],
            "ct": rec["ct"], "hg": sc[0], "ag": sc[1],
            "h2h": rec["h2h"], "spread": rec.get("spread"), "totals": rec.get("totals"),
            "id": rec["id"], "snap": rec["snap"], "books": rec.get("books_used"),
        })
    print("replayable matches:", len(replay))
    from collections import Counter
    print(Counter(x["league"] for x in replay))

    out = []
    for m in replay:
        res = {"league": m["league"], "home": m["home"], "away": m["away"],
               "ct": m["ct"].isoformat(), "hg": m["hg"], "ag": m["ag"],
               "snap": str(m.get("snap")), "books": m.get("books")}
        for mode in ("old", "new"):
            patch_cal(mode)
            cutoff = m["ct"]
            ts, lavg, index = get_team_stats(mode, cutoff)
            mm = {"id": m["id"], "league": m["league"], "home": m["home"], "away": m["away"],
                  "ct": m["ct"], "h2h": m["h2h"], "spread": m["spread"], "totals": m["totals"],
                  "coach_mods": {}}
            try:
                r = su.analyze_match(mm, ts, lavg, index)
            except Exception as e:
                res[mode] = {"error": str(e)}
                continue
            legs = []
            for b in r.get("bets") or []:
                try:
                    lres, lret = settle_batch.settle_leg(b["name"], b.get("odds") or 0.0, m["hg"], m["ag"])
                except Exception:
                    lres, lret = "unknown", None
                legs.append({"name": b["name"], "prob": b.get("prob"), "odds": b.get("odds"),
                             "ev": b.get("ev"), "star": b.get("star"), "ev_tier": b.get("ev_tier"),
                             "result": lres, "pnl": (lret - 1.0) if lret is not None else None})
            res[mode] = {
                "lambda": r.get("lambda"),
                "wdl": r.get("wdl"),
                "direction": (r.get("direction") or {}).get("name"),
                "dir_ev": (r.get("direction") or {}).get("ev"),
                "dir_prob": (r.get("direction") or {}).get("prob"),
                "vetoed": (r.get("direction") or {}).get("vetoed"),
                "risk_tags": r.get("risk_tags"),
                "draw_warn": r.get("draw_warn"),
                "bets": legs,
                "notes": r.get("notes"),
            }
        out.append(res)
    with io.open(os.path.join(ROOT, "_replay_adj_out.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print("saved _replay_adj_out.json  n=", len(out))

if __name__ == "__main__":
    run()
