# -*- coding: utf-8 -*-
"""比分矩阵与衍生概率: 基于独立泊松 λ_h/λ_a。

输出报告"模型结果"章节所需:
- 比分矩阵 P(hg=i, ag=j)
- Top3 比分 / 矩阵最高比分
- BTTS 双方进球概率
- 大小球概率(任意盘口线)
- 预期进球 / 总进球分布

用法: python football_analyzer/score_matrix.py  # 自检
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from devig import poisson_pmf

MAX_GOALS = 10


def score_matrix(lh: float, la: float, max_goals: int = MAX_GOALS) -> pd.DataFrame:
    """比分矩阵: 行=主队进球 0..max, 列=客队进球 0..max, 值=概率。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return pd.DataFrame()
    rows = []
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            row.append(poisson_pmf(i, lh) * poisson_pmf(j, la))
        rows.append(row)
    df = pd.DataFrame(rows, index=range(max_goals + 1), columns=range(max_goals + 1))
    return df


def score_dist(lh: float, la: float, max_goals: int = MAX_GOALS) -> list[tuple]:
    """所有比分的概率列表 [(i,j,prob), ...], 按概率降序。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return []
    dist = []
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            dist.append((i, j, poisson_pmf(i, lh) * poisson_pmf(j, la)))
    dist.sort(key=lambda x: x[2], reverse=True)
    return dist


def top_scores(lh: float, la: float, n: int = 3, max_goals: int = MAX_GOALS) -> list[tuple]:
    """Top n 比分 [(i,j,prob), ...]。"""
    return score_dist(lh, la, max_goals)[:n]


def matrix_top(lh: float, la: float, max_goals: int = MAX_GOALS) -> tuple:
    """矩阵最高概率比分 (i,j,prob)。"""
    dist = score_dist(lh, la, max_goals)
    return dist[0] if dist else (np.nan, np.nan, np.nan)


def btts_prob(lh: float, la: float, max_goals: int = MAX_GOALS) -> float:
    """双方进球概率 P(hg>=1 且 ag>=1) = (1-P(hg=0))*(1-P(ag=0))。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return np.nan
    return (1.0 - poisson_pmf(0, lh)) * (1.0 - poisson_pmf(0, la))


def over_under_prob(lh: float, la: float, line: float = 2.5,
                     max_goals: int = MAX_GOALS) -> float:
    """总进球 > line 的概率(大小球)。line=2.5 即大2.5。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return np.nan
    total = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            if i + j > line:
                total += poisson_pmf(i, lh) * poisson_pmf(j, la)
    return float(total)


def expected_goals(lh: float, la: float) -> dict:
    """预期进球摘要。"""
    return {"home": float(lh), "away": float(la), "total": float(lh + la)}


def total_goals_dist(lh: float, la: float, max_total: int = MAX_GOALS * 2) -> dict:
    """总进球分布 P(total=k)。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return {}
    dist = {}
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            k = i + j
            if k > max_total:
                continue
            dist[k] = dist.get(k, 0.0) + poisson_pmf(i, lh) * poisson_pmf(j, la)
    return dist


def _self_test():
    lh, la = 2.946, 0.755  # 报告中巴萨 vs 毕尔巴鄂的预期进球
    # 比分矩阵
    m = score_matrix(lh, la)
    assert m.shape == (11, 11)
    assert abs(m.values.sum() - 1.0) < 1e-3, f"矩阵概率和={m.values.sum()}"  # max_goals 截断误差
    # Top3
    top = top_scores(lh, la, n=3)
    assert len(top) == 3
    assert top[0][2] >= top[1][2] >= top[2][2]
    print(f"Top3 比分: {[(f'{i}-{j}', round(p,4)) for i,j,p in top]}")
    # 矩阵最高
    mt = matrix_top(lh, la)
    assert mt[2] == top[0][2]
    print(f"矩阵最高: {mt[0]}-{mt[1]} ({mt[2]:.4f})")
    # BTTS
    btts = btts_prob(lh, la)
    assert 0 <= btts <= 1
    print(f"BTTS 双方进球: {btts:.4f} (报告中 50.50%)")
    # 大小球
    ou = over_under_prob(lh, la, line=2.5)
    assert 0 <= ou <= 1
    print(f"大2.5概率: {ou:.4f} (报告中 71.07%)")
    # 预期进球
    eg = expected_goals(lh, la)
    assert abs(eg["total"] - 3.701) < 0.01
    print(f"预期进球: 主{eg['home']:.3f} 客{eg['away']:.3f} 总{eg['total']:.3f}")
    # 总进球分布
    tgd = total_goals_dist(lh, la)
    assert abs(sum(tgd.values()) - 1.0) < 1e-3  # 截断误差
    print(f"总进球分布 Top3: {sorted(tgd.items(), key=lambda x:-x[1])[:3]}")
    # 边界: NaN 输入
    assert score_matrix(np.nan, 1.0).empty
    assert np.isnan(btts_prob(np.nan, 1.0))
    print("== score_matrix 自检通过 ==")


if __name__ == "__main__":
    _self_test()
