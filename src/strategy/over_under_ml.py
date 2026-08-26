"""
ML大小球预测模型
使用XGBoost预测比赛总进球数
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class MLPrediction:
    """ML预测结果"""
    predicted_total_goals: float
    over25_prob: float
    under25_prob: float
    over35_prob: float
    under35_prob: float
    confidence: int  # 1-5星
    features_used: List[str]


class OverUnderMLModel:
    """大小球ML预测模型"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = None
        self.is_trained = False
        
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备特征"""
        features = pd.DataFrame()
        
        # 基础特征
        if 'home_xg' in df.columns and 'away_xg' in df.columns:
            features['total_xg'] = df['home_xg'] + df['away_xg']
            features['xg_diff'] = df['home_xg'] - df['away_xg']
        
        if 'home_shots_total' in df.columns and 'away_shots_total' in df.columns:
            features['total_shots'] = df['home_shots_total'] + df['away_shots_total']
            features['shots_diff'] = df['home_shots_total'] - df['away_shots_total']
        
        if 'home_shots_on_goal' in df.columns and 'away_shots_on_goal' in df.columns:
            features['total_shots_on_target'] = df['home_shots_on_goal'] + df['away_shots_on_goal']
        
        if 'home_corners' in df.columns and 'away_corners' in df.columns:
            features['total_corners'] = df['home_corners'] + df['away_corners']
        
        if 'home_possession' in df.columns:
            features['home_possession'] = df['home_possession']
        
        # 赔率特征
        if 'home_win' in df.columns and 'draw' in df.columns and 'away_win' in df.columns:
            features['odds_home'] = df['home_win']
            features['odds_draw'] = df['draw']
            features['odds_away'] = df['away_win']
            
            # 计算隐含概率
            total_odds = 1/df['home_win'] + 1/df['draw'] + 1/df['away_win']
            features['implied_home'] = (1/df['home_win']) / total_odds
            features['implied_draw'] = (1/df['draw']) / total_odds
            features['implied_away'] = (1/df['away_win']) / total_odds
        
        # 滚动特征（如果有）
        rolling_cols = [c for c in df.columns if '_w3' in c or '_w5' in c or '_w10' in c]
        for col in rolling_cols[:10]:  # 取前10个滚动特征
            if col in df.columns:
                features[col] = df[col]
        
        return features
    
    def _calculate_total_goals(self, df: pd.DataFrame) -> pd.Series:
        """计算总进球数"""
        if 'goals_home' in df.columns and 'goals_away' in df.columns:
            return df['goals_home'] + df['goals_away']
        elif 'home_goals' in df.columns and 'away_goals' in df.columns:
            return df['home_goals'] + df['away_goals']
        else:
            return pd.Series([0] * len(df))
    
    def train(self, data_path: str, target_col: str = 'total_goals'):
        """
        训练模型
        
        参数:
            data_path: 数据文件路径
            target_col: 目标列名
        """
        # 加载数据
        df = pd.read_csv(data_path)
        
        # 准备特征
        X = self._prepare_features(df)
        
        # 准备目标
        if target_col not in df.columns:
            y = self._calculate_total_goals(df)
        else:
            y = df[target_col]
        
        # 删除空值
        valid_idx = X.notna().all(axis=1) & y.notna()
        X = X[valid_idx]
        y = y[valid_idx]
        
        self.feature_columns = X.columns.tolist()
        
        # 简单模型：使用特征的加权平均
        # 这里不使用sklearn，而是用简单的统计模型
        self._train_simple_model(X, y)
        
        self.is_trained = True
        
    def _train_simple_model(self, X: pd.DataFrame, y: pd.Series):
        """训练简单模型（不依赖sklearn）"""
        # 计算每个特征与目标的相关性
        self.feature_weights = {}
        for col in X.columns:
            if X[col].std() > 0:
                corr = X[col].corr(y)
                if not np.isnan(corr):
                    self.feature_weights[col] = corr
        
        # 计算基础进球数（均值）
        self.base_goals = y.mean()
        
        # 计算标准差
        self.goals_std = y.std()
        
    def predict(
        self,
        home_xg: Optional[float] = None,
        away_xg: Optional[float] = None,
        home_shots: Optional[float] = None,
        away_shots: Optional[float] = None,
        home_shots_on_target: Optional[float] = None,
        away_shots_on_target: Optional[float] = None,
        home_possession: Optional[float] = None,
        odds_home: Optional[float] = None,
        odds_draw: Optional[float] = None,
        odds_away: Optional[float] = None,
        league_avg_goals: float = 2.8,
    ) -> MLPrediction:
        """
        预测总进球数
        """
        if not self.is_trained:
            # 如果没有训练，使用简单规则
            return self._predict_rule_based(
                home_xg, away_xg, league_avg_goals
            )
        
        # 构建特征向量
        features = {}
        
        if home_xg is not None and away_xg is not None:
            features['total_xg'] = home_xg + away_xg
            features['xg_diff'] = home_xg - away_xg
        
        if home_shots is not None and away_shots is not None:
            features['total_shots'] = home_shots + away_shots
            features['shots_diff'] = home_shots - away_shots
        
        if home_shots_on_target is not None and away_shots_on_target is not None:
            features['total_shots_on_target'] = home_shots_on_target + away_shots_on_target
        
        if home_possession is not None:
            features['home_possession'] = home_possession
        
        if odds_home is not None and odds_draw is not None and odds_away is not None:
            features['odds_home'] = odds_home
            features['odds_draw'] = odds_draw
            features['odds_away'] = odds_away
            
            total_odds = 1/odds_home + 1/odds_draw + 1/odds_away
            features['implied_home'] = (1/odds_home) / total_odds
            features['implied_draw'] = (1/odds_draw) / total_odds
            features['implied_away'] = (1/odds_away) / total_odds
        
        # 使用加权平均预测
        prediction = self.base_goals
        
        for feature, value in features.items():
            if feature in self.feature_weights:
                weight = self.feature_weights[feature]
                # 标准化值
                if feature in ['total_xg', 'total_shots', 'total_shots_on_target']:
                    prediction += value * weight * 0.1
                elif feature in ['xg_diff', 'shots_diff']:
                    prediction += value * weight * 0.05
        
        # 计算概率
        from scipy import stats
        
        # 使用正态分布计算概率
        over25_prob = 1 - stats.norm.cdf(2.5, prediction, self.goals_std)
        under25_prob = stats.norm.cdf(2.5, prediction, self.goals_std)
        over35_prob = 1 - stats.norm.cdf(3.5, prediction, self.goals_std)
        under35_prob = stats.norm.cdf(3.5, prediction, self.goals_std)
        
        # 计算信心
        confidence = self._calculate_confidence(
            prediction, over25_prob, under25_prob
        )
        
        return MLPrediction(
            predicted_total_goals=round(prediction, 2),
            over25_prob=round(over25_prob, 3),
            under25_prob=round(under25_prob, 3),
            over35_prob=round(over35_prob, 3),
            under35_prob=round(under35_prob, 3),
            confidence=confidence,
            features_used=list(features.keys())
        )
    
    def _predict_rule_based(
        self,
        home_xg: Optional[float],
        away_xg: Optional[float],
        league_avg_goals: float
    ) -> MLPrediction:
        """基于规则的预测（当没有训练数据时）"""
        
        if home_xg is not None and away_xg is not None:
            predicted = (home_xg + away_xg) / 2 + league_avg_goals / 2
        else:
            predicted = league_avg_goals
        
        # 简单概率计算
        std = 1.2  # 假设标准差
        from scipy import stats
        
        over25_prob = 1 - stats.norm.cdf(2.5, predicted, std)
        under25_prob = stats.norm.cdf(2.5, predicted, std)
        over35_prob = 1 - stats.norm.cdf(3.5, predicted, std)
        under35_prob = stats.norm.cdf(3.5, predicted, std)
        
        confidence = 3 if abs(predicted - 2.75) > 0.5 else 2
        
        return MLPrediction(
            predicted_total_goals=round(predicted, 2),
            over25_prob=round(over25_prob, 3),
            under25_prob=round(under25_prob, 3),
            over35_prob=round(over35_prob, 3),
            under35_prob=round(under35_prob, 3),
            confidence=confidence,
            features_used=['league_avg']
        )
    
    def _calculate_confidence(
        self,
        predicted: float,
        over25_prob: float,
        under25_prob: float
    ) -> int:
        """计算信心等级"""
        # 与2.5球的差距
        diff = abs(predicted - 2.5)
        
        if diff > 1.0:
            return 5
        elif diff > 0.75:
            return 4
        elif diff > 0.5:
            return 3
        elif diff > 0.25:
            return 2
        else:
            return 1


class EnhancedOverUnderModel:
    """增强版大小球模型（结合ML和规则）"""
    
    def __init__(self):
        self.ml_model = OverUnderMLModel()
        self.league_stats = self._load_league_stats()
        
    def _load_league_stats(self) -> Dict[str, Dict]:
        """加载联赛统计数据"""
        return {
            "中超": {"avg": 2.6, "over25": 55, "over35": 30},
            "MLS": {"avg": 3.0, "over25": 60, "over35": 40},
            "MLS Next Pro": {"avg": 3.42, "over25": 66, "over35": 45},
            "澳大利亚NPL": {"avg": 3.76, "over25": 77, "over35": 56},
            "澳大利亚Queensland U23": {"avg": 4.01, "over25": 76, "over35": 56},
            "澳大利亚NSW联赛U20": {"avg": 3.8, "over25": 72, "over35": 52},
            "澳大利亚Victoria U23": {"avg": 3.9, "over25": 74, "over35": 54},
            "球会友谊赛": {"avg": 2.8, "over25": 52, "over35": 32},
            "巴西甲级联赛": {"avg": 2.5, "over25": 50, "over35": 28},
            "俄罗斯联赛U19": {"avg": 3.2, "over25": 60, "over35": 40},
            # 丹麦杯 (DBU Pokalen) - 杯赛，高进球
            "丹麦杯": {"avg": 3.28, "over25": 78, "over35": 51},
        }
    
    def predict(
        self,
        league: str,
        ou_line: float,
        ou_odds_over: float,
        ou_odds_under: float,
        home_xg: Optional[float] = None,
        away_xg: Optional[float] = None,
        home_shots: Optional[float] = None,
        away_shots: Optional[float] = None,
    ) -> Dict:
        """
        综合预测
        
        返回: 包含预测结果和推荐的字典
        """
        # 获取联赛统计
        league_info = self.league_stats.get(league, {"avg": 2.8, "over25": 55, "over35": 35})
        league_avg = league_info["avg"]
        
        # ML预测
        ml_pred = self.ml_model.predict(
            home_xg=home_xg,
            away_xg=away_xg,
            home_shots=home_shots,
            away_shots=away_shots,
            league_avg_goals=league_avg
        )
        
        # 规则预测
        ratio = ou_line / league_avg
        if ratio < 0.85:
            rule_rec = "大球"
            rule_conf = 4
        elif ratio > 1.15:
            rule_rec = "小球"
            rule_conf = 4
        else:
            rule_rec = "观望"
            rule_conf = 2
        
        # 综合推荐
        if ml_pred.predicted_total_goals > ou_line and rule_rec == "大球":
            final_rec = "大球"
            final_conf = min(5, (ml_pred.confidence + rule_conf) // 2 + 1)
        elif ml_pred.predicted_total_goals < ou_line and rule_rec == "小球":
            final_rec = "小球"
            final_conf = min(5, (ml_pred.confidence + rule_conf) // 2 + 1)
        else:
            final_rec = rule_rec
            final_conf = max(1, (ml_pred.confidence + rule_conf) // 2 - 1)
        
        # 计算期望值
        if final_rec == "大球":
            implied_prob = 1 / ou_odds_over
            model_prob = ml_pred.over25_prob if ou_line <= 2.5 else ml_pred.over35_prob
        elif final_rec == "小球":
            implied_prob = 1 / ou_odds_under
            model_prob = ml_pred.under25_prob if ou_line <= 2.5 else ml_pred.under35_prob
        else:
            implied_prob = 0.5
            model_prob = 0.5
        
        expected_value = model_prob - implied_prob
        
        return {
            "recommendation": final_rec,
            "confidence": final_conf,
            "predicted_total_goals": ml_pred.predicted_total_goals,
            "over25_prob": ml_pred.over25_prob,
            "under25_prob": ml_pred.under25_prob,
            "over35_prob": ml_pred.over35_prob,
            "under35_prob": ml_pred.under35_prob,
            "league_avg": league_avg,
            "line_ratio": ratio,
            "expected_value": expected_value,
            "features_used": ml_pred.features_used,
        }


# 测试
if __name__ == "__main__":
    model = EnhancedOverUnderModel()
    
    # 测试1: 中超比赛
    result1 = model.predict(
        league="中超",
        ou_line=3.0,
        ou_odds_over=1.84,
        ou_odds_under=2.00,
        home_xg=1.2,
        away_xg=0.8,
    )
    print("河南队 vs 大连英博:")
    print(f"  推荐: {result1['recommendation']}")
    print(f"  预测总进球: {result1['predicted_total_goals']}")
    print(f"  大2.5概率: {result1['over25_prob']:.1%}")
    print(f"  小2.5概率: {result1['under25_prob']:.1%}")
    print(f"  信心: {'⭐' * result1['confidence']}")
    print(f"  期望值: {result1['expected_value']:.1%}")
    print()
    
    # 测试2: MLS Next Pro
    result2 = model.predict(
        league="MLS Next Pro",
        ou_line=3.0,
        ou_odds_over=1.71,
        ou_odds_under=2.10,
        home_xg=1.5,
        away_xg=1.2,
    )
    print("迈阿密国际B vs 查塔努加:")
    print(f"  推荐: {result2['recommendation']}")
    print(f"  预测总进球: {result2['predicted_total_goals']}")
    print(f"  大2.5概率: {result2['over25_prob']:.1%}")
    print(f"  小2.5概率: {result2['under25_prob']:.1%}")
    print(f"  信心: {'⭐' * result2['confidence']}")
    print(f"  期望值: {result2['expected_value']:.1%}")
