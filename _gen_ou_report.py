# -*- coding: utf-8 -*-
import io, json
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\analysis_records\ou_same_opp_settled_20260819.json", encoding="utf-8"))
rows = d["rows"]

def grp(rs):
    n = len(rs); hit = sum(1 for r in rs if r["hit"])
    ret = sum(r["odds"] if r["hit"] else 0.0 for r in rs)
    return n, hit, 100.0*hit/n, 100.0*(ret/n - 1.0)

L = []
L.append("# 已结算实盘：模型大小球 vs 市场方向 分组命中率/ROI（74场）")
L.append("")
L.append("> 数据：08-14~08-19 已完赛，scan 模型OU概率+市场赔率，BSD 赛果核对 | 平注模型方向@市场赔率")
L.append("> 统计口径：同向=模型方向与市场一致；反向=模型逆市场；命中=方向对；ROI=平注")
L.append("")
L.append("## 一、核心结论")
L.append("")
n, hit, hr, roi = grp(rows)
L.append("| 分组 | 场次 | 命中 | 命中率 | 平注ROI |")
L.append("|------|------|------|--------|---------|")
L.append("| **全量** | %d | %d | %.1f%% | %+.1f%% |" % (n, hit, hr, roi))
for name, rs in [("模型=市场 同向", [r for r in rows if r["same"]]),
                 ("模型逆市场 反向", [r for r in rows if not r["same"]]),
                 ("模型大球", [r for r in rows if r["model"]=="大"]),
                 ("模型小球", [r for r in rows if r["model"]=="小"]),
                 ("同向大", [r for r in rows if r["same"] and r["model"]=="大"]),
                 ("同向小", [r for r in rows if r["same"] and r["model"]=="小"]),
                 ("反向大", [r for r in rows if not r["same"] and r["model"]=="大"]),
                 ("反向小", [r for r in rows if not r["same"] and r["model"]=="小"])]:
    a, b, c, dd = grp(rs)
    L.append("| %s | %d | %d | %.1f%% | %+.1f%% |" % (name, a, b, c, dd))
L.append("")
L.append("**要点**：")
L.append("- 跟市场同向：命中 56.5% 但 ROI **-7.4%**（赔率低，命中不够覆盖水钱）——\"市场胜率高\"≠赚钱")
L.append("- 模型逆市场反向：命中 53.6% 但 ROI **+19.8%**（反向时拿的是高赔）")
L.append("- 模型**大球**是价值方向：命中 64.1%、ROI +19.0%；模型**小球**是亏损方向：命中 45.7%、ROI -15.1%")
L.append("- 之前 08-18 那批 16/20=80% 是 20 场小样本运气，且全部同向；拉长到 74 场同向只有 56.5%")
L.append("")
L.append("## 二、按联赛")
L.append("")
L.append("| 联赛 | 场次 | 命中 | 命中率 | ROI |")
L.append("|------|------|------|--------|-----|")
by_league = {}
for r in rows: by_league.setdefault(r["league"], []).append(r)
for lg, rs in sorted(by_league.items(), key=lambda x: -len(x[1])):
    a, b, c, dd = grp(rs)
    L.append("| %s | %d | %d | %.1f%% | %+.1f%% |" % (lg, a, b, c, dd))
L.append("")
L.append("## 三、74 场明细（按时间）")
L.append("")
L.append("| 时间 | 联赛 | 对阵 | 比分 | 总球 | 模型 | 市场 | 赔率 | 命中 | 分组 |")
L.append("|------|------|------|------|------|------|------|------|------|------|")
for r in sorted(rows, key=lambda x: x["ct"]):
    L.append("| %s | %s | %s vs %s | %s | %d | %s | %s | %.2f | %s | %s |" % (
        r["ct"][:16], r["league"], r["home"], r["away"], r["score"], r["total"],
        r["model"], r["mkt"], r["odds"], "✔" if r["hit"] else "✘", "同向" if r["same"] else "反向"))
fn = ROOT + r"\analysis_records\ou_same_opp_settled_20260819.md"
io.open(fn, "w", encoding="utf-8").write("\n".join(L))
print("saved:", fn)
