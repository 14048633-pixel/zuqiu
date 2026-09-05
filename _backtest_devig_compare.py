# -*- coding: utf-8 -*-
"""P1 回测: Shin vs 简单归一(proportional) 在 walk-forward 上的 ROI/命中/校准对比.
用法: python _backtest_devig_compare.py [--method shin|proportional]
"""
import sys, io, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\发家致富\football_analyzer')
import os
os.chdir(r'D:\发家致富\football_analyzer')

from data_loader import load_master
from features import build_features
from backtest import walk_forward

def fmt_summary(s):
    by_year = s.get("by_year")
    yrs = ""
    if by_year is not None and not by_year.empty:
        yrs = " | 分年ROI: " + ", ".join(
            "%s:%+.1f%%(%d注)" % (str(y), r["roi"]*100 if r["roi"]==r["roi"] else 0, r["bets"])
            for y, r in by_year.iterrows())
    cal = s.get("calibration")
    ece = ""
    if cal is not None and not cal.empty and hasattr(cal, "attrs") and "ece" in cal.attrs:
        ece = " | ECE=%.4f" % cal.attrs["ece"]
    return ("n=%d ROI=%+.2f%% 命中=%.2f%% avg_edge=%+.3f 最大回撤=%.2f%s%s"
            % (s["n_bets"], s["roi"]*100, s["hit_rate"]*100, s["avg_edge"], s["max_drawdown"], ece, yrs))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="shin", choices=["shin", "proportional"])
    ap.add_argument("--min_edge", type=float, default=None)
    ap.add_argument("--margin-min", type=float, default=0.0,
                    help="只保留 margin>=该值(1/odds 和 -1)的场, 聚焦大 margin 子集")
    args = ap.parse_args()

    print("加载 master + 构建特征...")
    master = load_master(include_espn=False)
    master = master[master["odds_h"].notna()].copy()
    if args.margin_min > 0:
        m = (1.0 / master["odds_h"] + 1.0 / master["odds_d"] + 1.0 / master["odds_a"]) - 1.0
        before = len(master)
        master = master[m >= args.margin_min].copy()
        print("margin>=%.2f 过滤: %d -> %d 场" % (args.margin_min, before, len(master)))
    print("master:", len(master), "场; 构建特征...")
    master = build_features(master)
    print("特征完成; walk-forward 180/60/120 (method=%s)..." % args.method)
    kw = dict(train_days=180, test_days=60, step_days=120, min_train=300,
              use_calibration=True, verbose=True)
    if args.min_edge is not None:
        kw["min_edge"] = args.min_edge
    bets, summary = walk_forward(master, devig_method=args.method, **kw)
    print("== method=%s 回测汇总 ==" % args.method)
    print(fmt_summary(summary))
