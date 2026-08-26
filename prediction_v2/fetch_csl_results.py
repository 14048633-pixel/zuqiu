# -*- coding: utf-8 -*-
"""中超(CSL) 2026赛季 逐场赛果抓取: ESPN scoreboard(主) + BSD(兜底) -> scan_upcoming 同格式 CSV
================================================================
来源: ESPN scoreboard(免费无key) / BSD Bzzoiro events(免费Token, 中超 league_id=52)
输出: data/raw/football_data/csl_2026_results.csv (列: Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,Season)
用法:
  python fetch_csl_results.py            # 增量更新(只追加新完赛场次)
  python fetch_csl_results.py --force    # 全量重建
只写入完赛场次; 队名归一化到 teams_alias.json 标准英文名(与盘口快照/scan 一致);
ESPN 403/空时自动切换 BSD 兜底(2026-08-22 实测 ESPN Akamai 反爬曾中断)。
"""
import argparse, csv, io, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "football_data", "csl_2026_results.csv")
ENV = os.path.join(ROOT, ".env")
ESPN_URL = ("https://site.api.espn.com/apis/site/v2/sports/soccer/chn.1/scoreboard"
            "?dates=20260101-20270101&limit=1000")
BSD_LEAGUE_ID = 52      # BSD 中超
DIV = "C1"
SEASON = "2026"

# ESPN 队名 -> teams_alias.json 标准英文名 (无则原样)
TEAM_MAP = {
    "Tianjin Jinmen Tiger": "Tianjin Jinmen Tiger FC",
    "Beijing Guoan": "Beijing FC",
    "Zhejiang Professional FC": "Zhejiang",
    "Chengdu Rongcheng": "Chengdu Rongcheng FC",
    "Liaoning Tieren": "Liaoning Tieren FC",
    "Shanghai Shenhua": "Shanghai Shenhua FC",
    "Shenzhen Xinpengcheng": "Shenzhen Peng City FC",
    "Henan": "Henan FC",
    # 以下6队保持 ESPN 官方名作为标准英文名(teams_alias 已加同键别名)
    "Shanghai Port": "Shanghai Port",
    "Shandong Taishan": "Shandong Taishan",
    "Wuhan Three Towns": "Wuhan Three Towns",
    "Qingdao West Coast": "Qingdao West Coast",
    "Qingdao Hainiu": "Qingdao Hainiu",
    "Chongqing Tonglianglong": "Chongqing Tonglianglong",
}


def fetch():
    req = urllib.request.Request(ESPN_URL, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _bsd_token():
    if not os.path.exists(ENV):
        return ""
    for line in io.open(ENV, encoding="utf-8"):
        if line.startswith("BZZOIRO_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def fetch_bsd():
    """BSD兜底: 中超 finished events -> [(date, home, away, hg, ag)]"""
    token = _bsd_token()
    if not token:
        return []
    since = (datetime.now(timezone.utc) - timedelta(days=120)).strftime("%Y-%m-%dT00:00:00Z")
    out, off = [], 0
    while True:
        u = ("https://sports.bzzoiro.com/api/v2/events/?league_id=%d&status=finished"
             "&date_from=%s&limit=100&offset=%d" % (BSD_LEAGUE_ID, since, off))
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + token})
        d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        rows = d.get("results") or []
        if not rows:
            break
        for ev in rows:
            h, a = ev.get("home_team"), ev.get("away_team")
            hs, as_ = ev.get("home_score"), ev.get("away_score")
            if not h or not a or hs is None or as_ is None:
                continue
            dt = (ev.get("event_date") or ev.get("start_time") or "")[:10].replace("-", "/")
            if not dt.startswith("20"):
                continue
            out.append((dt, norm_team(h), norm_team(a), int(hs), int(as_)))
        off += len(rows)
        if len(rows) < 100:
            break
    return out


def norm_team(name):
    t = TEAM_MAP.get(name, name)
    return t.strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="全量重建(默认增量)")
    args = ap.parse_args()

    rows, src = [], "ESPN"
    try:
        data = fetch()
        events = data.get("events") or []
        if not events:
            raise ValueError("ESPN 返回空 events")
        seen = set()
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
            h, a = norm_team(home["team"]["displayName"]), norm_team(away["team"]["displayName"])
            key = (date, h, a)
            if key in seen:
                continue
            seen.add(key)
            rows.append([DIV, date, h, a, int(home.get("score") or 0), int(away.get("score") or 0), SEASON])
    except Exception as e:
        print("ESPN不可用(%s), 切换BSD兜底..." % type(e).__name__)
        bsd = fetch_bsd()
        rows = [[DIV, dt, h, a, hg, ag, SEASON] for dt, h, a, hg, ag in bsd]
        src = "BSD"

    # 增量: 读旧文件跳过已存在
    old_keys = set()
    if not args.force and os.path.exists(OUT):
        with io.open(OUT, encoding="utf-8") as f:
            for r in csv.reader(f):
                if r and len(r) >= 7 and r[0] == DIV:
                    old_keys.add((r[1], r[2], r[3]))
    new_rows = [r for r in rows if (r[1], r[2], r[3]) not in old_keys]
    if new_rows or args.force:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        mode = "w" if args.force else "a"
        with io.open(OUT, mode, encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if args.force:
                w.writerow(["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "Season"])
            for r in (rows if args.force else new_rows):
                w.writerow(r)
    print("中超完赛场次(%s): %d  | 新增写入: %d" % (src, len(rows), len(rows) if args.force else len(new_rows)))
    print("输出: %s" % OUT)


if __name__ == "__main__":
    main()
