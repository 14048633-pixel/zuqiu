# -*- coding: utf-8 -*-
"""A/B: 真旧(白名单空) vs 生产路由(白名单16) — 同fold walk-forward 对照.
用法: python ab_strength.py [--leagues B1,POL,SAU,SW1] [--eval-year 2026]
指标: 1X2命中 / RPS / 预测总进球偏差 / λ平均差异.
"""
import sys, io, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\发家致富\football_analyzer")

import numpy as np
import pandas as pd

from data_loader import load_master
from model import poisson_fit, poisson_predict, rps_1x2
from dixon_coles import dc_1x2
from config import MODEL


def _enabled_leagues():
    import os
    env = (os.getenv("STRENGTH_V2_LEAGUES") or "").strip()
    return [x.strip() for x in env.split(",") if x.strip()] if env \
        else list(MODEL.get("strength_v2_leagues") or [])


def _fit_old(train):
    """真旧基准: 临时清空白名单路由, 保证对照的是旧 poisson_fit."""
    _save = MODEL.get("strength_v2_leagues")
    MODEL["strength_v2_leagues"] = []
    try:
        return poisson_fit(train)
    finally:
        MODEL["strength_v2_leagues"] = _save


def _eval(fit, eva, rho):
    rows = []
    for _, r in eva.iterrows():
        try:
            lh, la = poisson_predict(fit, r)
        except Exception:
            continue
        if not np.isfinite(lh) or not np.isfinite(la):
            continue
        ph, pd_, pa = dc_1x2(lh, la, rho)
        rows.append((lh + la, r["hg"] + r["ag"],
                     ph, pd_, pa, 0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2)))
    if len(rows) < 20:
        return None
    d = pd.DataFrame(rows, columns=["pred_t", "act_t", "ph", "pd", "pa", "y"])
    pred = np.where((d.ph >= d.pd) & (d.ph >= d.pa), 0, np.where(d.pd >= d.pa, 1, 2))
    probs = d[["ph", "pd", "pa"]].values
    return {"n": len(d),
            "acc": float((pred == d.y).mean()),
            "rps": rps_1x2(probs, d.y.values),
            "pred_total": float(d.pred_t.mean()),
            "act_total": float(d.act_t.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", default="B1,POL,SAU")
    ap.add_argument("--years", default="2025,2026")
    args = ap.parse_args()
    df = load_master(include_espn=False)
    print("master rows:", len(df))
    for lg in args.leagues.split(","):
        b = df[df["league"] == lg].sort_values("date")
        print("\n=== %s ===" % lg)
        for yr in args.years.split(","):
            train = b[b["date"] < "%s-01-01" % yr]
            eva = b[(b["date"] >= "%s-01-01" % yr) & (b["date"] < "%d-01-01" % (int(yr) + 1))]
            if len(train) < 150 or len(eva) < 30:
                print("  %s 样本不足" % yr)
                continue
            f1 = _fit_old(train)
            f2 = poisson_fit(train)          # 生产路由(当前白名单)
            rho = float((f1.get("_dc_rho") or {}).get(lg, 0.0))
            r1 = _eval(f1, eva, rho)
            r2 = _eval(f2, eva, rho)
            if not r1 or not r2:
                continue
            print("  [%s] n=%d" % (yr, r1["n"]))
            print("    旧: 命中 %.1f%%  RPS %.4f  模型场均 %.2f vs 实际 %.2f"
                  % (r1["acc"] * 100, r1["rps"], r1["pred_total"], r1["act_total"]))
            print("    v2: 命中 %.1f%%  RPS %.4f  模型场均 %.2f vs 实际 %.2f"
                  % (r2["acc"] * 100, r2["rps"], r2["pred_total"], r2["act_total"]))


if __name__ == "__main__":
    main()
