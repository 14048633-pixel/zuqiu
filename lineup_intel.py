# -*- coding: utf-8 -*-
"""首发名单核验 + 伤停λ修正 (BSD lineups, 免费)。

链路: find_event_id(队名+日期) -> fetch_lineups(首发XI+缺阵) 
      -> injury_coefs(位置加权λ修正, 镜像 D:\足球分析 scan_upcoming._injury_coef)
      -> verify_xi(缺阵名单 vs 首发核验: confirmed_out/cleared)

用法:
    python -m lineup_intel "Crystal Palace" "Man City" E0 2026-08-29
"""
import datetime as dt
import os
import sys

# 保证以 -m football_analyzer.lineup_intel 运行时能 import 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API = "https://sports.bzzoiro.com/api"
V2 = "https://sports.bzzoiro.com/api/v2"

# 攻击端位置(伤停影响λ更大)
_ATK_POS = ("F", "M", "FW", "MF", "AM", "ST", "W", "SS", "LW", "RW", "CF")


def _headers():
    key = os.environ.get("BZZOIRO_API_KEY", "")
    if not key:
        return None
    return {"Authorization": "Token " + key, "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"}


def _resolver():
    from odds_source import normalize_team, team_matcher
    tm = None
    try:
        tm = team_matcher()
    except Exception:
        tm = None

    def _res(raw):
        if tm is not None:
            try:
                r = tm.resolve(raw)
                if r:
                    return r
            except Exception:
                pass
        return normalize_team(raw or "")

    return _res


def find_event_id(home, away, date, timeout=15):
    """本地规范队名+日期 -> BSD event_id; 失败返回 None。"""
    headers = _headers()
    if not headers:
        return None
    try:
        import pandas as pd
        target = pd.Timestamp(date)
        tz = dt.timezone(dt.timedelta(hours=8))
        day_start = dt.datetime(target.year, target.month, target.day, 0, 0, tzinfo=tz)
        day_end = day_start + dt.timedelta(days=1) - dt.timedelta(seconds=1)
        d_from = day_start.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        d_to = day_end.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None
    _res = _resolver()
    try:
        off = 0
        while True:
            r = requests.get(API + "/events/", params={
                "date_from": d_from, "date_to": d_to, "limit": 50, "offset": off,
                "full": "true"}, headers=headers, timeout=timeout)
            if r.status_code != 200:
                return None
            res = r.json().get("results") or []
            for e in res:
                h = e.get("home_team") or ""
                a = e.get("away_team") or ""
                if _res(h) == home and _res(a) == away:
                    return e.get("id")
            if len(res) < 50:
                break
            off += 50
    except Exception:
        return None
    return None


def _squad_positions(team_id, timeout=15):
    """BSD 球队注册名单 -> {player_id: position}; 失败返回 {}。"""
    headers = _headers()
    if not headers or not team_id:
        return {}
    try:
        r = requests.get(V2 + "/teams/%d/squad/" % int(team_id),
                         headers=headers, timeout=timeout)
        if r.status_code != 200:
            return {}
        return {str(p.get("id")): p.get("position")
                for p in (r.json().get("players") or [])}
    except Exception:
        return {}


def fetch_squad_names(team_id, timeout=15):
    """BSD 球队注册名单 -> 球员英文名列表(去空去重, 小写)。失败返回 []。"""
    headers = _headers()
    if not headers or not team_id:
        return []
    try:
        r = requests.get(V2 + "/teams/%d/squad/" % int(team_id),
                         headers=headers, timeout=timeout)
        if r.status_code != 200:
            return []
        names = []
        for p in (r.json().get("players") or []):
            nm = str(p.get("name") or "").strip()
            if nm:
                names.append(nm.lower())
        return sorted(set(names))
    except Exception:
        return []


