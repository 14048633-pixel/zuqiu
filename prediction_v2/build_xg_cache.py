"""构建 xG 缓存：football-data 比赛 ↔ soccer-dataset 逐场 xG
=================================================
连接链：football-data(Date,HomeTeam,AwayTeam) → teams_map(fd_name→soccer_id) → fixtures(team_id+date±1天) → match_stats(home_xg/away_xg)
用法：python build_xg_cache.py [--out prediction_v2/xg_cache.csv]
"""
import argparse
import os
import sys
from datetime import timedelta

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from src.data_loader import load_football_data


def to_date(s):
    try:
        return pd.Timestamp(s).date()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "xg_cache.csv"))
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    data_dir = os.path.normpath(os.path.join(HERE, cfg["data"]["football_dir"]))
    teams_path = os.path.normpath(os.path.join(HERE, "teams_map.json"))

    print("1) 加载 football-data ...")
    df = load_football_data(data_dir, min_date=cfg["data"].get("min_date"),
                            max_date=cfg["data"].get("max_date"))
    df["d"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce").dt.date
    print(f"   {len(df)} 场")

    print("2) 加载 teams_map ...")
    import json
    tm = json.load(open(teams_path, encoding="utf-8"))
    name2id = {t: v["soccer_id"] for t, v in tm["football_data_to_soccer"].items()}

    print("3) 加载 soccer-dataset fixtures + match_stats ...")
    fx = pd.read_parquet(os.path.normpath(os.path.join(HERE, cfg["data"].get("soccer_fixtures", "../data/raw/soccer-dataset/fixtures.parquet"))))
    ms = pd.read_parquet(os.path.normpath(os.path.join(HERE, cfg["data"].get("soccer_match_stats", "../data/raw/soccer-dataset/match_stats.parquet"))))
    fx = fx[fx["status_norm"] == "FT"]
    fx = fx[["id", "date_utc", "home_team_id", "away_team_id", "goals_home", "goals_away"]]
    ms = ms[["fixture_id", "home_xg", "away_xg"]].dropna(subset=["home_xg", "away_xg"])
    fx["date"] = pd.to_datetime(fx["date_utc"]).dt.date
    print(f"   fixtures FT: {len(fx)}, xg有值: {len(ms)}")

    # 索引: (home_id, away_id) -> date -> fixture
    ms_map = dict(zip(ms["fixture_id"], zip(ms["home_xg"], ms["away_xg"])))
    fx_by_pair = {}
    for r in fx.itertuples():
        fx_by_pair.setdefault((int(r.home_team_id), int(r.away_team_id)), []).append(r)

    print("4) 匹配 ...")
    rows, matched = [], 0
    for r in df.itertuples():
        hid, aid = name2id.get(str(r.HomeTeam)), name2id.get(str(r.AwayTeam))
        if hid is None or aid is None:
            rows.append(None)
            continue
        cands = fx_by_pair.get((hid, aid), [])
        hit = None
        for f in cands:
            if abs((f.date - r.d).days) <= 1:
                hit = f
                break
        if hit is None:
            rows.append(None)
            continue
        xg = ms_map.get(hit.id)
        if xg is None:
            rows.append(None)
            continue
        rows.append({"Date": r.Date, "HomeTeam": r.HomeTeam, "AwayTeam": r.AwayTeam,
                     "league": r.league, "home_xg": float(xg[0]), "away_xg": float(xg[1])})
        matched += 1

    out = df[["Date", "HomeTeam", "AwayTeam", "league"]].copy()
    out["home_xg"] = [x["home_xg"] if x else None for x in rows]
    out["away_xg"] = [x["away_xg"] if x else None for x in rows]
    out["date"] = df["d"]
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"5) 写入 {args.out}")
    print(f"   匹配率: {matched}/{len(df)} = {matched/len(df):.1%}")
    cov = out["home_xg"].notna()
    print(f"   分联赛覆盖率:")
    print(out.loc[cov, "league"].value_counts().to_string())
    print(f"   按年覆盖率:")
    y = pd.to_datetime(out.loc[cov, "date"])
    print(y.dt.year.value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()