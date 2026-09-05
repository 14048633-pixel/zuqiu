# -*- coding: utf-8 -*-
"""蒙特卡洛比分采样与串关联合模拟 (V4.5 扩展模块).

基于 Dixon-Coles 比分分布对单场/多场做大量采样, 提供:
1. 单场: 1X2 / 大小球 / BTTS / 让球 的蒙特卡洛概率(采样真值)
        与 dixon_coles 解析法对照, 量化解析近似的截断/归一化误差
2. 串关: 多场联合采样 -> 串关整体真实通过率 + 对串关赔率的 EV
         (独立采样版; 协动扩展见 README 待办)

用法: python football_analyzer/mc_sim.py  # 自检(解析 vs 蒙特卡洛对照)
"""
from __future__ import annotations

import numpy as np

from dixon_coles import (dc_1x2, dc_btts_prob, dc_over_under_prob,
                         dc_score_dist)

DEFAULT_N = 200_000
MAX_GOALS = 10


def sample_scores(lh: float, la: float, rho: float = 0.0, n: int = DEFAULT_N,
                  seed: int | None = None, max_goals: int = MAX_GOALS):
    """从 Dixon-Coles 比分分布采样 n 场, 返回 (home_goals, away_goals) int 数组.
    复用 dc_score_dist(已归一化); rho=0 时退化为纯泊松采样.
    """
    dist = dc_score_dist(lh, la, rho, max_goals)
    if not dist:
        return None
    ij = np.array([(i, j) for i, j, _ in dist], dtype=np.int64)
    p = np.array([pr for _, _, pr in dist], dtype=np.float64)
    p = p / p.sum()
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(dist), size=n, p=p)
    return ij[idx, 0], ij[idx, 1]


def mc_1x2(lh: float, la: float, rho: float = 0.0, n: int = DEFAULT_N,
           seed: int | None = None):
    """蒙特卡洛 1X2 概率 (主胜, 平, 客胜)."""
    s = sample_scores(lh, la, rho, n, seed)
    if s is None:
        return np.nan, np.nan, np.nan
    hg, ag = s
    return float((hg > ag).mean()), float((hg == ag).mean()), float((hg < ag).mean())


def mc_over_under(lh: float, la: float, line: float = 2.5, rho: float = 0.0,
                  n: int = DEFAULT_N, seed: int | None = None):
    """蒙特卡洛 总进球 > line 概率(大小球)."""
    s = sample_scores(lh, la, rho, n, seed)
    if s is None:
        return np.nan
    hg, ag = s
    return float((hg + ag > line).mean())


def mc_btts(lh: float, la: float, rho: float = 0.0, n: int = DEFAULT_N,
            seed: int | None = None):
    """蒙特卡洛 双方进球概率."""
    s = sample_scores(lh, la, rho, n, seed)
    if s is None:
        return np.nan
    hg, ag = s
    return float(((hg >= 1) & (ag >= 1)).mean())


def mc_ah(lh: float, la: float, line: float = 0.0, rho: float = 0.0,
          n: int = DEFAULT_N, seed: int | None = None):
    """蒙特卡洛 让球盘概率. 口径与 match_report._ah_win_prob_single 一致:
    line 为正=主队受让, 负=主队让球. 返回 (主队赢盘, 走水, 主队输盘).
    注: 仅整数/半整数线有走水(半整数走水概率为0).
    """
    s = sample_scores(lh, la, rho, n, seed)
    if s is None:
        return np.nan, np.nan, np.nan
    hg, ag = s
    diff = hg - ag + line
    tol = 1e-9
    win = float((diff > tol).mean())
    push = float((np.abs(diff) <= tol).mean())
    lose = float((diff < -tol).mean())
    return win, push, lose


