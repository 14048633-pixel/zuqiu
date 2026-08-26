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
    data.append({"r": r, "p": prob, "odds": odds, "ev": ev, "o": o,
                 "veto": (r.get("veto") or "") == "1", "star": r.get("star")})
def show(tag, res):
    n, h, roi = res
    print("  %-46s n=%3d 命中%.1f%% ROI%+.1f%%" % (tag, n, h * 100, roi * 100))
def calc(sel):
    n = len(sel)
    if not n:
        return 0, 0.0, 0.0
    hit = sum(1 for d in sel if d["o"] == 1.0) + 0.5 * sum(1 for d in sel if d["o"] == 0.5)
    ret = sum(d["o"] * d["odds"] for d in sel)
    return n, hit / n, (ret / n) - 1
def P(star_set=None, veto=None, p_max=None, p_min=None, ev_min=None):
    sel = []
    for d in data:
        if star_set and d["star"] not in star_set:
            continue
        if veto is not None and ((d["veto"]) != veto):
            continue
        if p_max and d["p"] > p_max:
            continue
        if p_min and d["p"] < p_min:
            continue
        if ev_min is not None and d["ev"] < ev_min:
            continue
        sel.append(d)
    return calc(sel)
print("== 星级规则 ==")
show("star in (1,)", P(star_set=("1",)))
show("star in (3,)", P(star_set=("3",)))
show("star in (1,3)", P(star_set=("1", "3")))
show("star in (2,)", P(star_set=("2",)))
print("\n== 星级 + 概率区间 ==")
show("star(1,3) + p<=0.70", P(star_set=("1", "3"), p_max=0.70))
show("star(1,3) + p<=0.70 + veto=0", P(star_set=("1", "3"), p_max=0.70, veto=False))
show("star(1) + p<=0.70 + veto=0", P(star_set=("1",), p_max=0.70, veto=False))
show("star(1,3) + 0.55<=p<=0.70", P(star_set=("1", "3"), p_min=0.55, p_max=0.70))
print("\n== 概率区间(不看星级) ==")
show("0.55<=p<=0.70", P(p_min=0.55, p_max=0.70))
show("0.55<=p<=0.70 + veto=0", P(p_min=0.55, p_max=0.70, veto=False))
show("0.60<=p<=0.70 + veto=0", P(p_min=0.60, p_max=0.70, veto=False))
print("\n== 去掉70%+高估档 ==")
show("p<=0.70", P(p_max=0.70))
show("p<=0.70 + veto=0", P(p_max=0.70, veto=False))
print("\n== 综合: star1 + veto0 + 0.55-0.70 ==")
show("star(1)+veto0+0.55-0.70", P(star_set=("1",), veto=False, p_min=0.55, p_max=0.70))
