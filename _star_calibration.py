# -*- coding: utf-8 -*-
"""星级校准: 用生产同款逻辑(poisson_fit 含 strength_v2 路由 + DC + OU 校准)在历史数据上
walk-forward 重放出单, 按 EV/star 分桶统计真实命中率与ROI, 检验高置信端是否过度自信."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\发家致富\football_analyzer')
os.chdir(r'D:\发家致富\football_analyzer')
import numpy as np, pandas as pd, datetime as dt
from data_loader import load_master
from model import poisson_fit, poisson_1x2_probs, poisson_predict
from model import apply_1x2_calibration, apply_ou_calibration, apply_ou_isotonic
from dixon_coles import dc_over_under_prob, estimate_rho
from dixon_coles import dc_1x2
from shin_devig import devig3 as _shin_devig3
from ensemble_calib import ensemble_1x2

df = load_master(include_espn=False)
# 近 3 赛季 + 有赔率
df = df[(df["date"] >= pd.Timestamp("2023-08-01")) & df["odds_h"].notna()].copy()
df = df.sort_values("date").reset_index(drop=True)
print("重放样本:", len(df), "场 |", df["date"].min().date(), "->", df["date"].max().date())

TRAIN_DAYS = 730
TEST_DAYS = 60
MIN_TRAIN = 3000
folds = []
start = df["date"].min() + dt.timedelta(days=TRAIN_DAYS)
end = df["date"].max() - dt.timedelta(days=1)
cutoff = start
while cutoff < end:
    folds.append(cutoff); cutoff += dt.timedelta(days=TEST_DAYS)
print("折数:", len(folds))

records = []  # 每条腿: mkt, name, model_p, odds, ev, star, hit, roi_pnl
for fi, c in enumerate(folds):
    t_lo = c - dt.timedelta(days=TRAIN_DAYS)
    t_hi = c + dt.timedelta(days=TEST_DAYS)
    train = df[(df["date"] >= t_lo) & (df["date"] < c)].copy()
    test = df[(df["date"] >= c) & (df["date"] < t_hi)].copy()
    if len(train) < MIN_TRAIN or len(test) == 0:
        continue
    try:
        fit = poisson_fit(train)
        probs = poisson_1x2_probs(fit, test)
        rho = fit.get("_dc_rho", {}).get("global", 0.0)
    except Exception as e:
        print("  fold %s 失败: %s" % (c.date(), repr(e)[:80])); continue
    probs = probs.join(test[["league", "home", "away", "date", "odds_h", "odds_d", "odds_a", "ou25_over", "ou25_under", "hg", "ag"]])
    _c1x2 = fit.get("_calib_1x2") or {}
    _ou_cal = fit.get("_ou_calibration") or {}
    for _, r in probs.iterrows():
        oh, od, oa = r["odds_h"], r["odds_d"], r["odds_a"]
        oo, ou = r.get("ou25_over"), r.get("ou25_under")
        actual = 0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2)
        total = r["hg"] + r["ag"]
        lh, la = poisson_predict(fit, {"league": r["league"], "home": r["home"],
                                       "away": r["away"], "date": r["date"]})
        over_p = dc_over_under_prob(lh, la, 2.5, rho)
        # 生产同款 1X2: DC 概率 -> 市场 devig(Shin) -> ensemble(elo权重0) -> apply_1x2_calibration
        _dcp = dc_1x2(lh, la, rho)
        mkt = _shin_devig3(oh, od, oa) if all(isinstance(x, (int, float)) and x > 1
                                              for x in (oh, od, oa)) else None
        _ens = ensemble_1x2(_dcp, mkt, (r["ph"], r["pd"], r["pa"]), elo_h=0.0)
        ph, pd_, pa = _ens["ph"], _ens["pd"], _ens["pa"]
        _c1 = _c1x2.get(r["league"])
        if _c1:
            ph, pd_, pa = apply_1x2_calibration((ph, pd_, pa), _c1)
        _oc = _ou_cal.get(r["league"])
        _oi = (fit.get("_ou_isotonic") or {}).get(r["league"])
        if _oi is not None:
            over_p = apply_ou_isotonic(over_p, _oi)
        elif _oc:
            over_p = apply_ou_calibration(over_p, _oc)
        # 1X2 腿(生产口径: EV=p*pr-1)
        for nm, p, pr, clsid in (("主胜", ph, oh, 0), ("平局", pd_, od, 1), ("客胜", pa, oa, 2)):
            if not (isinstance(pr, (int, float)) and pr > 1): continue
            if p < 0.50: continue   # 校准后低置信过滤(2026-09-05)
            ev = p * pr - 1.0
            if ev <= 0: continue
            star = 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1)
            hit = 1 if actual == clsid else 0
            pnl = (pr - 1.0) if hit else -1.0
            records.append(("1x2", nm, p, pr, ev, star, hit, pnl))
        if isinstance(oo, (int, float)) and oo > 1 and not np.isnan(oo):
            if over_p >= 0.50:   # 校准后低置信过滤
                ev = over_p * oo - 1.0
                if ev > 0:
                    star = 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1)
                    hit = 1 if total >= 3 else 0
                    records.append(("ou", "大2.5", over_p, oo, ev, star, hit, (oo - 1.0) if hit else -1.0))
        if isinstance(ou, (int, float)) and ou > 1 and not np.isnan(ou) and (1.0 - over_p) >= 0.50:
            ev = (1.0 - over_p) * ou - 1.0
            if ev > 0:
                star = 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1)
                hit = 1 if total <= 2 else 0
                records.append(("ou", "小2.5", 1.0 - over_p, ou, ev, star, hit, (ou - 1.0) if hit else -1.0))
    if fi % 3 == 0:
        print("  fold %d/%d done, 累计腿 %d" % (fi + 1, len(folds), len(records)), flush=True)

R = pd.DataFrame(records, columns=["mkt", "name", "p", "odds", "ev", "star", "hit", "pnl"])
print("\n总腿:", len(R))
R.to_csv(r"D:\发家致富\analysis_records\star_calib_records.csv", index=False, encoding="utf-8-sig")

# ===== 按 EV 分桶 =====
bins = [0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30, 0.50, 1.0]
lab = ["0-2%", "2-5%", "5-8%", "8-10%", "10-12%", "12-15%", "15-20%", "20-30%", "30-50%", ">50%"]
R["ebin"] = pd.cut(R["ev"], bins=bins, labels=lab, include_lowest=True)
print("\n=== 按 EV 分桶 (生产 star 口径: >=15%=3, >=10%=2, >=1%=1) ===")
print("%-8s %6s %8s %8s %8s %8s" % ("EV桶", "n", "模型P", "实际", "偏差", "ROI"))
g = R.groupby("ebin", observed=True).apply(
    lambda s: pd.Series({"n": len(s), "mp": s["p"].mean(), "hit": s["hit"].mean(),
                         "roi": s["pnl"].sum() / len(s)}), include_groups=False).reset_index()
for _, x in g.iterrows():
    print("%-8s %6d %8.1f%% %8.1f%% %+7.1fpp %+7.1f%%" % (x["ebin"], x["n"], x["mp"] * 100, x["hit"] * 100, (x["mp"] - x["hit"]) * 100, x["roi"] * 100))

print("\n=== 按 star 分组 (生产分级) ===")
print("%-6s %6s %8s %8s %8s %8s" % ("star", "n", "模型P", "实际", "偏差", "ROI"))
for s in sorted(R["star"].unique()):
    sub = R[R["star"] == s]
    print("%-6d %6d %8.1f%% %8.1f%% %+7.1fpp %+7.1f%%" % (s, len(sub), sub["p"].mean() * 100, sub["hit"].mean() * 100, (sub["p"].mean() - sub["hit"].mean()) * 100, sub["pnl"].sum() / len(sub) * 100))

print("\n=== 按 mkt 拆 star=3 ===")
for mk in R["mkt"].unique():
    sub = R[(R["mkt"] == mk) & (R["star"] == 3)]
    if len(sub):
        print("%-4s star3: n=%d 模型P=%.1f%% 实际=%.1f%% ROI=%+.1f%%" % (mk, len(sub), sub["p"].mean() * 100, sub["hit"].mean() * 100, sub["pnl"].sum() / len(sub) * 100))
