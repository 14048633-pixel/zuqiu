# -*- coding: utf-8 -*-
"""football-data.org v4 -> 赛程/赛果/积分榜/球队/攻防stats 入库
============================================================
用法:
  python prediction_v2/fetch_footballdata.py                 # 默认 9 个主流联赛(英超/英冠/西甲/意甲/德甲/法甲/荷甲/葡超/巴甲)
  python prediction_v2/fetch_footballdata.py --all           # 追加欧冠/解放者杯/世界杯/欧洲杯(已结束赛季仅回填赛果)
  python prediction_v2/fetch_footballdata.py --codes PL,PD   # 只拉指定联赛代码
  python prediction_v2/fetch_footballdata.py --force         # 重拉(默认当日已有输出则跳过)

输出(data/raw/football_data/):
  footballdata_results.csv            # 已结束赛果(scan_upcoming 兼容列: Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,Season)
  footballdata_schedule_<date>.json   # 未开赛赛程(含足球数据id/开球UTC/两队名)
  footballdata_standings_<date>.json  # 积分榜(原始)
  footballdata_teams_<date>.json      # 球队(原始name/shortName/tla + 归一化标准名)
  footballdata_team_stats_<date>.json # 攻防stats(stats键, 与bsd_league_stats同构, 供 pull_match_package 兜底)

限制: 阵容/赔率端点需付费(Odds-Package/PRO), 免费key不可用 -> 对应字段标注"未提取", 不伪造.
限流: 免费档 6 请求/分钟, 按响应头 x-requests-available-minute 自适应休眠.
"""
import argparse, csv, io, json, os, sys, time, unicodedata
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "raw", "football_data")
ENV_FILE = os.path.join(ROOT, ".env")
BASE = "https://api.football-data.org/v4"
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y%m%d")

# (代码, Div, 系统中文联赛名, 是否国内联赛)
COMPETITIONS = [
    ("PL", "E0", "英超", True),
    ("ELC", "E1", "英冠", True),
    ("PD", "SP1", "西甲", True),
    ("SA", "I1", "意甲", True),
    ("BL1", "D1", "德甲", True),
    ("FL1", "F1", "法甲", True),
    ("DED", "N1", "荷甲", True),
    ("PPL", "P1", "葡超", True),
    ("BSA", "BR", "巴甲", True),
    ("CL", "CL", "欧冠", False),
    ("CLI", "CLI", "解放者杯", False),
    ("WC", "WC", "世界杯", False),
    ("EC", "EC", "欧洲杯", False),
]

# football-data.org shortName -> 本地数据池标准英文名(与 matches_2015_2025 / teams_map 一致)
TEAM_MAP = {
    # 英超
    "Man City": "Man City", "Man United": "Man United", "Forest": "Nott'm Forest",
    "Nott'm Forest": "Nott'm Forest", "Wolves": "Wolves", "Tottenham": "Tottenham",
    # 西甲
    "Atleti": "Ath Madrid", "Athletic": "Ath Bilbao", "Barça": "Barcelona",
    "Vallecano": "Vallecano", "Sociedad": "Sociedad", "Betis": "Betis",
    "Alavés": "Alaves", "Girona": "Girona", "Mallorca": "Mallorca",
    # 意甲
    "Milan": "Milan", "Roma": "Roma", "Inter": "Inter", "Juventus": "Juventus",
    # 德甲
    "Bayern": "Bayern Munich", "Schalke": "Schalke 04", "Köln": "FC Koln",
    "1. FC Köln": "FC Koln", "Frankfurt": "Ein Frankfurt", "Gladbach": "M'gladbach",
    "Leipzig": "RB Leipzig", "Bremen": "Werder Bremen", "St Pauli": "St Pauli",
    # 法甲
    "Paris SG": "Paris SG", "St Etienne": "St Etienne", "St-Etienne": "St Etienne",
    # 荷甲
    "PSV": "PSV Eindhoven", "Fortuna": "For Sittard", "PEC Zwolle": "Zwolle",
    "NEC": "Nijmegen", "Roda JC": "Roda", "ADO Den Haag": "Den Haag",
    "VVV": "VVV Venlo", "AZ": "AZ Alkmaar",
    # 英冠
    "QPR": "QPR", "Sheffield United": "Sheffield United", "Leeds": "Leeds",
}


def load_key():
    if not os.path.exists(ENV_FILE):
        return ""
    for line in io.open(ENV_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("FOOTBALL_DATA_KEY="):
            return s.split("=", 1)[1].strip().strip('"').strip("'").split()[0]
    return ""


KEY = load_key()


def norm_clean(s):
    """去重音/统一空格 -> 便于比对"""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.replace("-", " ").replace(".", " ").replace("'", " ").split())


