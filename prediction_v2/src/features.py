"""特征工程 —— 无泄漏核心。

按时间顺序单遍扫描全部比赛，每场比赛只使用严格早于其开赛时间的数据：
  - Elo 评分（K=32, 主场+100）
  - 攻防强度（指数时间衰减加权，含收缩先验）
  - 近5场滚动战绩（总/主场/客场分列）
  - 休息天数
  - 联赛场均进球（滚动窗口）
  - 历史交锋（同队对近6次总进球均值）

该构造保证"未来数据不可能进入特征"。
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from .data_loader import ALL_ODDS

REQUIRED_FEATURES = [
    "elo_home", "elo_away", "elo_diff",
    "att_home", "def_home", "att_away", "def_away",
    "gf_h5", "ga_h5", "pts_h5", "gf_a5", "ga_a5", "pts_a5",
    "gf_home_h5", "ga_home_h5", "gf_away_a5", "ga_away_a5",
    "days_home", "days_away",
    "league_avg_home", "league_avg_away", "league_avg_total",
    "league_scoring_idx", "league_strength",
    "h2h_total_avg", "h2h_n",
    "gf_h10", "ga_h10", "pts_h10",
    "gf_a10", "ga_a10", "pts_a10",
    "gf_home_h10", "ga_home_h10", "gf_away_a10", "ga_away_a10",
    "h2h_n3", "h2h_n5", "h2h_total3", "h2h_total5",
    "h2h_h_gf3", "h2h_h_ga3", "h2h_a_gf3", "h2h_a_ga3",
    "h2h_h_gf5", "h2h_h_ga5", "h2h_a_gf5", "h2h_a_ga5",
    "h2h_h_win3", "h2h_a_win3", "h2h_draw3",
    "h2h_h_win5", "h2h_a_win5", "h2h_draw5",
]

# 可选 ML 扩展特征（默认关闭；实验: run_backtest --extra-features tech,sos）
# 全部来自旧系统 fd_builder 移植：技术统计滚动(射门/射正/角球/犯规) + SoS(对手强度调整攻防)
EXTRA_FEATURES_MAP = {
    "tech": ["home_shots5", "away_shots5", "home_st5", "away_st5",
             "home_corners5", "away_corners5", "home_fouls5", "away_fouls5"],
    "sos": ["home_gf_sos", "home_ga_sos", "away_gf_sos", "away_ga_sos"],
}


def _fnum(v):
    """转 float；None/NaN 返回 None。"""
    try:
        v = float(v)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None


def _shrink(rate: float, n: float, prior: float) -> float:
    """向 1.0 收缩：样本越少越接近先验。"""
    return (n * rate + prior * 1.0) / (n + prior)


def build_features(matches: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """返回与 matches 对齐（同序同长）的特征 DataFrame。"""
    elo_k = float(cfg["elo_k"])
    hfa = float(cfg["elo_home_adv"])
    half_life = float(cfg["decay_half_life_days"])
    lam = math.log(2) / half_life
    prior = float(cfg["strength_prior"])
    min_games = int(cfg.get("min_games_strength", 3))

    def new_team():
        return {
            "elo": 1500.0, "last": None,
            "gf": 0.0, "ga": 0.0, "n": 0.0,
            "gf_h": 0.0, "ga_h": 0.0, "n_h": 0.0,
            "gf_a": 0.0, "ga_a": 0.0, "n_a": 0.0,
            "xgf": 0.0, "xga": 0.0, "xn": 0.0, "xlast": None,
            "xgf_h": 0.0, "xga_h": 0.0, "xn_h": 0.0,
            "xgf_a": 0.0, "xga_a": 0.0, "xn_a": 0.0,
            "last5": deque(maxlen=5), "last5_h": deque(maxlen=5), "last5_a": deque(maxlen=5),
        "last10": deque(maxlen=10), "last10_h": deque(maxlen=10), "last10_a": deque(maxlen=10),
            "last5_stats": deque(maxlen=5),
            "sos_gf": 0.0, "sos_ga": 0.0, "sos_opp_elo": 0.0, "sos_w": 0.0, "sos_last": None,
        }

    teams: dict = defaultdict(new_team)
    league_gh: dict = defaultdict(lambda: deque(maxlen=300))
    league_ga: dict = defaultdict(lambda: deque(maxlen=300))
    league_xgh: dict = defaultdict(lambda: deque(maxlen=300))
    league_xga: dict = defaultdict(lambda: deque(maxlen=300))
    h2h: dict = defaultdict(lambda: deque(maxlen=6))
    global_gh: deque = deque(maxlen=300)
    global_ga: deque = deque(maxlen=300)
    league_elo: dict = defaultdict(lambda: {"sum": 0.0, "n": 0.0})
    has_xg = "home_xg" in matches.columns and "away_xg" in matches.columns

    rows = []
    it = matches.itertuples(index=False)
    for r in it:
        home, away = r.HomeTeam, r.AwayTeam
        d = r.Date
        th, ta = teams[home], teams[away]

        # ---------- 快照：只用历史数据 ----------
        elo_h, elo_a = th["elo"], ta["elo"]
        elo_diff = (elo_h + hfa) - elo_a

        lg_gh = league_gh.get(r.league) or deque()
        lg_ga = league_ga.get(r.league) or deque()
        league_avg_h = max(sum(lg_gh) / len(lg_gh), 0.2) if lg_gh else 1.35
        league_avg_a = max(sum(lg_ga) / len(lg_ga), 0.2) if lg_ga else 1.15
        league_avg_t = league_avg_h + league_avg_a
        global_avg_t = ((sum(global_gh) + sum(global_ga)) / len(global_gh)
                        if global_gh else 2.5)
        league_scoring_idx = league_avg_t / global_avg_t if global_gh else 1.0
        _le = league_elo.get(r.league)
        league_strength = (_le["sum"] / _le["n"]) if _le and _le["n"] > 0 else 1500.0

        # 攻防强度（衰减加权 / 收缩）
        def rate(s, n, default):
            return s / n if n >= 1e-9 else default

        gf_home_rate = rate(th["gf_h"], th["n_h"], league_avg_h)
        ga_home_rate = rate(th["ga_h"], th["n_h"], league_avg_a)
        gf_away_rate = rate(ta["gf_a"], ta["n_a"], league_avg_a)
        ga_away_rate = rate(ta["ga_a"], ta["n_a"], league_avg_h)
        # 样本不足回退总体
        if th["n_h"] < min_games:
            gf_home_rate = rate(th["gf"], th["n"], league_avg_h)
            ga_home_rate = rate(th["ga"], th["n"], league_avg_a)
        if ta["n_a"] < min_games:
            gf_away_rate = rate(ta["gf"], ta["n"], league_avg_a)
            ga_away_rate = rate(ta["ga"], ta["n"], league_avg_h)

        att_home = _shrink(gf_home_rate / league_avg_h, max(th["n_h"], th["n"], 1.0), prior)
        def_home = _shrink(ga_home_rate / league_avg_a, max(th["n_h"], th["n"], 1.0), prior)
        att_away = _shrink(gf_away_rate / league_avg_a, max(ta["n_a"], ta["n"], 1.0), prior)
        def_away = _shrink(ga_away_rate / league_avg_h, max(ta["n_a"], ta["n"], 1.0), prior)

        # ---- xG 强度（仅当两队都有 xG 历史时给出, 否则 None -> 模型回退纯进球）----
        att_home_xg = def_home_xg = att_away_xg = def_away_xg = None
        if has_xg:
            lg_xgh = league_xgh.get(r.league) or deque()
            lg_xga = league_xga.get(r.league) or deque()
            league_xg_h = max(sum(lg_xgh) / len(lg_xgh), 0.2) if lg_xgh else 1.35
            league_xg_a = max(sum(lg_xga) / len(lg_xga), 0.2) if lg_xga else 1.15

            def xrate(s, n):
                return s / n if n >= 1e-9 else None

            xgf_home_r = xrate(th["xgf_h"], th["xn_h"])
            xga_home_r = xrate(th["xga_h"], th["xn_h"])
            xgf_away_r = xrate(ta["xgf_a"], ta["xn_a"])
            xga_away_r = xrate(ta["xga_a"], ta["xn_a"])
            if th["xn_h"] < min_games:
                xgf_home_r = xrate(th["xgf"], th["xn"])
                xga_home_r = xrate(th["xga"], th["xn"])
            if ta["xn_a"] < min_games:
                xgf_away_r = xrate(ta["xgf"], ta["xn"])
                xga_away_r = xrate(ta["xga"], ta["xn"])
            if None not in (xgf_home_r, xga_home_r):
                att_home_xg = _shrink(xgf_home_r / league_xg_h, max(th["xn_h"], th["xn"], 1.0), prior)
                def_home_xg = _shrink(xga_home_r / league_xg_a, max(th["xn_h"], th["xn"], 1.0), prior)
            if None not in (xgf_away_r, xga_away_r):
                att_away_xg = _shrink(xgf_away_r / league_xg_a, max(ta["xn_a"], ta["xn"], 1.0), prior)
                def_away_xg = _shrink(xga_away_r / league_xg_h, max(ta["xn_a"], ta["xn"], 1.0), prior)

        # ---- 技术统计滚动（近5场 射门/射正/角球/犯规；均为赛前可得的历史数据）----
        def stat_avg(team, key):
            vals = [m[key] for m in team["last5_stats"] if m.get(key) is not None]
            return sum(vals) / len(vals) if vals else None

        home_shots5 = stat_avg(th, "shots");   away_shots5 = stat_avg(ta, "shots")
        home_st5 = stat_avg(th, "st");         away_st5 = stat_avg(ta, "st")
        home_corners5 = stat_avg(th, "corners"); away_corners5 = stat_avg(ta, "corners")
        home_fouls5 = stat_avg(th, "fouls");   away_fouls5 = stat_avg(ta, "fouls")

        # ---- SoS（对手强度调整攻防；衰减加权；对手 Elo 用本场赛前快照值，无泄漏）----
        def sos_vals(team):
            if team["sos_w"] < 1e-9:
                return None, None
            avg_opp = team["sos_opp_elo"] / team["sos_w"]
            gf = team["sos_gf"] / team["sos_w"]
            ga = team["sos_ga"] / team["sos_w"]
            f = avg_opp / 1500.0
            return gf * f, ga * (2.0 - f)

        home_gf_sos, home_ga_sos = sos_vals(th)
        away_gf_sos, away_ga_sos = sos_vals(ta)

        # 近5场滚动（总 / 主 / 客）
        def roll5(dq):
            if not dq:
                return None
            gf = sum(g for g, _ in dq)
            ga = sum(a for _, a in dq)
            pts = sum(3 if g > a else 1 if g == a else 0 for g, a in dq)
            return gf, ga, pts

        h5 = roll5(th["last5"]); h5h = roll5(th["last5_h"])
        a5 = roll5(ta["last5"]); a5a = roll5(ta["last5_a"])

        # 近10场滚动（总 / 主 / 客）
        def roll10(dq):
            if not dq:
                return None
            gf = sum(g for g, _ in dq)
            ga = sum(a for _, a in dq)
            pts = sum(3 if g > a else 1 if g == a else 0 for g, a in dq)
            return gf, ga, pts

        h10 = roll10(th["last10"]); h10h = roll10(th["last10_h"])
        a10 = roll10(ta["last10"]); a10a = roll10(ta["last10_a"])

        # 休息天数
        days_h = (d - th["last"]).days if th["last"] is not None else 7
        days_a = (d - ta["last"]).days if ta["last"] is not None else 7

        # 历史交锋（窗口 3/5：总进球、双方进球、胜平负率）
        pair = tuple(sorted((home, away)))
        meets = h2h.get(pair) or deque()
        h2h_totals = [gh + ga for _, _, gh, ga in reversed(meets)][:4]
        h2h_avg = sum(h2h_totals) / len(h2h_totals) if h2h_totals else league_avg_t
        h2h_n = len(h2h_totals)

        def h2h_stats(w):
            ms = list(reversed(meets))[:w]
            n = len(ms)
            if n == 0:
                return (0, league_avg_t, league_avg_h, league_avg_a,
                        league_avg_a, league_avg_h, 1/3, 1/3, 1/3)
            h_gf = h_ga = a_gf = a_ga = tot = 0.0
            h_w = a_w = dr = 0
            for mh, ma, mgh, mga in ms:
                hs, ha = (mgh, mga) if mh == home else (mga, mgh)
                h_gf += hs; h_ga += ha; a_gf += ha; a_ga += hs
                tot += mgh + mga
                if hs > ha:
                    h_w += 1
                elif hs < ha:
                    a_w += 1
                else:
                    dr += 1
            return (n, tot / n, h_gf / n, h_ga / n, a_gf / n, a_ga / n,
                    h_w / n, a_w / n, dr / n)

        hh3 = h2h_stats(3); hh5 = h2h_stats(5)

        rows.append({
            "league": r.league, "date": d, "home": home, "away": away,
            "gh": r.FTHG, "ga": r.FTAG,
            "target": 2 if r.FTHG > r.FTAG else 0 if r.FTHG < r.FTAG else 1,
            "target_ou": 1 if r.FTHG + r.FTAG > 2.5 else 0,   # 大小球2.5二分类(1=大)
            "elo_home": elo_h, "elo_away": elo_a, "elo_diff": elo_diff,
            "att_home": att_home, "def_home": def_home,
            "att_away": att_away, "def_away": def_away,
            "att_home_xg": att_home_xg, "def_home_xg": def_home_xg,
            "att_away_xg": att_away_xg, "def_away_xg": def_away_xg,
            "gf_h5": h5[0] if h5 else league_avg_t * 5, "ga_h5": h5[1] if h5 else league_avg_t * 5,
            "pts_h5": h5[2] if h5 else 7.5,
            "gf_a5": a5[0] if a5 else league_avg_t * 5, "ga_a5": a5[1] if a5 else league_avg_t * 5,
            "pts_a5": a5[2] if a5 else 7.5,
            "gf_home_h5": h5h[0] if h5h else league_avg_h * 5, "ga_home_h5": h5h[1] if h5h else league_avg_a * 5,
            "gf_away_a5": a5a[0] if a5a else league_avg_a * 5, "ga_away_a5": a5a[1] if a5a else league_avg_h * 5,
            "gf_h10": h10[0] if h10 else league_avg_t * 10, "ga_h10": h10[1] if h10 else league_avg_t * 10,
            "pts_h10": h10[2] if h10 else 15.0,
            "gf_a10": a10[0] if a10 else league_avg_t * 10, "ga_a10": a10[1] if a10 else league_avg_t * 10,
            "pts_a10": a10[2] if a10 else 15.0,
            "gf_home_h10": h10h[0] if h10h else league_avg_h * 10,
            "ga_home_h10": h10h[1] if h10h else league_avg_a * 10,
            "gf_away_a10": a10a[0] if a10a else league_avg_a * 10,
            "ga_away_a10": a10a[1] if a10a else league_avg_h * 10,
            "days_home": float(days_h), "days_away": float(days_a),
            "league_avg_home": league_avg_h, "league_avg_away": league_avg_a,
            "league_avg_total": league_avg_t,
            "league_scoring_idx": league_scoring_idx, "league_strength": league_strength,
            "h2h_total_avg": h2h_avg, "h2h_n": float(h2h_n),
            "h2h_total3": hh3[1], "h2h_total5": hh5[1],
            "h2h_n3": float(hh3[0]), "h2h_n5": float(hh5[0]),
            "h2h_h_gf3": hh3[2], "h2h_h_ga3": hh3[3], "h2h_a_gf3": hh3[4], "h2h_a_ga3": hh3[5],
            "h2h_h_gf5": hh5[2], "h2h_h_ga5": hh5[3], "h2h_a_gf5": hh5[4], "h2h_a_ga5": hh5[5],
            "h2h_h_win3": hh3[6], "h2h_a_win3": hh3[7], "h2h_draw3": hh3[8],
            "h2h_h_win5": hh5[6], "h2h_a_win5": hh5[7], "h2h_draw5": hh5[8],
            "home_shots5": home_shots5, "away_shots5": away_shots5,
            "home_st5": home_st5, "away_st5": away_st5,
            "home_corners5": home_corners5, "away_corners5": away_corners5,
            "home_fouls5": home_fouls5, "away_fouls5": away_fouls5,
            "home_gf_sos": home_gf_sos, "home_ga_sos": home_ga_sos,
            "away_gf_sos": away_gf_sos, "away_ga_sos": away_ga_sos,
        })

        # ---------- 赛后更新（供后续比赛使用）----------
        gh, ga = r.FTHG, r.FTAG
        age = 0.0
        if th["last"] is not None:
            age = max((d - th["last"]).days, 0)
        f = math.exp(-lam * age)
        th["gf"] = th["gf"] * f + gh; th["ga"] = th["ga"] * f + ga; th["n"] = th["n"] * f + 1
        th["gf_h"] = th["gf_h"] * f + gh; th["ga_h"] = th["ga_h"] * f + ga; th["n_h"] = th["n_h"] * f + 1
        th["last5"].append((gh, ga)); th["last5_h"].append((gh, ga))
        th["last10"].append((gh, ga)); th["last10_h"].append((gh, ga))

        age = 0.0
        if ta["last"] is not None:
            age = max((d - ta["last"]).days, 0)
        f = math.exp(-lam * age)
        ta["gf"] = ta["gf"] * f + ga; ta["ga"] = ta["ga"] * f + gh; ta["n"] = ta["n"] * f + 1
        ta["gf_a"] = ta["gf_a"] * f + ga; ta["ga_a"] = ta["ga_a"] * f + gh; ta["n_a"] = ta["n_a"] * f + 1
        ta["last5"].append((ga, gh)); ta["last5_a"].append((ga, gh))
        ta["last10"].append((ga, gh)); ta["last10_a"].append((ga, gh))

        # ---- xG 更新（仅当该场有 xG 数据; 无 xG 的场次不推进 xG 状态, 避免污染）----
        if has_xg:
            hxg = getattr(r, "home_xg", None)
            axg = getattr(r, "away_xg", None)
            if hxg is not None and axg is not None and not pd.isna(hxg) and not pd.isna(axg):
                hxg, axg = float(hxg), float(axg)
                age_x = 0.0 if th["xlast"] is None else max((d - th["xlast"]).days, 0)
                fx = math.exp(-lam * age_x)
                th["xgf"] = th["xgf"] * fx + hxg; th["xga"] = th["xga"] * fx + axg; th["xn"] = th["xn"] * fx + 1
                th["xgf_h"] = th["xgf_h"] * fx + hxg; th["xga_h"] = th["xga_h"] * fx + axg; th["xn_h"] = th["xn_h"] * fx + 1
                th["xlast"] = d
                age_x = 0.0 if ta["xlast"] is None else max((d - ta["xlast"]).days, 0)
                fx = math.exp(-lam * age_x)
                ta["xgf"] = ta["xgf"] * fx + axg; ta["xga"] = ta["xga"] * fx + hxg; ta["xn"] = ta["xn"] * fx + 1
                ta["xgf_a"] = ta["xgf_a"] * fx + axg; ta["xga_a"] = ta["xga_a"] * fx + hxg; ta["xn_a"] = ta["xn_a"] * fx + 1
                ta["xlast"] = d
                league_xgh[r.league].append(hxg)
                league_xga[r.league].append(axg)

        # ---- 技术统计更新（仅当该场有统计; 无则不推进, 避免污染）----
        hs = _fnum(getattr(r, "HS", None)); as_ = _fnum(getattr(r, "AS", None))
        if hs is not None:
            th["last5_stats"].append({"shots": hs,
                                      "st": _fnum(getattr(r, "HST", None)),
                                      "corners": _fnum(getattr(r, "HC", None)),
                                      "fouls": _fnum(getattr(r, "HF", None))})
        if as_ is not None:
            ta["last5_stats"].append({"shots": as_,
                                      "st": _fnum(getattr(r, "AST", None)),
                                      "corners": _fnum(getattr(r, "AC", None)),
                                      "fouls": _fnum(getattr(r, "AF", None))})

        # ---- SoS 更新（对手 Elo 用本场赛前快照 elo_a / elo_h）----
        age_s = 0.0 if th["sos_last"] is None else max((d - th["sos_last"]).days, 0)
        fs = math.exp(-lam * age_s)
        th["sos_gf"] = th["sos_gf"] * fs + gh; th["sos_ga"] = th["sos_ga"] * fs + ga
        th["sos_opp_elo"] = th["sos_opp_elo"] * fs + elo_a; th["sos_w"] = th["sos_w"] * fs + 1.0
        th["sos_last"] = d
        age_s = 0.0 if ta["sos_last"] is None else max((d - ta["sos_last"]).days, 0)
        fs = math.exp(-lam * age_s)
        ta["sos_gf"] = ta["sos_gf"] * fs + ga; ta["sos_ga"] = ta["sos_ga"] * fs + gh
        ta["sos_opp_elo"] = ta["sos_opp_elo"] * fs + elo_h; ta["sos_w"] = ta["sos_w"] * fs + 1.0
        ta["sos_last"] = d

        # Elo
        exp_h = 1.0 / (1.0 + 10 ** ((elo_a - (elo_h + hfa)) / 400.0))
        exp_a = 1.0 - exp_h
        s_h = 1.0 if gh > ga else 0.5 if gh == ga else 0.0
        th["elo"] += elo_k * (s_h - exp_h)
        ta["elo"] += elo_k * ((1 - s_h) - exp_a)

        th["last"] = d; ta["last"] = d

        # 联赛 & 交锋
        league_gh[r.league].append(gh)
        league_ga[r.league].append(ga)
        global_gh.append(gh); global_ga.append(ga)
        _le = league_elo[r.league]
        _le["sum"] += elo_h + elo_a; _le["n"] += 2.0
        h2h[pair].append((home, away, gh, ga))

    feat = pd.DataFrame(rows)
    # 赔率透传（供回测定价/结算使用；不进入模型特征）
    odds_cols = [c for c in ALL_ODDS if c in matches.columns]
    if odds_cols:
        feat = pd.concat([feat, matches[odds_cols].reset_index(drop=True)], axis=1)
    return feat


def feature_matrix(feat: pd.DataFrame, extra: list = None) -> pd.DataFrame:
    """XGBoost/LightGBM 用的数值特征矩阵（NaN 用合理值填充）。

    extra: 可选 ["tech", "sos"]，加入旧系统移植的扩展特征（默认关闭，实验开关）。
    """
    cols = [c for c in REQUIRED_FEATURES if c in feat.columns]
    X = feat[cols].copy()
    X["days_home"] = X["days_home"].fillna(7.0)
    X["days_away"] = X["days_away"].fillna(7.0)
    X["h2h_total_avg"] = X["h2h_total_avg"].fillna(X["league_avg_home"] + X["league_avg_away"])
    X["h2h_n"] = X["h2h_n"].fillna(0.0)
    lg_t = X["league_avg_home"] + X["league_avg_away"]
    for c in ("gf_h10", "ga_h10"):
        X[c] = X[c].fillna(lg_t * 10)
    for c in ("gf_a10", "ga_a10"):
        X[c] = X[c].fillna(lg_t * 10)
    X["pts_h10"] = X["pts_h10"].fillna(15.0)
    X["pts_a10"] = X["pts_a10"].fillna(15.0)
    X["gf_home_h10"] = X["gf_home_h10"].fillna(X["league_avg_home"] * 10)
    X["ga_home_h10"] = X["ga_home_h10"].fillna(X["league_avg_away"] * 10)
    X["gf_away_a10"] = X["gf_away_a10"].fillna(X["league_avg_away"] * 10)
    X["ga_away_a10"] = X["ga_away_a10"].fillna(X["league_avg_home"] * 10)
    X["league_scoring_idx"] = X["league_scoring_idx"].fillna(1.0)
    X["league_strength"] = X["league_strength"].fillna(1500.0)
    for c in ("h2h_total3", "h2h_total5"):
        X[c] = X[c].fillna(lg_t)
    for c in ("h2h_n3", "h2h_n5"):
        X[c] = X[c].fillna(0.0)
    for c in ("h2h_h_gf3", "h2h_h_gf5", "h2h_a_ga3", "h2h_a_ga5"):
        X[c] = X[c].fillna(X["league_avg_home"])
    for c in ("h2h_h_ga3", "h2h_h_ga5", "h2h_a_gf3", "h2h_a_gf5"):
        X[c] = X[c].fillna(X["league_avg_away"])
    for c in ("h2h_h_win3", "h2h_a_win3", "h2h_draw3",
              "h2h_h_win5", "h2h_a_win5", "h2h_draw5"):
        X[c] = X[c].fillna(1 / 3)
    extra = list(extra or [])
    for name in extra:
        for c in EXTRA_FEATURES_MAP.get(name, []):
            if c in feat.columns:
                X[c] = feat[c]
    if "tech" in extra:
        for c in EXTRA_FEATURES_MAP["tech"]:
            if c in X.columns:
                X[c] = X[c].fillna(0.0)
    if "sos" in extra:
        for c in ("home_gf_sos", "away_gf_sos"):
            if c in X.columns:
                X[c] = X[c].fillna(X["league_avg_home"])
        for c in ("home_ga_sos", "away_ga_sos"):
            if c in X.columns:
                X[c] = X[c].fillna(X["league_avg_away"])
    return X


def build_league_baselines(matches: pd.DataFrame, feat: pd.DataFrame = None) -> pd.DataFrame:
    """按(联赛, 赛季)统计基准数据：场均进球(主/客/总)、大2.5率、胜平负率、平均Elo强度。

    强弱联赛校正系数：
      - scoring_idx  = 该联赛该赛季场均总进球 / 全部联赛同期场均总进球（进球环境）
      - strength_idx = 该联赛平均Elo / 1500（整体水平）
    season 口径：月份>=7 归当年赛季，否则归上一年（欧洲跨年赛季）。
    """
    df = matches.copy()
    df["season"] = np.where(df["Date"].dt.month >= 7, df["Date"].dt.year,
                            df["Date"].dt.year - 1)
    df["total_g"] = df["FTHG"] + df["FTAG"]
    df["over25"] = (df["total_g"] > 2.5).astype(float)
    df["hw"] = (df["FTHG"] > df["FTAG"]).astype(float)
    df["dr"] = (df["FTHG"] == df["FTAG"]).astype(float)
    df["aw"] = (df["FTHG"] < df["FTAG"]).astype(float)
    if feat is not None and "elo_home" in feat.columns:
        df["elo"] = (feat["elo_home"].values + feat["elo_away"].values) / 2.0
    else:
        df["elo"] = np.nan
    g = df.groupby(["league", "season"], dropna=False)
    out = g.agg(
        n=("FTHG", "size"),
        avg_home_goals=("FTHG", "mean"),
        avg_away_goals=("FTAG", "mean"),
        avg_total_goals=("total_g", "mean"),
        over25_rate=("over25", "mean"),
        home_win_rate=("hw", "mean"),
        draw_rate=("dr", "mean"),
        away_win_rate=("aw", "mean"),
        avg_elo=("elo", "mean"),
    ).reset_index()
    global_avg = df.groupby("season")["total_g"].mean()
    out["global_avg_total"] = out["season"].map(global_avg)
    out["scoring_idx"] = out["avg_total_goals"] / out["global_avg_total"]
    out["strength_idx"] = out["avg_elo"] / 1500.0
    return out
