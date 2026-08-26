"""
足球竞猜策略 v2.0
包含：大小球预测、让球策略、信心等级对齐
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MatchType(Enum):
    """比赛类型"""
    FRIENDLY = "友谊赛"
    YOUTH_U20 = "U20青年联赛"
    YOUTH_U23 = "U23青年联赛"
    DOMESTIC = "国内联赛"
    DOMESTIC_CUP = "国内杯赛"
    CONTINENTAL = "洲际赛事"
    SMALL_LEAGUE = "小联赛"


# 小联赛列表（数据质量差，预测可信度低）
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
]


# 小球特征联赛 (场均进球低, 大小球盘口应下探)
SMALL_BALL_LEAGUES = {
    "中乙": {"avg_goals": 1.32, "over25": 25, "over35": 10},
    "中乙联赛": {"avg_goals": 1.32, "over25": 25, "over35": 10},
}


class BetRecommendation(Enum):
    """投注推荐"""
    OVER = "大球"
    UNDER = "小球"
    WATCH = "观望"
    NO_BET = "不推荐"


@dataclass
class LeagueStats:
    """联赛统计数据"""
    name: str
    avg_goals: float
    over25_rate: float
    over35_rate: float
    home_advantage: float = 1.1  # 主场进球系数


@dataclass
class MatchAnalysis:
    """比赛分析结果"""
    match_name: str
    league: str
    match_type: MatchType
    
    # 大小球分析
    ou_recommendation: BetRecommendation
    ou_confidence: int  # 1-5星
    ou_line: float
    ou_odds_over: float
    ou_odds_under: float
    ou_reason: str
    
    # 让球分析
    hdp_recommendation: BetRecommendation
    hdp_confidence: int
    hdp_line: float
    hdp_odds_home: float
    hdp_odds_away: float
    hdp_reason: str
    
    # 综合
    total_confidence: int
    kelly_fraction: float


class OverUnderModel:
    """大小球预测模型"""
    
    def __init__(self):
        self.league_stats = self._load_league_stats()
    
    def _load_league_stats(self) -> Dict[str, LeagueStats]:
        """加载联赛统计数据"""
        return {
            "中超": LeagueStats("中超", 2.6, 55, 30, 1.08),
            "MLS": LeagueStats("MLS", 3.0, 60, 40, 1.1),
            "MLS Next Pro": LeagueStats("MLS Next Pro", 3.42, 66, 45, 1.12),
            "澳大利亚NPL": LeagueStats("澳大利亚NPL", 3.76, 77, 56, 1.1),
            "澳大利亚Queensland U23": LeagueStats("澳大利亚Queensland U23", 4.01, 76, 56, 1.15),
            "澳大利亚Queensland NPL": LeagueStats("澳大利亚Queensland NPL", 3.76, 77, 56, 1.1),
            "澳大利亚NSW联赛U20": LeagueStats("澳大利亚NSW联赛U20", 3.8, 72, 52, 1.12),
            "澳大利亚Victoria U23": LeagueStats("澳大利亚Victoria U23", 3.9, 74, 54, 1.13),
            "球会友谊赛": LeagueStats("球会友谊赛", 2.8, 52, 32, 1.05),
            "巴西甲级联赛": LeagueStats("巴西甲级联赛", 2.5, 50, 28, 1.08),
            "俄罗斯联赛U19": LeagueStats("俄罗斯联赛U19", 3.2, 60, 40, 1.1),
            "印度锡金超级联赛": LeagueStats("印度锡金超级联赛", 3.0, 58, 38, 1.08),
            "澳大利亚首都特区国家超级联赛U23": LeagueStats("澳大利亚首都特区国家超级联赛U23", 3.5, 65, 45, 1.1),
            "新西兰北部联赛": LeagueStats("新西兰北部联赛", 3.0, 58, 38, 1.08),
            "乌克兰甲级联赛": LeagueStats("乌克兰甲级联赛", 2.8, 52, 30, 1.08),
            "危地马拉联赛": LeagueStats("危地马拉联赛", 2.9, 55, 32, 1.08),
            "墨西哥甲级联赛": LeagueStats("墨西哥甲级联赛", 2.7, 52, 30, 1.08),
            # 丹麦杯 (DBU Pokalen) - 杯赛，高进球，强队重视
            "丹麦杯": LeagueStats("丹麦杯", 3.28, 78, 51, 1.22),
            # 中乙 (CL2) - 中国第3级别，全华班，小球闷平极高
            "中乙": LeagueStats("中乙", 1.32, 25, 10, 1.20),
            "中乙联赛": LeagueStats("中乙联赛", 1.32, 25, 10, 1.20),
            # 韩国K2 - 中等进球, 主客场差距极小, 客场爆冷常态 (2026真值)
            "韩国K2联赛": LeagueStats("韩国K2联赛", 2.82, 57, 27.4, 1.02),
            "K2联赛": LeagueStats("K2联赛", 2.82, 57, 27.4, 1.02),
            "韩K2": LeagueStats("韩K2", 2.82, 57, 27.4, 1.02),
            "K联赛2": LeagueStats("K联赛2", 2.82, 57, 27.4, 1.02),
            "K League 2": LeagueStats("K League 2", 2.82, 57, 27.4, 1.02),
            # 日本J1 - 2026-27跨年新规(外援5人/取消U23强制), 开季20场实测场均3.35/大2.5=70%/主客中性 (官方2.40已弃用)
            "日本J1联赛": LeagueStats("日本J1联赛", 3.35, 70, 40, 1.00),  # 2026-27新规实测(20场): 场均3.35/大2.5=70%
            "J1联赛": LeagueStats("J1联赛", 3.35, 70, 40, 1.00),
            "日职联": LeagueStats("日职联", 3.35, 70, 40, 1.00),
            "日本J联赛": LeagueStats("日本J联赛", 3.35, 70, 40, 1.00),
            "J1": LeagueStats("J1", 3.35, 70, 40, 1.00),
            "J League": LeagueStats("J League", 3.35, 70, 40, 1.00),
            # 欧联资格赛 (Europa League Qualifying) - 首回合保守+强弱分化
            "欧联资格赛": LeagueStats("欧联资格赛", 2.9, 56, 32, 1.15),
            "欧联": LeagueStats("欧联", 2.9, 56, 32, 1.15),
            "欧联杯": LeagueStats("欧联杯", 2.9, 56, 32, 1.15),
            "欧协联资格赛": LeagueStats("欧协联资格赛", 2.7, 50, 28, 1.15),
            "欧协联": LeagueStats("欧协联", 2.7, 50, 28, 1.15),
            "欧协联杯": LeagueStats("欧协联杯", 2.7, 50, 28, 1.15),
            "欧冠资格赛": LeagueStats("欧冠资格赛", 2.8, 55, 30, 1.15),
        }
    
    def predict(
        self,
        league: str,
        ou_line: float,
        ou_odds_over: float,
        ou_odds_under: float,
        match_type: MatchType = MatchType.DOMESTIC,
        home_avg_goals: Optional[float] = None,
        away_avg_goals: Optional[float] = None,
    ) -> Tuple[BetRecommendation, int, str]:
        """
        大小球预测
        
        返回: (推荐, 信心等级, 原因)
        """
        # 获取联赛统计
        if league not in self.league_stats:
            return BetRecommendation.WATCH, 2, f"无{league}数据"
        
        stats = self.league_stats[league]
        avg_goals = stats.avg_goals
        
        # 判断是否为小联赛
        is_small_league = league in SMALL_LEAGUES
        
        # 计算盘口与联赛场均比值
        ratio = ou_line / avg_goals
        
        # 基础判断（细调后的阈值）
        if is_small_league:
            # 小联赛：更严格的阈值（细调后）
            over_threshold = 0.70  # 细调: 0.75 -> 0.70
            under_threshold = 1.30  # 细调: 1.25 -> 1.30
        else:
            # 主流联赛：微调阈值
            over_threshold = 0.80  # 细调: 0.85 -> 0.80
            under_threshold = 1.20  # 细调: 1.15 -> 1.20
        
        if ratio < over_threshold:
            recommendation = BetRecommendation.OVER
            base_confidence = 4
            reason = f"盘口{ou_line}低于联赛场均{avg_goals}球（比值{ratio:.2f}）"
        elif ratio > under_threshold:
            recommendation = BetRecommendation.UNDER
            base_confidence = 4
            reason = f"盘口{ou_line}高于联赛场均{avg_goals}球（比值{ratio:.2f}）"
        else:
            recommendation = BetRecommendation.WATCH
            base_confidence = 2
            reason = f"盘口{ou_line}接近联赛场均{avg_goals}球（比值{ratio:.2f}）"
        
        # 信心调整
        confidence = base_confidence
        
        # 盘口差异调整
        diff = avg_goals - ou_line
        if abs(diff) > 0.5:
            confidence += 1
        
        # 水位调整
        avg_odds = (ou_odds_over + ou_odds_under) / 2
        if avg_odds < 1.85:
            confidence += 1
        elif avg_odds > 2.05:
            confidence -= 1
        
        # 比赛类型调整
        if match_type == MatchType.FRIENDLY:
            confidence -= 1
            reason += "（友谊赛，降低信心）"
        elif match_type in [MatchType.YOUTH_U20, MatchType.YOUTH_U23]:
            pass  # 不调整
        
        # 小联赛调整（细调后）
        if is_small_league:
            confidence -= 2  # 细调: -1 -> -2
            reason += "（小联赛，大幅降低信心）"
        
        # 球队数据调整（如果有）
        if home_avg_goals and away_avg_goals:
            expected_total = (home_avg_goals + away_avg_goals) / 2
            if abs(expected_total - ou_line) > 0.3:
                confidence += 1
                reason += f"，两队场均进球{expected_total:.1f}球"
        
        # 限制范围
        confidence = max(1, min(5, confidence))
        
        return recommendation, confidence, reason


class HandicapStrategy:
    """让球策略"""
    
    def __init__(self):
        self.ou_model = OverUnderModel()
    
    def predict(
        self,
        league: str,
        match_type: MatchType,
        odds_home: float,
        odds_draw: float,
        odds_away: float,
        hdp_line: float,
        hdp_odds_home: float,
        hdp_odds_away: float,
        model_home_prob: Optional[float] = None,
        model_draw_prob: Optional[float] = None,
        model_away_prob: Optional[float] = None,
    ) -> Tuple[BetRecommendation, int, str]:
        """
        让球预测
        
        返回: (推荐, 信心等级, 原因)
        """
        # 友谊赛不推荐让球
        if match_type == MatchType.FRIENDLY:
            return BetRecommendation.NO_BET, 1, "友谊赛不推荐让球"
        
        # 判断是否为小联赛
        is_small_league = league in SMALL_LEAGUES
        
        # 计算赔率隐含概率
        total_odds = 1/odds_home + 1/odds_draw + 1/odds_away
        implied_home = (1/odds_home) / total_odds
        implied_draw = (1/odds_draw) / total_odds
        implied_away = (1/odds_away) / total_odds
        
        # 使用模型概率（如果有）
        if model_home_prob is not None:
            home_prob = model_home_prob
            draw_prob = model_draw_prob
            away_prob = model_away_prob
        else:
            home_prob = implied_home
            draw_prob = implied_draw
            away_prob = implied_away
        
        # 让球盘口分析
        abs_line = abs(hdp_line)
        
        # 判断让球方向
        if hdp_line < 0:
            # 主队让球
            favored_team = "主队"
            favored_prob = home_prob
            underdog_prob = away_prob
            hdp_odds_favored = hdp_odds_home
        else:
            # 客队让球
            favored_team = "客队"
            favored_prob = away_prob
            underdog_prob = home_prob
            hdp_odds_favored = hdp_odds_away
        
        # 计算价值
        # 让球后的等效概率
        if abs_line <= 0.25:
            # 平手/平半，让球方需要赢才能赢盘
            favored_cover_prob = favored_prob * 0.9  # 约90%的情况
        elif abs_line <= 0.5:
            # 半球，让球方需要净胜1球
            favored_cover_prob = favored_prob * 0.7
        elif abs_line <= 0.75:
            # 半/一，让球方需要净胜1球全赢，净胜半球赢半
            favored_cover_prob = favored_prob * 0.6
        elif abs_line <= 1.0:
            # 一球，让球方需要净胜2球全赢
            favored_cover_prob = favored_prob * 0.5
        else:
            # 深盘，让球方需要净胜更多
            favored_cover_prob = favored_prob * 0.4
        
        # 计算期望值
        expected_value = favored_cover_prob * hdp_odds_favored - 1
        
        # 判断推荐
        if expected_value > 0.05:
            # 有价值，推荐让球方
            recommendation = BetRecommendation.OVER if hdp_line < 0 else BetRecommendation.UNDER
            confidence = 4 if expected_value > 0.1 else 3
            reason = f"{favored_team}让{abs_line}球，期望值{expected_value:.1%}，有价值"
        elif expected_value < -0.05:
            # 价值为负，推荐受让方
            recommendation = BetRecommendation.UNDER if hdp_line < 0 else BetRecommendation.OVER
            confidence = 4 if expected_value < -0.1 else 3
            reason = f"{favored_team}让{abs_line}球，期望值{expected_value:.1%}，受让方有价值"
        else:
            recommendation = BetRecommendation.WATCH
            confidence = 2
            reason = f"{favored_team}让{abs_line}球，期望值{expected_value:.1%}，无明显价值"
        
        # 深盘调整
        if abs_line > 1.0:
            confidence -= 1
            reason += "（深盘，降低信心）"
        
        # 小联赛调整（细调后）
        if is_small_league:
            confidence -= 2  # 细调: -1 -> -2
            reason += "（小联赛，大幅降低信心）"
        
        # 限制范围
        confidence = max(1, min(5, confidence))
        
        return recommendation, confidence, reason


class ConfidenceAligner:
    """信心等级对齐器"""
    
    @staticmethod
    def align(
        model_prob: float,
        bet_type: str,
        odds: float,
        league_type: str = "domestic"
    ) -> int:
        """
        根据模型概率对齐信心等级
        
        返回: 1-5星
        """
        # 计算期望值
        implied_prob = 1 / odds
        expected_value = model_prob - implied_prob
        
        # 基础信心
        if expected_value > 0.15:
            base = 5
        elif expected_value > 0.10:
            base = 4
        elif expected_value > 0.05:
            base = 3
        elif expected_value > 0:
            base = 2
        else:
            base = 1
        
        # 联赛类型调整
        if league_type == "friendly":
            base -= 1
        elif league_type in ["youth_u20", "youth_u23"]:
            base -= 0  # 不调整
        elif league_type == "small_league":
            base -= 1  # 小联赛降低信心
        
        return max(1, min(5, base))


class KellyCalculator:
    """凯利指数计算器"""
    
    @staticmethod
    def calculate(
        win_prob: float,
        odds: float,
        fraction: float = 0.25
    ) -> float:
        """
        计算凯利指数
        
        参数:
            win_prob: 胜率
            odds: 赔率
            fraction: 凯利比例（保守系数）
        
        返回: 推注比例（0-1）
        """
        # 凯利公式
        q = 1 - win_prob
        b = odds - 1
        
        kelly = (win_prob * b - q) / b
        
        # 应用保守系数
        kelly = kelly * fraction
        
        # 限制范围
        return max(0, min(0.25, kelly))


class StrategyEngine:
    """策略引擎"""
    
    def __init__(self):
        self.ou_model = OverUnderModel()
        self.hdp_strategy = HandicapStrategy()
        self.confidence_aligner = ConfidenceAligner()
        self.kelly_calc = KellyCalculator()
    
    def analyze_match(
        self,
        match_name: str,
        league: str,
        match_type: MatchType,
        odds_home: float,
        odds_draw: float,
        odds_away: float,
        ou_line: float,
        ou_odds_over: float,
        ou_odds_under: float,
        hdp_line: float,
        hdp_odds_home: float,
        hdp_odds_away: float,
        model_home_prob: Optional[float] = None,
        model_draw_prob: Optional[float] = None,
        model_away_prob: Optional[float] = None,
    ) -> MatchAnalysis:
        """
        完整比赛分析
        """
        # 大小球分析
        ou_rec, ou_conf, ou_reason = self.ou_model.predict(
            league=league,
            ou_line=ou_line,
            ou_odds_over=ou_odds_over,
            ou_odds_under=ou_odds_under,
            match_type=match_type,
        )
        
        # 让球分析
        hdp_rec, hdp_conf, hdp_reason = self.hdp_strategy.predict(
            league=league,
            match_type=match_type,
            odds_home=odds_home,
            odds_draw=odds_draw,
            odds_away=odds_away,
            hdp_line=hdp_line,
            hdp_odds_home=hdp_odds_home,
            hdp_odds_away=hdp_odds_away,
            model_home_prob=model_home_prob,
            model_draw_prob=model_draw_prob,
            model_away_prob=model_away_prob,
        )
        
        # 综合信心
        total_confidence = (ou_conf + hdp_conf) // 2
        
        # 凯利指数
        if ou_rec == BetRecommendation.OVER:
            kelly = self.kelly_calc.calculate(
                win_prob=0.6,  # 假设大球胜率60%
                odds=ou_odds_over,
            )
        elif ou_rec == BetRecommendation.UNDER:
            kelly = self.kelly_calc.calculate(
                win_prob=0.6,
                odds=ou_odds_under,
            )
        else:
            kelly = 0
        
        return MatchAnalysis(
            match_name=match_name,
            league=league,
            match_type=match_type,
            ou_recommendation=ou_rec,
            ou_confidence=ou_conf,
            ou_line=ou_line,
            ou_odds_over=ou_odds_over,
            ou_odds_under=ou_odds_under,
            ou_reason=ou_reason,
            hdp_recommendation=hdp_rec,
            hdp_confidence=hdp_conf,
            hdp_line=hdp_line,
            hdp_odds_home=hdp_odds_home,
            hdp_odds_away=hdp_odds_away,
            hdp_reason=hdp_reason,
            total_confidence=total_confidence,
            kelly_fraction=kelly,
        )


def format_analysis(analysis: MatchAnalysis) -> str:
    """格式化分析结果"""
    lines = [
        f"⚽ {analysis.match_name} ({analysis.league})",
        f"",
        f"📊 大小球:",
        f"  推荐: {analysis.ou_recommendation.value} @",
        f"  盘口: {analysis.ou_line}球",
        f"  赔率: 大{analysis.ou_odds_over} / 小{analysis.ou_odds_under}",
        f"  信心: {'⭐' * analysis.ou_confidence}",
        f"  原因: {analysis.ou_reason}",
        f"",
        f"📈 让球:",
        f"  推荐: {analysis.hdp_recommendation.value}",
        f"  盘口: {analysis.hdp_line}",
        f"  赔率: 主{analysis.hdp_odds_home} / 客{analysis.hdp_odds_away}",
        f"  信心: {'⭐' * analysis.hdp_confidence}",
        f"  原因: {analysis.hdp_reason}",
        f"",
        f"🎯 综合: {'⭐' * analysis.total_confidence}",
        f"💰 凯利: {analysis.kelly_fraction:.1%}",
    ]
    return "\n".join(lines)


# 测试
if __name__ == "__main__":
    engine = StrategyEngine()
    
    # 测试1: 河南队 vs 大连英博
    analysis1 = engine.analyze_match(
        match_name="河南队 vs 大连英博",
        league="中超",
        match_type=MatchType.DOMESTIC,
        odds_home=1.80,
        odds_draw=3.85,
        odds_away=3.65,
        ou_line=3.0,
        ou_odds_over=1.84,
        ou_odds_under=2.00,
        hdp_line=-0.5,
        hdp_odds_home=1.80,
        hdp_odds_away=2.06,
    )
    print(format_analysis(analysis1))
    print("\n" + "="*50 + "\n")
    
    # 测试2: 普罗斯佩联U20 vs 黑镇斯巴达U20
    analysis2 = engine.analyze_match(
        match_name="普罗斯佩联U20 vs 黑镇斯巴达U20",
        league="澳大利亚NSW联赛U20",
        match_type=MatchType.YOUTH_U20,
        odds_home=1.54,
        odds_draw=4.30,
        odds_away=4.10,
        ou_line=3.5,
        ou_odds_over=1.99,
        ou_odds_under=1.79,
        hdp_line=-1.0,
        hdp_odds_home=1.91,
        hdp_odds_away=1.87,
    )
    print(format_analysis(analysis2))
