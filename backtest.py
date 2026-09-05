# -*- coding: utf-8 -*-
"""严格 walk-forward 回测。

防未来泄露要点:
  1. 特征一次性按日期因果构建(每场只用此前数据)
  2. 每个窗口只用 [cutoff-train_days, cutoff) 训练
  3. 校准只用训练窗口内最后 20%(验证切片)
  4. 测试窗口 [cutoff, cutoff+test_days) 只做预测与结算
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from config import MODEL, STRATEGY
from features import build_features, FEATURE_COLS
from model import (poisson_fit, poisson_1x2_probs, train_xgb,
                   predict_proba_xgb, calibrate_platt, calibrate_apply)
from strategy import apply_strategy


def _blend(pp: pd.DataFrame, xp: np.ndarray, w_p: float = 0.5) -> np.ndarray:
    return w_p * pp.values + (1.0 - w_p) * xp


def walk_forward(df: pd.DataFrame, train_days: int = None, test_days: int = None,
                 step_days: int = None, min_edge: float = None,
                 min_train: int = None, start: pd.Timestamp = None,
                 end: pd.Timestamp = None, verbose: bool = True,
                 use_calibration: bool = True,
                 settle: str = "open",
                 devig_method: str = "shin") -> tuple[pd.DataFrame, dict]:
    """返回 (bets_df, summary)。

    settle: "open" = 按开盘价结算; "close" = 按临场/收盘价结算(odds_*_close 列,
    缺失时回退开盘价)。用于量化"开盘 vs 实盘可成交价"的差异。
    devig_method: 透传给 apply_strategy 去水方式(回测对比用)。
    """
    train_days = train_days or MODEL["train_days"]
    test_days = test_days or MODEL["test_days"]
    step_days = step_days or test_days
    min_train = min_train or MODEL["min_train"]
    min_edge = min_edge if min_edge is not None else STRATEGY["min_edge"]

    df = df.sort_values("date").reset_index(drop=True)
    d0 = df["date"].min()
    d1 = df["date"].max()
    start = start or (d0 + dt.timedelta(days=train_days))
    end = end or (d1 - dt.timedelta(days=1))
    start, end = pd.Timestamp(start), pd.Timestamp(end)

    folds = []
    cutoff = start
    while cutoff < end:
        folds.append(cutoff)
        cutoff += dt.timedelta(days=step_days)

    all_bets = []
    per_fold = []
    pooled = []  # (date, ph, pd, pa, actual, odds_h, odds_d, odds_a)
    for fi, cutoff in enumerate(folds):
        t_lo = cutoff - dt.timedelta(days=train_days)
        t_hi = cutoff + dt.timedelta(days=test_days)
        train = df[(df["date"] >= t_lo) & (df["date"] < cutoff)].copy()
        test = df[(df["date"] >= cutoff) & (df["date"] < t_hi)].copy()
        if len(train) < min_train or len(test) == 0:
            continue
        # 校准切片: 训练窗口最后 20%
        val_cut = train["date"].quantile(0.8)
        val = train[train["date"] >= val_cut].copy()
        tr = train[train["date"] < val_cut].copy()

        try:
            fit = poisson_fit(tr)
            pp_test = poisson_1x2_probs(fit, test)
            model, cols = train_xgb(tr)
            raw_test = predict_proba_xgb(model, test, cols)
            if use_calibration and len(val) >= 200:
                cal = calibrate_platt(model, val, cols)
                xp_test = calibrate_apply(cal, raw_test)
            else:
                xp_test = raw_test
            est = _blend(pp_test, xp_test)
        except Exception as exc:
            if verbose:
                print(f"  fold {cutoff.date()} 失败: {exc}")
            continue

        test = test.copy()
        test["ph"] = est[:, 0]
        test["pd"] = est[:, 1]
        test["pa"] = est[:, 2]
        for _, rr in test.iterrows():
            actual = 0 if rr["hg"] > rr["ag"] else (1 if rr["hg"] == rr["ag"] else 2)
            pooled.append((rr["date"], rr["ph"], rr["pd"], rr["pa"], actual,
                           rr["odds_h"], rr["odds_d"], rr["odds_a"]))
        bets = apply_strategy(test, min_edge=min_edge,
                              settle_odds_cols=(
                                  ("odds_h_close", "odds_d_close", "odds_a_close")
                                  if settle == "close" else None),
                              devig_method=devig_method)
        n_bets = int((bets["stake"] > 0).sum())
        bank = bets.loc[bets["stake"] > 0, "profit"].sum()
        staked = bets.loc[bets["stake"] > 0, "stake"].sum()
        per_fold.append({
            "cutoff": cutoff, "n_train": len(tr), "n_val": len(val),
            "n_test": len(test), "n_bets": n_bets,
            "profit": bank, "staked": staked,
        })
        all_bets.append(bets)
        if verbose:
            print(f"  fold {cutoff.date()} bets={n_bets} profit={bank:.2f} staked={staked:.2f}")

    if all_bets:
        bets = pd.concat(all_bets, ignore_index=True)
    else:
        bets = pd.DataFrame()

    summary = _summarize(bets, per_fold)
    if pooled:
        summary["calibration"] = _calibration_report(pooled)
    return bets, summary


def _calibration_report(pooled: list) -> pd.DataFrame:
    """置信度校准(confidence calibration)。

    对每个置信桶 [a,b]: 桶内"最大预测概率"均值(avg_pred) 应 ≈ 桶内实际命中率
    (actual_rate = 预测的 argmax 类别确实发生的比例)。diff = avg_pred - actual_rate,
    >0 表示该桶过度自信。另附 per-class 校准(各结果类别的预测概率 vs 实际发生率)
    与全局 ECE(Expected Calibration Error = sum(n_bin/N * |diff|), 越小越好)。
    """
    pdf = pd.DataFrame(pooled, columns=["date", "ph", "pd", "pa", "actual",
                                        "odds_h", "odds_d", "odds_a"])
    pdf["max_p"] = pdf[["ph", "pd", "pa"]].max(axis=1)
    pdf["pred_cls"] = pdf[["ph", "pd", "pa"]].values.argmax(axis=1)
    bins = [0, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7, 1.0]
    labels = ["<0.30", "0.30-0.40", "0.40-0.45", "0.45-0.50", "0.50-0.55",
              "0.55-0.60", "0.60-0.70", ">0.70"]
    pdf["bin"] = pd.cut(pdf["max_p"], bins=bins, labels=labels)
    rep = pdf.groupby("bin", observed=True).apply(
        lambda g: pd.Series({
            "n": len(g),
            "avg_pred": g["max_p"].mean(),
            "actual_rate": (g["pred_cls"] == g["actual"]).mean(),
            "diff": g["max_p"].mean() - (g["pred_cls"] == g["actual"]).mean(),
        }), include_groups=False)
    # per-class 校准: 对每类 c, 按"该类预测概率"分桶, 比较平均预测概率 vs 实际发生率
    cls_names = ["主胜", "平局", "客胜"]
    pc_cols = ["ph", "pd", "pa"]
    parts = []
    for c in range(3):
        sub = pd.DataFrame({"p": pdf[pc_cols[c]], "hit": (pdf["actual"] == c).astype(float)})
        sub = sub[sub["p"].notna()]
        if sub.empty:
            continue
        bc = pd.cut(sub["p"], bins=[0, 0.3, 0.4, 0.5, 0.6, 1.0], include_lowest=True)
        g = sub.groupby(bc, observed=True).apply(
            lambda g: pd.Series({
                "cls": cls_names[c], "n": len(g),
                "avg_p": g["p"].mean(), "actual_rate": g["hit"].mean(),
                "diff": g["p"].mean() - g["hit"].mean(),
            }), include_groups=False)
        parts.append(g.reset_index())
    per = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    # 全局 ECE
    N = pdf.shape[0]
    ece = float((rep["n"] / N * rep["diff"].abs()).sum()) if N else np.nan
    rep.attrs["ece"] = ece
    rep.attrs["per_class"] = per
    return rep


def _summarize(bets: pd.DataFrame, per_fold: list) -> dict:
    if bets.empty:
        return {"n_bets": 0, "roi": np.nan, "hit_rate": np.nan}
    active = bets[bets["stake"] > 0].copy()
    n = len(active)
    staked = active["stake"].sum()
    profit = active["profit"].sum()
    hits = active["profit"] > 0
    roi = profit / staked if staked > 0 else np.nan
    # 按年
    active = active.copy()
    active["year"] = active["date"].dt.year
    by_year = active.groupby("year").apply(
        lambda g: pd.Series({
            "bets": len(g), "staked": g["stake"].sum(),
            "profit": g["profit"].sum(),
            "roi": g["profit"].sum() / g["stake"].sum() if g["stake"].sum() > 0 else np.nan,
            "hit": (g["profit"] > 0).mean(),
        }), include_groups=False)
    # 回撤(按时间累计收益)
    active = active.sort_values("date")
    cum = active["profit"].cumsum()
    dd = float((cum.cummax() - cum).max())
    return {
        "n_bets": n,
        "staked": float(staked),
        "profit": float(profit),
        "roi": float(roi) if roi == roi else np.nan,
        "hit_rate": float(hits.mean()),
        "avg_edge": float(active["edge"].mean()) if n else np.nan,
        "max_drawdown": dd,
        "n_folds": len(per_fold),
        "by_year": by_year,
    }


def run_quick_backtest(df: pd.DataFrame = None, **kw) -> tuple[pd.DataFrame, dict]:
    """快速回归回测(小步长/少折)。"""
    if df is None:
        from data_loader import load_master
        df = load_master(include_espn=False)
        df = df[df["odds_h"].notna()].copy()
        print("构建特征...")
        df = build_features(df)
    return walk_forward(df, **kw)


if __name__ == "__main__":
    from data_loader import load_master
    master = load_master(include_espn=False)
    master = master[master["odds_h"].notna()].copy()
    print("加载完成:", len(master), "场; 构建特征...")
    master = build_features(master)
    print("特征完成; 开始回测(快速模式: 训练180天, 测试60天)...")
    bets, summary = walk_forward(master, train_days=180, test_days=60,
                                 step_days=120, min_train=300, use_calibration=True)
    print("== 回测汇总 ==")
    print(f"投注数={summary['n_bets']} ROI={summary['roi']:.2%} 命中率={summary['hit_rate']:.2%} "
          f"最大回撤={summary['max_drawdown']:.2f} 平均边际={summary['avg_edge']:.3f}")
    if summary.get("by_year") is not None and not summary["by_year"].empty:
        print(summary["by_year"].round(3))
