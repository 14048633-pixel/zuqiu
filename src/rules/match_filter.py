"""赛事过滤 + 黑名单 + 两回合杯赛λ修正 (SOP 数据清洗落地 v2)
================================================================
一、赛事类型过滤 (剔除污染样本, 防止混入 winrate_stats.json 基准):
  - friendly  友谊赛 (排除)
  - youth     U21/U19/青年队 (排除)
  - postponed 延期/推迟 (排除, 未开赛不算样本)
  - abandoned 腰斩/中断 (排除, 结果无效)
  - awarded   判改比分/判负/弃权 (排除, 非真实竞技结果)
  命中任一 -> excluded=True + reason; 自动写入黑名单。

二、黑名单 (strategy_data/blacklist.json):
  {"excluded_events": [{"league","home","away","reason","ts"}],
   "excluded_teams": ["队名", ...]}
  黑名单中的赛事/球队不参与胜率统计。

三、两回合杯赛:
  two_leg_lambda_coefs(leg_no, is_home_leg) -> 主客场基准修正系数
  首回合主场方略占先机(home_att×1.03); 次回合需追分/守成(att/def微调)。
"""
import json
import os
from datetime import datetime

BLACKLIST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              "strategy_data", "blacklist.json")

# 类型关键词 -> 排除原因
EXCLUDE_RULES = [
    (("friendly", "友谊赛", "热身赛"), "friendly 友谊/热身赛, 剔除"),
    (("u21", "u19", "青年队", "青年", "reserve", "预备队"), "youth 青年/预备队赛事, 剔除"),
    (("postponed", "延期", "推迟"), "postponed 延期未赛, 剔除"),
    (("abandoned", "腰斩", "中断"), "abandoned 腰斩/中断, 结果无效, 剔除"),
    (("awarded", "判改", "判负", "弃权", "forfeit"), "awarded 判改比分/弃权, 非竞技结果, 剔除"),
]


def filter_match(meta):
    """赛事过滤。

    meta: {"type"/"league"/"home"/"away"/"status"} 至少含 league/home/away。
    返回: {"excluded": bool, "reason": str, "category": str}
    """
    text = " ".join(str(v) for v in meta.values()).lower()
    for kws, reason in EXCLUDE_RULES:
        for kw in kws:
            if kw.lower() in text:
                return {"excluded": True, "reason": reason, "category": kw}
    return {"excluded": False, "reason": "", "category": ""}


def add_blacklist_event(meta, reason, path=BLACKLIST_PATH):
    """写入黑名单(excluded_events)。"""
    try:
        data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        data.setdefault("excluded_events", [])
        entry = {
            "league": meta.get("league", ""),
            "home": meta.get("home", ""),
            "away": meta.get("away", ""),
            "reason": reason,
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if entry not in data["excluded_events"]:
            data["excluded_events"].append(entry)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def two_leg_lambda_coefs(leg_no, is_home_leg):
    """两回合杯赛主客场基准修正 (乘在 λ 上)。

    leg_no: 1 首回合 / 2 次回合; is_home_leg: 该方本回合是否主场。
    返回 {"home_att": x, "away_att": x, "home_def": x, "away_def": x}
    注: 系数为经验默认, 具体赛事可按主客场战绩覆盖。
    """
    if leg_no == 1:
        if is_home_leg:
            # 首回合主场: 略占先机, 客队保守
            return {"home_att": 1.03, "away_att": 0.97, "home_def": 1.0, "away_def": 1.0}
        return {"home_att": 0.97, "away_att": 1.03, "home_def": 1.0, "away_def": 1.0}
    # 次回合: 总比分未决, 主场方需主动(攻击+), 客场方守成(防守+)
    if is_home_leg:
        return {"home_att": 1.05, "away_att": 0.95, "home_def": 1.02, "away_def": 1.0}
    return {"home_att": 0.95, "away_att": 1.05, "home_def": 1.0, "away_def": 1.02}