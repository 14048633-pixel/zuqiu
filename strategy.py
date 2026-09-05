# -*- coding: utf-8 -*-
"""策略模块：EV / 凯利 / 风控 / 串关。

- ev / kelly_fraction: 单注期望与仓位
- leg_correlation / check_parlay: 串关相关性控制与资金规则
- apply_strategy: 对预测表生成可投注信号
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import STRATEGY


def ev(prob: float, odds: float) -> float:
    """单位本金期望收益。odds 为欧赔。"""
    return prob * (odds - 1.0) - (1.0 - prob)


def kelly_fraction(prob: float, odds: float, kelly_frac: float = None) -> float:
    """分数凯利仓位。无优势返回 0。"""
    kelly_frac = kelly_frac or STRATEGY["kelly_fraction"]
    b = odds - 1.0
    if b <= 0:
        return 0.0
    f = (prob * b - (1.0 - prob)) / b
    if f <= 0:
        return 0.0
    return min(f * kelly_frac, STRATEGY["max_stake_pct"])




def confidence_modulate(stake_pct: float, n_eff, k: float = None) -> float:
    """连续仓位调制: 按球队有效样本量 n_eff 平滑缩放仓位.

    公式 f = n_eff/(n_eff+k), k 为半饱和常数(默认 STRATEGY["conf_n_eff_k"]).
      - n_eff 缺失/NaN  -> 保持原仓位(向后兼容, 未接入贝叶斯的路径不受影响)
      - n_eff <= 0      -> 0.0 (完全无数据, 不下注)
      - 其余             -> stake_pct * n_eff/(n_eff+k)
    EV 仍用均值(无偏)定方向, 本函数只按置信度调仓位, 不破坏 Kelly 统计前提.
    """
    if n_eff is None:
        return stake_pct
    if isinstance(n_eff, float) and np.isnan(n_eff):
        return stake_pct
    if not np.isfinite(n_eff) or n_eff <= 0:
        return 0.0
    k = k if k is not None else STRATEGY.get("conf_n_eff_k", 10.0)
    return stake_pct * (n_eff / (n_eff + k))


def injury_confidence_discount(injury_records: list | None,
                               missing_count: int | None = None,
                               key_positions=("F", "G")) -> tuple:
    """临场伤停 -> 最终仓位折扣 (2026-09-01).

    在贝叶斯 n_eff 仓位调制之后叠加: 历史数据够不够(n_eff) + 本场阵容行不行(伤停).
    injury_records: 百炼/BSD 结构化伤停 [{side, player, position, status, reason}]
    missing_count: 已统计的缺阵人数(可选, 避免重复解析)
    返回 (discount, veto):
      - 残阵(缺>=8 或 缺>=4且前锋缺2+/门将缺) -> (0.0, True) 禁出
      - 缺>=4 -> ×0.7; 关键位置(前锋/门将)缺 -> 再 ×0.7
      - 无伤停信息 -> (1.0, False) 保持原仓位
    """
    if injury_records is None:
        injury_records = []
    if missing_count is None:
        outs = [r for r in injury_records
                if str(r.get("status", "")).lower() in ("out", "缺阵", "out ")]
        missing_count = len(outs)
    if missing_count <= 0:
        return 1.0, False
    # 关键位置(前锋F/门将G)缺阵统计
    if injury_records:
        outs = [r for r in injury_records
                if str(r.get("status", "")).lower() in ("out", "缺阵", "out ")]
        f_missing = sum(1 for r in outs if str(r.get("position", "")).upper() == "F")
        g_missing = sum(1 for r in outs if str(r.get("position", "")).upper() == "G")
    else:
        f_missing = g_missing = 0
    key_missing = bool(f_missing >= 2 or g_missing >= 1)
    # 残阵: 缺>=8 或 (缺>=4 且 关键位置崩)
    if missing_count >= 8 or (missing_count >= 4 and key_missing):
        return 0.0, True
    d = 1.0
    if missing_count >= 4:
        d *= 0.7
    if key_missing:
        d *= 0.7
    return d, False


def apply_strategy(df: pd.DataFrame, est_cols=("ph", "pd", "pa"),
                   odds_cols=("odds_h", "odds_d", "odds_a"),
                   settle_odds_cols: tuple = None,
                   min_edge: float = None, daily_loss_stop: float = None,
                   devig_method: str = "shin") -> pd.DataFrame:
    """对含模型概率与市场赔率的比赛表生成投注建议。

    规则: 模型概率 > 市场去水概率 + min_edge 才出手；赔率按 SHIN 去水。
    devig_method: devig_1x2 去水方式("shin" 默认 / "proportional" 简单归一 / "power")，
    供回测对比去水口径。
    风控: 当日累计净亏损(负 profit 绝对值)达到 daily_loss_stop(总资金比例)
    后, 当日剩余注全部跳过。stake 为总资金比例, profit 同单位。
    返回追加列: edge, stake, odds_pick, pick, profit(结算后)

    settle_odds_cols: 结算用赔率列(默认=odds_cols)。用于"开盘选注 + 收盘价结算"
    对照 —— EV/edge 用 odds_cols(开盘), 命中结算用 settle_odds_cols(收盘),
    量化"开盘 vs 实盘可成交价"的水位摩擦。
    """
    from devig import devig_1x2
    settle_odds_cols = settle_odds_cols if settle_odds_cols is not None else odds_cols
    min_edge = min_edge if min_edge is not None else STRATEGY["min_edge"]
    daily_loss_stop = daily_loss_stop if daily_loss_stop is not None \
        else STRATEGY.get("daily_loss_stop", 0.20)
    out = df.copy()
    edges, stakes, picks, odds_pick, profits = [], [], [], [], []
    day_loss: dict = {}  # date -> 当日累计亏损(总资金比例)
    for _, r in out.iterrows():
        est = np.array([r[c] for c in est_cols], dtype=float)
        if not np.all(np.isfinite(est)) or est.sum() <= 0:
            edges.append(np.nan); stakes.append(0.0); picks.append(None)
            odds_pick.append(np.nan); profits.append(0.0)
            continue
        est = est / est.sum()
        o = np.array([r[c] for c in odds_cols], dtype=float)
        if not np.all(np.isfinite(o)) or np.any(o <= 1.0):
            edges.append(np.nan); stakes.append(0.0); picks.append(None)
            odds_pick.append(np.nan); profits.append(0.0)
            continue
        try:
            mkt = np.array(devig_1x2(*o, method=devig_method))
        except ValueError:
            edges.append(np.nan); stakes.append(0.0); picks.append(None)
            odds_pick.append(np.nan); profits.append(0.0)
            continue
        edge = est - mkt
        idx = int(np.argmax(edge))
        if edge[idx] >= min_edge:
            stake = kelly_fraction(est[idx], o[idx])
            neff = r.get("n_eff")
            if neff is not None:
                stake = confidence_modulate(stake, neff)
            if stake <= 0:
                edges.append(edge[idx]); stakes.append(0.0); picks.append(None)
                odds_pick.append(o[idx]); profits.append(0.0)
            else:
                d = r.get("date")
                # 单日止损: 当日已亏损达阈值 -> 跳过当日剩余注
                stopped = daily_loss_stop > 0 and d is not None and \
                    pd.notna(d) and day_loss.get(d, 0.0) >= daily_loss_stop
                if stopped:
                    edges.append(edge[idx]); stakes.append(0.0); picks.append(None)
                    odds_pick.append(o[idx]); profits.append(0.0)
                    continue
                edges.append(edge[idx]); stakes.append(stake)
                picks.append(idx); odds_pick.append(o[idx])
                # 结算(仅当已知比分) —— 用结算价 settle_odds_cols(默认=开盘价)
                so = np.array([r[c] for c in settle_odds_cols], dtype=float)
                if not np.all(np.isfinite(so)) or so[idx] <= 1.0:
                    # 结算价缺失/无效: 按开盘价结算(不剔除, 保证样本量)
                    so = o
                if pd.notna(r.get("hg")) and pd.notna(r.get("ag")):
                    actual = 0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2)
                    pft = stake * (so[idx] - 1.0) if actual == idx else -stake
                    profits.append(pft)
                    if pft < 0 and d is not None and pd.notna(d):
                        day_loss[d] = day_loss.get(d, 0.0) + (-pft)
                else:
                    profits.append(np.nan)
        else:
            edges.append(edge[idx]); stakes.append(0.0); picks.append(None)
            odds_pick.append(np.nan); profits.append(0.0)
    out["edge"] = edges
    out["stake"] = stakes
    out["pick"] = picks
    out["odds_pick"] = odds_pick
    out["profit"] = profits
    return out


# ---------------- 串关 ----------------

def leg_correlation(leg1: dict, leg2: dict) -> float:
    """两腿相关性粗估。同联赛同天最高，同联赛次之，仅同天更低。"""
    same_league = leg1.get("league") == leg2.get("league")
    same_day = leg1.get("date") == leg2.get("date")
    if same_league and same_day:
        return 0.30
    if same_league:
        return 0.15
    if same_day:
        return 0.05
    return 0.0


def parlay_prob(leg_probs: list[float], corr_pairs: list[float]) -> float:
    """组合概率：独立乘积再按相关性上修/下修。

    corr_pairs 为逐对相关性；组合概率近似 p_eff = prod(p_i) * prod(1 + c_ij * (1-p_i)*(1-p_j))
    """
    p = float(np.prod(leg_probs))
    for c in corr_pairs:
        p *= 1.0 + c
    return float(np.clip(p, 0.0, 1.0))


def check_parlay(legs: list[dict], max_legs: int = None, max_corr: float = None) -> tuple[bool, str]:
    """串关准入检查：腿数、最低概率、两两相关性、避免同场。"""
    max_legs = max_legs or STRATEGY["max_parlay_legs"]
    max_corr = max_corr if max_corr is not None else STRATEGY["max_corr"]
    if len(legs) < 2:
        return False, "至少需要2腿"
    if len(legs) > max_legs:
        return False, f"超过最大腿数{max_legs}"
    for i, lg in enumerate(legs):
        if lg.get("prob", 0) < STRATEGY["min_prob"]:
            return False, f"腿{i+1}概率过低(<{STRATEGY['min_prob']:.2f})"
        for j in range(i + 1, len(legs)):
            if lg.get("match") and lg["match"] == legs[j].get("match"):
                return False, "同一场比赛不能重复入串"
            c = leg_correlation(lg, legs[j])
            if c > max_corr:
                return False, f"腿{i+1}与腿{j+1}相关性{c:.2f}超过上限{max_corr}"
    return True, "ok"


def parlay_stake(parlay_p: float, parlay_odds: float, kelly_frac: float = None) -> float:
    """串关整体凯利仓位。"""
    return kelly_fraction(parlay_p, parlay_odds, kelly_frac)


def _self_test():
    assert abs(ev(0.55, 2.0) - 0.10) < 1e-9
    # 50% 概率 2.0 赔率无优势
    assert kelly_fraction(0.5, 2.0) == 0.0
    # 55% 概率 2.0 赔率 25%凯利
    f = kelly_fraction(0.55, 2.0)
    assert abs(f - 0.025) < 1e-9, f
    assert check_parlay([
        {"league": "E0", "date": "2024-01-01", "prob": 0.5, "match": "m1"},
        {"league": "SP1", "date": "2024-01-01", "prob": 0.5, "match": "m2"},
    ]) == (True, "ok")
    ok, msg = check_parlay([
        {"league": "E0", "date": "2024-01-01", "prob": 0.5, "match": "m1"},
        {"league": "E0", "date": "2024-01-01", "prob": 0.5, "match": "m2"},
    ])
    assert not ok, msg
    # 连续仓位调制: 无数据不调制 / 平滑缩放 / 无样本不下注
    assert confidence_modulate(0.05, None) == 0.05
    assert abs(confidence_modulate(0.05, 15, k=10) - 0.05 * 15 / 25) < 1e-9
    assert abs(confidence_modulate(0.05, 1, k=10) - 0.05 * 1 / 11) < 1e-9
    assert confidence_modulate(0.05, 0, k=10) == 0.0
    assert confidence_modulate(0.05, 30, k=10) > confidence_modulate(0.05, 5, k=10)
    print("== strategy 自检通过 ==")


if __name__ == "__main__":
    _self_test()
