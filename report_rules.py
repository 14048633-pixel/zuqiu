# -*- coding: utf-8 -*-
"""报告规则引擎: 强方向/双源同向/冲突分级/比分触发/置信度/意外路径。

对应报告"冲突分析"和"最终读法"章节的规则判定。
输入 match_report 的输出 + 市场赔率, 输出规则判定结果。

用法: python football_analyzer/report_rules.py  # 自检
"""
from __future__ import annotations

from typing import Optional

import numpy as np

# 规则阈值
STRONG_DIR_THRESHOLD = 0.70   # 强方向区间(综合校准概率)
MID_DIR_THRESHOLD = 0.55      # 中方向
BIG_SCORE_TRIGGER = {
    "win_prob": 0.70,          # 主胜/客胜概率
    "ah_line": 1.75,           # 让球深度(绝对值)
    "over_prob": 0.65,         # 大球概率
}
CONFLICT_PROB_GAP = 0.15      # 幅度冲突的概率差距阈值


def _direction(probs: tuple) -> str:
    """从 (ph, pd, pa) 判定方向: home/draw/away。全 NaN 返回 unknown。"""
    if not all(np.isfinite(x) for x in probs):
        return "unknown"
    idx = np.argmax(probs)
    return ["home", "draw", "away"][idx]


def _elo_direction(elo_home_win: float) -> str:
    """Elo 二元强弱方向: home_win > 0.5 → home, 否则 away。"""
    if not np.isfinite(elo_home_win):
        return "unknown"
    return "home" if elo_home_win > 0.5 else "away"


def strong_direction(ensemble: dict) -> dict:
    """强方向区间判定: 综合校准主胜或客胜 >= 70%。"""
    ph, pd_, pa = ensemble.get("home", np.nan), ensemble.get("draw", np.nan), ensemble.get("away", np.nan)
    if not all(np.isfinite(x) for x in (ph, pa)):
        return {"direction": "unknown", "level": "none", "prob": np.nan}
    if ph >= STRONG_DIR_THRESHOLD:
        return {"direction": "home", "level": "strong", "prob": ph}
    if pa >= STRONG_DIR_THRESHOLD:
        return {"direction": "away", "level": "strong", "prob": pa}
    if ph >= MID_DIR_THRESHOLD:
        return {"direction": "home", "level": "mid", "prob": ph}
    if pa >= MID_DIR_THRESHOLD:
        return {"direction": "away", "level": "mid", "prob": pa}
    return {"direction": _direction((ph, pd_, pa)), "level": "weak", "prob": max(ph, pa)}


def dual_source_alignment(report: dict, market_probs: Optional[tuple] = None) -> dict:
    """双源同向判定: 模型方向(综合校准) vs 市场方向是否一致。"""
    model_dir = _direction((report["ensemble"]["home"], report["ensemble"]["draw"], report["ensemble"]["away"]))
    if market_probs and all(np.isfinite(x) for x in market_probs):
        market_dir = _direction(market_probs)
    else:
        market_dir = "unknown"
    aligned = model_dir == market_dir and model_dir != "unknown"
    return {"model_direction": model_dir, "market_direction": market_dir, "aligned": aligned}


def conflict_analysis(report: dict, market_probs: Optional[tuple] = None) -> dict:
    """冲突分级: Elo vs 泊松 vs 市场的方向一致性。

    levels: none(无冲突) / magnitude(幅度冲突, 方向一致但概率差大) / direction(方向冲突)。
    """
    elo_dir = _elo_direction(report["elo"]["home_win"])
    poisson_dir = _direction((report["home_away_1x2"]["home"],
                               report["home_away_1x2"]["draw"],
                               report["home_away_1x2"]["away"]))
    if market_probs and all(np.isfinite(x) for x in market_probs):
        market_dir = _direction(market_probs)
    else:
        market_dir = "unknown"

    dirs = [d for d in (elo_dir, poisson_dir, market_dir) if d != "unknown"]
    unique_dirs = set(dirs)

    # 方向冲突: 存在两个不同的非平局方向
    non_draw = [d for d in unique_dirs if d in ("home", "away")]
    if len(non_draw) >= 2:
        level = "direction"
        desc = f"方向冲突: Elo={elo_dir}, 泊松={poisson_dir}, 市场={market_dir}"
    elif len(unique_dirs) == 1:
        # 方向一致, 检查概率差距是否过大(幅度冲突)
        if market_probs and all(np.isfinite(x) for x in market_probs):
            model_p = max(report["home_away_1x2"]["home"], report["home_away_1x2"]["away"])
            market_p = max(market_probs[0], market_probs[2])
            if abs(model_p - market_p) > CONFLICT_PROB_GAP:
                level = "magnitude"
                desc = f"幅度冲突: 方向一致({unique_dirs.pop()}), 但模型概率{model_p:.1%} vs 市场{market_p:.1%}, 差{abs(model_p-market_p):.1%}"
            else:
                level = "none"
                desc = "无冲突: Elo/泊松/市场方向一致, 概率差距在合理范围"
        else:
            level = "none"
            desc = "无冲突: Elo/泊松方向一致(无市场数据对照)"
    else:
        level = "magnitude"
        desc = f"部分冲突: Elo={elo_dir}, 泊松={poisson_dir}, 市场={market_dir}"

    return {"level": level, "description": desc,
            "elo_direction": elo_dir, "poisson_direction": poisson_dir,
            "market_direction": market_dir}


