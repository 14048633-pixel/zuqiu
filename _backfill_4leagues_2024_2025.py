# -*- coding: utf-8 -*-
"""4联赛 2024/2025 历史补拉 (美职/法乙/瑞超/巴甲) -> espn_{lg}_2024_2025_results.csv
模式同墨超: 自然年2024->"2024/2025"(权重0.7), 2025->"2025/2026"(权重1.0);
法乙例外: 按欧战赛季边界(8/1)归季。
输出列: Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,Season
"""
import csv, io, json, os, sys, time, urllib.request
from datetime import datetime

ROOT = r"D:\足球分析"
DATA_DIR = os.path.join(ROOT, "data", "raw", "football_data")
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

LEAGUES = {
    "美职": {"espn": "usa.1", "div": "ML", "style": "cal"},
    "法乙": {"espn": "fra.2", "div": "F2", "style": "euro"},
    "瑞超": {"espn": "swe.1", "div": "SW", "style": "cal"},
    "巴甲": {"espn": "bra.1", "div": "BR", "style": "cal"},
}
WINDOWS = [("20240101", "20240630"), ("20240701", "20241231"),
           ("20250101", "20250630"), ("20250701", "20251231")]

def fetch(code, d0, d1):
    url = ("https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s-%s&limit=1000" % (code, d0, d1))
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8"))
        except Exception as e:
            if i == 2:
                raise
            time.sleep(3)

def season_for(style, date):
    y, m, d = date.split("/")
    if style == "euro":
        return "2024/2025" if (int(y), int(m)) < (2025, 8) else "2025/2026"
    return "2024/2025" if y == "2024" else "2025/2026"

def load_existing(lg):
    p = os.path.join(DATA_DIR, "espn_%s_results.csv" % lg)
    keys, names = set(), set()
    if os.path.exists(p):
        with io.open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                dt = (r.get("Date") or "").strip()
                h = (r.get("HomeTeam") or "").strip()
                a = (r.get("AwayTeam") or "").strip()
                if dt and h and a:
                    keys.add((dt, h, a))
                    names.add(h); names.add(a)
    return keys, names

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    for lg, cfg in LEAGUES.items():
        rows, seen = [], set()
        for d0, d1 in WINDOWS:
            data = fetch(cfg["espn"], d0, d1)
            for ev in data.get("events") or []:
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
                if not h or not a or not date.startswith("20"):
                    continue
                key = (date, h, a)
                if key in seen:
                    continue
                seen.add(key)
                rows.append([cfg["div"], date, h, a, int(home.get("score") or 0), int(away.get("score") or 0), season_for(cfg["style"], date)])
            time.sleep(1.0)
        # 去重: 与现有2026文件按 (date,home,away) 精确比对
        old_keys, old_names = load_existing(lg)
        new_rows = [r for r in rows if (r[1], r[2], r[3]) not in old_keys]
        # 队名对齐报告: 新文件里的队名是否都在现有文件出现过
        new_names = set()
        for r in rows:
            new_names.add(r[2]); new_names.add(r[3])
        missing = sorted(n for n in new_names if n not in old_names)
        out = os.path.join(DATA_DIR, "espn_%s_2024_2025_results.csv" % lg)
        with io.open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "Season"])
            for r in rows:
                w.writerow(r)
        from collections import Counter
        seas = Counter(r[6] for r in rows)
        print("== %s: 2024/25窗口完赛 %d | 与2026文件重叠跳过 %d | 写入 %s | 赛季分布 %s" % (lg, len(rows), len(rows)-len(new_rows), out, dict(seas)))
        print("   队名不在2026文件出现(%d): %s" % (len(missing), missing[:12]))

if __name__ == "__main__":
    main()
