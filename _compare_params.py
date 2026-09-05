# -*- coding: utf-8 -*-
"""新旧参数回测对照: 验证 ELO/特征参数接线(config 生效)前后回测表现。

背景: 2026-08-28 修复前, config.FEATURES 的 form_window/h2h_window/min_matches/
decay_halflife 全部 0 引用, features.py/elo.py 内部有各自硬编码默认(长窗/慢衰减);
修复后接上 config 现值(短窗 5 场 / 半衰期 60 天)。本脚本对比两组参数的回测表现,
确认"接线后没让系统变差"。

用法: python football_analyzer/_compare_params.py
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import config
import data_loader
import backtest
import features
import elo

GROUPS = {
    # 现状(接线后): 短窗 + 快衰减
    "A_现状": {"form_window": 5, "min_matches": 3, "h2h_window": 5, "decay_halflife": 60},
    # 旧默认近似(接线前 features/elo 内部硬编码): 长窗 + 慢衰减
    "B_旧参数": {"form_window": 20, "min_matches": 3, "h2h_window": 10, "decay_halflife": 200},
}


def run_group(label: str, params: dict) -> dict:
    for k, v in params.items():
        config.FEATURES[k] = v
    # elo.HALF_LIFE 是 import 时取值, 改 config 后需 reload 才生效
    importlib.reload(elo)
    importlib.reload(features)
    t0 = time.time()
    feat = features.build_features(df)
    bets, summary = backtest.walk_forward(
        feat, train_days=180, test_days=60, step_days=90,
        min_train=200, use_calibration=True, verbose=False)
    dt_ = time.time() - t0
    out = {
        "group": label,
        **params,
        "n_bets": summary["n_bets"],
        "roi": summary["roi"],
        "hit_rate": summary.get("hit_rate"),
        "seconds": round(dt_, 1),
    }
    print(f"[{label}] n_bets={out['n_bets']} roi={out['roi']:.2%} "
          f"hit={out['hit_rate']:.1%} ({out['seconds']}s) "
          f"params={params}")
    return out


if __name__ == "__main__":
    t0 = time.time()
    df = data_loader.load_master(include_espn=False)
    df = df[df["odds_h"].notna()].head(4000).copy()
    print(f"加载 {len(df)} 场")
    results = [run_group(label, params) for label, params in GROUPS.items()]
    print("\n== 对比结论 ==")
    a = results[0]
    b = results[1]
    d_roi = (a["roi"] - b["roi"]) * 100
    print(f"现状 ROI {a['roi']:.2%} vs 旧参数 ROI {b['roi']:.2%} -> 差 {d_roi:+.2f}pp")
    print("提示: 对比为 head(4000) 同口径; 参数差异主要影响特征质量而非方向。")
