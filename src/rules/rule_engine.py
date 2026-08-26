"""
足球预测规则引擎 - 基于162条规则系统
集成可自动化的规则到预测流程中
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class RuleSignal:
    rule_id: str
    name: str
    triggered: bool
    strength: int  # -2 to +2 (negative = against home team)
    confidence: float  # 0-1
    reason: str

class FootballRuleEngine:
    def __init__(self):
        self.rules = {}
        self._init_rules()
    
    def _init_rules(self):
        """初始化所有可自动化的规则"""
        # 盘口赔率信号规则
        self.rules['R1'] = self._rule_R1  # 退盘=降信心
        self.rules['R2'] = self._rule_R2  # 升水=不看好
        self.rules['R3'] = self._rule_R3  # 变盘方向即倾向
        self.rules['R7'] = self._rule_R7  # 平赔暴跌=资金涌平局
        self.rules['R9'] = self._rule_R9  # 让步不足
        self.rules['R69'] = self._rule_R69  # 真硬不演盘口
        self.rules['R70'] = self._rule_R70  # 欧赔结构方向铁律
        
        # 量化模型规则
        self.rules['R49'] = self._rule_R49  # ELO→公平亚盘转换
        self.rules['R50'] = self._rule_R50  # 公平盘vs实际盘差值
        self.rules['R52'] = self._rule_R52  # ELO评分体系
        self.rules['R119'] = self._rule_R119  # 赔率偏差量化信号
        self.rules['R120'] = self._rule_R120  # 熵差系数
        
        # 大小球规则
        self.rules['R46'] = self._rule_R46  # 大小球锚定比分池
        self.rules['R47'] = self._rule_R47  # 进球数赔率交叉验证
        self.rules['R48'] = self._rule_R48  # 大小球变盘=进球修正
        
        # 资金风控规则
        self.rules['R117'] = self._rule_R117  # 让平集中度≤50%
        self.rules['R118'] = self._rule_R118  # 碾压+低赔让胜不可逆
        self.rules['R154'] = self._rule_R154  # 让平限流纪律
        
        # 分析纪律规则
        self.rules['R105'] = self._rule_R105  # 双面验证强制+净值量化
        self.rules['R107'] = self._rule_R107  # 全局优先级仲裁
    
    def analyze_match(self, match_data: Dict) -> Dict:
        """
        分析单场比赛，返回所有触发的规则信号
        
        match_data需要包含:
        - home_team, away_team
        - home_elo, away_elo
        - odds_home, odds_draw, odds_away (当前赔率)
        - pinnacle_home, pinnacle_draw, pinnacle_away (Pinnacle赔率)
        - odds_home_initial, odds_draw_initial, odds_away_initial (初盘赔率)
        - home_goals, away_goals (历史数据)
        """
        signals = []
        
        # 执行所有规则
        for rule_id, rule_func in self.rules.items():
            try:
                signal = rule_func(match_data)
                if signal and signal.triggered:
                    signals.append(signal)
            except Exception as e:
                print(f"Rule {rule_id} error: {e}")
        
        # 计算综合信号
        total_strength = sum(s.strength for s in signals)
        avg_confidence = np.mean([s.confidence for s in signals]) if signals else 0
        
        # 判断方向
        if total_strength > 0:
            direction = "home"
        elif total_strength < 0:
            direction = "away"
        else:
            direction = "draw"
        
        return {
            'signals': signals,
            'total_strength': total_strength,
            'avg_confidence': avg_confidence,
            'direction': direction,
            'n_signals': len(signals)
        }
    
    # ============================================================
    # 盘口赔率信号规则
    # ============================================================
    
    def _rule_R1(self, data: Dict) -> RuleSignal:
        """R1: 退盘=降信心 - 主队退盘说明机构对主队赢球信心下降"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_home_initial' in data and 'odds_home' in data:
            # 赔率上升 = 退盘
            odds_change = data['odds_home'] - data['odds_home_initial']
            if odds_change > 0.25:  # 退盘阈值
                triggered = True
                strength = -1
                confidence = min(0.8, 0.5 + odds_change * 0.5)
                reason = f"主胜赔率上升{odds_change:.2f}，退盘信号"
        
        return RuleSignal('R1', '退盘=降信心', triggered, strength, confidence, reason)
    
    def _rule_R2(self, data: Dict) -> RuleSignal:
        """R2: 升水=不看好 - 主队水位持续升高，主胜风险加大"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_home_initial' in data and 'odds_home' in data:
            odds_change = data['odds_home'] - data['odds_home_initial']
            if odds_change > 0.15:  # 升水阈值
                triggered = True
                strength = -1
                confidence = min(0.7, 0.5 + odds_change * 0.3)
                reason = f"主胜赔率持续上升，升水信号"
        
        return RuleSignal('R2', '升水=不看好', triggered, strength, confidence, reason)
    
    def _rule_R3(self, data: Dict) -> RuleSignal:
        """R3: 变盘方向即倾向 - 盘口变化方向=机构真实倾向"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_home_initial' in data and 'odds_home' in data:
            odds_change = data['odds_home'] - data['odds_home_initial']
            if abs(odds_change) > 0.1:
                triggered = True
                if odds_change > 0:
                    strength = -1
                    reason = f"主胜赔率上升{odds_change:.2f}，倾向客队"
                else:
                    strength = 1
                    reason = f"主胜赔率下降{abs(odds_change):.2f}，倾向主队"
                confidence = min(0.7, 0.5 + abs(odds_change) * 0.2)
        
        return RuleSignal('R3', '变盘方向即倾向', triggered, strength, confidence, reason)
    
    def _rule_R7(self, data: Dict) -> RuleSignal:
        """R7: 平赔暴跌=资金涌平局"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_draw_initial' in data and 'odds_draw' in data:
            draw_change = data['odds_draw_initial'] - data['odds_draw']
            if draw_change > 0.20:  # 平赔下降阈值
                triggered = True
                strength = 0  # 平局方向
                confidence = min(0.8, 0.5 + draw_change * 0.5)
                reason = f"平赔下降{draw_change:.2f}，资金涌入平局"
        
        return RuleSignal('R7', '平赔暴跌=资金涌平局', triggered, strength, confidence, reason)
    
    def _rule_R9(self, data: Dict) -> RuleSignal:
        """R9: 让步不足 - 强队只让平手/0.25=机构不认为能赢"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            if elo_diff > 100:  # 主队明显更强
                # 检查赔率是否反映不出优势
                if 'odds_home' in data and data['odds_home'] > 2.0:
                    triggered = True
                    strength = -1
                    confidence = 0.6
                    reason = f"ELO差{elo_diff:.0f}但主胜赔率{data['odds_home']:.2f}，让步不足"
        
        return RuleSignal('R9', '让步不足', triggered, strength, confidence, reason)
    
    def _rule_R69(self, data: Dict) -> RuleSignal:
        """R69: 真硬不演盘口 - 极低胜赔+平负双高=真信主胜"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'odds_draw', 'odds_away']):
            if data['odds_home'] <= 1.30 and data['odds_draw'] >= 4.0 and data['odds_away'] >= 8.0:
                triggered = True
                strength = 2
                confidence = 0.85
                reason = f"主胜{data['odds_home']:.2f}+平{data['odds_draw']:.1f}+负{data['odds_away']:.1f}，真硬盘"
        
        return RuleSignal('R69', '真硬不演盘口', triggered, strength, confidence, reason)
    
    def _rule_R70(self, data: Dict) -> RuleSignal:
        """R70: 欧赔结构方向铁律 - 高胜+低负=走客队"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'odds_draw', 'odds_away']):
            if (data['odds_home'] >= 2.0 and 
                data['odds_away'] <= data['odds_home'] and 
                data['odds_away'] <= data['odds_draw']):
                triggered = True
                strength = -1
                confidence = 0.7
                reason = f"主胜{data['odds_home']:.2f}高+客胜{data['odds_away']:.2f}低，倾向客队"
        
        return RuleSignal('R70', '欧赔结构方向铁律', triggered, strength, confidence, reason)
    
    # ============================================================
    # 量化模型规则
    # ============================================================
    
    def _rule_R49(self, data: Dict) -> RuleSignal:
        """R49: ELO→公平亚盘转换"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            # ELO差转胜率
            win_prob = 1 / (1 + 10 ** (-elo_diff / 400))
            
            # 转换为公平赔率
            fair_odds = 1 / win_prob
            
            if 'odds_home' in data:
                odds_diff = fair_odds - data['odds_home']
                if abs(odds_diff) > 0.2:
                    triggered = True
                    if odds_diff > 0:
                        strength = 1
                        reason = f"公平赔率{fair_odds:.2f}>实际{data['odds_home']:.2f}，主队被低估"
                    else:
                        strength = -1
                        reason = f"公平赔率{fair_odds:.2f}<实际{data['odds_home']:.2f}，主队被高估"
                    confidence = min(0.7, 0.5 + abs(odds_diff) * 0.3)
        
        return RuleSignal('R49', 'ELO公平盘', triggered, strength, confidence, reason)
    
    def _rule_R50(self, data: Dict) -> RuleSignal:
        """R50: 公平盘vs实际盘差值"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data and 'odds_home' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            win_prob = 1 / (1 + 10 ** (-elo_diff / 400))
            fair_odds = 1 / win_prob
            
            diff = data['odds_home'] - fair_odds
            
            if diff > 0.5:
                triggered = True
                strength = -1
                confidence = 0.7
                reason = f"实际盘{data['odds_home']:.2f}浅开{diff:.2f}，主队被高估"
            elif diff < -0.5:
                triggered = True
                strength = 1
                confidence = 0.7
                reason = f"实际盘{data['odds_home']:.2f}深开{abs(diff):.2f}，主队被低估"
        
        return RuleSignal('R50', '公平盘vs实际盘', triggered, strength, confidence, reason)
    
    def _rule_R52(self, data: Dict) -> RuleSignal:
        """R52: ELO评分体系 - 差100≈64%胜率"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            win_prob = 1 / (1 + 10 ** (-elo_diff / 400))
            
            if elo_diff > 200:
                triggered = True
                strength = 2
                confidence = 0.8
                reason = f"ELO差{elo_diff:.0f}，主队碾压级优势({win_prob:.1%})"
            elif elo_diff > 100:
                triggered = True
                strength = 1
                confidence = 0.7
                reason = f"ELO差{elo_diff:.0f}，主队明显优势({win_prob:.1%})"
            elif elo_diff < -200:
                triggered = True
                strength = -2
                confidence = 0.8
                reason = f"ELO差{elo_diff:.0f}，客队碾压级优势({1-win_prob:.1%})"
            elif elo_diff < -100:
                triggered = True
                strength = -1
                confidence = 0.7
                reason = f"ELO差{elo_diff:.0f}，客队明显优势({1-win_prob:.1%})"
        
        return RuleSignal('R52', 'ELO评分体系', triggered, strength, confidence, reason)
    
    def _rule_R119(self, data: Dict) -> RuleSignal:
        """R119: 赔率偏差量化信号"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'pinnacle_home']):
            deviation = abs(data['odds_home'] - data['pinnacle_home']) / data['pinnacle_home'] * 100
            
            if deviation >= 5:
                triggered = True
                if data['odds_home'] > data['pinnacle_home']:
                    strength = -2
                    reason = f"赔率偏差{deviation:.1f}%≥5%，主胜被高估"
                else:
                    strength = 2
                    reason = f"赔率偏差{deviation:.1f}%≥5%，主胜被低估"
                confidence = 0.8
            elif deviation >= 3:
                triggered = True
                if data['odds_home'] > data['pinnacle_home']:
                    strength = -1
                    reason = f"赔率偏差{deviation:.1f}%≥3%，主胜被高估"
                else:
                    strength = 1
                    reason = f"赔率偏差{deviation:.1f}%≥3%，主胜被低估"
                confidence = 0.65
        
        return RuleSignal('R119', '赔率偏差量化', triggered, strength, confidence, reason)
    
    def _rule_R120(self, data: Dict) -> RuleSignal:
        """R120: 熵差系数"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'odds_draw', 'odds_away']):
            # 计算隐含概率
            probs = [1/data['odds_home'], 1/data['odds_draw'], 1/data['odds_away']]
            probs = np.array(probs) / sum(probs)  # 归一化
            
            # 计算熵
            entropy = -np.sum(probs * np.log2(probs + 1e-10))
            max_entropy = np.log2(3)  # 最大熵
            
            # 熵差 = 越接近0越确定
            entropy_diff = 1 - entropy / max_entropy
            
            if entropy_diff > 0.2:
                triggered = True
                # 找最可能结果
                max_idx = np.argmax(probs)
                if max_idx == 0:
                    strength = 1
                    reason = f"熵差{entropy_diff:.2f}>0.2，主胜确定性高"
                elif max_idx == 2:
                    strength = -1
                    reason = f"熵差{entropy_diff:.2f}>0.2，客胜确定性高"
                confidence = min(0.7, 0.5 + entropy_diff)
        
        return RuleSignal('R120', '熵差系数', triggered, strength, confidence, reason)
    
    # ============================================================
    # 大小球规则
    # ============================================================
    
    def _rule_R46(self, data: Dict) -> RuleSignal:
        """R46: 大小球锚定比分池"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'ou_line' in data and 'ou_over_prob' in data:
            if data['ou_over_prob'] >= 0.6:
                triggered = True
                strength = 0  # 不直接影响胜负
                confidence = 0.7
                reason = f"大球概率{data['ou_over_prob']:.1%}≥60%，锚定高比分池"
            elif data['ou_over_prob'] <= 0.4:
                triggered = True
                strength = 0
                confidence = 0.7
                reason = f"小球概率{1-data['ou_over_prob']:.1%}≥60%，锚定低比分池"
        
        return RuleSignal('R46', '大小球锚定比分池', triggered, strength, confidence, reason)
    
    def _rule_R47(self, data: Dict) -> RuleSignal:
        """R47: 进球数赔率交叉验证"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'ou_line' in data and 'btts_prob' in data:
            if data['ou_line'] <= 2.0 and data['btts_prob'] <= 0.45:
                triggered = True
                strength = 0
                confidence = 0.6
                reason = f"O/U{data['ou_line']}+BTTS{data['btts_prob']:.1%}，低进球预期"
            elif data['ou_line'] >= 3.0 and data['btts_prob'] >= 0.55:
                triggered = True
                strength = 0
                confidence = 0.6
                reason = f"O/U{data['ou_line']}+BTTS{data['btts_prob']:.1%}，高进球预期"
        
        return RuleSignal('R47', '进球数交叉验证', triggered, strength, confidence, reason)
    
    def _rule_R48(self, data: Dict) -> RuleSignal:
        """R48: 大小球变盘=进球修正"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'ou_line_initial' in data and 'ou_line' in data:
            ou_change = data['ou_line'] - data['ou_line_initial']
            if abs(ou_change) >= 0.25:
                triggered = True
                if ou_change > 0:
                    strength = 0
                    reason = f"大小球从{data['ou_line_initial']}升至{data['ou_line']}，进球预期上调"
                else:
                    strength = 0
                    reason = f"大小球从{data['ou_line_initial']}降至{data['ou_line']}，进球预期下调"
                confidence = 0.65
        
        return RuleSignal('R48', '大小球变盘', triggered, strength, confidence, reason)
    
    # ============================================================
    # 资金风控规则
    # ============================================================
    
    def _rule_R117(self, data: Dict) -> RuleSignal:
        """R117: 让平集中度≤50%"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'draw_concentration' in data:
            if data['draw_concentration'] > 0.5:
                triggered = True
                strength = 0
                confidence = 0.8
                reason = f"让平集中度{data['draw_concentration']:.1%}>50%，超限"
        
        return RuleSignal('R117', '让平集中度', triggered, strength, confidence, reason)
    
    def _rule_R118(self, data: Dict) -> RuleSignal:
        """R118: 碾压+低赔让胜不可逆"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'elo_diff' in data and 'home_win_prob' in data:
            if data['elo_diff'] > 200 and data['home_win_prob'] > 0.6:
                triggered = True
                strength = 2
                confidence = 0.85
                reason = f"ELO差{data['elo_diff']:.0f}+胜率{data['home_win_prob']:.1%}，让胜锁定"
        
        return RuleSignal('R118', '碾压+低赔让胜', triggered, strength, confidence, reason)
    
    def _rule_R154(self, data: Dict) -> RuleSignal:
        """R154: 让平限流纪律"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'draw_bet_count' in data and 'total_bet_count' in data:
            if data['total_bet_count'] > 0:
                draw_ratio = data['draw_bet_count'] / data['total_bet_count']
                if draw_ratio > 0.5:
                    triggered = True
                    strength = 0
                    confidence = 0.8
                    reason = f"让平占比{draw_ratio:.1%}>50%，需限流"
        
        return RuleSignal('R154', '让平限流', triggered, strength, confidence, reason)
    
    # ============================================================
    # 分析纪律规则
    # ============================================================
    
    def _rule_R105(self, data: Dict) -> RuleSignal:
        """R105: 双面验证强制+净值量化"""
        # 这个规则在分析流程中执行，这里返回基础信号
        return RuleSignal('R105', '双面验证', True, 0, 0.5, "需人工执行双面验证")
    
    def _rule_R107(self, data: Dict) -> RuleSignal:
        """R107: 全局优先级仲裁"""
        return RuleSignal('R107', '优先级仲裁', True, 0, 0.5, "需人工执行优先级仲裁")


def test_rule_engine():
    """测试规则引擎"""
    engine = FootballRuleEngine()
    
    # 测试数据
    test_match = {
        'home_team': 'Team A',
        'away_team': 'Team B',
        'home_elo': 1600,
        'away_elo': 1400,
        'odds_home': 1.80,
        'odds_draw': 3.60,
        'odds_away': 4.50,
        'pinnacle_home': 1.75,
        'pinnacle_draw': 3.55,
        'pinnacle_away': 4.40,
        'odds_home_initial': 1.70,
        'odds_draw_initial': 3.70,
        'odds_away_initial': 4.80,
    }
    
    result = engine.analyze_match(test_match)
    
    print("=" * 50)
    print("规则引擎测试结果")
    print("=" * 50)
    print(f"触发规则数: {result['n_signals']}")
    print(f"总信号强度: {result['total_strength']}")
    print(f"平均置信度: {result['avg_confidence']:.2f}")
    print(f"推荐方向: {result['direction']}")
    print()
    
    for signal in result['signals']:
        print(f"[{signal.rule_id}] {signal.name}")
        print(f"  强度: {signal.strength:+d}, 置信度: {signal.confidence:.2f}")
        print(f"  原因: {signal.reason}")
        print()


if __name__ == "__main__":
    test_rule_engine()
