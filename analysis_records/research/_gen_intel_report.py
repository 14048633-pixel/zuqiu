# -*- coding: utf-8 -*-
"""rerun_0822_intel.md 报告生成"""
import sys, io, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\足球分析\analysis_records\research"
d = json.load(io.open(os.path.join(OUT, "rerun_0822_intel.json"), encoding="utf-8"))
rows = sorted(d["matches"], key=lambda x: (x["ct"][:5], x["league"]))

def pct(o): return ("%+.1f%%" % (o*100)) if isinstance(o,(int,float)) else "-"
L = []
L.append("# 08-22 凌晨 27 场 重算报告 v2（最新赔率 + BSD伤停/阵型情报注入）")
L.append("")
L.append("- 快照: %s｜模型: scan_upcoming 完整链路 + match_package 情报增强" % d.get("pulled_at",""))
L.append("- 情报注入: %d/%d 场（伤停名单/阵型/BSD盘口）｜出单口径: 批量 EV≥5%%；硬否决: 分歧>20pp" % (d.get("used_pkg",0), len(rows)))
L.append("")

bb = [x for x in rows if x["result"].get("best_bet")]
veto = [x for x in rows if x["result"].get("direction",{}).get("vetoed")]
n_pos = sum(1 for x in rows if any(b.get("ev",0)>0 for b in x["result"].get("bets") or []))
n_intel = sum(1 for x in rows if any("BSD伤停情报" in (t or "") for t in (x["result"].get("risk_tags") or [])))
L.append("## 📊 总览")
L.append("")
L.append("| 指标 | 值 |")
L.append("|---|---|")
L.append("| 总场次 | %d |" % len(rows))
L.append("| 出单 best_bet | %d |" % len(bb))
L.append("| 正EV场次 | %d |" % n_pos)
L.append("| 硬否决 | %d |" % len(veto))
L.append("| 有BSD伤停情报 | %d |" % n_intel)
L.append("")
L.append("### 出单列表（%d 场）" % len(bb))
L.append("")
L.append("| 开赛 | 联赛 | 比赛 | 出单方向 | 概率 | 赔率 | EV | 星级 | 分层 | 伤停情报 | 风险 |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|")
for x in sorted(bb, key=lambda t: -((t["result"].get("best_bet") or {}).get("ev",0))):
    r = x["result"]; b = r["best_bet"]
    rt = r.get("risk_tags") or []
    intel = next((t for t in rt if "BSD伤停情报" in t), "无")
    L.append("| %s | %s | %s vs %s | %s | %.0f%% | %.2f | %s | ★%d | %s | %s | %s |" % (
        x["ct"], x["league"], x["home"], x["away"], b["name"], b["prob"]*100, b["odds"],
        pct(b["ev"]), b.get("star",0), b.get("ev_tier","?"), intel, ",".join(rt)[:70]))
L.append("")
L.append("### 硬否决（%d 场）" % len(veto))
L.append("")
L.append("| 开赛 | 联赛 | 比赛 | 方向(否决前) | EV | 否决原因 |")
L.append("|---|---|---|---|---|---|")
for x in sorted(veto, key=lambda t: -((t["result"].get("direction") or {}).get("ev",0))):
    r = x["result"]; di = r.get("direction") or {}
    L.append("| %s | %s | %s vs %s | %s | %s | %s |" % (
        x["ct"], x["league"], x["home"], x["away"], di.get("name","-"), pct(di.get("ev")),
        (di.get("veto_reason") or "-")[:55]))
L.append("")
L.append("---")
L.append("")

for x in rows:
    r = x["result"]
    if "error" in r:
        L.append("## ❌ %s | %s vs %s（%s）：%s" % (x["league"], x["home"], x["away"], x["ct"], r["error"]))
        L.append(""); continue
    lam = r.get("lambda") or {}; wdl = r.get("wdl") or {}; mf = r.get("market_fair") or {}
    di = r.get("direction") or {}; bb2 = r.get("best_bet")
    fm = r.get("formation") or {}; ip = r.get("injury_pos") or {}; bs = r.get("bsd") or {}
    L.append("## %s | %s vs %s（%s）" % (x["league"], x["home"], x["away"], x["ct"]))
    L.append("")
    L.append("- 数据源: 主[%s] 客[%s]｜snap %s" % (r.get("data_src",{}).get("home","-"), r.get("data_src",{}).get("away","-"), x.get("snap","-")))
    L.append("- **λ**: 主 %.2f / 客 %.2f / 合计 %.2f" % (lam.get("home",0), lam.get("away",0), lam.get("sum",0)))
    L.append("- **1X2 模型**: 主 %.1f%% / 平 %.1f%% / 客 %.1f%%｜市场公平: 主 %s / 平 %s / 客 %s" % (
        wdl.get("home",0), wdl.get("draw",0), wdl.get("away",0),
        mf.get("home","-"), mf.get("draw","-"), mf.get("away","-")))
    if fm.get("home") or fm.get("away"):
        L.append("- **阵型**: 主 %s / 客 %s（%s）" % (fm.get("home") or "-", fm.get("away") or "-", "当场" if fm.get("src")=="cur" else "偏好"))
    if ip.get("home") or ip.get("away"):
        L.append("- **伤停位置**: 主 %s / 客 %s（未知%d）" % (dict(ip.get("home") or {}) or "-", dict(ip.get("away") or {}) or "-", ip.get("unknown",0)))
    if bs.get("ev") is not None:
        L.append("- **BSD双口径EV**: %s（我方EV %s）" % (pct(bs["ev"]), pct((di.get("ev") or 0))))
    L.append("")
    if r.get("bets"):
        L.append("### 全市场候选")
        L.append("")
        L.append("| 方向 | 模型概率 | 赔率 | EV | 封顶/原始 |")
        L.append("|---|---|---|---|---|")
        for b in r["bets"]:
            capped = b.get("prob_raw") is not None and abs((b.get("prob_raw") or 0) - b.get("prob",0)) > 0.001
            tag = ("封顶%.0f%%" % (b.get("prob_raw",0)*100)) if capped else "原始"
            L.append("| %s | %.1f%% | %.2f | %s | %s |" % (b.get("name","-"), b.get("prob",0)*100, b.get("odds",0), pct(b.get("ev")), tag))
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
    if r.get("notes"):
        L.append("> 说明: %s" % "；".join(r["notes"]))
    L.append("")
    L.append("---")
    L.append("")

out = os.path.join(OUT, "rerun_0822_intel.md")
io.open(out, "w", encoding="utf-8").write("\n".join(L))
print("saved:", out, "lines:", len(L))
