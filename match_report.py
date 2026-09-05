# -*- coding: utf-8 -*-
"""单场比赛"模型结果"统一输出: 组装 10 项指标 + 格式化报告文本。

模型版本: V4 (2026-08-30)
  - Elo λ修正 + [0.7,1.3]总系数包络
  - 按联赛分组概率校准
  - Dixon-Coles低比分修正
  - Elo历史缓存(批量场景性能优化)

对应报告"模型结果"章节:
1. 严格 EloML 强弱
2. 主客场比分分层 90 分钟
3. 综合校准
4. 预期进球
5. 大 2.5 概率
6. 双方进球概率
7. 最近八场
8. Top3 比分
9. 矩阵最高比分
10. 让球理解

用法: python football_analyzer/match_report.py  # 自检(巴萨 vs 毕尔巴鄂复现)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

import elo
from ensemble_calib import ensemble_1x2
from home_away_layer import home_away_1x2, home_away_summary
from model import (poisson_fit, apply_1x2_calibration, poisson_1x2, poisson_predict,
                   apply_ou_calibration, apply_ou_isotonic)
from score_matrix import (btts_prob, expected_goals, matrix_top,
                           over_under_prob, top_scores)
from dixon_coles import (dc_1x2, dc_btts_prob, dc_matrix_top,
                          dc_over_under_prob, dc_top_scores)


# Elo历史缓存: key=(df行数, 最后日期), value=compute_elo_history结果
# 批量扫描/回测时避免每场重算几万场历史; 数据变化时key自动失效
_elo_history_cache = {}


def get_latest_elo(df: pd.DataFrame, team: str, date) -> float:
    """从历史 df 计算某队在 date 前的最新 Elo rating。无数据返回 1500。"""
    if isinstance(date, str):
        date = pd.Timestamp(date)
    # 缓存key: 数据量+最新日期, 数据变化时自动失效
    _key = (len(df), str(df["date"].max()) if len(df) > 0 else "")
    if _key not in _elo_history_cache:
        try:
            from cache_utils import elo_history_cached
            _elo_history_cache[_key] = elo_history_cached(df)
        except Exception:
            _elo_history_cache[_key] = elo.compute_elo_history(df)
    hist = _elo_history_cache[_key]
    sub = hist[(hist["date"] < date) &
               ((hist["home"] == team) | (hist["away"] == team))]
    if len(sub) == 0:
        return 1500.0
    last = sub.sort_values("date").iloc[-1]
    return float(last["elo_home_pre"] if last["home"] == team else last["elo_away_pre"])


def _ah_win_prob_single(lh: float, la: float, line: float, max_goals: int = 10) -> dict:
    """单盘口(整数/半整数)让球赢盘/输盘/走水概率。line 为正=主队受让, 负=主队让球。"""
    from devig import poisson_pmf
    win = lose = push = 0.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lh) * poisson_pmf(j, la)
            diff = i - j + line  # 主队让球后净胜
            if abs(diff) < 1e-9:
                push += p
            elif diff > 0:
                win += p
            else:
                lose += p
    s = win + lose + push
    if s <= 0:
        return {"win": np.nan, "lose": np.nan, "push": np.nan}
    return {"win": win / s, "lose": lose / s, "push": push / s}


def ah_win_prob(lh: float, la: float, line: float, max_goals: int = 10) -> dict:
    """让球赢盘/输盘/走水概率。支持四分之一盘(0.25/0.75)拆盘。

    四分之一盘正确公式: 0.5 * P(line-0.25) + 0.5 * P(line+0.25)
    例如主让0.25 = 一半平手 + 一半主让0.5; 0-0比分=半输(走水一半+输一半)。
    """
    # 判断是否为四分之一盘(line 不是整数或半整数)
    remainder = abs(line % 0.5)
    is_quarter = remainder > 1e-9 and abs(remainder - 0.5) > 1e-9
    if is_quarter:
        r_low = _ah_win_prob_single(lh, la, line - 0.25, max_goals)
        r_high = _ah_win_prob_single(lh, la, line + 0.25, max_goals)
        return {
            "win": 0.5 * r_low["win"] + 0.5 * r_high["win"],
            "lose": 0.5 * r_low["lose"] + 0.5 * r_high["lose"],
            "push": 0.5 * r_low["push"] + 0.5 * r_high["push"],
        }
    return _ah_win_prob_single(lh, la, line, max_goals)


def recommend_ah_line(lh: float, la: float) -> float:
    """从 λ 差推荐让球线(最近 0.25 倍数, 主队让球为负)。"""
    if not np.isfinite(lh) or not np.isfinite(la):
        return 0.0  # 本地库无该队数据(λ=NaN) -> 让球线按平手, 报告不崩溃
    diff = lh - la
    # 取最近 0.25
    line = round(diff * 4) / 4
    # 主队强则让球(负), 主队弱则受让(正)
    return -line if line > 0 else -line


def match_model_report(fit: dict, df: pd.DataFrame, row: dict,
                       elo_home: Optional[float] = None,
                       elo_away: Optional[float] = None,
                       market_odds: Optional[tuple] = None,
                       ah_line: Optional[float] = None,
                       injury_coef: Optional[tuple] = None,
                       bayes: Optional[dict] = None) -> dict:
    """组装单场比赛"模型结果"10 项指标。

    bayes: bayes_poisson.bayes_fit 结果(可选), 提供后计算 n_eff 并检测"λ样本不足" 

    row: {league, home, away, date}
    market_odds: (odds_h, odds_d, odds_a) 可选, 用于市场去水
    ah_line: 让球线(负=主队让球), 不传则从 λ 推荐
    """
    league = row["league"]
    home, away = row["home"], row["away"]
    date = row.get("date", pd.Timestamp.now())

    # Dixon-Coles ρ 参数: 按联赛估计的低比分修正系数, 无数据用默认0.05
    rho = float((fit.get("_dc_rho") or {}).get(league, 0.05)) if fit else 0.05

    # 队名解析: 报告用名 -> 本地库规范名(MLS/墨超等源名差异), 保证 poisson/Elo 命中
    home_m, away_m = home, away
    try:
        from odds_source import team_matcher
        _tm = team_matcher()
        home_m = _tm.resolve(home) or home
        away_m = _tm.resolve(away) or away
    except Exception:
        pass
    row_m = dict(row, home=home_m, away=away_m)
    # 2026-09-03 修正: team_matcher 可能把原名解析成别的变体(如 Servette FC->Servette),
    # 而拟合表用的是原名 -> 解析名在本联赛无数据但原名有时, 回退用原名(防静默联赛均值兜底)
    try:
        _ft_teams = ((fit or {}).get(league) or {}).get("teams", {})
        if _ft_teams:
            if home_m not in _ft_teams and home in _ft_teams:
                home_m = home
            if away_m not in _ft_teams and away in _ft_teams:
                away_m = away
        row_m = dict(row, home=home_m, away=away_m)
    except Exception:
        pass

    # 1. Elo 强弱
    if elo_home is None:
        elo_home = get_latest_elo(df, home_m, date)
    if elo_away is None:
        elo_away = get_latest_elo(df, away_m, date)
    _hadv = 50 if league == "MLS" else 100  # MLS 主场优势近年下滑, Elo 主场分减半
    elo_h = elo.expected_score(elo_home, elo_away, home_adv=_hadv)

    # 2. 主客场比分分层
    ha = home_away_1x2(fit, row_m)
    lh, la = ha["lh"], ha["la"]
    # 本地库无该队数据(如 MLS/墨超) -> λ=NaN, 用联赛均值兜底, 避免后续报告崩溃
    if not np.isfinite(lh) or not np.isfinite(la):
        _lg = (fit.get(league) or {}).get("lg", {}) if fit else {}
        _ha = _lg.get("home_avg")
        _aa = _lg.get("away_avg")
        # 注意: NaN 是 truthy, 不能用 `_ha or 1.3` 兜底(NaN or 1.3 = NaN), 必须显式检查
        lh = float(_ha) if (_ha is not None and np.isfinite(_ha)) else 1.3
        la = float(_aa) if (_aa is not None and np.isfinite(_aa)) else 1.1
        lh, la = max(lh, 0.2), max(la, 0.2)
    # 伤停λ修正(首发核验): 主队λ×coef_h, 客队λ×coef_a (位置加权, 下限0.75)
    _lh_base, _la_base = lh, la  # 伤停前λ, 作为总系数包络的基准
    if injury_coef:
        lh *= float(injury_coef[0])
        la *= float(injury_coef[1])

    # Elo λ修正: rating差距影响预期进球(每100分差距调整8%, 单系数限幅0.5~1.8)
    # 仅当两队都有真实Elo数据(非默认1500)时应用, 避免升班马/新球队误修正
    # 架构原则: ensemble_1x2的elo权重保持0, 避免同一信号双重计数
    # 联赛专属调校: 低K值联赛(rating更稳定)修正幅度稍大, 高K值联赛修正幅度稍小
    _elo_coef_by_league = {
        "E2": 0.085,  # 英冠 K=24, rating稳定, 修正幅度+0.5pp(0.09稍大, 全量胜率降1.4pp)
        "P1": 0.07,   # 葡超 K=28
        "JP1": 0.07,  # J1 K=28
    }
    _elo_coef = _elo_coef_by_league.get(league, 0.08)
    if abs(elo_home - 1500.0) > 1e-9 and abs(elo_away - 1500.0) > 1e-9:
        _elo_diff = (elo_home - elo_away) / 100.0
        _elo_factor_h = max(0.5, min(1.8, 1.0 + _elo_coef * _elo_diff))
        _elo_factor_a = max(0.5, min(1.8, 1.0 - _elo_coef * _elo_diff))
        lh *= _elo_factor_h
        la *= _elo_factor_a
    # 总系数包络校验: 伤停×Elo的总修正(相对伤停前λ)限制在[0.7, 1.3]
    # 例: 伤停0.75 × Elo0.7 = 0.525 -> 钳位到0.7, 防止极端场次突破安全包络
    if _lh_base > 0:
        _total_h = lh / _lh_base
        if _total_h < 0.7 or _total_h > 1.3:
            lh = _lh_base * max(0.7, min(1.3, _total_h))
    if _la_base > 0:
        _total_a = la / _la_base
        if _total_a < 0.7 or _total_a > 1.3:
            la = _la_base * max(0.7, min(1.3, _total_a))

    # 3. 综合校准
    poisson_p = dc_1x2(lh, la, rho) if np.isfinite(lh) else (np.nan, np.nan, np.nan)
    market_p = None
    if market_odds:
        from devig import devig_1x2
        try:
            market_p = devig_1x2(*market_odds, method="shin")
        except Exception:
            market_p = None
    # 综合校准: ensemble融合泊松/市场/主客场三源; elo权重保持0(避免与λ内核Elo修正双重计数)
    ens = ensemble_1x2(poisson_p, market_p, (ha["ph"], ha["pd"], ha["pa"]),
                        elo_h=elo_h)
    # 1X2 概率校准(2026-09-04 P0): 用训练数据拟合的 预测概率->实际发生率 曲线修正
    # ensemble 输出(与 OU 校准同构), 解决高置信端过度自信导致 star=3 假高置信
    _c1x2 = ((fit or {}).get("_calib_1x2") or {}).get(league)
    if _c1x2:
        _ep = apply_1x2_calibration((ens["ph"], ens["pd"], ens["pa"]), _c1x2)
        ens["ph"], ens["pd"], ens["pa"] = _ep

    # 4. 预期进球
    eg = expected_goals(lh, la)

    # 5. 大 2.5 概率 (Dixon-Coles 低比分修正 + 概率校准)
    ou25 = dc_over_under_prob(lh, la, line=2.5, rho=rho)
    # 概率校准: 用训练数据的实际大球率修正泊松概率(解决置信度分层反常)
    # 分联赛校准(进球环境差异大, 全局混合会抹平差异); 该联赛无校准数据则不修正
    _ou_calib = ((fit.get("_ou_calibration") or {}).get(league)) if fit else None
    _ou_iso = ((fit.get("_ou_isotonic") or {}).get(league)) if fit else None
    if _ou_iso is not None:
        ou25 = apply_ou_isotonic(ou25, _ou_iso)   # isotonic 优先(2026-09-05)
    else:
        ou25 = apply_ou_calibration(ou25, _ou_calib)

    # 6. BTTS (Dixon-Coles 修正)
    btts = dc_btts_prob(lh, la, rho)

    # 7. 最近八场
    recent = home_away_summary(df, row_m, n=8)

    # 数据质量检测: Elo 默认值1500 或 最近八场样本不足 -> 标注警告
    data_warnings = []
    if abs(elo_home - 1500.0) <= 1e-9:
        data_warnings.append(f"主队'{home}'无Elo历史(用默认1500)")
    if abs(elo_away - 1500.0) <= 1e-9:
        data_warnings.append(f"客队'{away}'无Elo历史(用默认1500)")
    hn = recent.get("home_recent_home", {}).get("n", 0)
    an = recent.get("away_recent_away", {}).get("n", 0)
    if hn == 0:
        data_warnings.append(f"主队'{home}'无主场近8场数据")
    if an == 0:
        data_warnings.append(f"客队'{away}'无客场近8场数据")
    # λ 兜底检测(非有限值被联赛均值替换)
    if not np.isfinite(ha.get("lh", np.nan)) or not np.isfinite(ha.get("la", np.nan)):
        data_warnings.append("泊松λ用联赛均值兜底(无球队级数据)")
    # 联赛内无该队数据检测: poisson_predict 对无数据队返回强度1.0(联赛均值),
    # λ 仍是有限值, 不会触发上面的 NaN 兜底 -> 必须显式检查避免静默降级
    _ft = ((fit or {}).get(league) or {}).get("teams", {})
    if _ft:
        if home_m not in _ft:
            data_warnings.append(f"主队'{home}'无{league}联赛数据(用联赛均值)")
        if away_m not in _ft:
            data_warnings.append(f"客队'{away}'无{league}联赛数据(用联赛均值)")

    # 贝叶斯 λ 样本量检测: n_eff 小 -> 攻防强度后验区间宽, 概率置信度低
    n_eff_min = None
    if bayes:
        try:
            from bayes_poisson import uncertainty_score
            _u = uncertainty_score(bayes, row_m)
            if _u:
                n_eff_min = min(_u["home"]["n_eff"], _u["away"]["n_eff"])
                if n_eff_min < 5.0:
                    data_warnings.append(
                        f"λ贝叶斯样本不足(n_eff={n_eff_min:.1f}), 概率区间偏宽, 建议降置信")
        except Exception:
            pass

    # 8. Top3 比分 (Dixon-Coles 修正)
    top3 = dc_top_scores(lh, la, rho=rho, n=3)

    # 9. 矩阵最高 (Dixon-Coles 修正)
    mt = dc_matrix_top(lh, la, rho=rho)

    # 10. 让球理解
    if ah_line is None:
        ah_line = recommend_ah_line(lh, la)
    ah = ah_win_prob(lh, la, ah_line)

    return {
        "match": f"{home} vs {away}",
        "league": league,
        "date": str(date),
        "elo": {"home_rating": elo_home, "away_rating": elo_away,
                "home_win": elo_h, "away_win": 1 - elo_h},
        "home_away_1x2": {"home": ha["ph"], "draw": ha["pd"], "away": ha["pa"]},
        "ensemble": {"home": ens["ph"], "draw": ens["pd"], "away": ens["pa"],
                     "weights": ens["weights_used"]},
        "expected_goals": eg,
        "over_2_5": ou25,
        "btts": btts,
        "recent": recent,
        "top3_scores": top3,
        "matrix_top": mt,
        "asian_handicap": {"line": ah_line, "win": ah["win"],
                           "lose": ah["lose"], "push": ah["push"]},
        "data_warnings": data_warnings,
        "n_eff_min": n_eff_min,
    }


def format_model_result(r: dict) -> str:
    """格式化成报告"模型结果"章节文本。"""
    lines = []
    lines.append(f"== 模型结果: {r['match']} ==")
    lines.append(f"严格EloML: {r['elo']['home_win']:.2%} / {r['elo']['away_win']:.2%}"
                 f" (rating {r['elo']['home_rating']:.0f}/{r['elo']['away_rating']:.0f})")
    ha = r["home_away_1x2"]
    lines.append(f"主客场比分分层: 主胜{ha['home']:.2%} / 平局{ha['draw']:.2%} / 客胜{ha['away']:.2%}")
    en = r["ensemble"]
    lines.append(f"综合校准: 主胜{en['home']:.2%} / 平局{en['draw']:.2%} / 客胜{en['away']:.2%}")
    eg = r["expected_goals"]
    lines.append(f"预期进球: 主{eg['home']:.3f} / 客{eg['away']:.3f} / 总{eg['total']:.2f}")
    lines.append(f"大2.5概率: {r['over_2_5']:.2%}")
    lines.append(f"双方进球概率: {r['btts']:.2%}")
    hh = r["recent"]["home_recent_home"]
    aa = r["recent"]["away_recent_away"]
    lines.append(f"最近八场: 主队主场{hh['points']}分/进{hh['gf']}失{hh['ga']}; "
                 f"客队客场{aa['points']}分/进{aa['gf']}失{aa['ga']}")
    top3 = r["top3_scores"]
    lines.append(f"Top3比分: " + " / ".join(f"{i}-{j}({p:.1%})" for i, j, p in top3))
    mt = r["matrix_top"]
    lines.append(f"矩阵最高: {mt[0]}-{mt[1]} ({mt[2]:.1%})")
    ah = r["asian_handicap"]
    lines.append(f"让球理解: 线{ah['line']:+.2f} 赢盘{ah['win']:.1%}/输盘{ah['lose']:.1%}/走水{ah['push']:.1%}")
    # 数据质量警告
    warns = r.get("data_warnings") or []
    if warns:
        lines.append(f"⚠ 数据质量: {'; '.join(warns)}")
    return "\n".join(lines)


def _self_test():
    # 用真实数据复现(需要数据文件)
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from data_loader import load_recent_csv
    df = load_recent_csv()
    if df is None or len(df) == 0:
        print("跳过真实数据自检(数据文件不存在)")
        return
    # 找一场巴萨主场比赛
    barca = df[df["home"] == "Barcelona"].sort_values("date", ascending=False)
    if len(barca) == 0:
        print("跳过: 数据中无巴萨主场比赛")
        return
    row = barca.iloc[0]
    print(f"测试比赛: {row['date'].date()} {row['home']} vs {row['away']} ({row['league']})")
    # 用该场之前的数据 fit
    train = df[df["date"] < row["date"]]
    fit = poisson_fit(train)
    r = match_model_report(fit, train, row.to_dict())
    print(format_model_result(r))
    # 断言关键指标有效
    assert 0 < r["elo"]["home_win"] < 1
    assert abs(r["home_away_1x2"]["home"] + r["home_away_1x2"]["draw"] + r["home_away_1x2"]["away"] - 1) < 1e-6
    assert abs(r["ensemble"]["home"] + r["ensemble"]["draw"] + r["ensemble"]["away"] - 1) < 1e-6
    assert len(r["top3_scores"]) == 3
    assert 0 <= r["over_2_5"] <= 1
    assert 0 <= r["btts"] <= 1
    print("== match_report 自检通过 ==")


if __name__ == "__main__":
    _self_test()
