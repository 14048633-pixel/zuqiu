# -*- coding: utf-8 -*-
"""实盘账本无泄漏回测 CLI —— 只用赛前快照, 不偷看结果
====================================================
用法: python prediction_v2/ledger_backtest.py [--ledger analysis_records/bet_ledger.csv]
规则:
  1. 只统计 status=已结算 的行(预测在赛前已冻结落账, 无前视偏差)
  2. 剔除 snap_age_h<0 的行(赔率快照在开赛后拉取, 可能偷看到临场/比分信息)
  3. 分 全量/实单(veto=0)/被否决(veto=1)/市场/联赛 输出 方向命中率 + 平注ROI
口径: 方向命中=(win+0.5*half)/已决; 平注ROI=(win->odds-1, lose->-1, push->0, half->ret-1)/n
说明: 被否决的注虽未实下, 但代表系统方向判断, 单独统计用于校准"否决信号"有效性
"""
import io
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mkt(b):
    b = str(b)
    if b.startswith("小"):
        return "小球"
    if b.startswith("大"):
        return "大球"
    if b.startswith("让球主"):
        return "让球主"
    if b.startswith("让球客"):
        return "让球客"
    return "其他"


def pl_of(r):
    if r["result"] == "win":
        return r["odds"] - 1
    if r["result"] == "lose":
        return -1.0
    if r["result"] == "push":
        return 0.0
    if r["result"] == "half":
        return (r["ret"] - 1) if pd.notna(r["ret"]) else -0.5
    return 0.0


def stats(sub, label):
    if len(sub) == 0:
        print("%s: n=0" % label)
        return None
    sub = sub.copy()
    sub["pl"] = sub.apply(pl_of, axis=1)
    n = len(sub)
    wins = (sub["result"] == "win").sum()
    halves = (sub["result"] == "half").sum()
    pushes = (sub["result"] == "push").sum()
    decided = n - pushes
    hit = (wins + 0.5 * halves) / decided if decided else 0.0
    roi = sub["pl"].mean()
    print("%s: n=%d 胜=%d 半=%d 走水=%d 负=%d 方向命中=%.1f%% 平注ROI=%.2f%%"
          % (label, n, wins, halves, pushes, n - wins - halves - pushes, 100 * hit, 100 * roi))
    return {"label": label, "n": n, "hit": hit, "roi": roi}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=os.path.join(ROOT, "analysis_records", "bet_ledger.csv"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    df = pd.read_csv(args.ledger)
    settled = df[df["status"] == "已结算"].copy()
    print("账本总行数:", len(df), "| 已结算:", len(settled))
    leak = settled[settled["snap_age_h"].fillna(999) < 0]
    clean = settled[settled["snap_age_h"].fillna(999) >= 0].copy()
    print("剔除赛后才拉盘(snap_age_h<0, 可能偷看):", len(leak))
    for _, r in leak.iterrows():
        print("   ⚠️ %s %s %s snap_age_h=%s" % (r["league"], r["match"], r["bet_name"], r["snap_age_h"]))
    if len(clean) == 0:
        print("无可回测样本"); return
    clean["mkt"] = clean["bet_name"].apply(mkt)

    print("\n======== 实盘无泄漏回测 (赛前快照) ========")
    stats(clean, "【全量(含被否决)】")
    stats(clean[clean["veto"] == 0], "【实单口径 veto=0】")
    stats(clean[clean["veto"] == 1], "【被否决 veto=1】")
    print("--- 分市场(全量) ---")
    for m in ("小球", "大球", "让球主", "让球客"):
        stats(clean[clean["mkt"] == m], "  " + m)
    print("--- 分联赛(全量, n>=3) ---")
    for lg, sub in clean.groupby("league"):
        if len(sub) >= 3:
            stats(sub, "  " + lg)


    print("--- 教练分组(已结算, 全量) ---")
    def _fnum(x):
        try:
            f = float(x)
            if f != f:  # NaN
                return None
            return f
        except (TypeError, ValueError):
            return None
    def _coach_grp(row):
        atk = _fnum(row.get("coach_atk_mod"))
        n = _fnum(row.get("coach_sample_size"))
        if n is None:
            return "无教练数据"
        if n >= 80:
            return "样本充足(>=80)"
        if n < 30:
            return "新帅(<30)"
        return "中等(30-79)"
    clean["coach_grp"] = clean.apply(_coach_grp, axis=1)
    for g in ("新帅(<30)", "中等(30-79)", "样本充足(>=80)", "无教练数据"):
        stats(clean[clean["coach_grp"] == g], "  教练[" + g + "]")
    def _atk_grp(row):
        atk = _fnum(row.get("coach_atk_mod"))
        if atk is None:
            return "无教练数据"
        if atk >= 1.05:
            return "高攻教练(>=1.05)"
        if atk <= 0.95:
            return "低攻教练(<=0.95)"
        return "中性教练"
    clean["atk_grp"] = clean.apply(_atk_grp, axis=1)
    for g in ("高攻教练(>=1.05)", "中性教练", "低攻教练(<=0.95)", "无教练数据"):
        stats(clean[clean["atk_grp"] == g], "  攻[" + g + "]")


if __name__ == "__main__":
    main()
