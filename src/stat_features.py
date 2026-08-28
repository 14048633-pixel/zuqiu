import os
"""
从 API-Football 获取比赛统计数据（射门、控球率等）
用于构建比单纯进球更稳定的预测特征
"""
import requests
import pandas as pd
import time
from pathlib import Path

API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
BASE = "https://v3.football.api-sports.io"
STATS_CACHE = Path(__file__).resolve().parents[1] / "data" / "stat_cache"
STATS_CACHE.mkdir(parents=True, exist_ok=True)

# 提取哪些统计字段
USEFUL_STATS = [
    "Shots on Goal", "Shots off Goal", "Total Shots",
    "Shots insidebox", "Shots outsidebox",
    "Ball Possession", "Corner Kicks", "Fouls",
    "Yellow Cards", "Red Cards",
    "Goalkeeper Saves", "Total passes", "Passes accurate",
]


def get_fixture_stats(fixture_id):
    """获取单场比赛的完整统计数据"""
    cache_file = STATS_CACHE / f"{fixture_id}.json"
    if cache_file.exists():
        import json
        return json.loads(cache_file.read_text(encoding="utf-8"))

    r = requests.get(
        f"{BASE}/fixtures/statistics?fixture={fixture_id}",
        headers={"x-apisports-key": API_KEY}
    )
    if r.status_code != 200:
        return None
    data = r.json()
    if data.get("results", 0) == 0:
        return None

    result = {}
    for team_stats in data["response"]:
        team = team_stats["team"]["name"]
        stats = {}
        for s in team_stats.get("statistics", []):
            stype = s["type"]
            raw = s.get("value")
            if raw is None or raw == "":
                val = None
            elif isinstance(raw, str) and "%" in raw:
                val = float(raw.replace("%", ""))
            else:
                try:
                    val = int(raw)
                except (ValueError, TypeError):
                    val = None
            stats[stype] = val
        result[team] = stats

    cache_file.write_text(
        __import__("json").dumps(result, ensure_ascii=False), encoding="utf-8"
    )
    time.sleep(0.5)
    return result


def extract_key_stats(fixture_stats, team_name):
    """从统计数据中提取关键指标"""
    if not fixture_stats or team_name not in fixture_stats:
        return {}
    s = fixture_stats[team_name]
    return {
        "shots_on_target": s.get("Shots on Goal"),
        "shots_inside_box": s.get("Shots insidebox"),
        "possession_pct": s.get("Ball Possession"),
        "corners": s.get("Corner Kicks"),
        "total_passes": s.get("Total passes"),
        "pass_accuracy": s.get("Passes accurate"),
    }


def fetch_recent_stats(fixtures_df, max_calls=50):
    """
    批量获取最近 N 场比赛的统计数据
    fixtures_df 需要列: fixture_id, home_team, away_team
    返回: 每个 fixture 的 home/away 统计 dict
    """
    results = {}
    count = 0
    for _, row in fixtures_df.iterrows():
        fid = row["fixture_id"]
        if count >= max_calls:
            break
        stats = get_fixture_stats(fid)
        if stats:
            results[fid] = {
                "home": extract_key_stats(stats, row["home_team"]),
                "away": extract_key_stats(stats, row["away_team"]),
            }
            count += 1
    return results


def build_rolling_stat_features(df, stat_cache):
    """
    将统计缓存整合进特征 DataFrame
    对每个队伍计算滚动平均（最近5场）
    返回: 添加了 stat 特征列的新 DataFrame
    """
    rows = []
    for _, row in df.iterrows():
        fid = row["fixture_id"]
        ht = row["home_team"]
        at = row["away_team"]

        home_stats = stat_cache.get(fid, {}).get("home", {})
        away_stats = stat_cache.get(fid, {}).get("away", {})

        for prefix, stats in [("home", home_stats), ("away", away_stats)]:
            for k, v in stats.items():
                row[f"{prefix}_{k}"] = v
        rows.append(row)

    result = pd.DataFrame(rows)

    # 计算队伍滚动平均 (按日期排序)
    result["date"] = pd.to_datetime(result["date"])
    result = result.sort_values("date").reset_index(drop=True)

    stat_cols = ["shots_on_target", "shots_inside_box", "possession_pct",
                 "corners", "total_passes"]
    for team_type in ["home", "away"]:
        team_col = f"{team_type}_team"
        for stat in stat_cols:
            col = f"{team_type}_{stat}"
            if col not in result.columns:
                result[col] = None
            # 按队伍分组滚动平均
            result[f"{col}_avg5"] = result.groupby(team_col)[col].transform(
                lambda s: s.rolling(5, min_periods=1).mean()
            )
            result[f"{col}_avg5"] = result[f"{col}_avg5"].shift(1)
            result[f"{col}_avg3"] = result.groupby(team_col)[col].transform(
                lambda s: s.rolling(3, min_periods=1).mean()
            )
            result[f"{col}_avg3"] = result[f"{col}_avg3"].shift(1)

    return result
