"""
从 football-data.co.uk 数据构建特征 v3
保留原3/5/10窗口滚动特征 + 新增加: 时间衰减、SoS赛程强度、赛程密度
"""
import pandas as pd
import numpy as np
from pathlib import Path
from src.features.elo import EloRating

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
COL_MAP = {
    "Date": "date", "HomeTeam": "home_team", "AwayTeam": "away_team",
    "FTHG": "home_goals", "FTAG": "away_goals", "FTR": "result",
    "HS": "home_shots", "AS": "away_shots",
    "HST": "home_shots_target", "AST": "away_shots_target",
    "HC": "home_corners", "AC": "away_corners",
    "HF": "home_fouls", "AF": "away_fouls",
    "HY": "home_yellow", "AY": "away_yellow",
    "HR": "home_red", "AR": "away_red",
    "xg_home": "home_xg", "xg_away": "away_xg",
    "AvgH": "odds_home_avg", "AvgD": "odds_draw_avg", "AvgA": "odds_away_avg",
    "B365H": "odds_home", "B365D": "odds_draw", "B365A": "odds_away",
    "PSH": "pinnacle_home", "PSD": "pinnacle_draw", "PSA": "pinnacle_away",
}

RESULT_MAP = {"H": 2, "D": 1, "A": 0}
DECAY_LAMBDA = 0.965


def load_data(path=None):
    if path is None:
        path = DATA_DIR / "raw" / "football_data" / "matches_2015_2025.csv"
    df = pd.read_csv(path, low_memory=False)
    top = ["英超", "西甲", "意甲", "德甲", "法甲"]
    df = df[df["league"].isin(top)].copy()
    print(f"原始: {len(df)} (仅顶级联赛)")
    return df


def build_features(df, rolling_windows=None):
    rolling_windows = rolling_windows or [3, 5, 10]
    rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)
    df["target"] = df["result"].map(RESULT_MAP)
    df = df.dropna(subset=["target"])

    stat_cols = ["home_shots", "away_shots", "home_shots_target", "away_shots_target",
                 "home_corners", "away_corners", "home_fouls", "away_fouls",
                 "home_xg", "away_xg"]
    for col in stat_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    elo = EloRating()
    features = []
    team_history = {}
    team_last_date = {}

    for _, row in df.iterrows():
        home, away = row["home_team"], row["away_team"]
        current_date = row["date"]
        if home not in team_history:
            team_history[home] = []
        if away not in team_history:
            team_history[away] = []
        if home not in team_last_date:
            team_last_date[home] = None
        if away not in team_last_date:
            team_last_date[away] = None

        feat = {
            "fixture_id": row.name, "date": current_date,
            "home_team": home, "away_team": away,
            "home_goals": row.get("home_goals"),
            "away_goals": row.get("away_goals"),
            "target": row["target"],
        }
        feat.update(elo.preview_features(home, away))

        for oc in ["odds_home", "odds_draw", "odds_away", "pinnacle_home", "pinnacle_draw", "pinnacle_away"]:
            if oc in row and pd.notna(row[oc]):
                feat[oc] = row[oc]
        # 去水后的Pinnacle公允概率（作为训练特征）
        if pd.notna(feat.get("pinnacle_home")) and pd.notna(feat.get("pinnacle_draw")) and pd.notna(feat.get("pinnacle_away")):
            pi_h, pi_d, pi_a = 1/feat["pinnacle_home"], 1/feat["pinnacle_draw"], 1/feat["pinnacle_away"]
            pi_total = pi_h + pi_d + pi_a
            if pi_total > 0:
                feat["pinnacle_home_prob"] = round(pi_h / pi_total, 4)
                feat["pinnacle_draw_prob"] = round(pi_d / pi_total, 4)
                feat["pinnacle_away_prob"] = round(pi_a / pi_total, 4)

        # 旧: 等权滚动窗口 (3/5/10)
        for window in rolling_windows:
            h = _rolling(team_history[home], window)
            a = _rolling(team_history[away], window)
            for prefix, s in [("home", h), ("away", a)]:
                for k, v in s.items():
                    feat[f"{prefix}_{k}_w{window}"] = v

        # 新: 时间衰减 + SoS
        h = _rolling_decay(team_history[home], current_date)
        a = _rolling_decay(team_history[away], current_date)
        for prefix, s in [("home", h), ("away", a)]:
            for k, v in s.items():
                feat[f"{prefix}_{k}"] = v

        # 新: 赛程密度
        feat["home_rest_days"] = _rest_days(team_last_date[home], current_date)
        feat["away_rest_days"] = _rest_days(team_last_date[away], current_date)
        feat["home_congestion_7d"] = _congestion(team_history[home], current_date, 7)
        feat["away_congestion_7d"] = _congestion(team_history[away], current_date, 7)
        feat["home_congestion_14d"] = _congestion(team_history[home], current_date, 14)
        feat["away_congestion_14d"] = _congestion(team_history[away], current_date, 14)

        # 更新
        if pd.notna(row.get("home_goals")):
            hg, ag = row["home_goals"], row["away_goals"]
            elo.update(home, away, hg, ag)
            team_history[home].append(_md_v2(row, hg, ag, is_home=True, date=current_date,
                                            opponent_elo=elo.get_rating(away)))
            team_history[away].append(_md_v2(row, ag, hg, is_home=False, date=current_date,
                                            opponent_elo=elo.get_rating(home)))
            team_last_date[home] = current_date
            team_last_date[away] = current_date

        features.append(feat)

    result = pd.DataFrame(features).dropna(subset=["target"])
    print(f"特征矩阵: {len(result)} 行, {len(result.columns)} 列")
    return result