def roster_validate(signals, home_team_id=None, away_team_id=None, timeout=15):
    """roster 级串台校验: 每条带 player 的信号球员必须属于该侧球队注册名单。

    背景: 百炼联网情报曾把 West Brom 的 Bielik 错挂到 Cardiff(跨场串台),
    BSD缺阵名单无法识别(该队无此人即漏过)。用 BSD squad 名单做成员归属校验:
      verdict: in_roster / not_in_roster(串台或过期转会) / no_squad(名单拉取失败, 不判)
    返回 {rows: [...], squads: {"home": n, "away": n}}。
    """
    rosters = {
        "home": fetch_squad_names(home_team_id, timeout) if home_team_id else [],
        "away": fetch_squad_names(away_team_id, timeout) if away_team_id else [],
    }
    rows = []
    for sig in (signals or []):
        player = str(sig.get("player") or "").strip()
        side = str(sig.get("side") or "")
        if not player or side not in ("home", "away"):
            continue
        plow = player.lower()
        pool = rosters.get(side) or []
        if not pool:
            verdict, note = "no_squad", "该侧 squad 名单为空(拉取失败/无名单), 不判"
        else:
            hit = next((x for x in pool if plow in x or x in plow), None)
            if hit:
                verdict, note = "in_roster", "球员 %s 在 %s 注册名单内" % (player, side)
            else:
                verdict, note = ("not_in_roster",
                                 "球员 %s 不在 %s 注册名单 -> 疑似串台/信息污染, 丢弃"
                                 % (player, side))
        rows.append({"side": side, "player": player, "verdict": verdict, "note": note})
    return {"rows": rows,
            "squads": {"home": len(rosters["home"]), "away": len(rosters["away"])}}


def fetch_lineups(event_id, timeout=15):
    """BSD v2 lineups -> {lineup_status, updated_at, formation{home,away},
    xi{home,away}, unavailable{home,away}}; 失败返回 None。

    unavailable 缺 position 时用球队 squad 注册名单补位置(位置加权λ修正依赖)。"""
    headers = _headers()
    if not headers:
        return None
    try:
        r = requests.get(V2 + "/events/%d/lineups/" % int(event_id),
                         headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        d = r.json()
    except Exception:
        return None
    out = {"lineup_status": d.get("lineup_status"), "updated_at": d.get("updated_at"),
           "formation": {}, "xi": {}, "captains": {}, "unavailable": {}, "_team_ids": {}}
    lus = d.get("lineups") or {}
    team_ids = {}
    for side in ("home", "away"):
        lu = lus.get(side) or {}
        team_ids[side] = lu.get("team_id")
        out["formation"][side] = lu.get("formation")
        pls = lu.get("players") or []
        out["xi"][side] = [p.get("name") for p in pls]
        out["captains"][side] = [p.get("name") for p in pls if p.get("captain")]
    up = d.get("unavailable_players") or {}
    for side in ("home", "away"):
        recs = up.get(side) or []
        pos_map = _squad_positions(team_ids.get(side)) if team_ids.get(side) else {}
        for rec in recs:
            if not rec.get("position") and rec.get("id") is not None:
                rec["position"] = (pos_map.get(str(rec.get("id")))
                                   or pos_map.get(rec.get("id")))
        out["unavailable"][side] = recs
    out["_team_ids"] = team_ids
    try:
        _record_lineup_history(int(event_id), team_ids, out["xi"], out["captains"])
    except Exception:
        pass
    return out


# P1(2026-09-05): 旧 _injury_coef 已删除, 由 _injury_delta_recs(位置×主力×攻防双向) 取代




# ---- P1 (2026-09-05): 伤停量化升级 位置×主力权重×攻防双向 ----
_LH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "strategy_data", "lineup_history.json")


