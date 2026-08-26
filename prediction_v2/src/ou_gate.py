# -*- coding: utf-8 -*-
"""大小球信号闸门 (ou_gate)

在模型概率之上追加两道闸, 用于最终信号输出前过滤:
  1) 联赛基准闸: prob_small 必须显著高于该联赛"近30轮"小球自然占比(+6pt)
  2) 信号频率闸: 同联赛赛前最近15场里小球信号占比 < 65% (防信号扎堆/过度下注)

修正点(相对原始伪码):
  - 所有统计严格按 (联赛, 开赛日) 滚动, 只用开赛日之前的比赛 -> 无未来函数
  - 大球侧对称: 用大球自身滚动占比, 不再借用小球占比
  - 增加市场闸: 模型概率还必须打穿市场隐含概率(+5pt), 否则"高概率"可能已被市场定价
  - prob_big 用 1 - prob_small (大小球是二元市场), 不引入第二个独立预测

用法:
  from ou_gate import OuGate
  gate = OuGate(data_dir)
  v = gate.evaluate(league, match_date, prob_small, market_prob, odds)
  v["verdict"] -> "small" / "big" / "none"
"""
from __future__ import annotations

import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.normpath(os.path.join(HERE, "..", "output"))
DEFAULT_BETS = os.path.join(OUTPUT_DIR, "bets_poisson_all_edgecfg.csv")

# 闸门参数
BASELINE_WINDOW = 30    # 联赛小球自然占比窗口(场)
SIGNAL_WINDOW = 15      # 滚动信号占比窗口(场)
BASELINE_LIFT = 0.06    # 相对联赛基准的最小提升(用户原始口径)
MARKET_LIFT = 0.05      # 相对市场隐含概率的最小提升(修正: 防"已被定价")
RATIO_CAP = 0.65        # 滚动信号占比上限
MIN_SAMPLE = 8          # 窗口最少样本, 不足则不设该闸(不误杀)
SIGNAL_EDGE = 0.05      # 历史"信号"判定: 与生产口径一致 edge>=5%


def _load_data(data_dir: str, bets_csv: str = DEFAULT_BETS):
    """加载比赛结果(算联赛基准) + 历史信号(算滚动占比)。"""
    from data_loader import load_football_data
    results = load_football_data(data_dir)
    results["total"] = results["FTHG"] + results["FTAG"]
    bets = pd.read_csv(bets_csv)
    bets["date"] = pd.to_datetime(bets["date"], errors="coerce")
    bets = bets.dropna(subset=["date"])
    ou = bets[bets["side"].isin(["under", "over"])].copy()
    return results, ou


class OuGate:
    """大小球信号闸门。所有统计截止到开赛日之前, 无未来函数。"""

    def __init__(self, data_dir: str, bets_csv: str = DEFAULT_BETS):
        self.results, self.ou = _load_data(data_dir, bets_csv)

    def trailing_small_baseline(self, league: str, match_date,
                                window: int = BASELINE_WINDOW):
        """该联赛截至开赛日前最近 N 场小球自然占比(总进球<=2)。不足样本返回 None。"""
        sub = self.results[(self.results["league"] == league)
                           & (self.results["Date"] < match_date)]
        sub = sub.sort_values("Date").tail(window)
        if len(sub) < MIN_SAMPLE:
            return None
        return float((sub["total"] <= 2).mean())

    def trailing_signal_ratio(self, league: str, match_date, side: str,
                              window: int = SIGNAL_WINDOW):
        """该联赛截至开赛日前最近 N 场中 side(under/over) 信号占比。

        信号判定 = 历史该侧记录且 edge>=5%(与生产口径一致)。
        不足样本返回 None(该闸不生效)。
        """
        sub = self.ou[(self.ou["league"] == league)
                      & (self.ou["date"] < match_date)]
        sub = sub.sort_values("date").tail(window)
        if len(sub) < MIN_SAMPLE:
            return None
        return float(((sub["side"] == side) & (sub["edge"] >= SIGNAL_EDGE)).mean())

    def evaluate(self, league: str, match_date, prob_small: float,
                 market_prob: float, odds: float,
                 baseline_lift: float = BASELINE_LIFT,
                 market_lift: float = MARKET_LIFT,
                 ratio_cap: float = RATIO_CAP) -> dict:
        """核心闸门(修正版)。返回 verdict 与各闸明细。"""
        prob_small = float(prob_small)
        prob_big = 1.0 - prob_small
        market_big = 1.0 - float(market_prob)
        base_small = self.trailing_small_baseline(league, match_date)
        r_small = self.trailing_signal_ratio(league, match_date, "under")
        r_big = self.trailing_signal_ratio(league, match_date, "over")

        # 修正版阈值: 联赛基准 + 市场, 取更高者
        th_small = max(base_small + baseline_lift, market_prob + market_lift) \
            if base_small is not None else market_prob + market_lift
        th_big = max((1.0 - base_small) + baseline_lift, market_big + market_lift) \
            if base_small is not None else market_big + market_lift

        small_base_ok = prob_small > base_small + baseline_lift
        small_mkt_ok = prob_small > market_prob + market_lift
        small_freq_ok = r_small is None or r_small < ratio_cap
        big_base_ok = prob_big > (1.0 - base_small) + baseline_lift
        big_mkt_ok = prob_big > market_big + market_lift
        big_freq_ok = r_big is None or r_big < ratio_cap

        # 原伪码口径(只做对照, 不参与最终判定)
        orig_verdict = "none"
        if base_small is not None:
            if prob_small > base_small + baseline_lift and (r_small is None or r_small < ratio_cap):
                orig_verdict = "small"
            elif prob_big > (1.0 - base_small) + baseline_lift:
                orig_verdict = "big"

        if small_base_ok and small_mkt_ok and small_freq_ok:
            verdict = "small"
        elif big_base_ok and big_mkt_ok and big_freq_ok:
            verdict = "big"
        else:
            verdict = "none"

        return {
            "verdict": verdict,
            "orig_verdict": orig_verdict,
            "prob_small": prob_small, "prob_big": prob_big,
            "market_small": market_prob, "market_big": market_big,
            "odds": float(odds),
            "baseline_small": base_small,
            "baseline_big": None if base_small is None else 1.0 - base_small,
            "threshold_small": th_small, "threshold_big": th_big,
            "recent_small_ratio": r_small, "recent_big_ratio": r_big,
            "checks": {
                "small_base_ok": small_base_ok, "small_mkt_ok": small_mkt_ok,
                "small_freq_ok": small_freq_ok,
                "big_base_ok": big_base_ok, "big_mkt_ok": big_mkt_ok,
                "big_freq_ok": big_freq_ok,
            },
        }
