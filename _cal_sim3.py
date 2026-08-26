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
                 "veto": (r.get("veto") or "") == "1", "star": r.get("star")})
def cap(p, capv):
    return min(p, capv)
def blend2(p, mkt, thr, w):
    return p if p <= thr else w * p + (1 - w) * mkt
def sim(data, mode, capv, ev_th, use_veto):
    sel = []
    for d in data:
        if mode == "cap":
            p_cal = cap(d["p"], capv)
        elif mode == "blend2":
            p_cal = blend2(d["p"], d["mkt"], capv, 0.5)
        else:
            p_cal = d["p"]
        orr = d["p"] * d["odds"] / (1 + d["ev"])
        ev_cal = (p_cal / orr) * d["odds"] - 1
        if ev_cal < ev_th:
            continue
        if use_veto and d["veto"]:
            continue
        sel.append(d)
    n = len(sel)
    if not n:
        return 0, 0.0, 0.0
    hit = sum(1 for d in sel if d["o"] == 1.0) + 0.5 * sum(1 for d in sel if d["o"] == 0.5)
    ret = sum(d["o"] * d["odds"] for d in sel)
    return n, hit / n, (ret / n) - 1
def show(tag, res):
    n, h, roi = res
    print("  %-40s n=%3d 命中%.1f%% ROI%+.1f%%" % (tag, n, h * 100, roi * 100))
print("== 概率封顶 min(p, cap) ==")
for capv in [0.68, 0.65, 0.62, 0.60, 0.58]:
    show("cap=%.2f EV>=5%%" % capv, sim(data, "cap", capv, 0.05, False))
    show("cap=%.2f EV>=8%%" % capv, sim(data, "cap", capv, 0.08, False))
    show("cap=%.2f EV>=5%% 实单" % capv, sim(data, "cap", capv, 0.05, True))
print("\n== 封顶+方向不变 全量(无EV阈值) ==")
for capv in [0.65, 0.62, 0.60]:
    show("cap=%.2f 全量" % capv, sim(data, "cap", capv, -99, False))
print("\n== 封顶后 校准桶命中(全量无阈值) ==")
for d in data:
    d["pc"] = min(d["p"], 0.62)
for lo, hi in [(0.55,0.6),(0.6,0.65),(0.65,0.7),(0.7,1.01)]:
    sub = [d for d in data if lo <= d["pc"] < hi]
    if not sub:
        continue
    n = len(sub); hit = sum(1 for d in sub if d["o"]==1.0) + 0.5*sum(1 for d in sub if d["o"]==0.5)
    print("  cal[%.2f-%.2f) n=%2d 实际命中%.1f%%" % (lo, hi, n, hit/n*100))
