"""
冷门条件计数引擎 - 纯数据触发, 无人工分级, 无AI定性

判断冷门风险 = 统计数据信号触发条件数
≥4个 → 高冷门风险
2-3个 → 中等
≤1个 → 低风险

所有条件基于用户提供的数据, 非主观判断
"""
import re
from typing import Dict, List


class UpsetEngine:
    """冷门条件计数引擎"""

    def __init__(self):
        self.conditions = []
        self.triggered = []

    # ============================================================
    # 组A: 热门方的"假强势"信号
    # ============================================================
    def _check_hot_weakness(self, hot_info: str, hot_h2h: str) -> List[str]:
        """热门方弱势信号"""
        signals = []

        # A1: 近10场平局≥5场 (平局之王)
        m = re.search(r'(\d+)平', hot_info)
        if m and int(m.group(1)) >= 5:
            signals.append(f"A1平局多({m.group(1)}平)")

        # A2: 历史交锋大胜是旧记录 (≥1年前)
        m = re.search(r'20\d{2}-(0?1|0?2|0?3|0?4|0?5|0?6)', hot_h2h)
        if m:
            signals.append("A2交锋大胜是上半年旧记录")

        # A3: 热门方主力缺阵
        if any(w in hot_info for w in ['伤缺', '缺阵', '停赛', '上调一线队', '不首发']):
            signals.append("A3热门方核心缺阵")

        # A4: 热门方战意低
        if any(w in hot_info for w in ['无欲无求', '副业', '轮换', '练兵', '不主动', '保平', '只求']):
            signals.append("A4热门方战意低")

        # A5: 热门方体能差 (一周双赛/疲劳/体能透支)
        if any(w in hot_info for w in ['一周双赛', '疲劳', '体能透支', '体能不足', '密集赛程', '连续作战', '体力']):
            signals.append("A5热门方体能差")

        # A6: 热门方客场近期差 (客场连败/客场虫)
        if any(w in hot_info for w in ['客场连败', '客场虫', '客场差', '客场乏力', '客场不胜', '客场糟糕']):
            signals.append("A6热门方客场近期差")

        return signals

    # ============================================================
    # 组B: 冷门方的"爆冷资本"
    # ============================================================
    def _check_cold_strength(self, cold_info: str) -> List[str]:
        """冷门方爆冷资本"""
        signals = []

        # B1: 近期连胜/不败
        if '连胜' in cold_info or '不败' in cold_info or '连平' in cold_info:
            signals.append("B1冷门方近期不败")

        # B2: 主场强
        if '主场' in cold_info and ('不败' in cold_info or '连胜' in cold_info or '强' in cold_info):
            signals.append("B2冷门方主场强")

        # B3: 战意强
        if any(w in cold_info for w in ['保级', '冲甲', '抢分', '每分必争', '求生', '复仇']):
            signals.append("B3冷门方战意强")

        # B4: 防守稳固 (场均失球<1)
        m = re.search(r'场均失([\d.]+)', cold_info)
        if m and float(m.group(1)) < 1.0:
            signals.append(f"B4冷门方防守稳(失{m.group(1)})")

        # B5: 冷门方定位球能力强 (弱队靠定位球爆冷)
        if any(w in cold_info for w in ['定位球', '定位球强', '任意球', '角球']):
            signals.append("B5冷门方定位球强")

        # B6: 冷门方体能好 (对方体能差, 我方充沛)
        if any(w in cold_info for w in ['体能充沛', '体能好', '轮换休息', '以逸待劳', '休整充足']):
            signals.append("B6冷门方体能充沛")

        return signals

    # ============================================================
    # 组D: 交锋历史信号
    # ============================================================
    def _check_h2h_risk(self, h2h: str) -> List[str]:
        """交锋历史信号"""
        signals = []

        # D1: 历史交锋小球/平局多 (闷平风险)
        if any(w in h2h for w in ['小球', '闷平', '0-0', '平局多', '交锋小球', '总进球.*≤']):
            signals.append("D1历史交锋小球/闷平")

        # D2: 冷门方近期交锋不落下风
        if any(w in h2h for w in ['逼平', '战平', '冷门方胜', '击败']):
            signals.append("D2冷门方交锋不惧")

        return signals

    # ============================================================
    # 组C: 盘口/赔率信号
    # ============================================================
    def _check_line_risk(self, hdp_val: float, hot_odds: float) -> List[str]:
        """盘口风险信号"""
        signals = []

        # C1: 热门方让深盘 (让≥1.5)
        if hdp_val <= -1.5:
            signals.append(f"C1深盘让{hdp_val:.0f}")

        # C2: 热门方赔率虚低 (让球方赔率<1.7但需要大胜)
        if hot_odds < 1.7 and hdp_val <= -0.5:
            signals.append(f"C2低赔({hot_odds:.2f})+让球")

        # C3: 平手/浅盘 (热门方让球≤0.25)
        if abs(hdp_val) <= 0.25:
            signals.append(f"C3浅盘(平/平半)")

        return signals

    # ============================================================
    # 主入口: 判断冷门风险
    # ============================================================
    def assess(self, hot_team: str, hot_info: str, cold_info: str,
               h2h: str, hdp_val: float, hot_odds: float) -> Dict:
        """评估冷门风险 (纯数据触发)"""
        self.triggered = []

        # 组A: 热门方弱势
        signals_a = self._check_hot_weakness(hot_info, h2h)
        # 组B: 冷门方资本
        signals_b = self._check_cold_strength(cold_info)
        # 组C: 盘口风险
        signals_c = self._check_line_risk(hdp_val, hot_odds)
        # 组D: 交锋历史信号
        signals_d = self._check_h2h_risk(h2h)

        self.triggered = signals_a + signals_b + signals_c + signals_d
        count = len(self.triggered)

        # 风险等级 (纯计数, 无人工分级)
        if count >= 4:
            level = "高"
        elif count >= 2:
            level = "中"
        else:
            level = "低"

        return {
            "hot_team": hot_team,
            "triggered_count": count,
            "level": level,
            "conditions": self.triggered,
            "recommendation": (
                "避开热门方" if level == "高"
                else "谨慎" if level == "中"
                else "热门方可信"
            ),
        }


