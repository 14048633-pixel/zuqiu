# -*- coding: utf-8 -*-
"""每场数据包拉取: 赛程 -> 赔率 -> 伤停 -> 阵型 -> 攻防历史(缺失才补拉)
================================================
用法:
  python prediction_v2/pull_match_package.py --all                # 读最新 scan48h 全部未开赛
  python prediction_v2/pull_match_package.py --id 588012          # 单场
  python prediction_v2/pull_match_package.py --league 欧冠        # 按联赛过滤批量
  python prediction_v2/pull_match_package.py --force              # 重拉已有包(默认跳过24h内已拉)
输出: analysis_records/match_package/{event_id}.json
原则: 缺数据标注"未提取", 不伪造; 只新增文件, 不改动任何现有数据.
"""
import io, os, sys, json, glob, time, argparse, unicodedata
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
BJT = timezone(timedelta(hours=8))
PKG_DIR = os.path.join(ROOT, "analysis_records", "match_package")
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
os.chdir(ROOT)

import requests
from injuries_bzzoiro import HEADERS, load_token
import bsd_extra
import scan_upcoming as su

BASE = "https://sports.bzzoiro.com/api/v2"
TTL = 24 * 3600  # 已有包 24h 内不重拉


def log(msg):
    print("%s %s" % (datetime.now(BJT).strftime("%m-%d %H:%M:%S"), msg))


def bsd_get(path, tries=2, timeout=25):
    for i in range(1, tries + 1):
        try:
            r = requests.get(BASE + path, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code < 500:
                return None
        except Exception:
            pass
        if i < tries:
            time.sleep(2)
    return None


def latest_scan():
    fs = [f for pat in ("scan48h_*.json", "scan24h_*.json")
          for f in glob.glob(os.path.join(ROOT, "analysis_records", pat))
          if "finished" not in f]
    if not fs:
        return None
    fs.sort(key=lambda f: os.path.getmtime(f), reverse=True)  # 按修改时间取最新, 避免 final 等旧文件
    for fp in fs[:5]:
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
            ms = d.get("matches") or []
            if ms:
                return ms
        except Exception:
            continue
    return None


# ===== 攻防历史: 本地覆盖检查 + BSD 补拉 =====
def _load_local_attack():
    """合并 bsd_team_stats_*.json 攻防归档 -> {队名: stats}; 空dict不报错."""
    out = {}
    for fp in [f for pat in ("bsd_team_stats_*.json", "footballdata_team_stats_*.json")
         for f in glob.glob(os.path.join(ROOT, "data", "raw", "football_data", pat))]:
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
            st = d.get("stats") or {}
            for tn, s in st.items():
                if isinstance(s, dict) and s.get("n_home") is not None:
                    out.setdefault(tn.strip().lower(), s)
        except Exception:
            continue
    return out


_LOCAL_ATK = None


def local_attack():
    global _LOCAL_ATK
    if _LOCAL_ATK is None:
        _LOCAL_ATK = _load_local_attack()
    return _LOCAL_ATK


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").replace(".", " ").replace("'", " ").split())


def check_local_attack(league, home, away):
    """-> (dict) {home:{have,src,stats}, away:{...}}. src: local_csv / local_bsd / None."""
    out = {}
    loc = local_attack()
    try:
        ts, lavg, index = su.load_team_stats()
    except Exception:
        ts, index = {}, {}
    div = su.DIV_BY_LEAGUE.get(league)
    for side, name in (("home", home), ("away", away)):
        got = None
        src = None
        nrm = norm(name)
        if nrm in loc:
            got, src = loc[nrm], "local_bsd"
        else:
            std = index.get(nrm) or nrm
            team_div = ts.get(std, {})
            if div and div in team_div:
                got, src = team_div[div], "local_csv"
            elif team_div:
                best = max(team_div, key=lambda d: team_div[d].get("src_w", 0))
                got, src = team_div[best], "local_csv"
        out[side] = {"have": got is not None, "src": src, "stats": got}
    return out


def w_of(idx):
    if idx < 5:
        return 1.0
    if idx < 10:
        return 0.7
    if idx < 20:
        return 0.4
    return 0.2


def pull_attack_bsd(team_id, team_name):
    """BSD 补拉单队近40场攻防 -> stats dict; 失败/无赛果返回 None."""
    if not team_id:
        return None
    j = bsd_get("/events/?team_id=%d&status=finished&limit=60" % team_id)
    if not j:
        return None
    scored = []
    for e in (j.get("results") or []):
        hs, as_ = e.get("home_score"), e.get("away_score")
        if hs is None or as_ is None:
            continue
        scored.append((e.get("event_date") or "", e.get("home_team"), hs, as_, e.get("away_team")))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None
    rec = {"home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0], "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0]}
    for idx, (dt, h, hs, as_, a) in enumerate(scored[:40]):
        w = w_of(idx)
        is_home = (h or "").strip().lower() == (team_name or "").strip().lower()
        if is_home:
            rec["home_gf"][0] += float(hs) * w; rec["home_gf"][1] += w
            rec["home_ga"][0] += float(as_) * w; rec["home_ga"][1] += w
        else:
            rec["away_gf"][0] += float(as_) * w; rec["away_gf"][1] += w
            rec["away_ga"][0] += float(hs) * w; rec["away_ga"][1] += w

    def avg(v):
        return round(v[0] / v[1], 3) if v[1] > 0 else 0.0

    return {"home_gf": avg(rec["home_gf"]), "home_ga": avg(rec["home_ga"]),
            "away_gf": avg(rec["away_gf"]), "away_ga": avg(rec["away_ga"]),
            "n_home": round(rec["home_gf"][1], 1), "n_away": round(rec["away_gf"][1], 1),
            "n_scored": len(scored), "src_season": "BSD", "src_w": 1.0, "src_tag": "bsd",
            "team_id": team_id}


