"""盘口变动时间衰减权重 + 风险等级量化 (SOP 临场盘口 v2)
================================================================
问题: 开赛12小时前升盘 vs 赛前5分钟急速跳水, 风险等级完全不同,
      单纯二分"可信/陷阱"失真。
方案 (距开赛时间权重):
  >12h         -> 0.30 (远期变动, 参考意义低)
  3h~12h       -> 0.60
  0.5h~3h      -> 0.80
  0~30分钟     -> 1.00 (临场急速变动, 权重最高)

加权变动 = 原始变动幅度 x 时间权重; 量化风险等级 0-3:
  0 低    |加权变动|<=0.03
  1 中    |加权变动|<=0.08
  2 高    |加权变动|<=0.15
  3 极高  |加权变动|>0.15
用法:
  from line_movement import time_weight, risk_level, weighted_change
"""
# 默认时间权重分档 (小时)
DEFAULTS = {
    "far_h": 12.0,     # 超过视为远期
    "mid_h": 3.0,      # 3~12h 为中段
    "near_h": 0.5,     # 0.5h 内为临场
    "w_far": 0.30,
    "w_mid": 0.60,
    "w_near": 0.80,
    "w_now": 1.00,
}


def time_weight(hours_to_kickoff, cfg=None):
    """距开赛时间 -> 权重。hours_to_kickoff 为小时数(>=0)。"""
    c = dict(DEFAULTS)
    if cfg:
        c.update(cfg)
    h = float(hours_to_kickoff)
    if h > c["far_h"]:
        return c["w_far"]
    if h > c["mid_h"]:
        return c["w_mid"]
    if h > c["near_h"]:
        return c["w_near"]
    return c["w_now"]


def weighted_change(raw_change, hours_to_kickoff, cfg=None):
    """原始盘口/水位变动幅度 x 时间权重。"""
    return raw_change * time_weight(hours_to_kickoff, cfg)


def risk_level(weighted, thresholds=(0.03, 0.08, 0.15)):
    """加权变动 -> 风险等级 0-3 + 标签 + 建议。"""
    w = abs(float(weighted))
    if w <= thresholds[0]:
        return {"level": 0, "label": "低", "advice": "变动轻微, 维持赛前判断"}
    if w <= thresholds[1]:
        return {"level": 1, "label": "中", "advice": "温和异动, 结合水位方向参考"}
    if w <= thresholds[2]:
        return {"level": 2, "label": "高", "advice": "显著异动, 诱盘嫌疑上升, 降低置信"}
    return {"level": 3, "label": "极高", "advice": "极端异动(临场急速跳水), 大热必死警戒, 停止追热"}