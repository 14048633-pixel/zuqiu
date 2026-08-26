import pandas as pd
import numpy as np
from pathlib import Path
from src.features.elo import EloRating

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class FeatureBuilder:
    def __init__(self, rolling_windows=None, include_h2h=True, include_odds=True,
                 elo_config=None, stat_cache=None):
        self.rolling_windows = rolling_windows or [3, 5, 10]
        self.include_h2h = include_h2h
        self.include_odds = include_odds
        self.elo = EloRating(**(elo_config or {}))
        self.stat_cache = stat_cache or {}

    def build_team_features(self, fixtures_df):
        df = fixtures_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        all_teams = pd.unique(df[["home_team", "away_team"]].values.ravel())
        team_stats = {team: pd.DataFrame() for team in all_teams}

        records = []
        for _, row in df.iterrows():
            home, away = row["home_team"], row["away_team"]
            home_stats = self._get_recent_stats(team_stats[home], home)
            away_stats = self._get_recent_stats(team_stats[away], away)

            if home_goals := row.get("home_goals") is not None:
                home_goals = row["home_goals"]
                away_goals = row["away_goals"]
                winner = (1 if home_goals > away_goals
                          else -1 if home_goals < away_goals else 0)
                self._update_team_stats(team_stats[home], row, home_goals, away_goals, winner, is_home=True)
                self._update_team_stats(team_stats[away], row, away_goals, home_goals, -winner, is_home=False)

        return df

    def _get_recent_stats(self, history_df, team_name):
        if history_df.empty:
            return {
                "avg_goals_for": 0, "avg_goals_against": 0,
                "win_rate": 0, "form": 0,
                "avg_goals_for_home": 0, "avg_goals_against_home": 0,
                "avg_goals_for_away": 0, "avg_goals_against_away": 0,
            }

        recent = history_df.tail(10)
        gf = recent["goals_for"].mean()
        ga = recent["goals_against"].mean()
        win_rate = (recent["result"] == 1).mean()
        form = recent.tail(5)["result"].mean()

        home = recent[recent["is_home"] == True]
        away = recent[recent["is_home"] == False]
        gf_h = home["goals_for"].mean() if not home.empty else 0
        ga_h = home["goals_against"].mean() if not home.empty else 0
        gf_a = away["goals_for"].mean() if not away.empty else 0
        ga_a = away["goals_against"].mean() if not away.empty else 0

        return {
            "avg_goals_for": gf, "avg_goals_against": ga,
            "win_rate": win_rate, "form": form,
            "avg_goals_for_home": gf_h, "avg_goals_against_home": ga_h,
            "avg_goals_for_away": gf_a, "avg_goals_against_away": ga_a,
            "recent_games": len(recent),
        }

    def _update_team_stats(self, stats_dict, match, gf, ga, result, is_home):
        new_row = {
            "date": match["date"],
            "goals_for": gf,
            "goals_against": ga,
            "result": result,
            "is_home": is_home,
        }
        if isinstance(stats_dict, dict):
            stats_dict["_buffer"] = stats_dict.get("_buffer", []) + [new_row]
        else:
            stats_dict.loc[len(stats_dict)] = new_row

    def create_match_features(self, fixtures_df):
        df = fixtures_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        features = []
        team_history = {}

        for _, row in df.iterrows():
            home, away = row["home_team"], row["away_team"]
            if home not in team_history:
                team_history[home] = []
            if away not in team_history:
                team_history[away] = []

            feat = {
                "fixture_id": row["fixture_id"],
                "date": row["date"],
                "home_team": home,
                "away_team": away,
                "home_goals": row.get("home_goals"),
                "away_goals": row.get("away_goals"),
                "league_id": row.get("league_id"),
                "round": row.get("round"),
            }

            elo_feats = self.elo.preview_features(home, away)
            feat.update(elo_feats)

            for window in self.rolling_windows:
                home_stats = self._rolling_stats(team_history[home], window)
                away_stats = self._rolling_stats(team_history[away], window)
                for prefix, stats in [("home", home_stats), ("away", away_stats)]:
                    for k, v in stats.items():
                        feat[f"{prefix}_{k}_w{window}"] = v

            if row["home_goals"] is not None:
                self.elo.update(home, away, row["home_goals"], row["away_goals"],
                                league_id=row.get("league_id"))
                # 获取统计数据
                fid = row["fixture_id"]
                home_stats = {}
                away_stats = {}
                if fid in self.stat_cache:
                    home_stats = self.stat_cache[fid].get("home", {})
                    away_stats = self.stat_cache[fid].get("away", {})

                self._append_match(team_history[home], row, row["home_goals"],
                                   row["away_goals"], 1, is_home=True,
                                   stats=home_stats)
                self._append_match(team_history[away], row, row["away_goals"],
                                   row["home_goals"], -1, is_home=False,
                                   stats=away_stats)

            features.append(feat)

        return pd.DataFrame(features)

    def _rolling_stats(self, history, window):
        if len(history) == 0:
            return {
                "gf": 0, "ga": 0, "win_rate": 0, "form": 0,
                "gf_home": 0, "ga_home": 0, "gf_away": 0, "ga_away": 0,
                "games": 0,
            }
        recent = history[-window:]
        gf = np.mean([m["gf"] for m in recent])
        ga = np.mean([m["ga"] for m in recent])
        wins = sum(1 for m in recent if m["result"] == 1)
        win_rate = wins / len(recent)
        recent_home = [m for m in recent if m["is_home"]]
        recent_away = [m for m in recent if not m["is_home"]]

        feat = {
            "gf": gf, "ga": ga, "win_rate": win_rate, "form": wins / max(len(recent), 1),
            "gf_home": np.mean([m["gf"] for m in recent_home]) if recent_home else 0,
            "ga_home": np.mean([m["ga"] for m in recent_home]) if recent_home else 0,
            "gf_away": np.mean([m["gf"] for m in recent_away]) if recent_away else 0,
            "ga_away": np.mean([m["ga"] for m in recent_away]) if recent_away else 0,
            "games": len(recent),
        }

        # 统计特征滚动平均(射门、控球率等)
        stat_keys = ["shots_on_target", "shots_inside_box", "possession_pct",
                     "corners", "total_passes"]
        for sk in stat_keys:
            vals = [m.get(sk) for m in recent if m.get(sk) is not None]
            feat[sk] = np.mean(vals) if vals else 0

        return feat

    def _append_match(self, history, row, gf, ga, result, is_home, stats=None):
        match = {
            "gf": gf, "ga": ga, "result": result,
            "is_home": is_home,
            "date": row["date"],
        }
        if stats:
            match.update(stats)
        history.append(match)
