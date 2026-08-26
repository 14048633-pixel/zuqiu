# -*- coding: utf-8 -*-
import csv, io
rows = list(csv.DictReader(io.open(r"analysis_records/bet_ledger.csv", encoding="utf-8")))
def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
settled = [r for r in rows if (r.get("status") or "").startswith("已结算")]
settled = [r for r in settled if not (f(r.get("snap_age_h")) is not None and f(r["snap_age_h"]) < 0)]
def outcome(r):
    res = (r.get("result") or "").strip().lower()
    return {"win": 1.0, "half": 0.5, "push": 0.5, "lose": 0.0}.get(res)
data = []
for r in settled:
    prob, odds, ev = f(r.get("prob")), f(r.get("odds")), f(r.get("ev"))
    o = outcome(r)
    if prob is None or odds is None or ev is None or o is None:
        continue
    mkt = (1 + ev) / (prob * odds * odds)
    if not (0 < mkt < 1):
        continue
    data.append({"r": r, "p": prob, "odds": odds, "ev": ev, "mkt": mkt, "o": o,
                 "veto": (r.get("veto") or "") == "1"})
def blend(p, mkt, thr, w_mid, w_top):
    if p <= thr:
        return p
    if p <= thr + 0.05:
        return w_mid * p + (1 - w_mid) * mkt
    return w_top * p + (1 - w_top) * mkt
def sim(data, thr, w_mid, w_top, ev_th, use_veto):
    sel = []
    for d in data:
        p_cal = blend(d["p"], d["mkt"], thr, w_mid, w_top)
        orr = d["p"] * d["odds"] / (1 + d["ev"])
        ev_cal = (p_cal / orr) * d["odds"] - 1
        if ev_cal < ev_th:
            continue
        if use_veto and d["veto"]:
            continue
        sel.append((d, p_cal, ev_cal))
    n = len(sel)
    if not n:
        return 0, 0.0, 0.0
    hit = sum(1 for d, _, _ in sel if d["o"] == 1.0) + 0.5 * sum(1 for d, _, _ in sel if d["o"] == 0.5)
    ret = sum(d["o"] * d["odds"] for d, _, _ in sel)
    return n, hit / n, (ret / n) - 1
def show(tag, res):
    n, h, roi = res
    print("  %-40s n=%3d 命中%.1f%% ROI%+.1f%%" % (tag, n, h * 100, roi * 100))
print("== 基线 ==")
show("全量(原模型方向)", sim(data, 0.65, 1.0, 1.0, -99, False))
show("实单 veto=0", sim(data, 0.65, 1.0, 1.0, -99, True))
show("全量 EV>=5%", sim(data, 0.65, 1.0, 1.0, 0.05, False))
show("全量 EV>=8%", sim(data, 0.65, 1.0, 1.0, 0.08, False))
print("\n== 校准后(blend: p>0.65向市场回归) ==")
for w_mid, w_top in [(0.6, 0.4), (0.5, 0.3), (0.4, 0.2)]:
    print("  w[65-70]=%.1f  w[>70]=%.1f" % (w_mid, w_top))
    show("  全量EV>=5%", sim(data, 0.65, w_mid, w_top, 0.05, False))
    show("  全量EV>=8%", sim(data, 0.65, w_mid, w_top, 0.08, False))
    show("  实单EV>=5%", sim(data, 0.65, w_mid, w_top, 0.05, True))
    show("  实单EV>=8%", sim(data, 0.65, w_mid, w_top, 0.08, True))
print("\n== 校准后(blend: p>0.60即开始) ==")
for w_mid, w_top in [(0.6, 0.4), (0.5, 0.3)]:
    print("  w[60-65]=%.1f  w[>65]=%.1f" % (w_mid, w_top))
    show("  全量EV>=5%", sim(data, 0.60, w_mid, w_top, 0.05, False))
    show("  全量EV>=8%", sim(data, 0.60, w_mid, w_top, 0.08, False))
print("\n== 命中率校准效果(全量, 无阈值) ==")
for d in data:
    d["pc"] = blend(d["p"], d["mkt"], 0.65, 0.6, 0.4)
for lo, hi in [(0.5,0.55),(0.55,0.6),(0.6,0.65),(0.65,0.7),(0.7,1.01)]:
    sub = [d for d in data if lo <= d["pc"] < hi]
    if not sub:
        continue
    n = len(sub); hit = sum(1 for d in sub if d["o"]==1.0) + 0.5*sum(1 for d in sub if d["o"]==0.5)
    print("  cal[%.2f-%.2f) n=%2d 实际命中%.1f%%" % (lo, hi, n, hit/n*100))
