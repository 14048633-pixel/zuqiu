
# -*- coding: utf-8 -*-
"""BSD v2 补充数据: 当场伤停(lineups优先) + 逐队伤停(squad兜底) + 共识/多机构赔率 + BSD预测
============================================================
用法:
  # 1) 拉取 + 合并(所有 analysis_records/matches_info_*.json)
  python prediction_v2/bsd_extra.py --date 2026-08-16
  # 2) 只合并已有缓存(不消耗接口)
  python prediction_v2/bsd_extra.py --date 2026-08-16 --no-fetch
  # 3) 指定单个 matches_info 文件
  python prediction_v2/bsd_extra.py --date 2026-08-16 --info analysis_records/matches_info_20260816.json

数据(免费档, 2026-08-16 实测):
  GET /api/v2/events/{id}/lineups/           当场阵容(confirmed/predicted) + unavailable_players 缺阵名单, 永远200
  GET /api/v2/teams/{id}/squad/              俱乐部注册名单伤停(lineups不可用时的兜底)
  GET /api/v2/events/{id}/odds/              共识赔率(多机构平均)
  GET /api/v2/events/{id}/odds/comparison/   多机构 best 价 + bookmaker 数(免费替代 odds/best 付费档)
  GET /api/v2/events/{id}/prediction/        BSD dc-blend-v1 预测(λ交叉验证)

注意:
  * BASE_V2 = https://sports.bzzoiro.com/api/v2 —— 不要复用 injuries_bzzoiro 的 /api(v1) 前缀
  * /api/v2/odds/?event_id=.. 逐行 feed 实测 count=0, 不可用; 用 events/{id}/odds/ 替代
  * lineups 永远 200: 空时 lineup_status=unavailable, lineups/unavailable_players=null
"""
import argparse, glob, io, json, os, re, sys, time, unicodedata
import requests

from injuries_bzzoiro import (ROOT, TOKEN, HEADERS, fetch_events, _team_key)
from injuries_apifootball import (intel_text, summarize)

BASE_V2 = "https://sports.bzzoiro.com"   # 路径保持 /api/v2/... 前缀, 与文档一致
CACHE = os.path.join(ROOT, "analysis_records")


