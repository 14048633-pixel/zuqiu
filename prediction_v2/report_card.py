# -*- coding: utf-8 -*-
"""赛前参考报告生成器 (格式对齐用户示例)
用法:
  python prediction_v2/report_card.py --out-dir analysis_records/report_cards_20260817
  python prediction_v2/report_card.py --ids 215481,215502   # 只生成指定场
"""
import argparse, io, json, os, sys, collections
from datetime import datetime, timezone, timedelta
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import scan_upcoming as SC
import coach_quant as cq
import pipeline_scan as PS
from prob_calibration import dc_score_grid

BJT = timezone(timedelta(hours=8))

def quarter_ball(grid, line):
    """主队亚洲盘 line(负=主让): 返回 (主赢盘, 走水, 客赢盘) 概率.
    整盘: margin==line 走水; 半球盘/平手盘: 无走水; 1/4盘: 拆两半, 走水仅整数半出现."""
    def P(cond):
        return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    q = abs(round((abs(line) % 1.0) * 4) % 4) / 4.0  # 0, 0.25, 0.5, 0.75
    if q in (0.0, 0.5):
        w = P(lambda i, j: (i - j) + line > 0)
        push = P(lambda i, j: abs((i - j) + line) < 1e-9)
        return round(w, 4), round(push, 4), round(max(0.0, 1 - w - push), 4)
    lo = line - 0.25 if q == 0.25 else line - 0.25  # -0.25 -> -0.5; -0.75 -> -1.0
    hi = line + 0.25
    w_lo = P(lambda i, j: (i - j) + lo > 0) + 0.5 * P(lambda i, j: abs((i - j) + lo) < 1e-9)
    w_hi = P(lambda i, j: (i - j) + hi > 0) + 0.5 * P(lambda i, j: abs((i - j) + hi) < 1e-9)
    w = 0.5 * (w_lo + w_hi)
    push = 0.5 * (P(lambda i, j: abs((i - j) + lo) < 1e-9) + P(lambda i, j: abs((i - j) + hi) < 1e-9))
    return round(w, 4), round(push, 4), round(max(0.0, 1 - w - push), 4)

def ref_1x2(x, r, m):
    """1X2 参考度: 数据完整性 + 分歧扣分. 返回 0-100."""
    c = x["card"]
    s = 78.0
    for side in ("home", "away"):
        if c["attack"][side] in ("市场兜底", "联赛基准", "缺失"):
            s -= 8
    if not str(c["odds"]["1x2"]).startswith("有"):
        s -= 15
    elif "过期" in str(c["odds"]["1x2"]):
        s -= 22
    if c["coach"]["home"] == "未覆盖":
        s -= 4
    if c["coach"]["away"] == "未覆盖":
        s -= 4
    if c["formation"]["home"].startswith("缺失") or c["formation"]["away"].startswith("缺失"):
        s -= 3
    if not c["independent"]:
        s -= 10
    wdl = r.get("wdl") or {}
    fair = r.get("market_fair") or {}
    if wdl.get("home") is not None and fair.get("home") is not None:
        gap = max(abs(wdl.get(k, 0) - (fair.get(k) or 0)) for k in ("home", "draw", "away"))
        if gap > 20:
            s -= 12
        elif gap > 12:
            s -= 6
    return int(max(30, min(95, s)))

