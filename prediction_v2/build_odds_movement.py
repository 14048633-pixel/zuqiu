"""由快照历史生成 初盘->临场 变化特征表
================================================
用法:
  python build_odds_movement.py [--bookmaker pinnacle] [--out output/odds_snapshots/movement.csv]

输入: output/odds_snapshots/snapshots.csv（fetch_live_odds.py 追加）
输出: output/odds_snapshots/movement.csv（每场一行: first/last/move）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.live_odds import (load_snapshots, movement_table, judge_text,
                           snapshots_path)

HERE = os.path.dirname(os.path.abspath(__file__))


def h2k(v):
    try:
        v = float(v)
        return f"{v:.1f}h" if v >= 1 else f"{v*60:.0f}min"
    except (TypeError, ValueError):
        return "?"


def main():
    ap = argparse.ArgumentParser(description="生成 初盘->临场 变化表")
    ap.add_argument("--bookmaker", default="pinnacle")
    ap.add_argument("--in", dest="inp", default=snapshots_path(HERE))
    ap.add_argument("--out", default=os.path.join(HERE, "output", "odds_snapshots", "movement.csv"))
    ap.add_argument("--min-snapshots", type=int, default=2)
    args = ap.parse_args()

    df = load_snapshots(args.inp)
    if df.empty:
        print("❌ 快照为空或文件不存在:", args.inp)
        print("   先运行 python fetch_live_odds.py 抓取。")
        sys.exit(1)
    mv = movement_table(df, bookmakers=(args.bookmaker,))
    mv = mv[mv["n_snapshots"] >= args.min_snapshots].reset_index(drop=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    mv.to_csv(args.out, index=False)
    print(f"✔ 变化表已保存: {args.out}  ({len(mv)} 场, 至少 {args.min_snapshots} 份快照)")
    if mv.empty:
        print("   尚无满足条件的场次（每场至少 2 份快照才能算变化）。")
        return
    for _, r in mv.head(10).iterrows():
        print(f"  {r.get('home_team')} vs {r.get('away_team')} "
              f"[{r.get('league')}] 快照x{r.get('n_snapshots')} "
              f"距开赛{h2k(r.get('hours_to_kickoff_last'))}")
        print(f"      {judge_text(r, args.bookmaker)}")


if __name__ == "__main__":
    main()
