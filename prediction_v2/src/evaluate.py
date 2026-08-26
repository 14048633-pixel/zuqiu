"""评估 —— 指标、校准、基准对比。

指标口径（全部诚实标注）：
  - ROI = 总盈亏 / 总投入（含走水按结算处理）
  - 命中率 = 赢注 / 有结果注（走水不计）
  - LogLoss / Brier / ECE 在"全部测试比赛"上计算（不只下注的比赛）
  - 基准对比：市场热门(开盘价) 1 单位平注
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd


def log_loss_binary(p, y):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def brier_score(probs, y):
    """多分类 Brier。probs: (n,3) 列序 [away, draw, home]。"""
    y_onehot = np.zeros_like(probs)
    y_onehot[np.arange(len(y)), y] = 1.0
    return float(((probs - y_onehot) ** 2).sum(axis=1).mean())


def ece(probs, y, bins=10):
    """期望校准误差（二值化，按列取概率）。"""
    p = np.asarray(probs, float)
    y = np.asarray(y, float)
    edges = np.linspace(0, 1, bins + 1)
    errs = []
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1])
        if mask.sum() < 5:
            continue
        errs.append(abs(p[mask].mean() - y[mask].mean()))
    return float(np.mean(errs)) if errs else float("nan")


def summarize(bets: pd.DataFrame, preds: pd.DataFrame, cfg: dict) -> dict:
    mk = cfg["markets"]
    out = {"config": cfg}

    # ---------- 投注汇总 ----------
    if len(bets):
        bets = bets.copy()
        total_stake = bets["stake"].sum()
        decided = bets[bets["settle"] != 0]
        win_rate = float((bets["settle"] > 0).mean())
        push_rate = float((bets["settle"] == 0).mean())
        # 平注口径（每注1单位，不受凯利复利放大）
        bets["flat_profit_open"] = bets.apply(
            lambda r: r["settle"] * (r["odds_open"] - 1) if r["settle"] > 0 else r["settle"], axis=1)
        out["bets"] = {
            "n": int(len(bets)),
            "total_stake": round(total_stake, 2),
            "win_rate": round(win_rate, 4),
            "push_rate": round(push_rate, 4),
            "roi_open": round(float(bets["profit_open"].sum() / total_stake), 4),
            "roi_close": round(float(bets["profit_close"].sum() / total_stake), 4),
            "roi_flat_open": round(float(bets["flat_profit_open"].mean()), 4),
            "profit_open": round(float(bets["profit_open"].sum()), 2),
            "profit_close": round(float(bets["profit_close"].sum()), 2),
            "flat_profit_open": round(float(bets["flat_profit_open"].sum()), 2),
            "avg_edge": round(float(bets["edge"].mean()), 4),
            "n_decided": int(len(decided)),
            "decided_win_rate": round(float((decided["settle"] > 0).mean()), 4) if len(decided) else None,
        }
        # 分市场
        out["by_market"] = {}
        for m, g in bets.groupby("market"):
            out["by_market"][m] = {
                "n": int(len(g)),
                "roi_open": round(float(g["profit_open"].sum() / g["stake"].sum()), 4),
                "roi_close": round(float(g["profit_close"].sum() / g["stake"].sum()), 4),
                "win_rate": round(float((g["settle"] > 0).mean()), 4),
            }
        # 分年度
        bets = bets.copy()
        bets["year"] = pd.to_datetime(bets["date"]).dt.year
        out["by_year"] = {}
        for y, g in bets.groupby("year"):
            out["by_year"][int(y)] = {
                "n": int(len(g)),
                "roi_open": round(float(g["profit_open"].sum() / g["stake"].sum()), 4),
            }
        # 资金曲线（平注累计盈亏，避免凯利复利放大的失真）
        flat_curve = np.concatenate([[0.0], bets["flat_profit_open"].cumsum().values])
        out["bankroll"] = {
            "start": mk["initial_bankroll"],
            "end_kelly": round(mk["initial_bankroll"] + bets["profit_open"].sum(), 2),
            "flat_total_profit": round(float(bets["flat_profit_open"].sum()), 2),
            "max_drawdown_flat": round(_max_drawdown(flat_curve), 4),
            "note": "平注累计盈亏为可信口径；凯利资金按10%上限复利会指数放大，绝对值仅供参考",
        }
    else:
        out["bets"] = {"n": 0}

    # ---------- 全量预测质量（所有测试比赛） ----------
    if len(preds):
        p = preds.dropna(subset=["p_home", "p_draw", "p_away"])
        y = p["target"].values.astype(int)
        probs = np.column_stack([p["p_away"].values, p["p_draw"].values, p["p_home"].values])
        probs = np.clip(probs, 1e-9, 1 - 1e-9)
        probs /= probs.sum(axis=1, keepdims=True)
        ll_model = float(-np.log(probs[np.arange(len(y)), y]).mean())
        brier = brier_score(probs, y)
        ece_vals = [ece(probs[:, c], (y == c).astype(float)) for c in range(3)]
        out["preds"] = {
            "n": int(len(p)),
            "logloss_model": round(ll_model, 4),
            "brier_model": round(brier, 4),
            "ece_home": round(ece_vals[2], 4),
            "ece_draw": round(ece_vals[1], 4),
            "ece_away": round(ece_vals[0], 4),
        }
        # 市场 LogLoss（有市场概率的行）
        m = p.dropna(subset=["m_home", "m_draw", "m_away"])
        if len(m):
            ym = m["target"].values.astype(int)
            mprobs = np.column_stack([m["m_away"].values, m["m_draw"].values, m["m_home"].values])
            mprobs = np.clip(mprobs, 1e-9, 1 - 1e-9)
            mprobs /= mprobs.sum(axis=1, keepdims=True)
            out["preds"]["logloss_market"] = round(float(-np.log(mprobs[np.arange(len(ym)), ym]).mean()), 4)
            out["preds"]["brier_market"] = round(brier_score(mprobs, ym), 4)

    # ---------- 市场基准 ----------
    out["baseline_market_favorite"] = _market_favorite_baseline(preds)
    return out


def _market_favorite_baseline(preds: pd.DataFrame) -> dict:
    """每场押去水后的市场热门（开盘价，精确赔率），1 单位平注。"""
    if preds.empty:
        return {"n": 0}
    p = preds.dropna(subset=["m_fav", "m_fav_odds"]).copy()
    if p.empty:
        return {"n": 0}
    fav_map = {"away": 0, "draw": 1, "home": 2}
    p["fav"] = p["m_fav"].map(fav_map)
    p = p.dropna(subset=["fav"])
    p["fav_target"] = p["target"].astype(int).values == p["fav"].astype(int).values
    profit = np.where(p["fav_target"], p["m_fav_odds"] - 1.0, -1.0)
    return {
        "n": int(len(p)),
        "win_rate": round(float(p["fav_target"].mean()), 4),
        "roi": round(float(profit.mean()), 4),
    }


def _max_drawdown(curve: np.ndarray) -> float:
    """按百分比回撤；峰值<=0 时无意义返回 0。"""
    peak = np.maximum.accumulate(curve)
    pos = peak > 1e-9
    if not pos.any():
        return 0.0
    dd = np.where(pos, (curve - peak) / np.where(pos, peak, 1.0), 0.0)
    return float(-dd.min()) if len(dd) else 0.0


def print_report(report: dict):
    print("=" * 66)
    print("  回测报告")
    print("=" * 66)
    b = report.get("bets", {})
    if b.get("n", 0):
        print(f"  投注数: {b['n']}")
        print(f"  命中率(含半赢): {b['win_rate']:.1%}  走水率: {b['push_rate']:.1%}")
        print(f"  平注ROI@开盘: {b.get('roi_flat_open', float('nan')):+.2%}  (主口径, 每注1单位)")
        print(f"  凯利ROI@开盘: {b['roi_open']:+.2%}   @收盘: {b['roi_close']:+.2%}")
        print(f"  平注累计盈亏: {b.get('flat_profit_open', 0):+.2f}")
        bk = report.get("bankroll", {})
        if bk:
            print(f"  平注累计盈亏: {bk.get('flat_total_profit', 0):+.2f}  平注最大回撤: {bk.get('max_drawdown_flat', 0):.1%}")
        print("\n  分市场:")
        for m, g in report.get("by_market", {}).items():
            print(f"    {m:<6} n={g['n']:<5} ROI开盘={g['roi_open']:+.2%} ROI收盘={g['roi_close']:+.2%} 命中={g['win_rate']:.1%}")
        print("\n  分年度 ROI@开盘:")
        for y, g in report.get("by_year", {}).items():
            print(f"    {y}: n={g['n']:<4} {g['roi_open']:+.2%}")
    else:
        print("  无投注")
    pr = report.get("preds", {})
    if pr:
        print("\n  全量预测质量（所有测试比赛）:")
        print(f"    样本: {pr['n']}")
        print(f"    模型 LogLoss: {pr.get('logloss_model')}  市场 LogLoss: {pr.get('logloss_market')}")
        print(f"    模型 Brier: {pr.get('brier_model')}  市场 Brier: {pr.get('brier_market')}")
        print(f"    ECE: home={pr.get('ece_home')} draw={pr.get('ece_draw')} away={pr.get('ece_away')}")
    fb = report.get("baseline_market_favorite", {})
    if fb.get("n", 0):
        print(f"\n  市场基准(押热门@开盘, 1单位): n={fb['n']} 命中={fb['win_rate']:.1%} ROI={fb['roi']:+.2%}")


def save_report(report: dict, path: str):
    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_clean(x) for x in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (pd.Timestamp,)):
            return str(o)
        return o
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_clean(report), f, ensure_ascii=False, indent=2, default=str)
