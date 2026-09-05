# -*- coding: utf-8 -*-
"""资金曲线 / 生存率模拟 (bootstrap 重采样).
输入: D:\\足球分析\\analysis_records\\bet_ledger.csv (实盘账本)
口径: 严格可下注样本 = status已结算 & veto!=1 & stake_factor>0 & result in (win/lose/push/half)
方法: 有放回重采样生成 N 个虚拟赛季, 每赛季按真实系统风控跑完整下注序列.
风控复现 (config.STRATEGY):
  - 每注仓位 = Kelly(prob, odds) × 0.25, 封顶 5% 资金
  - 单日止损: 当日累计亏损 >= 20% 资金 -> 当日剩余注跳过
结算: win=+stake*(odds-1), lose=-stake, push=0, half=+0.5*stake*(odds-1)

用法: python bankroll_sim.py [--seasons 1000] [--seed 42]
"""
from __future__ import annotations

import argparse
import io
import os
import sys

import numpy as np
import pandas as pd

LEDGER = r"D:\足球分析\analysis_records\bet_ledger.csv"
INIT_BANK = 100.0
KELLY_FRAC = 0.25
MAX_STAKE_PCT = 0.05
DAILY_LOSS_STOP = 0.20


def load_real_samples() -> pd.DataFrame:
    """加载并筛选真实可下注样本."""
    df = pd.read_csv(LEDGER, encoding="utf-8-sig")
    mask = (
        (df["status"] == "已结算")
        & (df["veto"] != 1)
        & (df["stake_factor"] > 0)
        & df["result"].isin(["win", "lose", "push", "half"])
    )
    real = df[mask].copy()
    # 规范化 date (存在脏值)
    real["date"] = pd.to_datetime(real["date"], errors="coerce")
    return real


def settle_return(row) -> float:
    """单注每单位下注的收益率 (+1 全赢, -1 全输, 0 走水, half 半赢)."""
    r = row["result"]
    if r == "win":
        return float(row["odds"]) - 1.0
    if r == "lose":
        return -1.0
    if r == "push":
        return 0.0
    if r == "half":
        return 0.5 * (float(row["odds"]) - 1.0)
    return 0.0


def kelly_stake(prob: float, odds: float) -> float:
    """分数凯利仓位(资金比例), 复现 strategy.kelly_fraction."""
    b = odds - 1.0
    if b <= 0 or not np.isfinite(prob):
        return 0.0
    f = (prob * b - (1.0 - prob)) / b
    if f <= 0:
        return 0.0
    return min(f * KELLY_FRAC, MAX_STAKE_PCT)


def run_season(sample: pd.DataFrame, rng: np.random.Generator) -> dict:
    """跑一个赛季 (有放回抽 len(sample) 场), 按真实风控下注. 返回赛季统计."""
    n = len(sample)
    idx = rng.integers(0, n, size=n)
    season = sample.iloc[idx].reset_index(drop=True)

    bank = INIT_BANK
    peak = INIT_BANK
    max_drawdown = 0.0
    day_loss: dict = {}
    bets = 0
    wins = 0
    staked_total = 0.0
    profit_total = 0.0

    for _, row in season.iterrows():
        prob = float(row.get("prob", np.nan))
        odds = float(row["odds"])
        stake_pct = kelly_stake(prob, odds)
        if stake_pct <= 0:
            continue
        # 单日止损
        d = row["date"]
        if pd.notna(d) and day_loss.get(d, 0.0) >= DAILY_LOSS_STOP:
            continue
        stake = bank * stake_pct
        ret = settle_return(row)
        profit = stake * ret
        bank += profit
        if profit < 0 and pd.notna(d):
            day_loss[d] = day_loss.get(d, 0.0) + (-profit)
        bets += 1
        if ret > 0:
            wins += 1
        staked_total += stake
        profit_total += profit
        peak = max(peak, bank)
        dd = (peak - bank) / peak if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, dd)

    return {
        "final_bank": bank,
        "roi": profit_total / staked_total if staked_total > 0 else np.nan,
        "max_drawdown": max_drawdown,
        "bets": bets,
        "win_rate": wins / bets if bets > 0 else np.nan,
        "bankrupt": bank <= INIT_BANK * 0.3,  # 定义破产: 资金跌破初始30%
    }


def run_bootstrap(sample: pd.DataFrame, seasons: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(seasons):
        out.append(run_season(sample, rng))
    return out


def pct(x: np.ndarray, q: float) -> float:
    return float(np.nanpercentile(x, q))


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    real = load_real_samples()
    n = len(real)
    print(f"== 真实可下注样本: {n} 场 ==")
    print(f"   result: {dict(real['result'].value_counts())}")
    print(f"   平均赔率: {real['odds'].mean():.3f}  平均胜率(win/有效): "
          f"{(real['result']=='win').sum()}/{((real['result']=='win')|(real['result']=='lose')|(real['result']=='half')).sum()}")
    sample_roi = real.apply(settle_return, axis=1).mean()
    print(f"   样本每注平均收益率: {sample_roi:+.2%}  (每注等额1单位口径)")
    print()

    print(f"== Bootstrap {args.seasons} 赛季 (有放回, seed={args.seed}) ==")
    print("风控: Kelly0.25 / 单注上限5% / 单日止损20% / 初始资金100")
    sims = run_bootstrap(real, args.seasons, args.seed)
    fin = np.array([s["final_bank"] for s in sims])
    roi = np.array([s["roi"] for s in sims if np.isfinite(s["roi"])])
    dd = np.array([s["max_drawdown"] for s in sims])
    wr = np.array([s["win_rate"] for s in sims if np.isfinite(s["win_rate"])])
    bankrupt = sum(1 for s in sims if s["bankrupt"]) / len(sims)
    bets_arr = np.array([s["bets"] for s in sims])

    print(f"\n--- 赛季资金(初始100) ---")
    print(f"   P05={pct(fin,5):6.1f}  P25={pct(fin,25):6.1f}  P50(中位)={pct(fin,50):6.1f}  "
          f"P75={pct(fin,75):6.1f}  P95={pct(fin,95):6.1f}")
    print(f"   平均最终资金: {fin.mean():.1f}   (资金翻倍概率: {(fin>=200).mean():.1%})")
    print(f"   资金>=100(不亏): {(fin>=100).mean():.1%}   资金>=70: {(fin>=70).mean():.1%}")
    print(f"   平均每赛季下注: {bets_arr.mean():.0f} 场")

    print(f"\n--- 赛季ROI ---")
    print(f"   P05={pct(roi,5):+.1%}  P50={pct(roi,50):+.1%}  P95={pct(roi,95):+.1%}  均值={roi.mean():+.1%}")

    print(f"\n--- 风险 ---")
    print(f"   破产概率(跌破初始30%): {bankrupt:.1%}")
    print(f"   最大回撤 P50={pct(dd,50):.1%}  P95={pct(dd,95):.1%}")
    print(f"   赛季命中率 P50={pct(wr,50):.1%}  区间[P05,P95]=[{pct(wr,5):.1%},{pct(wr,95):.1%}]")


if __name__ == "__main__":
    main()
