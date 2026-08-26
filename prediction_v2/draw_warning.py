# -*- coding: utf-8 -*-
"""平局预警模块 v2 (独立, 不改EV/不改方向, 只输出提醒)
规则来源:
  历史3.7万场(2015-2026, 9联赛)平局赔率规律 + 账本108注/当日20场实盘验证
  升级点(v2): 平赔区间为主信号, 按联赛修正阈值; 高危联赛/否决/深盘/form 为辅助信号
用法:
  from draw_warning import draw_warning_score
  info = {"league":..., "h2h":[...], "resonance":..., "model_leg":..., "form":...}
  sc, tags = draw_warning_score(info)  -> (分, [标签])
"""
import re

# ===== 历史3.7万场按联赛平局峰值区(平局率>=33%为高危, 28~33%为提醒) =====
# 高危区: 平局率>=33% (历史实测 西甲37.5%/西乙33.2%/意甲33.2%/法甲33.0%)
ODDS_HIGH_ZONE = {
    "西甲": (2.8, 3.1), "西乙": (2.8, 3.1),
    "意甲": (3.0, 3.3), "法甲": (3.0, 3.3),
}
# 提醒区: 平局率28~33% (次级/主流分胜负型联赛的次高窗口)
ODDS_WARN_ZONE = {
    "英超": (3.0, 3.3), "英冠": (3.0, 3.3),
    "西甲": (3.1, 3.4), "西乙": (3.1, 3.4),
    "意甲": (3.3, 3.6), "法甲": (3.3, 3.6),
    "荷甲": (3.2, 3.5), "德乙": (3.4, 3.7), "德甲": (3.6, 3.9),
}
# 未入表联赛的通用区间(账本108注+当日20场实盘验证: 平赔3.0~3.8平局率54%)
GENERIC_HIGH = (2.8, 3.1)   # 无表联赛 高危区
GENERIC_WARN = (3.1, 3.8)   # 无表联赛 提醒区
# 高危联赛(账本17平局样本: 巴甲2/3 西甲1/1 土超1/2 葡超1/2 西乙2/5 阿甲2/6 荷甲2/7 美职3/11 英冠2/10)
HIGH_RISK_LEAGUES = {"巴甲", "西甲", "土超", "葡超", "西乙", "阿甲", "荷甲", "美职", "智利甲", "英冠"}
# 深盘让球: 让球主(-0.5)及更深 -> 平局场全灭 (历史4/4输, Ajax -1.2也输)
DEEP_HANDI_TH = -0.5


def _h2h_draw_odds(h2h):
    try:
        if h2h and len(h2h) >= 3 and h2h[1]:
            return float(h2h[1])
    except Exception:
        pass
    return None


def _odds_level(league, dp):
    """平赔区间打分(主信号): 高危+3 / 提醒+2 / 观察+1 / 无信号0"""
    if dp is None:
        return 0, ""
    hi = ODDS_HIGH_ZONE.get(league)
    wa = ODDS_WARN_ZONE.get(league)
    if hi and hi[0] <= dp <= hi[1]:
        return 3, "平赔%.2f高危区" % dp
    if wa and wa[0] <= dp <= wa[1]:
        return 2, "平赔%.2f提醒区" % dp
    if hi or wa:
        if dp < (hi or wa)[0]:
            return 1, "平赔%.2f偏低" % dp
        return 0, ""
    # 未入表联赛通用区间
    if GENERIC_HIGH[0] <= dp <= GENERIC_HIGH[1]:
        return 3, "平赔%.2f高危区" % dp
    if GENERIC_WARN[0] <= dp <= GENERIC_WARN[1]:
        return 2, "平赔%.2f提醒区" % dp
    return 0, ""


def _is_deep_handi(leg):
    m = re.search(r"让球(主|客)\(([+-]?[\d.]+)\)", leg or "")
    if not m:
        return False
    try:
        return float(m.group(2)) < DEEP_HANDI_TH
    except Exception:
        return False


def draw_warning_score(info):
    """计算平局预警分(0~10)与触发标签. 不改EV/不改方向, 仅提醒."""
    score = 0
    tags = []
    league = info.get("league") or ""
    # 主信号: 平赔区间(按联赛修正)
    dp = _h2h_draw_odds(info.get("h2h"))
    s0, t0 = _odds_level(league, dp)
    score += s0
    if t0:
        tags.append(t0)
    # 辅助信号: 高危联赛
    if league in HIGH_RISK_LEAGUES:
        score += 1
        tags.append("高危联赛(历史平局率高)")
    # 辅助信号: 硬否决/过期盘/分歧 (veto场平局率29% vs 15%)
    res = info.get("resonance") or ""
    if "硬否决" in res or "否决" in res:
        score += 1
        tags.append("硬否决场次")
    # 辅助信号: 让球深盘 (-0.5及更深)
    leg = info.get("model_leg") or info.get("model") or ""
    if _is_deep_handi(leg):
        score += 1
        tags.append("让球深盘")
    # 辅助信号: form 强支持 (历史2/2全平)
    if info.get("form") == "强支持":
        score += 1
        tags.append("form强支持反向")
    # 辅助信号: form 冲突/弱冲突
    if info.get("form") in ("冲突", "弱冲突"):
        score += 1
        tags.append("form冲突")
    # 辅助信号: 模型腿为让球 (让球腿平局场走盘/输盘风险高)
    if "让球" in (leg or ""):
        score += 1
        tags.append("让球腿")
    return score, tags


def draw_warning_label(score):
    """分值 -> 提醒等级"""
    if score >= 5:
        return "防平高危"
    if score >= 3:
        return "防平提醒"
    if score >= 1:
        return "平局观察"
    return ""