def norm_team(name):
    """football-data.org shortName -> 本地标准英文名(内置映射 + teams_alias 兜底)"""
    n = TEAM_MAP.get(name) or name
    try:
        alias_fp = os.path.join(ROOT, "strategy_data", "teams_alias.json")
        if os.path.exists(alias_fp):
            alias = json.load(io.open(alias_fp, encoding="utf-8")).get("alias") or {}
            n = alias.get(n) or alias.get(name) or n
    except Exception:
        pass
    return n.strip()


def season_label(result_set):
    """由 resultSet.first/last 推导赛季标签(与 SEASON_WEIGHT 键一致)"""
    try:
        first = (result_set or {}).get("first") or ""
        last = (result_set or {}).get("last") or ""
        fy, ly = first[:4], last[:4]
        if fy and ly and fy != ly:
            return "%s/%s" % (fy, ly)
        return fy or ""
    except Exception:
        return ""


def _get(path, params, tries=3):
    """GET + 限流自适应(按 x-requests-available-minute 休眠)"""
    import requests
    for i in range(1, tries + 1):
        try:
            r = requests.get(BASE + path, params=params,
                             headers={"X-Auth-Token": KEY}, timeout=30)
            if r.status_code == 200:
                hdr = {k.lower(): v for k, v in r.headers.items()}
                try:
                    left = int(hdr.get("x-requests-available-minute", 6) or 6)
                except Exception:
                    left = 6
                if left <= 2:
                    time.sleep(max(2.0, (6 - left + 1) * 2.5))
                return r.json()
            if r.status_code == 429:
                wait = min(60, 20 * i)
                print("  429限流, 退避%ds (第%d次)" % (wait, i), flush=True)
                time.sleep(wait)
                continue
            print("  HTTP %s: %s" % (r.status_code, (r.text or "")[:120]))
            return None
        except Exception as e:
            print("  第%d次失败: %s" % (i, type(e).__name__), flush=True)
        time.sleep(3)
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="含欧冠/解放者杯/世界杯/欧洲杯")
    ap.add_argument("--codes", default="", help="只拉指定联赛代码, 逗号分隔(如 PL,PD)")
    ap.add_argument("--force", action="store_true", help="重拉(默认当日已有输出跳过)")
    args = ap.parse_args()

    if not KEY:
        print("❌ 无 FOOTBALL_DATA_KEY(.env)")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    results_csv = os.path.join(OUT_DIR, "footballdata_results.csv")
    if os.path.exists(results_csv) and not args.force and not args.codes:
        print("⚠️ 当日已有输出(%s), 跳过. 用 --force 重拉." % results_csv)
        return

    codes = {c.strip() for c in args.codes.split(",") if c.strip()}
    comps = [c for c in COMPETITIONS if (c[0] in codes) or (not codes and (args.all or c[3]))]
    print("拉取 %d 个联赛: %s" % (len(comps), ", ".join(c[0] for c in comps)))

    results_rows, seen = [], set()
    schedule, standings, teams_all, stats_agg = {}, {}, {}, {}
    per_league = {}

    for code, div, cn, _dom in comps:
        print("== %s (%s) ==" % (cn, code), flush=True)
        j = _get("/competitions/%s/matches" % code, {})
        if not j:
            per_league[code] = {"error": "matches 拉取失败"}
            continue
        ms = j.get("matches") or []
        label = season_label(j.get("resultSet"))
        if not label:
            label = "2026/2027" if div in ("E0", "SP1") else "2026"
        n_fin = n_sch = 0
        for m in ms:
            status, date = m.get("status", ""), (m.get("utcDate") or "")[:10]
            home, away = m["homeTeam"]["name"], m["awayTeam"]["name"]
            hh, aa = norm_team(m["homeTeam"]["shortName"]), norm_team(m["awayTeam"]["shortName"])
            if status == "FINISHED":
                sc = (m.get("score") or {}).get("fullTime") or {}
                hg, ag = sc.get("home"), sc.get("away")
                if hg is None or ag is None:
                    continue
                dt = date.replace("-", "/")
                key = (div, dt, hh, aa)
                if key not in seen:
                    seen.add(key)
                    results_rows.append([div, dt, hh, aa, hg, ag, label])
                    for side, gf, ga in ((hh, hg, ag), (aa, ag, hg)):
                        r = stats_agg.setdefault(side, {"home_gf": [0.0, 0], "home_ga": [0.0, 0],
                                                       "away_gf": [0.0, 0], "away_ga": [0.0, 0]})
                        if side == hh:
                            r["home_gf"][0] += gf; r["home_gf"][1] += 1
                            r["home_ga"][0] += ga; r["home_ga"][1] += 1
                        else:
                            r["away_gf"][0] += gf; r["away_gf"][1] += 1
                            r["away_ga"][0] += ga; r["away_ga"][1] += 1
                n_fin += 1
            elif status in ("TIMED", "SCHEDULED"):
                schedule.setdefault(code, {"league": cn, "div": div, "matches": []})
                schedule[code]["matches"].append({
                    "fd_id": m.get("id"), "kickoff_utc": m.get("utcDate"), "status": status,
                    "home": hh, "away": aa, "home_raw": home, "away_raw": away,
                    "matchday": m.get("matchday"), "group": m.get("group")})
                n_sch += 1
        per_league[code] = {"league": cn, "div": div, "season": label,
                            "finished": n_fin, "scheduled": n_sch,
                            "lineups": "未提取(付费端点)", "odds": "未提取(需Odds-Package)"}
        print("  赛果 %d | 赛程 %d" % (n_fin, n_sch), flush=True)

        sj = _get("/competitions/%s/standings" % code, {})
        if sj:
            standings[code] = sj
            print("  积分榜 %s" % ((sj.get("standings") or [{}])[0].get("type", "")), flush=True)
        else:
            per_league[code]["standings"] = "未提取"
        time.sleep(6)

        tj = _get("/competitions/%s/teams" % code, {})
        if tj:
            teams_all[code] = {
                "league": cn, "teams": [{
                    "id": t.get("id"), "name": t.get("name"), "shortName": t.get("shortName"),
                    "tla": t.get("tla"), "std_name": norm_team(t.get("shortName"))}
                    for t in (tj.get("teams") or [])]}
            print("  球队 %d" % len(teams_all[code]["teams"]), flush=True)
        else:
            per_league[code]["teams"] = "未提取"
        time.sleep(6)

    # 写赛果CSV(增量合并, 按(div,date,home,away,season)去重)
    old_rows = []
    if os.path.exists(results_csv):
        with io.open(results_csv, encoding="utf-8", errors="replace") as f:
            old_rows = list(csv.DictReader(f))
    merged = {tuple(r[k] for k in ("Div", "Date", "HomeTeam", "AwayTeam", "Season")): r for r in old_rows}
    for r in results_rows:
        merged[(r[0], r[1], r[2], r[3], r[6])] = {"Div": r[0], "Date": r[1], "HomeTeam": r[2],
                                                  "AwayTeam": r[3], "FTHG": r[4], "FTAG": r[5], "Season": r[6]}
    rows = sorted(merged.values(), key=lambda x: (x["Div"], x["Date"]))
    with io.open(results_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "Season"])
        w.writeheader()
        w.writerows(rows)
    print("赛果CSV: %d 场 -> %s" % (len(rows), results_csv))

    def _avg(v):
        return round(v[0] / v[1], 3) if v[1] > 0 else 0.0
    stats_out = {t: {"home_gf": _avg(r["home_gf"]), "home_ga": _avg(r["home_ga"]),
                     "away_gf": _avg(r["away_gf"]), "away_ga": _avg(r["away_ga"]),
                     "n_home": r["home_gf"][1], "n_away": r["away_gf"][1],
                     "src_season": "footballdata", "src_w": 1.0, "src_tag": "footballdata"}
                 for t, r in sorted(stats_agg.items())}
    ts = datetime.now(timezone.utc).isoformat()
    with io.open(os.path.join(OUT_DIR, "footballdata_team_stats_%s.json" % TODAY), "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "note": "football-data.org 当前赛季赛果攻防汇总",
                   "n_matches": len(rows), "n_teams": len(stats_out), "stats": stats_out},
                  f, ensure_ascii=False, indent=1)
    with io.open(os.path.join(OUT_DIR, "footballdata_schedule_%s.json" % TODAY), "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "leagues": per_league, "schedule": schedule}, f, ensure_ascii=False, indent=1)
    with io.open(os.path.join(OUT_DIR, "footballdata_standings_%s.json" % TODAY), "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "leagues": per_league, "standings": standings}, f, ensure_ascii=False, indent=1)
    with io.open(os.path.join(OUT_DIR, "footballdata_teams_%s.json" % TODAY), "w", encoding="utf-8") as f:
        json.dump({"ts": ts, "leagues": per_league, "teams": teams_all}, f, ensure_ascii=False, indent=1)
    print("完成: %d 队攻防stats / %d 未开赛赛程 / 积分榜 %d / 球队 %d"
          % (len(stats_out), sum(len(v.get("matches", [])) for v in schedule.values()),
             len(standings), len(teams_all)))


if __name__ == "__main__":
    main()
