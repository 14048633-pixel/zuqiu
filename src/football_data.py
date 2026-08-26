"""
Football-data.co.uk 爬虫
免费、无Cloudflare、含射门/角球/赔率数据
"""
import pandas as pd
import time
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "football_data"
RAW_DIR.mkdir(parents=True, exist_ok=True)

LEAGUES = {
    "E0": "英超", "E1": "英冠",
    "SP1": "西甲", "SP2": "西乙",
    "I1": "意甲",
    "D1": "德甲", "D2": "德乙",
    "F1": "法甲",
    "N1": "荷甲",
}

COL_MAP = {
    "Date": "date",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": "result",  # H/A/D
    "HS": "home_shots",
    "AS": "away_shots",
    "HST": "home_shots_on_target",
    "AST": "away_shots_on_target",
    "HF": "home_fouls",
    "AF": "away_fouls",
    "HC": "home_corners",
    "AC": "away_corners",
    "HY": "home_yellow",
    "AY": "away_yellow",
    "HR": "home_red",
    "AR": "away_red",
    "AvgH": "odds_home",
    "AvgD": "odds_draw",
    "AvgA": "odds_away",
}


def fetch_season(league_code, season_code):
    """
    获取一个联赛一个赛季的数据
    season_code 格式: 2324 (表示 2023-2024)
    """
    url = f"https://www.football-data.co.uk/mmz4281/{season_code}/{league_code}.csv"
    try:
        df = pd.read_csv(url)
        df["league"] = LEAGUES.get(league_code, league_code)
        df["season"] = f"20{season_code[:2]}/20{season_code[2:]}"
        print(f"  {LEAGUES.get(league_code, league_code)} {season_code}: {len(df)} 场")
        return df
    except Exception as e:
        print(f"  获取失败 {league_code} {season_code}: {e}")
        return None


def fetch_all_leagues(start_season=2020, end_season=2024):
    """
    批量获取多赛季数据
    start_season~end_season 包含
    """
    all_dfs = []
    for season in range(start_season, end_season + 1):
        sc = f"{str(season)[2:]}{str(season+1)[2:]}"
        print(f"\n赛季 {season}/{season+1}:")
        for league in LEAGUES:
            df = fetch_season(league, sc)
            if df is not None:
                all_dfs.append(df)
            time.sleep(0.3)

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        path = RAW_DIR / f"matches_{start_season}_{end_season}.csv"
        combined.to_csv(path, index=False)
        print(f"\n合并 {len(combined)} 场, 已保存至 {path}")
        return combined
    return None


def normalize_columns(df):
    """重命名并清洗列"""
    rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    return df


def build_features_from_football_data(df):
    """将 football-data 转换为特征格式"""
    df = normalize_columns(df)

    # 结果编码: H=2(主胜), D=1(平), A=0(客胜)
    result_map = {"H": 2, "D": 1, "A": 0}
    df["target"] = df["result"].map(result_map)

    # 清理
    for col in ["home_shots", "away_shots", "home_shots_on_target",
                "away_shots_on_target", "home_corners", "away_corners",
                "home_fouls", "away_fouls"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df
