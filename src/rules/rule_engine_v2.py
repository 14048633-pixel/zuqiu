"""
足球预测规则引擎 v2 - 改进版
重点改进: 平局预测、信号强度校准
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

class FootballRuleEngineV2:
    def __init__(self):
        self.rules = {}
        self._init_rules()
    
    def _init_rules(self):
        """初始化所有可自动化的规则"""
        # 盘口赔率信号规则
        self.rules['R1'] = self._rule_R1
        self.rules['R2'] = self._rule_R2
        self.rules['R3'] = self._rule_R3
        self.rules['R7'] = self._rule_R7
        self.rules['R9'] = self._rule_R9
        self.rules['R69'] = self._rule_R69
        self.rules['R70'] = self._rule_R70
        
        # 新增: 平局专项规则
        self.rules['R7_draw'] = self._rule_R7_draw  # 平赔结构
        self.rules['R_draw_balance'] = self._rule_draw_balance  # 势均力敌
        self.rules['R_draw_elasticity'] = self._rule_draw_elasticity  # 赔率弹性
        
        # 量化模型规则
        self.rules['R49'] = self._rule_R49
        self.rules['R50'] = self._rule_R50
        self.rules['R52'] = self._rule_R52
        self.rules['R119'] = self._rule_R119
        self.rules['R120'] = self._rule_R120
        
        # 新增: ELO接近度规则
        self.rules['R_elo_close'] = self._rule_elo_close  # ELO接近=平局机会
        self.rules['R_elo_mid'] = self._rule_elo_mid  # ELO中等差距
        
        # 大小球规则
        self.rules['R46'] = self._rule_R46
        self.rules['R47'] = self._rule_R47
        self.rules['R48'] = self._rule_R48
        
        # 资金风控规则
        self.rules['R117'] = self._rule_R117
        self.rules['R118'] = self._rule_R118
        self.rules['R154'] = self._rule_R154
        
        # 分析纪律规则
        self.rules['R105'] = self._rule_R105
        self.rules['R107'] = self._rule_R107
        # ============================================================
        # 知识库补全规则 (2026-08-13 第二批)
        # ============================================================
        self.rules['R4'] = self._rule_R4      # 生死盘防走水
        self.rules['R5'] = self._rule_R5      # 低水诱客陷阱
        self.rules['R6'] = self._rule_R6      # 欧亚矛盾同向看衰
        self.rules['R18'] = self._rule_R18    # 值博率
        self.rules['R51'] = self._rule_R51    # 公平大小球vs实际盘
        self.rules['R71'] = self._rule_R71    # 让球盘>胜平负精度
        self.rules['R79'] = self._rule_R79    # 临场修正须盘口确认
        self.rules['R81'] = self._rule_R81    # 分析前查体彩盘口
        self.rules['R89'] = self._rule_R89    # 档位压制系数
        self.rules['R96'] = self._rule_R96    # 诱盘验证三条件
        self.rules['R108'] = self._rule_R108  # 矩阵单场集中度<=40%
        self.rules['R110'] = self._rule_R110  # SS退盘->让负优先
        self.rules['R112'] = self._rule_R112  # 赔率不变!=方向确认
        self.rules['R125'] = self._rule_R125  # 伤病位置权重
        self.rules['R132'] = self._rule_R132  # 连败资金缩减
        self.rules['R137'] = self._rule_R137  # xG/射门质量评估
        self.rules['R167'] = self._rule_R167  # 泊松强信号保护
        self.rules['R186'] = self._rule_R186  # 临场升盘确认
        # ============================================================
        # 情报类规则 (2026-08-13 第三批: R10/R98/R124/R127/R136/R143/R145/R147)
        # ============================================================
        self.rules['R10'] = self._rule_R10      # 伤病执行
        self.rules['R98'] = self._rule_R98      # 东道主首战=强方向锚
        self.rules['R124'] = self._rule_R124    # 裁判风格量化
        self.rules['R127'] = self._rule_R127    # 赛程密度量化
        self.rules['R136'] = self._rule_R136    # 小组赛出线算术
        self.rules['R143'] = self._rule_R143    # 门将超预期评估
        self.rules['R145'] = self._rule_R145    # 歇大了效应
        self.rules['R147'] = self._rule_R147    # 出线算术强制量化
        # ============================================================
        # 战意/环境规则 (2026-08-13 第四批: R25/R27/R61/R83/R85/R86/R87/R88/R133/R134/R135/R141)
        # ============================================================
        self.rules['R25'] = self._rule_R25      # 壮行战/告别战
        self.rules['R27'] = self._rule_R27      # 日职排位赛平局魔咒
        self.rules['R61'] = self._rule_R61      # 额外动力因子
        self.rules['R83'] = self._rule_R83      # 额外动力!=进球效率
        self.rules['R85'] = self._rule_R85      # 气候Debuff
        self.rules['R86'] = self._rule_R86      # 高原Debuff
        self.rules['R87'] = self._rule_R87      # 高温轻敌综合征
        self.rules['R88'] = self._rule_R88      # 战术克制权重
        self.rules['R133'] = self._rule_R133    # 心理/情绪因子
        self.rules['R134'] = self._rule_R134    # 高原/气候适应梯度
        self.rules['R135'] = self._rule_R135    # 雨战/风战量化
        self.rules['R141'] = self._rule_R141    # 开赛时间与生物钟
    
    def analyze_match(self, match_data: Dict) -> Dict:
        """分析单场比赛"""
        signals = []
        
        for rule_id, rule_func in self.rules.items():
            try:
                signal = rule_func(match_data)
                if signal and signal.triggered:
                    signals.append(signal)
            except Exception as e:
                pass
        
        # 计算综合信号
        total_strength = sum(s.strength for s in signals)
        avg_confidence = np.mean([s.confidence for s in signals]) if signals else 0
        
        # 改进的方向判断 (考虑平局)
        direction = self._determine_direction(total_strength, signals, match_data)
        
        return {
            'signals': signals,
            'total_strength': total_strength,
            'avg_confidence': avg_confidence,
            'direction': direction,
            'n_signals': len(signals)
        }
    
    def _determine_direction(self, strength: int, signals: List[RuleSignal], data: Dict) -> str:
        """改进的方向判断，增加平局检测"""
        
        # 检查平局信号
        draw_signals = [s for s in signals if s.rule_id in ['R7', 'R7_draw', 'R_draw_balance', 'R_elo_close', 'R27']]
        draw_strength = sum(s.strength for s in draw_signals)
        
        # 检查是否有强烈的非平局信号
        non_draw_signals = [s for s in signals if s.rule_id not in ['R7', 'R7_draw', 'R_draw_balance', 'R_elo_close', 'R27']]
        non_draw_strength = sum(s.strength for s in non_draw_signals)
        
        # 平局判断逻辑
        if draw_strength > 0 and abs(non_draw_strength) <= 1:
            return 'draw'
        
        # 原有逻辑
        if strength > 0:
            return 'home'
        elif strength < 0:
            return 'away'
        else:
            return 'draw'
    
    # ============================================================
    # 平局专项规则
    # ============================================================
    
    def _rule_R7_draw(self, data: Dict) -> RuleSignal:
        """平赔结构分析"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'odds_draw', 'odds_away']):
            # 平赔相对较低 = 平局可能性高
            avg_odds = (data['odds_home'] + data['odds_away']) / 2
            draw_ratio = data['odds_draw'] / avg_odds
            
            if draw_ratio < 0.85:  # 平赔明显偏低
                triggered = True
                strength = 0  # 平局方向
                confidence = 0.65
                reason = f"平赔{data['odds_draw']:.2f}相对偏低(比值{draw_ratio:.2f})，平局信号"
        
        return RuleSignal('R7_draw', '平赔结构', triggered, strength, confidence, reason)
    
    def _rule_draw_balance(self, data: Dict) -> RuleSignal:
        """势均力敌检测"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['home_elo', 'away_elo', 'odds_home', 'odds_away']):
            elo_diff = abs(data['home_elo'] - data['away_elo'])
            odds_ratio = data['odds_home'] / data['odds_away']
            
            # ELO接近 + 赔率接近 = 平局机会
            if elo_diff < 100 and 0.8 < odds_ratio < 1.2:
                triggered = True
                strength = 0
                confidence = 0.6
                reason = f"ELO差{elo_diff:.0f}+赔率比{odds_ratio:.2f}，势均力敌"
        
        return RuleSignal('R_draw_balance', '势均力敌', triggered, strength, confidence, reason)
    
    def _rule_draw_elasticity(self, data: Dict) -> RuleSignal:
        """赔率弹性分析"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'odds_draw', 'odds_away']):
            # 计算赔率弹性
            total_implied = 1/data['odds_home'] + 1/data['odds_draw'] + 1/data['odds_away']
            draw_implied = (1/data['odds_draw']) / total_implied
            
            # 平局隐含概率 > 28% = 平局机会
            if draw_implied > 0.28:
                triggered = True
                strength = 0
                confidence = min(0.7, 0.5 + (draw_implied - 0.28) * 2)
                reason = f"平局隐含概率{draw_implied:.1%}>28%，平局信号"
        
        return RuleSignal('R_draw_elasticity', '赔率弹性', triggered, strength, confidence, reason)
    
    # ============================================================
    # ELO规则
    # ============================================================
    
    def _rule_elo_close(self, data: Dict) -> RuleSignal:
        """ELO接近=平局机会"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = abs(data['home_elo'] - data['away_elo'])
            
            if elo_diff < 50:  # 非常接近
                triggered = True
                strength = 0
                confidence = 0.6
                reason = f"ELO差仅{elo_diff:.0f}，平局概率高"
            elif elo_diff < 100:  # 接近
                triggered = True
                strength = 0
                confidence = 0.5
                reason = f"ELO差{elo_diff:.0f}，平局概率中等"
        
        return RuleSignal('R_elo_close', 'ELO接近', triggered, strength, confidence, reason)
    
    def _rule_elo_mid(self, data: Dict) -> RuleSignal:
        """ELO中等差距"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            
            if 100 < elo_diff < 200:
                triggered = True
                strength = 1
                confidence = 0.6
                reason = f"ELO差{elo_diff:.0f}，主队优势但非碾压"
            elif -200 < elo_diff < -100:
                triggered = True
                strength = -1
                confidence = 0.6
                reason = f"ELO差{elo_diff:.0f}，客队优势但非碾压"
        
        return RuleSignal('R_elo_mid', 'ELO中等差距', triggered, strength, confidence, reason)
    
    # ============================================================
    # 盘口赔率信号规则 (保持不变)
    # ============================================================
    
    def _rule_R1(self, data: Dict) -> RuleSignal:
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_home_initial' in data and 'odds_home' in data:
            odds_change = data['odds_home'] - data['odds_home_initial']
            if odds_change > 0.25:
                triggered = True
                strength = -1
                confidence = min(0.8, 0.5 + odds_change * 0.5)
                reason = f"主胜赔率上升{odds_change:.2f}，退盘信号"
        
        return RuleSignal('R1', '退盘=降信心', triggered, strength, confidence, reason)
    
    def _rule_R2(self, data: Dict) -> RuleSignal:
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_home_initial' in data and 'odds_home' in data:
            odds_change = data['odds_home'] - data['odds_home_initial']
            if odds_change > 0.15:
                triggered = True
                strength = -1
                confidence = min(0.7, 0.5 + odds_change * 0.3)
                reason = f"主胜赔率持续上升，升水信号"
        
        return RuleSignal('R2', '升水=不看好', triggered, strength, confidence, reason)
    
    def _rule_R3(self, data: Dict) -> RuleSignal:
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
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'odds_draw_initial' in data and 'odds_draw' in data:
            draw_change = data['odds_draw_initial'] - data['odds_draw']
            if draw_change > 0.20:
                triggered = True
                strength = 0
                confidence = min(0.8, 0.5 + draw_change * 0.5)
                reason = f"平赔下降{draw_change:.2f}，资金涌入平局"
        
        return RuleSignal('R7', '平赔暴跌=资金涌平局', triggered, strength, confidence, reason)
    
    def _rule_R9(self, data: Dict) -> RuleSignal:
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            if elo_diff > 100:
                if 'odds_home' in data and data['odds_home'] > 2.0:
                    triggered = True
                    strength = -1
                    confidence = 0.6
                    reason = f"ELO差{elo_diff:.0f}但主胜赔率{data['odds_home']:.2f}，让步不足"
        
        return RuleSignal('R9', '让步不足', triggered, strength, confidence, reason)
    
    def _rule_R69(self, data: Dict) -> RuleSignal:
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
    # 量化模型规则 (保持不变)
    # ============================================================
    
    def _rule_R49(self, data: Dict) -> RuleSignal:
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            win_prob = 1 / (1 + 10 ** (-elo_diff / 400))
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
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if all(k in data for k in ['odds_home', 'odds_draw', 'odds_away']):
            probs = [1/data['odds_home'], 1/data['odds_draw'], 1/data['odds_away']]
            probs = np.array(probs) / sum(probs)
            
            entropy = -np.sum(probs * np.log2(probs + 1e-10))
            max_entropy = np.log2(3)
            entropy_diff = 1 - entropy / max_entropy
            
            if entropy_diff > 0.2:
                triggered = True
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
    # 大小球规则 (保持不变)
    # ============================================================
    
    def _rule_R46(self, data: Dict) -> RuleSignal:
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'ou_line' in data and 'ou_over_prob' in data:
            if data['ou_over_prob'] >= 0.6:
                triggered = True
                strength = 0
                confidence = 0.7
                reason = f"大球概率{data['ou_over_prob']:.1%}≥60%，锚定高比分池"
            elif data['ou_over_prob'] <= 0.4:
                triggered = True
                strength = 0
                confidence = 0.7
                reason = f"小球概率{1-data['ou_over_prob']:.1%}≥60%，锚定低比分池"
        
        return RuleSignal('R46', '大小球锚定比分池', triggered, strength, confidence, reason)
    
    def _rule_R47(self, data: Dict) -> RuleSignal:
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
    # 资金风控规则 (保持不变)
    # ============================================================
    
    def _rule_R117(self, data: Dict) -> RuleSignal:
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
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        
        if 'home_elo' in data and 'away_elo' in data and 'odds_home' in data:
            elo_diff = data['home_elo'] - data['away_elo']
            if elo_diff > 200 and data['odds_home'] < 1.5:
                triggered = True
                strength = 2
                confidence = 0.85
                reason = f"ELO差{elo_diff:.0f}+低赔{data['odds_home']:.2f}，让胜锁定"
        
        return RuleSignal('R118', '碾压+低赔让胜', triggered, strength, confidence, reason)
    
    def _rule_R154(self, data: Dict) -> RuleSignal:
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
    # 分析纪律规则 (保持不变)
    # ============================================================
    
    def _rule_R105(self, data: Dict) -> RuleSignal:
        return RuleSignal('R105', '双面验证', True, 0, 0.5, "需人工执行双面验证")
    
    def _rule_R107(self, data: Dict) -> RuleSignal:
        return RuleSignal('R107', '优先级仲裁', True, 0, 0.5, "需人工执行优先级仲裁")

    # ============================================================
    # 知识库补全规则 (2026-08-13 第二批)
    # ============================================================

    def _rule_R4(self, data: Dict) -> RuleSignal:
        """R4: 生死盘防走水 - 亚盘-1球需防平局或小胜"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        hdp = data.get('handicap_line')
        if hdp is not None and abs(abs(float(hdp)) - 1.0) < 1e-9:
            triggered = True
            confidence = 0.6
            reason = "亚盘-1球生死盘，防平局或小胜走水"
        return RuleSignal('R4', '生死盘防走水', triggered, strength, confidence, reason)

    def _rule_R5(self, data: Dict) -> RuleSignal:
        """R5: 低水诱客陷阱 - 客队低水0.75+平赔下降=诱买客队"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        aw = data.get('away_water')
        od_i = data.get('odds_draw_initial')
        od = data.get('odds_draw')
        if aw is not None and od is not None and od_i is not None:
            if float(aw) <= 0.75 and float(od) < float(od_i):
                triggered = True
                strength = 1
                confidence = 0.65
                reason = f"客队低水{float(aw):.2f}+平赔下降{float(od_i) - float(od):.2f}，诱买客队陷阱，偏向主队方向"
        return RuleSignal('R5', '低水诱客陷阱', triggered, strength, confidence, reason)

    def _rule_R6(self, data: Dict) -> RuleSignal:
        """R6: 欧亚矛盾同向看衰 - 退盘+欧赔主胜升高双信号看衰主队"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        hdp = data.get('handicap_line')
        hdp_i = data.get('handicap_initial')
        oh = data.get('odds_home')
        oh_i = data.get('odds_home_initial')
        if hdp is not None and hdp_i is not None and oh is not None and oh_i is not None:
            recede = float(hdp) > float(hdp_i)
            odds_up = float(oh) > float(oh_i)
            if recede and odds_up:
                triggered = True
                strength = -2
                confidence = 0.75
                reason = f"亚盘退盘({hdp_i}->{hdp})+欧赔主胜升({oh_i}->{oh})，双信号看衰主队"
        return RuleSignal('R6', '欧亚矛盾同向看衰', triggered, strength, confidence, reason)

    def _rule_R18(self, data: Dict) -> RuleSignal:
        """R18: 值博率 - 赔率<1.60不建议做胆"""
        triggered = False
        strength = 0
        confidence = 0.7
        reason = ""
        oh = data.get('odds_home')
        oa = data.get('odds_away')
        if oh is not None and float(oh) < 1.60:
            triggered = True
            reason = f"主胜赔率{float(oh):.2f}<1.60，值博率低不建议做胆"
        elif oa is not None and float(oa) < 1.60:
            triggered = True
            reason = f"客胜赔率{float(oa):.2f}<1.60，值博率低不建议做胆"
        return RuleSignal('R18', '值博率', triggered, strength, confidence, reason)

    def _rule_R51(self, data: Dict) -> RuleSignal:
        """R51: 公平大小球vs实际盘 - 公平值>实际0.5球=浅开->大球加分"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        fair = data.get('ou_fair_line')
        actual = data.get('ou_line')
        if fair is not None and actual is not None:
            diff = float(fair) - float(actual)
            if diff >= 0.5:
                triggered = True
                strength = 1
                confidence = 0.65
                reason = f"公平大小球{fair:.2f}>实际{actual:.2f}(差{diff:.2f})，浅开->大球加分"
        return RuleSignal('R51', '公平大小球', triggered, strength, confidence, reason)

    def _rule_R71(self, data: Dict) -> RuleSignal:
        """R71: 让球盘>胜平负精度 - 始终适用"""
        return RuleSignal('R71', '让球盘>胜平负精度', True, 0, 0.5, "让球盘更接近机构真实观点，优先参考")

    def _rule_R79(self, data: Dict) -> RuleSignal:
        """R79: 临场修正须盘口确认 - 修正方向与赔率方向矛盾->修正降权"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        corr = data.get('correction_direction')
        oh = data.get('odds_home')
        oh_i = data.get('odds_home_initial')
        if corr and oh is not None and oh_i is not None:
            change = float(oh) - float(oh_i)
            if abs(change) > 0.10:
                if corr == 'home' and change > 0:
                    triggered = True
                    confidence = 0.7
                    reason = f"修正方向主胜但主胜赔率升{change:.2f}>0.10，修正降权"
                elif corr in ('away', 'draw') and change < 0:
                    triggered = True
                    confidence = 0.7
                    reason = f"修正方向{corr}但主胜赔率降{abs(change):.2f}>0.10，修正降权"
        return RuleSignal('R79', '临场修正须盘口确认', triggered, strength, confidence, reason)

    def _rule_R81(self, data: Dict) -> RuleSignal:
        """R81: 分析前查体彩盘口 - 未开胜平负玩法则推单受限"""
        triggered = False
        strength = 0
        confidence = 0.8
        reason = ""
        markets = data.get('available_markets')
        if isinstance(markets, (list, tuple, set)) and len(markets) > 0:
            has_1x2 = any(str(m) in ('胜平负', '1X2', 'h2h', '1x2') for m in markets)
            if not has_1x2:
                triggered = True
                reason = f"该场未开胜平负玩法(开售:{','.join(str(m) for m in markets)})，推单受限"
        return RuleSignal('R81', '体彩盘口检查', triggered, strength, confidence, reason)

    def _rule_R89(self, data: Dict) -> RuleSignal:
        """R89: 档位压制系数 - T0-T3分档，档位差>=2->压制方向"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        ht = data.get('home_tier')
        at = data.get('away_tier')
        if ht is not None and at is not None:
            diff = int(ht) - int(at)
            if diff <= -2:
                triggered = True
                strength = 1
                confidence = 0.65
                reason = f"主队档位T{ht}压制客队T{at}，主胜倾向"
            elif diff >= 2:
                triggered = True
                strength = -1
                confidence = 0.65
                reason = f"客队档位T{at}压制主队T{ht}，客胜倾向"
        return RuleSignal('R89', '档位压制', triggered, strength, confidence, reason)

    def _rule_R96(self, data: Dict) -> RuleSignal:
        """R96: 诱盘验证三条件 - 连跌2-3时段须验证(凯利>1.05/BTTS矛盾/基本面硬伤)至少1条"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        fall = int(data.get('odds_fall_periods', 0) or 0)
        if fall >= 2:
            kelly = data.get('kelly_home')
            btts_conflict = data.get('btts_conflict', False)
            fund_neg = data.get('fundamental_negative', False)
            validated = bool(btts_conflict) or bool(fund_neg) or (kelly is not None and float(kelly) > 1.05)
            if validated:
                triggered = True
                strength = -1
                confidence = 0.7
                reason = f"主胜赔率连跌{fall}时段且三条件至少1条成立(凯利>1.05/BTTS矛盾/基本面硬伤)，标诱盘"
            else:
                triggered = True
                strength = 1
                confidence = 0.6
                reason = f"主胜赔率连跌{fall}时段但三条件全不满足，应视为真热而非诱盘"
        return RuleSignal('R96', '诱盘验证三条件', triggered, strength, confidence, reason)

    def _rule_R108(self, data: Dict) -> RuleSignal:
        """R108: 矩阵单场集中度<=40% - 同一场>40%=系统性摧毁"""
        triggered = False
        strength = 0
        confidence = 0.85
        reason = ""
        pct = data.get('match_stake_pct')
        if pct is not None and float(pct) > 0.40:
            triggered = True
            reason = f"单场仓位{float(pct):.0%}>40%，集中度过高需降低"
        return RuleSignal('R108', '单场集中度', triggered, strength, confidence, reason)

    def _rule_R110(self, data: Dict) -> RuleSignal:
        """R110: SS退盘->让负优先 - 5家全退>=1盘级->让负仓位>=60%"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        n = int(data.get('ss_recede_count', 0) or 0)
        od_draw = data.get('odds_hdp_draw')
        od_loss = data.get('odds_hdp_loss')
        if n >= 5:
            if od_draw is not None and od_loss is not None and float(od_loss) < float(od_draw):
                triggered = True
                strength = -2
                confidence = 0.8
                reason = f"5家全退(SS)且让负{od_loss:.2f}<让平{od_draw:.2f}，让负优先，仓位>=60%"
            else:
                triggered = True
                strength = -2
                confidence = 0.7
                reason = "5家全退(SS)>=1盘级，最保守解读让负优先"
        return RuleSignal('R110', 'SS退盘->让负优先', triggered, strength, confidence, reason)

    def _rule_R112(self, data: Dict) -> RuleSignal:
        """R112: 赔率不变!=方向确认 - 波动<=0.05持续3+时段且非最低"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        flat = int(data.get('flat_periods', 0) or 0)
        if flat >= 3:
            oh = data.get('odds_home')
            od = data.get('odds_draw')
            oa = data.get('odds_away')
            if oh is not None and od is not None and oa is not None:
                lowest = min(float(oh), float(od), float(oa))
                if abs(float(oh) - lowest) > 1e-9:
                    triggered = True
                    confidence = 0.6
                    reason = f"赔率波动<=0.05持续{flat}时段但主胜非最低项，不能当作方向确认"
        return RuleSignal('R112', '赔率不变!=方向确认', triggered, strength, confidence, reason)

    @staticmethod
    def _inj_weight(injuries) -> float:
        """伤病位置权重累计(门将-2>中卫-1.5>后腰/组织核心/中场-1>边后卫/后卫/边锋/攻击手/前锋-0.5)，
        同位置>=2人 x1.5，合计上限-3.0。"""
        weights = {
            '门将': -2.0, 'goalkeeper': -2.0, 'gk': -2.0,
            '中卫': -1.5, 'center_back': -1.5, 'cb': -1.5,
            '后腰': -1.0, 'defensive_mid': -1.0, 'dm': -1.0,
            '组织核心': -1.0, 'playmaker': -1.0, 'am': -1.0,
            '中场': -1.0, 'midfielder': -1.0, 'central_mid': -1.0, 'midfield': -1.0,
            '边后卫': -0.5, 'full_back': -0.5, 'fb': -0.5,
            '后卫': -0.75, 'defender': -0.75,
            '边锋': -0.5, 'winger': -0.5,
            '攻击手': -0.5, 'attacking_mid': -0.5,
            '前锋': -0.5, 'forward': -0.5, 'striker': -0.5, 'fw': -0.5,
        }
        total = 0.0
        if injuries and isinstance(injuries, dict):
            for pos, cnt in injuries.items():
                w = weights.get(str(pos).lower(), -0.5)
                c = max(1, int(cnt or 1))
                if c >= 2:
                    w *= 1.5
                total += w
        return max(total, -3.0)

    def _rule_R125(self, data: Dict) -> RuleSignal:
        """R125: 伤病位置权重 - 主客不对称(有主客分布时按差方向，否则按合计)"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        injuries = data.get('injuries')
        hi = data.get('home_injuries')
        ai = data.get('away_injuries')
        if isinstance(hi, dict) and isinstance(ai, dict) and (hi or ai):
            hw = self._inj_weight(hi)
            aw = self._inj_weight(ai)
            diff = hw - aw  # 负 = 主队伤停更重
            if diff <= -1.0:
                triggered = True
                strength = max(-3, int(round(diff)))
                confidence = 0.75
                reason = f"主队伤停权重{hw:.1f} > 客队{aw:.1f}，主队攻防降级"
            elif diff >= 1.0:
                triggered = True
                strength = min(3, int(round(diff)))
                confidence = 0.75
                reason = f"客队伤停权重{aw:.1f} > 主队{hw:.1f}，客队攻防降级"
            return RuleSignal('R125', '伤病位置权重', triggered, strength, confidence, reason)
        if injuries and isinstance(injuries, dict):
            total = self._inj_weight(injuries)
            parts = []
            for pos, cnt in injuries.items():
                w = self._inj_weight({pos: cnt})
                parts.append(f"{pos}x{int(cnt or 1)}={w:.1f}")
            if total <= -1.0:
                triggered = True
                strength = max(-2, int(round(total)))
                confidence = 0.75
                reason = f"伤病位置权重{total:.1f} ({'; '.join(parts)})，攻防降级"
        return RuleSignal('R125', '伤病位置权重', triggered, strength, confidence, reason)

    def _rule_R132(self, data: Dict) -> RuleSignal:
        """R132: 连败资金缩减 - 单日亏>100减半/连亏3日暂停"""
        triggered = False
        strength = 0
        confidence = 0.85
        reason = ""
        pnl = data.get('daily_pnl')
        losing = int(data.get('losing_days', 0) or 0)
        if pnl is not None and float(pnl) < -100:
            triggered = True
            reason = f"单日亏损{float(pnl):.0f}，资金减半"
        elif losing >= 3:
            triggered = True
            reason = f"连亏{losing}日，暂停推单"
        return RuleSignal('R132', '连败资金缩减', triggered, strength, confidence, reason)

    def _rule_R137(self, data: Dict) -> RuleSignal:
        """R137: xG/射门质量评估 - xG高没赢->反弹；xG低赢了->不可持续"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        hx = data.get('home_xg')
        hs = data.get('home_scored')
        ax = data.get('away_xg')
        av = data.get('away_scored')
        if hx is not None and hs is not None:
            if float(hx) - float(hs) > 0.5:
                triggered = True
                strength += 1
                confidence = max(confidence, 0.65)
                reason = f"主队xG{float(hx):.2f}>进球{int(hs)}，xG高没赢->反弹"
            elif float(hs) - float(hx) > 0.5:
                triggered = True
                strength -= 1
                confidence = max(confidence, 0.65)
                reason = f"主队xG{float(hx):.2f}<进球{int(hs)}，赢球不可持续->降级"
        if ax is not None and av is not None:
            if float(ax) - float(av) > 0.5:
                triggered = True
                strength -= 1
                confidence = max(confidence, 0.65)
                reason += ("；" if reason else "") + f"客队xG{float(ax):.2f}>进球{int(av)}，客队反弹"
            elif float(av) - float(ax) > 0.5:
                triggered = True
                strength += 1
                confidence = max(confidence, 0.65)
                reason += ("；" if reason else "") + f"客队xG{float(ax):.2f}<进球{int(av)}，客队不可持续"
        return RuleSignal('R137', 'xG反弹', triggered, strength, confidence, reason)

    def _rule_R167(self, data: Dict) -> RuleSignal:
        """R167: 泊松强信号保护 - 泊松>=50%严禁翻转，只降信号"""
        triggered = False
        strength = 0
        confidence = 0.9
        reason = ""
        probs = [float(p) for p in [data.get('poisson_home'), data.get('poisson_draw'), data.get('poisson_away')] if p is not None]
        if probs and max(probs) >= 0.50:
            idx = probs.index(max(probs))
            names = ['主胜', '平局', '客胜']
            triggered = True
            reason = f"泊松{names[idx]}概率{max(probs):.0%}>=50%，方向锁定严禁翻转，只允许降信号"
        return RuleSignal('R167', '泊松强信号保护', triggered, strength, confidence, reason)

    def _rule_R186(self, data: Dict) -> RuleSignal:
        """R186: 临场升盘确认 - 先退后升回到初盘或更高=方向锁定"""
        triggered = False
        strength = 0
        confidence = 0.5
        reason = ""
        hi = data.get('hdp_initial')
        ht = data.get('hdp_trough')
        hl = data.get('hdp_last')
        if hi is not None and ht is not None and hl is not None:
            hi, ht, hl = float(hi), float(ht), float(hl)
            if ht > hi and hl <= hi:
                triggered = True
                strength = 2
                confidence = 0.8
                reason = f"盘口先退({hi}->{ht})后升回({hl})，临场升盘确认，方向锁定主队"
        return RuleSignal('R186', '临场升盘确认', triggered, strength, confidence, reason)

    # ============================================================
    # 情报类规则 (2026-08-13 第三批)
    # ============================================================

    def _rule_R10(self, data: Dict) -> RuleSignal:
        """R10: 伤病执行 - 关键球员伤缺3人以上必须降级(主客不对称)"""
        n = int(data.get('key_injuries', 0) or 0)
        hk = data.get('home_key_injuries')
        ak = data.get('away_key_injuries')
        if hk is not None and ak is not None:
            hk = int(hk or 0)
            ak = int(ak or 0)
            if hk >= 3 and ak < 3:
                return RuleSignal('R10', '伤病执行', True, -1, 0.7, f"主队伤缺{hk}人>=3(客队{ak})，主队降级")
            if ak >= 3 and hk < 3:
                return RuleSignal('R10', '伤病执行', True, 1, 0.7, f"客队伤缺{ak}人>=3(主队{hk})，客队降级")
        if n >= 3:
            return RuleSignal('R10', '伤病执行', True, -1, 0.7, f"关键球员伤缺{n}人(>=3)，必须降级")
        return RuleSignal('R10', '伤病执行', False, 0, 0.5, "")

    def _rule_R98(self, data: Dict) -> RuleSignal:
        """R98: 东道主首战=强方向锚 - 77%历史胜率->主胜+2级"""
        if data.get('is_host_opener'):
            return RuleSignal('R98', '东道主首战', True, 2, 0.77, "东道主首战77%历史胜率，主胜+2级")
        return RuleSignal('R98', '东道主首战', False, 0, 0.5, "")

    def _rule_R124(self, data: Dict) -> RuleSignal:
        """R124: 裁判风格量化 - 严哨/宽松/主场哨/点球猎手4类"""
        style = data.get('referee_style')
        mapping = {
            'strict': (0, "严哨->红牌/点球多，利于小球与平局"),
            'lenient': (0, "宽松哨->利于大球与强队进攻"),
            'home_whistle': (1, "主场哨->主队受益"),
            'penalty_hunter': (0, "点球猎手->判点概率高，利好进攻强队"),
        }
        if style in mapping:
            strength, note = mapping[style]
            return RuleSignal('R124', '裁判风格', True, strength, 0.6, note)
        return RuleSignal('R124', '裁判风格', False, 0, 0.5, "")

    def _rule_R127(self, data: Dict) -> RuleSignal:
        """R127: 赛程密度量化 - 休息<3天疲劳修正"""
        triggered = False
        strength = 0
        reason = ""
        hr = data.get('home_rest_days')
        ar = data.get('away_rest_days')
        if hr is not None and float(hr) < 3:
            triggered = True
            strength -= 1
            reason += f"主队休息{float(hr):.0f}天(<3)"
        if ar is not None and float(ar) < 3:
            triggered = True
            strength += 1
            reason += ("；" if reason else "") + f"客队休息{float(ar):.0f}天(<3)"
        if reason:
            reason += "，赛程密集疲劳修正"
        return RuleSignal('R127', '赛程密度', triggered, strength, 0.6, reason)

    def _rule_R136(self, data: Dict) -> RuleSignal:
        """R136: 小组赛出线算术 - MD1赢->MD2保守+小球; MD1输->MD2激进+大球"""
        md = data.get('group_md')
        r1 = data.get('md1_result')
        if md == 2 and r1 == 'win':
            return RuleSignal('R136', '小组赛出线算术', True, 0, 0.6, "MD1赢->MD2保守+小球")
        if md == 2 and r1 == 'loss':
            return RuleSignal('R136', '小组赛出线算术', True, 0, 0.6, "MD1输->MD2激进+大球")
        return RuleSignal('R136', '小组赛出线算术', False, 0, 0.5, "")

    def _rule_R143(self, data: Dict) -> RuleSignal:
        """R143: 门将超预期评估 - PSxG-GA/90分级 (负=超预期/正=低于预期)"""
        triggered = False
        strength = 0
        reason = ""
        hg = data.get('home_gk_psxg_ga')
        ag = data.get('away_gk_psxg_ga')
        if hg is not None:
            v = float(hg)
            if v <= -0.5:
                triggered = True
                strength += 1
                reason += f"主队门将超预期(PSxG-GA={v:.2f})"
            elif v >= 0.5:
                triggered = True
                strength -= 1
                reason += f"主队门将低于预期(PSxG-GA={v:+.2f})"
        if ag is not None:
            v = float(ag)
            if v <= -0.5:
                triggered = True
                strength -= 1
                reason += ("；" if reason else "") + f"客队门将超预期(PSxG-GA={v:.2f})"
            elif v >= 0.5:
                triggered = True
                strength += 1
                reason += ("；" if reason else "") + f"客队门将低于预期(PSxG-GA={v:+.2f})"
        return RuleSignal('R143', '门将超预期', triggered, strength, 0.6, reason)

    def _rule_R145(self, data: Dict) -> RuleSignal:
        """R145: 歇大了效应 - 休息>6天->进攻端-0.2级 (慢热/小球倾向)"""
        triggered = False
        strength = 0
        reason = ""
        hr = data.get('home_rest_days')
        ar = data.get('away_rest_days')
        if hr is not None and float(hr) > 6:
            triggered = True
            reason += f"主队休息{float(hr):.0f}天>6，歇大了->进攻端-0.2级"
        if ar is not None and float(ar) > 6:
            triggered = True
            reason += ("；" if reason else "") + f"客队休息{float(ar):.0f}天>6，歇大了->进攻端-0.2级"
        if reason:
            reason += "，慢热/小球倾向"
        return RuleSignal('R145', '歇大了', triggered, strength, 0.6, reason)

    def _rule_R147(self, data: Dict) -> RuleSignal:
        """R147: 出线算术强制量化 - 动机4档+战意不对称"""
        hm = int(data.get('home_motivation', 2) or 2)
        am = int(data.get('away_motivation', 2) or 2)
        diff = hm - am
        if diff >= 2:
            return RuleSignal('R147', '出线算术', True, 1, 0.65, f"主队出线动机{hm}档>客队{am}档，战意不对称利好主队")
        if diff <= -2:
            return RuleSignal('R147', '出线算术', True, -1, 0.65, f"客队出线动机{am}档>主队{hm}档，战意不对称利好客队")
        return RuleSignal('R147', '出线算术', False, 0, 0.5, "")

    # ============================================================
    # 战意/环境规则 (2026-08-13 第四批)
    # ============================================================

    def _rule_R25(self, data: Dict) -> RuleSignal:
        """R25: 壮行战/告别战 - 主场告别战=全力大胜取悦球迷"""
        if data.get('is_farewell'):
            return RuleSignal('R25', '壮行告别战', True, 1, 0.6, "主场告别战，全力大胜取悦球迷")
        return RuleSignal('R25', '壮行告别战', False, 0, 0.5, "")

    def _rule_R27(self, data: Dict) -> RuleSignal:
        """R27: 日职排位赛平局魔咒 - 无欲无求排位赛1-1是默认比分"""
        league = str(data.get('league', ''))
        hm = int(data.get('home_motivation', 2) or 2)
        am = int(data.get('away_motivation', 2) or 2)
        if any(k in league for k in ('日职', 'J1', 'J联赛', 'j1')) and hm <= 1 and am <= 1:
            return RuleSignal('R27', '日职平局魔咒', True, 1, 0.6, "日职无欲无求排位赛，1-1默认比分，防平")
        return RuleSignal('R27', '日职平局魔咒', False, 0, 0.5, "")

    def _rule_R61(self, data: Dict) -> RuleSignal:
        """R61: 额外动力因子 - 回归/首秀等额外动力需效率正常才加成"""
        triggered = False
        strength = 0
        reason = ""
        if data.get('home_extra_motivation') and not data.get('home_low_efficiency'):
            triggered = True
            strength += 1
            reason += "主队额外动力(回归/首秀/里程碑)+效率正常"
        if data.get('away_extra_motivation') and not data.get('away_low_efficiency'):
            triggered = True
            strength -= 1
            reason += ("；" if reason else "") + "客队额外动力+效率正常"
        if reason:
            reason += "，战意加成"
        return RuleSignal('R61', '额外动力', triggered, strength, 0.6, reason)

    def _rule_R83(self, data: Dict) -> RuleSignal:
        """R83: 额外动力!=进球效率 - 低效球队额外动力归零"""
        triggered = False
        reason = ""
        if data.get('home_extra_motivation') and data.get('home_low_efficiency'):
            triggered = True
            reason += "主队低效+额外动力->额外动力归零"
        if data.get('away_extra_motivation') and data.get('away_low_efficiency'):
            triggered = True
            reason += ("；" if reason else "") + "客队低效+额外动力->额外动力归零"
        return RuleSignal('R83', '额外动力!=效率', triggered, 0, 0.6, reason)

    def _rule_R85(self, data: Dict) -> RuleSignal:
        """R85: 气候Debuff - 湿热+欧洲队->进球预期下降"""
        if data.get('weather_hot_humid') and data.get('european_team'):
            return RuleSignal('R85', '气候Debuff', True, 0, 0.6, "湿热+欧洲队，进球预期下降(小球/慢热倾向)")
        return RuleSignal('R85', '气候Debuff', False, 0, 0.5, "")

    def _rule_R86(self, data: Dict) -> RuleSignal:
        """R86: 高原Debuff - 2200m+低地队->下半场进球x0.7"""
        alt = data.get('altitude_m')
        if alt is not None and float(alt) >= 2000 and data.get('lowland_team'):
            return RuleSignal('R86', '高原Debuff', True, 0, 0.6,
                              f"高原{float(alt):.0f}m+低地队，下半场进球x0.7(小球/爆冷倾向)")
        return RuleSignal('R86', '高原Debuff', False, 0, 0.5, "")

    def _rule_R87(self, data: Dict) -> RuleSignal:
        """R87: 高温轻敌综合征 - 高温+T0/T1打T3+小组赛首轮->让胜-1级"""
        ht = data.get('home_tier')
        at = data.get('away_tier')
        if data.get('heat') and ht is not None and at is not None and int(ht) <= int(at) - 2                 and data.get('group_md') == 1:
            return RuleSignal('R87', '高温轻敌', True, -1, 0.6, "高温+T0/T1打T3+小组赛首轮，让胜-1级")
        return RuleSignal('R87', '高温轻敌', False, 0, 0.5, "")

    def _rule_R88(self, data: Dict) -> RuleSignal:
        """R88: 战术克制权重 - press克low_block克possession克counter克press"""
        beats = {'press': 'low_block', 'low_block': 'possession', 'possession': 'counter', 'counter': 'press'}
        hs = data.get('home_style')
        as_ = data.get('away_style')
        if hs in beats and as_ in beats:
            if beats[hs] == as_:
                return RuleSignal('R88', '战术克制', True, 1, 0.5, f"主队{hs}克客队{as_}")
            if beats[as_] == hs:
                return RuleSignal('R88', '战术克制', True, -1, 0.5, f"客队{as_}克主队{hs}")
        return RuleSignal('R88', '战术克制', False, 0, 0.5, "")

    def _rule_R133(self, data: Dict) -> RuleSignal:
        """R133: 心理/情绪因子 - 反弹+1/换帅+1/松懈-1/赛季末-1"""
        pmap = {'反弹': 1, '换帅': 1, '松懈': -1, '赛季末': -1}
        triggered = False
        strength = 0
        reason = ""
        hp = data.get('home_psychology')
        ap = data.get('away_psychology')
        if hp in pmap:
            triggered = True
            strength += pmap[hp]
            reason += f"主队情绪:{hp}({pmap[hp]:+d})"
        if ap in pmap:
            triggered = True
            strength -= pmap[ap]
            reason += ("；" if reason else "") + f"客队情绪:{ap}"
        return RuleSignal('R133', '心理情绪', triggered, strength, 0.6, reason)

    def _rule_R134(self, data: Dict) -> RuleSignal:
        """R134: 高原/气候适应梯度 - 客队适应<7天受冲击"""
        days = data.get('away_acclimatize_days')
        if days is not None:
            d = float(days)
            if d < 3:
                return RuleSignal('R134', '气候适应', True, 1, 0.6,
                                  f"客队适应时间{d:.0f}天(<3)，高原/气候冲击大，利好主队")
            if d < 7:
                return RuleSignal('R134', '气候适应', True, 1, 0.55,
                                  f"客队适应时间{d:.0f}天(3-7)，仍有影响")
        return RuleSignal('R134', '气候适应', False, 0, 0.5, "")

    def _rule_R135(self, data: Dict) -> RuleSignal:
        """R135: 雨战/风战量化 - 中雨-0.5/大雨-1/积水-1.5"""
        w = str(data.get('weather', ''))
        sev = {'小雨': 0, 'rain_light': 0, '中雨': 0.5, 'rain_medium': 0.5,
               '大雨': 1.0, 'rain_heavy': 1.0, '积水': 1.5, 'waterlogged': 1.5,
               '大风': 0.5, 'windy': 0.5}.get(w, 0)
        if sev > 0:
            strength = -1 if sev >= 1.0 else 0
            return RuleSignal('R135', '雨战风战', True, strength, 0.6,
                              f"{w}，进球预期下调{sev:.1f}(小球/受让方受益)")
        return RuleSignal('R135', '雨战风战', False, 0, 0.5, "")

    def _rule_R141(self, data: Dict) -> RuleSignal:
        """R141: 开赛时间与生物钟 - 非黄金时段慢热倾向"""
        h = data.get('kickoff_clock')
        if h is None:
            return RuleSignal('R141', '生物钟', False, 0, 0.5, "")
        h = int(h)
        if 19 <= h <= 22:
            return RuleSignal('R141', '生物钟', False, 0, 0.5, "")
        label = "下午" if 12 <= h < 19 else ("上午" if h < 12 else "深夜")
        debuff = 0.2 if 12 <= h < 19 else (0.3 if h < 12 else 0.5)
        return RuleSignal('R141', '生物钟', True, 0, 0.5,
                          f"开赛{label}({h}时)，生物钟影响-{debuff:.1f}，慢热倾向")


def test_v2():
    """测试V2版本"""
    import sys
    sys.path.insert(0, '.')
    
    df = pd.read_csv('data/processed/matches_with_features.csv', low_memory=False)
    engine = FootballRuleEngineV2()
    
    predictions = []
    actuals = []
    
    test_df = df.dropna(subset=['home_elo', 'away_elo', 'odds_home', 'odds_draw', 'odds_away']).head(1000)
    
    for _, row in test_df.iterrows():
        match_data = {
            'home_team': row.get('home_team', ''),
            'away_team': row.get('away_team', ''),
            'home_elo': row['home_elo'],
            'away_elo': row['away_elo'],
            'odds_home': row['odds_home'],
            'odds_draw': row['odds_draw'],
            'odds_away': row['odds_away'],
            'pinnacle_home': row.get('pinnacle_home', row['odds_home']),
            'pinnacle_draw': row.get('pinnacle_draw', row['odds_draw']),
            'pinnacle_away': row.get('pinnacle_away', row['odds_away']),
        }
        
        result = engine.analyze_match(match_data)
        pred_map = {'home': 2, 'draw': 1, 'away': 0}
        pred = pred_map.get(result['direction'], 1)
        actual = int(row['target'])
        
        predictions.append(pred)
        actuals.append(actual)
    
    from sklearn.metrics import accuracy_score
    accuracy = accuracy_score(actuals, predictions)
    
    print("=" * 50)
    print("规则引擎V2测试结果")
    print("=" * 50)
    print(f"测试场次: {len(predictions)}")
    print(f"总准确率: {accuracy:.1%}")


if __name__ == "__main__":
    test_v2()
