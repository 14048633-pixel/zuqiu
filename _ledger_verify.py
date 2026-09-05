# -*- coding: utf-8 -*-
"""实盘账本验证工具: bet_ledger.csv 口径清洗 + 扫描矩阵检测 + 真实下注模拟。

用途: 校验"实盘数据"是真实下注账本还是全方向扫描矩阵, 并用真实下注口径
(每场只下最优方向)计算 ROI。避免把对冲式扫描记录误读为下注收益。

用法: python football_analyzer/_ledger_verify.py <csv路径>
默认路径: D:\\足球分析\\analysis_records\\bet_ledger.csv
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

DEFAULT = r"D:\足球分析\analysis_records\bet_ledger.csv"


def settle_pnl(r) -> float:
    """单位本金收益: win=odds-1, lose=-1, push=0, half≈(odds-1)/2。"""
    if r["result"] == "win":
        return r["odds"] - 1.0
    if r["result"] == "lose":
        return -1.0
    if r["result"] == "push":
        return 0.0
    if r["result"] == "half":
        return (r["odds"] - 1.0) / 2.0
    return np.nan


def is_scan_matrix(cand: pd.DataFrame) -> tuple[bool, dict]:
    """检测是否全方向扫描矩阵: 同一场覆盖 1X2 三方向且恰好一个 win。"""
    x12 = cand[cand["bet_name"].str.contains("1X2")]
    g = x12.groupby(["date", "match"])["bet_name"].nunique()
    n3 = int((g == 3).sum())
    ok = int(x12.groupby(["date", "match"])
             .apply(lambda grp: (grp["result"] == "win").sum() == 1).sum())
    per_match = cand.groupby(["date", "match"]).size()
    return (n3 == len(g) and len(g) > 0), {
        "1X2三方向齐全场次": n3, "1X2总场次": len(g),
        "每场恰好一win场次": ok, "场均注数": round(per_match.mean(), 2),
    }


def run(path: str) -> None:
    df = pd.read_csv(path, encoding="utf-8-sig")
    print(f"总记录: {len(df)}")
    cand = df[(df["status"] == "已结算") & (df["veto"] != 1) &
              (df["result"].isin(["win", "lose", "push", "half"]))].copy()
    cand["pnl_calc"] = cand.apply(settle_pnl, axis=1)
    n_match = cand.groupby(["date", "match"]).ngroups
    print(f"有效已结算注: {len(cand)} 注 / {n_match} 场")

    is_scan, det = is_scan_matrix(cand)
    print(f"\n== 扫描矩阵检测 ==")
    print(f"  {'是(同一场多方向对冲, 非真实下注)' if is_scan else '否(疑似真实下注)'}: {det}")
    if cand["bookmaker"].notna().any() or cand["placed_odds"].notna().any():
        print(f"  含真实成交字段: bookmaker={cand['bookmaker'].notna().sum()} "
              f"placed_odds={cand['placed_odds'].notna().sum()}")
    else:
        print("  bookmaker/placed_odds 全空 -> 无真实成交记录")

    print(f"\n== 真实下注模拟(每场只下最优方向) ==")
    for label, sub, evg in [
        ("每场EV最高", cand, None),
        ("EV>0才下", cand[cand["ev"] > 0], None),
        ("高价值/标准tier", cand[cand["ev_tier"].isin(["高价值", "标准"])], None),
    ]:
        b = sub.sort_values("ev", ascending=False).groupby(["date", "match"]).first()
        n = len(b)
        if n == 0:
            continue
        r = b["pnl_calc"].sum() / n
        se = b["pnl_calc"].std() / np.sqrt(n)
        wins = (b["result"] == "win").sum()
        print(f"  {label}: n={n} ROI={r:+.2%} win={wins/n:.1%} "
              f"95%CI=[{r-1.96*se:+.1%},{r+1.96*se:+.1%}] t={r/se:.2f}")

    print(f"\n== 校准: 模型概率分箱 vs 实际win率 ==")
    c2 = cand[cand["prob"].notna()]
    pbins = [0, 0.45, 0.55, 0.65, 0.75, 0.9, 1.01]
    c2["pb"] = pd.cut(c2["prob"], bins=pbins, right=False)
    for b, g in c2.groupby("pb", observed=True):
        w = (g["result"] == "win").sum() / len(g)
        print(f"  prob {b}: n={len(g):>3} win={w:>6.1%} avg={g['prob'].mean():.3f}")

    vetoed = df[(df["status"] == "已结算") & (df["veto"] == 1) &
                (df["result"].isin(["win", "lose", "push", "half"]))].copy()
    if len(vetoed):
        vr = vetoed.apply(settle_pnl, axis=1).sum() / len(vetoed)
        print(f"\n== 风控否决对照 ==")
        print(f"  被否决注 n={len(vetoed)} ROI={vr:+.2%} (若下注会怎样)")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