def _load_lineup_history():
    import json as _json
    try:
        with open(_LH_FILE, encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return {}


def _save_lineup_history(h):
    import json as _json
    try:
        os.makedirs(os.path.dirname(_LH_FILE), exist_ok=True)
        with open(_LH_FILE, "w", encoding="utf-8") as f:
            _json.dump(h, f, ensure_ascii=False)
    except Exception:
        pass


def _record_lineup_history(event_id, team_ids, xi, captains):
    """本场首发XI -> lineup_history(主力判定数据源, 按event_id幂等, 保留最近200场)。"""
    h = _load_lineup_history()
    evs = h.setdefault("events", {})
    key = str(event_id)
    if key in evs:
        return
    rec = {"date": dt.date.today().isoformat()}
    for side in ("home", "away"):
        tid = team_ids.get(side)
        if tid:
            rec[str(tid)] = {"xi": xi.get(side) or [], "captains": captains.get(side) or []}
    evs[key] = rec
    if len(evs) > 200:
        for k in sorted(evs, key=lambda k_: evs[k_].get("date", ""))[:len(evs) - 200]:
            evs.pop(k, None)
    _save_lineup_history(h)


def _starter_rate(team_id, name):
    """近8场首发率(主力判定); 无历史返回 None。"""
    if not team_id or not name:
        return None
    h = _load_lineup_history()
    evs = h.get("events") or {}
    games = [e.get(str(team_id)) for e in evs.values()
             if str(team_id) in e and e[str(team_id)].get("xi")]
    recent = games[-8:]
    if len(recent) < 3:  # P5(2026-09-05): 冷启动<3场 -> 不判主力(走0.5保守), 避免单场误判100%
        return None
    n = 0
    nm = name.lower()
    for g in recent:
        if any(nm in x.lower() or x.lower() in nm for x in (g.get("xi") or [])):
            n += 1
    return n / len(recent)


_POS_IMPACT = {
    "G": (0.02, 0.04),  # 门将: 攻-2% 守-4%
    "D": (0.00, 0.04),  # 后卫: 守-4%
    "M": (0.02, 0.02),  # 中场: 攻守各-2%
    "F": (0.04, 0.00),  # 前锋: 攻-4%
}
_POS_CN = {"G": "门将", "D": "后卫", "M": "中场", "F": "前锋"}


def _norm_pos(pos):
    p = str(pos or "").upper()
    if p in ("G", "GK"):
        return "G"
    if p in ("D", "DF", "CB", "LB", "RB", "WB", "FB"):
        return "D"
    if p in ("M", "MF", "DM", "CM", "AM", "W"):
        return "M"
    if p in ("F", "FW", "ST", "CF", "SS", "LW", "RW"):
        return "F"
    return None


def _injury_delta_recs(recs, team_id, captains):
    """缺阵名单 -> (atk_loss, def_loss, details)。
    P1 双向量化: 位置×主力权重; 缺后防核心 -> def_loss 上升 -> 对手λ上调。"""
    recs = [r for r in (recs or []) if str(r.get("status") or "injured").lower()
            not in ("available", "returning", "doubtful_returning")]
    atk = def_ = 0.0
    details = []
    caps = [str(c or "").lower() for c in (captains or [])]
    for r in recs:
        name = str(r.get("name") or "")
        pos = _norm_pos(r.get("position"))
        if caps and name.lower() in caps:
            w, tag = 1.0, "核心(队长)"
        else:
            rate = _starter_rate(team_id, name)
            if rate is None:
                w, tag = 0.5, "主力待定"
            elif rate >= 0.6:
                w, tag = 1.0, "主力(首发%.0f%%)" % (rate * 100)
            elif rate >= 0.4:
                w, tag = 0.7, "常规(%.0f%%)" % (rate * 100)
            else:
                w, tag = 0.35, "轮换(%.0f%%)" % (rate * 100)
        if pos is None:
            b_atk, b_def, pos_cn = 0.01, 0.01, "?"
        else:
            b_atk, b_def = _POS_IMPACT[pos]
            pos_cn = _POS_CN[pos]
        if tag.startswith("核心"):
            b_atk += 0.02
            b_def += 0.02
        atk += b_atk * w
        def_ += b_def * w
        details.append({"name": name, "pos": pos_cn, "weight": round(w, 2), "tag": tag,
                        "atk": round(b_atk * w, 3), "def": round(b_def * w, 3)})
    return min(0.25, atk), min(0.25, def_), details


def injury_delta(lineups):
    """-> {"home": {"atk","def","detail"}, "away": {...}}。
    atk: 本队进攻损失(λ乘 (1-atk)); def: 本队防守损失(对手λ乘 (1+def))。"""
    out = {}
    if not lineups:
        return {"home": {"atk": 0.0, "def": 0.0, "detail": []},
                "away": {"atk": 0.0, "def": 0.0, "detail": []}}
    tids = lineups.get("_team_ids") or {}
    caps = lineups.get("captains") or {}
    for side in ("home", "away"):
        atk, def_, det = _injury_delta_recs(
            lineups.get("unavailable", {}).get(side), tids.get(side), caps.get(side) or [])
        out[side] = {"atk": round(atk, 4), "def": round(def_, 4), "detail": det}
    return out

def injury_coefs(lineups):
    """-> (coef_h, coef_a): 双向等价单系数(P1)。
    coef_h = (1-home.atk)×(1+away.def): 主队λ净变化(本队进攻损失 × 客队防守弱化)。
    缺客队后防核心 -> coef_h>1 (主队λ上调); 缺主队前锋 -> coef_h<1。"""
    d = injury_delta(lineups)
    return ((1 - d["home"]["atk"]) * (1 + d["away"]["def"]),
            (1 - d["away"]["atk"]) * (1 + d["home"]["def"]))


def injury_coefs_merged(lineups, ark_records=None):
    """BSD + ARK 合并后的双向λ修正(ARK补的缺阵也计入, 如马特塔类核心)。"""
    if not lineups:
        return (1.0, 1.0)
    v = verify_merged(lineups, ark_records)
    d = {"home": {"atk": 0.0, "def": 0.0}, "away": {"atk": 0.0, "def": 0.0}}
    tids = lineups.get("_team_ids") or {}
    caps = lineups.get("captains") or {}
    for side in ("home", "away"):
        out_recs = [{"name": r.get("name"), "position": r.get("position"),
                     "status": "injured", "reason": r.get("reason")}
                    for r in v.get(side, []) if r.get("verdict") == "confirmed_out"]
        atk, def_, _det = _injury_delta_recs(out_recs, tids.get(side), caps.get(side) or [])
        d[side] = {"atk": atk, "def": def_}
    return ((1 - d["home"]["atk"]) * (1 + d["away"]["def"]),
            (1 - d["away"]["atk"]) * (1 + d["home"]["def"]))


def verify_xi(lineups):
    """核验: BSD 缺阵名单 vs 确认首发XI。
    返回 per-side: [{name, position, reason, verdict}] , verdict=confirmed_out/cleared。"""
    out = {}
    if not lineups:
        return out
    for side in ("home", "away"):
        xi = lineups.get("xi", {}).get(side) or []
        xi_low = {str(x).lower() for x in xi}
        rows = []
        for p in lineups.get("unavailable", {}).get(side) or []:
            name = p.get("name") or ""
            short = p.get("short_name") or ""
            in_xi = (name.lower() in xi_low) or (short and short.lower() in xi_low)
            rows.append({"name": name, "position": p.get("position"),
                         "reason": p.get("reason"),
                         "verdict": "cleared" if in_xi else "confirmed_out"})
        out[side] = rows
    return out


def verify_merged(lineups, ark_records=None):
    """合并 BSD 缺阵 + ARK 结构化情报, 与首发XI核验。

    返回 per-side: [{name, position, reason, source(BSD/ARK/BSD+ARK), verdict}]。
    ARK 补 BSD 漏报(如马特塔类): ARK-only 记录也会被核验, 标记 [ARK补]。
    """
    out = {}
    if not lineups:
        return out
    for side in ("home", "away"):
        xi_low = {str(x).lower() for x in lineups.get("xi", {}).get(side) or []}
        seen = {}
        for p in lineups.get("unavailable", {}).get(side) or []:
            name = p.get("name") or ""
            if not name:
                continue
            seen[name.lower()] = {"name": name, "position": p.get("position"),
                                  "reason": p.get("reason"), "source": "BSD"}
        for r in (ark_records or []):
            if str(r.get("side") or "").lower() != side:
                continue
            pname = r.get("player") or ""
            if not pname:
                continue
            key = pname.lower()
            rec = seen.get(key)
            if rec:
                rec["source"] = "BSD+ARK"
                if not rec.get("position"):
                    rec["position"] = r.get("position")
                rec["reason"] = rec.get("reason") or r.get("reason")
            else:
                seen[key] = {"name": pname, "position": r.get("position"),
                             "reason": r.get("reason"), "source": "ARK"}
        rows = []
        for rec in seen.values():
            rec["verdict"] = "cleared" if rec["name"].lower() in xi_low else "confirmed_out"
            rows.append(rec)
        out[side] = rows
    return out


def signal_return_conflicts(signals, unavailable_by_side=None):
    """百炼"复出信号" vs BSD 缺阵名单 双源冲突检测 (2026-09-02).

    signals: dashscope_search.extract_signal_json 的 signals (type=return_from_injury)
    unavailable_by_side: {"home": [姓名...], "away": [姓名...]} (BSD 缺阵名单)
    返回 [{side, player, signal_level, bsd_status, verdict, note}]
      verdict: conflict(百炼复出 vs BSD缺阵, 等官方首发) / aligned(已在首发或无冲突) /
               unknown_player(名单无此人, 警惕串台/信息污染)
    """
    out = []
    unavail = unavailable_by_side or {}
    for sig in (signals or []):
        if str(sig.get("type") or "") != "return_from_injury":
            continue
        side = str(sig.get("side") or "")
        player = str(sig.get("player") or "").strip()
        if side not in ("home", "away") or not player:
            continue
        plow = player.lower()
        pool = [str(x).lower() for x in (unavail.get(side) or [])]
        matched = next((p for p in pool if plow in p or p in plow), None)
        if matched:
            verdict = "conflict"
            note = ("百炼报%s复出, BSD缺阵名单含%s -> 双源冲突, 等官方首发"
                    % (player, matched))
        else:
            verdict = "unknown_player"
            note = "百炼报%s复出, 但BSD该侧名单无此人 -> 可能串台/信息过旧, 人工核对" % player
        out.append({"side": side, "player": player,
                    "signal_level": sig.get("level"),
                    "bsd_status": "out" if matched else "not_in_list",
                    "verdict": verdict, "note": note})
    return out


def render_lineup_block(lineups, injury_coef, ark_records=None):
    """-> markdown 文本块(供报告追加)。BSD+ARK 双源合并核验。"""
    lines = ["", "**首发核验 (BSD confirmed + ARK 补充)**", ""]
    if not lineups:
        lines.append("- 无 BSD 首发数据")
        return "\n".join(lines)
    v = verify_merged(lineups, ark_records)
    pos_cn = {"G": "门将", "D": "后卫", "M": "中场", "F": "前锋"}
    for side, cn in (("home", "主队"), ("away", "客队")):
        fm = lineups.get("formation", {}).get(side) or "?"
        lines.append("- %s 阵型 %s:" % (cn, fm))
        rows = v.get(side) or []
        if not rows:
            lines.append("  - 无缺阵名单")
        for r in rows:
            mark = "✅复出(进首发)" if r["verdict"] == "cleared" else "❌确认缺阵"
            src = r.get("source", "")
            if src == "ARK":
                mark += " [ARK补]"
            elif src == "BSD+ARK":
                mark += " [双源]"
            pos = pos_cn.get(str(r.get("position") or "").upper(), r.get("position") or "?")
            lines.append("  - %s (%s) %s %s" % (r["name"], pos, r.get("reason") or "", mark))
        lines.append("")
    lines.append("- λ修正: 主队×%.3f / 客队×%.3f (位置加权, 下限0.75)"
                  % (injury_coef[0], injury_coef[1]))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 4:
        print("用法: python -m lineup_intel 主队 客队 联赛key [日期]")
        raise SystemExit(1)
    home, away, league = sys.argv[1], sys.argv[2], sys.argv[3]
    date = sys.argv[4] if len(sys.argv) > 4 else None
    import pandas as pd
    date = pd.Timestamp(date) if date else pd.Timestamp.now().normalize()
    eid = find_event_id(home, away, date)
    print("event_id:", eid)
    if not eid:
        raise SystemExit(1)
    lu = fetch_lineups(eid)
    if not lu:
        print("lineups: 无数据")
        raise SystemExit(1)
    coef = injury_coefs(lu)
    print(render_lineup_block(lu, coef))
