"""模型 —— 泊松（主模型，无训练状态）与 XGBoost（对照）。

泊松：λ_home = 联赛主队场均进球 × 主队进攻 × 客队防守
      λ_away = 联赛客队场均进球 × 客队进攻 × 主队防守
全部输入来自 features（已保证无泄漏）。
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .markets import goal_matrix, p_1x2, p_over, p_ah, p_ah_quarter, p_ou_quarter


class PoissonGoalModel:
    """无状态泊松模型：只需要一行特征即可预测。

    xg_blend: 0=纯进球强度; (0,1]=进球与 xG 强度按权重混合。
    仅当该场两队都有 xG 历史(4 列 xG 强度非空)时启用混合, 否则自动回退纯进球,
    保证"无 xG 数据的场次"与"基线口径"完全一致。
    """

    def __init__(self, max_goals: int = 10, xg_blend: float = 0.0):
        self.max_goals = max_goals
        self.xg_blend = float(xg_blend)

    def predict(self, row) -> dict:
        w = self.xg_blend
        if w > 0:
            cols = ("att_home_xg", "def_home_xg", "att_away_xg", "def_away_xg")
            vals = [row.get(c) if hasattr(row, "get") else getattr(row, c, None) for c in cols]
            # NaN 判断: v != v 对 float/np.float64 的 NaN 均为 True
            ok = all(v is not None and not bool(v != v) for v in vals)
            if ok:
                lam_h = min(max(row["league_avg_home"] * (w * row["att_home"] + (1 - w) * vals[0])
                                * (w * row["def_away"] + (1 - w) * vals[3]), 0.05), 6.0)
                lam_a = min(max(row["league_avg_away"] * (w * row["att_away"] + (1 - w) * vals[2])
                                * (w * row["def_home"] + (1 - w) * vals[1]), 0.05), 6.0)
                M = goal_matrix(lam_h, lam_a, self.max_goals)
                p_home, p_draw, p_away = p_1x2(M)
                return {"lam_h": lam_h, "lam_a": lam_a, "M": M,
                        "p_home": p_home, "p_draw": p_draw, "p_away": p_away}
        lam_h = row["league_avg_home"] * row["att_home"] * row["def_away"]
        lam_a = row["league_avg_away"] * row["att_away"] * row["def_home"]
        lam_h = min(max(lam_h, 0.05), 6.0)
        lam_a = min(max(lam_a, 0.05), 6.0)
        M = goal_matrix(lam_h, lam_a, self.max_goals)
        p_home, p_draw, p_away = p_1x2(M)
        return {
            "lam_h": lam_h, "lam_a": lam_a, "M": M,
            "p_home": p_home, "p_draw": p_draw, "p_away": p_away,
        }

    # ---- 便捷接口 ----
    def p_over_line(self, row, line: float) -> float:
        return p_ou_quarter(self.predict(row)["M"], line)

    def p_ah_line(self, row, line: float) -> float:
        return p_ah_quarter(self.predict(row)["M"], line)


class LGBModel:
    """LightGBM 1X2 分类器（CalibratedClassifierCV 内嵌校准），与 XGBModel 同接口。"""

    def __init__(self, params: dict):
        import lightgbm as lgb
        from sklearn.calibration import CalibratedClassifierCV

        self._lgb = lgb
        self._cal = CalibratedClassifierCV
        self.params = params
        self.model = None

    def _to_df(self, X: np.ndarray):
        """ndarray -> DataFrame(带特征名), 消除LGB 'no feature names' warning."""
        if hasattr(X, "columns"):
            return X
        try:
            import pandas as pd
            return pd.DataFrame(X, columns=["f%d" % i for i in range(X.shape[1])])
        except Exception:
            return X

    def fit(self, X: np.ndarray, y: np.ndarray):
        base = self._lgb.LGBMClassifier(
            n_estimators=self.params.get("n_estimators", 400),
            max_depth=self.params.get("max_depth", 4),
            learning_rate=self.params.get("learning_rate", 0.05),
            subsample=self.params.get("subsample", 0.8),
            colsample_bytree=self.params.get("colsample_bytree", 0.8),
            min_child_samples=self.params.get("min_child_samples", 30),
            reg_lambda=self.params.get("reg_lambda", 1.0),
            random_state=self.params.get("random_state", 42),
            n_jobs=4,
            verbose=-1,
        )
        self.model = self._cal(base, method="sigmoid", cv=3)
        classes = np.unique(y)
        self.model.classes_ = classes
        self.model.fit(self._to_df(X), y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """返回 [p_away, p_draw, p_home] 顺序（与 target 0/1/2 对齐）。"""
        proba = self.model.predict_proba(self._to_df(X))
        out = np.zeros((len(X), int(max(self.model.classes_)) + 1))
        for k, c in enumerate(self.model.classes_):
            out[:, int(c)] = proba[:, k]
        return out


class CatModel:
    """CatBoost 1X2 分类器（CalibratedClassifierCV 内嵌校准），与 XGBModel 同接口。

    CatBoost 原生处理类别特征; 此处特征均为数值, 与 XGB/LGB 同一输入口径做对照。
    """

    def __init__(self, params: dict):
        from catboost import CatBoostClassifier
        from sklearn.calibration import CalibratedClassifierCV

        self._cb = CatBoostClassifier
        self._cal = CalibratedClassifierCV
        self.params = params
        self.model = None

    def fit(self, X: np.ndarray, y: np.ndarray):
        base = self._cb(
            iterations=self.params.get("iterations", 300),
            depth=self.params.get("depth", 4),
            learning_rate=self.params.get("learning_rate", 0.05),
            l2_leaf_reg=self.params.get("l2_leaf_reg", 1.0),
            subsample=self.params.get("subsample", 0.8),
            bootstrap_type="Bernoulli",  # 默认bayesian不支持subsample
            rsm=self.params.get("rsm", 0.8),
            loss_function="MultiClass",
            random_seed=self.params.get("random_seed", 42),
            thread_count=self.params.get("thread_count", 4),
            verbose=False,
        )
        self.model = self._cal(base, method="sigmoid", cv=3)
        classes = np.unique(y)
        self.model.classes_ = classes
        self.model.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """返回 [p_away, p_draw, p_home] 顺序（与 target 0/1/2 对齐）。"""
        proba = self.model.predict_proba(X)
        out = np.zeros((len(X), int(max(self.model.classes_)) + 1))
        for k, c in enumerate(self.model.classes_):
            out[:, int(c)] = proba[:, k]
        return out


class XGBModel:
    """XGBoost 1X2 分类器（CalibratedClassifierCV 内嵌校准）。"""

    def __init__(self, params: dict, max_goals: int = 10):
        import xgboost as xgb
        from sklearn.calibration import CalibratedClassifierCV

        self._xgb = xgb
        self._cal = CalibratedClassifierCV
        self.params = params
        self.model = None
        self.max_goals = max_goals

    def fit(self, X: np.ndarray, y: np.ndarray):
        base = self._xgb.XGBClassifier(
            n_estimators=self.params.get("n_estimators", 200),
            max_depth=self.params.get("max_depth", 4),
            learning_rate=self.params.get("learning_rate", 0.05),
            subsample=self.params.get("subsample", 0.8),
            colsample_bytree=self.params.get("colsample_bytree", 0.8),
            min_child_weight=self.params.get("min_child_weight", 3),
            reg_lambda=self.params.get("reg_lambda", 1.0),
            eval_metric="mlogloss",
            random_state=self.params.get("random_state", 42),
            n_jobs=4,
        )
        self.model = self._cal(base, method="sigmoid", cv=3)

        # 类别均衡：按序填充以符合 0/1/2 的列顺序
        classes = np.unique(y)
        self.model.classes_ = classes
        self.model.fit(X, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """返回 [p_away, p_draw, p_home] 顺序（与 target 0/1/2 对齐）。"""
        proba = self.model.predict_proba(X)
        # sklearn 列序按 classes_ 升序: 0=away,1=draw,2=home(二分类时0=under,1=over)
        out = np.zeros((len(X), int(max(self.model.classes_)) + 1))
        for k, c in enumerate(self.model.classes_):
            out[:, int(c)] = proba[:, k]
        return out


def poisson_from_strengths(league_avg_h: float, league_avg_a: float,
                           att_h: float, def_h: float,
                           att_a: float, def_a: float,
                           max_goals: int = 10) -> tuple[float, float, np.ndarray]:
    """独立工具：由强度直接算 λ 与比分矩阵（供预测/测试复用）。"""
    lam_h = min(max(league_avg_h * att_h * def_a, 0.05), 6.0)
    lam_a = min(max(league_avg_a * att_a * def_h, 0.05), 6.0)
    return lam_h, lam_a, goal_matrix(lam_h, lam_a, max_goals)
