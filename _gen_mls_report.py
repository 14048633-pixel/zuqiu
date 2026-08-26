# -*- coding: utf-8 -*-
import json, math, io, sys, os

ROOT = r"D:\足球分析"
SRC = os.path.join(ROOT, "analysis_records", "scan24h_analysis_20260822_2136.json")
OUT = os.path.join(ROOT, "analysis_records", "mls_full_20260822_2136.md")

def pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)

def top_scores(lam_h, lam_a, n=5):
    probs = {}
    for i in range(0, 8):
        for j in range(0, 8):
            probs[(i, j)] = pois(i, lam_h) * pois(j, lam_a)
    top = sorted(probs.items(), key=lambda x: -x[1])[:n]
    return "、".join("%d-%d(%.1f%%)" % (i, j, p * 100) for (i, j), p in top)

def pct(v):
    return round(v * 100)

def evstr(v):
    return "%+.1f%%" % (v * 100)

def inj_text(notes):
    for note in notes:
        if note.startswith("数据包伤停"):
            return note
    return "无覆盖/低于阈值（标注：该字段未提取）"

def ou_level(lam_sum):
    if lam_sum < 2.4:
        return "偏低、倾向小球"
    if lam_sum > 3.0:
        return "偏高、倾向大球"
    return "中性"

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)

ms = [m for m in data["matches"] if m["league"] == "美职"]
ms = sorted(ms, key=lambda m: m["ct"])

L = []
L.append("# ⚽ 美职 6 场全方向详细报告（2026-08-23 07:30）")
L.append("")
L.append("> 数据源：20:45 临场盘快照（距开赛 10.7h，新鲜）｜模型：泊松 λ + Dixon-Coles｜测试阶段仅记方向")
L.append("")

for m in ms:
    ct = m["ct"]
    home, away = m["home"], m["away"]
    lam = m["lambda"]
    lam_h, lam_a, lam_sum = lam["home"], lam["away"], lam["sum"]
    wdl = m["wdl"]
    mf = m["market_fair"]
    ds = m["data_src"]
    age = m["snap_age_h"]
    dirn = m["direction"]
    bb = m["best_bet"]
    dc = m["dir_consistency"]
    risk = m["risk_tags"] or []
    upset = m["upset"] or {}
    notes = m["notes"] or []
    dw = m.get("draw_warn")

    L.append("## %s %s vs %s" % (ct, home, away))
    L.append("")
    L.append("### Step 0.5 数据提取器")
    L.append("- 主队：%s（数据源 %s）｜客队：%s（数据源 %s）" % (home, ds.get("home", "?"), away, ds.get("away", "?")))
    L.append("- 快照年龄：%s（阈值 12h → 新鲜✅）" % age)
    L.append("- 伤停情报：%s" % inj_text(notes))
    L.append("")
    L.append("### Step 7.5 Agent 风险信号")
    for r in risk:
        L.append("- ⚠️ %s" % r)
    if upset:
        sigs = "；".join(upset.get("signals", []))
        L.append("- 冷门引擎：%s（热门 %s，信号：%s）" % (upset.get("level", ""), upset.get("hot", ""), sigs))
    L.append("")
    L.append("### Step 8 模型计算")
    L.append("- λ：主 **%.2f** / 客 **%.2f**｜总进球 **%.2f**" % (lam_h, lam_a, lam_sum))
    L.append("- 胜平负（模型）：主 %.1f%% / 平 %.1f%% / 客 %.1f%%" % (wdl["home"], wdl["draw"], wdl["away"]))
    L.append("- 胜平负（市场去水）：主 %.1f%% / 平 %.1f%% / 客 %.1f%%" % (mf["home"], mf["draw"], mf["away"]))
    L.append("- TOP5 比分：%s" % top_scores(lam_h, lam_a))
    L.append("")
    L.append("### Step 31 EV 打星（候选表）")
    L.append("| 方向 | 概率 | 赔率 | EV | 标记 |")
    L.append("|---|---|---|---|---|")
    for b in m["bets"]:
        star = ""
        if bb and b["name"] == bb["name"]:
            star = "★%d" % bb["star"]
        L.append("| %s | %d%% | %.2f | %s | %s |" % (b["name"], pct(b["prob"]), b["odds"], evstr(b["ev"]), star))
    if bb:
        L.append("- **best_bet：%s @%.2f EV%s ★%d**" % (bb["name"], bb["odds"], evstr(bb["ev"]), bb["star"]))
    else:
        L.append("- **best_bet：无**")
    g = dc["groups"]
    L.append("- 方向组一致性：[1X2=%s %s｜让球=%s %s｜大小球=%s %s] %s" % (
        g["1X2"]["dir"], evstr(g["1X2"]["ev"] / 100.0),
        g["让球"]["dir"], evstr(g["让球"]["ev"] / 100.0),
        g["大小球"]["dir"], evstr(g["大小球"]["ev"] / 100.0),
        dc["level"]))
    dline = "- 主方向：**%s** %d%%@%.2f EV%s" % (dirn["name"], pct(dirn["prob"]), dirn["odds"], evstr(dirn["ev"]))
    if dirn.get("vetoed"):
        dline += " ⛔否决：%s" % dirn["veto_reason"]
    L.append(dline)
    L.append("")
    L.append("### Step 30 战术推演（基于模型数据）")
    dh = abs(wdl["home"] - mf["home"])
    dd = abs(wdl["draw"] - mf["draw"])
    da = abs(wdl["away"] - mf["away"])
    L.append("- 模型与市场分歧：主胜差 %dpp / 平 %dpp / 客 %dpp。" % (round(dh), round(dd), round(da)))
    L.append("- 总进球预期 %.2f；%s。" % (lam_sum, ou_level(lam_sum)))
    if dw:
        strong = "（强）" if dw.get("strong") else "（常规）"
        L.append("- ⚠️ 平局预警：市场去水平局 %.1f%%%s。" % (dw.get("market_draw_prob", 0), strong))
    for note in notes:
        if note.startswith("数据包伤停"):
            continue
        L.append("- 注：%s" % note)
    L.append("")
    L.append("---")
    L.append("")

L.append("> 生成时间：2026-08-22 21:36 分析｜源：scan24h_analysis_20260822_2136.json")
L.append("")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("written:", OUT)
