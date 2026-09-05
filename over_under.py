# -*- coding: utf-8 -*-
"""大小球 2.5 建模与回测(1X2 之外的新市场)。

- 模型: 独立泊松 λ_h/λ_a(由 poisson_fit 攻防强度估计), 总进球分布
  P(total=k) = Σ_{i=0..k} P_h(i)·P_a(k-i), P(over2.5) = 1 - P(total<=2)
- 市场: B365>2.5 / B365<2.5 比例去水 -> 公平 P(over)
- 策略: model P - market P >= min_edge 下注; 凯利仓位; 结算按实际总进球
- 回测: 严格 walk-forward, 泊松只在训练窗 fit, 测试窗只预测+结算(防未来泄露)

用法: python football_analyzer/over_under.py           # 自检
      python football_analyzer/over_under.py backtest   # 全样本回测
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

from config import STRATEGY
from model import poisson_fit, poisson_predict
from strategy import kelly_fraction


# ---------------- 概率 ----------------

def poisson_cdf_total(lh: float, la: float, k: int) -> float:
    """P(总进球 <= k), 基于独立泊松 λ_h, λ_a。"""
    prob = 0.0
    for t in range(k + 1):
        for i in range(t + 1):
            prob += (math.exp(-lh) * lh ** i / math.factorial(i)) * \
                    (math.exp(-la) * la ** (t - i) / math.factorial(t - i))
    return float(prob)


def ou25_probs(lh: float, la: float) -> tuple[float, float]:
    """返回 (P(over2.5), P(under2.5))。"""
    p_le2 = poisson_cdf_total(lh, la, 2)
    return 1.0 - p_le2, p_le2


def market_ou25(over_odds: float, under_odds: float):
    """市场去水(比例法)。返回 (fair_p_over, fair_p_under); 赔率无效返回 None。"""
    if not over_odds or not under_odds or over_odds <= 1 or under_odds <= 1:
        return None
    qo, qu = 1.0 / over_odds, 1.0 / under_odds
    s = qo + qu
    return qo / s, qu / s


# ---------------- 策略 ----------------

def apply_ou25_strategy(df: pd.DataFrame, min_edge: float = None,
                        use_close: bool = False) -> pd.DataFrame:
    """对含 lh/la 列的比赛表生成大小球建议并结算。

    追加列: ou_edge_over/ou_edge_under/ou_stake/ou_pick(0=over,1=under,-1=None)/
            ou_odds/ou_profit
    use_close=True 用临场盘(B365C>2.5)作为市场与结算价。
    """
    min_edge = min_edge if min_edge is not None else STRATEGY["min_edge"]
    col_over = "ou25_over_close" if use_close else "ou25_over"
    col_under = "ou25_under_close" if use_close else "ou25_under"
    # reset_index 保证 iterrows 的 i 与数组位置一致(test 子集索引可能不连续)
    out = df.copy().reset_index(drop=True)
    n = len(out)
    eo = np.full(n, np.nan)
    eu = np.full(n, np.nan)
    stakes = np.zeros(n)
    picks = np.full(n, -1, dtype=int)
    odds_pick = np.full(n, np.nan)
    profits = np.full(n, np.nan)
    for i, r in out.iterrows():
        if not (np.isfinite(r.get("lh", np.nan)) and np.isfinite(r.get("la", np.nan))):
            continue
        p_over, p_under = ou25_probs(r["lh"], r["la"])
        mkt = market_ou25(r.get(col_over), r.get(col_under))
        if mkt is None:
            continue
        eo[i] = p_over - mkt[0]
        eu[i] = p_under - mkt[1]
        if eo[i] >= min_edge:
            st = kelly_fraction(p_over, r[col_over])
            if st <= 0:
                continue
            stakes[i] = st; picks[i] = 0; odds_pick[i] = r[col_over]
            total = r.get("hg", np.nan) + r.get("ag", np.nan)
            if pd.notna(total):
                profits[i] = st * (r[col_over] - 1.0) if total > 2.5 else -st
        elif eu[i] >= min_edge:
            st = kelly_fraction(p_under, r[col_under])
            if st <= 0:
                continue
            stakes[i] = st; picks[i] = 1; odds_pick[i] = r[col_under]
            total = r.get("hg", np.nan) + r.get("ag", np.nan)
            if pd.notna(total):
                profits[i] = st * (r[col_under] - 1.0) if total <= 2.5 else -st
    out["ou_edge_over"] = eo
    out["ou_edge_under"] = eu
    out["ou_stake"] = stakes
    out["ou_pick"] = picks
    out["ou_odds"] = odds_pick
    out["ou_profit"] = profits
    return out


# ---------------- 回测 ----------------

def backtest_ou25(df: pd.DataFrame, train_days: int = 180, test_days: int = 60,
                  step_days: int = 90, min_train: int = 200, min_edge: float = None,
                  use_close: bool = False, verbose: bool = True,
                  ) -> tuple[pd.DataFrame, dict]:
    """大小球 2.5 严格 walk-forward 回测。返回 (bets_df, summary)。"""
    import datetime as dt
    min_edge = min_edge if min_edge is not None else STRATEGY["min_edge"]
    df = df[df["ou25_over"].notna() & df["ou25_under"].notna() &
            df["hg"].notna() & df["ag"].notna()].copy()
    df = df.sort_values("date").reset_index(drop=True)
    d0, d1 = df["date"].min(), df["date"].max()
    folds = []
    cutoff = d0 + dt.timedelta(days=train_days)
    while cutoff < d1:
        folds.append(cutoff)
        cutoff += dt.timedelta(days=step_days)

    all_bets = []
    per_fold = []
    for fi, cutoff in enumerate(folds):
        t_lo = cutoff - dt.timedelta(days=train_days)
        t_hi = cutoff + dt.timedelta(days=test_days)
        train = df[(df["date"] >= t_lo) & (df["date"] < cutoff)].copy()
        test = df[(df["date"] >= cutoff) & (df["date"] < t_hi)].copy()
        if len(train) < min_train or len(test) == 0:
            continue
        try:
            fit = poisson_fit(train)
        except Exception as exc:
            if verbose:
                print(f"  fold {cutoff.date()} fit 失败: {exc}")
            continue
        lams = test.apply(lambda r: poisson_predict(fit, r), axis=1)
        test = test.copy()
        test["lh"] = [x[0] for x in lams]
        test["la"] = [x[1] for x in lams]
        bets = apply_ou25_strategy(test, min_edge=min_edge, use_close=use_close)
        active = bets[bets["ou_stake"] > 0]
        n_bets = len(active)
        bank = active["ou_profit"].sum()
        staked = active["ou_stake"].sum()
        per_fold.append({"cutoff": cutoff, "n_train": len(train), "n_test": len(test),
                         "n_bets": n_bets, "profit": bank, "staked": staked})
        all_bets.append(active)
        if verbose:
            print(f"  fold {cutoff.date()} bets={n_bets} profit={bank:.2f} staked={staked:.2f}")

    if all_bets:
        bets = pd.concat(all_bets, ignore_index=True)
    else:
        bets = pd.DataFrame()
    summary = _summarize(bets, per_fold)
    return bets, summary


def _summarize(bets: pd.DataFrame, per_fold: list) -> dict:
    if bets.empty:
        return {"n_bets": 0, "roi": np.nan, "hit_rate": np.nan}
    staked = bets["ou_stake"].sum()
    profit = bets["ou_profit"].sum()
    n = len(bets)
    hits = (bets["ou_profit"] > 0).sum()
    return {
        "n_bets": n,
        "roi": profit / staked if staked > 0 else np.nan,
        "hit_rate": hits / n if n else np.nan,
        "over_n": int((bets["ou_pick"] == 0).sum()),
        "under_n": int((bets["ou_pick"] == 1).sum()),
    }


# ---------------- 自检 ----------------

def _self_test():
    # 数学: lh=la=1.5 -> total λ=3, P(total<=2) 解析核对
    lh = la = 1.5
    p_le2 = poisson_cdf_total(lh, la, 2)
    # 解析: P(total=k) = Poisson(3, k)
    from math import exp
    p_le2_exact = sum(exp(-3.0) * 3.0 ** k / math.factorial(k) for k in range(3))
    assert abs(p_le2 - p_le2_exact) < 1e-12, (p_le2, p_le2_exact)
    p_over, p_under = ou25_probs(lh, la)
    assert abs((p_over + p_under) - 1.0) < 1e-12
    # 市场去水
    mkt = market_ou25(1.9, 1.9)
    assert mkt is not None and abs(mkt[0] - 0.5) < 1e-9
    mkt2 = market_ou25(2.0, 1.7)
    assert abs(mkt2[0] + mkt2[1] - 1.0) < 1e-12
    assert market_ou25(None, 1.9) is None
    # 结算: 构造两场, 一场 over 中一场 under 中
    import pandas as pd
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "league": ["T", "T"], "home": ["A", "C"], "away": ["B", "D"],
        "hg": [3, 1], "ag": [0, 0],      # 3球 -> over; 1球 -> under
        "lh": [2.0, 1.0], "la": [1.0, 1.0],
        "ou25_over": [1.9, 1.9], "ou25_under": [1.9, 1.9],
    })
    out = apply_ou25_strategy(df, min_edge=0.0)
    # 场1: p_over=P(total>2.5 | λ=3)=0.5768, 市场0.5, edge>0 -> 下 over 且中
    r0 = out.iloc[0]
    assert r0["ou_pick"] == 0 and r0["ou_profit"] > 0, (r0["ou_pick"], r0["ou_profit"])
    # 场2: p_over=P(total>2.5 | λ=2)=0.323, edge_under>0 -> 下 under 且中
    r1 = out.iloc[1]
    assert r1["ou_pick"] == 1 and r1["ou_profit"] > 0, (r1["ou_pick"], r1["ou_profit"])
    print("== over_under 自检通过 ==")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "backtest":
        from data_loader import load_master
        import time
        np.random.seed(42)
        t0 = time.time()
        df = load_master(include_espn=False)
        print(f"加载 {len(df)} 场")
        bets, s = backtest_ou25(df, verbose=True)
        print(f"\n== 大小球2.5 回测结果 ==\nn_bets={s['n_bets']} roi={s['roi']:.2%} "
              f"hit={s['hit_rate']:.1%} over={s['over_n']} under={s['under_n']} "
              f"({time.time()-t0:.0f}s)")
        return 0
    _self_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