def compare_analytic_vs_mc(lh: float, la: float, rho: float = 0.0,
                           n: int = DEFAULT_N, seed: int = 42) -> dict:
    """单场对照: 解析(dc_*) vs 蒙特卡洛. 返回含最大绝对差的对照表.
    蒙特卡洛是"采样真值"(仅受采样噪声影响), 解析法是 max_goals 截断+归一化的快近似.
    """
    a_1x2 = dc_1x2(lh, la, rho)
    m_1x2 = mc_1x2(lh, la, rho, n, seed)
    a_ou = dc_over_under_prob(lh, la, 2.5, rho)
    m_ou = mc_over_under(lh, la, 2.5, rho, n, seed)
    a_b = dc_btts_prob(lh, la, rho)
    m_b = mc_btts(lh, la, rho, n, seed)

    rows = {
        "主胜": (a_1x2[0], m_1x2[0]),
        "平局": (a_1x2[1], m_1x2[1]),
        "客胜": (a_1x2[2], m_1x2[2]),
        "大2.5": (a_ou, m_ou),
        "双方进球": (a_b, m_b),
    }
    out = {"n": n, "rows": {}}
    max_abs = 0.0
    for k, (a, m) in rows.items():
        d = abs(a - m)
        max_abs = max(max_abs, d)
        out["rows"][k] = {"analytic": round(float(a), 5),
                          "mc": round(float(m), 5),
                          "abs_diff": round(float(d), 5)}
    out["max_abs_diff"] = float(max_abs)
    return out


# ---------------- 串关联合模拟 ----------------

def _leg_hit(hg: np.ndarray, ag: np.ndarray, leg: dict) -> np.ndarray:
    """单腿命中判定(向量化). leg.market: 1x2 / ou / btts / ah.
    side: home/draw/away / over/under / yes/no / 数值(让球主队视角).
    """
    mkt = leg["market"]
    side = leg.get("side", "home")
    if mkt == "1x2":
        if side == "home":
            return hg > ag
        if side == "draw":
            return hg == ag
        return hg < ag
    if mkt == "ou":
        total = hg + ag
        line = float(leg.get("line", 2.5))
        return total > line if side == "over" else total <= line
    if mkt == "btts":
        both = (hg >= 1) & (ag >= 1)
        return both if side == "yes" else ~both
    if mkt == "ah":
        line = float(leg.get("line", 0.0))
        diff = hg - ag + line
        tol = 1e-9
        if side == "home":
            return diff > tol
        if side == "push":
            return np.abs(diff) <= tol
        return diff < -tol
    raise ValueError("unknown market: %s" % mkt)


def parlay_sim(legs: list[dict], n: int = DEFAULT_N, seed: int | None = None,
               parlay_odds: float | None = None) -> dict:
    """串关联合模拟(独立采样版): 每腿从自身 DC 分布采样 n 场, 统计联合全中频率.

    legs: [{"lh":..,"la":..,"rho":..,"market":"1x2|ou|btts|ah","side":..,"line":..(可选)}, ...]
    返回: {通过率, 每腿边缘命中率, 全中次数, n, EV(若给 parlay_odds)}
    注意: 独立采样下通过率≈独立乘积; 跨场协动需要 copula/共享冲击(扩展, 见 README 待办).
    """
    if not legs:
        return {"通过率": 0.0, "命中": 0, "n": n, "EV": None}
    rng = np.random.default_rng(seed)
    all_hit = None
    margins = []
    for leg in legs:
        _s = sample_scores(float(leg["lh"]), float(leg["la"]),
                           float(leg.get("rho", 0.0)), n,
                           seed=int(rng.integers(0, 2 ** 31)))
        if _s is None:
            raise ValueError("非法 λ: %s" % leg)
        hg, ag = _s
        hit = _leg_hit(hg, ag, leg)
        margins.append(float(hit.mean()))
        all_hit = hit if all_hit is None else (all_hit & hit)
    n_hit = int(all_hit.sum())
    pass_rate = n_hit / n
    out = {"通过率": pass_rate, "每腿边缘命中率": margins,
           "命中": n_hit, "n": n}
    if parlay_odds is not None:
        out["EV"] = pass_rate * float(parlay_odds) - 1.0
    return out


