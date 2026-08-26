"""API-Football 小联赛基准核对（免费档 2022-2024 赛季）
====================================================
用法: python fetch_league_baseline_check.py [--league 293] [--seasons 2022,2023,2024]
输出: strategy_data/k2_baseline_api_check_2022_2024.json
数据源: api-sports.io v3 (FOOTBALL_API_KEY, 免费档仅 2022-2024)
"""
import json
import os
import sys
import urllib.request

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except Exception:
    pass

API_KEY = os.environ.get("FOOTBALL_API_KEY") or os.environ.get("ODDS_API_KEY")
BASE_URL = "https://v3.football.api-sports.io"


def get(url):
    req = urllib.request.Request(url, headers={"x-apisports-key": API_KEY})
    with urllib.request.urlopen(req, timeout=30) as resp:
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
    hg = [f["goals"]["home"] for f in fs]
    ag = [f["goals"]["away"] for f in fs]
    tot = [h + a for h, a in zip(hg, ag)]
    return {
        "season": season, "n": n,
        "home_goals": round(sum(hg) / n, 4),
        "away_goals": round(sum(ag) / n, 4),
        "avg_goals": round(sum(tot) / n, 4),
        "over25_rate": round(sum(1 for t in tot if t > 2.5) / n, 4),
        "home_win_rate": round(sum(1 for f in fs if f["goals"]["home"] > f["goals"]["away"]) / n, 4),
        "draw_rate": round(sum(1 for f in fs if f["goals"]["home"] == f["goals"]["away"]) / n, 4),
        "away_win_rate": round(sum(1 for f in fs if f["goals"]["home"] < f["goals"]["away"]) / n, 4),
    }, None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", type=int, default=293, help="K League 2=293, K1=292")
    ap.add_argument("--seasons", default="2022,2023,2024")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if not API_KEY:
        print("❌ 未找到 FOOTBALL_API_KEY（.env）")
        sys.exit(2)

    seasons = [int(x) for x in args.seasons.split(",")]
    out = {"league": args.league, "source": "api-sports.io v3 fixtures", "seasons": {}}
    for s in seasons:
        st, err = season_stats(args.league, s)
        if err:
            out["seasons"][str(s)] = {"error": err}
            print(f"⚠️ {s}: {err}")
        else:
            out["seasons"][str(s)] = st
            print(f"✔ K{args.league} {s}: n={st['n']} 主{st['home_goals']} 客{st['away_goals']} "
                  f"总{st['avg_goals']} 大2.5={st['over25_rate']:.1%} "
                  f"主胜{st['home_win_rate']:.1%} 平{st['draw_rate']:.1%} 客胜{st['away_win_rate']:.1%}")

    rows = [v for v in out["seasons"].values() if "n" in v]
    if rows:
        tot_n = sum(r["n"] for r in rows)
        agg = {"n": tot_n,
               "home_goals": round(sum(r["home_goals"] * r["n"] for r in rows) / tot_n, 4),
               "away_goals": round(sum(r["away_goals"] * r["n"] for r in rows) / tot_n, 4),
               "avg_goals": round(sum(r["avg_goals"] * r["n"] for r in rows) / tot_n, 4),
               "over25_rate": round(sum(r["over25_rate"] * r["n"] for r in rows) / tot_n, 4),
               "home_win_rate": round(sum(r["home_win_rate"] * r["n"] for r in rows) / tot_n, 4),
               "draw_rate": round(sum(r["draw_rate"] * r["n"] for r in rows) / tot_n, 4),
               "away_win_rate": round(sum(r["away_win_rate"] * r["n"] for r in rows) / tot_n, 4)}
        out["aggregate"] = agg
        print(f"\n✔ 聚合 n={tot_n}: 主{agg['home_goals']} 客{agg['away_goals']} 总{agg['avg_goals']} "
              f"大2.5={agg['over25_rate']:.1%} 主胜{agg['home_win_rate']:.1%} 平{agg['draw_rate']:.1%} 客胜{agg['away_win_rate']:.1%}")

    out_path = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                        f"k{args.league}_baseline_api_check_{'_'.join(str(s) for s in seasons)}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✔ 已保存: {out_path}")


if __name__ == "__main__":
    main()
