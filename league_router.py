# -*- coding: utf-8 -*-
"""联赛类型路由: 区分 联赛/杯赛/欧战, 为杯赛专用分支提供检测与映射 (2026-09-01).

背景: 旧逻辑把杯赛硬映射到国家顶级联赛 key (DFB Pokal->D1), 跨级别对战
(如低级别队 vs 德甲队) 被塞进德甲尺度计算, 导致伪EV (实测: 汉堡1911 vs 多特
输出主胜 EV+829% ★3, 主队无 Elo/无德甲数据被当成德甲均值队)。
本模块提供:
  - CUP_LEAGUES : 杯赛集合 (BSD 联赛英文名 -> {country, top_league})
  - is_cup()    : 是否杯赛
  - cup_meta()  : 杯赛元信息 (目标国家顶级联赛 key, 供参考系修正用)
  - route_league(): 统一路由 -> {type: cup|euro|league, top_league, country}
  - has_data_missing(): 数据缺失检测 (供伪EV防护消费端统一拦截)
"""
from __future__ import annotations

# 杯赛集合: BSD 联赛英文名 -> 归属国家 + 该国顶级联赛 key
# top_league 供后续"参考系修正"使用(低级别队按自身级别先验, 而非顶级联赛均值)
CUP_LEAGUES = {
    # 德国
    "DFB Pokal": {"country": "DE", "top_league": "D1"},
    # 意大利
    "Coppa Italia": {"country": "IT", "top_league": "I1"},
    "Supercoppa Italiana": {"country": "IT", "top_league": "I1"},
    # 英格兰
    "FA Cup": {"country": "EN", "top_league": "E0"},
    "EFL Cup": {"country": "EN", "top_league": "E0"},
    "EFL Trophy": {"country": "EN", "top_league": "E2"},
    # 西班牙
    "Copa del Rey": {"country": "ES", "top_league": "SP1"},
    "Supercopa de España": {"country": "ES", "top_league": "SP1"},
    # 法国
    "Coupe de France": {"country": "FR", "top_league": "F1"},
    "Coupe de la Ligue": {"country": "FR", "top_league": "F1"},
    "Trophée des Champions": {"country": "FR", "top_league": "F1"},
    # 巴西
    "Copa do Brasil": {"country": "BR", "top_league": "BR"},
    # 葡萄牙
    "Taça de Portugal": {"country": "PT", "top_league": "P1"},
    "Taça da Liga": {"country": "PT", "top_league": "P1"},
    # 荷兰
    "KNVB Beker": {"country": "NL", "top_league": "N1"},
    # 比利时
    "Beker van België": {"country": "BE", "top_league": "B1"},
    "Croky Cup": {"country": "BE", "top_league": "B1"},
    # 土耳其
    "Türkiye Kupası": {"country": "TR", "top_league": "T1"},
    # 阿根廷
    "Copa Argentina": {"country": "AR", "top_league": "ARG"},
    "Supercopa Argentina": {"country": "AR", "top_league": "ARG"},
    # 美国/加拿大
    "US Open Cup": {"country": "US", "top_league": "MLS"},
    "Canadian Championship": {"country": "CA", "top_league": "MLS"},
    # 日本
    "Emperor's Cup": {"country": "JP", "top_league": "JP1"},
    "J.League Cup": {"country": "JP", "top_league": "JP1"},
}

# 欧战: 跨联赛对战, 球队均为顶级联赛队(Elo 数据充足), 参考系问题远小于杯赛
EURO_LEAGUES = {
    "UEFA Champions League": {"top_league": "E0"},
    "UCL": {"top_league": "E0"},
    "UEFA Europa League": {"top_league": "E0"},
    "UEL": {"top_league": "E0"},
    "UEFA Conference League": {"top_league": "E0"},
    "UECL": {"top_league": "E0"},
}


def is_cup(league_name: str) -> bool:
    """按 BSD 联赛英文名判断是否为杯赛."""
    return league_name in CUP_LEAGUES


def cup_meta(league_name: str):
    """杯赛元信息: {country, top_league}. 非杯赛返回 None."""
    return CUP_LEAGUES.get(league_name)


def route_league(league_name: str) -> dict:
    """统一路由: 返回 {type, top_league, country}.
      - type='cup'   : 杯赛 -> 走杯赛专用分支(参考系修正/伪EV防护)
      - type='euro'  : 欧战 -> 参考系可用, 但标注跨联赛对战
      - type='league': 普通联赛 -> 现有联赛流程(零改动)
    """
    meta = cup_meta(league_name)
    if meta:
        return {"type": "cup", "top_league": meta["top_league"], "country": meta["country"]}
    if league_name in EURO_LEAGUES:
        return {"type": "euro", "top_league": EURO_LEAGUES[league_name]["top_league"], "country": None}
    return {"type": "league", "top_league": None, "country": None}


# 数据缺失关键词: 命中任一 -> 该场概率/Elo/λ 存在静默降级, EV 不可信
DATA_MISSING_KEYWORDS = (
    "无Elo历史",        # 默认 1500, 零信息
    "无联赛数据",        # 被联赛均值兜底(如低级别队塞进顶级联赛)
    "无主场近8场",       # 无主客场近况
    "无客场近8场",
    "用联赛均值兜底",    # λ 非有限被均值替换
    # 2026-09-02 修复: match_report 实际文案是 "无{league}联赛数据(用联赛均值)" 与
    # "泊松λ用联赛均值兜底", 此前 "无联赛数据"/"用联赛均值兜底" 均失配
    # (中间隔着联赛代码/缺"兜底"二字) -> 德丙队 vs 德甲队伪EV +119% 漏拦。
    "用联赛均值",        # 覆盖 "(用联赛均值)" 与 "(用联赛均值兜底)" 两种写法
)


def has_data_missing(data_warnings) -> str | None:
    """检测是否任一队数据缺失(Elo默认/无联赛数据/无近况/λ兜底).

    返回触发警告原文(供消费端拦截BEST并标注), 无缺失返回 None。
    依据: 汉堡1911 vs 多特(DFB Pokal) 主队无数据被当德甲均值 -> 伪EV +829% ★3。
    """
    if not data_warnings:
        return None
    for w in data_warnings:
        if any(k in w for k in DATA_MISSING_KEYWORDS):
            return w
    return None
