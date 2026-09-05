"""Dixon-Coles 低比分修正模型。

对独立泊松的低比分(0-0/0-1/1-0/1-1)应用 τ 修正, 解决泊松低估平局和
0-0 比分的问题。ρ<0 表示 0-0/1-1 比泊松预测更常见(足球典型 ρ≈-0.1~-0.03)。

核心公式:
  P_DC(i,j) = τ(i,j; ρ) × P_pois(i; λh) × P_pois(j; λa)
  τ(0,0) = 1 - λh·λa·ρ
  τ(0,1) = 1 + λh·ρ
  τ(1,0) = 1 + λa·ρ
  τ(1,1) = 1 - ρ
  τ(other) = 1

用法: python football_analyzer/dixon_coles.py  # 自检
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from devig import poisson_pmf, poisson_1x2

MAX_GOALS = 10


def dc_tau(i: int, j: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles τ 修正系数。clamp到[0.3,2.0]防止极端λ/ρ导致负数或过度放大。"""
    if i == 0 and j == 0:
        tau = 1.0 - lh * la * rho
    elif i == 0 and j == 1:
        tau = 1.0 + lh * rho
    elif i == 1 and j == 0:
        tau = 1.0 + la * rho
    elif i == 1 and j == 1:
        tau = 1.0 - rho
    else:
        return 1.0
    return float(max(0.3, min(2.0, tau)))


def dc_score_matrix(lh: float, la: float, rho: float = 0.0,
                    max_goals: int = MAX_GOALS) -> pd.DataFrame:
    """Dixon-Coles 比分矩阵(已归一化)。rho=0 退化为纯泊松。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return pd.DataFrame()
    rho = float(np.clip(rho, -0.2, 0.2))
    rows = []
    total = 0.0
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lh) * poisson_pmf(j, la) * dc_tau(i, j, lh, la, rho)
            row.append(p)
            total += p
        rows.append(row)
    # 归一化(τ 修正后概率和可能偏离 1); rho=0 时 τ 全为 1, 跳过归一化避免浮点误差
    if abs(rho) > 1e-12 and total > 0:
        rows = [[p / total for p in row] for row in rows]
    return pd.DataFrame(rows, index=range(max_goals + 1), columns=range(max_goals + 1))


def dc_score_dist(lh: float, la: float, rho: float = 0.0,
                  max_goals: int = MAX_GOALS) -> list[tuple]:
    """所有比分的 Dixon-Coles 概率列表, 按概率降序。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return []
    rho = float(np.clip(rho, -0.2, 0.2))
    dist = []
    total = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lh) * poisson_pmf(j, la) * dc_tau(i, j, lh, la, rho)
            dist.append((i, j, p))
            total += p
    if abs(rho) > 1e-12 and total > 0:
        dist = [(i, j, p / total) for i, j, p in dist]
    dist.sort(key=lambda x: x[2], reverse=True)
    return dist


def dc_top_scores(lh: float, la: float, rho: float = 0.0, n: int = 3,
                  max_goals: int = MAX_GOALS) -> list[tuple]:
    """Top n Dixon-Coles 比分。"""
    return dc_score_dist(lh, la, rho, max_goals)[:n]


def dc_matrix_top(lh: float, la: float, rho: float = 0.0,
                  max_goals: int = MAX_GOALS) -> tuple:
    """Dixon-Coles 矩阵最高概率比分。"""
    dist = dc_score_dist(lh, la, rho, max_goals)
    return dist[0] if dist else (np.nan, np.nan, np.nan)


def dc_btts_prob(lh: float, la: float, rho: float = 0.0,
                 max_goals: int = MAX_GOALS) -> float:
    """Dixon-Coles 双方进球概率 P(hg>=1 且 ag>=1)。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return np.nan
    mat = dc_score_matrix(lh, la, rho, max_goals)
    if mat.empty:
        return np.nan
    return float(mat.iloc[1:, 1:].sum().sum())


def dc_over_under_prob(lh: float, la: float, line: float = 2.5, rho: float = 0.0,
                       max_goals: int = MAX_GOALS) -> float:
    """Dixon-Coles 总进球 > line 的概率。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return np.nan
    mat = dc_score_matrix(lh, la, rho, max_goals)
    if mat.empty:
        return np.nan
    total = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            if i + j > line:
                total += mat.iloc[i, j]
    return float(total)


