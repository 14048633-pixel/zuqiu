# -*- coding: utf-8 -*-
import io, json

ROOT = r"D:\足球分析"
mev = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
v3d = json.load(io.open(ROOT + r"\analysis_records\key46_v3_lambda_20260818_2357.json", encoding="utf-8"))
by_odds = {r["id"]: r for r in key46}
v3_by = {r["id"]: r for r in v3d}

def market_over(o):
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if not ov or not un: return None, None, None
    po = (1.0/ov) / (1.0/ov + 1.0/un)
    return po*100, ov, un

rows = []
for r in mev:
    if r.get("ev_ou") is None: continue
    mo = r.get("model_over25")
    o = by_odds.get(r["id"], {}).get("bsd_odds") or {}
    mp, pov, uov = market_over(o)
    ev = r["ev_ou"]
    lam = r.get("lam") or []
    lam_sum = (lam[0]+lam[1]) if len(lam)==2 and lam[0] is not None else None
    edge = (mo - mp) if (mo is not None and mp is not None) else None
    if ev is None: star = "—"
    elif ev >= 0.08: star = "★★★"
    elif ev >= 0.05: star = "★★"
    elif ev >= 0.02: star = "★"
    else: star = "无"
    rows.append({
        "id": r["id"], "league": r["league"], "kickoff": r["kickoff"],
        "home": r["home"], "away": r["away"],
        "lam": lam_sum, "over_p": mo, "ou": r["model_ou"], "ou_p": r["model_ou_prob"],
        "mkt_over_p": mp, "mkt_ou_odds": (pov, uov), "ev": ev, "edge": edge, "star": star,
    })

def kf_key(x):
    d, t = x["kickoff"].split()
    return d, t

rows.sort(key=lambda x: (x["kickoff"][:5], x["kickoff"][6:]))

def fmt(x):
    return ("%+.1f%%" % (x*100)) if x is not None else "—"

lines = []
lines.append("# 大小球策略表（旧 raw λ 引擎 · 按开赛时间排序）")
lines.append("")
lines.append("> 数据源：key46 扫描（bsd_odds 快照 08-18 14:57Z）+ 旧 raw λ 模型 | 生成 2026-08-19")
lines.append("> 统计：大球 %d / 小球 %d ｜ EV≥5%%：%d 场 ｜ EV≥8%%：%d 场 ｜ 共 %d 场" % (
    sum(1 for x in rows if x["ou"]=="大2.5"), sum(1 for x in rows if x["ou"]=="小2.5"),
    sum(1 for x in rows if x["ev"] is not None and x["ev"]>=0.05),
    sum(1 for x in rows if x["ev"] is not None and x["ev"]>=0.08), len(rows)))
lines.append("")
lines.append("| # | 时间 | 联赛 | 对阵 | λ和 | 方向 | 模型大球 | 市场大球 | 盘口(大/小) | 模型EV | 差(pp) | 星级 |")
lines.append("|---|------|------|------|-----|------|---------|---------|------------|--------|--------|------|")
for i, x in enumerate(rows, 1):
    mp = ("%.0f%%" % x["mkt_over_p"]) if x["mkt_over_p"] is not None else "—"
    odds = ("%.2f/%.2f" % x["mkt_ou_odds"]) if x["mkt_ou_odds"][0] else "—/—"
    ed = ("%+.1f" % x["edge"]) if x["edge"] is not None else "—"
    lam = ("%.2f" % x["lam"]) if x["lam"] is not None else "—"
    lines.append("| %d | %s | %s | %s vs %s | %s | %s | %.0f%% | %s | %s | %s | %s | %s |" % (
        i, x["kickoff"], x["league"], x["home"], x["away"], lam,
        x["ou"], x["over_p"], mp, odds, fmt(x["ev"]), ed, x["star"]))

fn = ROOT + r"\analysis_records\ou_strategy_old_raw_20260819_by_time.md"
io.open(fn, "w", encoding="utf-8").write("\n".join(lines))
print("saved:", fn)
for x in rows:
    print("%s | %s | %s vs %s | λ%.2f | %s %.0f%% | 市%.0f%% | %s | %s" % (
        x["kickoff"], x["league"], x["home"], x["away"], x["lam"] or 0,
        x["ou"], x["over_p"], x["mkt_over_p"] or 0, fmt(x["ev"]), x["star"]))
