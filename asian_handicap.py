# -*- coding: utf-8 -*-
"""亚盘结算与蒙特卡洛估值。

结算约定(margin = 主队净胜球)：
  line 为整数   : 胜出>line 全赢; ==line 走盘退款; 否则全输
  line=*.25     : 拆成 n 与 n+0.5 各一半
  line=*.75     : 拆成 n+0.5 与 n+1 各一半
净收益分数 f: 全赢=+1, 全输=-1, 走盘=0, 半赢=+0.5, 半输=-0.5
"""
from __future__ import annotations

import math

import numpy as np


def settle_ah(margin: float, line: float) -> float:
    """Asian handicap settlement, return net profit fraction f in {-1,-0.5,0,0.5,1}.

    Convention: line = home handicap (positive = home gives, negative = home receives).
    Negative lines via symmetry: settle(m, L) = -settle(-m, -L).
    """
    if line is None or not np.isfinite(line):
        raise ValueError(f"bad line: {line}")
    if line < 0:
        return -settle_ah(-margin, -line)
    whole = math.floor(line + 1e-9)
    frac = round(line - whole, 2)
    if frac == 0.0:
        if margin > whole:
            return 1.0
        if margin == whole:
            return 0.0
        return -1.0
    if frac == 0.25:
        return 0.5 * settle_ah(margin, whole) + 0.5 * settle_ah(margin, whole + 0.5)
    if frac == 0.5:
        return 1.0 if margin > whole + 0.5 else -1.0
    if frac == 0.75:
        return 0.5 * settle_ah(margin, whole + 0.5) + 0.5 * settle_ah(margin, whole + 1.0)
    raise ValueError(f"bad line: {line}")


def ah_net_profit(margin: float, line: float, odds: float) -> float:
    """亚盘单注净收益(以 1 单位本金计)。odds 为亚盘水位(如 0.90 或 1.90)。"""
    f = settle_ah(margin, line)
    if f == 0:
        return 0.0
    if f > 0:
        return f * (odds - 1.0)
    return f


def ah_push_rate(lh: float, la: float, line: float, n: int = 20000,
                 seed: int | None = None) -> float:
    """蒙特卡洛估算某盘口走盘(退款)概率。"""
    rng = np.random.default_rng(seed)
    h = rng.poisson(lh, size=n)
    a = rng.poisson(la, size=n)
    push = 0
    for m in (h - a):
        if settle_ah(m, line) == 0.0:
            push += 1
    return push / n


def margin_pmf(lh: float, la: float, k_lo: int = -15, k_hi: int = 15) -> dict:
    """联合泊松净胜球分布 P(margin=k), k 取 [k_lo, k_hi]。"""
    out = {}
    for k in range(k_lo, k_hi + 1):
        s = 0.0
        for i in range(max(0, k), max(0, k) + 13):
            j = i - k
            if j < 0:
                continue
            s += (math.exp(-lh) * lh ** i / math.factorial(i)) * \
                 (math.exp(-la) * la ** j / math.factorial(j))
        out[k] = s
    return out


def ah_win_frac(lh: float, la: float, line: float) -> float:
    """解析计算期望结算分数 E[settle(margin, line)] ∈ [-1, 1]。

    等价于: P(全赢)*1 + P(半赢)*0.5 + P(走盘)*0 + P(半输)*-0.5 + P(全输)*-1。
    可用于: 亚盘公平概率 p_eff=(1+E[f])/2, 以及快速 EV 估算(替代蒙特卡洛)。
    """
    probs = margin_pmf(lh, la)
    return sum(p * settle_ah(k, line) for k, p in probs.items())


def ah_ev_analytic(lh: float, la: float, line: float, odds: float) -> float:
    """解析 EV(以 1 单位本金计), 主队下注视角。odds 为亚盘水位(英式,如 1.90)。"""
    probs = margin_pmf(lh, la)
    return sum(p * ah_net_profit(k, line, odds) for k, p in probs.items())


def ah_ev_away(lh: float, la: float, line: float, odds_a: float) -> float:
    """解析 EV(以 1 单位本金计), 客队下注视角。odds_a 为客队水位。"""
    probs = margin_pmf(lh, la)
    # 客队赢盘 = 主队视角净胜取反(margin -> -margin, 线不变)
    return sum(p * ah_net_profit(-k, line, odds_a) for k, p in probs.items())


