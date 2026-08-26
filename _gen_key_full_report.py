# -*- coding: utf-8 -*-
import io, json
ROOT = r"D:\足球分析"
mev = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
key = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
km = json.load(io.open(ROOT + r"\analysis_records\ou_key_matches_20260819.json", encoding="utf-8"))
by = {r["id"]: r for r in key}
mev_by = {r["id"]: r for r in mev}

def mkt_over(o):
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if not ov or not un: return None, None
    po = (1.0/ov) / (1.0/ov + 1.0/un)
    return po*100, ("大" if po > 0.5 else "小")

def fmt_ev(v):
    return ("%+.1f%%" % (v*100)) if v is not None else "—"

L = []
L.append("# 重点场次完整报告（2026-08-19）")
L.append("")
L.append("> 分级依据：74场已结算验证（模型大球=价值方向64.1%/+19%、模型小球=亏损方向45.7%/-15.1%）")
L.append("> 规则：P1=模型大+λ正常2.6~3.4+市场同向大｜P2=模型大但λ异常>3.5需复核｜P3=模型小球降权")
L.append("> 数据：BSD赔率/预测 + the-odds交叉 + 旧raw λ模型 + 快照 08-18 14:57Z（早盘，临场需重拉）")
L.append("")

def detail_block(x, tag):
    rid = None
    for k in by:
        if by[k]["home"]==x["home"] and by[k]["away"]==x["away"] and by[k]["kickoff"]==x["ko"]:
            rid = k; break
    k = by.get(rid, {})
    m = mev_by.get(rid, {})
    o = k.get("bsd_odds") or {}
    bo = k.get("bsd_ou25") or {}
    bp = k.get("bsd_pred") or {}
    to = (k.get("to") or {}).get("ou25") or {}
    mp, md = mkt_over(o)
    lam = x.get("lam")
    lam_s = ("%.2f" % lam) if lam else "—"
    ov = o.get("over_25_goals"); un = o.get("under_25_goals")
    odds = ("%.2f / %.2f" % (ov, un)) if ov else "—"
    eg = bp.get("eg") or {}
    recs = bp.get("recs") or {}
    bsdp = bp.get("prob")
    L.append("### %s %s | %s vs %s" % (x["ko"], x["lg"], x["home"], x["away"]))
    L.append("")
    L.append("| 项目 | 值 |")
    L.append("|------|-----|")
    L.append("| 分级 | %s（%s） |" % (tag, {
        1: "模型大+λ正常+市场同向大",
        2: "模型大但λ异常>3.5，人工复核",
        3: "模型小球=亏损方向，降权",
    }.get(x.get("pri"), "")))
    L.append("| λ和(旧raw) | %s（主%.2f/客%.2f） |" % (lam_s, m.get("lam",[None,None])[0] or 0, m.get("lam",[None,None])[1] or 0))
    L.append("| 模型方向 | 大2.5 %.0f%% / 小2.5 %.0f%% |" % (x["over_p"], 100-x["over_p"]))
    L.append("| 市场方向 | %s（去水 %.0f%%） |" % (md or "—", mp or 0))
    L.append("| 盘口 | 大 %s / 小 %s |" % (odds, ""))
    L.append("| 模型EV | %s |" % fmt_ev(x["ev"]))
    L.append("| 模型vs市场差 | %+.1fpp |" % ((x["over_p"] - mp) if mp else 0))
    L.append("| BSD大小球 | %s %.0f%% |" % (bo.get("dir") or "—", bo.get("prob") or 0))
    L.append("| BSD比分预测 | %s（主%.2f/客%.2f, 置信%.0f%%） |" % (bp.get("score") or "—", eg.get("home") or 0, eg.get("away") or 0, bsdp or 0))
    L.append("| BSD推荐 | %s |" % (recs or "—"))
    L.append("| the-odds交叉 | %s %.0f%%（大%.2f/小%.2f） |" % (to.get("dir") or "—", to.get("dir_prob") or 0, to.get("over") or 0, to.get("under") or 0))
    L.append("| 快照时间 | %s |" % (k.get("bsd_odds_ts") or "—"))
    L.append("")

L.append("## P1 重点（15场）")
L.append("")
for x in km["p1"]:
    detail_block(x, "P1")
L.append("## P2 观察（5场）")
L.append("")
for x in km["p2"]:
    detail_block(x, "P2")
L.append("## P3 降权清单（26场·简表）")
L.append("")
L.append("| 时间 | 联赛 | 对阵 | λ和 | 模型 | EV | 市场 | 分组 |")
L.append("|------|------|------|-----|------|-----|------|------|")
for x in km["p3"]:
    mp = x.get("mkt_p")
    same = "同向" if x.get("mkt")==x["model"] else "反向"
    L.append("| %s | %s | %s vs %s | %.2f | 小2.5 %.0f%% | %s | %s %.0f%% | %s |" % (
        x["ko"], x["lg"], x["home"], x["away"], x["lam"] or 0, 100-x["over_p"],
        fmt_ev(x["ev"]), x.get("mkt") or "—", mp or 0, same))

fn = ROOT + r"\analysis_records\ou_key_full_report_20260819.md"
io.open(fn, "w", encoding="utf-8").write("\n".join(L))
print("saved:", fn)
print("P1:", len(km["p1"]), "P2:", len(km["p2"]), "P3:", len(km["p3"]))
