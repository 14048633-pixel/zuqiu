# -*- coding: utf-8 -*-
"""未开赛比赛 完整信息批量拉取(ESPN赛果CSV本地计算, 零额外API消耗, 跨联赛搜索)
================================================
数据: data/raw/football_data/espn_*.csv (2026窗口, 已增量更新)
     + BSD官方积分榜(免费, 含xG/官方form, 覆盖18联赛, 6h文件缓存)
     跨联赛搜索: 升班马/降级队近期数据自动取原属联赛(如桑坦德->西乙, 伯恩利->英超)
输出: analysis_records/matches_info_YYYYMMDD.json + .md
内容: 本季积分榜排名/积分/进球失球(BSD优先) | 近5场(含主客场) | 交锋记录
缺口: 伤停/轮换/战意 未获取(本地无此数据源), 逐场标注
"""
import csv, io, json, os, sys, time, unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))

DATA_DIR = os.path.join(ROOT, "data", "raw", "football_data")
SCAN_JSON = os.path.join(ROOT, "analysis_records", "20260816_scan_upcoming.json")
TS = datetime.now(timezone.utc).strftime("%Y%m%d")
OUT_JSON = os.path.join(ROOT, "analysis_records", "matches_info_%s.json" % TS)
OUT_MD = os.path.join(ROOT, "analysis_records", "matches_info_%s.md" % TS)
BJT = timezone(timedelta(hours=8))

# 联赛 -> 本季赛季标签
SEASON = {
    "英乙": "2026/2027", "瑞超": "2026", "挪超": "2026", "巴甲": "2026", "阿甲": "2026",
    "美职": "2026", "土超": "2026", "墨超": "2026", "智利甲": "2026", "丹超": "2026",
    "意乙": "2026/2027", "法乙": "2026/2027", "荷甲": "2026/2027", "德乙": "2026/2027",
    "比甲": "2026/2027", "英冠": "2026/2027", "葡超": "2026/2027", "西乙": "2026/2027",
    "西甲": "2026/2027", "英超": "2026/2027", "土甲": "2026/2027",
}

def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("-", " ").replace(".", " ").replace("'", " ").replace("&", " ").replace("+", " ")
    return " ".join(s.split())

def load_aliases():
    p = os.path.join(ROOT, "strategy_data", "teams_alias.json")
    try:
        return json.load(io.open(p, encoding="utf-8")).get("alias", {})
    except Exception:
        return {}

ALIAS = load_aliases()

def canon(name):
    return ALIAS.get(name.strip(), name.strip())

def team_key(name):
    return norm(canon(name))

