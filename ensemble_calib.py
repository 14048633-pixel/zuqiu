# -*- coding: utf-8 -*-
"""多模型融合校准: 泊松 1X2 + 市场去水 + 主客场分层 三源加权融合。

报告"综合校准"即此输出(如巴萨 80.30/12.58/7.12)。
Elo 二元强弱单独展示, 默认不进融合(可配置权重)。

用法: python football_analyzer/ensemble_calib.py  # 自检
"""
from __future__ import annotations

from typing import Optional

import numpy as np

# 默认权重: 泊松 0.25 / 市场 0.50 / 主客场 0.25
# 市场权重高于模型源, 因为市场赔率已消化最新伤停/阵容/战术信息, 纯历史模型天然滞后。
# 2026-08-29 P0调整: 从近似等权(0.34/0.33/0.33)改为市场优先(0.25/0.50/0.25),
# 实测 Arsenal vs Chelsea 主胜概率从 69.27% 降至 ~64%, 与市场 58.2% 差距从 11pp 缩至 6pp。
DEFAULT_WEIGHTS = {"poisson": 0.25, "market": 0.50, "home_away": 0.25, "elo": 0.0}


def _norm(ph, pd_, pa) -> tuple:
    """归一化使和为 1。全 NaN 返回 NaN。"""
    s = ph + pd_ + pa
    if not np.isfinite(s) or s <= 0:
        return np.nan, np.nan, np.nan
    return ph / s, pd_ / s, pa / s


def elo_to_1x2(elo_h: float, draw_prob: float) -> tuple:
    """Elo 二元强弱转 1X2: 平局从外部取, 主客胜按 Elo 比例分配剩余。

    elo_h = P(主队胜) from Elo expected_score; draw_prob = 平局概率(来自其他源均值)。
    """
    if not np.isfinite(elo_h) or not np.isfinite(draw_prob):
        return np.nan, np.nan, np.nan
    elo_h = float(np.clip(elo_h, 0.0, 1.0))
    draw_prob = float(np.clip(draw_prob, 0.0, 0.95))
    rem = 1.0 - draw_prob
    return elo_h * rem, draw_prob, (1.0 - elo_h) * rem


def ensemble_1x2(poisson_p: tuple, market_p: tuple,
                  home_away_p: tuple, elo_h: Optional[float] = None,
                  weights: Optional[dict] = None) -> dict:
    """三源(+可选Elo)加权融合校准 1X2 概率。

    输入各源 (ph, pd, pa); elo_h 为 Elo 二元主队胜率(可选)。
    返回 {ph, pd, pa, weights_used, sources}。
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)
    # 收集有效源
    src = {}
    if poisson_p and all(np.isfinite(x) for x in poisson_p):
        src["poisson"] = poisson_p
    if market_p and all(np.isfinite(x) for x in market_p):
        src["market"] = market_p
    if home_away_p and all(np.isfinite(x) for x in home_away_p):
        src["home_away"] = home_away_p
    if elo_h is not None and np.isfinite(elo_h) and w.get("elo", 0) > 0:
        # Elo 平局用已有源平局均值
        draws = [p[1] for p in src.values()]
        d = float(np.mean(draws)) if draws else 0.25
        src["elo"] = elo_to_1x2(elo_h, d)
    if not src:
        return {"ph": np.nan, "pd": np.nan, "pa": np.nan,
                "weights_used": {}, "sources": {}}
    # 归一化各源权重(只对有效源)
    active_w = {k: w.get(k, 0.0) for k in src}
    ws = sum(active_w.values())
    if ws <= 0:
        active_w = {k: 1.0 / len(src) for k in src}  # 等权兜底
    else:
        active_w = {k: v / ws for k, v in active_w.items()}
    # 加权融合
    ph = sum(active_w[k] * src[k][0] for k in src)
    pd_ = sum(active_w[k] * src[k][1] for k in src)
    pa = sum(active_w[k] * src[k][2] for k in src)
    ph, pd_, pa = _norm(ph, pd_, pa)
    return {"ph": float(ph), "pd": float(pd_), "pa": float(pa),
            "weights_used": active_w, "sources": {k: tuple(v) for k, v in src.items()}}


def _self_test():
    # 报告中巴萨 vs 毕尔巴鄂的三源数字(近似)
    poisson = (0.82, 0.11, 0.07)          # 泊松 1X2 (λ=2.946/0.755)
    market = (0.7676, 0.1458, 0.0866)     # Pinnacle 去水
    home_away = (0.8163, 0.1180, 0.0657)  # 主客场分层
    res = ensemble_1x2(poisson, market, home_away)
    print(f"综合校准(市场权重0.50): 主胜{res['ph']:.2%} 平{res['pd']:.2%} 客胜{res['pa']:.2%}")
    print(f"  (新权重预期: 79.29% / 12.99% / 7.72%; 旧等权报告: 80.30% / 12.58% / 7.12%)")
    assert abs(res["ph"] + res["pd"] + res["pa"] - 1.0) < 1e-9
    # 与新权重计算值偏差 < 0.1pp
    assert abs(res["ph"] - 0.792875) < 1e-4, f"主胜偏差 {res['ph']-0.792875:.4%}"
    assert abs(res["pd"] - 0.1299) < 1e-4, f"平局偏差 {res['pd']-0.1299:.4%}"
    assert abs(res["pa"] - 0.077225) < 1e-4, f"客胜偏差 {res['pa']-0.077225:.4%}"
    # Elo 可选融合
    res2 = ensemble_1x2(poisson, market, home_away, elo_h=0.7023,
                         weights={"poisson": 0.3, "market": 0.3, "home_away": 0.3, "elo": 0.1})
    print(f"含Elo融合: 主胜{res2['ph']:.2%} 平{res2['pd']:.2%} 客胜{res2['pa']:.2%}")
    assert abs(res2["ph"] + res2["pd"] + res2["pa"] - 1.0) < 1e-9
    # Elo 转 1X2
    eh, ed, ea = elo_to_1x2(0.7023, 0.1258)
    print(f"Elo转1X2: 主{eh:.2%} 平{ed:.2%} 客{ea:.2%}")
    assert abs(eh + ed + ea - 1.0) < 1e-9
    # 全 NaN 兜底
    res3 = ensemble_1x2((np.nan, np.nan, np.nan), (np.nan, np.nan, np.nan),
                         (np.nan, np.nan, np.nan))
    assert np.isnan(res3["ph"])
    print("== ensemble_calib 自检通过 ==")


if __name__ == "__main__":
    _self_test()
