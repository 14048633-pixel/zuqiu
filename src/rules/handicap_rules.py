"""
让球盘专用规则引擎 - 基于162条规则系统
核心: R117/R118/R142/R154/R201
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class HandicapSignal:
    rule_id: str
    name: str
    triggered: bool
    direction: str  # 'hdp_win', 'hdp_draw', 'hdp_lose'
    strength: int  # -2 to +2
    confidence: float
    reason: str

class HandicapRuleEngine:
    def __init__(self):
        self.rules = {
            'R45': self._rule_R45,   # 让负需排除赢1球区间
            'R80': self._rule_R80,   # 体彩让球≠亚盘
            'R117': self._rule_R117, # 让平集中度≤50%
            'R118': self._rule_R118, # 碾压+低赔让胜不可逆
            'R142': self._rule_R142, # 执行强制锁
            'R154': self._rule_R154, # 让平限流纪律
            'R169': self._rule_R169, # 让球盘精度规则
            'R201': self._rule_R201, # 让球结算公式
        }
    
    def analyze_handicap(self, data: Dict) -> Dict:
        """
        分析让球盘方向
        data需要包含:
        - goal_diff: 预期净胜球
        - handicap_line: 让球线 (如-1, 0, +1)
        - odds_hdp_win: 让胜赔率
        - odds_hdp_draw: 让平赔率
        - odds_hdp_lose: 让负赔率
        - elo_diff: ELO差
        - is_crushing: 是否碾压局势
        """
        signals = []
        
        for rule_id, rule_func in self.rules.items():
            signal = rule_func(data)
            if signal and signal.triggered:
                signals.append(signal)
        
        # 综合判断
        direction = self._determine_direction(signals, data)
        
        return {
            'signals': signals,
            'direction': direction,
            'n_signals': len(signals)
        }
    
    def _determine_direction(self, signals: List[HandicapSignal], data: Dict) -> str:
        """决定让球方向"""
        # 检查是否有锁定信号
        for signal in signals:
            if signal.rule_id == 'R118' and signal.triggered:
                return 'hdp_win'  # R118锁定让胜
        
        # 统计信号
        win_signals = sum(1 for s in signals if s.direction == 'hdp_win')
        lose_signals = sum(1 for s in signals if s.direction == 'hdp_lose')
        draw_signals = sum(1 for s in signals if s.direction == 'hdp_draw')
        
        # R117: 让平≤50%
        if draw_signals > win_signals and draw_signals > lose_signals:
            # 让平信号最多，但R117限制
            if win_signals > lose_signals:
                return 'hdp_win'
            else:
                return 'hdp_lose'
        
        if win_signals > lose_signals:
            return 'hdp_win'
        elif lose_signals > win_signals:
            return 'hdp_lose'
        else:
            return 'hdp_draw'
    
    # ============================================================
    # 核心规则实现
    # ============================================================
    
    def _rule_R45(self, data: Dict) -> HandicapSignal:
        """R45: 让负需排除赢1球区间"""
        triggered = False
        direction = 'hdp_draw'
        strength = 0
        confidence = 0.5
        reason = ""
        
        hdp = data.get('handicap_line', 0)
        goal_diff = data.get('goal_diff', 0)
        
        # 如果让球线是-1，赢1球=让平，不是让负
        if hdp == -1 and goal_diff == 1:
            triggered = True
            direction = 'hdp_draw'
            strength = 0
            confidence = 0.8
            reason = "R45: 赢1球=让平，排除让负"
        
        return HandicapSignal('R45', '排除赢1球区间', triggered, direction, strength, confidence, reason)
    
    def _rule_R80(self, data: Dict) -> HandicapSignal:
        """R80: 体彩让球≠亚盘"""
        # 这个规则提醒分析时要区分
        return HandicapSignal('R80', '体彩≠亚盘', False, 'hdp_draw', 0, 0.5, "")
    
    def _rule_R117(self, data: Dict) -> HandicapSignal:
        """R117: 让平集中度≤50%"""
        triggered = False
        direction = 'hdp_draw'
        strength = 0
        confidence = 0.5
        reason = ""
        
        draw_concentration = data.get('draw_concentration', 0)
        
        if draw_concentration > 0.5:
            triggered = True
            direction = 'hdp_draw'
            strength = -1  # 降权
            confidence = 0.8
            reason = f"R117: 让平集中度{draw_concentration:.1%}>50%，需限流"
        
        return HandicapSignal('R117', '让平集中度', triggered, direction, strength, confidence, reason)
    
    def _rule_R118(self, data: Dict) -> HandicapSignal:
        """R118: 碾压+低赔让胜不可逆"""
        triggered = False
        direction = 'hdp_win'
        strength = 0
        confidence = 0.5
        reason = ""
        
        is_crushing = data.get('is_crushing', False)
        odds_hdp_win = data.get('odds_hdp_win', 999)
        
        # 碾压≥3项 + 让胜<1.80 → 锁定让胜
        if is_crushing and odds_hdp_win < 1.80:
            triggered = True
            direction = 'hdp_win'
            strength = 2
            confidence = 0.9
            reason = f"R118: 碾压+让胜{odds_hdp_win:.2f}<1.80，锁定让胜"
        
        return HandicapSignal('R118', '碾压+低赔让胜', triggered, direction, strength, confidence, reason)
    
    def _rule_R142(self, data: Dict) -> HandicapSignal:
        """R142: 执行强制锁"""
        triggered = False
        direction = 'hdp_draw'
        strength = 0
        confidence = 0.5
        reason = ""
        
        # 检查三道锁
        lock1 = data.get('r131_checked', False)  # R131的7项勾选
        lock2 = data.get('r142_forced', False)   # 强制规则触发
        lock3 = data.get('r142_selfcheck', False) # 反向测试
        
        if lock1 and lock2 and lock3:
            triggered = True
            confidence = 0.85
            reason = "R142: 三道锁全部通过"
        
        return HandicapSignal('R142', '执行强制锁', triggered, direction, strength, confidence, reason)
    
    def _rule_R154(self, data: Dict) -> HandicapSignal:
        """R154: 让平限流纪律"""
        triggered = False
        direction = 'hdp_draw'
        strength = 0
        confidence = 0.5
        reason = ""
        
        daily_draw_count = data.get('daily_draw_count', 0)
        max_draw_per_day = 2  # 每日让平≤2条
        
        if daily_draw_count >= max_draw_per_day:
            triggered = True
            direction = 'hdp_draw'
            strength = -1
            confidence = 0.8
            reason = f"R154: 今日让平已{daily_draw_count}条，达到上限"
        
        return HandicapSignal('R154', '让平限流', triggered, direction, strength, confidence, reason)
    
    def _rule_R169(self, data: Dict) -> HandicapSignal:
        """R169: 让球盘精度规则"""
        triggered = False
        direction = 'hdp_win'
        strength = 0
        confidence = 0.5
        reason = ""
        
        expected_goal_diff = data.get('expected_goal_diff', 0)
        handicap_line = data.get('handicap_line', 0)
        
        # 让胜需预期净胜球≥1.5
        if expected_goal_diff - handicap_line >= 1.5:
            triggered = True
            direction = 'hdp_win'
            strength = 1
            confidence = 0.7
            reason = f"R169: 预期净胜球{expected_goal_diff:.1f}-让球{handicap_line}={expected_goal_diff-handicap_line:.1f}≥1.5"
        
        return HandicapSignal('R169', '让球盘精度', triggered, direction, strength, confidence, reason)
    
    def _rule_R201(self, data: Dict) -> HandicapSignal:
        """R201: 让球结算公式"""
        triggered = False
        direction = 'hdp_draw'
        strength = 0
        confidence = 0.5
        reason = ""
        
        handicap_line = data.get('handicap_line', 0)
        goal_diff = data.get('goal_diff', 0)
        
        # 结算公式: 净胜球 - 让球数
        adjusted = goal_diff - handicap_line
        
        if adjusted > 0:
            direction = 'hdp_win'
            reason = f"R201: 净胜球{goal_diff}-让球{handicap_line}={adjusted}>0，让胜"
        elif adjusted < 0:
            direction = 'hdp_lose'
            reason = f"R201: 净胜球{goal_diff}-让球{handicap_line}={adjusted}<0，让负"
        else:
            direction = 'hdp_draw'
            reason = f"R201: 净胜球{goal_diff}-让球{handicap_line}={adjusted}=0，让平"
        
        triggered = True
        confidence = 0.95
        
        return HandicapSignal('R201', '让球结算公式', triggered, direction, strength, confidence, reason)


def test_handicap_engine():
    """测试让球引擎"""
    engine = HandicapRuleEngine()
    
    # 测试用例1: 碾压局势
    test1 = {
        'goal_diff': 2.5,  # 预期净胜2.5球
        'handicap_line': -2,
        'odds_hdp_win': 1.65,
        'odds_hdp_draw': 3.50,
        'odds_hdp_lose': 5.00,
        'elo_diff': 350,
        'is_crushing': True,
        'draw_concentration': 0.3,
    }
    
    result1 = engine.analyze_handicap(test1)
    print("=" * 50)
    print("测试1: 碾压局势 (让球-2)")
    print("=" * 50)
    print(f"方向: {result1['direction']}")
    for s in result1['signals']:
        if s.triggered:
            print(f"  [{s.rule_id}] {s.name}: {s.reason}")
    
    # 测试用例2: 均衡局势
    test2 = {
        'goal_diff': 0.5,
        'handicap_line': -1,
        'odds_hdp_win': 2.20,
        'odds_hdp_draw': 3.20,
        'odds_hdp_lose': 3.10,
        'elo_diff': 80,
        'is_crushing': False,
        'draw_concentration': 0.45,
    }
    
    result2 = engine.analyze_handicap(test2)
    print("\n" + "=" * 50)
    print("测试2: 均衡局势 (让球-1)")
    print("=" * 50)
    print(f"方向: {result2['direction']}")
    for s in result2['signals']:
        if s.triggered:
            print(f"  [{s.rule_id}] {s.name}: {s.reason}")


if __name__ == "__main__":
    test_handicap_engine()
