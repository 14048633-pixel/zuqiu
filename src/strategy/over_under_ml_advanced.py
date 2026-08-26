"""
增强版大小球ML模型
使用XGBoost和sklearn训练更精确的预测模型
支持小联赛单独调整
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

# 尝试导入sklearn和xgboost
try:
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("sklearn未安装，使用基础模型")

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("xgboost未安装，使用sklearn模型")

# 小联赛列表
SMALL_LEAGUES = [
    "MLS Next Pro",
    "澳大利亚Queensland U23",
    "澳大利亚NSW联赛U20",
    "澳大利亚Victoria U23",
    "澳大利亚首都特区国家超级联赛U23",
    "印度锡金超级联赛",
    "新西兰北部联赛",
    "俄罗斯联赛U19",
    "乌克兰甲级联赛",
    "危地马拉联赛",
    "墨西哥甲级联赛",
    "澳大利亚NPL",
    "澳大利亚Queensland NPL",
    # 注意：丹麦杯不在小联赛列表中，作为主流杯赛处理
    # "丹麦杯",
]

# 小联赛特征调整系数（细调后）
SMALL_LEAGUE_ADJUSTMENTS = {
    "confidence_penalty": -2,  # 细调: -1 -> -2
    "variance_multiplier": 1.4,  # 细调: 1.3 -> 1.4
    "min_confidence": 1,  # 最低信心
    "max_confidence": 3,  # 细调: 4 -> 3
}


@dataclass
class AdvancedMLPrediction:
    """高级ML预测结果"""
    predicted_total_goals: float
    over25_prob: float
    under25_prob:  float
    over35_prob: float
    under35_prob: float
    confidence: int
    model_type: str
    feature_importance: Dict[str, float]
    metrics: Dict[str, float]

    def over_prob_for_line(self, line: float) -> float:
        """计算任意盘口的大球概率（基于预测总进球和RMSE标准差）"""
        if not self.metrics or 'rmse' not in self.metrics:
            return self.over25_prob if line <= 2.5 else self.over35_prob
        from scipy import stats
        std = self.metrics.get('rmse', 1.2)
        return 1 - stats.norm.cdf(line, self.predicted_total_goals, std)

    def under_prob_for_line(self, line: float) -> float:
        """计算任意盘口的小球概率"""
        return 1 - self.over_prob_for_line(line)


class AdvancedOverUnderModel:
    """高级大小球ML模型"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler() if HAS_SKLEARN else None
        self.feature_columns = None
        self.is_trained = False
        self.model_type = "rule_based"
        self.feature_importance = {}
        self.metrics = {}
        self.league_models = {}  # 联赛专属模型
        self.league_stats = {}  # 联赛统计数据
        
    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """创建特征"""
        features = pd.DataFrame()
        
        # 1. xG特征
        if 'home_xg' in df.columns and 'away_xg' in df.columns:
            features['total_xg'] = df['home_xg'] + df['away_xg']
            features['xg_diff'] = df['home_xg'] - df['away_xg']
            features['home_xg_ratio'] = df['home_xg'] / (df['home_xg'] + df['away_xg'] + 0.01)
        
        # 2. 射门特征
        if 'home_shots_total' in df.columns and 'away_shots_total' in df.columns:
            features['total_shots'] = df['home_shots_total'] + df['away_shots_total']
            features['shots_diff'] = df['home_shots_total'] - df['away_shots_total']
            features['home_shots_ratio'] = df['home_shots_total'] / (df['home_shots_total'] + df['away_shots_total'] + 0.01)
        
        # 3. 射正特征
        if 'home_shots_on_goal' in df.columns and 'away_shots_on_goal' in df.columns:
            features['total_shots_on_target'] = df['home_shots_on_goal'] + df['away_shots_on_goal']
            features['shots_on_target_diff'] = df['home_shots_on_goal'] - df['away_shots_on_goal']
        
        # 4. 角球特征
        if 'home_corners' in df.columns and 'away_corners' in df.columns:
            features['total_corners'] = df['home_corners'] + df['away_corners']
        
        # 5. 控球率特征
        if 'home_possession' in df.columns:
            features['home_possession'] = df['home_possession']
            features['possession_diff'] = df['home_possession'] - 50
        
        # 6. 赔率特征
        if 'home_win' in df.columns and 'draw' in df.columns and 'away_win' in df.columns:
            features['odds_home'] = df['home_win']
            features['odds_draw'] = df['draw']
            features['odds_away'] = df['away_win']
            
            # 隐含概率
            total_odds = 1/df['home_win'] + 1/df['draw'] + 1/df['away_win']
            features['implied_home'] = (1/df['home_win']) / total_odds
            features['implied_draw'] = (1/df['draw']) / total_odds
            features['implied_away'] = (1/df['away_win']) / total_odds
            
            # 赔率差异
            features['odds_diff'] = df['home_win'] - df['away_win']
        
        # 7. 滚动特征
        rolling_cols = [c for c in df.columns if '_w3' in c or '_w5' in c]
        for col in rolling_cols[:8]:
            if col in df.columns:
                features[col] = df[col]
        
        # 8. 犯规和黄牌（比赛激烈程度）
        if 'home_fouls' in df.columns and 'away_fouls' in df.columns:
            features['total_fouls'] = df['home_fouls'] + df['away_fouls']
        
        if 'home_yellow_cards' in df.columns and 'away_yellow_cards' in df.columns:
            features['total_yellows'] = df['home_yellow_cards'] + df['away_yellow_cards']
        
        # 9. 联赛特征
        if 'league' in df.columns:
            # 是否为小联赛
            features['is_small_league'] = df['league'].isin(SMALL_LEAGUES).astype(int)
            
            # 联赛场均进球（如果有）
            if 'league_avg_goals' in df.columns:
                features['league_avg_goals'] = df['league_avg_goals']
        
        return features
    
    def _create_league_features(self, league: str, is_small: bool) -> Dict[str, float]:
        """创建联赛特定特征"""
        features = {}
        
        # 是否为小联赛
        features['is_small_league'] = 1 if is_small else 0
        
        # 联赛统计
        if league in self.league_stats:
            stats = self.league_stats[league]
            features['league_avg_goals'] = stats.get('avg_goals', 2.8)
            features['league_variance'] = stats.get('variance', 1.2)
        else:
            # 默认值
            if is_small:
                features['league_avg_goals'] = 2.5  # 小联赛平均进球较低
                features['league_variance'] = 1.5  # 小联赛方差较大
            else:
                features['league_avg_goals'] = 2.8
                features['league_variance'] = 1.2
        
        return features
    
    def _get_target(self, df: pd.DataFrame) -> pd.Series:
        """获取目标变量（总进球数）"""
        if 'goals_home' in df.columns and 'goals_away' in df.columns:
            return df['goals_home'] + df['goals_away']
        elif 'home_goals' in df.columns and 'away_goals' in df.columns:
            return df['home_goals'] + df['away_goals']
        elif 'target' in df.columns:
            # 如果target是胜平负，需要转换
            return df['target']
        else:
            return pd.Series([0] * len(df))
    
    def _calculate_league_stats(self, df: pd.DataFrame):
        """计算联赛统计数据"""
        if 'league' not in df.columns:
            return
        
        for league in df['league'].unique():
            league_df = df[df['league'] == league]
            
            # 计算场均进球
            total_goals = 0
            if 'goals_home' in league_df.columns and 'goals_away' in league_df.columns:
                total_goals = (league_df['goals_home'] + league_df['goals_away']).mean()
            elif 'home_goals' in league_df.columns and 'away_goals' in league_df.columns:
                total_goals = (league_df['home_goals'] + league_df['away_goals']).mean()
            
            # 计算方差
            variance = 1.2  # 默认方差
            if 'goals_home' in league_df.columns and 'goals_away' in league_df.columns:
                goals = league_df['goals_home'] + league_df['goals_away']
                variance = goals.var() if len(goals) > 1 else 1.2
            
            self.league_stats[league] = {
                'avg_goals': total_goals,
                'variance': variance,
                'is_small': league in SMALL_LEAGUES,
                'sample_size': len(league_df),
            }
    
    def train(self, data_path: str, model_type: str = "xgboost", train_separate_leagues: bool = True):
        """
        训练模型
        
        参数:
            data_path: 数据文件路径
            model_type: 模型类型 ("xgboost", "random_forest", "gradient_boosting")
            train_separate_leagues: 是否为小联赛训练单独模型
        """
        if not HAS_SKLEARN:
            print("sklearn未安装，使用基础模型")
            self.model_type = "rule_based"
            return
        
        # 加载数据
        print(f"加载数据: {data_path}")
        df = pd.read_csv(data_path)
        print(f"数据形状: {df.shape}")
        
        # 计算联赛统计
        self._calculate_league_stats(df)
        print(f"联赛数量: {len(self.league_stats)}")
        
        # 创建特征
        X = self._create_features(df)
        y = self._get_target(df)
        
        # 删除空值
        valid_idx = X.notna().all(axis=1) & y.notna()
        X = X[valid_idx]
        y = y[valid_idx]
        
        print(f"有效样本数: {len(X)}")
        
        if len(X) < 100:
            print("样本数不足，使用基础模型")
            self.model_type = "rule_based"
            return
        
        self.feature_columns = X.columns.tolist()
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # 标准化
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 选择模型
        if model_type == "xgboost" and HAS_XGBOOST:
            self.model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                random_state=42,
                verbosity=0
            )
            self.model_type = "xgboost"
        elif model_type == "random_forest":
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=6,
                random_state=42,
                n_jobs=-1
            )
            self.model_type = "random_forest"
        else:
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                random_state=42
            )
            self.model_type = "gradient_boosting"
        
        # 训练主模型
        print(f"训练主模型: {self.model_type}")
        self.model.fit(X_train_scaled, y_train)
        
        # 评估
        y_pred = self.model.predict(X_test_scaled)
        
        self.metrics = {
            'mae': mean_absolute_error(y_test, y_pred),
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'r2': r2_score(y_test, y_pred),
            'train_size': len(X_train),
            'test_size': len(X_test),
        }
        
        # 特征重要性
        if hasattr(self.model, 'feature_importances_'):
            for feat, imp in zip(self.feature_columns, self.model.feature_importances_):
                self.feature_importance[feat] = round(imp, 4)
        
        self.is_trained = True
        
        print(f"主模型训练完成!")
        print(f"  MAE: {self.metrics['mae']:.3f}")
        print(f"  RMSE: {self.metrics['rmse']:.3f}")
        print(f"  R2: {self.metrics['r2']:.3f}")
        
        # 为小联赛训练单独模型
        if train_separate_leagues:
            self._train_league_specific_models(df, model_type)
        
        return self.metrics
    
    def _train_league_specific_models(self, df: pd.DataFrame, model_type: str):
        """为小联赛训练单独模型"""
        if 'league' not in df.columns:
            return
        
        print("\n=== 训练联赛专属模型 ===")
        
        for league in SMALL_LEAGUES:
            league_df = df[df['league'] == league]
            
            if len(league_df) < 50:  # 样本数不足
                print(f"  {league}: 样本数不足({len(league_df)}), 跳过")
                continue
            
            print(f"  {league}: {len(league_df)}样本")
            
            # 创建特征
            X_league = self._create_features(league_df)
            y_league = self._get_target(league_df)
            
            # 删除空值
            valid_idx = X_league.notna().all(axis=1) & y_league.notna()
            X_league = X_league[valid_idx]
            y_league = y_league[valid_idx]
            
            if len(X_league) < 50:
                print(f"    有效样本不足, 跳过")
                continue
            
            # 划分训练集和测试集
            X_train, X_test, y_train, y_test = train_test_split(
                X_league, y_league, test_size=0.2, random_state=42
            )
            
            # 标准化
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # 选择模型
            if model_type == "xgboost" and HAS_XGBOOST:
                model = xgb.XGBRegressor(
                    n_estimators=50,
                    max_depth=3,
                    learning_rate=0.1,
                    random_state=42,
                    verbosity=0
                )
            elif model_type == "random_forest":
                model = RandomForestRegressor(
                    n_estimators=50,
                    max_depth=4,
                    random_state=42,
                    n_jobs=-1
                )
            else:
                model = GradientBoostingRegressor(
                    n_estimators=50,
                    max_depth=3,
                    learning_rate=0.1,
                    random_state=42
                )
            
            # 训练
            model.fit(X_train_scaled, y_train)
            
            # 评估
            y_pred = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)
            
            # 保存模型
            self.league_models[league] = {
                'model': model,
                'scaler': scaler,
                'feature_columns': X_league.columns.tolist(),
                'mae': mae,
            }
            
            print(f"    MAE: {mae:.3f}")
        
        print(f"联赛专属模型训练完成: {len(self.league_models)}个")
    
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
        home_corners: Optional[float] = None,
        away_corners: Optional[float] = None,
        home_fouls: Optional[float] = None,
        away_fouls: Optional[float] = None,
        league_avg_goals: float = 2.8,
        league: Optional[str] = None,
    ) -> AdvancedMLPrediction:
        """
        预测总进球数
        
        参数:
            league: 联赛名称（用于小联赛调整）
        """
        # 检查是否为小联赛
        is_small_league = league in SMALL_LEAGUES if league else False
        
        # 如果有联赛专属模型，优先使用
        if league and league in self.league_models:
            return self._predict_with_league_model(
                league, home_xg, away_xg, home_shots, away_shots,
                home_shots_on_target, away_shots_on_target, home_possession,
                odds_home, odds_draw, odds_away, home_corners, away_corners,
                home_fouls, away_fouls
            )
        
        if not self.is_trained or self.model_type == "rule_based":
            return self._predict_rule_based(
                home_xg, away_xg, league_avg_goals, is_small_league
            )
        
        # 构建特征向量
        features = {}
        
        if home_xg is not None and away_xg is not None:
            features['total_xg'] = home_xg + away_xg
            features['xg_diff'] = home_xg - away_xg
            features['home_xg_ratio'] = home_xg / (home_xg + away_xg + 0.01)
        
        if home_shots is not None and away_shots is not None:
            features['total_shots'] = home_shots + away_shots
            features['shots_diff'] = home_shots - away_shots
            features['home_shots_ratio'] = home_shots / (home_shots + away_shots + 0.01)
        
        if home_shots_on_target is not None and away_shots_on_target is not None:
            features['total_shots_on_target'] = home_shots_on_target + away_shots_on_target
            features['shots_on_target_diff'] = home_shots_on_target - away_shots_on_target
        
        if home_corners is not None and away_corners is not None:
            features['total_corners'] = home_corners + away_corners
        
        if home_possession is not None:
            features['home_possession'] = home_possession
            features['possession_diff'] = home_possession - 50
        
        if odds_home is not None and odds_draw is not None and odds_away is not None:
            features['odds_home'] = odds_home
            features['odds_draw'] = odds_draw
            features['odds_away'] = odds_away
            
            total_odds = 1/odds_home + 1/odds_draw + 1/odds_away
            features['implied_home'] = (1/odds_home) / total_odds
            features['implied_draw'] = (1/odds_draw) / total_odds
            features['implied_away'] = (1/odds_away) / total_odds
            features['odds_diff'] = odds_home - odds_away
        
        if home_fouls is not None and away_fouls is not None:
            features['total_fouls'] = home_fouls + away_fouls
        
        # 添加联赛特征
        features['is_small_league'] = 1 if is_small_league else 0
        features['league_avg_goals'] = league_avg_goals
        
        # 创建特征DataFrame
        X_pred = pd.DataFrame([features])
        
        # 确保所有特征列都存在
        for col in self.feature_columns:
            if col not in X_pred.columns:
                X_pred[col] = 0
        
        X_pred = X_pred[self.feature_columns]
        
        # 标准化
        X_pred_scaled = self.scaler.transform(X_pred)
        
        # 预测
        predicted = self.model.predict(X_pred_scaled)[0]
        predicted = max(0, predicted)  # 确保非负
        
        # 计算概率
        from scipy import stats
        
        # 小联赛使用更大的方差
        if is_small_league:
            std = self.metrics.get('rmse', 1.2) * SMALL_LEAGUE_ADJUSTMENTS['variance_multiplier']
        else:
            std = self.metrics.get('rmse', 1.2)
        
        over25_prob = 1 - stats.norm.cdf(2.5, predicted, std)
        under25_prob = stats.norm.cdf(2.5, predicted, std)
        over35_prob = 1 - stats.norm.cdf(3.5, predicted, std)
        under35_prob = stats.norm.cdf(3.5, predicted, std)
        
        # 计算信心
        confidence = self._calculate_confidence(predicted, 2.5, is_small_league)
        
        return AdvancedMLPrediction(
            predicted_total_goals=round(predicted, 2),
            over25_prob=round(over25_prob, 3),
            under25_prob=round(under25_prob, 3),
            over35_prob=round(over35_prob, 3),
            under35_prob=round(under35_prob, 3),
            confidence=confidence,
            model_type=self.model_type,
            feature_importance=self.feature_importance,
            metrics=self.metrics,
        )
    
    def _predict_with_league_model(
        self,
        league: str,
        home_xg: Optional[float],
        away_xg: Optional[float],
        home_shots: Optional[float],
        away_shots: Optional[float],
        home_shots_on_target: Optional[float],
        away_shots_on_target: Optional[float],
        home_possession: Optional[float],
        odds_home: Optional[float],
        odds_draw: Optional[float],
        odds_away: Optional[float],
        home_corners: Optional[float],
        away_corners: Optional[float],
        home_fouls: Optional[float],
        away_fouls: Optional[float],
    ) -> AdvancedMLPrediction:
        """使用联赛专属模型预测"""
        league_data = self.league_models[league]
        model = league_data['model']
        scaler = league_data['scaler']
        feature_columns = league_data['feature_columns']
        
        # 构建特征向量
        features = {}
        
        if home_xg is not None and away_xg is not None:
            features['total_xg'] = home_xg + away_xg
            features['xg_diff'] = home_xg - away_xg
            features['home_xg_ratio'] = home_xg / (home_xg + away_xg + 0.01)
        
        if home_shots is not None and away_shots is not None:
            features['total_shots'] = home_shots + away_shots
            features['shots_diff'] = home_shots - away_shots
            features['home_shots_ratio'] = home_shots / (home_shots + away_shots + 0.01)
        
        if home_shots_on_target is not None and away_shots_on_target is not None:
            features['total_shots_on_target'] = home_shots_on_target + away_shots_on_target
            features['shots_on_target_diff'] = home_shots_on_target - away_shots_on_target
        
        if home_corners is not None and away_corners is not None:
            features['total_corners'] = home_corners + away_corners
        
        if home_possession is not None:
            features['home_possession'] = home_possession
            features['possession_diff'] = home_possession - 50
        
        if odds_home is not None and odds_draw is not None and odds_away is not None:
            features['odds_home'] = odds_home
            features['odds_draw'] = odds_draw
            features['odds_away'] = odds_away
            
            total_odds = 1/odds_home + 1/odds_draw + 1/odds_away
            features['implied_home'] = (1/odds_home) / total_odds
            features['implied_draw'] = (1/odds_draw) / total_odds
            features['implied_away'] = (1/odds_away) / total_odds
            features['odds_diff'] = odds_home - odds_away
        
        if home_fouls is not None and away_fouls is not None:
            features['total_fouls'] = home_fouls + away_fouls
        
        # 添加联赛特征
        league_info = self.league_stats.get(league, {})
        features['is_small_league'] = 1
        features['league_avg_goals'] = league_info.get('avg_goals', 2.5)
        
        # 创建特征DataFrame
        X_pred = pd.DataFrame([features])
        
        # 确保所有特征列都存在
        for col in feature_columns:
            if col not in X_pred.columns:
                X_pred[col] = 0
        
        X_pred = X_pred[feature_columns]
        
        # 标准化
        X_pred_scaled = scaler.transform(X_pred)
        
        # 预测
        predicted = model.predict(X_pred_scaled)[0]
        predicted = max(0, predicted)  # 确保非负
        
        # 计算概率（使用联赛专属MAE）
        from scipy import stats
        mae = league_data.get('mae', 1.2)
        std = mae * SMALL_LEAGUE_ADJUSTMENTS['variance_multiplier']
        
        over25_prob = 1 - stats.norm.cdf(2.5, predicted, std)
        under25_prob = stats.norm.cdf(2.5, predicted, std)
        over35_prob = 1 - stats.norm.cdf(3.5, predicted, std)
        under35_prob = stats.norm.cdf(3.5, predicted, std)
        
        # 计算信心（小联赛降低）
        confidence = self._calculate_confidence(predicted, 2.5, is_small_league=True)
        
        return AdvancedMLPrediction(
            predicted_total_goals=round(predicted, 2),
            over25_prob=round(over25_prob, 3),
            under25_prob=round(under25_prob, 3),
            over35_prob=round(over35_prob, 3),
            under35_prob=round(under35_prob, 3),
            confidence=confidence,
            model_type=f"league_specific_{league}",
            feature_importance={},
            metrics={'mae': mae},
        )
    
    def _predict_rule_based(
        self,
        home_xg: Optional[float],
        away_xg: Optional[float],
        league_avg_goals: float,
        is_small_league: bool = False
    ) -> AdvancedMLPrediction:
        """基于规则的预测"""
        
        if home_xg is not None and away_xg is not None:
            predicted = (home_xg + away_xg) / 2 + league_avg_goals / 2
        else:
            predicted = league_avg_goals
        
        # 小联赛使用更大的方差
        if is_small_league:
            std = 1.2 * SMALL_LEAGUE_ADJUSTMENTS['variance_multiplier']
        else:
            std = 1.2
        
        from scipy import stats
        
        over25_prob = 1 - stats.norm.cdf(2.5, predicted, std)
        under25_prob = stats.norm.cdf(2.5, predicted, std)
        over35_prob = 1 - stats.norm.cdf(3.5, predicted, std)
        under35_prob = stats.norm.cdf(3.5, predicted, std)
        
        confidence = self._calculate_confidence(predicted, 2.5, is_small_league)
        
        return AdvancedMLPrediction(
            predicted_total_goals=round(predicted, 2),
            over25_prob=round(over25_prob, 3),
            under25_prob=round(under25_prob, 3),
            over35_prob=round(over35_prob, 3),
            under35_prob=round(under35_prob, 3),
            confidence=confidence,
            model_type="rule_based",
            feature_importance={},
            metrics={},
        )
    
    def _calculate_confidence(self, predicted: float, line: float, is_small_league: bool = False) -> int:
        """计算信心等级"""
        diff = abs(predicted - line)
        
        if diff > 1.0:
            base_confidence = 5
        elif diff > 0.75:
            base_confidence = 4
        elif diff > 0.5:
            base_confidence = 3
        elif diff > 0.25:
            base_confidence = 2
        else:
            base_confidence = 1
        
        # 小联赛调整
        if is_small_league:
            base_confidence += SMALL_LEAGUE_ADJUSTMENTS['confidence_penalty']
            base_confidence = max(SMALL_LEAGUE_ADJUSTMENTS['min_confidence'], 
                                 min(SMALL_LEAGUE_ADJUSTMENTS['max_confidence'], base_confidence))
        
        return base_confidence
    
    def save_model(self, path: str):
        """保存模型"""
        import pickle
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_columns': self.feature_columns,
            'model_type': self.model_type,
            'feature_importance': self.feature_importance,
            'metrics': self.metrics,
        }
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
        print(f"模型已保存: {path}")
    
    def load_model(self, path: str):
        """加载模型"""
        import pickle
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_columns = model_data['feature_columns']
        self.model_type = model_data['model_type']
        self.feature_importance = model_data['feature_importance']
        self.metrics = model_data['metrics']
        self.is_trained = True
        print(f"模型已加载: {path}")


