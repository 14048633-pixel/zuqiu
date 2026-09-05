# -*- coding: utf-8 -*-
"""特征工程：严格时间截断的滚动特征。

所有特征只使用 date 严格早于当前比赛的记录(防未来信息泄露)。
球队画像按 (league, team) 复合键构建，避免跨联赛混淆(旧系统缺陷)。
"""
from __future__ import annotations

from bisect import bisect_left

import numpy as np
import pandas as pd

from elo import compute_elo_history
from config import FEATURES


class TeamHistory:
    """单队事件日志，按日期有序，支持截断查询。"""

    def __init__(self):
        self.dates: list = []
        self.recs: list = []

    def add(self, date, rec):
        self.dates.append(date)
        self.recs.append(rec)

    def before(self, date, window=None):
        idx = bisect_left(self.dates, date)
        recs = self.recs[:idx]
        if window is not None and len(recs) > window:
            recs = recs[-window:]
        return recs


class FeatureState:
    """可复用的特征状态：在时间线上增量构建，可对任意未来日期计算特征。"""

    def __init__(self):
        self.hist: dict = {}
        self.h2h: dict = {}
        self.league_goals: dict = {}
        self.elo = None

    def observe(self, r):
        """吸收一场已赛比赛(需按时间升序调用)。"""
        date, league = r["date"], r["league"]
        home, away = r["home"], r["away"]
        hg, ag = r["hg"], r["ag"]
        key_h = (league, home)
        key_a = (league, away)
        w_pts = 3.0 if hg > ag else (1.0 if hg == ag else 0.0)
        l_pts = 3.0 if ag > hg else (1.0 if hg == ag else 0.0)
        self.hist.setdefault(key_h, TeamHistory()).add(date,
            (date, w_pts, hg, ag, r.get("home_shots"), r.get("away_shots"),
             r.get("home_sot"), r.get("home_corners"), "H"))
        self.hist.setdefault(key_a, TeamHistory()).add(date,
            (date, l_pts, ag, hg, r.get("away_shots"), r.get("home_shots"),
             r.get("away_sot"), r.get("away_corners"), "A"))
        h2h_key = tuple(sorted([key_h, key_a]))
        self.h2h.setdefault(h2h_key, TeamHistory()).add(date, (date, key_h, key_a, hg, ag))
        self.league_goals.setdefault(league, []).append(hg + ag)

    def features_for(self, date, league, home, away) -> dict:
        """对 (date, league, home, away) 计算赛前特征(只用严格早于 date 的数据)。"""
        key_h = (league, home)
        key_a = (league, away)
        h_recs = self.hist.get(key_h, TeamHistory()).before(date, FEATURES["form_window"])
        a_recs = self.hist.get(key_a, TeamHistory()).before(date, FEATURES["form_window"])

        def _form_pts(recs):
            if not recs:
                return np.nan
            w = [1.0 / (i + 1) for i in range(len(recs))]
            return float(np.average([x[1] for x in recs], weights=w))

        def _avg(recs, idx):
            if not recs:
                return np.nan
            w = [1.0 / (i + 1) for i in range(len(recs))]
            return float(np.average([x[idx] for x in recs], weights=w))

        # 样本不足门槛: 少于 min_matches 场的球队, 画像特征视为不可靠(NaN)
        min_n = FEATURES["min_matches"]
        valid_h = len(h_recs) >= min_n
        valid_a = len(a_recs) >= min_n
        h_home = [x for x in h_recs if x[8] == "H"]
        a_away = [x for x in a_recs if x[8] == "A"]

        h2h_key = tuple(sorted([key_h, key_a]))
        meetings = self.h2h.get(h2h_key, TeamHistory()).before(date, FEATURES["h2h_window"])
        h2h_pts_h = h2h_pts_a = np.nan
        h2h_n = 0
        if meetings:
            h2h_n = len(meetings)
            pts_h, pts_a = [], []
            for (hd, hk, ak, hgx, agx) in meetings:
                if hk == key_h:
                    if hgx > agx:
                        pts_h.append(3); pts_a.append(0)
                    elif hgx == agx:
                        pts_h.append(1); pts_a.append(1)
                    else:
                        pts_h.append(0); pts_a.append(3)
                else:
                    if agx > hgx:
                        pts_h.append(3); pts_a.append(0)
                    elif agx == hgx:
                        pts_h.append(1); pts_a.append(1)
                    else:
                        pts_h.append(0); pts_a.append(3)
            w = [1.0 / (i + 1) for i in range(len(pts_h))]
            h2h_pts_h = float(np.average(pts_h, weights=w))
            h2h_pts_a = float(np.average(pts_a, weights=w))

        lg = self.league_goals.get(league, [])
        lg_avg_total = float(np.mean(lg[-200:])) if lg else np.nan

        def _rest(recs, d):
            if not recs:
                return np.nan
            return (d - recs[-1][0]).days

        feat = {
            "form_pts_h": _form_pts(h_recs) if valid_h else np.nan,
            "form_pts_a": _form_pts(a_recs) if valid_a else np.nan,
            "form_gf_h": _avg(h_recs, 2) if valid_h else np.nan,
            "form_ga_h": _avg(h_recs, 3) if valid_h else np.nan,
            "form_gf_a": _avg(a_recs, 2) if valid_a else np.nan,
            "form_ga_a": _avg(a_recs, 3) if valid_a else np.nan,
            "form_home_gf_h": _avg(h_home, 2) if h_home and valid_h else np.nan,
            "form_away_ga_a": _avg(a_away, 3) if a_away and valid_a else np.nan,
            "shots_f_h": _avg(h_recs, 4) if valid_h else np.nan,
            "shots_a_h": _avg(h_recs, 5) if valid_h else np.nan,
            "shots_f_a": _avg(a_recs, 4) if valid_a else np.nan,
            "shots_a_a": _avg(a_recs, 5) if valid_a else np.nan,
            "sot_f_h": _avg(h_recs, 6) if valid_h else np.nan,
            "sot_f_a": _avg(a_recs, 6) if valid_a else np.nan,
            "corners_f_h": _avg(h_recs, 7) if valid_h else np.nan,
            "corners_f_a": _avg(a_recs, 7) if valid_a else np.nan,
            "h2h_n": h2h_n,
            "h2h_pts_h": h2h_pts_h,
            "h2h_pts_a": h2h_pts_a,
            "lg_avg_total": lg_avg_total,
            "rest_h": _rest(h_recs, date),
            "rest_a": _rest(a_recs, date),
        }
        # ELO 差异(需要 ELO 引擎状态)
        if self.elo is not None:
            rh = self.elo.get_rating(home, date)
            ra = self.elo.get_rating(away, date)
            feat["elo_diff"] = rh - ra
            feat["days_since_home"] = _rest(h_recs, date)
            feat["days_since_away"] = _rest(a_recs, date)
        else:
            feat["elo_diff"] = np.nan
            feat["days_since_home"] = _rest(h_recs, date)
            feat["days_since_away"] = _rest(a_recs, date)

        feat["form_pts_diff"] = feat["form_pts_h"] - feat["form_pts_a"]
        feat["form_gf_diff"] = feat["form_gf_h"] - feat["form_gf_a"]
        feat["form_ga_diff"] = feat["form_ga_h"] - feat["form_ga_a"]
        feat["shots_diff"] = feat["shots_f_h"] - feat["shots_f_a"]
        feat["sot_diff"] = feat["sot_f_h"] - feat["sot_f_a"]
        feat["corner_diff"] = feat["corners_f_h"] - feat["corners_f_a"]
        feat["h2h_diff"] = feat["h2h_pts_h"] - feat["h2h_pts_a"]
        feat["rest_diff"] = feat["rest_h"] - feat["rest_a"]
        return feat


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """为比赛表追加特征列(因果构建，每场只用此前数据)。"""
    df = df.sort_values("date").reset_index(drop=True)
    df = compute_elo_history(df)

    state = FeatureState()
    # 将 ELO 引擎接入 state 供 features_for 使用
    from elo import EloEngine
    state.elo = EloEngine()
    # 重建 ELO 状态(与 compute_elo_history 相同的更新顺序)
    elo_eng = EloEngine()
    rows = []
    for _, r in df.iterrows():
        feat = state.features_for(r["date"], r["league"], r["home"], r["away"])
        feat["elo_home"] = elo_eng.get_rating(r["home"], r["date"])
        feat["elo_away"] = elo_eng.get_rating(r["away"], r["date"])
        feat["elo_diff"] = feat["elo_home"] - feat["elo_away"]
        rows.append(feat)
        state.observe(r)
        elo_eng.update(r["home"], r["away"], r["hg"], r["ag"], r["date"])
    feat = pd.DataFrame(rows, index=df.index)
    out = pd.concat([df, feat], axis=1)
    return out.loc[:, ~out.columns.duplicated()]


