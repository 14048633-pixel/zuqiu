# -*- coding: utf-8 -*-
"""通用 ESPN 联赛逐场赛果抓取器 -> scan_upcoming 同格式 CSV
================================================================
来源: https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard (免费无key)
用法:
  python fetch_espn_league.py --league 英乙      # 增量更新
  python fetch_espn_league.py --league 英乙 --force
  python fetch_espn_league.py --all             # 拉全部已配置联赛
窗口: 自然年 20260101-20270101 (已验证: eng.3/eng.4/swe.1/nor.1/bra.1/arg.1/usa.1/tur.1/mex.1/chi.1/den.1/ita.2/fra.2)
"""
import argparse, csv, io, json, os, sys, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "raw", "football_data")

# 联赛配置: key=中文联赛名, espn=ESPN联赛码, div=输出Div, season=自然年赛季(自动标签跨年)
LEAGUES = {
    "英乙": {"espn": "eng.4", "div": "E3", "season": "2026/2027"},
    "瑞超": {"espn": "swe.1", "div": "SW", "season": "2026"},
    "挪超": {"espn": "nor.1", "div": "NO", "season": "2026"},
    "巴甲": {"espn": "bra.1", "div": "BR", "season": "2026"},
    "阿甲": {"espn": "arg.1", "div": "AR", "season": "2026"},
    "美职": {"espn": "usa.1", "div": "ML", "season": "2026"},
    "土超": {"espn": "tur.1", "div": "TK", "season": "2026"},
    "墨超": {"espn": "mex.1", "div": "MX", "season": "2026"},
    "智利甲": {"espn": "chi.1", "div": "CH", "season": "2026"},
    "丹超": {"espn": "den.1", "div": "DK", "season": "2026"},
    "意乙": {"espn": "ita.2", "div": "I2", "season": "2026/2027"},
    "法乙": {"espn": "fra.2", "div": "F2", "season": "2026/2027"},
    "荷甲": {"espn": "ned.1", "div": "D1", "season": "2026/2027"},
    "德乙": {"espn": "ger.2", "div": "D2", "season": "2026/2027"},
    "比甲": {"espn": "bel.1", "div": "BE", "season": "2026/2027"},
    "英冠": {"espn": "eng.2", "div": "E2", "season": "2026/2027"},
    "葡超": {"espn": "por.1", "div": "PO", "season": "2026/2027"},
    "西乙": {"espn": "esp.2", "div": "S2", "season": "2026/2027"},
    "西甲": {"espn": "esp.1", "div": "SD", "season": "2026/2027"},
    "英超": {"espn": "eng.1", "div": "E1", "season": "2026/2027"},
    "土甲": {"espn": "tur.2", "div": "T2", "season": "2026/2027"},
}
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates=20260101-20270101&limit=1000"

# 跨年联赛(秋开春结): 8/1前场次归上季, 之后归当季
AUTUMN_LEAGUES = {"E3", "I2", "F2", "D1", "D2", "BE", "E2", "PO", "S2", "SD", "E1", "T2"}
AUTUMN_CUT = datetime(2026, 8, 1)


def _season_for(div, date_str):
    if div in AUTUMN_LEAGUES:
        d = datetime.strptime(date_str[:10], "%Y/%m/%d")
        return "2025/2026" if d < AUTUMN_CUT else "2026/2027"
    return LEAGUES[_div_to_lg(div)]["season"]


def _div_to_lg(div):
    for lg, cfg in LEAGUES.items():
        if cfg["div"] == div:
            return lg
    return div


def fetch(espn_code):
    url = URL.format(code=espn_code)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pull_league(lg, force=False):
    cfg = LEAGUES[lg]
    out_path = os.path.join(DATA_DIR, "espn_{}_results.csv".format(lg))
    data = fetch(cfg["espn"])
    events = data.get("events") or []
    seen = set()
    rows = []
    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        st = (comp.get("status") or {}).get("type") or {}
        if st.get("name") != "STATUS_FULL_TIME":
            continue
        cs = comp.get("competitors") or []
        home = next((c for c in cs if c.get("homeAway") == "home"), None)
        away = next((c for c in cs if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        date = (ev.get("date") or "")[:10].replace("-", "/")
        h = (home["team"].get("displayName") or "").strip()
        a = (away["team"].get("displayName") or "").strip()
        if not h or not a:
            continue
        key = (date, h, a)
        if key in seen:
            continue
        seen.add(key)
        season = _season_for(cfg["div"], date)
        rows.append([cfg["div"], date, h, a, int(home.get("score") or 0), int(away.get("score") or 0), season])

    old_keys = set()
    if not force and os.path.exists(out_path):
        with io.open(out_path, encoding="utf-8") as f:
            for r in csv.reader(f):
                if r and len(r) >= 7 and r[0] == cfg["div"]:
                    old_keys.add((r[1], r[2], r[3]))
    new_rows = [r for r in rows if (r[1], r[2], r[3]) not in old_keys]
    if new_rows or force:
        os.makedirs(DATA_DIR, exist_ok=True)
        new_file = (not os.path.exists(out_path)) or os.path.getsize(out_path) == 0
        mode = "w" if (force or new_file) else "a"
        with io.open(out_path, mode, encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if force or new_file:
                w.writerow(["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "Season"])
            for r in (rows if force else new_rows):
                w.writerow(r)
    return len(rows), (len(rows) if force else len(new_rows)), out_path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=list(LEAGUES) + ["all"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    lgs = list(LEAGUES) if args.league == "all" else [args.league]
    for lg in lgs:
        total, added, out = pull_league(lg, args.force)
        print("%s: API完赛 %d | 新增 %d | -> %s" % (lg, total, added, out))


if __name__ == "__main__":
    main()