def ah_ev(lh: float, la: float, line: float, odds: float,
          n: int = 20000, seed: int | None = None) -> float:
    """蒙特卡洛计算某亚盘投注的期望收益(单位本金)。"""
    rng = np.random.default_rng(seed)
    h = rng.poisson(lh, size=n)
    a = rng.poisson(la, size=n)
    profits = np.array([ah_net_profit(m, line, odds) for m in (h - a)])
    return float(profits.mean())


def _self_test():
    assert settle_ah(2, 1) == 1.0
    assert settle_ah(1, 1) == 0.0
    assert settle_ah(0, 1) == -1.0

    assert settle_ah(1, 0.25) == 1.0
    assert settle_ah(0, 0.25) == -0.5
    assert settle_ah(-1, 0.25) == -1.0

    assert settle_ah(0, 0.75) == -1.0     # 0.5输 + 1.0输
    assert settle_ah(1, 0.75) == 0.5      # 0.5赢 + 1.0走
    assert settle_ah(2, 0.75) == 1.0      # 两半全赢

    assert settle_ah(1, 1.25) == -0.5     # 1.0走 + 1.5输
    assert settle_ah(2, 1.25) == 1.0      # 两半全赢

    assert settle_ah(1, 1.75) == -1.0     # 1.5输 + 2.0输
    assert settle_ah(2, 1.75) == 0.5      # 1.5赢 + 2.0走
    assert settle_ah(3, 1.75) == 1.0      # 两半全赢
    assert settle_ah(0, -0.25) == 0.5
    assert settle_ah(-1, -0.25) == -1.0
    assert settle_ah(0, -0.75) == 1.0
    assert settle_ah(1, -1.25) == 1.0
    assert settle_ah(0, -1.25) == 1.0
    assert settle_ah(-2, 1.0) == -1.0
    assert settle_ah(-2, -1.0) == -1.0
    print("== 结算函数边界自检通过 ==")

    lh, la = 1.5, 1.2
    n = 40000
    rng = np.random.default_rng(42)
    h = rng.poisson(lh, size=n)
    a = rng.poisson(la, size=n)
    margins = h - a
    win_full = (margins > 1).mean()
    push_frac = (margins == 1).mean()
    ev_analytic = win_full * (1.9 - 1.0) - (1 - win_full - push_frac) + 0.0 * push_frac
    ev_mc = ah_ev(lh, la, 1.0, 1.9, n=n, seed=42)
    print(f"解析EV={ev_analytic:.4f} 蒙特卡洛EV={ev_mc:.4f} 差={abs(ev_analytic-ev_mc):.4f}")
    assert abs(ev_analytic - ev_mc) < 0.01

    # 解析 ah_win_frac 与蒙特卡洛 E[settle] 对照
    lh, la, line = 1.5, 1.2, 0.75
    n = 60000
    rng = np.random.default_rng(7)
    h = rng.poisson(lh, size=n)
    a = rng.poisson(la, size=n)
    frac_mc = np.array([settle_ah(m, line) for m in (h - a)]).mean()
    frac_an = ah_win_frac(lh, la, line)
    print(f"E[settle] 蒙特卡洛={frac_mc:.4f} 解析={frac_an:.4f} 差={abs(frac_mc-frac_an):.4f}")
    assert abs(frac_mc - frac_an) < 0.01

    # 解析 EV(主/客) 与蒙特卡洛对照
    odds_h, odds_a = 1.90, 1.95
    evh_an = ah_ev_analytic(lh, la, line, odds_h)
    eva_an = ah_ev_away(lh, la, line, odds_a)
    evh_mc = ah_ev(lh, la, line, odds_h, n=n, seed=7)
    h2 = rng.poisson(lh, size=n)
    a2 = rng.poisson(la, size=n)
    eva_mc = np.array([ah_net_profit(-m, line, odds_a) for m in (h2 - a2)]).mean()
    print(f"主EV 解析={evh_an:.4f} MC={evh_mc:.4f} 差={abs(evh_an-evh_mc):.4f} | "
          f"客EV 解析={eva_an:.4f} MC={eva_mc:.4f} 差={abs(eva_an-eva_mc):.4f}")
    assert abs(evh_an - evh_mc) < 0.01 and abs(eva_an - eva_mc) < 0.01


if __name__ == "__main__":
    _self_test()
    print("asian_handicap.py 自检通过")
