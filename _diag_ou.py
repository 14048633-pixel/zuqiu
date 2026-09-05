# -*- coding: utf-8 -*-
"""大小球2.5 诊断: min_edge 敏感性 + 模型概率校准分箱 + 方向分解。
用法: python football_analyzer/_diag_ou.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data_loader import load_master
from model import poisson_fit, poisson_predict
from over_under import backtest_ou25, apply_ou25_strategy, ou25_probs, market_ou25


def diag_min_edge(df):
    print("== min_edge 敏感性(全样本 walk-forward) ==")
    print(f"{'min_edge':>9} {'n_bets':>7} {'roi':>8} {'hit':>6}")
    for me in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08]:
        _, s = backtest_ou25(df, min_edge=me, verbose=False)
        print(f"{me:>9.3f} {s['n_bets']:>7} {s['roi']:>8.2%} {s['hit_rate']:>6.1%}")


def diag_calibration(df):
    """下注样本: 模型 P(over) 分箱 vs 实际 over 率 vs 市场隐含 P(over)。"""
    print("\n== 模型 P(over) 校准(全部可下注样本) ==")
    import datetime as dt
    df = df[df["ou25_over"].notna() & df["ou25_under"].notna() &
            df["hg"].notna() & df["ag"].notna()].sort_values("date").reset_index(drop=True)
    cutoff = df["date"].min() + dt.timedelta(days=180)
    rows = []
    while cutoff < df["date"].max():
        tr = df[(df["date"] >= cutoff - dt.timedelta(days=180)) & (df["date"] < cutoff)]
        te = df[(df["date"] >= cutoff) & (df["date"] < cutoff + dt.timedelta(days=60))]
        if len(tr) < 200 or len(te) == 0:
            cutoff += dt.timedelta(days=90)
            continue
        fit = poisson_fit(tr)
        for _, r in te.iterrows():
            lh, la = poisson_predict(fit, r)
            if not (np.isfinite(lh) and np.isfinite(la)):
                continue
            p_over, _ = ou25_probs(lh, la)
            mkt = market_ou25(r["ou25_over"], r["ou25_under"])
            if mkt is None:
                continue
            rows.append({"p_over": p_over, "mkt_over": mkt[0],
                         "actual_over": 1.0 if (r["hg"] + r["ag"]) > 2.5 else 0.0})
        cutoff += dt.timedelta(days=90)
    d = pd.DataFrame(rows)
    print(f"样本 {len(d)}")
    bins = [0, 0.4, 0.5, 0.55, 0.6, 0.7, 1.0]
    d["bin"] = pd.cut(d["p_over"], bins=bins, right=False)
    g = d.groupby("bin", observed=True).agg(
        n=("actual_over", "size"), model=("p_over", "mean"),
        mkt=("mkt_over", "mean"), actual=("actual_over", "mean"))
    print(g.round(4).to_string())
    # 系统性偏差: 模型-市场 与 实际-市场
    print(f"\n模型-市场均值: {(d['p_over']-d['mkt_over']).mean():+.4f}  "
          f"实际-市场均值: {(d['actual_over']-d['mkt_over']).mean():+.4f}")
    print(f"over 实际率 {d['actual_over'].mean():.4f} vs 市场隐含 {d['mkt_over'].mean():.4f} vs 模型 {d['p_over'].mean():.4f}")


def diag_direction(df):
    print("\n== over/under 方向分解(全部下注) ==")
    import datetime as dt
    df = df[df["ou25_over"].notna() & df["ou25_under"].notna() &
            df["hg"].notna() & df["ag"].notna()].sort_values("date").reset_index(drop=True)
    cutoff = df["date"].min() + dt.timedelta(days=180)
    allb = []
    while cutoff < df["date"].max():
        tr = df[(df["date"] >= cutoff - dt.timedelta(days=180)) & (df["date"] < cutoff)]
        te = df[(df["date"] >= cutoff) & (df["date"] < cutoff + dt.timedelta(days=60))]
        if len(tr) < 200 or len(te) == 0:
            cutoff += dt.timedelta(days=90)
            continue
        fit = poisson_fit(tr)
        lams = te.apply(lambda r: poisson_predict(fit, r), axis=1)
        te = te.copy()
        te["lh"] = [x[0] for x in lams]
        te["la"] = [x[1] for x in lams]
        allb.append(apply_ou25_strategy(te, min_edge=0.02))
        cutoff += dt.timedelta(days=90)
    bets = pd.concat(allb, ignore_index=True)
    bets = bets[bets["ou_stake"] > 0]
    for pick, name in [(0, "over"), (1, "under")]:
        sub = bets[bets["ou_pick"] == pick]
        if len(sub):
            print(f"{name:>6}: n={len(sub):>5} roi={sub['ou_profit'].sum()/sub['ou_stake'].sum():>7.2%} "
                  f"hit={(sub['ou_profit']>0).mean():>6.1%} avg_edge={sub['ou_edge_over' if pick==0 else 'ou_edge_under'].mean():+.4f}")
    # edge 分箱的实际收益
    print("\nedge 分箱 ROI:")
    for pick, col in [(0, "ou_edge_over"), (1, "ou_edge_under")]:
        sub = bets[bets["ou_pick"] == pick].copy()
        if len(sub) == 0:
            continue
        sub["edge_bin"] = pd.cut(sub[col], bins=[0.02, 0.04, 0.06, 0.08, 0.12, 0.2, 1.0], right=False)
        g = sub.groupby("edge_bin", observed=True).agg(
            n=("ou_stake", "size"), roi=("ou_profit", lambda x: x.sum() / sub.loc[x.index, "ou_stake"].sum()))
        print(f"  {'over' if pick==0 else 'under'}:")
        print(g.round(4).to_string())


if __name__ == "__main__":
    np.random.seed(42)
    df = load_master(include_espn=False)
    print(f"加载 {len(df)} 场")
    diag_min_edge(df)
    diag_calibration(df)
    diag_direction(df)