def score_trigger(report: dict) -> dict:
    """比分触发条件: 强方向(≥70%) + 让球深(≥1.75) + 大球高(>65%) → 高分路径。"""
    sd = strong_direction(report["ensemble"])
    ah_abs = abs(report["asian_handicap"]["line"])
    over = report["over_2_5"]
    triggered = (sd["level"] == "strong" and
                 ah_abs >= BIG_SCORE_TRIGGER["ah_line"] and
                 over > BIG_SCORE_TRIGGER["over_prob"])
    return {
        "triggered": triggered,
        "win_prob": sd["prob"],
        "ah_line_abs": ah_abs,
        "over_prob": over,
        "conditions": {
            "win>=70%": sd["level"] == "strong",
            f"ah>={BIG_SCORE_TRIGGER['ah_line']}": ah_abs >= BIG_SCORE_TRIGGER["ah_line"],
            f"over>{BIG_SCORE_TRIGGER['over_prob']:.0%}": over > BIG_SCORE_TRIGGER["over_prob"],
        },
    }


def confidence_layers(report: dict, conflict: dict) -> dict:
    """置信度分层: 方向/净胜球/具体比分。"""
    sd = strong_direction(report["ensemble"])
    # 方向置信度
    if conflict["level"] == "direction":
        dir_conf = "低"
    elif conflict["level"] == "magnitude":
        dir_conf = "中"
    elif sd["level"] == "strong":
        dir_conf = "高"
    elif sd["level"] == "mid":
        dir_conf = "中高"
    else:
        dir_conf = "中"
    # 净胜球置信度(让球赢盘概率)
    ah_win = report["asian_handicap"]["win"]
    if ah_win >= 0.60:
        gd_conf = "中高"
    elif ah_win >= 0.50:
        gd_conf = "中"
    else:
        gd_conf = "低"
    # 具体比分置信度(Top1 概率)
    top1_p = report["matrix_top"][2]
    if top1_p >= 0.15:
        score_conf = "中高"
    elif top1_p >= 0.10:
        score_conf = "中"
    else:
        score_conf = "低"
    return {"direction": dir_conf, "goal_difference": gd_conf, "exact_score": score_conf}


def surprise_paths(report: dict) -> dict:
    """意外路径: 主要意外(第二可能结果) + 极端意外(最低概率非零方向)。"""
    ph, pd_, pa = (report["ensemble"]["home"], report["ensemble"]["draw"], report["ensemble"]["away"])
    probs = {"home": ph, "draw": pd_, "away": pa}
    sorted_dirs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    main_dir = sorted_dirs[0][0]
    # 主要意外 = 第二可能的方向
    second_dir, second_p = sorted_dirs[1]
    # 极端意外 = 最低概率的方向
    worst_dir, worst_p = sorted_dirs[2]
    # 从比分分布找意外比分
    from score_matrix import score_dist
    lh, la = report["expected_goals"]["home"], report["expected_goals"]["away"]
    dist = score_dist(lh, la)
    # 主要意外比分: 第二方向里概率最高的比分
    def top_score_for_dir(direction):
        for i, j, p in dist:
            if direction == "home" and i > j:
                return (i, j, p)
            if direction == "draw" and i == j:
                return (i, j, p)
            if direction == "away" and i < j:
                return (i, j, p)
        return None
    main_surprise_score = top_score_for_dir(second_dir)
    extreme_surprise_score = top_score_for_dir(worst_dir)
    return {
        "main_direction": main_dir,
        "main_surprise": {"direction": second_dir, "prob": second_p,
                           "score": main_surprise_score},
        "extreme_surprise": {"direction": worst_dir, "prob": worst_p,
                              "score": extreme_surprise_score},
    }


