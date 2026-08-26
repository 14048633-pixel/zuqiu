# -*- coding: utf-8 -*-
"""api-sports.io 中超(CSL=169) 联赛基准核对/拉取
用法: python fetch_csl_baseline.py [--seasons 2022,2023,2024,2025,2026]
输出: strategy_data/csl_baseline_api_check_<seasons>.json
数据源: api-sports.io v3 (FOOTBALL_API_KEY)
"""
import argparse
import json
import os
import sys
import urllib.request
from collections import Counter

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

API_KEY = os.environ.get("FOOTBALL_API_KEY") or os.environ.get("ODDS_API_KEY")
BASE_URL = "https://v3.football.api-sports.io"
LEAGUE = 169  # Chinese Super League 中超


def get(url):
    req = urllib.request.Request(url, headers={"x-apisports-key": API_KEY})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def season_stats(league, season):
    d = get(f"{BASE_URL}/fixtures?league={league}&season={season}")
    if d.get("errors"):
        return None, d["errors"]
    uniq = {}
    for f in (d.get("response") or []):
        fid = f["fixture"]["id"]
        if fid not in uniq:
            uniq[fid] = f
    fs = list(uniq.values())
    n = len(fs)
    if not n:
        return None, "empty"
    hg = [(f["goals"]["home"] or 0) for f in fs]
    ag = [(f["goals"]["away"] or 0) for f in fs]
    tot = [h + a for h, a in zip(hg, ag)]
    score_counts = Counter(f"{h}-{a}" for h, a in zip(hg, ag))
    top_scores = {k: round(v * 100.0 / n, 1) for k, v in score_counts.most_common(6)}
    return {
        "season": season, "n": n,
        "home_goals": round(sum(hg) / n, 4),
        "away_goals": round(sum(ag) / n, 4),
        "avg_goals": round(sum(tot) / n, 4),
        "over25_rate": round(sum(1 for t in tot if t > 2.5) / n, 4),
        "over35_rate": round(sum(1 for t in tot if t > 3.5) / n, 4),
        "home_win_rate": round(sum(1 for h, a in zip(hg, ag) if h > a) / n, 4),
        "draw_rate": round(sum(1 for h, a in zip(hg, ag) if h == a) / n, 4),
        "away_win_rate": round(sum(1 for h, a in zip(hg, ag) if h < a) / n, 4),
        "top_scores": top_scores,
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2022,2023,2024,2025,2026")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if not API_KEY:
        print("FAIL no FOOTBALL_API_KEY in .env")
        sys.exit(2)

    seasons = [int(x) for x in args.seasons.split(",")]
    out = {"league": LEAGUE, "league_name": "Chinese Super League 中超",
           "source": "api-sports.io v3 fixtures", "seasons": {}}
    for s in seasons:
        try:
            st, err = season_stats(LEAGUE, s)
        except Exception as e:
            st, err = None, f"exception: {e}"
        if err:
            out["seasons"][str(s)] = {"error": err}
            print(f"WARN {s}: {err}")
        else:
            out["seasons"][str(s)] = st
            print(f"OK  CSL {s}: n={st['n']} 主{st['home_goals']} 客{st['away_goals']} "
                  f"总{st['avg_goals']} 大2.5={st['over25_rate']*100:.1f}% "
                  f"主胜{st['home_win_rate']*100:.1f}% 平{st['draw_rate']*100:.1f}% "
                  f"客胜{st['away_win_rate']*100:.1f}%")

    rows = [v for v in out["seasons"].values() if "n" in v]
    if rows:
        tot_n = sum(r["n"] for r in rows)
        agg = {"n": tot_n,
               "home_goals": round(sum(r["home_goals"] * r["n"] for r in rows) / tot_n, 4),
               "away_goals": round(sum(r["away_goals"] * r["n"] for r in rows) / tot_n, 4),
               "avg_goals": round(sum(r["avg_goals"] * r["n"] for r in rows) / tot_n, 4),
               "over25_rate": round(sum(r["over25_rate"] * r["n"] for r in rows) / tot_n, 4),
               "over35_rate": round(sum(r["over35_rate"] * r["n"] for r in rows) / tot_n, 4),
               "home_win_rate": round(sum(r["home_win_rate"] * r["n"] for r in rows) / tot_n, 4),
               "draw_rate": round(sum(r["draw_rate"] * r["n"] for r in rows) / tot_n, 4),
               "away_win_rate": round(sum(r["away_win_rate"] * r["n"] for r in rows) / tot_n, 4)}
        out["aggregate"] = agg
        print(f"\nAGG n={tot_n}: 主{agg['home_goals']} 客{agg['away_goals']} 总{agg['avg_goals']} "
              f"大2.5={agg['over25_rate']*100:.1f}% 主胜{agg['home_win_rate']*100:.1f}% "
              f"平{agg['draw_rate']*100:.1f}% 客胜{agg['away_win_rate']*100:.1f}%")

    here = os.path.dirname(os.path.abspath(__file__))
    out_path = args.out or os.path.join(here, f"csl_baseline_api_check_{'_'.join(str(s) for s in seasons)}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nSAVED {out_path}")


if __name__ == "__main__":
    main()
