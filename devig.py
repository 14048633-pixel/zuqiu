# -*- coding: utf-8 -*-
"""赔率去水与泊松 lambda 反推。

- devig_1x2: SHIN 去水(默认)，也可用比例法/幂法做对照
- invert_lambdas: 由真实概率反推泊松期望进球(scipy 最小二乘 + 收敛断言)
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq, least_squares

MAX_GOALS = 10


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def poisson_1x2(lh: float, la: float, max_goals: int = MAX_GOALS) -> tuple:
    """由主客期望进球计算 1X2 概率(独立泊松)。"""
    ph = pd_ = pa = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lh) * poisson_pmf(j, la)
            if i > j:
                ph += p
            elif i == j:
                pd_ += p
            else:
                pa += p
    s = ph + pd_ + pa
    return ph / s, pd_ / s, pa / s


def _shin_implied(z: float, q: np.ndarray) -> np.ndarray:
    """SHIN 公式: p_i = (sqrt(z^2 + 4(1-z) q_i^2/Q) - z) / (2-2z)。"""
    s = q.sum()
    return (np.sqrt(z ** 2 + 4.0 * (1.0 - z) * q ** 2 / s) - z) / (2.0 - 2.0 * z)


def devig_1x2(odds_h, odds_d, odds_a, method: str = "shin") -> tuple:
    """欧赔去水，返回归一化真实概率 (p_h, p_d, p_a)。"""
    odds = np.array([odds_h, odds_d, odds_a], dtype=float)
    if np.any(odds <= 1.0) or not np.all(np.isfinite(odds)):
        raise ValueError(f"非法赔率: {odds}")
    q = 1.0 / odds
    if method == "proportional":
        return tuple(q / q.sum())
    if method == "power":
        def resid(k):
            pk = q ** k
            return pk.sum() - 1.0
        k = 1.0
        for _ in range(200):
            f = resid(k)
            if abs(f) < 1e-10:
                break
            dk = max(abs(k) * 1e-6, 1e-9)
            fp = (resid(k + dk) - resid(k - dk)) / (2 * dk)
            if abs(fp) < 1e-12:
                break
            k -= f / fp
            k = min(max(k, 0.1), 3.0)
        pk = q ** k
        return tuple(pk / pk.sum())
    if method == "shin":
        if q.sum() <= 1.0:
            return tuple(q / q.sum())
        z = brentq(lambda zz: 1.0 - _shin_implied(zz, q).sum(), 0.0, 100.0, xtol=1e-12)
        p = _shin_implied(z, q)
        return tuple(p / p.sum())
    raise ValueError(f"未知去水方法: {method}")


def invert_lambdas(p_h, p_d, p_a, max_goals: int = MAX_GOALS, tol: float = 5e-3) -> tuple:
    """由 1X2 真实概率反推 (lambda_home, lambda_away, 拟合残差)。"""
    target = np.array([p_h, p_d, p_a], dtype=float)
    target = target / target.sum()
    x0 = np.array([1.3, 1.2])

    def resid(x):
        ph, pd_, pa = poisson_1x2(x[0], x[1], max_goals)
        return np.array([ph, pd_, pa]) - target

    sol = least_squares(resid, x0, bounds=([0.05, 0.05], [6.0, 6.0]),
                        xtol=1e-10, ftol=1e-10, gtol=1e-10, max_nfev=2000)
    lh, la = sol.x
    ph, pd_, pa = poisson_1x2(lh, la, max_goals)
    err = max(abs(ph - p_h), abs(pd_ - p_d), abs(pa - p_a))
    if err > tol:
        raise RuntimeError(
            f"lambda 反推未收敛: err={err:.4f} > tol={tol}; "
            f"target=({p_h:.3f},{p_d:.3f},{p_a:.3f}) got=({ph:.3f},{pd_:.3f},{pa:.3f})")
    return lh, la, err


def _self_test():
    from penaltyblog import implied as pb_implied
    cases = [(1.5, 4.0, 7.0), (1.2, 6.5, 13.0), (2.05, 3.4, 3.6), (1.85, 3.3, 4.5)]
    print("== SHIN 对照 penaltyblog ==")
    for o in cases:
        ours = devig_1x2(*o, method="shin")
        res = pb_implied.calculate_implied(list(o), pb_implied.ImpliedMethod.SHIN,
                                           pb_implied.OddsFormat.DECIMAL)
        theirs = tuple(res.probabilities)
        diff = max(abs(a - b) for a, b in zip(ours, theirs))
        print(f"odds={o} ours={tuple(round(x,4) for x in ours)} "
              f"pb={tuple(round(x,4) for x in theirs)} maxdiff={diff:.6f}")
        assert diff < 1e-6

    print("== lambda 反推自检 ==")
    for o in cases:
        p = devig_1x2(*o, method="shin")
        lh, la, err = invert_lambdas(*p)
        ph, pd_, pa = poisson_1x2(lh, la)
        print(f"odds={o} target=({p[0]:.3f},{p[1]:.3f},{p[2]:.3f}) "
              f"lambda=({lh:.3f},{la:.3f}) rec=({ph:.3f},{pd_:.3f},{pa:.3f}) err={err:.4f}")
        assert err < 5e-3


if __name__ == "__main__":
    _self_test()
    print("devig.py 全部自检通过")
