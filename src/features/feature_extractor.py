"""
数据特征提取器 - 从用户情报文本中提取关键预测指标
解决"数据蕴含方向但模型没提取"的问题

输入: 用户提供的情报文本 (近期状态/历史交锋/伤病/战意/阵型)
输出: 结构化特征字典, 供模型计算
"""
import re
from typing import Dict, List, Optional


class MatchFeatureExtractor:
    """从情报文本提取预测特征"""

    def __init__(self):
        self.features = {}

    # ============================================================
    # 1. 职业化程度 (业余vs职业 = 断层关键)
    # ============================================================
    def _extract_professionalism(self, home_info: str, away_info: str) -> Dict:
        """判断两队职业化程度 (基于联赛级别, 不依赖队名)"""
        # 联赛级别 → 职业化分 (中冠/业余=0, 中乙/半职业=1, 中甲/中超/职业=2)
        level_pro = {
            '中超': 2, '中甲': 2, '丹超': 2, '丹甲': 2, '丹乙': 2, '英超': 2, '西甲': 2, '德甲': 2, '意甲': 2, '法甲': 2,
            '中乙': 1, '丹丙': 1, '半职业': 1, '地区联赛': 1,
            '中冠': 0, '业余': 0, '丹丁': 0, '丹麦丁': 0, '青年': 0, '青训': 0,
        }
        # 档次关键词 (描述球队强弱)
        tier_strong = ['榜首', '冲甲强队', '冲甲第一梯队', '攻防顶尖', '顶级', '领头羊', '豪门']
        tier_weak = ['保级', '垫底', '降级', '弱旅', '弱队', '中游偏弱', '保级高危', '学生军']

        def score(text: str) -> int:
            s = 1  # 默认中游
            # 先按联赛级别判断
            for lv, val in level_pro.items():
                if lv in text:
                    s = val
                    break
            # 档次修正
            if any(w in text for w in tier_strong):
                s = max(s, 2)
            elif any(w in text for w in tier_weak):
                s = min(s, 0)
            return s

        home_s = score(home_info)
        away_s = score(away_info)
        return {
            'home_professionalism': home_s,   # 0业余/1半职业/2职业
            'away_professionalism': away_s,
            'pro_gap': home_s - away_s,       # 负=客队职业化高
            'amateur_vs_pro': 1 if (home_s == 0 and away_s == 2) else 0,  # 业余vs职业
            'pro_vs_amateur': 1 if (home_s == 2 and away_s == 0) else 0,
        }

    # ============================================================
    # 2. 近期状态 (连胜/连败/不败)
    # ============================================================
    def _extract_form(self, text: str) -> Dict:
        """提取近期状态"""
        form = {
            'win_streak': 0,   # 连胜
            'lose_streak': 0,  # 连败
            'unbeaten': 0,     # 不败场数
            'recent_wins': 0,
            'recent_losses': 0,
            'recent_draws': 0,
        }

        # 连胜: "4连胜" "5连胜" "连胜"
        m = re.search(r'(\d+)连胜', text)
        if m:
            form['win_streak'] = int(m.group(1))
        elif '连胜' in text:
            form['win_streak'] = 3

        # 连败
        m = re.search(r'(\d+)连败', text)
        if m:
            form['lose_streak'] = int(m.group(1))
        elif '连败' in text:
            form['lose_streak'] = 2

        # 不败: "连续6场不败" "10场不败"
        m = re.search(r'连续?(\d+)场不败|(\d+)场不败|(\d+)场.*不败', text)
        if m:
            form['unbeaten'] = int(next(g for g in m.groups() if g))
        elif '不败' in text:
            form['unbeaten'] = 5

        # 总战绩 "6胜2平2负"
        m = re.search(r'(\d+)胜(\d+)平(\d+)负', text)
        if m:
            form['recent_wins'] = int(m.group(1))
            form['recent_draws'] = int(m.group(2))
            form['recent_losses'] = int(m.group(3))

        return form

    def _form_score(self, form: Dict) -> float:
        """状态综合分 (-1到1)"""
        total = form['recent_wins'] + form['recent_draws'] + form['recent_losses']
        if total == 0:
            return 0
        score = (form['recent_wins'] - form['recent_losses']) / total
        # 连胜加成
        score += min(form['win_streak'], 5) * 0.05
        score -= min(form['lose_streak'], 5) * 0.05
        return max(-1, min(1, score))

    # ============================================================
    # 3. 历史交锋模式 (攻坚难/小球/碾压)
    # ============================================================
    def _extract_h2h(self, text: str) -> Dict:
        h2h = {
            'total_matches': 0,
            'avg_goals': 0,
            'all_small': 0,      # 交锋全小球=攻坚难
            'h2h_domination': 0, # 交锋碾压
            'h2h_draws': 0,      # 交锋平局数
        }

        # 交锋场次
        m = re.search(r'(\d+)次交锋|交锋(\d+)次|(\d+)次交手|交手(\d+)次', text)
        if m:
            h2h['total_matches'] = int(next(g for g in m.groups() if g))

        # 场均总进球
        m = re.search(r'场均总进球\s*([\d.]+)|总交锋场均([\d.]+)球|对战场均([\d.]+)球', text)
        if m:
            h2h['avg_goals'] = float(next(g for g in m.groups() if g))

        # 全小球/闷平
        if '0-0' in text or '闷平' in text or '全部.*平' in text:
            h2h['all_small'] = 1
        if '零封' in text or '全胜' in text or '碾压' in text:
            h2h['h2h_domination'] = 1

        # 平局数
        m = re.search(r'(\d+)场平局|(\d+)次平局|全部战平', text)
        if m:
            h2h['h2h_draws'] = int(next(g for g in m.groups() if g)) if m.lastindex else 0

        return h2h

    # ============================================================
    # 4. 攻防瘫痪信号
    # ============================================================
    def _extract_attack_defense(self, text: str) -> Dict:
        """进攻/防守瘫痪信号"""
        feat = {
            'attack_disabled': 0,  # 锋线哑火
            'defense_weak': 0,     # 防线漏洞
            'avg_goals_for': 0,
            'avg_goals_against': 0,
        }

        # 场均进球/失球 - 兼容多种格式:
        #   A) "场均进1.3失0.7" (紧凑)
        #   B) "场均进球1.3球场均失球0.7球" (独立字段)
        #   C) "场均进球1.3 场均失球0.7"
        m = re.search(r'场均进([\d.]+)失([\d.]+)', text)
        if m:
            feat['avg_goals_for'] = float(m.group(1))
            feat['avg_goals_against'] = float(m.group(2))
        else:
            # 格式B/C: 独立提取"场均进球X球"和"场均失球X球"
            m_gf = re.search(r'场均进球\s*([\d.]+)\s*球', text)
            m_ga = re.search(r'场均失球\s*([\d.]+)\s*球', text)
            if m_gf:
                feat['avg_goals_for'] = float(m_gf.group(1))
            if m_ga:
                feat['avg_goals_against'] = float(m_ga.group(1))
            if feat['avg_goals_for'] == 0 and feat['avg_goals_against'] == 0:
                # 兜底: 分别匹配
                m = re.search(r'场均进([\d.]+)', text)
                if m:
                    feat['avg_goals_for'] = float(m.group(1))
                m = re.search(r'场均失([\d.]+)|进[\d.]*失([\d.]+)', text)
                if m:
                    feat['avg_goals_against'] = float(m.group(1) or m.group(2))

        # 锋线哑火 (进攻<1球)
        if feat['avg_goals_for'] < 1.0 and feat['avg_goals_for'] > 0:
            feat['attack_disabled'] = 1
        if '哑火' in text or '锋线乏力' in text or '进攻乏力' in text or '攻坚能力差' in text:
            feat['attack_disabled'] = 1

        # 防线漏洞 (失球>2)
        if feat['avg_goals_against'] > 2.0:
            feat['defense_weak'] = 1
        if '防守漏洞' in text or '防线漏洞' in text or '防守崩盘' in text or '后防' in text:
            feat['defense_weak'] = 1

        return feat

    # ============================================================
    # 5. 关键球员缺阵
    # ============================================================
    def _extract_injuries(self, text: str) -> Dict:
        feat = {
            'key_player_out': 0,     # 关键球员缺阵
            'defense_key_out': 0,    # 防线核心缺阵
            'attack_key_out': 0,     # 进攻核心缺阵
            'full_squad': 0,         # 阵容完整
        }

        # 关键缺阵
        if '伤缺' in text or '缺阵' in text or '缺席' in text or '伤停' in text:
            feat['key_player_out'] = 1
        # 防线核心
        if any(w in text for w in ['中卫', '后卫', '防线核心', '门将']):
            feat['defense_key_out'] = 1
        # 进攻核心
        if any(w in text for w in ['前锋', '射手', '进攻核心', '头号射手']):
            feat['attack_key_out'] = 1
        # 阵容完整
        if '全队健康' in text or '阵容完整' in text or '无伤病' in text or '全员健康' in text:
            feat['full_squad'] = 1
            feat['key_player_out'] = 0

        return feat

    # ============================================================
    # 6. 战意
    # ============================================================
    def _extract_motivation(self, text: str) -> Dict:
        feat = {
            'motivation_home': 3,  # 1-5
            'motivation_away': 3,
        }

        high = ['拉满', '极高', '强烈', '全力', '争胜', '爆冷', '全力抢分', '冲甲', '冲超', '夺冠', '复仇', '保级']
        low = ['无欲无求', '副业', '轮换', '战意低', '摆烂', '放弃', '不主动', '练兵', '无抢分', '只求保平', '锻炼新人']

        def score_motivation(section: str) -> int:
            s = 3
            for w in high:
                if w in section:
                    s = 5
                    break
            for w in low:
                if w in section:
                    s = min(s, 1)
            return s

        # 拆分主/客战意
        home_part, away_part = text, text
        if '客队' in text and '主队' in text:
            home_part = text.split('客队')[0]
            away_part = text.split('主队')[-1]
        elif '主队' in text:
            home_part = text.split('主队')[-1]
        elif '客队' in text:
            away_part = text.split('客队')[-1]

        feat['motivation_home'] = score_motivation(home_part)
        feat['motivation_away'] = score_motivation(away_part)
        return feat

    # ============================================================
    # 主入口: 提取全部特征
    # ============================================================
    def extract(self, home_info: str, away_info: str, h2h_text: str = '',
                injuries_text: str = '', motivation_text: str = '') -> Dict:
        """从情报提取全部特征"""
        self.features = {}

        # 职业化
        self.features.update(self._extract_professionalism(home_info, away_info))

        # 升班马 (次级联赛升级队, 攻防强度需打折修正)
        self.features['home_promoted'] = 1 if ('升班马' in home_info or '升班' in home_info) else 0
        self.features['away_promoted'] = 1 if ('升班马' in away_info or '升班' in away_info) else 0

        # 近期状态
        home_form = self._extract_form(home_info)
        away_form = self._extract_form(away_info)
        self.features['home_form_score'] = round(self._form_score(home_form), 3)
        self.features['away_form_score'] = round(self._form_score(away_form), 3)
        self.features['form_diff'] = round(self.features['home_form_score'] - self.features['away_form_score'], 3)

        # 历史交锋
        h2h = self._extract_h2h(h2h_text)
        self.features.update(h2h)

        # 攻防
        home_adv = self._extract_attack_defense(home_info)
        away_adv = self._extract_attack_defense(away_info)
        self.features['home_attack_disabled'] = home_adv['attack_disabled']
        self.features['away_attack_disabled'] = away_adv['attack_disabled']
        self.features['home_defense_weak'] = home_adv['defense_weak']
        self.features['away_defense_weak'] = away_adv['defense_weak']
        self.features['home_gf'] = home_adv['avg_goals_for']
        self.features['away_gf'] = away_adv['avg_goals_for']
        self.features['home_ga'] = home_adv['avg_goals_against']
        self.features['away_ga'] = away_adv['avg_goals_against']

        # 伤病
        inj = self._extract_injuries(injuries_text)
        self.features.update(inj)

        # 战意
        self.features.update(self._extract_motivation(motivation_text))

        return self.features


