# -*- coding: utf-8 -*-
"""历史重放: 生产 poisson_fit(白名单) 逐联赛 walk-forward, 统计"方向判定"样本.
输出每个联赛 × 维度(1X2 / 大 / 小) 的 命中数与正确率, 加速规则结论积累.
用法: python replay_accuracy.py [--leagues E0,I1,D1,B1,POL] [--years 2023,2024,2025,2026]
"""
import sys, io, json, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\发家致富\football_analyzer")
import numpy as np
import pandas as pd

from data_loader import load_master
from model import poisson_fit, poisson_predict
from dixon_coles import dc_over_under_prob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="E0,I1,D1,B1,POL")
    ap.add_argument("--years", default="2023,2024,2025,2026")
    args = ap.parse_args()
    df = load_master(include_espn=False)
    agg = {}
    for lg in args.leagues.split(","):
        b = df[df["league"] == lg].sort_values("date")
        stat = {"n_1x2": 0, "hit_1x2": 0, "n_over": 0, "hit_over": 0,
                "n_under": 0, "hit_under": 0}
        for yr in args.years.split(","):
            train = b[b["date"] < "%s-01-01" % yr]
            eva = b[(b["date"] >= "%s-01-01" % yr) & (b["date"] < "%d-01-01" % (int(yr) + 1))]
            if len(train) < 150 or len(eva) < 30:
                continue
            fit = poisson_fit(train)
            rho = float((fit.get("_dc_rho") or {}).get(lg, 0.0))
            for _, r in eva.iterrows():
                try:
                    lh, la = poisson_predict(fit, r)
                except Exception:
                    continue
                if not np.isfinite(lh) or not np.isfinite(la):
                    continue
                ph = 1.0 - dc_over_under_prob(lh, la, 2.5, rho)
                # 1X2
                import dixon_coles as dc
                wh, wd, wa = dc.dc_1x2(lh, la, rho)
                pred = 0 if wh >= wd and wh >= wa else (1 if wd >= wa else 2)
                act = 0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2)
                stat["n_1x2"] += 1
                stat["hit_1x2"] += int(pred == act)
                # OU
                total = r["hg"] + r["ag"]
                if ph >= 0.5:
                    stat["n_over"] += 1
                    stat["hit_over"] += int(total >= 3)
                else:
                    stat["n_under"] += 1
                    stat["hit_under"] += int(total <= 2)
        agg[lg] = stat
        s = stat
        print("%s: 1X2 %d/%d(%.0f%%) | 大 %d/%d(%.0f%%) | 小 %d/%d(%.0f%%)"
              % (lg, s["hit_1x2"], s["n_1x2"],
                 s["hit_1x2"] / s["n_1x2"] * 100 if s["n_1x2"] else 0,
                 s["hit_over"], s["n_over"],
                 s["hit_over"] / s["n_over"] * 100 if s["n_over"] else 0,
                 s["hit_under"], s["n_under"],
                 s["hit_under"] / s["n_under"] * 100 if s["n_under"] else 0))
    json.dump(agg, open(r"D:\足球分析\analysis_records\replay_accuracy.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved replay_accuracy.json")


if __name__ == "__main__":
    main()
