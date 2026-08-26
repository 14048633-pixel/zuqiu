"""生成联赛基准数据表（联赛场均进球 + 强弱联赛校正系数）。

口径（与 features.build_league_baselines 一致）：
  - 场均进球：主/客/总进球（按 联赛 x 赛季，欧洲跨年赛季口径）
  - 强弱联赛校正系数：
      scoring_idx  = 该联赛场均总进球 / 全部联赛同期场均总进球（进球环境）
      strength_idx = 该联赛平均Elo / 1500（整体水平）

用法:
  python build_league_baselines.py [--out output/league_baselines.csv]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml

from src.data_loader import load_football_data_xg
from src.features import build_features, build_league_baselines

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="联赛基准数据表")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    ap.add_argument("--out", default=os.path.join(HERE, "output", "league_baselines.csv"))
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    data_dir = os.path.normpath(os.path.join(HERE, cfg["data"]["football_dir"]))
    xg_cache = os.path.normpath(os.path.join(HERE, cfg["data"].get("xg_cache", "xg_cache.csv")))

    print("加载数据...")
    df = load_football_data_xg(data_dir, xg_cache=xg_cache,
                               min_date=cfg["data"].get("min_date"),
                               max_date=cfg["data"].get("max_date"))
    print(f"  {len(df)} 场比赛, {df['Date'].min().date()} -> {df['Date'].max().date()}")
    print("构建特征(取Elo强度)...")
    feat = build_features(df, cfg["features"])
    out = build_league_baselines(df, feat)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"已保存: {args.out} ({len(out)} 行)")

    summary = (out.groupby("league")
               .agg(seasons=("season", "count"),
                    avg_total=("avg_total_goals", "mean"),
                    over25=("over25_rate", "mean"),
                    avg_elo=("avg_elo", "mean"),
                    scoring_idx=("scoring_idx", "mean"),
                    strength_idx=("strength_idx", "mean"))
               .round(3).sort_values("avg_elo", ascending=False))
    pd = __import__("pandas")
    print("\n联赛基准汇总（跨赛季均值, 按平均Elo降序）:")
    print(summary.to_string())


if __name__ == "__main__":
    main()
