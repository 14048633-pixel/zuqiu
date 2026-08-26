"""构建球队映射字典 teams_map.json
=================================================
用途：统一多源队名，支撑 xG/赔率流等新数据接入。
连接键：football-data 队名(HomeTeam/AwayTeam) <-> soccer-dataset teams.parquet 的 fd_name/name。
用法：python build_teams_map.py [--out prediction_v2/teams_map.json]
"""
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd

from src.data_loader import load_football_data


def norm(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return str(s).strip().lower().replace("-", " ").replace(".", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "teams_map.json"))
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    data_dir = os.path.normpath(os.path.join(HERE, cfg["data"]["football_dir"]))
    print("1) 加载 football-data ...")
    df = load_football_data(data_dir, min_date=cfg["data"].get("min_date"),
                            max_date=cfg["data"].get("max_date"))
    fd_teams = defaultdict(set)
    for _, r in df.iterrows():
        fd_teams[str(r["league"])].add(str(r["HomeTeam"]).strip())
        fd_teams[str(r["league"])].add(str(r["AwayTeam"]).strip())
    all_fd = sorted({t for v in fd_teams.values() for t in v})
    print(f"   football-data 球队: {len(all_fd)}")

    print("2) 加载 soccer-dataset teams.parquet ...")
    tq_path = os.path.normpath(os.path.join(HERE, cfg["data"].get("soccer_teams", "../data/raw/soccer-dataset/teams.parquet")))
    teams = pd.read_parquet(tq_path)
    by_fd = {}
    by_name = {}
    for _, r in teams.iterrows():
        rec = {
            "soccer_id": int(r["id"]),
            "soccer_name": str(r["name"]),
            "fd_name": str(r["fd_name"]) if r.get("fd_name") and not pd.isna(r["fd_name"]) else None,
            "api_football_id": int(r["api_football_id"]) if r.get("api_football_id") and not pd.isna(r["api_football_id"]) else None,
        }
        if r.get("fd_name") and not pd.isna(r["fd_name"]):
            by_fd[norm(r["fd_name"])] = rec
        if r.get("name") and not pd.isna(r["name"]):
            by_name.setdefault(norm(r["name"]), rec)
    print(f"   soccer-dataset 球队: {len(teams)}")

    matched, unmatched = {}, []
    for t in all_fd:
        n = norm(t)
        hit = by_fd.get(n)
        if hit is None:
            hit = by_name.get(n)
        if hit is not None:
            matched[t] = hit
        else:
            unmatched.append(t)

    out = {
        "version": "2026-08-13",
        "source": "football-data.co.uk (matches_2015_2025 + recent) <-> soccer-dataset teams.parquet",
        "join_key": "football-data HomeTeam/AwayTeam == teams.fd_name/name (归一化: 小写/去连字符)",
        "football_data_teams_by_league": {k: sorted(v) for k, v in fd_teams.items()},
        "football_data_to_soccer": matched,
        "unmatched": unmatched,
        "stats": {
            "fd_total": len(all_fd),
            "matched": len(matched),
            "unmatched": len(unmatched),
            "match_rate": round(len(matched) / max(len(all_fd), 1), 4),
        },
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"3) 写入 {args.out}")
    print(f"   匹配率: {out['stats']['matched']}/{out['stats']['fd_total']} = {out['stats']['match_rate']:.1%}")
    print(f"   未匹配({len(unmatched)}): {unmatched[:20]}")


if __name__ == "__main__":
    main()