def dc_1x2(lh: float, la: float, rho: float = 0.0,
           max_goals: int = MAX_GOALS) -> tuple:
    """Dixon-Coles 1X2 概率 (主胜, 平, 客胜)。"""
    if not (np.isfinite(lh) and np.isfinite(la)):
        return np.nan, np.nan, np.nan
    mat = dc_score_matrix(lh, la, rho, max_goals)
    if mat.empty:
        return np.nan, np.nan, np.nan
    ph = float(sum(mat.iloc[i, j] for i in range(max_goals + 1)
                   for j in range(max_goals + 1) if i > j))
    pd_ = float(sum(mat.iloc[i, j] for i in range(max_goals + 1)
                    for j in range(max_goals + 1) if i == j))
    pa = float(sum(mat.iloc[i, j] for i in range(max_goals + 1)
                   for j in range(max_goals + 1) if i < j))
    return ph, pd_, pa


def estimate_rho(df_train: pd.DataFrame, fit: dict, min_samples: int = 300) -> dict:
    """用训练数据按联赛估计 Dixon-Coles ρ 参数。

    矩估计法: 比较实际 0-0+1-1 频率与泊松预测频率, 反推 ρ。
    足球低比分比独立泊松更常见(实际频率>泊松预测) -> ρ 应为负(提升 0-0/1-1)。
    修复(2026-08-30): 原实现符号反了, ρ>0 反而压低平局概率。
    样本不足 min_samples 的联赛返回默认 ρ=0.05。
    返回 {"<league>": rho_value}。
    """
    rho_out = {}
    for league, g in df_train.groupby("league"):
        if len(g) < min_samples:
            rho_out[league] = 0.05
            continue
        actual_low = 0  # 实际 0-0 + 1-1 场数
        pois_low = 0.0  # 泊松预测 0-0 + 1-1 概率和
        for _, row in g.iterrows():
            from model import poisson_predict
            lh, la = poisson_predict(fit, row)
            if not np.isfinite(lh) or not np.isfinite(la):
                continue
            p00 = poisson_pmf(0, lh) * poisson_pmf(0, la)
            p11 = poisson_pmf(1, lh) * poisson_pmf(1, la)
            pois_low += p00 + p11
            if (row["hg"] == 0 and row["ag"] == 0) or (row["hg"] == 1 and row["ag"] == 1):
                actual_low += 1
        if pois_low > 0 and actual_low > 0:
            ratio = actual_low / pois_low
            # 实际低频比分更多 -> ratio>1 -> ρ 负(增加 0-0/1-1)
            rho = float(np.clip((1.0 - ratio) * 0.3, -0.15, 0.10))
        else:
            rho = 0.05
        rho_out[league] = rho
    return rho_out


def _self_test():
    """自检: Dixon-Coles vs 纯泊松对比。"""
    lh, la = 1.5, 1.2
    print(f"=== Dixon-Coles 自检 (λh={lh}, λa={la}) ===")
    for rho in [0.0, 0.05, 0.1]:
        p00_pois = poisson_pmf(0, lh) * poisson_pmf(0, la)
        p11_pois = poisson_pmf(1, lh) * poisson_pmf(1, la)
        mat = dc_score_matrix(lh, la, rho)
        p00_dc = mat.iloc[0, 0]
        p11_dc = mat.iloc[1, 1]
        ou = dc_over_under_prob(lh, la, 2.5, rho)
        ph, pd_, pa = dc_1x2(lh, la, rho)
        print(f"ρ={rho:.2f}: 0-0 {p00_pois:.4f}->{p00_dc:.4f}, "
              f"1-1 {p11_pois:.4f}->{p11_dc:.4f}, "
              f"大2.5={ou:.4f}, 1X2=({ph:.3f},{pd_:.3f},{pa:.3f})")
    # 验证 rho=0 退化为纯泊松
    mat_dc = dc_score_matrix(lh, la, 0.0)
    from score_matrix import score_matrix
    mat_pois = score_matrix(lh, la)
    diff = (mat_dc - mat_pois).abs().sum().sum()
    print(f"\nρ=0 与纯泊松差异: {diff:.2e} (应≈0)")
    assert diff < 1e-10, "rho=0 应退化为纯泊松"
    print("Dixon-Coles 自检通过")


if __name__ == "__main__":
    _self_test()
