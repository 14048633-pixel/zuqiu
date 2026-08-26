"""
多模型融合预测器 v2
核心改进:
1. 业余连胜需按对手级别修正 (业余队对业余弱队刷的连胜≠真状态)
2. 历史交锋模式有独立权重 (0-0闷平=攻坚难)
3. 每个指标是独立"专家模型", 输出方向分, 最后加权融合

原理: 多个关键指标各自打分 → 加权融合 → 比单一指标更准
"""
import re, math
from typing import Dict, List


class EnsemblePredictor:
    """多模型融合预测器"""

    def __init__(self):
        # 各专家模型权重 (基于实验校准)
        self.weights = {
            'poisson': 0.8,        # 场均进失球泊松
            'form': 0.8,           # 近期状态
            'professional': 1.2,   # 职业化断层
            'h2h': 1.0,            # 历史交锋
            'attack_defense': 0.5, # 攻防瘫痪
            'injury': 0.4,         # 关键伤缺
            'upset_capital': 2.0,  # 爆冷资本 (核心)
        }

    # ============================================================
    # 专家1: 泊松模型 (场均进失球)
    # ============================================================
    def expert_poisson(self, home: str, away: str) -> float:
        """基于场均进失球的方向分 (正=主队占优)"""
        gf_ga = []
        for t in [home, away]:
            m = re.search(r'场均进([\d.]+)失([\d.]+)', t)
            if m:
                gf_ga.append((float(m.group(1)), float(m.group(2))))
            else:
                gf_ga.append((1.5, 1.5))

        h_gf, h_ga = gf_ga[0]
        a_gf, a_ga = gf_ga[1]
        lam_h = (h_gf / 1.64) * (a_ga / 1.64) * 1.64
        lam_a = (a_gf / 1.64) * (h_ga / 1.64) * 1.64
        # 方向分: -1到1
        return max(-1, min(1, (lam_h - lam_a) / (lam_h + lam_a)))

    # ============================================================
    # 专家2: 近期状态 (关键改进: 业余连胜打折)
    # ============================================================
    def _extract_form(self, text: str) -> Dict:
        form = {'wins': 0, 'draws': 0, 'losses': 0, 'streak': 0, 'unbeaten': 0}
        m = re.search(r'(\d+)胜(\d+)平(\d+)负', text)
        if m:
            form['wins'], form['draws'], form['losses'] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m = re.search(r'(\d+)连胜', text)
        if m:
            form['streak'] = int(m.group(1))
        elif '连胜' in text:
            form['streak'] = 3
        m = re.search(r'(\d+)连败', text)
        if m:
            form['streak'] = -int(m.group(1))
        elif '连败' in text:
            form['streak'] = -2
        return form

    def _is_amateur(self, text: str) -> bool:
        return any(w in text for w in ['业余', '青年', '青训', '业余梯队', '兼职', '丹丁'])

    def _is_pro(self, text: str) -> bool:
        return any(w in text for w in ['职业', '丹超', '丹甲', '丹乙', '全职'])

    def expert_form(self, home: str, away: str) -> float:
        """近期状态方向分 (业余连胜打折: 业余队对业余弱队刷的连胜≠真状态)"""
        hf = self._extract_form(home)
        af = self._extract_form(away)

        def form_score(f, is_amateur, opp_is_pro):
            total = f['wins'] + f['draws'] + f['losses']
            if total == 0:
                return 0
            score = (f['wins'] - f['losses']) / total
            # 连胜加成
            score += min(abs(f['streak']), 5) * 0.08 * (1 if f['streak'] > 0 else -1)
            # 【关键修正】业余队连胜打5折 (对手是业余弱队, 含金量低)
            if is_amateur and f['streak'] > 0:
                score *= 0.5
            # 业余队面对职业对手, 连胜更不可信
            if is_amateur and opp_is_pro:
                score *= 0.3
            return score

        h_score = form_score(hf, self._is_amateur(home), self._is_pro(away))
        a_score = form_score(af, self._is_amateur(away), self._is_pro(home))
        return max(-1, min(1, h_score - a_score))

    # ============================================================
    # 专家3: 职业化断层
    # ============================================================
    def _level_from_text(self, text: str) -> int:
        """从文本/级别字段提取联赛等级 (1=丹超最高, 5=丹麦丁最低)"""
        # 处理 "丹丁(4)", "丹超(1)", "丹丙(3)" 等
        m = re.search(r'(丹超|丹甲|丹乙|丹丙|丹丁|丹麦丁)\(?(\d)?\)?', text)
        if m:
            num = m.group(2)
            if num:
                return int(num)
            mapping = {'丹超': 1, '丹甲': 2, '丹乙': 2, '丹丙': 4, '丹丁': 5, '丹麦丁': 5}
            return mapping.get(m.group(1), 3)
        # 关键词兜底
        if '职业' in text or '丹超' in text:
            return 1
        if '丹甲' in text:
            return 2
        if '业余' in text or '青年' in text or '丹丁' in text or '丹麦丁' in text:
            return 5
        return 3

    def expert_professional(self, home: str, away: str) -> float:
        """职业化方向分 (基于联赛等级, 正=主队等级高)"""
        h_level = self._level_from_text(home)
        a_level = self._level_from_text(away)
        diff = a_level - h_level  # 正值=客队等级更高(客队更强)
        return max(-1, min(1, diff * 0.35))

    # ============================================================
    # 专家4: 历史交锋
    # ============================================================
    def expert_h2h(self, h2h: str) -> float:
        """历史交锋方向分 (负=客队占优/攻坚难)"""
        score = 0.0
        # 客队全胜/碾压
        if '全胜' in h2h or '零封' in h2h or '碾压' in h2h:
            score -= 1.0
        # 主队占优
        if '主队' in h2h and ('占优' in h2h or '上风' in h2h):
            score += 0.8
        # 【关键改进】0-0闷平 = 攻坚难, 主队难赢
        if '0-0' in h2h or '闷平' in h2h:
            score -= 0.5
        # 交锋小球 = 进球难
        if '小球' in h2h or '总进球都不足' in h2h:
            score -= 0.3
        return max(-1, min(1, score))

    # ============================================================
    # 专家5: 攻防瘫痪
    # ============================================================
    def expert_attack_defense(self, home: str, away: str) -> float:
        """攻防瘫痪方向分"""
        score = 0.0
        for t, sign in [(home, 1), (away, -1)]:
            m = re.search(r'场均进([\d.]+)', t)
            gf = float(m.group(1)) if m else 1.5
            if gf < 1.0:
                score += sign * 1.2  # 该队锋线哑火, 对手有利
            if '哑火' in t or '进攻乏力' in t or '攻坚能力差' in t:
                score += sign * 1.0
        return max(-1, min(1, score))

    # ============================================================
    # 专家6: 关键伤缺
    # ============================================================
    def expert_injury(self, home_inj: str, away_inj: str) -> float:
        """伤缺方向分"""
        score = 0.0
        for t, sign in [(home_inj, 1), (away_inj, -1)]:
            if '缺阵' in t or '伤缺' in t or '伤停' in t:
                if any(w in t for w in ['中卫', '后卫', '防线', '门将']):
                    score += sign * 0.8  # 防线核心缺阵
                elif any(w in t for w in ['前锋', '射手', '头号']):
                    score += sign * 0.6  # 进攻核心缺阵
                else:
                    score += sign * 0.3
            if '全员健康' in t or '无伤病' in t or '阵容完整' in t:
                score += sign * 0.2
        return max(-1, min(1, score))

    # ============================================================
    # 核心模型: 爆冷资本 (业余vs职业的关键判定)
    # ============================================================
    def upset_capital(self, home: str, away: str, h2h: str) -> float:
        """
        业余主队的爆冷资本 (正=主队有爆冷条件)
        资本 = 主队状态分 + 客队客场差 + 主队战意 - 级别差距惩罚
        
        规律:
        - 业余主队状态爆棚 + 职业客队客场差 → 资本足, 主队可能爆冷
        - 业余主队状态差 + 职业客队状态好 → 资本弱, 被血洗
        """
        # 主队状态 (业余连胜已打折)
        form_s = self.expert_form(home, away)
        # 级别差 (负=客队级别高)
        pro_s = self.expert_professional(home, away)
        # 交锋
        h2h_s = self.expert_h2h(h2h)

        # 爆冷资本 = 主队状态优势 - 级别劣势
        # 关键: 级别差决定"主队状态是否可信"
        level_diff = -pro_s / 0.35 if pro_s != 0 else 0  # 恢复等级差(客队-主队)
        # 业余主队vs职业客队时, 级别差惩罚
        if level_diff >= 2:
            # 跨2级+: 即使主队状态好, 也打折 (级别差是硬伤)
            capital = form_s * 0.5 + pro_s * 0.3 + h2h_s * 0.3
        elif level_diff == 1:
            capital = form_s * 0.8 + pro_s * 0.4 + h2h_s * 0.4
        else:
            # 同级别: 状态/交锋主导
            capital = form_s + h2h_s * 0.5
        return max(-1, min(1, capital))

    # ============================================================
    # 融合: form主导 + 其他专家否决/确认 (非简单加权)
    # ============================================================
    def predict(self, home: str, away: str, h2h: str = '',
                home_inj: str = '', away_inj: str = '') -> Dict:
        experts = {
            'poisson': self.expert_poisson(home, away),
            'form': self.expert_form(home, away),
            'professional': self.expert_professional(home, away),
            'h2h': self.expert_h2h(h2h),
            'attack_defense': self.expert_attack_defense(home, away),
            'injury': self.expert_injury(home_inj, away_inj),
            'upset_capital': self.upset_capital(home, away, h2h),
        }

        # form是主模型(62%最准), 其他作为确认/否决
        base = experts['form']

        # 确认: 状态差明确时, 方向以form为主
        direction = '主队' if base > 0.15 else '客队' if base < -0.15 else '均势'

        # 否决规则 (防爆冷)
        veto = None
        # 1. 断层悬殊 + 主队状态是"业余刷的" → 改判客队
        if experts['professional'] < -0.6 and base > 0:
            # 业余vs职业跨级大, 即使form说主队, 也要谨慎
            # 除非upset_capital显示主队有真实爆冷资本
            if experts['upset_capital'] < 0:
                veto = '客队'
        # 2. 历史交锋碾压客队
        if experts['h2h'] < -0.6 and base > 0.1:
            if experts['upset_capital'] < 0:
                veto = '客队'

        if veto:
            direction = veto

        # 融合分 (供参考)
        total_weight = sum(self.weights.values())
        fusion = sum(experts[k] * self.weights[k] for k in experts) / total_weight
        confidence = min(abs(base), 1.0)

        return {
            'experts': experts,
            'weights': self.weights,
            'fusion_score': fusion,
            'direction': direction,
            'confidence': confidence,
            'primary_model': 'form',
            'veto': veto,
        }


