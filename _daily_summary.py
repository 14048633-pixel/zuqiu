# -*- coding: utf-8 -*-
"""每日拉取汇总: 读 v2_best_scan -> 统计 -> 写 daily_pull_YYYYMMDD.md"""
import io, json, sys
from collections import Counter, defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

IN = r"D:\足球分析\analysis_records\v2_best_scan_20260905_0905.json"
OUT = r"D:\足球分析\analysis_records\daily_pull_20260905.md"
d = json.load(io.open(IN, encoding="utf-8"))

lg_cnt = Counter()
best_cnt = 0
star_cnt = Counter()
mkt_cnt = Counter()
inj_cnt = 0
inj_notes = []
best_rows = []
legs_total = 0
high_conf = []  # ★3
for m in d:
    lg_cnt[m["league"]] += 1
    if m.get("best"):
        best_cnt += 1
        best_rows.append((m["home"], m["away"], m["league"], m["best"]))
    if (m.get("injury_coef") or [1, 1]) not in ([1.0, 1.0], [1, 1]):
        inj_cnt += 1
    bs = m.get("bets") or []
    legs_total += len(bs)
    for b in bs:
        star_cnt[b.get("star")] += 1
        mkt_cnt[b.get("mkt")] += 1
        if b.get("star") == 3:
            high_conf.append((m["home"], m["away"], m["league"], b))
    for b in bs:
        if b.get("mkt") == "ou" and "small" in b.get("name", ""):
            inj_notes.append((m["home"], m["away"], b.get("name"), b.get("odds"), b.get("ev"), b.get("star")))

# 时间排序
def ko_key(m):
    return m.get("ko_bjt") or ""
d_sorted = sorted(d, key=ko_key)

lines = []
A = lines.append
A("# 每日数据拉取 · 2026-09-05")
A("")
A("> 由定时任务「足球每日数据拉取」触发 · 新系统 batch_predict.py（BSD 赛程 + 伤停λ修正）")
A("")
A("## 一、总览")
A("")
A("| 指标 | 数值 |")
A("|---|---|")
A("| 可跑场次（本地有数据） | %d |" % len(d))
A("| 有 BEST 推荐 | %d |" % best_cnt)
A("| 总腿数 | %d |" % legs_total)
A("| 有伤停λ修正场次 | %d |" % inj_cnt)
A("")
A("## 二、星级分布（腿）")
A("")
A("| 星级 | 腿数 |")
A("|---|---|")
for s in (3, 2, 1):
    A("| ★%d | %d |" % (s, star_cnt.get(s, 0)))
A("")
A("## 三、市场分布（腿）")
A("")
A("| 市场 | 腿数 |")
A("|---|---|")
for mk, n in mkt_cnt.most_common():
    A("| %s | %d |" % (mk, n))
A("")
A("## 四、联赛分布（可跑场次）")
A("")
A("| 联赛 | 场次 |")
A("|---|---|")
for lg, n in lg_cnt.most_common():
    A("| %s | %d |" % (lg, n))
A("")
A("## 五、★3 高置信推荐")
A("")
if high_conf:
    A("| 对阵 | 联赛 | 方向 | 概率 | 赔率 | EV |")
    A("|---|---|---|---|---|---|")
    for h, aw, lg, b in high_conf:
        A("| %s vs %s | %s | %s | %.0f%% | %.2f | %+.1f%% |" % (
            h, aw, lg, b["name"], b["prob"], b["odds"], b["ev"]))
else:
    A("（本批无 ★3 高置信腿）")
A("")
A("## 六、全部 BEST 推荐")
A("")
for h, aw, lg, b in best_rows:
    A("- **%s vs %s**（%s）：%s p%.0f%% @%.2f EV%+.1f%% ★%d%s" % (
        h, aw, lg, b["name"], b.get("prob", 0), b.get("odds", 0), b.get("ev", 0),
        b.get("star", 0), " ⚠" if b.get("note") else ""))
A("")
A("## 七、伤停修正摘要")
A("")
A("场次（系数非 1.0）：%d/%d。系数偏离 >5%% 的场次：" % (inj_cnt, len(d)))
for m in d_sorted:
    c = m.get("injury_coef") or [1, 1]
    if abs(c[0] - 1) > 0.05 or abs(c[1] - 1) > 0.05:
        A("- **%s vs %s**（%s）：主x%.3f 客x%.3f ｜ %s" % (
            m["home"], m["away"], m["league"], c[0], c[1], m.get("injury_note") or ""))
A("")
A("## 八、待办/备注")
A("")
A("- 本批为 9/5 09:00 → 9/6 09:00 窗口（欧洲 9/5 晚 + 美洲 9/6 早）")
A("- Puebla 场次已取消（BSD cancelled）；延期场未计入")
A("- 结算建议：赛后跑 `settle_snapshot.py` 出单快照 + `_signal_review.py --write` 沉淀伤停信号")
A("- 数据来源：BSD 赛程/盘口 + 本地历史库拟合；赔率缺失场次已跳过")
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("written ->", OUT)
print("可跑 %d | BEST %d | 腿 %d | ★3 %d | 伤停修正 %d" % (
    len(d), best_cnt, legs_total, star_cnt.get(3, 0), inj_cnt))
