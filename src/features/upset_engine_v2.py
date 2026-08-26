"""
冷门识别引擎 v2.0 - 基于完整专业框架
用户提供的系统化冷门识别清单

四组信号 + 分级 + 排除误区
全部纯数据触发, 无主观判断
"""
import math
import re
from typing import Dict, List


class UpsetEngineV2:
    """冷门识别引擎 v2"""

    def __init__(self):
        self.hot_items = []    # 强队隐患
        self.cold_items = []   # 弱队优势
        self.line_items = []   # 盘赔信号
        self.env_items = []    # 场地加分
        self.h2h_items = []    # 交锋信号
        self.ucl_items = []    # 欧冠资格赛专项
        self.uel_items = []    # 欧联资格赛专项
        self.exclusions = []   # 排除误区
        self.total_count = 0

    # ============================================================
    # 一、强队(热门方)隐患项
    # ============================================================
    def _check_hot_risks(self, hot_info: str) -> List[str]:
        items = []

        # 1. 近5场不败/主场连续零封+轻敌
        if ('不败' in hot_info or '零封' in hot_info) and ('轻敌' in hot_info or '吹捧' in hot_info or '媒体' in hot_info):
            items.append("H1近5场不败+轻敌氛围")
        elif '轻敌' in hot_info or '心态放松' in hot_info or '大意' in hot_info:
            items.append("H1强队轻敌")

        # 2. 主力中卫/边后卫停赛或受伤
        if any(w in hot_info for w in ['中卫停赛', '中卫受伤', '边后卫停赛', '边后卫受伤', '防线核心停赛', '防线残缺', '主力中卫', '主力边后卫', '停赛']):
            items.append("H2防线主力缺阵")

        # 3. 中场组织核心缺席
        if any(w in hot_info for w in ['前腰伤缺', '组织核心缺席', '中场核心伤', '前腰缺阵', '中场创造力下滑', '组织核心', '中场核心缺', '中场.*伤', '中伤缺']):
            items.append("H3中场组织核心缺阵")

        # 4. 3天内连续作战/一周双赛/长途飞行商业赛
        if any(w in hot_info for w in ['一周双赛', '3天', '3天内', '长途飞行', '商业赛', '远征', '体能下滑', '体能差']):
            items.append("H4密集赛程/长途消耗")

        # 5. 已锁定冠军/欧战资格, 无抢分刚需
        if any(w in hot_info for w in ['锁定冠军', '欧战资格', '无抢分', '无保级压力', '无欲无求', '没压力', '只求客场进球', '不愿大举压上', '不愿拼命']):
            items.append("H5无抢分刚需")

        # 6. 历史对阵连续2场以上全胜
        if any(w in hot_info for w in ['血脉压制', '历史全胜', '连续.*全胜', '从未输过']):
            items.append("H6历史碾压+习惯轻视")

        # 7. 领先主动收缩防守
        if any(w in hot_info for w in ['领先后收缩', '领先后防守', '主动收缩', '领先后控']):
            items.append("H7领先后收缩防守")

        return items

    # ============================================================
    # 二、弱队(受让方)有利条件
    # ============================================================
    def _check_cold_adv(self, cold_info: str) -> List[str]:
        items = []

        # 1. 降级区/附加区, 保级战意强
        if any(w in cold_info for w in ['降级区', '降级附加', '保级', '求生', '每分必争']):
            items.append("C1保级战意强")

        # 2. 连续多轮不胜, 急需止颓, 防守凝聚力强
        if any(w in cold_info for w in ['连续.*不胜', '多轮不胜', '急需止颓', '防守凝聚力', '摆大巴', '防守反击', '稳守']):
            items.append("C2不胜止颓+死守")

        # 3. 主力完整, 541大巴
        if ('541' in cold_info or '铁桶' in cold_info or '大巴' in cold_info or '摆大巴' in cold_info or '密集防守' in cold_info):
            items.append("C3大巴密集防守")

        # 4. 客场无包袱, 只求平局
        if any(w in cold_info for w in ['无心理包袱', '只求平局', '目标平局', '客场拿分', '不压上', '死守']):
            items.append("C4客场无包袱只求平")

        # 5. 过往2次逼平/战胜过热队
        if any(w in cold_info for w in ['逼平', '战平', '战胜过', '历史不惧', '交锋占优', '击败']):
            items.append("C5历史交锋不惧")

        # 6. 弱队定位球/远射/反击强 (破僵手段)
        if any(w in cold_info for w in ['定位球', '定位球强', '远射', '反击强', '反击效率', '偷袭']):
            items.append("C6弱队定位球/反击强")

        return items

    # ============================================================
    # 三、盘赔冷门信号
    # ============================================================
    @staticmethod
    def _safe_float(v, default=0.0):
        """数值安全兜底: None/NaN/Inf/非数值 → default (P0 脏数据防崩溃)."""
        try:
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (TypeError, ValueError):
            return default

    def _check_line_signals(self, hdp_val: float, hot_odds: float, line_note: str = '') -> List[str]:
        items = []
        hdp = self._safe_float(hdp_val)      # P0: 空/乱码盘口 → 0.0 平手兜底
        hot_odds = self._safe_float(hot_odds, 99.0)

        # 1. 强队让深盘(≥1球) + 大小球只开2.5及小
        if hdp <= -1.0 and '2.5' in line_note:
            items.append("L1深盘+小盘(2.5)")

        # 2. 大热低赔 (原始赔率判断, 补充去水概率信号见 _check_fair_signals)
        if 0 < hot_odds < 1.8:
            items.append("L2大热低赔")

        # 3. 多源赔率分歧 (P0: 分歧>5% 放大冷门风险)
        if self._odds_disparity > 0.05:
            items.append("L3多源赔率分歧%.0f%%" % (self._odds_disparity * 100))

        return items

    # ============================================================
    # 去水公平概率信号 (P0: 平赔参与热门判定 + 机构抽水归一)
    # ============================================================
    def _check_fair_signals(self) -> List[str]:
        items = []
        fh, fa, fd = self._fair
        if fh is None or fa is None:
            return items
        if fd is None:
            fd = 1.0 - fh - fa
        vals = [fh, fa, fd]
        if any(not (0 < v < 1) for v in vals):
            return items
        max_fair = max(vals)
        fav = 'home' if max_fair == fh else ('away' if max_fair == fa else 'draw')
        # 1. 平局为市场最大概率 → 无明显热门
        if fav == 'draw':
            items.append("L4平局为最大公平概率(无明显热门)")
        elif fd >= 0.30 and max_fair - fd <= 0.06:
            items.append("L4平局接近热门(平局价值高)")
        # 2. 大热 = 去水公平概率≥55% (替代单纯原始低赔)
        if max_fair >= 0.55:
            items.append("L2大热低赔(去水概率>=55%%)")
        # 3. 主客公平概率差≤5%且非平局热门 → 强行标热失真提示
        if abs(fh - fa) <= 0.05 and fav != 'draw' and max_fair < 0.55:
            items.append("L5主客接近无明显热门(慎标冷门)")
        return items

    # ============================================================
    # 结构化量化特征信号 (P1: 伤停/疲劳/样本量/攻防差)
    # ============================================================
    def _check_feature_signals(self, feature_pack) -> List[str]:
        items = []
        fp = feature_pack or {}
        hot_side = fp.get('hot_side', 'home')
        hi = self._safe_float(fp.get('home_injury_weight'), 1.0)
        ai = self._safe_float(fp.get('away_injury_weight'), 1.0)
        # 1. 热门方结构化伤停 (系数<0.95 视为有效减损)
        if hot_side == 'home' and 0 < hi < 0.95:
            items.append("F1热门方伤停(系数%.2f)" % hi)
        elif hot_side == 'away' and 0 < ai < 0.95:
            items.append("F1热门方伤停(系数%.2f)" % ai)
        # 2. 疲劳修正
        fat = self._safe_float(fp.get('fatigue_level'), 1.0)
        if 0 < fat < 0.95:
            items.append("F2疲劳修正(系数%.2f)" % fat)
        # 3. 低样本不确定性
        nh = int(self._safe_float(fp.get('sample_n_home'), 0))
        na = int(self._safe_float(fp.get('sample_n_away'), 0))
        if hot_side == 'home' and 0 < nh < 4:
            items.append("F3热门方样本不足(%d场)" % nh)
        elif hot_side == 'away' and 0 < na < 4:
            items.append("F3热门方样本不足(%d场)" % na)
        # 4. 基本面攻防差小 → 冷门温床
        diff = abs(self._safe_float(fp.get('lam_base_diff'), 99.0))
        if 0 <= diff <= 0.3:
            items.append("F4基本面攻防接近(冷门温床)")
        return items

    # ============================================================
    # 四、场地与环境加分项
    # ============================================================
    def _check_env(self, cold_info: str, hot_info: str) -> List[str]:
        items = []

        # 人工草/高原/寒冷/场地
        if any(w in cold_info for w in ['人工草', '高原', '寒冷', '场地']):
            items.append("E1特殊场地(人工草/高原)")

        # 暴雨/高温
        if any(w in cold_info for w in ['暴雨', '高温', '大雨', '雨战']):
            items.append("E2恶劣天气")

        # 裁判宽松/身体对抗
        if any(w in cold_info for w in ['裁判宽松', '身体对抗', '肉搏', '凶狠']):
            items.append("E3对抗激烈")

        return items

    # ============================================================
    # 欧冠资格赛专项信号
    # ============================================================
    def _check_ucl_signals(self, hot_info: str, cold_info: str) -> List[str]:
        items = []

        # U1: 五大联赛休赛/未开赛 (无实战)
        if any(w in hot_info for w in ['未开赛', '休赛', '未开始', '友谊赛', '热身赛', '没有联赛']):
            items.append("U1五大联赛休赛无实战")

        # U2: 缺2名主力后卫 (中卫+边卫)
        if sum(1 for w in ['中卫', '边卫', '边后卫', '后卫', '防线'] if w in hot_info) >= 2:
            items.append("U2双后卫主力缺阵")

        # U3: 小国/联赛进行中 (对方节奏好)
        if any(w in cold_info for w in ['联赛正常', '捷甲', '瑞典超', '哈萨', '亚美尼', '联赛开打', '正式比赛节奏']):
            items.append("U3小国联赛进行中节奏好")

        # U4: 人工草魔鬼主场
        if any(w in cold_info for w in ['人工草', '魔鬼主场', '北极', '高原']):
            items.append("U4人工草魔鬼主场")

        # U5: 首回合 (资格赛保守)
        if '首回合' in cold_info or '首回合' in hot_info or '资格赛' in cold_info:
            items.append("U5首回合保守")

        return items

    # ============================================================
    # 欧联资格赛专项信号 (Europa League Qualifying)
    # ============================================================
    def _check_uel_signals(self, hot_info: str, cold_info: str, h2h: str) -> List[str]:
        items = []

        # EL1: 五大联赛球队降级欧联 (欧冠淘汰/附加赛出局, 战意存疑)
        if any(w in hot_info for w in ['欧冠淘汰', '欧冠出局', '欧冠附加赛出局', '空降欧联', '掉欧联', '欧冠资格赛淘汰']):
            items.append("EL1欧冠掉队战意存疑")

        # EL2: 有降级保底 → 中游队战意打折 (欧联淘汰掉欧协联, 不会出局)
        if any(w in hot_info for w in ['掉欧协联', '降级欧协联', '保底', '欧协联', '还有欧战', '不会出局']):
            items.append("EL2有欧协联保底战意打折")

        # EL3: 协会排名低 → 杯赛冠军实力一般 (21-33名球队)
        if any(w in hot_info for w in ['杯赛冠军', '小国杯赛', '协会排名低', '排名21', '排名22', '排名23', '排名24', '排名25']):
            items.append("EL3小协会杯赛冠军")

        # EL4: 主要路径中游球队 (无争冠动力, 只为欧战名额)
        if any(w in cold_info for w in ['主要路径', '联赛第3', '联赛第4', '殿军', '欧战名额', '只为欧战']):
            items.append("EL4主要路径中游战意")

        # EL5: 首回合客场进球规则仍有效 (欧联保留客场进球, 客队可能求稳)
        if any(w in cold_info for w in ['客场进球', '首回合保守', '只求客场进球', '客场拿分']):
            items.append("EL5客场进球规则求稳")

        return items

    # ============================================================
    # 五、交锋历史信号
    # ============================================================
    def _check_h2h_risk(self, h2h: str) -> List[str]:
        items = []

        # 1. 历史交锋平局多/小球 (闷平风险)
        if any(w in h2h for w in ['平局', '小球', '闷平', '0-0', '平局多', '60%平局', '平局居多']):
            items.append("D1历史交锋平局多/小球")

        # 2. 冷门方历史曾逼平/战胜热门
        if any(w in h2h for w in ['逼平', '战胜', '战平', '不惧', '克制']):
            items.append("D2冷门方历史不惧热门")

        return items

    # ============================================================
    # 五、排除误区
    # ============================================================
    def _check_exclusions(self, hot_info: str, cold_info: str, h2h: str,
                          rank_gap: float) -> List[str]:
        excl = []

        # 1. 强队轮换全替补
        if any(w in hot_info for w in ['轮换全替补', '全替补', '大轮换']):
            excl.append("X1强队轮换(非冷门)")

        # 2. 两队排名差距≤3位
        if rank_gap and 0 < rank_gap <= 3:
            excl.append("X2实力接近(排名差≤3)")

        # 3. 弱队主场常年碾压
        if any(w in cold_info for w in ['常年主场', '主场碾压', '主场压制']):
            excl.append("X3主场固有优势(非冷门)")

        return excl

    # ============================================================
    # 主入口
    # ============================================================
    def assess(self, hot_team: str, hot_info: str, cold_info: str,
               h2h: str, hdp_val: float, hot_odds: float,
               line_note: str = '', rank_gap: float = None,
               league_type: str = '',
               fair_h: float = None, fair_a: float = None, fair_d: float = None,
               odds_disparity: float = 0.0, cup_mode: bool = None,
               feature_pack: dict = None, hot_is_home: bool = None) -> Dict:
        """完整冷门评估 v3 (纯数据触发).

        league_type: ucl/uel/uefa = 欧足联资格赛专项 (cup_mode 显式开关, 联赛不套用杯赛修正)
        fair_h/fair_a/fair_d: 去水后公平概率 (P0: 平赔参与热门判定, 消除抽水偏差)
        odds_disparity: 多源赔率分歧 0~1 (P0: >0.05 放大冷门风险)
        feature_pack: 结构化量化特征 (P1: 伤停系数/疲劳/样本量/攻防差)
        hot_is_home: 热门方是否主队, 用于输出带方向的 risk_signal (±10% 前置截断)
        """
        self._odds_disparity = max(0.0, self._safe_float(odds_disparity))
        self._fair = (fair_h, fair_a, fair_d)
        self._cup_mode = (league_type in ('ucl', 'uel', 'uefa')) if cup_mode is None else bool(cup_mode)
        hdp_val = self._safe_float(hdp_val)   # P0: 空/乱码盘口 → 0.0 平手兜底

        self.hot_items = self._check_hot_risks(hot_info)
        self.cold_items = self._check_cold_adv(cold_info)
        self.line_items = self._check_line_signals(hdp_val, hot_odds, line_note)
        self.fair_items = self._check_fair_signals()
        self.feature_items = self._check_feature_signals(feature_pack)
        self.env_items = self._check_env(cold_info, hot_info)
        self.h2h_items = self._check_h2h_risk(h2h)
        self.exclusions = self._check_exclusions(hot_info, cold_info, h2h, rank_gap)
        # 欧足联资格赛专项: 仅杯赛/资格赛模式启用 (P1: 联赛不套用杯赛修正)
        self.ucl_items = self._check_ucl_signals(hot_info, cold_info) if (self._cup_mode and league_type in ('ucl', 'uefa')) else []
        self.uel_items = self._check_uel_signals(hot_info, cold_info, h2h) if (self._cup_mode and league_type in ('uel', 'uefa')) else []

        all_signals = (self.hot_items + self.cold_items + self.line_items + self.fair_items
                       + self.feature_items + self.env_items + self.h2h_items
                       + self.ucl_items + self.uel_items)
        self.total_count = len(all_signals)

        # 分级 (用户规则)
        if self.total_count >= 6:
            level = "高危大冷"
            rec = "弱队直接赢球概率很高"
        elif self.total_count >= 4:
            level = "中度风险"
            rec = "直接看好下盘"
        elif self.total_count >= 2:
            level = "轻度风险"
            rec = "防平局即可"
        else:
            level = "低风险"
            rec = "热门方可信"

        # 排除误区检查
        if self.exclusions:
            excl_note = " [排除误区] " + "、".join(self.exclusions)
            # 若有误区, 降低一级
            if self.total_count >= 6:
                level = "中度风险"
                rec = "直接看好下盘(但存在排除误区)"
        else:
            excl_note = ""

        # P2: 冷门强度 → 带方向 RiskSignal, 前置硬限幅 ±10% (不延迟到 λ 阶段拦截)
        level_risk = {"高危大冷": 0.10, "中度风险": 0.06, "轻度风险": 0.03, "低风险": 0.0}
        upset_signal = level_risk.get(level, 0.0)
        extra = 0.0
        if self._odds_disparity > 0.05:
            extra += 0.01
        if len(self.feature_items) >= 2:
            extra += 0.01
        upset_signal = max(0.0, min(0.10, upset_signal + extra))
        risk_signal = 0.0
        if hot_is_home is not None:
            risk_signal = -upset_signal if hot_is_home else upset_signal
            risk_signal = max(-0.10, min(0.10, risk_signal))

        return {
            "hot_team": hot_team,
            "triggered_count": self.total_count,
            "hot_items": self.hot_items,
            "cold_items": self.cold_items,
            "line_items": self.line_items,
            "fair_items": self.fair_items,
            "feature_items": self.feature_items,
            "env_items": self.env_items,
            "h2h_items": self.h2h_items,
            "ucl_items": self.ucl_items,
            "uel_items": self.uel_items,
            "exclusions": self.exclusions,
            "level": level,
            "recommendation": rec,
            "note": excl_note,
            "fair_probs": {"home": round(fair_h, 4) if fair_h is not None else None,
                           "draw": round(fair_d, 4) if fair_d is not None else None,
                           "away": round(fair_a, 4) if fair_a is not None else None},
            "odds_disparity": round(self._odds_disparity, 4),
            "cup_mode": self._cup_mode,
            "score_breakdown": {
                "hot": len(self.hot_items), "cold": len(self.cold_items),
                "line": len(self.line_items), "fair": len(self.fair_items),
                "feature": len(self.feature_items), "env": len(self.env_items),
                "h2h": len(self.h2h_items), "ucl": len(self.ucl_items), "uel": len(self.uel_items),
            },
            "upset_signal": round(upset_signal, 4),
            "risk_signal": round(risk_signal, 4),
        }

    def format_result(self, r: Dict) -> str:
        lines = []
        lines.append(f"热门方: {r['hot_team']}")
        lines.append(f"命中条件总数: {r['triggered_count']}")
        if r['hot_items']:
            lines.append(f"【强队隐患】" + "、".join(r['hot_items']))
        if r['cold_items']:
            lines.append(f"【弱队优势】" + "、".join(r['cold_items']))
        if r['line_items']:
            lines.append(f"【盘赔信号】" + "、".join(r['line_items']))
        if r['env_items']:
            lines.append(f"【场地加分】" + "、".join(r['env_items']))
        if r.get('h2h_items'):
            lines.append(f"【交锋信号】" + "、".join(r['h2h_items']))
        if r.get('ucl_items'):
            lines.append(f"【欧冠资格赛】" + "、".join(r['ucl_items']))
        if r.get('uel_items'):
            lines.append(f"【欧联资格赛】" + "、".join(r['uel_items']))
        if r['exclusions']:
            lines.append(f"【排除误区】" + "、".join(r['exclusions']))
        lines.append(f"★ 冷门等级: {r['level']}")
        lines.append(f"  建议: {r['recommendation']}")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    engine = UpsetEngineV2()

    # 测试: 弗拉门戈 vs 圣保罗
    print("=" * 70)
    print("  测试: 弗拉门戈 vs 圣保罗")
    hot = "弗拉门戈近10场6胜3平1负不败率90%主场9场不败核心前腰帕奎塔伤缺轻敌领先后收缩防守长途飞行体能下滑无保级压力"
    cold = "圣保罗连续6轮不胜客场7场不胜541大巴死守只求平局无心理包袱核心卢卡斯莫拉赛季报销主力中卫伤缺"
    r = engine.assess("弗拉门戈", hot, cold, "历史60%平局", -1.0, 1.45, "大小球2.5", rank_gap=10)
    print(engine.format_result(r))
    print(f"\n  实际: 弗拉门戈1-1圣保罗 → 引擎判断{'正确✅' if r['level'] in ('中度风险','高危大冷') else '需复盘'}")