# ---------------- 自检 ----------------

def _self_test():
    lh, la = 1.5, 1.2
    rho = 0.05
    n = 200_000
    print(f"=== 蒙特卡洛自检 (λh={lh}, λa={la}, ρ={rho}, n={n}) ===")

    # 1) 单场对照
    cmp = compare_analytic_vs_mc(lh, la, rho, n)
    print("解析 vs 蒙特卡洛对照:")
    for k, v in cmp["rows"].items():
        print(f"  {k:6s} 解析={v['analytic']:.5f}  MC={v['mc']:.5f}  差={v['abs_diff']:.5f}")
    print(f"  最大绝对差: {cmp['max_abs_diff']:.5f}")
    assert cmp["max_abs_diff"] < 0.005, f"解析/MC 差过大: {cmp['max_abs_diff']}"

    # 2) 概率和≈1
    ph, pd_, pa = mc_1x2(lh, la, rho, n, 1)
    assert abs(ph + pd_ + pa - 1.0) < 1e-6, f"1X2 和={ph+pd_+pa}"
    print(f"  1X2 MC 和={ph+pd_+pa:.6f} ✓")

    # 3) rho=0 蒙特卡洛 ≈ 纯泊松解析(score_matrix)
    from score_matrix import over_under_prob
    m_ou0 = mc_over_under(lh, la, 2.5, 0.0, n, 2)
    a_ou0 = over_under_prob(lh, la, 2.5)
    assert abs(m_ou0 - a_ou0) < 0.005, f"rho=0 大2.5: MC={m_ou0} 泊松={a_ou0}"
    print(f"  ρ=0 蒙特卡洛大2.5={m_ou0:.4f} vs 纯泊松={a_ou0:.4f} ✓")

    # 4) 串关独立采样 vs 独立乘积(strategy.parlay_prob 口径)
    from strategy import parlay_prob
    legs = [
        {"lh": 1.8, "la": 1.0, "rho": 0.05, "market": "1x2", "side": "home"},
        {"lh": 1.2, "la": 1.4, "rho": 0.05, "market": "1x2", "side": "away"},
        {"lh": 1.5, "la": 1.2, "rho": 0.05, "market": "ou", "side": "over", "line": 2.5},
    ]
    ps = parlay_sim(legs, n=100_000, seed=7)
    # 独立乘积(相关性0)
    indep = 1.0
    for m in ps["每腿边缘命中率"]:
        indep *= m
    print(f"  串关3串1: 独立采样通过率={ps['通过率']:.4f}  独立乘积={indep:.4f}")
    assert abs(ps["通过率"] - indep) < 0.01, f"串关采样≠独立乘积: {ps['通过率']} vs {indep}"
    # 与 parlay_prob(相关性0)对照
    probs = [0.0] * len(legs)
    pp = parlay_prob([float(m) for m in ps["每腿边缘命中率"]], [0.0] * 3)
    print(f"  parlay_prob(corr=0)={pp:.4f}")
    assert abs(ps["通过率"] - pp) < 0.01, f"串关采样 vs parlay_prob: {ps['通过率']} vs {pp}"

    # 5) 串关 EV
    ps2 = parlay_sim(legs, n=100_000, seed=7, parlay_odds=10.0)
    print(f"  串关 @10.0 EV={ps2['EV']:+.4f} (通过率{ps2['通过率']:.4f})")

    # 6) 让球走水
    aw, ap, al = mc_ah(lh, la, -0.5, rho, n, 3)  # 主让0.5(无走水)
    assert abs(ap) < 1e-6, "半整数线不应有走水"
    print(f"  主让0.5: 赢盘={aw:.4f} 走水={ap:.4f} 输盘={al:.4f} ✓")

    print("== mc_sim 自检通过 ==")


if __name__ == "__main__":
    _self_test()
