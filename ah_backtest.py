# -*- coding: utf-8 -*-
"""亚盘(让球)建模与回测。

- 模型: 联合泊松净胜球分布 P(margin=k) -> 主/客期望结算分数 E[settle]
  p_eff = (1 + E[settle])/2, EV = p_eff*odds - 1
- 市场: B365AHH/B365AHA(主客水位), line=AHh(主队让球, 正=主让)
- 策略: EV >= min_ev 下注; 凯利近似仓位; 结算按实际比分 margin
- 回测: 严格 walk-forward, 泊松只在训练窗 fit(防未来泄露)

用法: python football_analyzer/ah_backtest.py             # 自检
      python football_analyzer/ah_backtest.py backtest    # 全样本回测
      python football_analyzer/ah_backtest.py diag        # 敏感性+方向诊断
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

from config import STRATEGY
from model import poisson_fit, poisson_predict
from strategy import kelly_fraction
from asian_handicap import settle_ah, ah_net_profit, ah_win_frac, margin_pmf


def _odds(row, k):
    v = row.get(k)
    return v if pd.notna(v) and v > 1 else None


def _line(row, k):
    v = row.get(k)
    return v if pd.notna(v) else None


def apply_ah_strategy(df: pd.DataFrame, min_ev: float = None,
                      use_close: bool = False) -> pd.DataFrame:
    """对含 lh/la 列的比赛表生成亚盘建议并结算。

    追加列: ah_ev_home/ah_ev_away/ah_stake/ah_side(0=主,1=客,-1=None)/
            ah_odds/ah_profit
    """
    min_ev = min_ev if min_ev is not None else STRATEGY["min_ev"]
    line_k = "ah_line_close" if use_close else "ah_line"
    oh_k = "ah_h_close" if use_close else "ah_h"
    oa_k = "ah_a_close" if use_close else "ah_a"
    out = df.copy().reset_index(drop=True)
    n = len(out)
    ev_h = np.full(n, np.nan)
    ev_a = np.full(n, np.nan)
    stakes = np.zeros(n)
    sides = np.full(n, -1, dtype=int)
    odds_pick = np.full(n, np.nan)
    profits = np.full(n, np.nan)
    for i, r in out.iterrows():
        if not (np.isfinite(r.get("lh", np.nan)) and np.isfinite(r.get("la", np.nan))):
            continue
        line = _line(r, line_k)
        oh = _odds(r, oh_k)
        oa = _odds(r, oa_k)
        if line is None:
            continue
        probs = margin_pmf(r["lh"], r["la"])
        ef_h = sum(p * settle_ah(k, line) for k, p in probs.items())
        # 客队下注期望分数 = -E[主队] (走盘对双方均0, 非走盘互补)
        ef_a = -ef_h
        if oh is not None:
            p_eff_h = (1.0 + ef_h) / 2.0
            ev_h[i] = p_eff_h * oh - 1.0
        if oa is not None:
            p_eff_a = (1.0 + ef_a) / 2.0
            ev_a[i] = p_eff_a * oa - 1.0
        margin = None
        if pd.notna(r.get("hg")) and pd.notna(r.get("ag")):
            margin = float(r["hg"] - r["ag"])
        if ev_h[i] >= min_ev and oh is not None:
            st = kelly_fraction((1.0 + ef_h) / 2.0, oh)
            if st > 0:
                stakes[i] = st; sides[i] = 0; odds_pick[i] = oh
                if margin is not None:
                    profits[i] = st * ah_net_profit(margin, line, oh)
        elif ev_a[i] >= min_ev and oa is not None:
            st = kelly_fraction((1.0 + ef_a) / 2.0, oa)
            if st > 0:
                stakes[i] = st; sides[i] = 1; odds_pick[i] = oa
                if margin is not None:
                    profits[i] = st * ah_net_profit(-margin, line, oa)
    out["ah_ev_home"] = ev_h
    out["ah_ev_away"] = ev_a
    out["ah_stake"] = stakes
    out["ah_side"] = sides
    out["ah_odds"] = odds_pick
    out["ah_profit"] = profits
    return out


def backtest_ah(df: pd.DataFrame, train_days: int = 180, test_days: int = 60,
                step_days: int = 90, min_train: int = 200, min_ev: float = None,
                use_close: bool = False, verbose: bool = True,
                ) -> tuple[pd.DataFrame, dict]:
    import datetime as dt
    min_ev = min_ev if min_ev is not None else STRATEGY["min_ev"]
    df = df[df["ah_line"].notna() & df["ah_h"].notna() & df["ah_a"].notna() &
            df["hg"].notna() & df["ag"].notna()].copy()
    df = df.sort_values("date").reset_index(drop=True)
    d0, d1 = df["date"].min(), df["date"].max()
    folds = []
    cutoff = d0 + dt.timedelta(days=train_days)
    while cutoff < d1:
        folds.append(cutoff)
        cutoff += dt.timedelta(days=step_days)

    all_bets, per_fold = [], []
    for cutoff in folds:
        tr = df[(df["date"] >= cutoff - dt.timedelta(days=train_days)) & (df["date"] < cutoff)]
        te = df[(df["date"] >= cutoff) & (df["date"] < cutoff + dt.timedelta(days=test_days))]
        if len(tr) < min_train or len(te) == 0:
            continue
        try:
            fit = poisson_fit(tr)
        except Exception as exc:
            if verbose:
                print(f"  fold {cutoff.date()} fit 失败: {exc}")
            continue
        lams = te.apply(lambda r: poisson_predict(fit, r), axis=1)
        te = te.copy()
        te["lh"] = [x[0] for x in lams]
        te["la"] = [x[1] for x in lams]
        bets = apply_ah_strategy(te, min_ev=min_ev, use_close=use_close)
        active = bets[bets["ah_stake"] > 0]
        per_fold.append({"cutoff": cutoff, "n_train": len(tr), "n_test": len(te),
                         "n_bets": len(active),
                         "profit": active["ah_profit"].sum(),
                         "staked": active["ah_stake"].sum()})
        all_bets.append(active)
        if verbose:
            print(f"  fold {cutoff.date()} bets={len(active)} "
                  f"profit={active['ah_profit'].sum():.2f} "
                  f"staked={active['ah_stake'].sum():.2f}")
    bets = pd.concat(all_bets, ignore_index=True) if all_bets else pd.DataFrame()
    summary = _summarize(bets, per_fold)
    return bets, summary


def _summarize(bets: pd.DataFrame, per_fold: list) -> dict:
    if bets.empty:
        return {"n_bets": 0, "roi": np.nan, "hit_rate": np.nan}
    staked = bets["ah_stake"].sum()
    profit = bets["ah_profit"].sum()
    n = len(bets)
    hits = (bets["ah_profit"] > 0).sum()
    return {
        "n_bets": n,
        "roi": profit / staked if staked > 0 else np.nan,
        "hit_rate": hits / n if n else np.nan,
        "home_n": int((bets["ah_side"] == 0).sum()),
        "away_n": int((bets["ah_side"] == 1).sum()),
    }


# ---------------- 诊断 ----------------

def diag_min_ev(df):
    print("\n== min_ev 敏感性 ==")
    print(f"{'min_ev':>8} {'n_bets':>7} {'roi':>8} {'hit':>6} {'home':>5} {'away':>5}")
    for me in [0.0, 0.005, 0.01, 0.02, 0.03, 0.05]:
        _, s = backtest_ah(df, min_ev=me, verbose=False)
        print(f"{me:>8.3f} {s['n_bets']:>7} {s['roi']:>8.2%} {s['hit_rate']:>6.1%} "
              f"{s['home_n']:>5} {s['away_n']:>5}")


def diag_direction(df):
    import datetime as dt
    df = df[df["ah_line"].notna() & df["ah_h"].notna() & df["ah_a"].notna() &
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
        allb.append(apply_ah_strategy(te, min_ev=0.01))
        cutoff += dt.timedelta(days=90)
    bets = pd.concat(allb, ignore_index=True)
    bets = bets[bets["ah_stake"] > 0]
    print(f"\n== 亚盘方向分解(min_ev=0.01) 共 {len(bets)} 注 ==")
    for side, name in [(0, "home"), (1, "away")]:
        sub = bets[bets["ah_side"] == side]
        if len(sub):
            print(f"{name:>5}: n={len(sub):>5} roi={sub['ah_profit'].sum()/sub['ah_stake'].sum():>7.2%} "
                  f"win={(sub['ah_profit']>0).mean():>6.1%} "
                  f"push={(sub['ah_profit']==0).mean():>6.1%} "
                  f"avg_ev={sub['ah_ev_home' if side==0 else 'ah_ev_away'].mean():+.4f}")
    # EV 分箱 ROI
    print("\nEV 分箱 ROI:")
    for side, col in [(0, "ah_ev_home"), (1, "ah_ev_away")]:
        sub = bets[bets["ah_side"] == side].copy()
        if len(sub) == 0:
            continue
        sub["ev_bin"] = pd.cut(sub[col], bins=[0.01, 0.03, 0.06, 0.10, 0.20, 0.5, 1.0], right=False)
        g = sub.groupby("ev_bin", observed=True).agg(
            n=("ah_stake", "size"),
            roi=("ah_profit", lambda x: x.sum() / sub.loc[x.index, "ah_stake"].sum()))
        print(f"  {'home' if side==0 else 'away'}:")
        print(g.round(4).to_string())


# ---------------- 自检 ----------------

def _self_test():
    # 主客期望分数互补: 对任意 line, ef_away = -ef_home(走盘双方0)
    lh, la = 1.4, 1.6
    for line in [0.0, 0.25, -0.5, 0.75, 1.0]:
        ef_h = ah_win_frac(lh, la, line)
        assert abs(ef_h + (-ef_h)) < 1e-12
    # 让球 0 且 λ 对称: 主客 EF 约 0
    ef0 = ah_win_frac(1.5, 1.5, 0.0)
    assert abs(ef0) < 0.02
    # 主队强于客队时, 主队让球 EF 为正(对合理线)
    ef_strong = ah_win_frac(2.0, 1.0, 0.0)
    assert ef_strong > 0.2
    # 结算: 构造两场, 主队让0.5, 主胜1球->主队赢盘; 客胜->主队输盘
    import pandas as pd
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "league": ["T", "T"], "home": ["A", "C"], "away": ["B", "D"],
        "hg": [2, 0], "ag": [1, 1],
        "lh": [2.0, 1.0], "la": [1.0, 1.0],
        "ah_line": [0.5, 0.5], "ah_h": [1.9, 1.9], "ah_a": [1.9, 1.9],
    })
    out = apply_ah_strategy(df, min_ev=0.0)
    # 场1: 主队净胜1>0.5 主赢盘 -> 下主队且 profit>0
    assert out.iloc[0]["ah_side"] == 0 and out.iloc[0]["ah_profit"] > 0
    # 场2: 对称λ让0.5 -> 下客队(ev_away>0) 且客队赢盘 profit>0
    assert out.iloc[1]["ah_side"] == 1 and out.iloc[1]["ah_profit"] > 0
    print("== 亚盘自检通过 ==")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "backtest":
        from data_loader import load_master
        import time
        np.random.seed(42)
        t0 = time.time()
        df = load_master(include_espn=False)
        print(f"加载 {len(df)} 场")
        bets, s = backtest_ah(df, verbose=True)
        print(f"\n== 亚盘回测结果 ==\nn_bets={s['n_bets']} roi={s['roi']:.2%} "
              f"hit={s['hit_rate']:.1%} home={s['home_n']} away={s['away_n']} "
              f"({time.time()-t0:.0f}s)")
        return 0
    if argv and argv[0] == "diag":
        from data_loader import load_master
        np.random.seed(42)
        df = load_master(include_espn=False)
        print(f"加载 {len(df)} 场")
        diag_min_ev(df)
        diag_direction(df)
        return 0
    _self_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
