"""单场预测 API —— CLI 与旧系统桥接共用。

- feature_row_from_dataset: 从 football-data 数据集构建该场特征（只用该场开赛前数据）
- score_feature_row: 给特征行评分（泊松 λ/1X2/大小球/亚盘概率）+ 市场对比(EV/凯利)
"""
import os

import pandas as pd

from .data_loader import load_football_data_xg
from .features import build_features
from .models import PoissonGoalModel
from .markets import devig, devig2, p_ou_quarter, p_ah_quarter, ev, kelly_fraction

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_cache = {"df": None, "max_date": None, "xg": None}


def _load_cfg(cfg_path=None):
    import yaml
    path = cfg_path or os.path.join(HERE, "config.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def feature_row_from_dataset(league: str, home: str, away: str, date_str: str,
                             cfg: dict = None):
    """用数据集历史构建该场特征（严格只含开赛前数据）。"""
    cfg = cfg or _load_cfg()
    data_dir = os.path.normpath(os.path.join(HERE, cfg["data"]["football_dir"]))
    xg_cache = os.path.normpath(os.path.join(HERE, cfg["data"].get("xg_cache", "xg_cache.csv")))
    if _cache["df"] is None or _cache["max_date"] != date_str or _cache["xg"] != xg_cache:
        df = load_football_data_xg(data_dir, xg_cache=xg_cache, max_date=date_str)
        _cache["df"], _cache["max_date"], _cache["xg"] = df, date_str, xg_cache
    else:
        df = _cache["df"]
    row = {"Date": pd.Timestamp(date_str), "HomeTeam": home, "AwayTeam": away,
           "FTHG": 0, "FTAG": 0, "Div": "", "league": league}
    for c in df.columns:
        row.setdefault(c, None)
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    feat = build_features(df, cfg["features"])
    return feat.iloc[-1]


def score_feature_row(row, odds=None, ou_line=2.5, ou=None, ah=None,
                      cfg: dict = None) -> dict:
    """对特征行评分并输出市场对比。返回 dict：
      lam_h/lam_a/p_home/p_draw/p_away/p_over + bets 列表(含 EV/凯利)
    """
    cfg = cfg or _load_cfg()
    model = PoissonGoalModel(max_goals=cfg["features"]["max_goals"],
                             xg_blend=cfg.get("model", {}).get("xg_blend", 0.0))
    pred = model.predict(row)
    M = pred["M"]
    out = {
        "lam_h": round(pred["lam_h"], 3), "lam_a": round(pred["lam_a"], 3),
        "p_home": pred["p_home"], "p_draw": pred["p_draw"], "p_away": pred["p_away"],
        "p_over": p_ou_quarter(M, ou_line), "ou_line": ou_line,
        "pre": {
            "league": row.get("league"),
            "league_avg_home": _num(row.get("league_avg_home"), 1.35),
            "league_avg_away": _num(row.get("league_avg_away"), 1.15),
            "league_scoring_idx": _num(row.get("league_scoring_idx"), 1.0),
            "league_strength": _num(row.get("league_strength"), 1500.0),
            "form_home": {
                "gf10": _num(row.get("gf_h10")), "ga10": _num(row.get("ga_h10")),
                "pts10": _num(row.get("pts_h10")),
                "gf_home10": _num(row.get("gf_home_h10")), "ga_home10": _num(row.get("ga_home_h10")),
            },
            "form_away": {
                "gf10": _num(row.get("gf_a10")), "ga10": _num(row.get("ga_a10")),
                "pts10": _num(row.get("pts_a10")),
                "gf_away10": _num(row.get("gf_away_a10")), "ga_away10": _num(row.get("ga_away_a10")),
            },
            "h2h": {
                "n3": int(row.get("h2h_n3") or 0), "n5": int(row.get("h2h_n5") or 0),
                "total3": _num(row.get("h2h_total3")), "total5": _num(row.get("h2h_total5")),
                "h_win3": _num(row.get("h2h_h_win3"), 1 / 3),
                "a_win3": _num(row.get("h2h_a_win3"), 1 / 3),
                "draw3": _num(row.get("h2h_draw3"), 1 / 3),
                "h_win5": _num(row.get("h2h_h_win5"), 1 / 3),
                "a_win5": _num(row.get("h2h_a_win5"), 1 / 3),
                "draw5": _num(row.get("h2h_draw5"), 1 / 3),
            },
        },
        "bets": [],
    }
    frac = cfg["markets"]["kelly_fraction"]
    cap = cfg["markets"]["kelly_cap"]

    if odds:
        oh, od, oa = odds
        mh, md, ma = devig(oh, od, oa)
        out["market_1x2"] = {"m_home": mh, "m_draw": md, "m_away": ma}
        for name, p, m, o in [("home", pred["p_home"], mh, oh),
                              ("draw", pred["p_draw"], md, od),
                              ("away", pred["p_away"], ma, oa)]:
            out["bets"].append(_bet("1x2", name, p, m, o, frac, cap))

    if ou:
        o_over, o_under = ou
        if o_over and o_under:
            m_over, m_under = devig2(o_over, o_under)
            p_over, p_under = out["p_over"], 1 - out["p_over"]
            out["market_ou"] = {"m_over": m_over, "m_under": m_under}
            for name, p, m, o in [("over", p_over, m_over, o_over),
                                  ("under", p_under, m_under, o_under)]:
                out["bets"].append(_bet("ou", f"{name}{ou_line}", p, m, o, frac, cap))

    if ah:
        line, ah_h, ah_a = ah
        if ah_h and ah_a:
            p_h = p_ah_quarter(M, line)
            m_h, m_a = devig2(ah_h, ah_a)
            out["market_ah"] = {"m_home": m_h, "m_away": m_a}
            for name, p, m, o in [(f"home{line:+.2f}", p_h, m_h, ah_h),
                                  (f"away{line:+.2f}", 1 - p_h, m_a, ah_a)]:
                out["bets"].append(_bet("ah", name, p, m, o, frac, cap))

    return out


def _num(v, default=None):
    try:
        if v is None or (isinstance(v, float) and v != v):
            return default
        return round(float(v), 3)
    except (TypeError, ValueError):
        return default


def _bet(market, side, prob, market_prob, odds, frac, cap):
    return {
        "market": market, "side": side,
        "prob": round(prob, 4), "market_prob": round(market_prob, 4),
        "edge": round(prob - market_prob, 4), "odds": round(odds, 3),
        "ev": round(ev(prob, odds), 4),
        "kelly": round(kelly_fraction(prob, odds, frac, cap), 4),
    }