def test_extractor():
    """测试特征提取器"""
    ex = MatchFeatureExtractor()

    # 测试欧雷 vs 弗雷德里西亚
    home = "欧雷业余青年梯队, 近10场5胜1平4负, 场均进1.6失1.9, 近2连败, 防守漏洞"
    away = "弗雷德里西亚丹乙职业队, 近10场6胜2平2负, 场均进2.4失1.1, 近5场4胜1平不败"
    h2h = "职业正式赛从未交手"
    inj = "欧雷无主力伤病, 弗雷主力中场格林伤缺"
    mot = "欧雷战意中等锻炼青年, 弗雷战意强烈冲升级"

    feats = ex.extract(home, away, h2h, inj, mot)
    print("=== 欧雷 vs 弗雷德里西亚 特征提取 ===")
    for k, v in feats.items():
        print(f"  {k}: {v}")
    print(f"""
  【解读】
  业余vs职业: {feats['amateur_vs_pro']} (1=业余vs职业断层)
  状态差: {feats['form_diff']} (负=客队状态好)
  → 数据方向: 客队碾压, 不该买主队受让!
""")

    # 测试FC南海岸 vs 伊绍伊
    home2 = "FC南海岸丹丁业余, 近10场6胜1平3负, 场均进3.3失2.7, 4连胜, 10场全大2.5"
    away2 = "伊绍伊丹乙职业, 近10场2胜5平3负, 场均进1.4失1.7, 3连平, 客场不主动战意低"
    feats2 = ex.extract(home2, away2, "从未交手", "FC中卫伤缺", "FC战意极高爆冷, 伊绍伊战意低保级优先")
    print("=== FC南海岸 vs 伊绍伊 特征提取 ===")
    for k, v in feats2.items():
        print(f"  {k}: {v}")
    print(f"""
  【解读】
  状态差: {feats2['form_diff']} (正=主队状态好)
  → 数据方向: 主队赢, 买主队受让合理
""")


if __name__ == "__main__":
    test_extractor()
