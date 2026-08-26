# -*- coding: utf-8 -*-
import sys, io, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))
results = d["results"]

def cell(b, t):
    if b and t:
        return f"{b['dir']} {b['prob']:.0f}% (BSD) / {t['dir']} {t.get('dir_prob', 0):.0f}% (TO)"
    if b:
        return f"{b['dir']} {b['prob']:.0f}%"
    if t:
        return f"{t['dir']} {t.get('dir_prob', 0):.0f}% (TO)"
    return "—"

now8 = datetime.now(timezone(timedelta(hours=8)))
L = ["# 46 场重点联赛方向扫描（欧冠7/欧联12/欧协联24/中超1/西甲2）", ""]
L.append(f"> 拉取 {now8:%Y-%m-%d %H:%M} | BSD 共识赔率+预测 + the-odds-api 交叉(欧冠/中超/西甲) | 测试期只观察不下单")
L.append("> 方向=去水后最大概率边; BSD预测=BSD dc-blend-v1; TO=the-odds-api")
L.append("")
for lg in ("欧冠", "欧联", "欧协联", "中超", "西甲"):
    grp = [r for r in results if r["league"] == lg]
    L.append(f"## {lg}（{len(grp)} 场）")
    L.append("| 开赛 | 比赛 | 1X2 | 大小2.5 | BSD预测(置信) | BSD λ(主/客) | 让球(TO) |")
    L.append("|---|---|---|---|---|---|---|")
    for r in grp:
        c1 = cell(r.get("bsd_1x2"), (r.get("to") or {}).get("1x2"))
        c2 = cell(r.get("bsd_ou25"), (r.get("to") or {}).get("ou25"))
        pd = r.get("bsd_pred") or {}
        eg = pd.get("eg") or {}
        pdir = {"H": "主胜", "D": "平局", "A": "客胜"}.get(pd.get("dir"), "—")
        sp = (r.get("to") or {}).get("spread")
        sp_s = "—"
        if sp:
            hdp = sp["hdp_home"]
            sp_s = f"主让{hdp} {sp['fair'][0]:.0f}%" if hdp < 0 else f"主受+{abs(hdp)} {sp['fair'][0]:.0f}%"
        L.append(f"| {r['kickoff']} | {r['home']} vs {r['away']} | {c1} | {c2} | {pdir}({pd.get('prob', 0):.0f}%) | {eg.get('home', 0):.2f}/{eg.get('away', 0):.2f} | {sp_s} |")
    L.append("")
L.append("## 三方同向提示（市场1X2 + BSD预测 同向且市场优势≥55%）")
n_hint = 0
for r in results:
    b = r.get("bsd_1x2") or {}
    pd = r.get("bsd_pred") or {}
    if not b or not pd.get("dir"):
        continue
    dir_cn = {"H": "主胜", "D": "平局", "A": "客胜"}.get(pd["dir"])
    if dir_cn and dir_cn == b.get("dir") and (b.get("prob") or 0) >= 55:
        L.append(f"- **{r['home']} vs {r['away']}**（{r['league']} {r['kickoff']}）：市场{b['dir']} {b['prob']:.0f}% = BSD{dir_cn} {pd.get('prob', 0):.0f}%，λ {(pd.get('eg') or {}).get('home', 0):.2f}/{(pd.get('eg') or {}).get('away', 0):.2f}")
        n_hint += 1
if n_hint == 0:
    L.append("- 无")
L.append("")
md = "\n".join(L)
fnm = "key46_%s.md" % now8.strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fnm, "w", encoding="utf-8").write(md)
print("saved analysis_records/" + fnm, "| 同向:", n_hint)
