# -*- coding: utf-8 -*-
"""临场赔率更新汇总: 对比早上(0905) vs 现在(1806) 盘口, 标注异动(>10%)."""
import io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MORN = r"D:\足球分析\analysis_records\v2_best_scan_20260905_0905.json"
EVEN = r"D:\足球分析\analysis_records\v2_best_scan_20260905_1806.json"
OUT = r"D:\足球分析\analysis_records\live_update_20260905_1800.md"

am = json.load(io.open(MORN, encoding="utf-8"))
pm = json.load(io.open(EVEN, encoding="utf-8"))

def key(m):
    return (m.get("home", "").strip().lower(), m.get("away", "").strip().lower())

am_map = {key(m): m for m in am}
common = []
only_pm = []
for m in pm:
    k = key(m)
    if k in am_map:
        common.append((am_map[k], m))
    else:
        only_pm.append(m)
only_am = [m for m in am if key(m) not in {key(x) for x in pm}]

def implied_odds(mkt):
    p = max(mkt, 0.01)
    return 1.0 / (p / 100.0)

moves = []
for a, b in common:
    # 主胜隐含赔率变化
    h_am = implied_odds(a["market_wdl"][0])
    h_pm = implied_odds(b["market_wdl"][0])
    chg = (h_pm - h_am) / h_am * 100
    best_am = (a.get("best") or {}).get("name")
    best_pm = (b.get("best") or {}).get("name")
    moves.append({
        "home": b["home"], "away": b["away"], "league": b["league"], "ko": b["ko_bjt"],
        "h_am": h_am, "h_pm": h_pm, "chg": chg,
        "best_am": best_am, "best_pm": best_pm, "star_am": (a.get("best") or {}).get("star"),
        "star_pm": (b.get("best") or {}).get("star"),
        "model_am": a["model_wdl"], "model_pm": b["model_wdl"],
    })

moves.sort(key=lambda x: abs(x["chg"]), reverse=True)
alerts = [x for x in moves if abs(x["chg"]) > 10]

lines = []
A = lines.append
A("# 临场赔率更新 · 2026-09-05 18:00")
A("")
A("> 定时任务「足球临场赔率更新」· 新系统 batch_predict.py（BSD 最新盘口 + 伤停λ修正）")
A("> 对比基准：今早 09:05 快照 `v2_best_scan_20260905_0905.json`")
A("")
A("## 一、总览")
A("")
A("| 指标 | 数值 |")
A("|---|---|")
A("| 早上可跑场次 | %d |" % len(am))
A("| 临场可跑场次 | %d |" % len(pm))
A("| 两批交集（可比） | %d |" % len(common))
A("| 临场新增场次 | %d |" % len(only_pm))
A("| 早上有、临场无 | %d |" % len(only_am))
A("| **盘口异动（主胜赔率变动>10%%）** | **%d** |" % len(alerts))
A("| 临场 BEST | %d / %d |" % (sum(1 for m in pm if m.get("best")), len(pm)))
A("")
A("## 二、盘口异动预警（主胜赔率变动 >10%）")
A("")
if alerts:
    A("| 对阵 | 联赛 | 开赛 | 早主胜赔 | 临场主胜赔 | 变动 | 早BEST→临场BEST |")
    A("|---|---|---|---|---|---|---|")
    for x in alerts:
        A("| **%s vs %s** | %s | %s | %.2f | %.2f | **%+.0f%%** | %s → %s" % (
            x["home"], x["away"], x["league"], x["ko"], x["h_am"], x["h_pm"], x["chg"],
            x["best_am"] or "-", x["best_pm"] or "-"))
else:
    A("（无）")
A("")
A("## 三、临场 BEST 推荐（全部）")
A("")
for m in pm:
    b = m.get("best")
    if not b:
        continue
    A("- **%s vs %s**（%s %s）：%s p%.0f%% @%.2f EV%+.1f%% ★%d%s" % (
        m["home"], m["away"], m["league"], m["ko_bjt"], b["name"], b.get("prob", 0),
        b.get("odds", 0), b.get("ev", 0), b.get("star", 0),
        " ⚠" if b.get("note") or b.get("note_big_div") else ""))
A("")
A("## 四、★3 高置信")
A("")
s3 = [(m, b) for m in pm for b in (m.get("bets") or []) if b.get("star") == 3]
if s3:
    A("| 对阵 | 方向 | 概率 | 赔率 | EV |")
    A("|---|---|---|---|---|")
    for m, b in s3:
        A("| %s vs %s | %s | %.0f%% | %.2f | %+.1f%% |" % (
            m["home"], m["away"], b["name"], b["prob"], b["odds"], b["ev"]))
else:
    A("（无 ★3）")
A("")
A("## 五、伤停λ修正（系数偏离>5%）")
A("")
for m in pm:
    c = m.get("injury_coef") or [1, 1]
    if abs(c[0] - 1) > 0.05 or abs(c[1] - 1) > 0.05:
        A("- **%s vs %s**：主x%.3f 客x%.3f ｜ %s" % (
            m["home"], m["away"], c[0], c[1], m.get("injury_note") or ""))
A("")
A("## 六、备注")
A("")
A("- 只更新未开赛比赛；临场新增 J1/K1/亚冠等亚洲早场（9/6 白天）")
A("- 赔率源：BSD 共识盘；拉取失败场次已跳过（无默认值）")
A("- P5-fix：修复 fetch_lineups=None 时 injury_detail 为 list 导致崩溃（已回归）")
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("written ->", OUT)
print("交集 %d | 异动 %d | 临场BEST %d | ★3 %d" % (
    len(common), len(alerts), sum(1 for m in pm if m.get("best")), len(s3)))