# 测试
if __name__ == "__main__":
    model = AdvancedOverUnderModel()
    
    # 测试基础预测（无训练数据）
    print("=== 基础预测测试 ===")
    result = model.predict(
        home_xg=1.2,
        away_xg=0.8,
        league_avg_goals=2.6,
    )
    print(f"预测总进球: {result.predicted_total_goals}")
    print(f"大2.5概率: {result.over25_prob:.1%}")
    print(f"小2.5概率: {result.under25_prob:.1%}")
    print(f"信心: {'⭐' * result.confidence}")
    print(f"模型类型: {result.model_type}")
    print()
    
    # 尝试训练模型
    print("=== 训练模型测试 ===")
    import os
    data_path = "D:/ai/电脑庄家/足球竞猜模型训练/data/raw/mls_matches.csv"
    if os.path.exists(data_path):
        metrics = model.train(data_path, model_type="xgboost")
        if metrics:
            print(f"训练指标: {metrics}")
            
            # 训练后预测
            result2 = model.predict(
                home_xg=1.5,
                away_xg=1.2,
                odds_home=2.1,
                odds_draw=3.5,
                odds_away=3.2,
            )
            print(f"\n训练后预测:")
            print(f"  预测总进球: {result2.predicted_total_goals}")
            print(f"  大2.5概率: {result2.over25_prob:.1%}")
            print(f"  模型类型: {result2.model_type}")
            print(f"  特征重要性: {result2.feature_importance}")
    else:
        print(f"数据文件不存在: {data_path}")