def _get(path, tries=2, timeout=20):
    """GET 一个 BSD v2 端点(带重试), 失败返回 None. 4xx 不重试."""
    for i in range(1, tries + 1):
        try:
            r = requests.get(BASE_V2 + path, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            print("  HTTP %s: %s" % (r.status_code, (r.text or "")[:160]))
            if r.status_code < 500:
                return None
        except Exception as e:
            print("  第%d/%d次失败: %s" % (i, tries, type(e).__name__))
        if i < tries:
            time.sleep(3)
    return None


def event_settle_scores(j):
    """BSD event -> 90-minute settle score check.
    BSD puts the after-extra-time score into home_score/away_score with period=AET/PEN,
    and does not expose the 90-minute score -> needs_verify=True (fill from authoritative source).
    Outlier: Larne was mislabelled period=FT/minute=90 while score was actually AET 0:3,
    so minute>=100 also triggers the AET flag as a fallback.
    Returns: {period, is_aet, hg_aet, ag_aet, hg_90, ag_90, needs_verify}
    """
    period = str(j.get("period") or "FT")
    minute = j.get("current_minute") or 0
    try:
        minute = int(minute)
    except (TypeError, ValueError):
        minute = 0
    is_aet = period in ("AET", "PEN") or minute >= 100
    hg, ag = j.get("home_score"), j.get("away_score")
    if not is_aet:
        return {"period": period, "is_aet": False,
                "hg_aet": None, "ag_aet": None,
                "hg_90": hg, "ag_90": ag, "needs_verify": False}
    return {"period": period, "is_aet": True,
            "hg_aet": hg, "ag_aet": ag,
            "hg_90": None, "ag_90": None, "needs_verify": True}


def fetch_squad(team_id):
    """-> players 列表; 失败返回 None."""
    j = _get("/api/v2/teams/%d/squad/" % team_id)
    if j is None:
        return None
    return j.get("players") or []


def _coach_rec(ev, side):
    """event 的 home_coach/away_coach -> {id,name,short_name,profile}; 缺返回 None."""
    try:
        c = ev.get(side + "_coach") or {}
        if not c.get("id"):
            return None
        return {"id": c["id"],
                "name": c.get("name") or "",
                "short_name": c.get("short_name") or "",
                "profile": c.get("profile") or ""}
    except Exception:
        return None


def _coach_formation(ev, side):
    """event 的 home_coach/away_coach -> preferred_formation(如 4-2-3-1); 缺返回 None."""
    try:
        c = ev.get(side + "_coach") or {}
        return (c.get("preferred_formation") or "").strip() or None
    except Exception:
        return None


def fetch_lineups(event_id):
    """当场阵容 -> {lineup_status, confidence{home,away}, formation{home,away},
                     unavailable_players{home,away}}; 失败 None.
    formation 来自 BSD lineups.home/away.formation(如 4-2-3-1), 未公布时为 None."""
    j = _get("/api/v2/events/%d/lineups/" % event_id)
    if j is None:
        return None
    lu = j.get("lineups") or {}
    conf = {}
    formation = {}
    for side in ("home", "away"):
        s = lu.get(side) or {}
        if not isinstance(s, dict):
            continue
        conf[side] = s.get("confidence")
        formation[side] = s.get("formation")
    return {"lineup_status": j.get("lineup_status"),
            "confidence": conf,
            "formation": formation,
            "unavailable_players": j.get("unavailable_players") or {"home": [], "away": []},
            "updated_at": j.get("updated_at")}

def fetch_odds(event_id):
    """共识赔率 + 多机构 best 价(comparison 免费). 全空返回 None."""
    out = {"consensus": {}, "best": {}, "bookmakers_count": 0, "total_odds": 0}
    j = _get("/api/v2/events/%d/odds/" % event_id)
    if j is not None:
        out["consensus"] = j.get("odds") or {}
        out["bookmakers_count"] = j.get("bookmakers_count") or 0
        out["total_odds"] = j.get("total_odds") or 0
    c = _get("/api/v2/events/%d/odds/comparison/" % event_id)
    if c is not None:
        out["bookmakers_count"] = c.get("bookmakers_count") or out["bookmakers_count"]
        out["total_odds"] = c.get("total_odds") or out["total_odds"]
        for mkt, outs in (c.get("markets") or {}).items():
            for oc, rec in (outs or {}).items():
                if not isinstance(rec, dict):
                    continue
                out["best"].setdefault(mkt, {})[str(oc).lower()] = {
                    "odds": rec.get("best_odds"),
                    "bookmaker": rec.get("best_bookmaker_slug"),
                    "n": len(rec.get("bookmakers") or {})}
    if out["consensus"] or out["best"]:
        return out
    return None


def fetch_prediction(event_id):
    """BSD 预测 -> 精简结构; 失败返回 None."""
    j = _get("/api/v2/events/%d/prediction/" % event_id)
    if j is None:
        return None
    m = j.get("markets") or {}
    return {"model": (j.get("model") or {}).get("version"),
            "confidence": (j.get("model") or {}).get("confidence"),
            "created_at": j.get("created_at"),
            "markets": m,
            "expected_goals": m.get("expected_goals") or {},
            "recommendations": j.get("recommendations")}


# ===== 联赛/赛季/积分榜 (docs/football/leagues) =====
_LEAGUES_LIST = None


def leagues_list():
    """全量联赛 -> [(name, id)]; 失败返回 []."""
    global _LEAGUES_LIST
    if _LEAGUES_LIST is None:
        j = _get("/api/v2/leagues/?limit=200")
        _LEAGUES_LIST = [((x.get("name") or "").strip(), x.get("id")) for x in (j or {}).get("results") or []]
    return _LEAGUES_LIST


def current_season(league_id):
    """当前赛季 -> {id, name, year, start_date, end_date} 或 None."""
    j = _get("/api/v2/leagues/%d/season/" % league_id)
    if j and j.get("season"):
        return j["season"]
    return None


def fetch_standings(league_id, season_id):
    """积分榜 -> 行列表(position/team_name/played/won/drawn/lost/gf/ga/gd/pts/xgf/xga/xgd/form); 杯赛groups合并; 失败返回 []."""
    j = _get("/api/v2/leagues/%d/standings/?season_id=%d" % (league_id, season_id))
    if not j:
        return []
    st = j.get("standings")
    if isinstance(st, list):
        return st
    if isinstance(st, dict):
        out = []
        for v in st.values():
            if isinstance(v, list):
                out += v
        return out
    return []


def lineup_recs(raw, pos_map=None):
    """lineups.unavailable_players 元素 -> 统一精简记录(复用 summarize 上限).
    pos_map: {player_id: position} 用于补伤停球员位置(G/D/M/F), 缺省不补."""
    recs = []
    for p in raw or []:
        _pos = None
        _pid = p.get("id") or p.get("player_id")
        if pos_map and _pid is not None:
            _pos = pos_map.get(str(_pid)) or pos_map.get(_pid)
        recs.append({"name": p.get("name") or p.get("short_name") or "?",
                     "status": p.get("status") or "injured",
                     "reason": p.get("reason") or "",
                     "expected_return": p.get("expected_return"),
                     "position": _pos})
    return summarize(recs)

def _backfill_pos(recs, name_pos):
    """backfill position for already-merged injury recs"""
    for r in recs or []:
        if r.get("position") or not (r.get("name") or ""):
            continue
        _p = name_pos.get(r.get("name"))
        if _p:
            r["position"] = _p


def squad_recs(players):
    """players -> 非available 球员摘要."""
    recs = []
    for p in players or []:
        avail = (p.get("availability") or "available").lower()
        if avail in ("injured", "doubtful", "suspended", "questionable"):
            recs.append({"name": p.get("name") or "?",
                         "status": avail,
                         "reason": p.get("injury_type") or "",
                         "expected_return": p.get("injury_expected_return"),
                         "position": p.get("position")})
    return summarize(recs)


def _load_events(date, no_fetch):
    raw_path = os.path.join(CACHE, "bzzoiro_events_%s.json" % date)
    if no_fetch or os.path.exists(raw_path):
        if not os.path.exists(raw_path):
            print("无已有 events 文件: %s" % raw_path)
            return None
        events = json.load(io.open(raw_path, encoding="utf-8")).get("events") or []
        print("使用已有事件 %s (%d 场)" % (raw_path, len(events)))
        return events
    events = fetch_events(date)
    if events is None:
        print("拉取事件失败")
        return None
    with io.open(raw_path, "w", encoding="utf-8") as f:
        json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "date": date, "n_events": len(events), "events": events},
                  f, ensure_ascii=False, indent=1)
    print("已存 %s (%d 场)" % (raw_path, len(events)))
    return events


