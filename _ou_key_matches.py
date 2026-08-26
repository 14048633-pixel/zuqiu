# -*- coding: utf-8 -*-
import io, json
ROOT = r"D:\足球分析"
mev = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
key = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
by = {r["id"]: r for r in key}

def market_over(o):
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if not ov or not un: return None, None
    po = (1.0/ov) / (1.0/ov + 1.0/un)
    return po*100, ("大" if po > 0.5 else "小")

rows = []
for r in mev:
    o = by.get(r["id"], {}).get("bsd_odds") or {}
    mp, md = market_over(o)
    lam = r.get("lam") or []
    lam_sum = (lam[0]+lam[1]) if len(lam)==2 and lam[0] is not None else None
    rows.append({
        "ko": r["kickoff"], "lg": r["league"], "home": r["home"], "away": r["away"],
        "model": ("大" if r["model_over25"]>50 else "小"),
        "over_p": r["model_over25"], "mkt": md, "mkt_p": mp,
        "lam": lam_sum, "ev": r.get("ev_ou"),
    })

def pri(x):
    if x["model"]=="大":
        if x["lam"] is not None and 2.6 <= x["lam"] <= 3.4:
            return 1
        return 2
    return 3

for x in rows: x["pri"] = pri(x)
rows.sort(key=lambda x: (x["pri"], x["ko"]))

def fmt_ev(v):
    return ("%+.1f%%" % (v*100)) if v is not None else "—"

def show(rs, title, note):
    print("== %s ==" % title)
    if note: print(note)
    for x in rs:
        flag = ""
        if x["model"]=="大" and x["lam"] is not None and (x["lam"]>3.4 or x["lam"]<2.6):
            flag = " ⚠λ异常%.2f" % x["lam"]
        same = ""
        if x["mkt"]:
            same = "同向" if x["mkt"]==x["model"] else "反向"
        print("  %s %s | %-28s vs %-24s | λ%s | 模型%s(%.0f%%) | 市场%s(%s) %s | EV%s%s" % (
            x["ko"], x["lg"], x["home"], x["away"],
            ("%.2f" % x["lam"]) if x["lam"] is not None else "—",
            x["model"], x["over_p"] if x["model"]=="大" else 100-x["over_p"],
            x["mkt"] or "—", ("%.0f%%" % x["mkt_p"]) if x["mkt_p"] is not None else "—",
            same, fmt_ev(x["ev"]), flag))
    print()

show([x for x in rows if x["pri"]==1], "P1 重点（模型大 + λ正常2.6~3.4 + 市场同向大）", "按新验证规律：模型大球=价值方向（74场命中64.1% ROI+19%），这15场优先记方向")
show([x for x in rows if x["pri"]==2], "P2 观察（模型大但λ异常，人工复核）", "λ>3.5的大球=异常高位，参考勿重仓")
show([x for x in rows if x["pri"]==3], "P3 低优先级（模型小球=亏损方向）", "74场验证模型小球命中45.7% ROI-15.1%，同向小更差，仅作参考")

n1 = sum(1 for x in rows if x["pri"]==1); n2 = sum(1 for x in rows if x["pri"]==2); n3 = sum(1 for x in rows if x["pri"]==3)
print("汇总: P1=%d P2=%d P3=%d 总=%d" % (n1, n2, n3, len(rows)))

# 存档
out = {"p1": [x for x in rows if x["pri"]==1], "p2": [x for x in rows if x["pri"]==2], "p3": [x for x in rows if x["pri"]==3]}
io.open(ROOT + r"\analysis_records\ou_key_matches_20260819.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved: analysis_records/ou_key_matches_20260819.json")
