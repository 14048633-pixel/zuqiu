# -*- coding: utf-8 -*-
"""开盘 vs 收盘价结算对照: 量化"回测(开盘价) vs 实盘可成交价(临场价)"的差异。

背景: 回测默认按开盘价(B365H)结算, 但实盘拿不到开盘价、只能按临场/收盘价成交,
这可能是"回测 vs 实盘"偏差的来源之一。本脚本在"有收盘价"的样本上,
用同一批下注分别按开盘价/收盘价结算, 对比 ROI。

用法: python football_analyzer/_backtest_settle_compare.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from data_loader import load_master
from features import build_features
from backtest import walk_forward

if __name__ == "__main__":
    t0 = time.time()
    df = load_master(include_espn=False)
    # 只保留收盘价完整且有开盘价的样本(足彩网覆盖段), 保证 open/close 可直接对比
    df = df[df["odds_h_close"].notna() & df["odds_h"].notna()].copy()
    print(f"有收盘价样本 {len(df)} 场, 时间范围 {df['date'].min().date()} ~ {df['date'].max().date()}")
    df = build_features(df)
    np.random.seed(42)
    results = {}
    for settle in ["open", "close"]:
        bets, s = walk_forward(df, train_days=180, test_days=60, step_days=90,
                               min_train=200, use_calibration=True, verbose=False,
                               settle=settle)
        results[settle] = s
        print(f"[{settle}结算] n_bets={s['n_bets']} roi={s['roi']:.2%} "
              f"hit={s.get('hit_rate'):.1%} ({time.time()-t0:.1f}s)")
    if results["open"]["n_bets"] and results["close"]["n_bets"]:
        d = (results["close"]["roi"] - results["open"]["roi"]) * 100
        print(f"\n== 结论 ==\n收盘价结算 ROI {results['close']['roi']:.2%} vs "
              f"开盘价 {results['open']['roi']:.2%} -> 差 {d:+.2f}pp")
        print("(负值 = 临场价水位更差, 实盘按临场价成交会侵蚀回测收益)")
