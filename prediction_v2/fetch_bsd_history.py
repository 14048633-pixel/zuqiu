# -*- coding: utf-8 -*-
"""BSD历史赛果 -> 球队攻防stats(补数据池缺口: 保甲/希腊超/欧冠等)
============================================================
用法: python prediction_v2/fetch_bsd_history.py --leagues "22,24,7,54,11,6" --days 400 --limit 30
输出: data/raw/football_data/bsd_league_stats.json
  {norm队名: {home_gf/home_ga/away_gf/away_ga/n_home/n_away/src_season/src_w/src_tag}}
限流: 请求间隔1.8s, 429退避25s, 最多4次重试
"""
import argparse, io, json, os, sys, time, unicodedata, collections
from datetime import datetime, timezone, timedelta
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")


def load_token():
    if not os.path.exists(ENV_FILE):
        return ""
    for line in io.open(ENV_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("BZZOIRO_API_KEY="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


TOKEN = load_token()
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Authorization": "Token " + TOKEN}
BASE = "https://sports.bzzoiro.com/api/v2"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace("-", " ").replace(".", " ").replace("'", " ").replace("&", " ").split())


def _get(path, tries=4):
    for i in range(1, tries + 1):
        try:
            r = requests.get(BASE + path, headers=H, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                print("  429限流, 退避25s (第%d次)" % i, flush=True)
                time.sleep(25)
                continue
            print("  HTTP %s: %s" % (r.status_code, (r.text or "")[:120]))
            return None
        except Exception as e:
            print("  第%d次失败: %s" % (i, type(e).__name__))
        time.sleep(3)
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="22,24,7", help="BSD league_id 逗号分隔")
    ap.add_argument("--days", type=int, default=400)
    ap.add_argument("--out", default="data/raw/football_data/bsd_league_stats.json")
    ap.add_argument("--limit", type=int, default=60, help="每联赛最多拉页数(每页100)")
    args = ap.parse_args()
    if not TOKEN:
        print("❌ 无 BZZOIRO_API_KEY")
        return
    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime("%Y-%m-%dT00:00:00Z")
    agg = collections.defaultdict(lambda: {"home_gf": [0.0, 0], "home_ga": [0.0, 0],
                                           "away_gf": [0.0, 0], "away_ga": [0.0, 0]})
    total = 0
    for lid in [x.strip() for x in args.leagues.split(",") if x.strip()]:
        off, pages = 0, 0
        while pages < args.limit:
            j = _get("/events/?league_id=%s&status=finished&date_from=%s&limit=100&offset=%d" % (lid, since, off))
            if j is None:
                break
            rows = j.get("results") or []
            if not rows:
                break
            for ev in rows:
                h, a = ev.get("home_team"), ev.get("away_team")
                hs, as_ = ev.get("home_score"), ev.get("away_score")
                if not h or not a or hs is None or as_ is None:
                    continue
                w = 1.0
                for side, gf, ga in ((h, hs, as_), (a, as_, hs)):
                    r = agg[norm(side)]
                    if side == h:
                        r["home_gf"][0] += gf * w; r["home_gf"][1] += w
                        r["home_ga"][0] += ga * w; r["home_ga"][1] += w
                    else:
                        r["away_gf"][0] += gf * w; r["away_gf"][1] += w
                        r["away_ga"][0] += ga * w; r["away_ga"][1] += w
                total += 1
            off += len(rows)
            pages += 1
            time.sleep(1.8)
        print("联赛 %s: 拉取 %d 场" % (lid, off), flush=True)
    out = {}
    for t, r in agg.items():
        def avg(v):
            return round(v[0] / v[1], 3) if v[1] > 0 else 0.0
        out[t] = {"home_gf": avg(r["home_gf"]), "home_ga": avg(r["home_ga"]),
                  "away_gf": avg(r["away_gf"]), "away_ga": avg(r["away_ga"]),
                  "n_home": r["home_gf"][1], "n_away": r["away_gf"][1],
                  "src_season": "BSD", "src_w": 1.0, "src_tag": "bsd"}
    with io.open(os.path.join(ROOT, args.out), "w", encoding="utf-8") as f:
        json.dump({"ts": datetime.now(timezone.utc).isoformat(), "leagues": args.leagues,
                   "days": args.days, "n_matches": total, "n_teams": len(out), "stats": out},
                  f, ensure_ascii=False, indent=1)
    print("完成: %d 场, %d 队 -> %s" % (total, len(out), args.out))


if __name__ == "__main__":
    main()