def test():
    engine = UpsetEngine()

    # 测试1: 兰州 vs 北理工 (兰州热门)
    print("=" * 70)
    print("  兰州陇原 vs 北京理工 (热门=兰州, 让半一)")
    hot_info = "兰州近10场1胜7平2负12平局平局之王新帅首秀"
    cold_info = "北京理工垫底1胜6平11负学生军保级求生"
    r = engine.assess("兰州", hot_info, cold_info, "北理工历史3胜1平占优", -0.75, 1.52)
    print(f"  触发{len(r['conditions'])}个: {r['conditions']}")
    print(f"  冷门风险: {r['level']} → {r['recommendation']}")

    # 测试2: 海港B vs 山西 (海港B热门)
    print("\n" + "=" * 70)
    print("  海港B vs 山西 (热门=海港B, 让平半)")
    hot_info = "海港B近10场6胜2平2负保榜首追求稳定拿分不冒险"
    cold_info = "山西5连胜近10场7胜2平1负防守稳场均失0.8冲甲抢分"
    r2 = engine.assess("海港B", hot_info, cold_info, "海港B历史5-0山西是旧记录", -0.25, 2.14)
    print(f"  触发{len(r2['conditions'])}个: {r2['conditions']}")
    print(f"  冷门风险: {r2['level']} → {r2['recommendation']}")

    # 测试3: 湖北 vs 江西 (湖北热门)
    print("\n" + "=" * 70)
    print("  湖北 vs 江西 (热门=湖北, 受让平半)")
    hot_info = "湖北近10场4胜4平2负主场6场不败核心射手状态火热"
    cold_info = "江西中游近10场3胜4平3负客场偏弱"
    r3 = engine.assess("湖北", hot_info, cold_info, "湖北历史2胜1平", 0.25, 2.68)
    print(f"  触发{len(r3['conditions'])}个: {r3['conditions']}")
    print(f"  冷门风险: {r3['level']} → {r3['recommendation']}")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test()
