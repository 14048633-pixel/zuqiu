# -*- coding: utf-8 -*-
"""主客场比分分层: 基于 poisson_fit 的主客场分离强度 + 最近主客场战绩。

输出报告"模型结果"章节所需:
- 主客场比分分层 1X2 概率(主胜/平/客胜)
- 最近八场主客场战绩(积分/进/失/胜平负)

用法: python football_analyzer/home_away_layer.py  # 自检
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from model import poisson_fit, poisson_predict, poisson_1x2


def home_away_1x2(fit: dict, row) -> dict:
    """主客场比分分层 1X2 概率: 用 poisson_predict(主客场分离 λ) + poisson_1x2。

    返回 {ph, pd, pa, lh, la}。未知联赛返回 NaN。
    """
    lh, la = poisson_predict(fit, row)
    if not (np.isfinite(lh) and np.isfinite(la)):
        return {"ph": np.nan, "pd": np.nan, "pa": np.nan, "lh": np.nan, "la": np.nan}
    ph, pd_, pa = poisson_1x2(lh, la)
    return {"ph": float(ph), "pd": float(pd_), "pa": float(pa),
            "lh": float(lh), "la": float(la)}


def team_recent_form(df: pd.DataFrame, team: str, date, n: int = 8,
                     side: str = "all") -> dict:
    """某队最近 n 场战绩。side='home' 只看主场, 'away' 只看客场, 'all' 全部。

    返回 {n, points, gf, ga, w, d, l, points_per_game}。无比赛返回全 0。
    """
    if isinstance(date, str):
        date = pd.Timestamp(date)
    sub = df[df["date"] < date].copy()
    if side == "home":
        sub = sub[sub["home"] == team]
        sub["gf"] = sub["hg"]
        sub["ga"] = sub["ag"]
        sub["result"] = np.where(sub["hg"] > sub["ag"], "w",
                                  np.where(sub["hg"] == sub["ag"], "d", "l"))
    elif side == "away":
        sub = sub[sub["away"] == team]
        sub["gf"] = sub["ag"]
        sub["ga"] = sub["hg"]
        sub["result"] = np.where(sub["ag"] > sub["hg"], "w",
                                  np.where(sub["ag"] == sub["hg"], "d", "l"))
    else:
        h = sub[sub["home"] == team].copy()
        h["gf"] = h["hg"]; h["ga"] = h["ag"]
        h["result"] = np.where(h["hg"] > h["ag"], "w", np.where(h["hg"] == h["ag"], "d", "l"))
        a = sub[sub["away"] == team].copy()
        a["gf"] = a["ag"]; a["ga"] = a["hg"]
        a["result"] = np.where(a["ag"] > a["hg"], "w", np.where(a["ag"] == a["hg"], "d", "l"))
        sub = pd.concat([h, a], ignore_index=True)
    sub = sub.sort_values("date", ascending=False).head(n)
    if len(sub) == 0:
        return {"n": 0, "points": 0, "gf": 0, "ga": 0, "w": 0, "d": 0, "l": 0, "ppg": 0.0}
    pts = sub["result"].map({"w": 3, "d": 1, "l": 0}).sum()
    return {
        "n": len(sub),
        "points": int(pts),
        "gf": int(sub["gf"].sum()),
        "ga": int(sub["ga"].sum()),
        "w": int((sub["result"] == "w").sum()),
        "d": int((sub["result"] == "d").sum()),
        "l": int((sub["result"] == "l").sum()),
        "ppg": round(pts / len(sub), 2),
    }


def home_away_summary(df: pd.DataFrame, row, n: int = 8) -> dict:
    """主队最近主场 n 场 + 客队最近客场 n 场战绩摘要。"""
    home = team_recent_form(df, row["home"], row["date"], n=n, side="home")
    away = team_recent_form(df, row["away"], row["date"], n=n, side="away")
    return {"home_recent_home": home, "away_recent_away": away}


def _self_test():
    # 构造小数据验证
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"]),
        "league": ["T", "T", "T", "T"],
        "home": ["A", "A", "B", "A"],
        "away": ["B", "C", "A", "B"],
        "hg": [2, 1, 0, 3],
        "ag": [1, 2, 1, 0],
    })
    fit = poisson_fit(df)
    # 主客场 1X2
    row = {"league": "T", "home": "A", "away": "B"}
    ha = home_away_1x2(fit, row)
    assert abs(ha["ph"] + ha["pd"] + ha["pa"] - 1.0) < 1e-6
    print(f"主客场 1X2: 主胜{ha['ph']:.1%} 平{ha['pd']:.1%} 客胜{ha['pa']:.1%} (λ={ha['lh']:.2f}/{ha['la']:.2f})")
    # 最近主场战绩
    form_a = team_recent_form(df, "A", "2024-01-23", n=8, side="home")
    print(f"A 最近主场: {form_a}")
    assert form_a["n"] == 3  # A 主场 3 场(01-01, 01-08, 01-22)
    assert form_a["w"] == 2 and form_a["l"] == 1
    # 最近客场战绩
    form_b = team_recent_form(df, "B", "2024-01-23", n=8, side="away")
    print(f"B 最近客场: {form_b}")
    assert form_b["n"] == 2  # B 客场 2 场(01-01, 01-22)
    # 摘要
    summ = home_away_summary(df, {"date": "2024-01-23", "home": "A", "away": "B"}, n=8)
    assert summ["home_recent_home"]["n"] == 3
    assert summ["away_recent_away"]["n"] == 2
    print("== home_away_layer 自检通过 ==")


if __name__ == "__main__":
    _self_test()
