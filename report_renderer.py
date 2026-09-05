# -*- coding: utf-8 -*-
"""报告模板渲染: 把 match_report + report_rules 输出渲染成完整分析报告。

结构(对照参考报告):
1. 顶部 7 列汇总表
2. 市场来源 + 市场快照
3. 模型结果(10项)
4. 阵容影响(占位)
5. 冲突分析
6. 最终读法(方向/让球/大小球/比分矩阵/意外/置信度)
7. 一句话总结
8. 免责声明

用法: python football_analyzer/report_renderer.py  # 自检
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from config import DIV_CN


def _dir_cn(d: str) -> str:
    return {"home": "主胜", "draw": "平局", "away": "客胜"}.get(d, d)


def _ah_description(line: float, win_prob: float) -> str:
    """让球理解文字描述。"""
    if not np.isfinite(line):
        return "无让球数据"
    side = "主让" if line < 0 else "主受让"
    abs_line = abs(line)
    if win_prob >= 0.60:
        conf = "赢盘概率较高"
    elif win_prob >= 0.50:
        conf = "赢盘略占优"
    else:
        conf = "赢盘不占优"
    return f"{side}{abs_line:.2f}({conf} {win_prob:.0%})"


def _ou_description(over_prob: float, total_xg: float) -> str:
    """大小球倾向文字描述。"""
    if over_prob >= 0.65:
        trend = "明显偏大"
    elif over_prob >= 0.55:
        trend = "略偏大"
    elif over_prob >= 0.45:
        trend = "中性"
    else:
        trend = "偏小"
    # 核心总进球区间
    if total_xg >= 3.5:
        interval = "3-4球"
    elif total_xg >= 2.8:
        interval = "2-3球"
    elif total_xg >= 2.2:
        interval = "2球左右"
    else:
        interval = "1-2球"
    return f"{trend}(大2.5={over_prob:.0%}, 核心区间{interval})"


def render_summary_table(report: dict, rules: dict) -> str:
    """顶部 7 列汇总表。"""
    elo = report["elo"]
    ha = report["home_away_1x2"]
    mp = rules.get("market_probs")
    ah = report["asian_handicap"]
    ou = report["over_2_5"]
    top3 = report["top3_scores"]
    surprise = rules["surprise"]["main_surprise"]

    elo_str = f"{elo['home_win']:.1%}/{elo['away_win']:.1%}"
    ha_str = f"主{ha['home']:.1%}/平{ha['draw']:.1%}/客{ha['away']:.1%}"
    if mp and all(np.isfinite(x) for x in mp):
        mp_str = f"主{mp[0]:.1%}/平{mp[1]:.1%}/客{mp[2]:.1%}"
    else:
        mp_str = "无市场数据"
    ah_str = _ah_description(ah["line"], ah["win"])
    ou_str = _ou_description(ou, report["expected_goals"]["total"])
    top3_str = " / ".join(f"{i}-{j}" for i, j, _ in top3)
    if surprise.get("score"):
        si, sj, sp = surprise["score"]
        surprise_str = f"{si}-{sj}({surprise['direction']})"
    else:
        surprise_str = f"{_dir_cn(surprise['direction'])}"

    header = "| 严格EloML强弱 | 俱乐部比分分层90分钟 | 市场去水概率 | 让球理解 | 大小球倾向 | Top3比分 | 可能意外 |"
    sep = "|---|---|---|---|---|---|---|"
    row = f"| {elo_str} | {ha_str} | {mp_str} | {ah_str} | {ou_str} | {top3_str} | {surprise_str} |"
    return "\n".join([header, sep, row])


def render_market_snapshot(report: dict, rules: dict, market_odds: Optional[tuple],
                            source_info: str = "composite") -> str:
    """市场来源 + 市场快照。"""
    lines = ["**市场来源**: composite(theoddsapi + bsd 共识)"]
    lines.append("")
    lines.append("**市场快照**")
    lines.append("")
    if market_odds and all(np.isfinite(x) for x in market_odds):
        lines.append(f"- 综合赔率: 主{market_odds[0]:.2f} / 平{market_odds[1]:.2f} / 客{market_odds[2]:.2f}")
    mp = rules.get("market_probs")
    if mp and all(np.isfinite(x) for x in mp):
        lines.append(f"- 市场去水: 主{mp[0]:.2%} / 平{mp[1]:.2%} / 客{mp[2]:.2%}")
    ah = report["asian_handicap"]
    if np.isfinite(ah["line"]):
        side = "主让" if ah["line"] < 0 else "主受让"
        lines.append(f"- 亚洲让球: {side}{abs(ah['line']):.2f}")
        lines.append(f"- 让球赢盘概率: {ah['win']:.1%} / 输盘 {ah['lose']:.1%}" +
                     (f" / 走水 {ah['push']:.1%}" if ah.get("push", 0) > 0 else ""))
    lines.append(f"- 大小球: 大2.5概率 {report['over_2_5']:.1%}")
    # 双源同向
    dual = rules["dual_source"]
    if dual["aligned"]:
        lines.append(f"- 双源同向: 模型与市场方向一致({_dir_cn(dual['model_direction'])})")
    else:
        lines.append(f"- 双源分歧: 模型={_dir_cn(dual['model_direction'])}, 市场={_dir_cn(dual['market_direction'])}")
    return "\n".join(lines)


def render_model_result(report: dict) -> str:
    """模型结果 10 项。"""
    from match_report import format_model_result
    return format_model_result(report)


def fetch_lineup_intel(home: str, away: str, league: str,
                        max_queries: int = 4) -> dict:
    """用百炼(qwen-plus)联网检索伤停/首发/战意情报。无凭证时返回 enabled=False。"""
    import os
    try:
        from dashscope_search import extract_injury_json, has_credentials
        if not has_credentials():
            return {"enabled": False, "reason": "no_credentials",
                    "answers": [], "results": []}
        league_cn = DIV_CN.get(league, league)
        r = extract_injury_json(home, away, league_cn, max_attempts=2)
        if r.get("ok"):
            recs = r.get("records", [])
            answers = [{"query": f"{home} vs {away} 伤停",
                        "text": "; ".join(f"{x.get('side','')} {x.get('player','')}({x.get('reason','')})"
                                       for x in recs) or "无伤病停赛"}]
            return {"enabled": True, "backend": "dashscope",
                    "answers": answers, "results": [], "warnings": [],
                    "records": recs}
        else:
            err = r.get("error", {}).get("message", "unknown")
            return {"enabled": False, "reason": f"dashscope_error: {err}",
                    "answers": [], "results": []}
    except Exception as exc:
        return {"enabled": False, "reason": f"error: {exc}",
                "answers": [], "results": []}


def render_lineup(home: str, away: str, intel: Optional[dict] = None) -> str:
    """阵容影响: 伤停/首发/战意情报。"""
    lines = ["**阵容影响**"]
    lines.append("")
    if intel and intel.get("enabled"):
        answers = intel.get("answers") or []
        if answers:
            # AI 情报摘要(取第一条, 截断)
            summary = answers[0].get("text", "").strip()
            if len(summary) > 800:
                summary = summary[:800] + "..."
            lines.append(f"- **AI 情报摘要**({intel.get('backend', 'ark')} 联网):")
            lines.append(f"  {summary}")
        results = intel.get("results") or []
        if results:
            lines.append("")
            lines.append("- **引用来源**:")
            for it in results[:5]:
                title = it.get("title", "")[:60]
                site = it.get("site", "")
                url = it.get("url", "")
                lines.append(f"  - {title}" + (f" ({site})" if site else "") +
                             (f" {url}" if url else ""))
        if intel.get("warnings"):
            lines.append(f"- 提示: {'; '.join(str(w)[:80] for w in intel['warnings'][:3])}")
    else:
        reason = intel.get("reason", "unknown") if intel else "not_fetched"
        if reason == "no_credentials":
            lines.append(f"{home}:")
            lines.append("- 暂无伤停信息(未配置 ARK_API_KEY + ARK_ENDPOINT_ID)")
            lines.append("")
            lines.append(f"{away}:")
            lines.append("- 暂无伤停信息(未配置 ARK_API_KEY + ARK_ENDPOINT_ID)")
        else:
            lines.append(f"{home}:")
            lines.append(f"- 暂无伤停信息(情报获取失败: {reason})")
            lines.append("")
            lines.append(f"{away}:")
            lines.append(f"- 暂无伤停信息(情报获取失败: {reason})")
    return "\n".join(lines)


def render_conflict(rules: dict) -> str:
    """冲突分析。"""
    c = rules["conflict"]
    lines = ["**冲突分析**"]
    lines.append("")
    level_cn = {"none": "无冲突", "magnitude": "幅度冲突", "direction": "方向冲突"}.get(c["level"], c["level"])
    lines.append(f"- 冲突等级: **{level_cn}**")
    lines.append(f"- {c['description']}")
    # 平局预警 (2026-08-29)
    dw = rules.get("draw_warning") or {}
    if dw.get("level"):
        dw_cn = {"strong": "⚠强预警", "normal": "⚠预警"}.get(dw["level"], dw["level"])
        src = "市场去水" if dw.get("market_based") else "模型"
        lines.append(f"- **平局{dw_cn}({src}平局 {dw['draw_prob']:.1%})**")
        lines.append("  - 让球建议只用+号(受让方)" + ("; 2.50 大小球盘降星/谨慎" if dw["level"] == "strong" else ""))
    # 各源方向
    lines.append(f"- 各源方向: Elo={_dir_cn(c['elo_direction'])}, "
                 f"泊松={_dir_cn(c['poisson_direction'])}, 市场={_dir_cn(c['market_direction'])}")
    # 比分触发
    st = rules["score_trigger"]
    if st["triggered"]:
        lines.append(f"- 比分触发: 满足高分路径条件(主胜{st['win_prob']:.0%} + 让球{st['ah_line_abs']:.2f} + 大球{st['over_prob']:.0%})")
    else:
        cond_str = ", ".join(f"{k}={'✓' if v else '✗'}" for k, v in st["conditions"].items())
        lines.append(f"- 比分触发: 未满足({cond_str})")
    return "\n".join(lines)


def _filter_scores(dist: list, direction: str, min_gd: int = None,
                    opponent_goals: bool = None) -> list:
    """从比分分布按方向/净胜球/对方进球筛选。"""
    out = []
    for i, j, p in dist:
        if direction == "home" and not (i > j):
            continue
        if direction == "away" and not (i < j):
            continue
        if direction == "draw" and not (i == j):
            continue
        if min_gd is not None and abs(i - j) < min_gd:
            continue
        if opponent_goals is True:
            if direction == "home" and j == 0:
                continue
            if direction == "away" and i == 0:
                continue
        if opponent_goals is False:
            if direction == "home" and j > 0:
                continue
            if direction == "away" and i > 0:
                continue
        out.append((i, j, p))
    return out


def render_final_read(report: dict, rules: dict) -> str:
    """最终读法。"""
    from score_matrix import score_dist
    sd = rules["strong_direction"]
    conf = rules["confidence"]
    surprise = rules["surprise"]
    ah = report["asian_handicap"]
    mt = report["matrix_top"]
    main_dir = sd["direction"]

    # 主方向比分分布
    lh, la = report["expected_goals"]["home"], report["expected_goals"]["away"]
    dist = score_dist(lh, la)
    dir_scores = _filter_scores(dist, main_dir)
    core3 = dir_scores[:3] if len(dir_scores) >= 3 else dir_scores
    first = dir_scores[0] if dir_scores else mt
    # 强势比分(净胜球>=3, 没有则降级>=2)
    strong = _filter_scores(dist, main_dir, min_gd=3)
    if not strong:
        strong = _filter_scores(dist, main_dir, min_gd=2)
    # 对方进球分支
    opp_score = _filter_scores(dist, main_dir, opponent_goals=True)

    lines = ["**最终读法**"]
    lines.append("")
    # 方向
    model_dir = _dir_cn(rules["dual_source"]["model_direction"])
    market_dir = _dir_cn(rules["dual_source"]["market_direction"])
    main_dir_cn = _dir_cn(main_dir)
    lines.append(f"- 严格模型方向: {main_dir_cn}")
    lines.append(f"- 市场方向: {market_dir}")
    if rules["dual_source"]["aligned"]:
        lines.append(f"- 综合更接近胜利的一方: {main_dir_cn}")
    else:
        lines.append(f"- 综合更接近胜利的一方: {main_dir_cn}(模型与市场有分歧, 置信度降低)")
    # 推荐预测方向
    second_dir = _dir_cn(surprise["main_surprise"]["direction"])
    lines.append(f"- 推荐预测方向: {main_dir_cn}, {second_dir}为第二路径")
    # 让球
    lines.append(f"- 让球理解: {_ah_description(ah['line'], ah['win'])}")
    # 大小球
    lines.append(f"- 大小球: {_ou_description(report['over_2_5'], report['expected_goals']['total'])}")
    # 比分矩阵
    lines.append(f"- 矩阵最高比分: {mt[0]}-{mt[1]}")
    if core3:
        lines.append(f"- 三个核心比分: " + " / ".join(f"{i}-{j}" for i, j, _ in core3))
    if first:
        lines.append(f"- 方向首选比分: {first[0]}-{first[1]}")
    # 强势比分(主方向净胜>=2)
    if strong:
        si, sj, _ = strong[0]
        lines.append(f"- 强势{main_dir_cn}比分: {si}-{sj}")
    # 对方进球分支
    if opp_score:
        oi, oj, _ = opp_score[0]
        # 第二个对方进球比分(如果有)
        if len(opp_score) >= 2:
            oi2, oj2, _ = opp_score[1]
            lines.append(f"- 对方进球分支: {oi}-{oj}或{oi2}-{oj2}")
        else:
            lines.append(f"- 对方进球分支: {oi}-{oj}")
    # 高分路径(如果触发)
    if rules["score_trigger"]["triggered"]:
        if main_dir == "home":
            lines.append(f"- 高分路径: 4-0 / 4-1(满足主胜>70%+让球深+大球>65%)")
        else:
            lines.append(f"- 高分路径: 0-4 / 1-4(满足客胜>70%+让球深+大球>65%)")
    # 意外
    ms = surprise["main_surprise"]
    es = surprise["extreme_surprise"]
    ms_score = f"{ms['score'][0]}-{ms['score'][1]}" if ms.get("score") else _dir_cn(ms["direction"])
    es_score = f"{es['score'][0]}-{es['score'][1]}" if es.get("score") else _dir_cn(es["direction"])
    lines.append(f"- 主要意外: {ms_score}({_dir_cn(ms['direction'])} {ms['prob']:.1%})")
    lines.append(f"- 极端意外: {es_score}({_dir_cn(es['direction'])} {es['prob']:.1%})")
    # 置信度
    lines.append(f"- 置信度: {main_dir_cn}{conf['direction']}; 净胜球{conf['goal_difference']}; 具体比分{conf['exact_score']}")
    return "\n".join(lines)


def render_one_sentence(report: dict, rules: dict) -> str:
    """一句话总结。"""
    from score_matrix import score_dist
    sd = rules["strong_direction"]
    main_dir = _dir_cn(sd["direction"])
    main_dir_key = sd["direction"]
    # 主方向 Top3
    lh, la = report["expected_goals"]["home"], report["expected_goals"]["away"]
    dist = score_dist(lh, la)
    dir_scores = _filter_scores(dist, main_dir_key)
    core = dir_scores[:3] if len(dir_scores) >= 3 else (report["top3_scores"][:3])
    conflict_level = rules["conflict"]["level"]
    if conflict_level == "direction":
        prefix = "模型与市场存在方向分歧, "
    elif conflict_level == "magnitude":
        prefix = "各层方向一致但幅度有分歧, "
    else:
        prefix = "所有核心层方向一致, "
    score_str = "、".join(f"{i}-{j}" for i, j, _ in core)
    if report["over_2_5"] > 0.65:
        ou_note = f", 同时大球概率超过65%, 需保留高分路径"
    else:
        ou_note = ""
    return (f"{prefix}{main_dir}是更接近胜利的一方, 主看{score_str}{ou_note}。")


def render_full_report(report: dict, rules: dict, market_odds: Optional[tuple] = None,
                        source_info: str = "composite", with_intel: bool = True,
                        intel: Optional[dict] = None) -> str:
    """渲染完整报告。with_intel=True 时自动联网检索伤停/首发情报(需 ARK 凭证)。"""
    home, away = report["match"].split(" vs ")
    # 阵容情报
    if intel is None and with_intel:
        intel = fetch_lineup_intel(home, away, report.get("league", ""))
    parts = []
    # 标题
    parts.append(f"# {report['match']} 比赛分析报告")
    parts.append(f"*{report['league']} | {report['date']}*")
    parts.append("")
    # 1. 顶部汇总表
    parts.append(render_summary_table(report, rules))
    parts.append("")
    # 2. 市场快照
    parts.append(render_market_snapshot(report, rules, market_odds, source_info))
    parts.append("")
    # 3. 模型结果
    parts.append("**模型结果**")
    parts.append("")
    parts.append(render_model_result(report))
    parts.append("")
    # 4. 阵容影响
    parts.append(render_lineup(home, away, intel))
    parts.append("")
    # 5. 冲突分析
    parts.append(render_conflict(rules))
    parts.append("")
    # 6. 最终读法
    parts.append(render_final_read(report, rules))
    parts.append("")
    # 7. 一句话
    parts.append("**一句话:** " + render_one_sentence(report, rules))
    parts.append("")
    # 8. 免责
    parts.append("---")
    parts.append("*本内容仅用于模型学习与足球比赛分析, 不涉及、不建议、也不参与任何体彩、竞猜、博彩或相关行为。*")
    return "\n".join(parts)


def _self_test():
    # 用巴萨场景渲染
    report = {
        "match": "Barcelona vs Athletic Bilbao",
        "league": "SP1",
        "date": "2026-01-15",
        "elo": {"home_win": 0.7023, "away_win": 0.2977, "home_rating": 1700, "away_rating": 1580},
        "home_away_1x2": {"home": 0.8163, "draw": 0.1180, "away": 0.0657},
        "ensemble": {"home": 0.8030, "draw": 0.1258, "away": 0.0712, "weights": {}},
        "expected_goals": {"home": 2.946, "away": 0.755, "total": 3.701},
        "over_2_5": 0.7107,
        "btts": 0.505,
        "recent": {"home_recent_home": {"points": 18, "gf": 16, "ga": 6, "n": 8},
                   "away_recent_away": {"points": 7, "gf": 11, "ga": 16, "n": 8}},
        "top3_scores": [(2, 0, 0.107), (3, 0, 0.105), (2, 1, 0.081)],
        "matrix_top": (2, 0, 0.107),
        "asian_handicap": {"line": -1.75, "win": 0.62, "lose": 0.30, "push": 0.08},
    }
    from report_rules import analyze_rules
    rules = analyze_rules(report, market_odds=(1.25, 6.58, 11.08))
    out = render_full_report(report, rules, market_odds=(1.25, 6.58, 11.08), with_intel=False)
    print(out)
    # 基本断言
    assert "Barcelona vs Athletic Bilbao" in out
    assert "严格EloML强弱" in out
    assert "市场快照" in out
    assert "模型结果" in out
    assert "冲突分析" in out
    assert "最终读法" in out
    assert "一句话" in out
    assert "免责" in out or "体彩" in out
    print("\n== report_renderer 自检通过 ==")


if __name__ == "__main__":
    _self_test()
