# -*- coding: utf-8 -*-
"""模型 vs 市场 实盘对比: 从账本重建市场隐含概率, 校准/头对头/分歧分组."""
import csv, io, math, collections

rows = list(csv.DictReader(io.open(r"analysis_records/bet_ledger.csv", encoding="utf-8")))
def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

settled = [r for r in rows if (r.get("status") or "").startswith("已结算")]
# 剔除赛后拉盘
settled = [r for r in settled if not (f(r.get("snap_age_h")) is not None and f(r["snap_age_h"]) < 0)]
print("样本:", len(settled))

def outcome(r):
    res = (r.get("result") or "").strip().lower()
    return {"win": 1.0, "half": 0.5, "push": 0.5, "lose": 0.0, "": None}.get(res)

rows2 = []
for r in settled:
    prob, odds, ev, snap = f(r.get("prob")), f(r.get("odds")), f(r.get("ev")), f(r.get("snap_age_h"))
    o = outcome(r)
    if prob is None or odds is None or ev is None or o is None:
        continue
    try:
        mkt = (1 + ev) / (prob * odds * odds)  # 反推市场隐含概率
    except ZeroDivisionError:
        continue
    if not (0 < mkt < 1):
        continue
    rows2.append({"r": r, "prob": prob, "odds": odds, "ev": ev, "mkt": mkt,
                  "edge": prob - mkt, "o": o, "veto": (r.get("veto") or "") == "1",
                  "snap": snap, "ret": f(r.get("ret"))})

print("可用对比样本:", len(rows2))

def hit_roi(sub):
    n = len(sub)
    if not n:
        return 0, 0.0
    wins = sum(1 for x in sub if x["o"] == 1.0)
    halfs = sum(1 for x in sub if x["o"] == 0.5)
    ret = sum(x["o"] * x["odds"] for x in sub)
    roi = (ret / n) - 1
    return (wins + 0.5 * halfs) / n, roi

def mae_brier(sub):
    n = len(sub)
    if not n:
        return 0, 0, 0
    mae_m = sum(abs(x["prob"] - x["o"]) for x in sub) / n
    mae_k = sum(abs(x["mkt"] - x["o"]) for x in sub) / n
    brier_m = sum((x["prob"] - x["o"]) ** 2 for x in sub) / n
    brier_k = sum((x["mkt"] - x["o"]) ** 2 for x in sub) / n
    return mae_m, mae_k, brier_m - brier_k  # <0 模型更准

all_ = rows2
hm, roi = hit_roi(all_)
mm, mk, db = mae_brier(all_)
print("\n== 全量 %d 注 ==" % len(all_))
print("模型方向: 命中率%.1f%% 平注ROI%+.1f%%" % (hm * 100, roi * 100))
print("MAE: 模型%.3f vs 市场%.3f | Brier差(模型-市场)%+.4f (%s)" % (mm, mk, db, "模型更准" if db < 0 else "市场更准"))

# 按模型edge分组
print("\n== 按模型vs市场分歧(edge=prob-mkt)分组 ==")
for label, cond in [("edge>=10pp", lambda x: x["edge"] >= 0.10),
                    ("5pp<=edge<10pp", lambda x: 0.05 <= x["edge"] < 0.10),
                    ("0<=edge<5pp", lambda x: 0 <= x["edge"] < 0.05),
                    ("-5pp<edge<0", lambda x: -0.05 < x["edge"] < 0),
                    ("edge<=-5pp", lambda x: x["edge"] <= -0.05)]:
    sub = [x for x in all_ if cond(x)]
    if not sub:
        continue
    h, r = hit_roi(sub)
    print("  %-14s n=%2d 命中%.1f%% ROI%+.1f%%" % (label, len(sub), h * 100, r * 100))

# 概率桶校准
print("\n== 模型概率桶校准 ==")
buckets = [(0.4, 0.5), (0.5, 0.55), (0.55, 0.6), (0.6, 0.65), (0.65, 0.7), (0.7, 1.01)]
for lo, hi in buckets:
    sub = [x for x in all_ if lo <= x["prob"] < hi]
    if not sub:
        continue
    h, r = hit_roi(sub)
    avg_p = sum(x["prob"] for x in sub) / len(sub)
    avg_m = sum(x["mkt"] for x in sub) / len(sub)
    print("  prob[%.2f-%.2f) n=%2d 平均模型%.0f%%/市场%.0f%% -> 实际命中%.1f%% ROI%+.1f%%" % (
        lo, hi, len(sub), avg_p * 100, avg_m * 100, h * 100, r * 100))

# 实单vs否决
print("\n== 实单(veto=0) vs 否决(veto=1) ==")
for label, cond in [("实单", lambda x: not x["veto"]), ("否决", lambda x: x["veto"])]:
    sub = [x for x in all_ if cond(x)]
    h, r = hit_roi(sub)
    mm_, mk_, db_ = mae_brier(sub)
    print("  %s n=%2d 命中%.1f%% ROI%+.1f%% | MAE模型%.3f/市场%.3f" % (label, len(sub), h * 100, r * 100, mm_, mk_))

# 按方向
print("\n== 按方向 ==")
for label, key in [("大球", "大"), ("小球", "小"), ("让球主", "让球主"), ("让球客", "让球客"), ("胜平负", "1X2")]:
    sub = [x for x in all_ if label in (x["r"].get("bet_name") or "")]
    if not sub:
        continue
    h, r = hit_roi(sub)
    print("  %s n=%2d 命中%.1f%% ROI%+.1f%%" % (label, len(sub), h * 100, r * 100))

# 按星级
print("\n== 按星级 ==")
for st in ("1", "2", "3"):
    sub = [x for x in all_ if (x["r"].get("star") or "") == st]
    if not sub:
        continue
    h, r = hit_roi(sub)
    print("  star=%s n=%2d 命中%.1f%% ROI%+.1f%%" % (st, len(sub), h * 100, r * 100))
