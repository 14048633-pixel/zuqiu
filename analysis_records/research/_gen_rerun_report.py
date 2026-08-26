# -*- coding: utf-8 -*-
"""生成 rerun_0822_live.md 完整报告（每场完整链路）"""
import sys, io, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\足球分析\analysis_records\research"
d = json.load(io.open(os.path.join(OUT, "rerun_0822_live.json"), encoding="utf-8"))
rows = sorted(d["matches"], key=lambda x: (x["ct"][:5], x["league"]))

def f2(o): return ("%.2f" % o) if isinstance(o,(int,float)) else "-"
def pct(o): return ("%+.1f%%" % (o*100)) if isinstance(o,(int,float)) else "-"

L = []
L.append("# 08-22 凌晨 27 场 完整重算报告（最新赔率 %s）" % d.get("pulled_at",""))
L.append("")
L.append("- 数据源: the-odds-api 22 场 + API-Football 5 场｜快照: `snapshots_live_0822.csv`｜模型: scan_upcoming 完整链路重跑")
L.append("- 出单口径: 批量无情报 EV≥5%｜硬否决: 盘口过期 / 模型vs市场分歧>20pp")
L.append("")

bb = [x for x in rows if x["result"].get("best_bet")]
veto = [x for x in rows if x["result"].get("direction",{}).get("vetoed")]
n_pos = sum(1 for x in rows if any(b.get("ev",0)>0 for b in x["result"].get("bets") or []))
L.append("## 📊 总览")
L.append("")
L.append("| 指标 | 值 |")
L.append("|---|---|")
L.append("| 总场次 | %d |" % len(rows))
L.append("| 出单 best_bet | %d |" % len(bb))
L.append("| 正EV场次 | %d |" % n_pos)
L.append("| 硬否决 | %d |" % len(veto))
L.append("")
L.append("### 出单列表（%d 场）" % len(bb))
L.append("")
L.append("| 开赛 | 联赛 | 比赛 | 出单方向 | 概率 | 赔率 | EV | 星级 | 分层 | 风险 |")
L.append("|---|---|---|---|---|---|---|---|---|---|")
for x in sorted(bb, key=lambda t: -((t["result"].get("best_bet") or {}).get("ev",0))):
    r = x["result"]; b = r["best_bet"]
    L.append("| %s | %s | %s vs %s | %s | %.0f%% | %.2f | %s | ★%d | %s | %s |" % (
        x["ct"], x["league"], x["home"], x["away"], b["name"], b["prob"]*100, b["odds"],
        pct(b["ev"]), b.get("star",0), b.get("ev_tier","?"), ",".join(r.get("risk_tags") or [])[:60]))
L.append("")
L.append("### 硬否决（%d 场，EV>5%% 但触发风控）" % len(veto))
L.append("")
L.append("| 开赛 | 联赛 | 比赛 | 方向(否决前) | EV | 否决原因 |")
L.append("|---|---|---|---|---|---|")
for x in sorted(veto, key=lambda t: -((t["result"].get("direction") or {}).get("ev",0))):
    r = x["result"]; di = r.get("direction") or {}
    L.append("| %s | %s | %s vs %s | %s | %s | %s |" % (
        x["ct"], x["league"], x["home"], x["away"], di.get("name","-"), pct(di.get("ev")),
        (di.get("veto_reason") or "-")[:50]))
L.append("")
L.append("---")
L.append("")

for x in rows:
    r = x["result"]
    if "error" in r:
        L.append("## ❌ %s | %s vs %s（%s）：%s" % (x["league"], x["home"], x["away"], x["ct"], r["error"]))
        L.append(""); continue
    lam = r.get("lambda") or {}
    wdl = r.get("wdl") or {}
    mf = r.get("market_fair") or {}
    di = r.get("direction") or {}
    bb2 = r.get("best_bet")
    L.append("## %s | %s vs %s（%s）" % (x["league"], x["home"], x["away"], x["ct"]))
    L.append("")
    L.append("- 数据源: 主[%s] 客[%s]｜snap %s" % (r.get("data_src",{}).get("home","-"), r.get("data_src",{}).get("away","-"), x.get("snap","-")))
    L.append("- **λ**: 主 %.2f / 客 %.2f / 合计 %.2f" % (lam.get("home",0), lam.get("away",0), lam.get("sum",0)))
    L.append("- **1X2 模型**: 主 %.1f%% / 平 %.1f%% / 客 %.1f%%｜市场公平: 主 %s / 平 %s / 客 %s" % (
        wdl.get("home",0), wdl.get("draw",0), wdl.get("away",0),
        mf.get("home","-"), mf.get("draw","-"), mf.get("away","-")))
    L.append("")
    if r.get("bets"):
        L.append("### 全市场候选")
        L.append("")
        L.append("| 方向 | 模型概率 | 赔率 | EV | 封顶/原始 |")
        L.append("|---|---|---|---|---|")
        for b in r["bets"]:
            capped = b.get("prob_raw") is not None and abs((b.get("prob_raw") or 0) - b.get("prob",0)) > 0.001
            tag = ("封顶%.0f%%" % (b.get("prob_raw",0)*100)) if capped else "原始"
            L.append("| %s | %.1f%% | %.2f | %s | %s |" % (
                b.get("name","-"), b.get("prob",0)*100, b.get("odds",0), pct(b.get("ev")), tag))
    L.append("")
    if bb2:
        L.append("### ✅ BEST: **%s** %.0f%% @%.2f **EV %s** ★%d[%s]" % (
            bb2["name"], bb2["prob"]*100, bb2["odds"], pct(bb2["ev"]), bb2.get("star",0), bb2.get("ev_tier","?")))
    else:
        L.append("### ❌ 无正EV出单")
    L.append("")
    if di.get("vetoed"):
        L.append("> ⛔ 方向被否决：%s" % (di.get("veto_reason") or "-"))
    if r.get("risk_tags"):
        L.append("> 风险: %s" % "；".join(r["risk_tags"]))
    dw = r.get("draw_warn")
    if dw:
        L.append("> ⚠ 平局预警: 市场去水平局 %.0f%%（%s）" % (dw.get("market_draw_prob",0)*100, "强" if dw.get("strong") else "常规"))
    if r.get("notes"):
        L.append("> 说明: %s" % "；".join(r["notes"]))
    L.append("")
    L.append("---")
    L.append("")

out = os.path.join(OUT, "rerun_0822_live.md")
io.open(out, "w", encoding="utf-8").write("\n".join(L))
print("saved:", out, "lines:", len(L))
