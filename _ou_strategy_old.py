# -*- coding: utf-8 -*-
import io, json, statistics

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
    v = v3_by.get(r["id"]) or {}
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

rows.sort(key=lambda x: -(x["ev"] or -1))
n_big = sum(1 for x in rows if x["ou"]=="大2.5")
n_small = sum(1 for x in rows if x["ou"]=="小2.5")
n_ev5 = sum(1 for x in rows if x["ev"] is not None and x["ev"]>=0.05)
n_ev8 = sum(1 for x in rows if x["ev"] is not None and x["ev"]>=0.08)

def fmt(x):
    return ("%+.1f%%" % (x*100)) if x is not None else "—"

lines = []
lines.append("# 大小球策略表（旧 raw λ 引擎 · 高胜率版本）")
lines.append("")
lines.append("> 数据源：key46 扫描（bsd_odds 快照 08-18 14:57Z）+ 旧 raw λ 模型 | 生成 2026-08-19")
lines.append("> 统计：大球 %d / 小球 %d ｜ EV≥5%%：%d 场 ｜ EV≥8%%：%d 场 ｜ 共 %d 场" % (n_big, n_small, n_ev5, n_ev8, len(rows)))
lines.append("> 用法：测试期只记方向对命中率；EV 仅用于区分优先级（★★★ 核心 / ★★ 观察 / ★ 小注）")
lines.append("")
lines.append("| # | 时间 | 联赛 | 对阵 | λ和 | 模型方向 | 大球概率 | 市场大球 | 盘口(大/小) | 模型EV | 差(pp) | 星级 |")
lines.append("|---|------|------|------|-----|---------|---------|---------|------------|--------|--------|------|")
for i, x in enumerate(rows, 1):
    mp = ("%.0f%%" % x["mkt_over_p"]) if x["mkt_over_p"] is not None else "—"
    odds = ("%.2f/%.2f" % x["mkt_ou_odds"]) if x["mkt_ou_odds"][0] else "—/—"
    ed = ("%+.1f" % x["edge"]) if x["edge"] is not None else "—"
    lam = ("%.2f" % x["lam"]) if x["lam"] is not None else "—"
    lines.append("| %d | %s | %s | %s vs %s | %s | %s | %.0f%% | %s | %s | %s | %s | %s |" % (
        i, x["kickoff"], x["league"], x["home"], x["away"], lam,
        x["ou"], x["over_p"], mp, odds, fmt(x["ev"]), ed, x["star"]))
lines.append("")
lines.append("## 三星候选（EV≥8%）")
lines.append("")
for x in [r for r in rows if r["ev"] is not None and r["ev"]>=0.08]:
    mp = ("%.0f%%" % x["mkt_over_p"]) if x["mkt_over_p"] is not None else "—"
    lines.append("- %s | %s vs %s：%s（模型概率 %.0f%%）｜市场大球 %s ｜EV %s ｜λ和 %.2f" % (
        x["kickoff"], x["home"], x["away"], x["ou"], x["ou_p"], mp, fmt(x["ev"]), x["lam"] or 0))
lines.append("")
lines.append("## 风控标注（低置信不下单，仅记录方向）")
lines.append("")
for x in rows:
    flags = []
    if x["lam"] is not None and (x["lam"] < 1.8 or x["lam"] > 3.6): flags.append("λ异常%.2f" % x["lam"])
    if x["edge"] is not None and abs(x["edge"]) > 25: flags.append("与市场差%.0fpp" % x["edge"])
    if x["mkt_ou_odds"][0] is None: flags.append("缺盘口")
    if flags:
        mp = ("%.0f%%" % x["mkt_over_p"]) if x["mkt_over_p"] is not None else "—"
        lines.append("- %s | %s vs %s：%s EV%s ｜%s" % (x["kickoff"], x["home"], x["away"], x["ou"], fmt(x["ev"]), "；".join(flags)))

fn = ROOT + r"\analysis_records\ou_strategy_old_raw_20260819.md"
io.open(fn, "w", encoding="utf-8").write("\n".join(lines))
print("saved:", fn)
print("大球 %d / 小球 %d | EV≥5%% %d | EV≥8%% %d | n=%d" % (n_big, n_small, n_ev5, n_ev8, len(rows)))