def _load_alias():
    p = os.path.join(ROOT, "strategy_data", "teams_alias.json")
    try:
        return json.load(io.open(p, encoding="utf-8")).get("alias", {})
    except Exception:
        return {}


_ALIAS = _load_alias()


def _cand_names(*vals):
    """候选名: 原始名 + 别名库标准名(去重)."""
    out = []
    for v in vals:
        if not v:
            continue
        s = str(v)
        if s not in out:
            out.append(s)
        c = _ALIAS.get(s)
        if c and c not in out:
            out.append(c)
    return out


def _norm(t):
    """全名规范化(去重音符/小写/非字母数字->空格), 供模糊比对用."""
    t = unicodedata.normalize("NFKD", str(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.split(r"[^a-z0-9]+", t.lower())).strip()


def _sim(a, b):
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _fuzzy_name(a, b):
    """队名模糊分: 完全相同=1; token集合包含=0.9; 否则 SequenceMatcher(0~1)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    wa, wb = set(na.split()), set(nb.split())
    if wa and wb and (wa <= wb or wb <= wa):
        return 0.9
    return _sim(a, b)


def _same_day(match, ev):
    """match.time 是 BJT(MM-DD HH:MM), ev.event_date 是 UTC ISO; 误差≤1天."""
    try:
        mt = match.get("time") or ""
        bj = mt[:5].split("-")
        if len(bj) != 2:
            return True
        import datetime as _dt
        from datetime import timezone, timedelta as _td
        mday = _dt.date(2026, int(bj[0]), int(bj[1]))
        eday = _dt.datetime.fromisoformat((ev.get("event_date") or "").replace("Z", "+00:00")).date()
        return abs((mday - eday).days) <= 1
    except Exception:
        return True


def _match_event(match, events):
    """在 events 里找同一场: 精确key(含别名) -> 全名模糊(双队相似度≥0.7取最优), 带日期护栏."""
    h_names = _cand_names(match.get("home"), match.get("home_espn"))
    a_names = _cand_names(match.get("away"), match.get("away_espn"))
    hks = set(_team_key(x) for x in h_names)
    aks = set(_team_key(x) for x in a_names)
    if not hks or not aks:
        return None
    best = None
    for ev in events:
        if not _same_day(match, ev):
            continue
        ev_h = _cand_names(ev.get("home_team") or "")
        ev_a = _cand_names(ev.get("away_team") or "")
        if (any(_team_key(x) in hks for x in ev_h) and any(_team_key(x) in aks for x in ev_a)):
            return ev
        hsim = max([_fuzzy_name(mn, en) for mn in h_names for en in ev_h] or [0.0])
        asim = max([_fuzzy_name(mn, en) for mn in a_names for en in ev_a] or [0.0])
        if hsim >= 0.7 and asim >= 0.7:
            score = hsim + asim
            if best is None or score > best[0]:
                best = (score, ev)
    return best[1] if best else None


def _side_team_id(ev, side):
    obj = ev.get("home_team_obj") if side == "home" else ev.get("away_team_obj")
    return (obj or {}).get("id")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--no-fetch", action="store_true", help="只合并已有缓存(不消耗接口)")
    ap.add_argument("--info", help="指定 matches_info json(默认全部 matches_info_*.json)")
    ap.add_argument("--skip-odds", action="store_true", help="跳过赔率拉取")
    ap.add_argument("--skip-prediction", action="store_true", help="跳过 BSD 预测拉取")
    args = ap.parse_args()

    events = _load_events(args.date, args.no_fetch)
    if events is None:
        return

    if args.info:
        targets = [args.info if os.path.isabs(args.info) else os.path.join(ROOT, args.info)]
    else:
        targets = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "matches_info_*.json")))
    if not targets:
        print("无 matches_info 文件")
        return

    sq_path = os.path.join(CACHE, "bsd_squads_%s.json" % args.date)
    ln_path = os.path.join(CACHE, "bsd_lineups_%s.json" % args.date)
    od_path = os.path.join(CACHE, "bsd_odds_%s.json" % args.date)
    pr_path = os.path.join(CACHE, "bsd_predictions_%s.json" % args.date)
    squads = json.load(io.open(sq_path, encoding="utf-8")) if os.path.exists(sq_path) else {}
    lineups = json.load(io.open(ln_path, encoding="utf-8")) if os.path.exists(ln_path) else {}
    odds_cache = json.load(io.open(od_path, encoding="utf-8")) if os.path.exists(od_path) else {}
    pred_cache = json.load(io.open(pr_path, encoding="utf-8")) if os.path.exists(pr_path) else {}

    # 匹配: 用 (league,time,home,away) 稳定键
    matched = {}   # key -> event
    need_sq = set()
    for p in targets:
        if not os.path.exists(p):
            continue
        for m in json.load(io.open(p, encoding="utf-8")).get("matches") or []:
            ev = _match_event(m, events)
            if ev is None:
                continue
            key = (m.get("league"), m.get("time"), m.get("home"), m.get("away"))
            matched[key] = ev
            htid = _side_team_id(ev, "home")
            atid = _side_team_id(ev, "away")
            if htid:
                need_sq.add(htid)
            if atid:
                need_sq.add(atid)
    print("匹配到 BSD 场次: %d | 需拉 squad 队数: %d" % (len(matched), len(need_sq)), flush=True)

    # 逐队 squad (只拉缺失; lineups 无当场数据时的兜底)
    for tid in sorted(need_sq):
        if str(tid) in squads:
            continue
        players = fetch_squad(tid)
        if players is None:
            print("  squad 拉取失败 team=%s, 标注空" % tid, flush=True)
            squads[str(tid)] = {"players": []}
        else:
            squads[str(tid)] = {"players": players}
            print("  squad team=%s: %d人, 伤停%d" % (tid, len(players), len(squad_recs(players))), flush=True)
        if not args.no_fetch:
            with io.open(sq_path, "w", encoding="utf-8") as f:
                json.dump(squads, f, ensure_ascii=False, indent=1)
        time.sleep(0.15)

    # 逐场 lineups / odds / prediction (只拉缺失)
    for key, ev in matched.items():
        eid = str(ev.get("id"))
        if eid not in lineups and not args.no_fetch:
            lu = fetch_lineups(ev.get("id"))
            lineups[eid] = lu if lu is not None else {}
            st = lineups[eid].get("lineup_status") if lineups[eid] else "?x"
            n_up = len((lineups[eid].get("unavailable_players") or {}).get("home") or []) + \
                   len((lineups[eid].get("unavailable_players") or {}).get("away") or [])
            print("  lineups event=%s: %s 缺阵%d" % (eid, st or "空", n_up), flush=True)
            with io.open(ln_path, "w", encoding="utf-8") as f:
                json.dump(lineups, f, ensure_ascii=False, indent=1)
            time.sleep(0.15)
        if not args.skip_odds and eid not in odds_cache and not args.no_fetch:
            od = fetch_odds(ev.get("id"))
            odds_cache[eid] = od if od is not None else {}
            print("  odds event=%s: %s" % (eid, ("%d家" % odds_cache[eid].get("bookmakers_count", 0)) if odds_cache[eid] else "空"), flush=True)
            with io.open(od_path, "w", encoding="utf-8") as f:
                json.dump(odds_cache, f, ensure_ascii=False, indent=1)
            time.sleep(0.15)
        if not args.skip_prediction and eid not in pred_cache and not args.no_fetch:
            pr = fetch_prediction(ev.get("id"))
            pred_cache[eid] = pr if pr is not None else {}
            print("  pred event=%s: %s" % (eid, ("ok" if pred_cache[eid] else "空")), flush=True)
            with io.open(pr_path, "w", encoding="utf-8") as f:
                json.dump(pred_cache, f, ensure_ascii=False, indent=1)
            time.sleep(0.15)

    # 合并进 matches_info
    for p in targets:
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        n_sq = n_odds = n_pred = 0
        for m in d.get("matches") or []:
            key = (m.get("league"), m.get("time"), m.get("home"), m.get("away"))
            ev = matched.get(key)
            if ev is None:
                continue
            eid = str(ev.get("id"))
            inj = m.setdefault("injuries", {})
            inj.setdefault("sources", {})
            lu = lineups.get(eid) or {}
            if lu:
                m["bsd_lineups"] = {"status": lu.get("lineup_status"),
                                    "home_conf": (lu.get("confidence") or {}).get("home"),
                                    "away_conf": (lu.get("confidence") or {}).get("away"),
                                    "formation": lu.get("formation") or {},
                                    "coach": {"home": _coach_formation(ev, "home"),
                                              "away": _coach_formation(ev, "away")}}
                _coaches = {}
                for _s in ("home", "away"):
                    _cr = _coach_rec(ev, _s)
                    if _cr:
                        _coaches[_s] = _cr
                if _coaches:
                    m["bsd_coaches"] = _coaches
            _pos_map = {}
            _name_pos = {}
            for _tid in (_side_team_id(ev, "home"), _side_team_id(ev, "away")):
                for _pl in (squads.get(str(_tid), {}).get("players") or []):
                    if _pl.get("id") is not None:
                        _pos_map[str(_pl["id"])] = _pl.get("position")
                    _nm = _pl.get("name") or _pl.get("short_name")
                    if _nm and not _name_pos.get(_nm):
                        _name_pos[_nm] = _pl.get("position")
            for side in ("home", "away"):
                if _side_team_id(ev, side) is None:
                    continue
                if inj.get(side + "_covered"):
                    _backfill_pos(inj.get(side) or [], _name_pos)
                    continue
                recs, covered, src = None, False, None
                st = lu.get("lineup_status")
                up = lu.get("unavailable_players")
                if st in ("confirmed", "predicted") and up is not None:
                    recs = lineup_recs(up.get(side) or [], pos_map=_pos_map)
                    # confirmed=官方名单(0缺阵也算确认); predicted+0缺阵=区域覆盖不足, 不标"0人"误导
                    if recs or st == "confirmed":
                        covered, src = True, "bsd_lineups"
                else:
                    tid = _side_team_id(ev, side)
                    recs = squad_recs((squads.get(str(tid), {}).get("players") or []))
                    if recs:
                        covered, src = True, "bsd_squad"
                if covered:
                    inj[side] = recs
                    inj[side + "_covered"] = True
                    inj["sources"][side] = src
                    n_sq += 1
            m["intel"] = intel_text(inj.get("home_covered"), inj.get("home", []),
                                    inj.get("away_covered"), inj.get("away", []))
            if not args.skip_odds and eid in odds_cache and odds_cache[eid]:
                m["bsd_odds"] = odds_cache[eid]
                n_odds += 1
            if not args.skip_prediction and eid in pred_cache and pred_cache[eid]:
                m["bsd_prediction"] = pred_cache[eid]
                n_pred += 1
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        md = os.path.splitext(p)[0] + ".md"
        try:
            from _batch_match_info import render_md
            with io.open(md, "w", encoding="utf-8") as f:
                f.write("\n".join(render_md(d.get("matches") or [])))
        except Exception as e:
            print("  (md更新失败: %s)" % type(e).__name__)
        print("合并 %s: 伤停补%d 赔率%d 预测%d" % (p, n_sq, n_odds, n_pred))


if __name__ == "__main__":
    main()