# -*- coding: utf-8 -*-
"""全样本分联赛/分场景 ROI 诊断。

目的: 总体回测只有 ROI -16.56%, 不知道亏在哪。本脚本用全样本(非 head(4000))
跑 walk-forward, 按联赛/年份/方向/edge区间/odds区间分解, 回答:
  1. 哪些联赛纯亏(砍) / 哪些接近持平(集中实盘验证) / 哪些有微弱正 edge
  2. 模型在哪些场景(热门/冷门/主胜/客胜)还有一点信息
  3. Codex 接入实时盘口时应优先覆盖哪些联赛

用法: python football_analyzer/_diagnose_leagues.py
产出: 控制台表格 + football_analyzer/league_diagnosis.csv
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from config import DIV_CN
from data_loader import load_master
from features import build_features
from backtest import walk_forward

OUT_CSV = Path(__file__).resolve().parent / "league_diagnosis.csv"


def stat(sub: pd.DataFrame) -> dict:
    if sub is None or len(sub) == 0:
        return {"n": 0, "stake": 0.0, "profit": 0.0, "roi": None, "hit": None}
    st = float(sub["stake"].sum())
    pft = float(sub["profit"].sum())
    return {
        "n": len(sub),
        "stake": round(st, 1),
        "profit": round(pft, 2),
        "roi": round(pft / st, 4) if st > 0 else None,
        "hit": round(float((sub["profit"] > 0).mean()), 3),
    }


def fmt(s: dict) -> str:
    if s["n"] == 0 or s["roi"] is None:
        return f"n={s['n']} 无注"
    return (f"n={s['n']:<5} roi={s['roi']:>+7.2%} hit={s['hit']:.1%} "
            f"stake={s['stake']:>8.0f} profit={s['profit']:>+9.0f}")


if __name__ == "__main__":
    t0 = time.time()
    np.random.seed(42)
    df = load_master(include_espn=False)
    df = df[df["odds_h"].notna()].copy()
    print(f"加载 {len(df)} 场, 时间 {df['date'].min().date()} ~ {df['date'].max().date()}")
    feat = build_features(df)
    print(f"特征构建完成 ({time.time()-t0:.0f}s)")
    bets, summary = walk_forward(feat, train_days=180, test_days=60, step_days=90,
                                 min_train=200, use_calibration=True, verbose=False)
    print(f"回测完成: {summary['n_bets']} 注 ROI={summary['roi']:.2%} "
          f"hit={summary['hit_rate']:.1%} ({time.time()-t0:.0f}s)")
    active = bets[bets["stake"] > 0].copy()
    active["year"] = active["date"].dt.year
    active["league_cn"] = active["league"].map(DIV_CN).fillna(active["league"])

    rows = []

    def _add(group: str, key, sub: pd.DataFrame):
        s = stat(sub)
        s["group"] = group
        s["key"] = key
        rows.append(s)
        return s

    # ---- 分联赛 ----
    print("\n===== 1. 分联赛 (按注数排序) =====")
    lg_rows = []
    for league, sub in active.groupby("league_cn"):
        lg_rows.append((league, stat(sub)))
    lg_rows.sort(key=lambda x: -x[1]["n"])
    for league, s in lg_rows:
        print(f"{league:<8} {fmt(s)}")
        _add("league", league, active[active["league_cn"] == league])

    # ---- 按年份 ----
    print("\n===== 2. 按年份 =====")
    for y, sub in active.groupby("year"):
        print(f"{y}  {fmt(stat(sub))}")
        _add("year", str(y), sub)

    # ---- 按方向 ----
    print("\n===== 3. 按推荐方向 =====")
    for pidx, name in [(0, "主胜"), (1, "平局"), (2, "客胜")]:
        print(f"{name}  {fmt(stat(active[active['pick'] == pidx]))}")
        _add("pick", name, active[active["pick"] == pidx])

    # ---- 按 edge 区间 ----
    print("\n===== 4. 按 edge 区间 =====")
    bins = [(0.03, 0.05), (0.05, 0.08), (0.08, 0.12), (0.12, 1.0)]
    for lo, hi in bins:
        sub = active[(active["edge"] >= lo) & (active["edge"] < hi)]
        print(f"edge {lo:.2f}-{hi:.2f}  {fmt(stat(sub))}")
        _add("edge", f"{lo:.2f}-{hi:.2f}", sub)

    # ---- 按赔率区间(热门/中等/冷门) ----
    print("\n===== 5. 按下注赔率区间 =====")
    odds_bins = [(1.0, 1.8, "热门<1.8"), (1.8, 2.6, "中等1.8-2.6"), (2.6, 3.5, "偏高2.6-3.5"), (3.5, 99, "冷门>3.5")]
    for lo, hi, label in odds_bins:
        sub = active[(active["odds_pick"] >= lo) & (active["odds_pick"] < hi)]
        print(f"{label}  {fmt(stat(sub))}")
        _add("odds", label, sub)

    # ---- 汇总 + 落 CSV ----
    out = pd.DataFrame(rows)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\nCSV 已保存: {OUT_CSV}")
    print(f"总耗时 {time.time()-t0:.0f}s")