def draw_warning(report: dict, market_probs: Optional[tuple] = None) -> dict:
    """平局预警 (2026-08-29 新增, 对齐旧系统口径).

    市场去水平局 >= 26% = 普通预警(让球只用+号/受让)
    市场去水平局 >= 30% = 强预警(让球只用+号, 2.50 大小球盘降星/谨慎)
    市场去水平局缺失时用 ensemble 平局概率兜底并标注 market_based=False。
    """
    if market_probs and all(np.isfinite(x) for x in market_probs):
        draw_p = float(market_probs[1])
        market_based = True
    else:
        draw_p = float(report["ensemble"]["draw"])
        market_based = False
    level = None
    if draw_p >= 0.30:
        level = "strong"
    elif draw_p >= 0.26:
        level = "normal"
    return {"level": level, "draw_prob": round(draw_p, 4), "market_based": market_based}


def analyze_rules(report: dict, market_odds: Optional[tuple] = None) -> dict:
    """规则引擎总入口: 输入 match_report 输出, 返回全部规则判定。"""
    from devig import devig_1x2
    market_probs = None
    if market_odds and all(np.isfinite(x) for x in market_odds):
        try:
            market_probs = devig_1x2(*market_odds, method="shin")
        except Exception:
            market_probs = None
    sd = strong_direction(report["ensemble"])
    dual = dual_source_alignment(report, market_probs)
    conflict = conflict_analysis(report, market_probs)
    trigger = score_trigger(report)
    conf = confidence_layers(report, conflict)
    surprise = surprise_paths(report)
    dw = draw_warning(report, market_probs)
    return {
        "strong_direction": sd,
        "dual_source": dual,
        "conflict": conflict,
        "score_trigger": trigger,
        "confidence": conf,
        "surprise": surprise,
        "draw_warning": dw,
        "market_probs": market_probs,
    }


def _self_test():
    # 构造一个模拟 report(巴萨 vs 毕尔巴鄂, 强方向)
    report = {
        "elo": {"home_win": 0.7023},
        "home_away_1x2": {"home": 0.8163, "draw": 0.1180, "away": 0.0657},
        "ensemble": {"home": 0.8030, "draw": 0.1258, "away": 0.0712},
        "expected_goals": {"home": 2.946, "away": 0.755},
        "over_2_5": 0.7107,
        "asian_handicap": {"line": -1.75, "win": 0.62, "lose": 0.30, "push": 0.08},
        "matrix_top": (2, 0, 0.107),
    }
    market_odds = (1.25, 6.58, 11.08)
    rules = analyze_rules(report, market_odds)
    print("== 巴萨场景(强方向) ==")
    print(f"强方向: {rules['strong_direction']}")
    print(f"双源同向: {rules['dual_source']}")
    print(f"冲突: {rules['conflict']['level']} - {rules['conflict']['description']}")
    print(f"比分触发: {rules['score_trigger']['triggered']} (条件: {rules['score_trigger']['conditions']})")
    print(f"置信度: {rules['confidence']}")
    print(f"意外: 主要={rules['surprise']['main_surprise']['direction']} "
          f"({rules['surprise']['main_surprise']['prob']:.1%}), "
          f"极端={rules['surprise']['extreme_surprise']['direction']} "
          f"({rules['surprise']['extreme_surprise']['prob']:.1%})")
    assert rules["strong_direction"]["level"] == "strong"
    assert rules["strong_direction"]["direction"] == "home"
    assert rules["dual_source"]["aligned"] is True
    assert rules["conflict"]["level"] == "none"
    assert rules["score_trigger"]["triggered"] is True  # 80%>70, ah=1.75, over=71%>65%
    assert rules["confidence"]["direction"] == "高"

    # 构造冲突场景(里尔 vs 巴黎: Elo看好里尔, 泊松/市场看好巴黎)
    report2 = {
        "elo": {"home_win": 0.6391},
        "home_away_1x2": {"home": 0.2969, "draw": 0.2664, "away": 0.4367},
        "ensemble": {"home": 0.2648, "draw": 0.2583, "away": 0.4769},
        "expected_goals": {"home": 1.103, "away": 1.398},
        "over_2_5": 0.4566,
        "asian_handicap": {"line": 0.25, "win": 0.563, "lose": 0.437, "push": 0.0},
        "matrix_top": (1, 1, 0.126),
    }
    market_odds2 = (4.63, 3.87, 1.73)
    rules2 = analyze_rules(report2, market_odds2)
    print("\n== 里尔场景(方向冲突) ==")
    print(f"强方向: {rules2['strong_direction']}")
    print(f"双源同向: {rules2['dual_source']}")
    print(f"冲突: {rules2['conflict']['level']} - {rules2['conflict']['description']}")
    print(f"比分触发: {rules2['score_trigger']['triggered']}")
    print(f"置信度: {rules2['confidence']}")
    assert rules2["conflict"]["level"] == "direction"  # Elo=home, 泊松/市场=away
    assert rules2["confidence"]["direction"] == "低"
    assert rules2["score_trigger"]["triggered"] is False
    print("\n== report_rules 自检通过 ==")


if __name__ == "__main__":
    _self_test()
