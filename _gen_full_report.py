# -*- coding: utf-8 -*-
import io, json
ROOT = r"D:\足球分析"

mev = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
key = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
v3d = json.load(io.open(ROOT + r"\analysis_records\key46_v3_lambda_20260818_2357.json", encoding="utf-8"))
settled = json.load(io.open(ROOT + r"\analysis_records\ou_same_opp_settled_20260819.json", encoding="utf-8"))["rows"]
km = json.load(io.open(ROOT + r"\analysis_records\ou_key_matches_20260819.json", encoding="utf-8"))
by = {r["id"]: r for r in key}
v3_by = {r["id"]: r for r in v3d}

def mkt_over(o):
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if not ov or not un: return None, None
    po = (1.0/ov) / (1.0/ov + 1.0/un)
    return po*100, ("大" if po > 0.5 else "小")

def fmt_ev(v):
    return ("%+.1f%%" % (v*100)) if v is not None else "—"

L = []
L.append("# 大小球策略完整报告（2026-08-19）")
L.append("")
L.append("> 内容：①74场已结算实盘验证 ②46场待赛完整明细 ③市场双源交叉 ④欧冠方向翻转说明 ⑤重点场次分级 ⑥结论与规则建议")
L.append("> 数据源：BSD赔率/预测 + the-odds-api交叉 + 本地扫描(旧raw λ) + BSD赛果核对")
L.append("")

# ============ 一、74场验证 ============
L.append("## 一、74 场已结算实盘验证（模型大小球 vs 市场方向）")
L.append("")
L.append("> 08-14~08-19 已完赛 | 平注模型方向@市场赔率 | 明细见 ou_same_opp_settled_20260819.md")
L.append("")
def grp(rs):
    n = len(rs); hit = sum(1 for r in rs if r["hit"])
    ret = sum(r["odds"] if r["hit"] else 0.0 for r in rs)
    return n, hit, 100.0*hit/n, 100.0*(ret/n-1.0)
L.append("| 分组 | 场次 | 命中 | 命中率 | 平注ROI |")
L.append("|------|------|------|--------|---------|")
for name, rs in [("全量", settled),
                 ("模型=市场 同向", [r for r in settled if r["same"]]),
                 ("模型逆市场 反向", [r for r in settled if not r["same"]]),
                 ("模型大球", [r for r in settled if r["model"]=="大"]),
                 ("模型小球", [r for r in settled if r["model"]=="小"]),
                 ("同向大", [r for r in settled if r["same"] and r["model"]=="大"]),
                 ("同向小", [r for r in settled if r["same"] and r["model"]=="小"]),
                 ("反向大", [r for r in settled if not r["same"] and r["model"]=="大"]),
                 ("反向小", [r for r in settled if not r["same"] and r["model"]=="小"])]:
    a,b,c,dd = grp(rs)
    L.append("| %s | %d | %d | %.1f%% | %+.1f%% |" % (name, a, b, c, dd))
L.append("")
L.append("**核心结论**：跟市场同向命中56.5%但ROI -7.4%（水钱吃掉）；模型逆市场反向ROI +19.8%；**模型大球=价值方向(64.1%/+19.0%)，模型小球=亏损方向(45.7%/-15.1%)**。08-18那批16/20=80%为20场小样本+全同向运气。")
L.append("")
L.append("**按联赛**：英乙+42.8%、挪超+74%、瑞超+20.8%、巴甲+15.1%、美职+8.8%、英冠-4.9%、荷甲-46%、葡超-100%、土超-100%、比甲-100%")
L.append("")

# ============ 二、46场完整明细 ============
L.append("## 二、46 场待赛完整明细（旧 raw λ 引擎 · 按时间）")
L.append("")
L.append("| # | 时间 | 联赛 | 对阵 | λ和 | 方向 | 模型大球 | 市场大球 | 盘口(大/小) | 模型EV | 差(pp) | 星级 |")
L.append("|---|------|------|------|-----|------|---------|---------|------------|--------|--------|------|")
rows = []
for r in mev:
    o = by.get(r["id"], {}).get("bsd_odds") or {}
    mp, md = mkt_over(o)
    lam = r.get("lam") or []
    lam_sum = (lam[0]+lam[1]) if len(lam)==2 and lam[0] is not None else None
    over = r.get("model_over25")
    ev = r.get("ev_ou")
    if ev is None: star = "—"
    elif ev >= 0.08: star = "★★★"
    elif ev >= 0.05: star = "★★"
    elif ev >= 0.02: star = "★"
    else: star = "无"
    edge = (over - mp) if (over is not None and mp is not None) else None
    rows.append({
        "ko": r["kickoff"], "lg": r["league"], "home": r["home"], "away": r["away"],
        "lam": lam_sum, "ou": ("大2.5" if over and over>50 else "小2.5"),
        "over_p": over, "mkt_p": mp, "ov": (o or {}).get("over_25_goals"), "un": (o or {}).get("under_25_goals"),
        "ev": ev, "edge": edge, "star": star,
    })
rows.sort(key=lambda x: (x["ko"][:5], x["ko"][6:]))
for i, x in enumerate(rows, 1):
    mp = ("%.0f%%" % x["mkt_p"]) if x["mkt_p"] is not None else "—"
    odds = ("%.2f/%.2f" % (x["ov"], x["un"])) if x["ov"] else "—/—"
    ed = ("%+.1f" % x["edge"]) if x["edge"] is not None else "—"
    lam = ("%.2f" % x["lam"]) if x["lam"] is not None else "—"
    op = x["over_p"] if x["over_p"] is not None else 0
    L.append("| %d | %s | %s | %s vs %s | %s | %s | %.0f%% | %s | %s | %s | %s | %s |" % (
        i, x["ko"], x["lg"], x["home"], x["away"], lam, x["ou"], op, mp, odds, fmt_ev(x["ev"]), ed, x["star"]))