def features_for_match(df: pd.DataFrame, date, league: str, home: str, away: str) -> dict:
    """对任意比赛(含未来)计算赛前特征：只用 date 之前的记录。"""
    past = df[df["date"] < pd.Timestamp(date)].sort_values("date")
    from elo import EloEngine
    state = FeatureState()
    elo_eng = EloEngine()
    for _, r in past.iterrows():
        state.observe(r)
        elo_eng.update(r["home"], r["away"], r["hg"], r["ag"], r["date"])
    state.elo = elo_eng
    return state.features_for(pd.Timestamp(date), league, home, away)


FEATURE_COLS = [
    "elo_diff", "form_pts_diff", "form_gf_diff", "form_ga_diff",
    "shots_diff", "sot_diff", "corner_diff", "h2h_diff", "rest_diff",
    "days_since_home", "days_since_away", "lg_avg_total",
    "h2h_n", "h2h_pts_h", "h2h_pts_a",
]


def _self_test():
    # 9 场: 让 A/B/C 在靠后场次积累 >= min_matches(3) 场历史, 验证样本不足/充足两条路径
    n = 9
    dates = pd.to_datetime([f"2024-01-{i+1:02d}" for i in range(n)])
    df = pd.DataFrame({
        "date": dates,
        "league": ["T"] * n,
        "home": ["A", "B", "A", "A", "B", "C", "B", "A", "C"],
        "away": ["B", "A", "C", "D", "C", "A", "D", "B", "A"],
        "hg": [2, 1, 3, 2, 1, 1, 2, 2, 0],
        "ag": [0, 0, 1, 1, 1, 0, 1, 0, 1],
        "home_shots": [10, 8, 12, 11, 7, 9, 8, 11, 6],
        "away_shots": [6, 7, 4, 5, 6, 5, 7, 4, 8],
        "home_sot": [5, 3, 6, 5, 3, 4, 3, 5, 2],
        "away_sot": [2, 3, 1, 2, 2, 2, 3, 1, 3],
        "home_corners": [6, 4, 7, 6, 3, 5, 4, 6, 2],
        "away_corners": [3, 3, 2, 2, 4, 3, 5, 2, 4],
        "home_yellow": [1, 0, 2, 1, 1, 0, 1, 2, 0],
        "away_yellow": [0, 1, 0, 1, 2, 1, 2, 0, 1],
        "home_red": [0, 0, 0, 0, 0, 0, 0, 0, 0],
        "away_red": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    })
    feat = build_features(df)
    # 第1场: 双方均无历史 -> NaN(且不满足 min_matches)
    assert np.isnan(feat.loc[0, "form_pts_h"])
    assert np.isnan(feat.loc[0, "form_pts_a"])
    # 样本不足(<min_matches): B 在第2场(索引1)仅1场历史 -> NaN
    assert np.isnan(feat.loc[1, "form_pts_h"])
    # A 在第4场(索引3, A vs D)前已有3场历史(>=min_matches): 主胜3 + 客负0 + 主胜3
    # 时间权重 [1, 0.5, 1/3]
    v = feat.loc[3, "form_pts_h"]
    expected = (3.0 * 1.0 + 0.0 * 0.5 + 3.0 * (1.0 / 3.0)) / (1.0 + 0.5 + 1.0 / 3.0)
    assert abs(v - expected) < 1e-9, (v, expected)

    # features_for_match 与 build_features 一致(对第4场 A vs D)
    f2 = features_for_match(df, "2024-01-04", "T", "A", "D")
    assert abs(f2["form_pts_h"] - feat.loc[3, "form_pts_h"]) < 1e-9, (f2["form_pts_h"], feat.loc[3, "form_pts_h"])
    print("== features 自检通过 ==")


if __name__ == "__main__":
    _self_test()
