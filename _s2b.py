# -*- coding: utf-8 -*-
import csv, io
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
    data.append({"r": r, "p": f(r.get("prob")), "odds": f(r.get("odds")), "o": o,
                 "star": r.get("star"), "name": r.get("bet_name") or "",
                 "lg": r.get("league") or "?", "veto": (r.get("veto") or "") == "1"})
s2 = [d for d in data if d["star"] == "2"]
def calc(sub, tag):
    n = len(sub)
    if not n:
        print("  %-46s n=0" % tag); return
    hit = sum(1 for d in sub if d["o"] == 1.0) + 0.5 * sum(1 for d in sub if d["o"] == 0.5)
    ret = sum(d["o"] * d["odds"] for d in sub)
    print("  %-46s n=%2d 命中%.1f%% ROI%+.1f%%" % (tag, n, hit / n * 100, (ret / n - 1) * 100))
def mkt(d):
    return d["name"].split("(")[0]
BAD_LG = {"英冠", "比甲", "荷甲", "智利甲", "德乙", "葡超", "J1"}
calc(s2, "star2 基线")
calc([d for d in s2 if not (0.65 <= d["p"] < 0.70)], "star2 - 去掉p∈[0.65,0.70)档")
calc([d for d in s2 if not (mkt(d) in ("让球主", "小2.50"))], "star2 - 去掉让球主+小球")
calc([d for d in s2 if not (d["odds"] < 2.0 and d["odds"] >= 1.7)], "star2 - 去掉odds∈[1.7,2.0)")
calc([d for d in s2 if d["lg"] not in BAD_LG], "star2 - 去掉7负联赛")
calc([d for d in s2 if not (0.65 <= d["p"] < 0.70) and mkt(d) not in ("让球主", "小2.50")], "组合: 去掉p档+让球主/小球")
calc([d for d in s2 if not (mkt(d) == "让球主" and 0.60 <= d["p"] < 0.72)], "只滤: 让球主且p∈[0.60,0.72)")
calc([d for d in s2 if not (mkt(d) == "让球主" and 0.60 <= d["p"] < 0.72) and not (mkt(d) == "小2.50" and d["odds"] < 2.0)], "滤: 让球主p档 + 小球低赔")
print("\n== 全量角度: 过滤后整体(所有star) ==")
def keep(d):
    if d["star"] != "2":
        return True
    if 0.65 <= d["p"] < 0.70:
        return False
    if mkt(d) in ("让球主", "小2.50"):
        return False
    return True
calc([d for d in data if keep(d)], "全量 - star2重灾注")
calc([d for d in data if keep(d) and not d["veto"]], "全量 - star2重灾注 且 实单")
