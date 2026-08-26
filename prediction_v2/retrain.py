"""增量训练/重跑脚本 —— 新赛季/新数据到位后一键重跑并归档
=================================================
用法：
  python retrain.py                          # 默认重跑 poisson, 归档到 output/archive/日期
  python retrain.py --models poisson,xgb,lgb # 模型矩阵对比
  python retrain.py --market ou --edge 0.05  # 只回测大小球, 覆盖边际

流程：加载最新数据 → 构建无泄漏特征 → 各模型 walk-forward 回测 → 归档报告/注单 → 输出对比表。
模型均为"每折重训/无状态"，无需持久化权重；重跑即增量训练。
"""
import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd
import yaml

from src.data_loader import load_football_data_xg
from src.features import build_features
from src.backtest import run_backtest
from src.evaluate import summarize, save_report


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["data"]["football_dir"] = os.path.normpath(os.path.join(HERE, cfg["data"]["football_dir"]))
    return cfg


def main():
    ap = argparse.ArgumentParser(description="prediction_v2 增量训练/重跑")
    ap.add_argument("--models", default="poisson", help="逗号分隔: poisson,xgb,lgb")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    ap.add_argument("--market", default=None, choices=["1x2", "ou", "ah"])
    ap.add_argument("--edge", type=float, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.edge:
        for k in list(cfg["markets"]):
            if k.startswith("edge_"):
                cfg["markets"][k] = args.edge
    if args.market:
        for k in list(cfg["markets"]):
            if k.startswith("edge_") and k != f"edge_{args.market}":
                cfg["markets"][k] = 1.0
    out_dir = args.out or os.path.join(HERE, "output", "archive", datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    print("1) 加载数据...")
    xg_cache = os.path.normpath(os.path.join(HERE, cfg["data"].get("xg_cache", "xg_cache.csv")))
    df = load_football_data_xg(cfg["data"]["football_dir"], xg_cache=xg_cache,
                               min_date=cfg["data"].get("min_date"),
                               max_date=cfg["data"].get("max_date"))
    leagues = cfg["data"].get("leagues") or []
    if leagues:
        df = df[df["league"].isin(leagues)]
    print(f"   {len(df)} 场, {df['Date'].min().date()} -> {df['Date'].max().date()}")

    print("2) 构建特征...")
    feat = build_features(df, cfg["features"])

    rows = []
    for m in [x.strip() for x in args.models.split(",") if x.strip()]:
        print(f"3) 回测 {m} (market={args.market or 'all'})...")
        res = run_backtest(feat, cfg, model_type=m)
        report = summarize(res["bets"], res["preds"], cfg)
        tag = f"{m}_{args.market or 'all'}_edge{args.edge if args.edge is not None else 'cfg'}"
        save_report(report, os.path.join(out_dir, f"report_{tag}.json"))
        if len(res["bets"]):
            res["bets"].to_csv(os.path.join(out_dir, f"bets_{tag}.csv"), index=False)
        b = report.get("bets", {})
        rows.append({
            "model": m, "n_bets": b.get("n"),
            "flat_roi_open": b.get("roi_flat_open"),
            "kelly_roi_open": b.get("roi_open"),
            "logloss_model": report.get("preds", {}).get("logloss_model"),
            "logloss_market": report.get("preds", {}).get("logloss_market"),
        })
        print(f"    {m}: 注数={rows[-1]['n_bets']} 平注ROI={rows[-1]['flat_roi_open']:+.2%}")

    print("\n4) 模型横向对比:")
    print(f"  {'model':<10}{'n_bets':>8}{'平注ROI@开':>12}{'凯利ROI@开':>12}{'LogLoss':>10}")
    for r in rows:
        print(f"  {r['model']:<10}{r['n_bets']:>8}{r['flat_roi_open']:>12.2%}"
              f"{r['kelly_roi_open']:>12.2%}{r['logloss_model']:>10.4f}")
    print(f"\n已归档: {out_dir}")


if __name__ == "__main__":
    main()