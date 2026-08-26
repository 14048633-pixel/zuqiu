"""多维风控 + EV噪声阈值 + 仓位纪律 (SOP Step 7 / Step 31 落地)
================================================================
一、风险分 0-1 (多维加权, 取代单一"让平集中度"指标):
  因子与权重:
    - 赔率分歧指数  (多机构同盘口概率标准差, 0~1 归一)  权重 0.30
    - 盘口历史ROI   (该联赛+盘口近100注ROI, 0~1 归一)   权重 0.30
    - 球队大小分漂移 (近5场实际进球 vs λ预期的偏离)     权重 0.20
    - 连亏状态       (当前连亏注数, 3注起算)            权重 0.20
  风险分 > 0.6 -> 星级-1, 取消 best_bet 资格。

二、EV 噪声区间 (过滤 0~8% 微幅正EV, 防止低价值信号放大交易频次):
  ev < 0            -> 放弃
  0 <= ev < 0.08    -> 噪声区间, 仅观察不出推荐
  ev >= 0.08        -> 进入候选池
  best_bet 判定仍需叠加: 赔率下限(高级联赛1.60/次级1.40) + 历史ROI过滤。

三、仓位纪律 (三级风控):
  - 单日所有投注总额 <= 本金 15%
  - 连亏 3 注 -> 仓位减半; 连亏 5 注 -> 当日停止推荐
  - 单策略回撤 >= 本金 10% -> 停用该策略至少 7 天
  - 单周期盈利 > 本金 20% -> 提取 50% 利润锁定, 剩余维持原仓位
"""
import math


# ---- 配置默认值 (可用 strategy_data/system_config.json 覆盖) ----
DEFAULTS = {
    "ev_noise_min": 0.08,        # EV 安全阈值: 0~8% 为噪声区间
    "min_odds_major": 1.60,      # 高级联赛赔率下限
    "min_odds_minor": 1.40,      # 次级联赛赔率下限
    "risk_threshold": 0.6,       # 风险分阈值, 超过则降级
    "daily_limit_pct": 0.15,     # 单日总投注上限
    "lose3_halve": True,         # 连亏3注仓位减半
    "lose5_stop": True,          # 连亏5注当日停推
    "drawdown_stop_pct": 0.10,   # 单策略回撤止损
    "drawdown_stop_days": 7,     # 止损停用天数
    "profit_lock_pct": 0.20,     # 盈利锁定线
    "profit_lock_ratio": 0.50,   # 锁定利润比例
}


def risk_score(dispersion=0.0, hist_roi=0.0, drift=0.0, lose_streak=0, weights=None):
    """多维风险分 0-1。

    dispersion: 多机构概率标准差 (0~1)
    hist_roi:  该联赛+盘口近100注ROI (-1~+inf, 归一: max(0, -roi) 截断到1)
    drift:     球队大小分漂移 |实际-预期|/预期 (0~1)
    lose_streak: 当前连亏注数
    """
    w = weights or {"dispersion": 0.30, "hist_roi": 0.30, "drift": 0.20, "lose": 0.20}
    disp_n = max(0.0, min(1.0, float(dispersion) / 0.15))          # 15% 离散 => 1.0
    roi_n = max(0.0, min(1.0, -float(hist_roi)))                   # roi<=0 视为风险
    drift_n = max(0.0, min(1.0, float(drift)))
    lose_n = max(0.0, min(1.0, (float(lose_streak) - 2) / 3.0))    # 3注起算, 5注=1.0
    score = (w["dispersion"] * disp_n + w["hist_roi"] * roi_n +
             w["drift"] * drift_n + w["lose"] * lose_n)
    return round(min(1.0, score), 4)


def ev_tier(ev, risk=0.0, threshold=None):
    """EV 分级 + 风险降级。

    返回: {tier: "best"|"candidate"|"noise"|"drop", downgraded: bool, reason: str}
    """
    threshold = DEFAULTS["ev_noise_min"] if threshold is None else threshold
    if ev < 0:
        return {"tier": "drop", "downgraded": False, "reason": "EV<0"}
    downgraded = risk > DEFAULTS["risk_threshold"]
    if downgraded:
        return {"tier": "candidate", "downgraded": True,
                "reason": "风险分%.2f>%.2f, 星级-1且取消best_bet" % (risk, DEFAULTS["risk_threshold"])}
    if ev < threshold:
        return {"tier": "noise", "downgraded": False,
                "reason": "EV=%.1f%% 处于0~%.0f%%噪声区间, 仅观察" % (ev * 100, threshold * 100)}
    return {"tier": "best", "downgraded": False, "reason": "通过"}


def check_position(state):
    """仓位纪律检查。

    state: {"day_staked": float, "bankroll": float, "lose_streak": int,
            "strategy_drawdown": float, "strategy_days_off": int,
            "cycle_profit": float, "stake_ratio": float}
    返回: {ok: bool, stake_ratio: float, action: str, rules: [str]}
    """
    bankroll = max(float(state.get("bankroll", 100.0)), 1e-9)
    stake = float(state.get("stake_ratio", 0.05))
    rules = []

    day_used = float(state.get("day_staked", 0.0)) / bankroll
    if day_used + stake > DEFAULTS["daily_limit_pct"]:
        rules.append("单日投注将超本金15%上限")
        return {"ok": False, "stake_ratio": stake, "action": "reject",
                "rules": rules}

    lose = int(state.get("lose_streak", 0))
    if lose >= 5 and DEFAULTS["lose5_stop"]:
        rules.append("连亏%d注, 当日停止推荐" % lose)
        return {"ok": False, "stake_ratio": stake, "action": "stop_day", "rules": rules}
    if lose >= 3 and DEFAULTS["lose3_halve"]:
        stake = stake / 2.0
        rules.append("连亏%d注, 仓位减半至%.1f%%" % (lose, stake * 100))

    dd = float(state.get("strategy_drawdown", 0.0))
    off_days = int(state.get("strategy_days_off", 0))
    if dd >= DEFAULTS["drawdown_stop_pct"] and off_days < DEFAULTS["drawdown_stop_days"]:
        rules.append("单策略回撤%.1f%%达止损线, 停用%d天(已%d天)" %
                     (dd * 100, DEFAULTS["drawdown_stop_days"], off_days))
        return {"ok": False, "stake_ratio": stake, "action": "pause_strategy", "rules": rules}

    profit = float(state.get("cycle_profit", 0.0)) / bankroll
    action = "bet"
    if profit > DEFAULTS["profit_lock_pct"]:
        rules.append("周期盈利%.1f%%>%.0f%%, 提取50%%利润锁定" %
                     (profit * 100, DEFAULTS["profit_lock_pct"] * 100))
        action = "bet_locked"
    rules.append("通过: 单注仓位%.1f%%" % (stake * 100))
    return {"ok": True, "stake_ratio": round(stake, 4), "action": action, "rules": rules}