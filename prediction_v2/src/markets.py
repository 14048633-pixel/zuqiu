"""市场工具 —— 去水、结算、凯利、EV。

结算口径：
  - 让球：主队视角，盘口 AHh（正=主受让）。整/半盘直接结算，1/4盘拆成两个半盘取均值。
  - 大小球：固定线（默认2.5），整数线平局=走水。
  - 返回 r ∈ [-1, 1]：1=全赢，-1=全输，0=走水，±0.5=赢/输一半。
"""
from __future__ import annotations

import math

import numpy as np


# ---------------- 去水 ----------------
def devig(oh: float, od: float, oa: float) -> tuple[float, float, float]:
    """1X2 比例去水 → 公平概率 (home, draw, away)。"""
    inv = 1.0 / oh + 1.0 / od + 1.0 / oa
    return 1.0 / oh / inv, 1.0 / od / inv, 1.0 / oa / inv


def devig2(o1: float, o2: float) -> tuple[float, float]:
    """两路去水。"""
    inv = 1.0 / o1 + 1.0 / o2
    return 1.0 / o1 / inv, 1.0 / o2 / inv


def overround(oh: float, od: float, oa: float) -> float:
    return 1.0 / oh + 1.0 / od + 1.0 / oa


# ---------------- 泊松概率 ----------------
def poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def goal_matrix(lam_h: float, lam_a: float, max_goals: int = 10) -> np.ndarray:
    ph = np.array([poisson_pmf(k, lam_h) for k in range(max_goals + 1)])
    pa = np.array([poisson_pmf(k, lam_a) for k in range(max_goals + 1)])
    ph /= ph.sum()
    pa /= pa.sum()
    return np.outer(ph, pa)


def p_1x2(M: np.ndarray) -> tuple[float, float, float]:
    """(主胜, 平, 客胜)。"""
    n = M.shape[0]
    idx = np.arange(n)
    home = np.tril(M, -1).sum()   # i>j
    away = np.triu(M, 1).sum()    # i<j
    draw = 1.0 - home - away
    return float(home), float(draw), float(away)


def p_over(M: np.ndarray, line: float) -> float:
    """大球概率（整数线含半权走水）。"""
    n = M.shape[0]
    p = 0.0
    for i in range(n):
        for j in range(n):
            tot = i + j
            if tot > line:
                p += M[i, j]
            elif abs(tot - line) < 1e-9:
                p += 0.5 * M[i, j]
    return float(p)


def p_ah(M: np.ndarray, line: float) -> float:
    """主队让球 line 的赢盘概率（整数/半盘含半权走水）。"""
    n = M.shape[0]
    p = 0.0
    for i in range(n):
        for j in range(n):
            m = (i - j) + line
            if m > 0:
                p += M[i, j]
            elif abs(m) < 1e-9:
                p += 0.5 * M[i, j]
    return float(p)


def p_ah_quarter(M: np.ndarray, line: float) -> float:
    """1/4 盘口 → 两个半盘平均。"""
    if abs(line * 2 - round(line * 2)) < 1e-9:
        return p_ah(M, line)
    return 0.5 * (p_ah(M, line - 0.25) + p_ah(M, line + 0.25))


def p_ou_quarter(M: np.ndarray, line: float) -> float:
    if abs(line * 2 - round(line * 2)) < 1e-9:
        return p_over(M, line)
    return 0.5 * (p_over(M, line - 0.25) + p_over(M, line + 0.25))


# ---------------- 结算 ----------------
def _settle_half(margin: float) -> float:
    if margin > 0:
        return 1.0
    if margin < 0:
        return -1.0
    return 0.0


def settle_ah(line: float, gh: int, ga: int) -> float:
    """主队让 line 的结算，返回 r ∈ [-1,1]。"""
    if abs(line * 2 - round(line * 2)) < 1e-9:
        return _settle_half((gh - ga) + line)
    return 0.5 * (_settle_half((gh - ga) + line - 0.25) +
                  _settle_half((gh - ga) + line + 0.25))


def settle_ou(line: float, total: int) -> float:
    if abs(line * 2 - round(line * 2)) < 1e-9:
        return _settle_half(total - line)
    return 0.5 * (_settle_half(total - line - 0.25) +
                  _settle_half(total - line + 0.25))


# ---------------- 投注 ----------------
def ev(prob: float, odds: float) -> float:
    return prob * odds - 1.0


def kelly_fraction(prob: float, odds: float, frac: float = 0.25, cap: float = 0.10) -> float:
    """1/4 凯利，上限 cap。"""
    if odds <= 1.0 or prob <= 0.0:
        return 0.0
    b = odds - 1.0
    f_star = (prob * b - (1.0 - prob)) / b
    if f_star <= 0.0:
        return 0.0
    return max(0.0, min(f_star * frac, cap))


def profit_for(r: float, stake: float, odds: float) -> float:
    """按结算 r 计算盈亏（r>0 按赔率，r<=0 按全/半输）。"""
    if r > 0:
        return stake * r * (odds - 1.0)
    return stake * r
