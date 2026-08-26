# -*- coding: utf-8 -*-
import io, json, os
from datetime import datetime, timezone, timedelta
ROOT = r"D:\足球分析"
BJT = timezone(timedelta(hours=8))

L = []
L.append("# 临场盘特征验证（2026-08-25）")
L.append("")
L.append("## 一、历史回测：临场盘口特征有没有用（无泄漏重放）")
L.append("")
L.append("方法：账本已结算 BEST 场次，每场用快照库重放「最早赛前快照(早盘) vs 最晚赛前快照(临场)」，各自重算 BEST 腿，结算对比。")
L.append("")
L.append("| 分组 | 场次 | 命中 | ROI |")
L.append("| --- | --- | --- | --- |")
L.append("| 临场有效盘(≤12h) BEST 出单 | 27 | **66.7%** | **+28.8%** |")
L.append("| 强临场(≤3h) BEST 出单 | 19 | 63.2% | +24.7% |")
L.append("| 早盘过期→临场救回 | 22 | **72.7%** | **+40.7%** |")
L.append("| 账本历史 ★出单（对照） | 161 | 51.9% | +0.3% |")
L.append("")
L.append("结论：**临场盘特征有效**——命中提升约 15pp，ROI 提升约 28pp；最大价值在「救回早盘过期被否决、但临场实际是高价值」的场次（命中 72.7%）。")
L.append("")
L.append("注意：样本仅 27 场，方向一致但需继续积累；历史快照大多距开赛 100h+，真正的临场盘此前稀缺。")
L.append("")
L.append("## 二、只拉 BEST 场次临场盘（BSD 免费 consensus）")
L.append("")
L.append("脚本：`prediction_v2/_pull_best_live.py`（BSD 现场拉最新 consensus，重算 BEST 腿 EV）")
L.append("")
now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M")
L.append("### 今日 8 场 BEST 临场确认（%s）" % now)
L.append("")
L.append("| 时间 | 对阵 | 腿 | 原EV | 临场EV | ΔEV | 状态 |")
L.append("| --- | --- | --- | --- | --- | --- | --- |")
fs = sorted(__import__("glob").glob(os.path.join(ROOT, "analysis_records", "best_live_confirm_*.json")), key=os.path.getmtime)
if fs:
    d = json.load(io.open(fs[-1], encoding="utf-8"))
    for r in d:
        ev = ("%+.1f%%" % (r["orig_ev"]*100)) if r["orig_ev"] is not None else "-"
        lv = ("%+.1f%%" % (r["live_ev"]*100)) if r["live_ev"] is not None else "-"
        dv = ("%+.1f%%" % (r["delta_ev"]*100)) if r["delta_ev"] is not None else "-"
        L.append("| %s | %s vs %s | %s | %s | %s | %s | %s |" % (r["ko"], r["home"], r["away"], r["leg"], ev, lv, dv, r["status"]))
L.append("")
L.append("## 三、落地建议")
L.append("")
L.append("1. 每轮扫描出 BEST 后，只对 BEST 场次跑 `_pull_best_live.py` 拉临场盘（BSD 免费），临场 EV≥5% 才保留出单；临场掉出的场次标记观察。")
L.append("2. 账本新增字段 `live_ev / delta_ev / live_snap`，结算后按「临场确认 vs 掉出」分组统计，300 场后验证本次回测结论。")
L.append("3. 亚盘腿 BSD 无数据：临场确认时用 API-Football 免费 100 次/天补 BEST 场次亚盘。")
L.append("")

p = os.path.join(ROOT, "analysis_records", "live_feature_report_20260825.md")
io.open(p, "w", encoding="utf-8").write("\n".join(L))
print("saved", p)
