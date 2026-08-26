# -*- coding: utf-8 -*-
"""ou_gate 演示: 对今日候选比赛跑大小球信号闸门 + 历史回测验证闸门有效性。

输出:
  output/ou_gate_report.txt   逐场闸门明细
  output/ou_gate_backtest.txt 历史闸门回测(通过 vs 拦截 的命中率/ROI)

用法:
  python ou_gate_demo.py
"""
import argparse
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "src"))

import pandas as pd

from scan_candidates import match_team, feature_row_from_dataset, score_feature_row, OU_LINE, display
from src.predict_api import _load_cfg
from src.team_names_cn import to_cn
from ou_gate import OuGate, SIGNAL_EDGE, SIGNAL_WINDOW, BASELINE_WINDOW, RATIO_CAP


def backtest_gate(gate: OuGate, leagues, min_date="2019-07-01"):
    """历史验证: 对每条大小球记录用"它之前的数据"跑闸门, 比较通过/拦截的命中率与ROI。

    实现: 按 (联赛, 日期) 分组滑动, 基准与信号占比只用 < 当日 的历史, 无未来函数。
    """
    rows = []
    for lg in leagues:
        ou = gate.ou[(gate.ou["league"] == lg) & (gate.ou["date"] >= pd.Timestamp(min_date))] \
            .sort_values("date").reset_index(drop=True)
        res = gate.results[(gate.results["league"] == lg)].sort_values("Date")
        # 结果基准滑动窗: 最近 BASELINE_WINDOW 场的小球flag
        res_iter = res.iterrows()
        res_dq = []
        res_next = None
        # 信号滑动窗: 最近 SIGNAL_WINDOW 条大小球记录(严格早于当日)
        sig_dq = []
        for d, grp in ou.groupby("date"):
            # 推入早于该日的比赛结果
            while True:
                if res_next is None:
                    try:
                        res_next = next(res_iter)
                    except StopIteration:
                        res_next = None
                        break
                if res_next is None or res_next[1]["Date"] < d:
                    if res_next is not None:
                        res_dq.append(1 if res_next[1]["total"] <= 2 else 0)
                    res_next = None
                    continue
                break
            while len(res_dq) > BASELINE_WINDOW:
                res_dq.pop(0)
            base = sum(res_dq) / len(res_dq) if res_dq else None
            r_small = sum(1 for s, e in sig_dq if s == "under" and e >= SIGNAL_EDGE) / len(sig_dq) if sig_dq else None
            r_big = sum(1 for s, e in sig_dq if s == "over" and e >= SIGNAL_EDGE) / len(sig_dq) if sig_dq else None
            for _, r in grp.iterrows():
                prob_small = r["prob"] if r["side"] == "under" else 1.0 - r["prob"]
                market_prob = r["market_prob"] if r["side"] == "under" else 1.0 - r["market_prob"]
                odds = r["odds_close"] if pd.notna(r["odds_close"]) else r["odds_open"]
                # 只统计满足生产口径(edge>=5%)的 under 记录, 看闸门是否过滤掉低质量
                if r["side"] == "under" and r["edge"] >= SIGNAL_EDGE:
                    passed = False
                    if base is not None and prob_small > base + 0.06 and (r_small is None or r_small < RATIO_CAP):
                        passed = True
                    rows.append({
                        "date": d, "league": lg, "side": r["side"],
                        "prob": r["prob"], "edge": r["edge"], "odds": odds,
                        "settle": r["settle"], "profit": r["profit_close"] if pd.notna(r["profit_close"]) else r["profit_open"],
                        "stake": r["stake"], "passed": passed,
                        "baseline_small": base, "r_small": r_small,
                    })
            # 当日记录推入信号窗
            for _, r in grp.iterrows():
                sig_dq.append((r["side"], r["edge"]))
            while len(sig_dq) > SIGNAL_WINDOW:
                sig_dq.pop(0)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-08-14", help="特征构建统一日期")
    args = ap.parse_args()
    cfg = _load_cfg(os.path.join(BASE, "config.yaml"))
    data_dir = os.path.normpath(os.path.join(BASE, cfg["data"]["football_dir"]))
    gate = OuGate(data_dir)

    out_path = os.path.join(BASE, "output", "ou_gate_report.txt")
    out = io.open(out_path, "w", encoding="utf-8", newline="\n")
    def P(*a):
        out.write(" ".join(str(x) for x in a) + "\n")

    # ---------- 1) 今日候选逐场闸门 ----------
    df = pd.read_csv(os.path.join(BASE, "output", "today_matches.csv"), encoding="utf-8-sig")
    tm = json.load(open(os.path.join(BASE, "teams_map.json"), encoding="utf-8"))
    teams_by_league = tm["football_data_teams_by_league"]
    P("="*78)
    P("大小球信号闸门(修正版) — 逐场明细")
    P("基准: 联赛近30轮小球自然占比+6pt | 市场: 隐含概率+5pt | 频率: 近15场信号占比<65%")
    P("="*78)
    n_small = n_big = n_none = 0
    for _, r in df.iterrows():
        odds = (r["odds_h"], r["odds_d"], r["odds_a"])
        ou = (r["ou_over25"], r["ou_under25"])
        if any(pd.isna(x) for x in odds) or any(pd.isna(x) for x in ou):
            continue
        fd_h = match_team(r["league"], r["home"], teams_by_league)
        fd_a = match_team(r["league"], r["away"], teams_by_league)
        if pd.isna(fd_h) or pd.isna(fd_a):
            continue
        try:
            row = feature_row_from_dataset(r["league"], fd_h, fd_a, args.date)
            res = score_feature_row(row, odds=odds, ou_line=OU_LINE, ou=ou)
        except Exception:
            continue
        u = {b["side"]: b for b in res["bets"]}.get(f"under{OU_LINE}")
        if not u:
            continue
        match_date = pd.Timestamp(f"20{args.date[2:4]}-{r['kickoff_utc'][:5]}")
        v = gate.evaluate(r["league"], match_date, u["prob"], u["market_prob"], u["odds"])
        n_small += v["verdict"] == "small"
        n_big += v["verdict"] == "big"
        n_none += v["verdict"] == "none"
        tag = {"small": "小球", "big": "大球", "none": "无信号"}[v["verdict"]]
        P("")
        P(f"[{r['league']}] {to_cn(r['home'])} vs {to_cn(r['away'])} ({r['kickoff_utc']} UTC)")
        P(f"  模型小球 {v['prob_small']:.1%} vs 市场 {v['market_small']:.1%} | 赔率 {v['odds']:.2f} | 大球 {v['prob_big']:.1%}")
        P(f"  联赛基准(近30轮): 小球 {v['baseline_small']:.1%} / 大球 {v['baseline_big']:.1%}")
        P(f"  阈值: 小球>{v['threshold_small']:.1%} 大球>{v['threshold_big']:.1%}")
        P(f"  滚动信号占比: 小球 {v['recent_small_ratio']:.0%} 大球 {v['recent_big_ratio']:.0%} (上限 {RATIO_CAP:.0%})")
        c = v["checks"]
        P(f"  检查: 小球[基准{c['small_base_ok']} 市场{c['small_mkt_ok']} 频率{c['small_freq_ok']}] "
          f"大球[基准{c['big_base_ok']} 市场{c['big_mkt_ok']} 频率{c['big_freq_ok']}]")
        P(f"  >>> 最终: {tag}  (原伪码判定: {v['orig_verdict']})")
    P("")
    P(f"汇总: 小球{n_small} 大球{n_big} 无信号{n_none}")
    out.close()

    # ---------- 2) 历史闸门回测 ----------
    leagues = ["英冠", "西乙", "英超", "西甲", "德甲", "德乙", "意甲", "法甲", "荷甲"]
    bt = backtest_gate(gate, leagues)
    bt_path = os.path.join(BASE, "output", "ou_gate_backtest.txt")
    with io.open(bt_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("历史闸门回测(小球 edge>=5% 记录, 用记录之前数据判定)\n")
        f.write("="*78 + "\n")
        f.write(f"总记录: {len(bt)}\n")
        if len(bt):
            for name, mask in [("全部小球信号", bt["passed"].notna()),
                               ("闸门通过", bt["passed"] == True),
                               ("闸门拦截", bt["passed"] == False)]:
                g = bt[mask]
                if not len(g):
                    continue
                hit = (g["settle"] == 1).mean()
                roi = g["profit"].sum() / g["stake"].sum()
                f.write(f"  {name:<12} n={len(g):>5} 命中率={hit:>6.1%} ROI={roi:>+7.2%} "
                        f"均值edge={g['edge'].mean():.1%}\n")
            # 按联赛拆
            f.write("\n按联赛:\n")
            for lg, g in bt.groupby("league"):
                pa = g[g["passed"]]
                pb = g[~g["passed"]]
                if len(pa) and len(pb):
                    f.write(f"  {lg}: 通过 n={len(pa)} 命中={(pa['settle']==1).mean():.1%} ROI={pa['profit'].sum()/pa['stake'].sum():+.2%} | "
                            f"拦截 n={len(pb)} 命中={(pb['settle']==1).mean():.1%} ROI={pb['profit'].sum()/pb['stake'].sum():+.2%}\n")
    print("report ->", out_path)
    print("backtest ->", bt_path)


if __name__ == "__main__":
    main()
