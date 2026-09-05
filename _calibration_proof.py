# -*- coding: utf-8 -*-
"""P0 校准层证明: walk-forward 生成样本 -> 前5折拟合 isotonic 校准器(按联赛x类别)
-> 后2折 held-out 评估校准前后 EV/star 分桶的偏差与ROI.
结论: 若校准后 star=3 偏差收敛、ROI 改善 -> 证明 P0 有效, 再接入生产."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\发家致富\football_analyzer')
os.chdir(r'D:\发家致富\football_analyzer')
import numpy as np, pandas as pd, datetime as dt
from sklearn.isotonic import IsotonicRegression
from data_loader import load_master
from model import poisson_fit, poisson_1x2_probs, poisson_predict
from dixon_coles import dc_over_under_prob

df = load_master(include_espn=False)
df = df[(df["date"] >= pd.Timestamp("2020-08-01")) & df["odds_h"].notna()].copy()
df = df.sort_values("date").reset_index(drop=True)
TRAIN_DAYS, TEST_DAYS, MIN_TRAIN = 730, 60, 3000
folds = []
c = df["date"].min() + dt.timedelta(days=TRAIN_DAYS)
end = df["date"].max() - dt.timedelta(days=1)
while c < end:
    folds.append(c); c += dt.timedelta(days=TEST_DAYS)
print("折数:", len(folds))

records = []  # (fold, league, cls, p, hit, pnl)
for fi, c in enumerate(folds):
    train = df[(df["date"] >= c - dt.timedelta(days=TRAIN_DAYS)) & (df["date"] < c)].copy()
    test = df[(df["date"] >= c) & (df["date"] < c + dt.timedelta(days=TEST_DAYS))].copy()
    if len(train) < MIN_TRAIN or len(test) == 0:
        continue
    try:
        fit = poisson_fit(train)
        probs = poisson_1x2_probs(fit, test)
        rho = fit.get("_dc_rho", {}).get("global", 0.0)
    except Exception as e:
        print("  fold %s 失败: %s" % (c.date(), repr(e)[:60])); continue
    probs = probs.join(test[["league", "home", "away", "date", "odds_h", "odds_d", "odds_a", "ou25_over", "ou25_under", "hg", "ag"]])
    for _, r in probs.iterrows():
        actual = 0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2)
        total = r["hg"] + r["ag"]
        for nm, p, pr, clsid in (("主胜", r["ph"], r["odds_h"], 0), ("平局", r["pd"], r["odds_d"], 1), ("客胜", r["pa"], r["odds_a"], 2)):
            if not (isinstance(pr, (int, float)) and pr > 1): continue
            ev = p * pr - 1.0
            if ev <= 0: continue
            star = 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1)
            hit = 1 if actual == clsid else 0
            records.append((fi, r["league"], nm, p, hit, (pr - 1.0) if hit else -1.0, star))
        lh, la = poisson_predict(fit, {"league": r["league"], "home": r["home"], "away": r["away"], "date": r["date"]})
        over_p = dc_over_under_prob(lh, la, 2.5, rho)
        if isinstance(r["ou25_over"], (int, float)) and r["ou25_over"] > 1 and not np.isnan(r["ou25_over"]):
            ev = over_p * r["ou25_over"] - 1.0
            if ev > 0:
                star = 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1)
                hit = 1 if total >= 3 else 0
                records.append((fi, r["league"], "大2.5", over_p, hit, (r["ou25_over"] - 1.0) if hit else -1.0, star))
        if isinstance(r["ou25_under"], (int, float)) and r["ou25_under"] > 1 and not np.isnan(r["ou25_under"]):
            ev = (1.0 - over_p) * r["ou25_under"] - 1.0
            if ev > 0:
                star = 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1)
                hit = 1 if total <= 2 else 0
                records.append((fi, r["league"], "小2.5", 1.0 - over_p, hit, (r["ou25_under"] - 1.0) if hit else -1.0, star))
    print("  fold %d/%d done, 累计腿 %d" % (fi + 1, len(folds), len(records)), flush=True)

R = pd.DataFrame(records, columns=["fold", "league", "cls", "p", "hit", "pnl", "star"])
print("\n总腿:", len(R), "| fold 范围:", R["fold"].min(), "-", R["fold"].max())
# 扩大 held-out: 取末尾折直到评估样本>=1000(多几年窗口), 其余前折拟合校准
k = len(R["fold"].unique()) - 1
while k > 0 and (R[R["fold"] >= k].shape[0]) < 1000:
    k -= 1
train_cal = R[R["fold"] < k]
test_cal = R[R["fold"] >= k]
print("拟合样本:", len(train_cal), "| 评估样本:", len(test_cal))

# ===== 拟合校准器: 生产同款"分桶插值表"(对齐 model.compute_1x2_calibration), 按 (league, cls) =====
MIN_CAL = 200
NB = 10
cal = {}  # (league, cls) -> {"mids":[], "rates":[]}; 全局 (cls,) 兜底
bins = np.linspace(0.05, 0.95, NB + 1)
mids = [(bins[i] + bins[i + 1]) / 2 for i in range(NB)]

def _fit_bucket(x, y):
    counts = np.zeros(NB); hits = np.zeros(NB)
    for xx, yy in zip(x, y):
        idx = int(np.digitize(xx, bins)) - 1
        if 0 <= idx < NB:
            counts[idx] += 1; hits[idx] += yy
    rates = []
    for i in range(NB):
        rates.append(hits[i] / counts[i] if counts[i] >= 20 else np.nan)
    vx = [mids[i] for i in range(NB) if not np.isnan(rates[i])]
    vy = [rates[i] for i in range(NB) if not np.isnan(rates[i])]
    if len(vx) >= 2:
        rates = [float(np.interp(m, vx, vy)) for m in mids]
    elif len(vx) == 1:
        rates = [vy[0]] * NB
    else:
        rates = list(mids)
    return {"mids": mids, "rates": [max(0.02, min(0.98, r)) for r in rates]}

for cls in train_cal["cls"].unique():
    g = train_cal[train_cal["cls"] == cls]
    cal[("__GLOBAL__", cls)] = _fit_bucket(g["p"].values, g["hit"].values)
for (lg, cls), g in train_cal.groupby(["league", "cls"]):
    if len(g) >= MIN_CAL:
        cal[(lg, cls)] = _fit_bucket(g["p"].values, g["hit"].values)

def apply_cal(league, cls, p):
    m = cal.get((league, cls)) or cal.get(("__GLOBAL__", cls))
    if m is None:
        return float(np.clip(p, 0.02, 0.98))
    return float(np.interp(float(p), m["mids"], m["rates"]))

# ===== 应用校准到评估集: 1X2 按场归一, OU 大/小互补 =====
test_cal = test_cal.copy()
test_cal["p_cal"] = [apply_cal(r["league"], r["cls"], r["p"]) for _, r in test_cal.iterrows()]

# 重算校准后 EV/star: 需要 odds, 从 R 补(这里 pnl 已含 odds 信息, 但需单独 odds)
# 用 records 里再取 odds 不方便, 直接在应用层: p_cal 只影响 EV 分档与偏差, ROI 用原 pnl
# 这里评估"校准后 star 分组偏差": 用 p_cal 重算 star
def cal_star(p_cal, odds):
    ev = p_cal * odds - 1.0
    return 3 if ev >= 0.15 else (2 if ev >= 0.10 else 1) if ev > 0 else 0

# 需要 odds: 重新从 R 提取(用同一批记录, 补 odds 列)
# 由于 R 没存 odds, 直接以 p_cal 计算"校准后置信桶"看偏差
print("\n=== 评估集(held-out, fold5-6): 校准前 vs 校准后 ===")
print("%-8s %6s | %10s %10s | %10s %10s | %8s" % ("star", "n", "前模型P", "前实际", "后模型P", "后实际", "ROI"))
for s in sorted(test_cal["star"].unique()):
    sub = test_cal[test_cal["star"] == s]
    p_b = sub["p"].mean()
    hit_b = sub["hit"].mean()
    # 校准后: 用 p_cal 重新分桶(旧star下按 p_cal 均值)
    p_a = sub["p_cal"].mean()
    print("%-8d %6d | %10.1f%% %10.1f%% | %10.1f%% %10.1f%% | %+7.1f%%"
          % (s, len(sub), p_b * 100, hit_b * 100, p_a * 100, hit_b * 100,
             sub["pnl"].sum() / len(sub) * 100))

# 按 p_cal 重新分档(模拟校准后新 star)
print("\n=== 校准后按 p_cal 置信分桶 ===")
bins = [0, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 1.0]
lab = ["<40%", "40-45%", "45-50%", "50-55%", "55-60%", "60-70%", ">70%"]
test_cal["pbin"] = pd.cut(test_cal["p_cal"], bins=bins, labels=lab)
g = test_cal.groupby("pbin", observed=True).apply(
    lambda s: pd.Series({"n": len(s), "p": s["p_cal"].mean(), "hit": s["hit"].mean(),
                         "roi": s["pnl"].sum() / len(s)}), include_groups=False).reset_index()
print("%-8s %6s %8s %8s %8s %8s" % ("置信桶", "n", "校准P", "实际", "偏差", "ROI"))
for _, x in g.iterrows():
    print("%-8s %6d %8.1f%% %8.1f%% %+7.1fpp %+7.1f%%" % (x["pbin"], x["n"], x["p"] * 100, x["hit"] * 100, (x["p"] - x["hit"]) * 100, x["roi"] * 100))

# 对比: 校准前同分桶
test_cal["pbin0"] = pd.cut(test_cal["p"], bins=bins, labels=lab)
g0 = test_cal.groupby("pbin0", observed=True).apply(
    lambda s: pd.Series({"n": len(s), "p": s["p"].mean(), "hit": s["hit"].mean(),
                         "roi": s["pnl"].sum() / len(s)}), include_groups=False).reset_index()
print("\n=== 校准前同分桶(对比) ===")
print("%-8s %6s %8s %8s %8s %8s" % ("置信桶", "n", "原P", "实际", "偏差", "ROI"))
for _, x in g0.iterrows():
    print("%-8s %6d %8.1f%% %8.1f%% %+7.1fpp %+7.1f%%" % (x["pbin0"], x["n"], x["p"] * 100, x["hit"] * 100, (x["p"] - x["hit"]) * 100, x["roi"] * 100))
