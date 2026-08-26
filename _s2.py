# -*- coding: utf-8 -*-
import csv, io, collections
rows = list(csv.DictReader(io.open(r"analysis_records/bet_ledger.csv", encoding="utf-8")))
def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
def outcome(r):
    res = (r.get("result") or "").strip().lower()
    return {"win": 1.0, "half": 0.5, "push": 0.5, "lose": 0.0, "": None}.get(res)
settled = [r for r in rows if (r.get("status") or "").startswith("已结算")]
settled = [r for r in settled if not (f(r.get("snap_age_h")) is not None and f(r["snap_age_h"]) < 0)]
data = []
for r in settled:
    o = outcome(r)
    if o is None:
        continue
    prob, odds, ev, star = f(r.get("prob")), f(r.get("odds")), f(r.get("ev")), r.get("star")
    data.append({"r": r, "p": prob, "odds": odds, "ev": ev, "o": o, "star": star,
                 "veto": (r.get("veto") or "") == "1", "name": r.get("bet_name") or ""})
def calc(sub, tag=""):
    n = len(sub)
    if not n:
        return
    hit = sum(1 for d in sub if d["o"] == 1.0) + 0.5 * sum(1 for d in sub if d["o"] == 0.5)
    ret = sum(d["o"] * d["odds"] for d in sub)
    print("  %-34s n=%2d 命中%.1f%% ROI%+.1f%%" % (tag, n, hit / n * 100, (ret / n - 1) * 100))
def grp(sub, keyfn):
    g = collections.defaultdict(list)
    for d in sub:
        g[keyfn(d)].append(d)
    return g
s2 = [d for d in data if d["star"] == "2"]
print("star2 总量:", len(s2))
print("\n== 按盘口类型 ==")
for k, sub in sorted(grp(s2, lambda d: d["name"].split("(")[0]).items()):
    calc(sub, k)
print("\n== 按联赛 ==")
for k, sub in sorted(grp(s2, lambda d: d["r"].get("league") or "?").items(), key=lambda kv: -len(kv[1])):
    calc(sub, "%s" % k)
print("\n== 按赔率区间 ==")
for k, sub in sorted(grp(s2, lambda d: "odds<1.7" if d["odds"] < 1.7 else "1.7-2.0" if d["odds"] < 2.0 else "2.0-2.5" if d["odds"] < 2.5 else "odds>=2.5").items()):
    calc(sub, k)
print("\n== 按模型概率区间 ==")
for k, sub in sorted(grp(s2, lambda d: "p<0.55" if d["p"] < 0.55 else "0.55-0.60" if d["p"] < 0.60 else "0.60-0.65" if d["p"] < 0.65 else "0.65-0.70" if d["p"] < 0.70 else "p>=0.70").items()):
    calc(sub, k)
print("\n== veto分布 ==")
for k, sub in sorted(grp(s2, lambda d: "实单" if not d["veto"] else "否决").items()):
    calc(sub, k)
print("\n== 类型 x 联赛 (亏损重灾区) ==")
for (t, lg), sub in collections.Counter([(d["name"].split("(")[0], d["r"].get("league") or "?") for d in s2]).most_common(12):
    ss = [d for d in s2 if d["name"].split("(")[0] == t and (d["r"].get("league") or "?") == lg]
    calc(ss, "%s x %s" % (t, lg))
