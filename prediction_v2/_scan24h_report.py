# -*- coding: utf-8 -*-
"""scan24h_analysis JSON -> 整洁 MD 报告"""
import json, glob, os, sys, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BJT = timezone(timedelta(hours=8))
f = sorted(glob.glob("analysis_records/scan24h_analysis_*.json"), key=os.path.getmtime)[-1]
d = json.load(open(f, encoding="utf-8"))
ms = d["matches"]
now = datetime.now(BJT)

def age(r):
    a = r.get("snap_age_h")
    return a if a is not None else 999

def started(r):
    try:
        kt = datetime.strptime(r["ct"], "%m-%d %H:%M").replace(year=2026, tzinfo=BJT)
    except Exception:
        return False
    return kt <= now

fresh = [r for r in ms if age(r) <= 12]
stale = [r for r in ms if age(r) > 12]
no_odds = d.get("unmatched", [])
bb_all = [r for r in ms if r.get("best_bet")]
draw_warns = [r for r in ms if r.get("draw_warn")]

def fmt_dir(r):
    di = r.get("direction")
    if not di:
        return "—"
    s = "**%s** %.0f%% @%.2f" % (di["name"], di["prob"] * 100, di["odds"])
    if di.get("wdl_name"):
        s += "（胜平负看%s %.0f%%）" % (di["wdl_name"], di["wdl_prob"] * 100)
    if di.get("vetoed"):
        s += "　⛔否决：" + (di.get("veto_reason") or "")
    return s

def fmt_bb(r):
    b = r.get("best_bet")
    if not b:
        return "—"
    return "★%d %s %.0f%% @%.2f　EV%+.1f%%" % (b.get("star", 0), b["name"], b["prob"] * 100, b["odds"], b["ev"] * 100)

def fmt_risk(r):
    t = r.get("risk_tags", [])
    return "；".join(t) if t else "—"

def fmt_lamb(r):
    lm = r.get("lambda") or {}
    if not lm:
        return "—"
    return "%.2f / %.2f" % (lm.get("home", 0), lm.get("away", 0))

def row_line(r):
    t = r["ct"] + ("（已开赛）" if started(r) else "")
    return "| %s | %s | %s vs %s | %s | %s | %s | %s |" % (
        t, r["league"], r["home"], r["away"], fmt_lamb(r), fmt_dir(r), fmt_bb(r), fmt_risk(r))

lines = []
lines.append("# ⚽ 2026-8-22 早上8点拉取的比赛 — 有价值场次分析（111 场）")
lines.append("")
lines.append("> 扫描窗口：%s ～ %s（+08:00）｜生成时间：%s" % (d.get("window_start", "?"), d.get("window_end", "?"), now.strftime("%Y-%m-%d %H:%M")))
lines.append("> 数据说明：BSD 比赛包 111/111 拉取成功（攻防 0 缺）；赔率以 the-odds-api 快照为准；伤停无覆盖 35 场（BSD 已知限制）。")
lines.append("")
lines.append("## 📊 总览")
lines.append("")
lines.append("- 有价值场次：**111** 场（20 联赛）｜已分析：**103** 场｜无赔率：**8** 场")
lines.append("- best_bet：**%d** 场（★）｜平局预警：%d 场｜方向否决：%d 场" % (len(bb_all), len(draw_warns),
        sum(1 for r in ms if (r.get("direction") or {}).get("vetoed"))))