# 
# ===== league_id -> 中文名 映射(单场模式补全) =====
_LEAGUE_CN = None

def _league_name(lid):
    global _LEAGUE_CN
    if _LEAGUE_CN is None:
        _LEAGUE_CN = {}
        try:
            for nm, i in bsd_extra.leagues_list():
                _LEAGUE_CN[i] = nm
        except Exception:
            pass
    return _LEAGUE_CN.get(lid)



_COACH_CACHE = None


def _load_coach_cache():
    global _COACH_CACHE
    if _COACH_CACHE is None:
        try:
            d = json.load(io.open(os.path.join(ROOT, "analysis_records", "coach_cache.json"), encoding="utf-8"))
            _COACH_CACHE = {"coaches": d.get("coaches") or {}, "by_name": d.get("by_name") or {}}
        except Exception:
            _COACH_CACHE = {"coaches": {}, "by_name": {}}
    return _COACH_CACHE


def _coach_from_cache(cid, cname):
    """coach_cache 查教练(id 优先, name 兜底) -> {name,profile,preferred_formation,...} 或 None."""
    cc = _load_coach_cache()
    rec = cc["coaches"].get(str(cid)) if cid else None
    if not rec and cname:
        nid = cc["by_name"].get(cname.strip().lower())
        if nid:
            rec = cc["coaches"].get(str(nid))
    if not rec:
        return None
    return {"id": rec.get("id"), "name": rec.get("name"), "short_name": rec.get("short_name"),
            "profile": rec.get("tactical_profile") or rec.get("profile"),
            "preferred_formation": rec.get("preferred_formation"),
            "matches_total": rec.get("matches_total"),
            "avg_goals_scored": rec.get("avg_goals_scored"),
            "avg_goals_conceded": rec.get("avg_goals_conceded")}


