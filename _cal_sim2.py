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
def bucket_rate(p):
    if p < 0.55: return 0.62
    if p < 0.60: return 0.42
    if p < 0.65: return 0.59
    if p < 0.70: return 0.47
    return 0.52
def cal_map(p, mode):
    if mode == "bucket":          return bucket_rate(p)
    if mode == "bucket_half":     return 0.5 * bucket_rate(p) + 0.5 * p
    if mode == "shrink08":        return 0.5 + (p - 0.5) * 0.8
    if mode == "shrink07":        return 0.5 + (p - 0.5) * 0.7
    if mode == "shrink06":        return 0.5 + (p - 0.5) * 0.6
    return p
def sim(data, mode, ev_th, use_veto, band=None, star=None):
    sel = []
    for d in data:
        p_cal = cal_map(d["p"], mode)
        orr = d["p"] * d["odds"] / (1 + d["ev"])
        ev_cal = (p_cal / orr) * d["odds"] - 1
        if ev_cal < ev_th:
            continue
        if use_veto and d["veto"]:
            continue
        if band and not (band[0] <= d["p"] < band[1]):
            continue
        if star and d["star"] not in star:
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
    print("  %-42s n=%3d 命中%.1f%% ROI%+.1f%%" % (tag, n, h * 100, roi * 100))
print("== 各种校准映射 (EV>=5%, 全量) ==")
for mode in ["bucket", "bucket_half", "shrink08", "shrink07", "shrink06"]:
    show(mode, sim(data, mode, 0.05, False))
print("\n== 各种校准映射 (EV>=5%, 实单veto=0) ==")
for mode in ["bucket", "bucket_half", "shrink08", "shrink07", "shrink06"]:
    show(mode, sim(data, mode, 0.05, True))
print("\n== 组合策略 (原概率) ==")
show("veto=0", sim(data, "none", -99, True))
show("veto=0 + band[0.55-0.65]", sim(data, "none", -99, True, band=(0.55, 0.65)))
show("veto=0 + star in (1,)", sim(data, "none", -99, True, star=("1",)))
show("veto=0 + star(1) + band[0.55-0.70]", sim(data, "none", -99, True, band=(0.55, 0.70), star=("1",)))
show("全量 + band[0.55-0.65]", sim(data, "none", -99, False, band=(0.55, 0.65)))
show("全量 + band[0.60-0.65]", sim(data, "none", -99, False, band=(0.60, 0.65)))
show("全量 + band[0.55-0.65] + EV>=5%", sim(data, "none", 0.05, False, band=(0.55, 0.65)))
show("veto=0 + band[0.55-0.65] + EV>=5%", sim(data, "none", 0.05, True, band=(0.55, 0.65)))
print("\n== bucket校准 + 实单 ==")
show("bucket + veto=0", sim(data, "bucket", -99, True))
show("bucket + veto=0 + EV>=5%", sim(data, "bucket", 0.05, True))
show("bucket + 全量 + EV>=8%", sim(data, "bucket", 0.08, False))