lines.append("- 快照新鲜（距开赛≤12h，方向可直接参考）：**%d** 场｜盘口过期（距开赛>12h，需赛前重拉临场）：**%d** 场" % (len(fresh), len(stale)))
lines.append("- 联赛映射修正：%s" % (d.get("mapped_league_fixes") or "无"))
lines.append("")
lc = collections.Counter(r["league"] for r in ms)
lines.append("## 🏆 联赛分布")
lines.append("")
lines.append(" | ".join("%s %d" % (k, v) for k, v in lc.most_common()))
lines.append("")
if bb_all:
    lines.append("## ✅ BEST（★ 建议关注）")
    lines.append("")
    lines.append("| 时间 | 联赛 | 对阵 | λ(主/客) | 方向 | 最佳推荐 | 风险 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in sorted(bb_all, key=lambda x: x["ct"]):
        lines.append(row_line(r))
    lines.append("")
lines.append("## 🕐 快照新鲜（距开赛 ≤12h，方向可参考）")
lines.append("")
lines.append("| 时间 | 联赛 | 对阵 | λ(主/客) | 方向 | BEST | 风险 |")
lines.append("|---|---|---|---|---|---|---|")
for r in sorted(fresh, key=lambda x: x["ct"]):
    lines.append(row_line(r))
lines.append("")
lines.append("## ⏳ 盘口过期（距开赛 >12h，方向为预判，赛前需重拉临场快照）")
lines.append("")
lines.append("| 时间 | 联赛 | 对阵 | λ(主/客) | 方向 | BEST | 风险 |")
lines.append("|---|---|---|---|---|---|---|")
for r in sorted(stale, key=lambda x: x["ct"]):
    lines.append(row_line(r))
lines.append("")
lines.append("## ❌ 无赔率（8 场，未匹配到 the-odds-api 快照，无法出方向）")
lines.append("")
lines.append("| 时间 | 联赛 | 对阵 | 备注 |")
lines.append("|---|---|---|---|")
note_map = {
    "FC Thun vs Servette FC": "扫描标瑞超（瑞典超），实为瑞士超，源未覆盖",
    "FC Luzern vs FC Lausanne-Sport": "扫描标瑞超（瑞典超），实为瑞士超，源未覆盖",
    "FC Zürich vs Basel": "扫描标瑞超（瑞典超），实为瑞士超，源未覆盖",
    "UTA Arad vs FC Corvinul Hunedoara": "扫描标丹超，实为罗甲，源未覆盖",
    "FC Dinamo București vs FC Universitatea Cluj": "扫描标丹超，实为罗甲，源未覆盖",
    "Club León vs CF Monterrey": "墨超，快照仅有次日 09:00 BJT 场次，需按正确开赛时间重拉",
    "Querétaro FC vs CD Toluca": "墨超，同上，快照只有次日场次",
    "KAA Gent vs Oud-Heverlee Leuven": "比甲，源未覆盖该场",
}
for u in sorted(no_odds, key=lambda x: x.get("kickoff_iso", "")):
    try:
        t = datetime.fromisoformat(u["kickoff_iso"].replace("Z", "+00:00")).astimezone(BJT).strftime("%m-%d %H:%M")
    except Exception:
        t = str(u.get("kickoff_iso", "?"))
    k = "%s vs %s" % (u["home"], u["away"])
    lines.append("| %s | %s | %s vs %s | %s |" % (t, u["league"], u["home"], u["away"], note_map.get(k, "源未覆盖")))
lines.append("")
lines.append("## 📌 数据质量备注")
lines.append("")
lines.append("1. **J1（7 场）**：本地攻防仅 1~2 场样本（2026/27 新跨年赛季开局），全部收缩至联赛均值，λ 无区分度（均 1.51/1.51）；方向仅供冷启动参考，需赛前随样本累积重算。")
lines.append("2. **中超（5 场）**：已正常出方向，其中 19:00 后场次盘口在开赛 12h 外，属过期预判。")
lines.append("3. **盘口过期否决**：距开赛 >12h 的快照一律标 ⛔ 否决（阈值 12h）；定时任务每 30 分钟全量 + 赛前 5 分钟增量刷新，越接近开赛快照越新，否决会自动解除。")
lines.append("4. **伤停情报**：BSD 包内伤停覆盖不足（35 场无覆盖），均标注「纯数据无伤病情报」。")
lines.append("5. **映射修正**：丹超→罗甲 1 场（Petrolul vs Rapid）已按赔率侧联赛分析；其余罗甲/瑞士超场次无赔率。")
lines.append("6. **已开赛**：生成时间（%s）之前开球的场次标「已开赛」，方向仅作复盘参考。" % now.strftime("%H:%M"))
lines.append("")
outf = f.replace(".json", ".md")
open(outf, "w", encoding="utf-8").write("\n".join(lines))
print("saved:", outf)
print("fresh:", len(fresh), "stale:", len(stale), "no_odds:", len(no_odds), "best_bet:", len(bb_all))
