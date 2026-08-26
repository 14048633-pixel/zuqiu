import numpy as np


LEAGUE_WEIGHTS = {
    39: 32,   # 英超
    140: 30,  # 西甲
    135: 30,  # 意甲
    78: 30,   # 德甲
    61: 30,   # 法甲
    2: 35,    # 欧冠
    3: 25,    # 欧联
}


class EloRating:
    def __init__(self, initial_rating=1500, k_factor=32, home_advantage=100):
        self.ratings = {}
        self.initial_rating = initial_rating
        self.k_factor = k_factor
        self.home_advantage = home_advantage

    def get_rating(self, team):
        return self.ratings.get(team, self.initial_rating)

    def expected_score(self, rating_a, rating_b):
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def goal_diff_multiplier(self, goal_diff):
        if goal_diff <= 1:
            return 1.0
        elif goal_diff == 2:
            return 1.5
        elif goal_diff == 3:
            return 1.75
        else:
            return 2.0

    def preview_features(self, home_team, away_team):
        home_elo = self.get_rating(home_team)
        away_elo = self.get_rating(away_team)
        home_expected = self.expected_score(home_elo + self.home_advantage, away_elo)
        return {
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff": home_elo - away_elo,
            "elo_home_win_prob": round(home_expected, 4),
        }

    def update(self, home_team, away_team, home_goals, away_goals, league_id=None):
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        home_elo = home_rating + self.home_advantage
        home_expected = self.expected_score(home_elo, away_rating)
        away_expected = 1 - home_expected

        if home_goals > away_goals:
            home_actual, away_actual = 1.0, 0.0
        elif home_goals < away_goals:
            home_actual, away_actual = 0.0, 1.0
        else:
            home_actual, away_actual = 0.5, 0.5

        gd_mult = self.goal_diff_multiplier(abs(home_goals - away_goals))
        k = LEAGUE_WEIGHTS.get(league_id, self.k_factor) * gd_mult

        self.ratings[home_team] = home_rating + k * (home_actual - home_expected)
        self.ratings[away_team] = away_rating + k * (away_actual - away_expected)