# ===== 单场打包 =====
def build_package(m, force=False):
    eid = m["id"]
    fp = os.path.join(PKG_DIR, "%d.json" % eid)
    if os.path.exists(fp) and not force:
        mt = os.path.getmtime(fp)
        if time.time() - mt < TTL:
            return "skip_existing"
    pkg = {
        "id": eid,
        "league": m.get("league"),
        "kickoff": m.get("kickoff"),
        "kickoff_iso": m.get("kickoff_iso"),
        "home": m.get("home"),
        "away": m.get("away"),
        "home_id": m.get("home_id"),
        "away_id": m.get("away_id"),
        "pulled_at": datetime.now(BJT).isoformat(),
        "missing": [],
    }

    # 1) 赛程基础(event detail: 教练/场地/轮次)
    ev = bsd_get("/events/%d/" % eid)
    if ev:
        # league 名兜底: 批量模式已有, 单场模式只有 league_id
        if not pkg.get("league"):
            pkg["league"] = ev.get("league_name") or _league_name(ev.get("league_id"))
        ch = _coach_from_cache(ev.get("home_coach_id"), ev.get("home_coach_name"))
        ca = _coach_from_cache(ev.get("away_coach_id"), ev.get("away_coach_name"))
        pkg["schedule"] = {
            "venue": (ev.get("venue") or {}).get("name") if isinstance(ev.get("venue"), dict) else None,
            "round": ev.get("round"),
            "group": ev.get("group"),
            "coaches": {"home": ch, "away": ca},
            "preferred_formation": {
                "home": (ch or {}).get("preferred_formation"),
                "away": (ca or {}).get("preferred_formation"),
            },
        }
        if not ch:
            pkg["missing"].append("home教练(coach_cache未命中 id=%s) 未提取" % ev.get("home_coach_id"))
        if not ca:
            pkg["missing"].append("away教练(coach_cache未命中 id=%s) 未提取" % ev.get("away_coach_id"))
    else:
        pkg["missing"].append("赛程详情(BSD event detail) 未提取")
        pkg["schedule"] = None

    # 2) 赔率 (BSD consensus + best)
    odds = bsd_extra.fetch_odds(eid)
    if odds:
        pkg["odds"] = odds
    else:
        pkg["missing"].append("BSD赔率 未提取")
        pkg["odds"] = None

    # 3) 伤停 + 4) 阵型 (BSD lineups)
    lu = bsd_extra.fetch_lineups(eid)
    if lu:
        up = lu.get("unavailable_players") or {"home": [], "away": []}
        inj = {"home": up.get("home") or [], "away": up.get("away") or [],
               "home_covered": bool(up.get("home")) or lu.get("lineup_status") == "confirmed",
               "away_covered": bool(up.get("away")) or lu.get("lineup_status") == "confirmed",
               "sources": {"home": "bsd_lineups", "away": "bsd_lineups"}}
        pkg["injuries"] = inj
        pkg["lineups"] = {
            "lineup_status": lu.get("lineup_status"),
            "confidence": lu.get("confidence"),
            "formation": lu.get("formation"),
            "updated_at": lu.get("updated_at"),
        }
    else:
        pkg["missing"].append("BSD伤停/阵型 未提取")
        pkg["injuries"] = None
        pkg["lineups"] = None

    # 5) 攻防历史: 本地覆盖检查 -> 缺失才 BSD 补拉
    atk = check_local_attack(pkg["league"], pkg["home"], pkg["away"])
    pkg["attack"] = {}
    for side in ("home", "away"):
        r = atk[side]
        if r["have"]:
            pkg["attack"][side] = {"have": True, "src": r["src"], "stats": r["stats"]}
        else:
            pulled = pull_attack_bsd(pkg[side + "_id"], pkg[side])
            if pulled:
                pkg["attack"][side] = {"have": True, "src": "bsd_pulled", "stats": pulled}
            else:
                pkg["attack"][side] = {"have": False, "src": None, "stats": None}
                pkg["missing"].append("%s攻防历史 未提取" % side)

    os.makedirs(PKG_DIR, exist_ok=True)
    with io.open(fp, "w", encoding="utf-8") as f:
        json.dump(pkg, f, ensure_ascii=False, indent=1)
    return "ok->%d.json" % eid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int)
    ap.add_argument("--league")
    ap.add_argument("--leagues", help="白名单联赛, 逗号分隔(与最新scan24h/48h匹配)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.id is not None:
        matches = [{"id": args.id}]
        # 单场模式补全赛程字段: 用 BSD event detail
        ev = bsd_get("/events/%d/" % args.id)
        if ev:
            matches[0].update({
                "league": ev.get("league_name"),
                "kickoff_iso": ev.get("event_date"),
                "home": (ev.get("home_team") or {}).get("name") if isinstance(ev.get("home_team"), dict) else ev.get("home_team"),
                "away": (ev.get("away_team") or {}).get("name") if isinstance(ev.get("away_team"), dict) else ev.get("away_team"),
                "home_id": (ev.get("home_team") or {}).get("id") if isinstance(ev.get("home_team"), dict) else ev.get("home_team_id"),
                "away_id": (ev.get("away_team") or {}).get("id") if isinstance(ev.get("away_team"), dict) else ev.get("away_team_id"),
            })
            ko = ev.get("event_date") or ""
            if ko:
                try:
                    dt = datetime.fromisoformat(ko.replace("Z", "+00:00")).astimezone(BJT)
                    matches[0]["kickoff"] = dt.strftime("%m-%d %H:%M")
                except Exception:
                    pass
        else:
            log("单场 %d event detail 拉取失败, 无法补全赛程" % args.id)
            return
    else:
        matches = latest_scan() or []
        if args.league:
            matches = [m for m in matches if m.get("league") == args.league]
        if args.leagues:
            _wl = {x.strip() for x in args.leagues.split(",") if x.strip()}
            matches = [m for m in matches if m.get("league") in _wl]
        matches = [m for m in matches if m.get("id")]

    if not matches:
        log("无可拉取目标")
        return

    log("目标 %d 场" % len(matches))
    ok, skip, fail = 0, 0, 0
    for m in matches:
        try:
            res = build_package(m, force=args.force)
            if res == "skip_existing":
                skip += 1
            elif res.startswith("ok"):
                ok += 1
                log("  %s %s | %s vs %s | %s" % (m.get("kickoff", "?"), m.get("league", "?"), m.get("home", "?"), m.get("away", "?"), res))
            else:
                fail += 1
                log("  FAIL %s %s vs %s" % (m.get("league", "?"), m.get("home", "?"), m.get("away", "?")))
        except Exception as e:
            fail += 1
            log("  ERR %s %s vs %s: %s" % (m.get("league", "?"), m.get("home", "?"), m.get("away", "?"), type(e).__name__))
        time.sleep(0.4)
    log("完成: 新拉 %d | 已有跳过 %d | 失败 %d | 输出目录 %s" % (ok, skip, fail, PKG_DIR))


if __name__ == "__main__":
    main()
