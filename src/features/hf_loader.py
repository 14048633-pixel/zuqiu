"""
Load data from HuggingFace parquet files and normalize to fd_builder format.
Supports target leagues by name and produces a DataFrame compatible with build_features().
"""
import pandas as pd
import numpy as np
from pathlib import Path

XG_DIR = Path(__file__).resolve().parents[2] / "data" / "xg"

HF_RENAME = {
    "home_team_name": "HomeTeam",
    "away_team_name": "AwayTeam",
    "date": "Date",
    "home_shots_total": "HS",
    "away_shots_total": "AS",
    "home_shots_on_goal": "HST",
    "away_shots_on_goal": "AST",
    "home_corners": "HC",
    "away_corners": "AC",
    "home_fouls": "HF",
    "away_fouls": "AF",
    "home_yellow_cards": "HY",
    "away_yellow_cards": "AY",
    "home_red_cards": "HR",
    "away_red_cards": "AR",
    "home_xg": "xg_home",
    "away_xg": "xg_away",
}

RESULT_MAP = {"H": 2, "D": 1, "A": 0}


def load_hf_data():
    """Load all parquet files."""
    return {
        "fixtures": pd.read_parquet(XG_DIR / "fixtures.parquet"),
        "match_stats": pd.read_parquet(XG_DIR / "match_stats.parquet"),
        "odds": pd.read_parquet(XG_DIR / "odds.parquet"),
        "teams": pd.read_parquet(XG_DIR / "teams.parquet"),
        "leagues": pd.read_parquet(XG_DIR / "leagues.parquet"),
    }


def get_league_ids(data, league_names):
    """Get league IDs from league names."""
    lf = data["leagues"]
    ids = []
    for name in league_names:
        match = lf[lf["name"].str.contains(name, case=False, na=False)]
        if len(match) > 0:
            ids.append(match["id"].iloc[0])
            print(f"  {name}: league_id={match['id'].iloc[0]} (fd_code={match['fd_code'].iloc[0]})")
        else:
            print(f"  {name}: NOT FOUND")
    return ids


def normalize(data, league_ids):
    """
    Normalize HuggingFace data to fd_builder-compatible format.
    Returns a DataFrame with fd_builder column names.
    """
    fx = data["fixtures"]
    ms = data["match_stats"]
    od = data["odds"]
    teams = data["teams"]

    # Filter fixtures to target leagues
    fx_sub = fx[fx["league_id"].isin(league_ids)].copy()
    print(f"  Fixtures in target leagues: {len(fx_sub)}")

    # Get played matches
    fx_played = fx_sub[fx_sub["is_played"]].copy()
    print(f"  Played matches: {len(fx_played)}")

    # Add team names
    team_id_to_name = dict(zip(teams["id"], teams["name"]))
    fx_played["home_team_name"] = fx_played["home_team_id"].map(team_id_to_name)
    fx_played["away_team_name"] = fx_played["away_team_id"].map(team_id_to_name)
    # Format date as DD/MM/YYYY for fd_builder compatibility
    fx_played["date"] = pd.to_datetime(fx_played["date_utc"]).dt.strftime("%d/%m/%Y")

    # Merge match stats
    fx_with_ms = fx_played.merge(
        ms[["fixture_id", "home_shots_total", "away_shots_total",
            "home_shots_on_goal", "away_shots_on_goal",
            "home_corners", "away_corners",
            "home_fouls", "away_fouls",
            "home_yellow_cards", "away_yellow_cards",
            "home_red_cards", "away_red_cards",
            "home_possession", "away_possession",
            "home_xg", "away_xg"]],
        left_on="id", right_on="fixture_id", how="left"
    )

    # Merge Pinnacle odds
    pinnacle = od[od["bookmaker"] == "Pinnacle"].copy()
    fx_with_odds = fx_with_ms.merge(
        pinnacle[["fixture_id", "home_win", "draw", "away_win"]],
        left_on="id", right_on="fixture_id", how="left", suffixes=("", "_odds")
    )

    # Build result column
    def result_label(h, a):
        if pd.isna(h) or pd.isna(a):
            return None
        if h > a:
            return "H"
        elif h < a:
            return "A"
        return "D"

    fx_with_odds["result"] = fx_with_odds.apply(
        lambda r: result_label(r["goals_home"], r["goals_away"]), axis=1
    )

    # Rename columns to fd_builder format
    first_rename = {
        "home_win": "PSH",
        "draw": "PSD",
        "away_win": "PSA",
        "goals_home": "FTHG",
        "goals_away": "FTAG",
        "result": "FTR",
    }
    result = fx_with_odds.rename(columns=first_rename)

    # Apply HF_RENAME for stat columns
    cols_to_rename = {k: v for k, v in HF_RENAME.items() if k in result.columns}
    result = result.rename(columns=cols_to_rename)

    # Add required fd_builder columns
    result["Div"] = result["league_id"].astype(str)
    result["season"] = result["calendar_year"].astype(str)

    # Drop unnecessary columns
    keep_cols = list(HF_RENAME.values()) + ["FTHG", "FTAG", "FTR", "PSH", "PSD", "PSA", "Div", "season"]
    keep_cols = [c for c in keep_cols if c in result.columns]
    keep_cols = list(dict.fromkeys(keep_cols))  # deduplicate while preserving order
    result = result[keep_cols]

    return result


def load_and_normalize(league_names, save_csv=None):
    """
    Full pipeline: load HF data, filter to league_names, normalize to fd_builder format.
    If save_csv is provided, saves the result to that path.
    """
    print("Loading HuggingFace data...")
    data = load_hf_data()

    print(f"\nGetting league IDs for: {league_names}")
    league_ids = get_league_ids(data, league_names)

    print(f"\nNormalizing data...")
    df = normalize(data, league_ids)
    print(f"  Result: {len(df)} rows, {len(df.columns)} cols")
    print(f"  Columns: {list(df.columns)}")

    if save_csv:
        df.to_csv(save_csv, index=False)
        print(f"  Saved to: {save_csv}")

    return df


if __name__ == "__main__":
    leagues = ["Eredivisie", "Primeira Liga", "Jupiler Pro League",
               "Championship", "Superliga"]
    out_path = Path(__file__).resolve().parents[2] / "data" / "raw" / "football_data" / "hf_new_leagues.csv"
    df = load_and_normalize(leagues, out_path)
