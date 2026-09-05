# -*- coding: utf-8 -*-
"""组合切面补充分析: 找最有利场景是否可能接近正。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from data_loader import load_master
from features import build_features
from backtest import walk_forward


def st(sub):
    if len(sub) == 0:
        return "无注"
    st_ = sub["stake"].sum()
    pft = sub["profit"].sum()
    return f"n={len(sub)} roi={pft/st_:+.2%} hit={(sub['profit']>0).mean():.1%}"


if __name__ == "__main__":
    np.random.seed(42)
    df = load_master(include_espn=False)
    df = df[df["odds_h"].notna()].copy()
    feat = build_features(df)
    bets, s = walk_forward(feat, train_days=180, test_days=60, step_days=90,
                           min_train=200, use_calibration=True, verbose=False)
    a = bets[bets["stake"] > 0].copy()
    print("主胜&热门<2.0     :", st(a[(a["pick"] == 0) & (a["odds_pick"] < 2.0)]))
    print("主胜&edge<0.08    :", st(a[(a["pick"] == 0) & (a["edge"] < 0.08)]))
    print("主胜&edge<0.08&热门:", st(a[(a["pick"] == 0) & (a["edge"] < 0.08) & (a["odds_pick"] < 2.0)]))
    print("热门<1.8&edge<0.08:", st(a[(a["odds_pick"] < 1.8) & (a["edge"] < 0.08)]))
    pool = ["F2", "D2", "F1", "AUT"]
    print("微正池(F2/D2/F1/AUT):", st(a[a["league"].isin(pool)]))
    print("  其中主胜          :", st(a[a["league"].isin(pool) & (a["pick"] == 0)]))
    # 主胜 & 微正池
    print("微正池&主胜         :", st(a[a["league"].isin(pool) & (a["pick"] == 0)]))