def fuzzy_eq(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    wa, wb = set(a.split()), set(b.split())
    if wa and wb and (wa <= wb or wb <= wa):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.82

# ===== BSD积分榜替换本地算表 (免费, 实测覆盖: J1/中超/西甲/荷甲/英冠/英乙/西乙/巴甲/瑞超/挪超/丹超/比甲/蓡超/土超/墨超/美职/法乙; 未覆盖: 德乙/智利甲/阿甲/未开季五大联赛) =====
BSD_LEAGUE_ID = {"英超": 1, "西甲": 3, "意甲": 4, "德甲": 5, "法甲": 6, "蓡超": 2,
                 "巴甲": 9, "荷甲": 10, "土超": 11, "英冠": 12, "比甲": 14,
                 "美职": 18, "墨超": 19, "瑞超": 26, "西乙": 38,
                 "J1": 49, "中超": 52, "挪超": 54, "丹超": 84, "阿甲": 85,
                 "英乙": 87, "英甲": 86, "法乙": 89}
_BSD_STD_PATH = os.path.join(ROOT, "analysis_records", "bsd_standings_cache.json")
_BSD_STD_TTL = 6 * 3600
_BSD_STANDINGS = {}


def _bsd_cache_load():
    try:
        d = json.load(io.open(_BSD_STD_PATH, encoding="utf-8"))
        if time.time() - d.get("ts", 0) < _BSD_STD_TTL:
            return d.get("data", {})
    except Exception:
        pass
    return {}


def _bsd_cache_save(data):
    try:
        with io.open(_BSD_STD_PATH, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)
    except Exception:
        pass


def bsd_standings(lg):
    """-> {team_key: row} 或 {}; 文件缓存6h; 未覆盖/失败返空(不网络)."""
    if lg in _BSD_STANDINGS:
        return _BSD_STANDINGS[lg]
    disk = _bsd_cache_load()
    if lg in disk:
        _BSD_STANDINGS[lg] = disk[lg]
        return disk[lg]
    out = {}
    lid = BSD_LEAGUE_ID.get(lg)
    if lid:
        try:
            from bsd_extra import current_season, fetch_standings
            s = current_season(lid)
            if s:
                for r in fetch_standings(lid, s["id"]):
                    tn = (r.get("team_name") or "").strip()
                    if tn:
                        out[team_key(tn)] = r
                if out:
                    disk[lg] = out
                    _bsd_cache_save(disk)
        except Exception:
            out = {}
    _BSD_STANDINGS[lg] = out
    return out


class GlobalData:
    """跨联赛数据层: 所有 ESPN 赛果合并搜索。"""
    def __init__(self):
        self.matches = []  # {league,date,home,away,hg,ag,season}
        self.by_key = {}   # team_key -> canonical espn name
        for fn in sorted(os.listdir(DATA_DIR)):
            if not fn.startswith("espn_") or not fn.endswith("_results.csv"):
                continue
            lg = fn[len("espn_"):-len("_results.csv")]
            fp = os.path.join(DATA_DIR, fn)
            with io.open(fp, encoding="utf-8") as f:
                rd = csv.DictReader(f)
                for r in rd:
                    try:
                        m = {"league": lg,
                             "date": datetime.strptime(r["Date"], "%Y/%m/%d"),
                             "home": r["HomeTeam"].strip(),
                             "away": r["AwayTeam"].strip(),
                             "hg": int(r["FTHG"]), "ag": int(r["FTAG"]),
                             "season": r.get("Season", "").strip()}
                    except Exception:
                        continue
                    self.matches.append(m)
        self.matches.sort(key=lambda x: x["date"])
        for m in self.matches:
            for t in (m["home"], m["away"]):
                self.by_key.setdefault(team_key(t), t)

    def find(self, name, prefer_lg=None):
        """返回 (espn队名, 来源联赛) 或 (None,None)。优先当前联赛, 否则跨联赛模糊。"""
        k = team_key(name)
        if k in self.by_key:
            t = self.by_key[k]
            lg = self._league_of(t)
            return t, lg
        cands = []
        for m in self.matches:
            for t in (m["home"], m["away"]):
                tk = team_key(t)
                if fuzzy_eq(k, tk):
                    cands.append((t, m["league"]))
        if not cands:
            return None, None
        if prefer_lg:
            for t, lg in cands:
                if lg == prefer_lg:
                    return t, lg
        t, lg = cands[0]
        return t, lg

    def _league_of(self, team):
        k = team_key(team)
        for m in self.matches:
            if team_key(m["home"]) == k or team_key(m["away"]) == k:
                return m["league"]
        return None

    def table(self, lg):
        """本季积分榜: {team_key: (rank, stats)}; BSD官方优先(含xG/官方form), 本地ESPN兑底."""
        bm = bsd_standings(lg)
        if bm:
            out = {}
            for t, r in bm.items():
                played = r.get("played") or 0
                xgf = r.get("xgf"); xga = r.get("xga")
                # BSD xG为赛季累计值, 统一归一为场均(避免中超xgd=18.8这类误读)
                if played > 0:
                    xgf = round(xgf / played, 2) if xgf is not None else None
                    xga = round(xga / played, 2) if xga is not None else None
                xgd = round(xgf - xga, 2) if (xgf is not None and xga is not None) else r.get("xgd")
                s = {"P": played, "W": r.get("won", 0), "D": r.get("drawn", 0), "L": r.get("lost", 0),
                     "GF": r.get("gf", 0), "GA": r.get("ga", 0), "Pts": r.get("pts", 0),
                     "xgf": xgf, "xga": xga, "xgd": xgd, "form_bsd": r.get("form")}
                out[t] = (r.get("position"), s)
            return out
        stats = {}
        for m in self.matches:
            if m["league"] != lg or m["season"] != SEASON.get(lg, ""):
                continue
            for t, gf, ga in ((m["home"], m["hg"], m["ag"]), (m["away"], m["ag"], m["hg"])):
                k = team_key(t)
                s = stats.setdefault(k, {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "Pts": 0})
                s["P"] += 1; s["GF"] += gf; s["GA"] += ga
                if gf > ga: s["W"] += 1; s["Pts"] += 3
                elif gf == ga: s["D"] += 1; s["Pts"] += 1
                else: s["L"] += 1
        rank = sorted(stats.items(), key=lambda kv: (-kv[1]["Pts"], -(kv[1]["GF"] - kv[1]["GA"]), -kv[1]["GF"]))
        return {t: (i + 1, s) for i, (t, s) in enumerate(rank)}

    def form(self, team, n=5, loc=None):
        k = team_key(team)
        rows = [m for m in self.matches if team_key(m["home"]) == k or team_key(m["away"]) == k]
        if loc == "home":
            rows = [m for m in rows if team_key(m["home"]) == k]
        elif loc == "away":
            rows = [m for m in rows if team_key(m["away"]) == k]
        out = []
        for m in rows[-n:]:
            g = m["hg"] if team_key(m["home"]) == k else m["ag"]
            gc = m["ag"] if team_key(m["home"]) == k else m["hg"]
            res = "W" if g > gc else ("D" if g == gc else "L")
            out.append("%s %s %d-%d(%s)" % (m["date"].strftime("%m-%d"), res, g, gc, m["season"]))
        return out

    def h2h(self, h, a, n=5):
        hk, ak = team_key(h), team_key(a)
        rows = [m for m in self.matches
                if (team_key(m["home"]) == hk and team_key(m["away"]) == ak)
                or (team_key(m["home"]) == ak and team_key(m["away"]) == hk)]
        out = []
        for m in rows[-n:]:
            out.append("%s %s %d-%d" % (m["date"].strftime("%Y-%m-%d"), m["home"], m["hg"], m["ag"]))
        return out

def render_md(out):
    """把 matches 列表渲染成 markdown 报告(与 injuries 合并共用)."""
    lines = ["# 未开赛 %d 场 完整信息 (%s)" % (len(out), datetime.now(BJT).strftime("%m-%d %H:%M")),
             "", "数据: ESPN 2026 赛果CSV(跨联赛搜索, 含升班马/降级队原属联赛)",
             "排名=BSD官方积分榜(含xG/官方form, 6h缓存), 未覆盖联赛用本地ESPN自动计算; 近5场=开赛前最近5场; 交锋=2026窗口内; 伤停/轮换/战意=API-Football/BSD(如已合并)。", ""]
    cur_day = ""
    for r in out:
        day = r["time"].split(" ")[0]
        if day != cur_day:
            cur_day = day
            lines.append("## %s" % day)
        lines.append("### %s %s  %s vs %s" % (r["time"], r["league"], r["home"], r["away"]))
        for side, tag in (("home", "主队"), ("away", "客队")):
            info = r[side + "_info"]
            es = r[side + "_espn"]
            if not info or not es:
                lines.append("- %s %s: 无ESPN数据(联赛未覆盖/队名未匹配)" % (tag, r[side]))
                continue
            src = ("(跨联赛%s)" % r[side + "_src_lg"]) if r[side + "_src_lg"] != r["league"] else ""
            rank_s = ("第%d名" % info["rank"]) if info["rank"] else "未进本季榜"
            xg_s = ""
            if info.get("xgd") is not None:
                xg_s = " | xG %s/%s(xgd %s)%s" % (
                    info.get("xgf", "?"), info.get("xga", "?"),
                    round(info["xgd"], 2),
                    (" form:%s" % info["form_bsd"]) if info.get("form_bsd") else "")
            lines.append("- %s %s [%s%s]: 本季 %d场 %d胜%d平%d负 进%d失%d 积%d | %s%s"
                         % (tag, r[side], es, src, info["P"], info["W"], info["D"],
                            info["L"], info["GF"], info["GA"], info["Pts"], rank_s, xg_s))
            lines.append("  - 近5场: %s" % ("; ".join(info["form5"]) if info["form5"] else "无"))
            fk = "form5_home" if side == "home" else "form5_away"
            lines.append("  - 近5%s: %s" % ("主场" if side == "home" else "客场",
                         "; ".join(info[fk]) if info[fk] else "无"))
        lines.append("- 交锋(2026内): %s" % ("; ".join(r["h2h"]) if r["h2h"] else "无记录"))
        lines.append("- 情报: %s" % r["intel"])
        lines.append("")
    return lines


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse as _ap
    _ap_parser = _ap.ArgumentParser()
    _ap_parser.add_argument("--with-injuries", action="store_true", help="拉取API-Football伤停并合并(消耗配额)")
    _ap_parser.add_argument("--with-bsd", action="store_true", help="BSD v2补充: 逐队伤停+共识赔率+BSD预测(消耗BSD接口)")
    _ap_args = _ap_parser.parse_args()
    scan = json.load(io.open(SCAN_JSON, encoding="utf-8"))
    now = datetime.now(timezone.utc)
    matches = [m for m in scan["matches"]
               if datetime.fromisoformat(m["ct"]).replace(tzinfo=timezone.utc) > now]
    gd = GlobalData()
    out = []
    for m in sorted(matches, key=lambda x: x["ct"]):
        lg = m["league"]
        h_es, h_lg = gd.find(m["home"], prefer_lg=lg)
        a_es, a_lg = gd.find(m["away"], prefer_lg=lg)
        ct = datetime.fromisoformat(m["ct"]).replace(tzinfo=timezone.utc).astimezone(BJT)
        rec = {"league": lg, "time": ct.strftime("%m-%d %H:%M"), "home": m["home"], "away": m["away"],
               "home_espn": h_es, "away_espn": a_es,
               "home_src_lg": h_lg, "away_src_lg": a_lg}
        table = gd.table(lg)
        for side, es, other in (("home", h_es, a_es), ("away", a_es, h_es)):
            if not es:
                rec[side + "_info"] = None
                continue
            info = {}
            tkey = team_key(es)
            if tkey in table:
                rk, s = table[tkey]
                info["rank"] = rk; info["P"] = s["P"]; info["W"] = s["W"]; info["D"] = s["D"]
                info["L"] = s["L"]; info["GF"] = s["GF"]; info["GA"] = s["GA"]; info["Pts"] = s["Pts"]
                for _xk in ("xgf", "xga", "xgd", "form_bsd"):
                    if s.get(_xk) is not None:
                        info[_xk] = s[_xk]
            else:
                info["rank"] = None; info["P"] = 0; info["W"] = 0; info["D"] = 0
                info["L"] = 0; info["GF"] = 0; info["GA"] = 0; info["Pts"] = 0
            info["form5"] = gd.form(es, 5)
            info["form5_" + ("home" if side == "home" else "away")] = gd.form(es, 5, loc=side)
            rec[side + "_info"] = info
        rec["h2h"] = gd.h2h(h_es, a_es) if (h_es and a_es) else []
        rec["intel"] = "未获取伤停/轮换/战意情报(ESPN无伤停接口, 本地无此数据源)"
        out.append(rec)
    _dates = sorted({datetime.fromisoformat(m["ct"]).replace(tzinfo=timezone.utc).astimezone(BJT).strftime("%Y-%m-%d") for m in matches})
    if _ap_args.with_injuries:
        from injuries_apifootball import fetch_injuries, build_team_map as _af_map, merge_into_info as _af_merge
        for _d in _dates:
            _recs = fetch_injuries(_d)
            if _recs is None:
                print("  ⚠️ %s API-Football伤停拉取失败, 跳过" % _d)
                continue
            _ip = os.path.join(ROOT, "analysis_records", "apifootball_injuries_%s.json" % _d)
            with io.open(_ip, "w", encoding="utf-8") as f:
                json.dump({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "date": _d, "results": len(_recs), "response": _recs}, f, ensure_ascii=False, indent=1)
            _day = [r for r in out if r["time"].startswith(_d[5:])]
            _nh, _na = _af_merge(_day, _af_map(_recs), src="apifootball")
            print("  %s API-Football伤停合并: 主队%d 客队%d" % (_d, _nh, _na))
        try:
            from injuries_bzzoiro import fetch_events as _bzz_fetch, build_team_map as _bzz_map
            for _d in _dates:
                _evs = _bzz_fetch(_d)
                if _evs is None:
                    print("  ⚠️ %s BSD伤停拉取失败, 跳过" % _d)
                    continue
                _bp = os.path.join(ROOT, "analysis_records", "bzzoiro_events_%s.json" % _d)
                with io.open(_bp, "w", encoding="utf-8") as f:
                    json.dump({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "date": _d, "n_events": len(_evs), "events": _evs}, f, ensure_ascii=False, indent=1)
                _day = [r for r in out if r["time"].startswith(_d[5:])]
                _nh, _na = _af_merge(_day, _bzz_map(_evs), src="bsd")
                print("  %s BSD伤停合并: 主队%d 客队%d" % (_d, _nh, _na))
        except Exception as _e:
            print("  ⚠️ BSD伤停合并失败: %s" % type(_e).__name__)
    if _ap_args.with_bsd:
        try:
            import bsd_extra
            for _d in _dates:
                _tmp = os.path.join(ROOT, "analysis_records", "matches_info_%s.json" % datetime.now(timezone.utc).strftime("%Y%m%d"))
                with io.open(_tmp, "w", encoding="utf-8") as f:
                    json.dump({"matches": out}, f, ensure_ascii=False, indent=1)
                _old_argv = list(sys.argv)
                sys.argv = ["bsd_extra", "--date", _d, "--info", _tmp]
                try:
                    bsd_extra.main()
                finally:
                    sys.argv = _old_argv
                _merged = json.load(io.open(_tmp, encoding="utf-8"))
                out[:] = _merged.get("matches") or []
        except Exception as _e:
            print("  ⚠️ BSD v2补充失败: %s" % type(_e).__name__)
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "n": len(out), "matches": out}, f, ensure_ascii=False, indent=1)
    with io.open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(render_md(out)))
    print("已生成 %s (%d 场) 和 %s" % (OUT_JSON, len(out), OUT_MD))


if __name__ == "__main__":
    main()
