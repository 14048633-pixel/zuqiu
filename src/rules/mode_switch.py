"""
R90模式切换 - 区分友谊赛/正赛
不同模式使用不同规则和权重
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict

@dataclass
class MatchMode:
    is_friendly: bool
    confidence: float
    reason: str

class ModeSwitcher:
    """R90: 模式切换"""
    
    # 友谊赛特征
    FRIENDLY_KEYWORDS = ['friendly', '热身', '邀请赛', '杯赛资格', '季前赛']
    
    # 正赛特征
    COMPETITIVE_KEYWORDS = ['联赛', '杯赛', '冠军', '淘汰', '决赛', '预选', '世预', '欧预']
    
    def detect_mode(self, match_data: Dict) -> MatchMode:
        """检测比赛模式"""
        
        # 1. 根据联赛判断
        league = match_data.get('league', '').lower()
        
        # 五大联赛 = 正赛
        if any(l in league for l in ['英超', '西甲', '德甲', '意甲', '法甲', 'premier', 'la liga', 'bundesliga']):
            return MatchMode(False, 0.9, "五大联赛=正赛")
        
        # MLS/韩职/巴甲等 = 正赛
        if any(l in league for l in ['美职', '韩职', '巴甲', 'mls', 'k league']):
            return MatchMode(False, 0.85, "职业联赛=正赛")
        
        # 2. 根据日期判断 (季前赛通常在7-8月)
        date = match_data.get('date', '')
        if '07-' in date or '08-' in date:
            # 可能是季前赛
            return MatchMode(True, 0.6, "7-8月可能季前赛")
        
        # 3. 根据ELO判断 (友谊赛ELO差异可能更大)
        elo_diff = abs(match_data.get('home_elo', 1500) - match_data.get('away_elo', 1500))
        if elo_diff > 300:
            return MatchMode(True, 0.5, "ELO差>300可能友谊赛")
        
        # 默认正赛
        return MatchMode(False, 0.7, "默认正赛")


class FriendlyRules:
    """友谊赛专用规则"""
    
    def apply(self, data: Dict) -> Dict:
        """应用友谊赛规则"""
        adjustments = {
            'confidence_penalty': 0,  # 置信度惩罚
            'direction_adjustment': 0,  # 方向调整
            'warnings': []
        }
        
        # R24: 友谊赛深盘穿盘陷阱
        if data.get('handicap_line', 0) <= -2:
            adjustments['confidence_penalty'] += 0.2
            adjustments['warnings'].append("R24: 友谊赛深盘穿盘率低")
        
        # R42: 友谊赛轮换=战意断崖
        if data.get('is_rotated', False):
            adjustments['confidence_penalty'] += 0.15
            adjustments['warnings'].append("R42: 轮换导致战意下降")
        
        # R62: 友谊赛收兵=被扳平
        if data.get('leading_by_1', False):
            adjustments['direction_adjustment'] = -1  # 趋向平局
            adjustments['warnings'].append("R62: 领先1球可能收兵被扳平")
        
        # R59: 控盘成本阈值 (友谊赛操纵成本低)
        adjustments['confidence_penalty'] += 0.1
        adjustments['warnings'].append("R59: 友谊赛操纵成本低，需警惕")
        
        return adjustments


class CompetitiveRules:
    """正赛专用规则"""
    
    def apply(self, data: Dict) -> Dict:
        """应用正赛规则"""
        adjustments = {
            'confidence_penalty': 0,
            'direction_adjustment': 0,
            'warnings': []
        }
        
        # R97: 正赛替补深度
        if data.get('has_good_bench', False):
            adjustments['direction_adjustment'] = 0.5  # 下半场进球预期+0.3
            adjustments['warnings'].append("R97: 替补深度好，下半场进球预期+0.3")
        
        # R109: 正赛绝平/绝杀风险
        if data.get('leading_by_1', False) and data.get('opponent_setpiece', False):
            adjustments['warnings'].append("R109: 1球领先+对手定位球强=绝平风险")
        
        # R115: 半场平局≠全场平局
        if data.get('ht_draw', False):
            adjustments['warnings'].append("R115: 半场平局≠全场平局")
        
        return adjustments


def test_mode_switch():
    """测试模式切换"""
    switcher = ModeSwitcher()
    friendly_rules = FriendlyRules()
    competitive_rules = CompetitiveRules()
    
    # 测试用例
    test_matches = [
        {'league': '英超', 'home_elo': 1800, 'away_elo': 1750, 'date': '2026-03-15'},
        {'league': '友谊赛', 'home_elo': 1800, 'away_elo': 1500, 'date': '2026-07-20'},
        {'league': 'K联赛', 'home_elo': 1600, 'away_elo': 1550, 'date': '2026-09-10'},
    ]
    
    for match in test_matches:
        mode = switcher.detect_mode(match)
        print(f"\n联赛: {match['league']}")
        print(f"  模式: {'友谊赛' if mode.is_friendly else '正赛'}")
        print(f"  置信度: {mode.confidence:.1%}")
        print(f"  原因: {mode.reason}")
        
        if mode.is_friendly:
            adj = friendly_rules.apply(match)
        else:
            adj = competitive_rules.apply(match)
        
        if adj['warnings']:
            print(f"  警告: {adj['warnings']}")


if __name__ == "__main__":
    test_mode_switch()