L.append("")

# ============ 三、20场正EV vs BSD交叉 ============
L.append("## 三、20 场正EV（≥5%）vs BSD 双源交叉")
L.append("")
L.append("| 对阵 | 模型 | EV | BSD | the-odds | 判定 |")
L.append("|------|------|-----|-----|----------|------|")
sel = [x for x in rows if x["ev"] is not None and x["ev"] >= 0.05]
sel.sort(key=lambda x: -x["ev"])
for x in sel:
    bd = by.get([k for k,v in by.items() if False][0], {}) if False else None
    # 从key取bsd_ou25与to
    kb = None; td = None
    for rid, kk in by.items():
        if kk["home"]==x["home"] and kk["away"]==x["away"] and kk["kickoff"]==x["ko"]:
            kb = (kk.get("bsd_ou25") or {}).get("dir")
            td = ((kk.get("to") or {}).get("ou25") or {}).get("dir")
            break
    tag = []
    if kb and x["ou"][0]==kb[0]: tag.append("BSD同")
    elif kb: tag.append("BSD反")
    else: tag.append("BSD无")
    if td and x["ou"][0]==td[0]: tag.append("TO同")
    elif td: tag.append("TO反")
    else: tag.append("TO无")
    L.append("| %s vs %s | %s | %s | %s | %s | %s |" % (
        x["home"], x["away"], x["ou"], fmt_ev(x["ev"]), kb or "—", td or "—", "+".join(tag)))
L.append("")
L.append("**结论**：20场正EV里 11场与BSD同向、9场反向（全为模型小vs市场大假正）；the-odds仅1场有盘。模型方向必须=BSD方向才纳入。")
L.append("")

# ============ 四、欧冠翻转 ============
L.append("## 四、欧冠 08-19 03:00 方向翻转说明")
L.append("")
L.append("| 场次 | 旧raw(当前) | BSD λ | BSD市场 | 状态 |")
L.append("|------|------------|--------|---------|------|")
L.append("| 费内巴切 vs 里昂 | 小2.5 EV-4.9% | 大2.5(λ2.12/1.14) | 大2.5 53% | ⚠️翻转 |")
L.append("| 萨格勒布迪纳摩 vs 维京 | 小2.5 EV+14.6% | 大2.5(λ1.68/1.77) | 大2.5 58% | ⚠️翻转 |")
L.append("| 列夫斯基 vs AEK | 小2.5 EV+12.7% | 大2.5(λ1.76/1.07) | 小2.5 60% | 部分反向 |")
L.append("")
L.append("**根因**：旧raw客场λ被压极低（AEK 0.30/里昂 0.75/维京 1.20 vs BSD 1.07/1.14/1.77），欧冠跨联赛应以BSD λ/市场为准。")
L.append("")

# ============ 五、重点场次 ============
L.append("## 五、重点场次分级（按74场验证规律）")
L.append("")
L.append("### P1 重点（15场：模型大 + λ正常2.6~3.4 + 市场同向大）")
L.append("")
L.append("| 时间 | 联赛 | 对阵 | λ和 | 模型大 | 市场大 | EV |")
L.append("|------|------|------|-----|--------|--------|-----|")
for x in km["p1"]:
    L.append("| %s | %s | %s vs %s | %.2f | %.0f%% | %s | %s |" % (
        x["ko"], x["lg"], x["home"], x["away"], x["lam"] or 0, x["over_p"],
        ("%.0f%%" % x["mkt_p"]) if x["mkt_p"] else "—", fmt_ev(x["ev"])))
L.append("")
L.append("### P2 观察（5场：模型大但λ异常>3.5，人工复核）")
L.append("")
for x in km["p2"]:
    L.append("- %s %s | %s vs %s：λ%.2f 模型大%.0f%% EV%s" % (
        x["ko"], x["lg"], x["home"], x["away"], x["lam"] or 0, x["over_p"], fmt_ev(x["ev"])))
L.append("")
L.append("### P3 降权（26场：模型小球=亏损方向，仅记参考）")
L.append("")
L.append("代表场次：亚特兰大EV+41%、贾盖隆尼亚+48.8%、圣特赖登+36.8%、林肯红魔、根特、沙姆洛克、赫塔菲等——模型小球74场命中45.7% ROI-15.1%，EV再高不优先。")
L.append("")

# ============ 六、规则建议 ============
L.append("## 六、测试期规则建议")
L.append("")
L.append("1. OU记方向优先级：模型大球 > 反向大 > 同向大；模型小球整体降权标注低置信")
L.append("2. 出单候选硬门槛：模型方向 = BSD方向 才纳入（20场→11场），有the-odds再加TO验证")
L.append("3. 欧冠/跨联赛资格赛 OU 以 BSD λ 为准，旧raw仅同联赛内部使用")
L.append("4. λ 异常(>3.5或<1.8) 只记方向、不按EV出单，人工复核")
L.append("5. 样本74场仍小，按300场阶段推进，重点扩'反向大'场次结算样本")
L.append("")
L.append("---")
L.append("产物：ou_same_opp_settled_20260819.json/.md、ou_key_matches_20260819.json、ou_strategy_old_raw_20260819_by_time.md")

fn = ROOT + r"\analysis_records\ou_full_report_20260819.md"
io.open(fn, "w", encoding="utf-8").write("\n".join(L))
print("saved:", fn)
print("rows in 46:", len(rows), "| P1:", len(km["p1"]), "P2:", len(km["p2"]), "P3:", len(km["p3"]), "| settled:", len(settled))
