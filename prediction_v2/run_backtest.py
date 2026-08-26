"""回测 CLI：
  python run_backtest.py [--model poisson|xgb|lgb] [--edge 0.03] [--out output/xxx]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd

from src.data_loader import load_football_data_xg
from src.features import build_features
from src.backtest import run_backtest
from src.evaluate import summarize, print_report, save_report

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 路径转绝对
    cfg["data"]["football_dir"] = os.path.normpath(
        os.path.join(HERE, cfg["data"]["football_dir"]))
    return cfg


def main():
    ap = argparse.ArgumentParser(description="prediction_v2 无泄漏回测")
    ap.add_argument("--model", default="poisson", choices=["poisson", "xgb", "lgb", "cat"])
    ap.add_argument("--target", default="1x2", choices=["1x2", "ou"],
                    help="ML训练目标: 1x2(默认) | ou(大小球2.5二分类)")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    ap.add_argument("--edge", type=float, default=None, help="覆盖各市场边际")
    ap.add_argument("--xg-blend", type=float, default=None,
                    help="进球与xG强度混合权重(0~1, 如0.5), 覆盖 config.model.xg_blend")
    ap.add_argument("--only-xg", action="store_true",
                    help="只回测有逐场xG的比赛(同口径对比xG效果用)")
    ap.add_argument("--extra-features", nargs="*", choices=["tech", "sos"], default=None,
                    help="ML扩展特征(旧系统移植): tech=射门/射正/角球/犯规滚动, sos=对手强度调整攻防")
    ap.add_argument("--market", default=None, choices=["1x2", "ou", "ah"],
                    help="只回测单一市场")
    ap.add_argument("--out", default=None, help="输出目录")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.edge:
        for k in cfg["markets"]:
            if k.startswith("edge_"):
                cfg["markets"][k] = args.edge
    if args.xg_blend is not None:
        cfg["model"]["xg_blend"] = args.xg_blend
    if args.extra_features:
        cfg["model"]["extra_ml_features"] = args.extra_features
    out_dir = args.out or os.path.join(HERE, "output")
    os.makedirs(out_dir, exist_ok=True)

    print("1) 加载数据...")
    xg_cache = os.path.normpath(os.path.join(HERE, cfg["data"].get("xg_cache", "xg_cache.csv")))
    df = load_football_data_xg(cfg["data"]["football_dir"], xg_cache=xg_cache,
                               min_date=cfg["data"].get("min_date"),
                               max_date=cfg["data"].get("max_date"))
    if "home_xg" in df.columns:
        print(f"   xG 覆盖: {df['home_xg'].notna().sum()}/{len(df)} = {df['home_xg'].notna().mean():.1%}")
        if args.only_xg:
            df = df[df["home_xg"].notna()].reset_index(drop=True)
            print(f"   仅保留有xG: {len(df)} 场")
    leagues = cfg["data"].get("leagues") or []
    if leagues:
        df = df[df["league"].isin(leagues)]
    print(f"   {len(df)} 场比赛, {df['Date'].min().date()} -> {df['Date'].max().date()}")

    print("2) 构建无泄漏特征...")
    feat = build_features(df, cfg["features"])
    print(f"   特征完成: {len(feat)} 行 x {feat.shape[1]} 列")

    if args.market:
        for k in list(cfg["markets"]):
            if k.startswith("edge_") and k != f"edge_{args.market}":
                cfg["markets"][k] = 1.0  # 屏蔽其他市场
    print(f"3) 回测 (model={args.model}, market={args.market or 'all'})...")
    res = run_backtest(feat, cfg, model_type=args.model, target=args.target)

    print("4) 评估...")
    report = summarize(res["bets"], res["preds"], cfg)
    print_report(report)

    tag = f"{args.model}_{args.target}_{args.market or 'all'}_edge{args.edge if args.edge is not None else 'cfg'}"
    if args.xg_blend is not None:
        tag += f"_xg{args.xg_blend}"
    if args.only_xg:
        tag += "_onlyxg"
    extra = list(cfg.get("model", {}).get("extra_ml_features", []))
    if extra:
        tag += "_tf" + "_".join(sorted(extra))
    save_report(report, os.path.join(out_dir, f"report_{tag}.json"))
    if len(res["bets"]):
        res["bets"].to_csv(os.path.join(out_dir, f"bets_{tag}.csv"), index=False)
    res["preds"].to_csv(os.path.join(out_dir, f"preds_{tag}.csv"), index=False)
    print(f"\n已保存: {out_dir}/report_{tag}.json")


if __name__ == "__main__":
    main()
