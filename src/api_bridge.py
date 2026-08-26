"""
Flask 前端桥接 — 融合引擎 (XGBoost + Dixon-Coles + Elo)
"""
import sys, os, difflib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES_PATH = os.path.join(ROOT, "data", "processed", "matches_with_features.csv")

_fusion = None
_team_cache = {}

_ALIAS_MAP = {
    "manchester city": "Man City", "man city": "Man City",
    "manchester united": "Man United", "man utd": "Man United", "man united": "Man United",
    "tottenham": "Tottenham", "spurs": "Tottenham",
    "real madrid": "Real Madrid", "real": "Real Madrid",
    "barcelona": "Barcelona", "barca": "Barcelona",
    "atletico madrid": "Atletico Madrid", "atletico": "Atletico Madrid",
    "bayern munich": "Bayern Munich", "bayern": "Bayern Munich",
    "borussia dortmund": "Dortmund", "dortmund": "Dortmund",
    "inter milan": "Inter", "inter": "Inter",
    "ac milan": "Milan", "milan": "Milan",
    "juventus": "Juventus", "juve": "Juventus",
    "paris sg": "Paris SG", "paris saint-germain": "Paris SG", "psg": "Paris SG",
    "leicester": "Leicester", "newcastle": "Newcastle",
    "west ham": "West Ham", "wolves": "Wolves",
    "brighton": "Brighton", "crystal palace": "Crystal Palace",
    "aston villa": "Aston Villa", "everton": "Everton",
    "fulham": "Fulham", "brentford": "Brentford",
    "nottingham forest": "Nott'm Forest", "nott'm forest": "Nott'm Forest",
    "southampton": "Southampton", "bournemouth": "Bournemouth",
    "ipswich": "Ipswich",
}


def _resolve(name):
    if name in _team_cache:
        return name
    lower = name.lower()
    if lower in _ALIAS_MAP:
        return _ALIAS_MAP[lower]
    matches = difflib.get_close_matches(name, _team_cache.keys(), n=1, cutoff=0.6)
    return matches[0] if matches else name


def _init():
    global _fusion, _team_cache
    if _fusion is not None:
        return
    from src.models.fusion import FusionEngine
    _fusion = FusionEngine()
    _fusion.load()
    # 缓存XGBoost已知球队
    df = pd.read_csv(FEATURES_PATH, low_memory=False)
    fn = _fusion._trainer.feature_names if hasattr(_fusion, "_trainer") else []
    for team in pd.unique(pd.concat([df["home_team"], df["away_team"]])):
        home_rows = df[df["home_team"] == team].sort_values("date").tail(10)
        away_rows = df[df["away_team"] == team].sort_values("date").tail(10)
        profile = {}
        for c in fn:
            if c.startswith("home_") or c.startswith("elo_"):
                vals = home_rows[c].dropna().tail(5).values if c in home_rows.columns else []
            elif c.startswith("away_"):
                vals = away_rows[c].dropna().tail(5).values if c in away_rows.columns else []
            else:
                vals = []
            profile[c] = float(np.mean(vals)) if len(vals) > 0 else 0.0
        _team_cache[team] = profile
    _fusion._team_cache = _team_cache


def predict_match(home_team, away_team, league="", home_odds=None, draw_odds=None, away_odds=None):
    """融合预测: 返回所有模型 + 融合结果"""
    _init()

    home_key = _resolve(home_team)
    away_key = _resolve(away_team)
    use_model = home_key in _team_cache and away_key in _team_cache

    if use_model:
        r = _fusion.predict_fused(home_key, away_key)
        if r:
            f = r["fusion"]
            label = "主胜" if f[0] > max(f[1], f[2]) else ("平局" if f[1] > f[2] else "客胜")
            result = {
                "home_team": home_team, "away_team": away_team,
                "prediction": label,
                "confidence": round(max(f), 4),
                "probabilities": {"home": round(f[0], 4), "draw": round(f[1], 4), "away": round(f[2], 4)},
                "odds_implied": {
                    "home": round(1 / f[0], 2) if f[0] > 0 else 999,
                    "draw": round(1 / f[1], 2) if f[1] > 0 else 999,
                    "away": round(1 / f[2], 2) if f[2] > 0 else 999,
                },
                "models": r["detail"],
                "source": "fusion",
            }
            # 大小球 (DC)
            ou = _fusion.predict_over_under(home_key, away_key)
            if "dc" in ou:
                po, pu = ou["dc"]
                result["over_under"] = {
                    "prob_over": round(po, 4), "prob_under": round(pu, 4),
                    "prediction": "大2.5" if po > 0.5 else "小2.5",
                    "confidence": round(max(po, pu), 4),
                }
            return result

    # Fallback: 低级别联赛分析器 v2（时间衰减+贝叶斯收缩+主客拆分）
    try:
        from src.low_league import analyze_match
        ll = analyze_match(home_team, away_team)
        probs = ll.get("probabilities")
        home_s = ll.get("home_stats")
        if probs and home_s and home_s.get("matches_raw", 0) >= 2:
            label = "主胜" if probs["home"] > max(probs.get("draw", 0), probs.get("away", 0)) else ("平局" if probs.get("draw", 0) > probs.get("away", 0) else "客胜")
            return {
                "home_team": home_team, "away_team": away_team,
                "prediction": label, "confidence": round(max(probs.values()), 4),
                "probabilities": {k: round(v, 4) for k, v in probs.items()},
                "odds_implied": {k: round(1 / v, 2) if v > 0 else 999 for k, v in probs.items()},
                "source": ll.get("source", "low_league_v2"),
                "data_quality": ll.get("data_quality", "unknown"),
                "home_stats": home_s,
                "away_stats": ll.get("away_stats"),
            }
    except Exception as e:
        print(f"[api_bridge] low_league fallback error: {e}", file=__import__('sys').stderr)

    # Fallback: 赔率估值
    if home_odds and draw_odds and away_odds:
        p = {"home": 1 / home_odds, "draw": 1 / draw_odds, "away": 1 / away_odds}
        t = sum(p.values())
        probs = {k: v / t for k, v in p.items()}
        label = "主胜" if probs["home"] > max(probs["draw"], probs["away"]) else ("平局" if probs["draw"] > probs["away"] else "客胜")
    else:
        probs = {"home": 0.45, "draw": 0.25, "away": 0.30}
        label = "主胜"
    return {
        "home_team": home_team, "away_team": away_team,
        "prediction": label, "confidence": round(max(probs.values()), 4),
        "probabilities": probs,
        "odds_implied": {"home": round(1 / probs["home"], 2), "draw": round(1 / probs["draw"], 2), "away": round(1 / probs["away"], 2)},
        "source": "odds" if (home_odds and draw_odds and away_odds) else "prior",
    }