def test():
    p = EnsemblePredictor()
    cases = [
        ("欧雷 vs 弗雷德里西亚",
         "欧雷业余青年梯队近10场5胜1平4负场均进1.6失1.9近2连败防守漏洞",
         "弗雷德里西亚丹乙职业近10场6胜2平2负场均进2.4失1.1近5场4胜1平不败",
         "职业正式赛从未交手", "欧雷无伤", "弗雷主力中场格林伤缺"),
        ("霍尔斯特布罗 vs 奥尔堡",
         "霍尔斯特布罗丹麦丁业余近10场7胜2平1负场均进2.9失1.3近5连胜",
         "奥尔堡丹超职业近10场3胜3平4负场均进1.6失1.8客场2胜3平5负",
         "从未正式交手", "霍尔斯特全健康", "奥尔堡主力右后卫重伤"),
        ("灵斯泰德 vs 费林",
         "灵斯泰德丹丙近10场5胜2平3负场均进2.2失1.9主场强",
         "费林丹丙近10场2胜4平4负场均进1.4失2.1客场1胜3平6负",
         "2次交锋均0-0闷平小球", "灵斯泰德头号射手不首发", "费林中场核心伤缺"),
        ("FC南海岸 vs 伊绍伊",
         "FC南海岸丹丁业余近10场6胜1平3负场均进3.3失2.7近4连胜10场全大2.5",
         "伊绍伊丹乙职业近10场2胜5平3负场均进1.4失1.7近3连平客场不主动",
         "从未正式交手", "FC中卫霍夫曼伤缺", "伊绍伊右边锋伤缺"),
    ]
    for name, h, a, h2h, hi, ai in cases:
        r = p.predict(h, a, h2h, hi, ai)
        print(f"\n  {name}")
        print(f"  专家分: " + " ".join(f"{k}:{v:+.1f}" for k, v in r['experts'].items()))
        print(f"  融合: {r['fusion_score']:+.2f} → {r['direction']} (置信{r['confidence']:.0%})")


if __name__ == "__main__":
    test()