def make_report(x, r, m, grid, lam_h, lam_a, rho):
    h2h = m.get("h2h") or {}
    tt = m.get("totals") or {}
    sp = m.get("spread") or {}
    line = tt.get("line") or 2.5
    over = tt.get("over_price"); under = tt.get("under_price")
    def P(cond):
        return sum(grid[i][j] for i in range(9) for j in range(9) if cond(i, j))
    p_hw = P(lambda i, j: i > j); p_dr = P(lambda i, j: i == j); p_aw = P(lambda i, j: i < j)
    # 大小球(含走水)
    if abs(line - round(line)) < 0.01:
        push = P(lambda i, j: abs(i + j - line) < 0.01)
        p_over = P(lambda i, j: i + j > line)
        p_under = P(lambda i, j: i + j < line)
    else:
        push = 0.0
        p_over = P(lambda i, j: i + j > line)
        p_under = 1 - p_over
    # Top 比分
    top = sorted(((grid[i][j], i, j) for i in range(9) for j in range(9)), reverse=True)[:2]
    # 亚洲盘
    hdp = sp.get("hdp_home", 0.0) or 0.0
    if sp.get("home_price") and sp.get("away_price"):
        aw, ap, al = quarter_ball(grid, hdp)
        asian_ok = True
    else:
        aw = ap = al = None; asian_ok = False
    # 让球胜平负 (3向, 线=让球线)
    hdp3 = round(hdp * 2) / 2 if asian_ok else 0.0
    w3 = P(lambda i, j: (i - j) + hdp3 > 0)
    d3 = P(lambda i, j: abs((i - j) + hdp3) < 1e-9)
    l3 = P(lambda i, j: (i - j) + hdp3 < 0)
    # 半全场 (HT λ≈FT*0.45 独立近似, 低置信)
    hg = dc_score_grid(lam_h * 0.45, lam_a * 0.45, rho=0.0, max_goals=4)
    def PH(cond):
        return sum(hg[i][j] for i in range(5) for j in range(5) if cond(i, j))
    htw = PH(lambda i, j: i > j); htd = PH(lambda i, j: i == j); hta = PH(lambda i, j: i < j)
    combos = {"主/主": htw * p_hw, "主/平": htw * p_dr, "主/客": htw * p_aw,
              "平/主": htd * p_hw, "平/平": htd * p_dr, "平/客": htd * p_aw,
              "客/主": hta * p_hw, "客/平": hta * p_dr, "客/客": hta * p_aw}
    top_htft = max(combos.items(), key=lambda kv: kv[1])
    # 市场隐含(去水)
    fair = r.get("market_fair") or {}
    wdl = r.get("wdl") or []
    odds_h, odds_d, odds_a = h2h.get("home"), h2h.get("draw"), h2h.get("away")
    fair_h, fair_d, fair_a = fair.get("home"), fair.get("draw"), fair.get("away")
    # 倾向
    def pick3(a, b, c):
        idx = max(range(3), key=lambda k: [a, b, c][k] or 0)
        return ["主队", "平局", "客队"][idx], [a, b, c][idx]
    lean_w, p_w = pick3(p_hw, p_dr, p_aw)
    lean_as, p_as = ("主队", aw) if (aw or 0) >= (al or 0) else ("客队", al or 0)
    lean_ou, p_ou = ("大", p_over) if p_over >= p_under else ("小", p_under)
    # 参考度
    ref = ref_1x2(x, r, m)
    ref_sp = (ref - 8) if (asian_ok and sp.get("home_price")) else 40
    ref_tt = (ref - 6) if (over and under) else 35
    ref_htft = 48
    ref_corner = 35
    ref3 = (ref - 10) if asian_ok else ref
    ref_overall = int(round(0.42 * ref + 0.16 * max(ref3, 30) + 0.18 * max(ref_sp, 30) + 0.14 * max(ref_tt, 30)
                            + 0.05 * ref_corner + 0.05 * ref_htft))
    risk = "低"
    tags = r.get("risk_tags") or []
    if r.get("direction", {}).get("vetoed") or "非独立数据" in tags or (r.get("lambda") or {}).get("home", 0) > 4 or (r.get("lambda") or {}).get("away", 0) > 4:
        risk = "高"
    elif len(tags) >= 2:
        risk = "中"
    elif tags:
        risk = "中"
    # 主看
    di = r.get("direction") or {}
    main = di.get("name") or "无方向"
    if di.get("vetoed"):
        main += " ⛔(%s)" % (di.get("veto_reason") or "盘口过期,需临场重拉")
    elif r.get("ev_tier") == "否决":
        main += " ⛔(禁出/否决,仅参考方向)"
    # 走势段落
    gap_w = (p_hw - (fair_h / 100 if fair_h is not None else 0)) * 100 if fair_h is not None else None
    nar = []
    nar.append("根据市场主盘与模型测算, 主队胜率%.1f%%(市场去水%.1f%%)" % (p_hw * 100, fair_h if fair_h is not None else 0))
    if asian_ok:
        nar.append("亚洲让球主队%s盘, 主队赢盘概率%.1f%%" % ("%.2f" % hdp if hdp else "0", aw * 100))
    nar.append("预期总进球%.1f球(主%.1f/客%.1f)" % (lam_h + lam_a, lam_h, lam_a))
    if p_over >= p_under:
        nar.append("大小球偏向大球(大%.1f%%/小%.1f%%%s)" % (p_over * 100, p_under * 100, ("/走水%.1f%%" % (push * 100)) if push else ""))
    else:
        nar.append("大小球偏向小球(小%.1f%%/大%.1f%%%s)" % (p_under * 100, p_over * 100, ("/走水%.1f%%" % (push * 100)) if push else ""))
    if gap_w is not None and abs(gap_w) > 8:
        nar.append("模型与市场主胜分歧%+.1fpp" % gap_w)
    # 临场关注
    warns = []
    c = x["card"]
    if "过期" in str(c["odds"]["1x2"]):
        warns.append("盘口快照距开赛超过12小时, 临场变盘无法捕捉, 需赛前30分钟重拉")
    elif str(c["odds"]["1x2"]).startswith("有"):
        warns.append("仅有当前快照, 缺乏开盘初盘轨迹, 无法精准评估临场变盘与欧亚联动走势")
    warns.append("角球盘口基于联赛历史先验推演(basis=competition_prior), 缺乏球队针对性角球统计, 置信度低(仅%d%%)" % ref_corner)
    if p_dr > 0.28:
        warns.append("平局概率%.1f%%, 若以平局收场%s" % (p_dr * 100,
            ("亚洲让球主队%s将输一半本金" % ("%.2f" % hdp if asian_ok else "")) if asian_ok else "相关盘口将受冲击"))
    if not asian_ok:
        warns.append("无有效让球盘数据, 亚洲盘参考度下调")
    if any("概率封顶校准" in n for n in r.get("notes") or []):
        warns.append("已应用概率封顶校准(高置信档>65%%压至%s%%), 主看EV为封顶后口径" % (SC.PROB_CAP * 100))
    for t in tags:
        if "禁出" in t:
            warns.append("%s, 该场禁出不出单, 方向仅供参考" % t)
        elif "历史负ROI(观察期" in t:
            warns.append("%s, 测试期仅标注不禁出, 300场后定名单" % t)
        elif "标准档降星" in t:
            warns.append("让球客标准档已降星(历史负ROI), 仓位下调")
    if any("概率禁带" in n for n in r.get("notes") or []):
        warns.append("概率禁带已生效: 让球主/小球原始概率∈[65%%,70%%)的高估腿被剔除, 不纳入候选")
    if "伤停" in json.dumps(x.get("card", {}).get("injury", {}), ensure_ascii=False) and "位置未知" in json.dumps(x.get("card", {}).get("injury", {}), ensure_ascii=False):
        warns.append("伤停球员位置数据不齐, 影响λ修正精度")
    # 输出
    lines = []
    lines.append("⚽️ 赛前参考 · %s %s" % (x["league"], x["ct"]))
    lines.append("`%s vs %s`" % (x["home"], x["away"]))
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📌 本场观点")
    lines.append("• 主看：%s" % main)
    if asian_ok:
        lines.append("• 亚洲让球：主队 %+.2f（主队赢盘 %.1f%%）" % (hdp, aw * 100))
    lines.append("• 综合参考度：%d%%" % ref_overall)
    lines.append("• 风险：%s" % risk)
    lines.append("• 让球按主队方向显示：“+”为受让，“-”为让球。")
    lines.append("")
    lines.append("📊 盘口判断")
    lines.append("1. 胜平负：主胜 %.1f%%；平局 %.1f%%；客胜 %.1f%%；倾向 %s" % (p_hw * 100, p_dr * 100, p_aw * 100, lean_w))
    lines.append(" ├ 简评：市场主盘开出主胜%s，数据测算主胜概率达%.1f%%%s。" % (
        ("%.2f" % odds_h) if odds_h else "暂无", p_hw * 100,
        ("，模型与市场分歧%+.1fpp" % gap_w) if gap_w is not None and abs(gap_w) > 3 else ""))
    lines.append(" └ 参考度：%d%%" % ref)
    lines.append("2. 让球胜平负：主队让球 %+.1f；让胜 %.1f%%；让平 %.1f%%；让负 %.1f%%；倾向 %s" % (hdp3, w3 * 100, d3 * 100, l3 * 100, "主队" if w3 >= l3 else "客队"))
    lines.append(" ├ 简评：%s。" % ("该盘口接近均势, 置信度相对保守" if max(w3, l3) < 0.45 else ("让球后主队胜率%.1f%%, 具备一定优势" % (max(w3, l3) * 100))))
    lines.append(" └ 参考度：%d%%" % ref3)
    lines.append("3. 让球胜负（亚洲盘）：主队盘口 %+.2f；主队赢盘 %.1f%%；客队赢盘 %.1f%%；走水 %.1f%%；倾向 %s" % (
        hdp, (aw or 0) * 100, (al or 0) * 100, (ap or 0) * 100, lean_as if asian_ok else "-"))
    lines.append(" ├ 简评：%s" % ("主队让球盘下主队赢盘概率达%.1f%%, 具备一定的风险抵御能力。" % ((aw or 0) * 100) if asian_ok else "无有效让球盘数据"))
    lines.append(" └ 参考度：%d%%" % ref_sp)
    lines.append("4. 大小球：主盘 %+.1f；大球 %.1f%%；小球 %.1f%%；走水 %.1f%%；倾向 %s" % (
        line, p_over * 100, p_under * 100, push * 100, lean_ou))
    lines.append(" ├ 简评：预期总进球为%.1f球, 数据测算基线设定%.1f球界限, %s概率%.1f%%。" % (
        lam_h + lam_a, line, "大球" if p_over >= p_under else "小球", max(p_over, p_under) * 100))
    lines.append(" └ 参考度：%d%%" % ref_tt)
    lines.append("5. 比分 Top2：%d-%d（%.1f%%）；%d-%d（%.1f%%）" % (
        top[0][1], top[0][2], top[0][0] * 100, top[1][1], top[1][2], top[1][0] * 100))
    lines.append("6. 角球：主盘 未提取；大角 -%；小角 -%；走水 -%；参考度 35%")
    lines.append(" ├ 简评：角球分析采用联赛历史数据先验推演(basis=competition_prior), 并非直接市场即时盘口, 置信度低。")
    lines.append(" └ 参考度：%d%%" % ref_corner)
    lines.append("7. 半全场：倾向 %s；概率 %.1f%%" % (top_htft[0], top_htft[1] * 100))
    lines.append(" ├ 简评：基于全场泊松与半场λ近似估算, 为%s的最可能组合路径。" % top_htft[0])
    lines.append(" └ 参考度：%d%%" % ref_htft)
    lines.append("")
    lines.append("📝 比赛走势")
    lines.append("• %s。" % "，".join(nar))
    lines.append("")
    lines.append("⚠️ 临场关注")
    for w in warns:
        lines.append("• %s" % w)
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bsd", default="analysis_records/bsd_v2_2026-08-17.json")
    ap.add_argument("--v1", default="analysis_records/bzzoiro_events_2026-08-17.json")
    ap.add_argument("--squads", default="analysis_records/bsd_squads_2026-08-17.json")
    ap.add_argument("--odds", default="analysis_records/key_matches_odds_20260817.json")
    ap.add_argument("--bsd-stats", default="data/raw/football_data/bsd_league_stats.json")
    ap.add_argument("--out-dir", default="analysis_records/report_cards_20260817")
    ap.add_argument("--ids", default="")
    args = ap.parse_args()
    v2 = PS.load_json(os.path.join(ROOT, args.bsd)) or {}
    if not v2.get("data"):
        print("BSD v2 缺失"); return
    overlay = (PS.load_json(os.path.join(ROOT, args.odds)) or {}).get("overlay") or {}
    team_stats, lavg, index = SC.load_team_stats()
    bsd_stats = PS.load_json(os.path.join(ROOT, args.bsd_stats))
    PS.merge_bsd_stats(team_stats, index, bsd_stats)
    coach_cache = cq.load_cache()
    PS._load_league_map()
    coach_map = PS.build_coach_map(PS.load_json(os.path.join(ROOT, args.v1)))
    squads_pos = PS.squad_pos_map(PS.load_json(os.path.join(ROOT, args.squads)))
    now = datetime.now(timezone.utc)
    ids = [s for s in args.ids.split(",") if s] if args.ids else None
    os.makedirs(os.path.join(ROOT, args.out_dir), exist_ok=True)
    idx = []
    for eid, d in v2["data"].items():
        if ids and eid not in ids:
            continue
        pred = d.get("prediction") or {}
        ev = pred.get("event") or {}
        home = ev.get("home_team") or "?"
        away = ev.get("away_team") or "?"
        league_raw = ev.get("league_name") or "?"
        league = PS.LEAGUE_MAP.get(league_raw, league_raw)
        if league == league_raw and league_raw not in ("?", ""):
            league = "未知联赛:" + league_raw
        try:
            ct = datetime.fromisoformat(str(ev.get("event_date") or "").replace("Z", "+00:00"))
        except Exception:
            ct = now
        od = (d.get("odds") or {}).get("odds") or {}
        ov = overlay.get(eid)
        if ov and (ov.get("h2h") or {}).get("home"):
            od = {"home_win": ov["h2h"]["home"], "draw": ov["h2h"]["draw"], "away_win": ov["h2h"]["away"],
                  "over_25_goals": (ov.get("totals") or {}).get("over"),
                  "under_25_goals": (ov.get("totals") or {}).get("under")}
        snap = (ov.get("snap_iso") or now.isoformat()) if ov else now.isoformat()
        info = PS.build_info(eid, d, coach_map.get(eid) or {}, squads_pos)
        cm = cq.match_mods(coach_cache, info, PS.META_DIV.get(league, league)) if (info and coach_cache) else {}
        m = PS.build_match(league, home, away, ct, od, snap)
        if ov and (ov.get("spread") or {}).get("home_price"):
            spd = ov["spread"]
            m["spread"] = {"hdp_home": spd["hdp_home"], "home_price": spd["home_price"], "away_price": spd["away_price"]}
        m["coach_mods"] = cm
        r = SC.analyze_match(m, team_stats, lavg, index)
        r["info"] = info
        r["bsd"] = SC._bsd_cross_check(r, info)
        r["formation"] = SC._formation_check(r, info)
        r["injury_pos"] = SC._injury_pos_check(r, info)
        x = {"id": eid, "league": league, "home": home, "away": away,
             "ct": ct.astimezone(BJT).strftime("%m-%d %H:%M"),
             "card": PS.make_card(m, r, info, cm, r.get("snap_age_h"), None)}
        lam_h, lam_a = r["lambda"]["home"], r["lambda"]["away"]
        cal = SC._cal_for_league(league) or {}
        rho = cal.get("rho", 0.0)
        grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
        txt = make_report(x, r, m, grid, lam_h, lam_a, rho)
        fn = os.path.join(ROOT, args.out_dir, "report_%s_%s_vs_%s.md" % (eid, home.replace("/", "-"), away.replace("/", "-")))
        io.open(fn, "w", encoding="utf-8").write(txt)
        idx.append({"id": eid, "league": league, "home": home, "away": away, "ct": x["ct"], "file": fn})
        print("✔", eid, league, home, "vs", away)
    io.open(os.path.join(ROOT, args.out_dir, "_index.json"), "w", encoding="utf-8").write(
        json.dumps({"ts": now.isoformat(), "matches": idx}, ensure_ascii=False, indent=1))
    print("生成", len(idx), "份 ->", os.path.join(ROOT, args.out_dir))

if __name__ == "__main__":
    main()