# ---- 旧: 等权滚动窗口 ----

def _rolling(history, window):
    if not history:
        return {k: 0 for k in ["gf", "ga", "win_rate", "form",
                               "gf_home", "gf_away",
                               "shots", "shots_target", "corners", "fouls",
                               "xg", "xga"]}
    r = history[-window:]
    wins = sum(m["result"] == 1 for m in r)
    draws = sum(m["result"] == 0.5 for m in r)
    home = [m for m in r if m.get("is_home")]
    away = [m for m in r if not m.get("is_home")]
    return {
        "gf": np.mean([m["gf"] for m in r]),
        "ga": np.mean([m["ga"] for m in r]),
        "win_rate": (wins + draws * 0.5) / len(r),
        "form": sum(m["result"] for m in r[-5:]) / 5,
        "gf_home": np.mean([m["gf"] for m in home]) if home else 0,
        "gf_away": np.mean([m["gf"] for m in away]) if away else 0,
        "shots": np.mean([m.get("shots", 0) for m in r]),
        "shots_target": np.mean([m.get("shots_target", 0) for m in r]),
        "corners": np.mean([m.get("corners", 0) for m in r]),
        "fouls": np.mean([m.get("fouls", 0) for m in r]),
        "xg": np.mean([m.get("xg", 0) for m in r]),
        "xga": np.mean([m.get("xga", 0) for m in r]),
    }


# ---- 新: 时间衰减 + SoS ----

def _decay_weight(days_ago):
    return DECAY_LAMBDA ** days_ago


def _rolling_decay(history, current_date):
    if not history:
        return {k: 0.0 for k in [
            "gf_decay", "ga_decay", "gd_decay",
            "clean_sheet_rate_decay", "btts_rate_decay",
            "gf_sos", "ga_sos",
            "xg_decay", "xga_decay",
        ]}

    w_total = 0.0
    w_gf = w_ga = 0.0
    w_cs = w_btts = 0.0
    w_opp_elo_gf = w_opp_elo_ga = 0.0
    w_opp_elo_n = 0.0
    w_xg = w_xga = 0.0

    for m in history:
        days = (current_date - m["date"]).days if m["date"] else 365
        w = _decay_weight(max(days, 0))
        w_total += w
        w_gf += m["gf"] * w
        w_ga += m["ga"] * w
        if m["ga"] == 0:
            w_cs += w
        if m["gf"] > 0 and m["ga"] > 0:
            w_btts += w
        opp_elo = m.get("opponent_elo", 1500)
        w_opp_elo_gf += m["gf"] * opp_elo * w
        w_opp_elo_ga += m["ga"] * opp_elo * w
        w_opp_elo_n += opp_elo * w
        w_xg += m.get("xg", 0) * w
        w_xga += m.get("xga", 0) * w

    if w_total == 0:
        return {k: 0.0 for k in [
            "gf_decay", "ga_decay", "gd_decay",
            "clean_sheet_rate_decay", "btts_rate_decay",
            "gf_sos", "ga_sos",
            "xg_decay", "xga_decay",
        ]}

    avg_gf = w_gf / w_total
    avg_ga = w_ga / w_total
    avg_opp_elo = w_opp_elo_n / (w_gf + w_ga + 1e-8) if w_gf + w_ga > 0 else 1500
    sos_factor = avg_opp_elo / 1500.0

    return {
        "gf_decay": round(avg_gf, 4),
        "ga_decay": round(avg_ga, 4),
        "gd_decay": round((w_gf - w_ga) / w_total, 4),
        "clean_sheet_rate_decay": round(w_cs / w_total, 4),
        "btts_rate_decay": round(w_btts / w_total, 4),
        "gf_sos": round(avg_gf * sos_factor, 4),
        "ga_sos": round(avg_ga * (2 - sos_factor), 4),
        "xg_decay": round(w_xg / w_total, 4),
        "xga_decay": round(w_xga / w_total, 4),
    }


def _rest_days(last_date, current_date):
    if last_date is None:
        return 7
    return (current_date - last_date).days


def _congestion(history, current_date, days_back):
    if not history:
        return 0
    cutoff = current_date - pd.Timedelta(days=days_back)
    return sum(1 for m in history if m["date"] and m["date"] >= cutoff)


def _md_v2(row, gf, ga, is_home, date, opponent_elo):
    p = "home" if is_home else "away"
    op = "away" if is_home else "home"
    return {
        "gf": gf, "ga": ga,
        "result": 1 if gf > ga else 0.5 if gf == ga else 0,
        "is_home": is_home,
        "date": date,
        "opponent_elo": opponent_elo,
        "shots": row.get(f"{p}_shots", 0) or 0,
        "shots_target": row.get(f"{p}_shots_target", 0) or 0,
        "corners": row.get(f"{p}_corners", 0) or 0,
        "fouls": row.get(f"{p}_fouls", 0) or 0,
        "xg": row.get(f"{p}_xg", 0) or 0,
        "xga": row.get(f"{op}_xg", 0) or 0,
    }
