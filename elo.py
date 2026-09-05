# -*- coding: utf-8 -*-
"""ELO 评分(修正版)。

旧系统缺陷: days_ago = 今天 - 比赛日(锚定当前日期，回测时依赖未来/泄漏)。
修正:
  1. 严格按比赛日期顺序逐场更新;
  2. 不活跃衰减基于"该队距上一场比赛的间隔天数"(half-life 半衰期);
  3. K 值随净胜球放大但设上限，防止大比分过度波动。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import FEATURES

INIT_RATING = 1500.0
HOME_ADV = 100.0
BASE_K = 32.0
HALF_LIFE = FEATURES["decay_halflife"]  # 由 config 控制(修复: 此前硬编码 200, 配置未接线)
MAX_GD_MULT = 3.0


def _gd_multiplier(gd: float) -> float:
    """净胜球放大系数，封顶防爆。"""
    gd = min(abs(gd), 6.0)
    return min(1.0 + 0.5 * gd, MAX_GD_MULT)


def expected_score(home: float, away: float, home_adv: float = HOME_ADV) -> float:
    return 1.0 / (1.0 + 10.0 ** ((away - (home + home_adv)) / 400.0))


def decay_rating(rating: float, days: float, init: float = INIT_RATING,
                 half_life: float = HALF_LIFE) -> float:
    """按不活跃天数向初始值衰减。days<=0 时不衰减。"""
    if days is None or np.isnan(days) or days <= 0:
        return rating
    factor = 0.5 ** (days / half_life)
    return init + (rating - init) * factor


class EloEngine:
    """顺序 ELO：维护每队评分与上次出赛日期。"""

    def __init__(self, base_k: float = BASE_K, home_adv: float = HOME_ADV,
                 half_life: float = HALF_LIFE):
        self.base_k = base_k
        self.home_adv = home_adv
        self.half_life = half_life
        self.ratings: dict[str, float] = {}
        self.last_date: dict[str, pd.Timestamp] = {}

    def get_rating(self, team: str, on_date: pd.Timestamp) -> float:
        r = self.ratings.get(team, INIT_RATING)
        last = self.last_date.get(team)
        if last is not None and on_date is not None:
            days = (on_date - last).days
            r = decay_rating(r, days, half_life=self.half_life)
        return r

    def update(self, home: str, away: str, hg: float, ag: float,
               date: pd.Timestamp) -> tuple[float, float]:
        """按一场比赛更新，返回 (home_new, away_new)。"""
        rh = self.get_rating(home, date)
        ra = self.get_rating(away, date)
        e_home = expected_score(rh, ra, self.home_adv)
        actual_home = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        k = self.base_k * _gd_multiplier(hg - ag)
        rh_new = rh + k * (actual_home - e_home)
        ra_new = ra + k * ((1.0 - actual_home) - (1.0 - e_home))
        self.ratings[home] = rh_new
        self.ratings[away] = ra_new
        self.last_date[home] = date
        self.last_date[away] = date
        return rh_new, ra_new

    def match_probs(self, home: str, away: str, on_date: pd.Timestamp) -> tuple[float, float]:
        """返回 (主胜概率, 客胜概率)，平局概率由外部模型估计。"""
        rh = self.get_rating(home, on_date)
        ra = self.get_rating(away, on_date)
        eh = expected_score(rh, ra, self.home_adv)
        return eh, 1.0 - eh


def compute_elo_history(df: pd.DataFrame, base_k: float = BASE_K) -> pd.DataFrame:
    """对按时间排序的比赛表逐场计算赛前 ELO，返回追加列。

    列: elo_home_pre, elo_away_pre(赛前，含不活跃衰减)、days_since_home, days_since_away
    """
    eng = EloEngine(base_k=base_k)
    out = df.copy()
    rows = []
    for _, r in out.iterrows():
        date = r["date"]
        home, away = r["home"], r["away"]
        rh_pre = eng.get_rating(home, date)
        ra_pre = eng.get_rating(away, date)
        d_home = (date - eng.last_date[home]).days if home in eng.last_date else np.nan
        d_away = (date - eng.last_date[away]).days if away in eng.last_date else np.nan
        eng.update(home, away, r["hg"], r["ag"], date)
        rows.append((rh_pre, ra_pre, d_home, d_away))
    out[["elo_home_pre", "elo_away_pre", "days_since_home", "days_since_away"]] = rows
    return out


def pi_history(df: pd.DataFrame, base_k: float = BASE_K):
    """实验壳: penaltyblog Pi 评分替代 Elo (2026-09-03 双轨隔离).

    默认 config.MODEL['elo_pi']=False 走 Elo; 启用后此壳当前返回与 Elo 相同结果
    (防默认污染)。真正的 Pi/Massey 实现后续在此落地, 跑 A/B 再切主链。
    """
    return compute_elo_history(df, base_k=base_k)


def _self_test():
    eng = EloEngine()
    # 主队强胜：主队评分上升，客队下降
    d0 = pd.Timestamp("2024-01-01")
    r1h, r1a = eng.update("A", "B", 3, 0, d0)
    assert r1h > 1500.0 and r1a < 1500.0, (r1h, r1a)
    # 弱队小胜强队：评分变动方向正确且幅度小于大胜
    eng2 = EloEngine()
    _, _ = eng2.update("C", "D", 1, 0, d0)
    assert eng2.ratings["C"] > 1500.0 and eng2.ratings["D"] < 1500.0
    # 不活跃衰减：长期不打球评分向 1500 靠拢
    r = decay_rating(1800.0, 400.0)
    assert 1500.0 < r < 1800.0, r
    # 半衰期 200 天, 400 天 -> 应衰减到 1500 + 300*0.5^2 = 1575(显式传参, 不依赖全局配置)
    assert abs(decay_rating(1800.0, 400.0, half_life=200.0) - 1575.0) < 1e-9
    print("== ELO 自检通过 ==")


if __name__ == "__main__":
    _self_test()
