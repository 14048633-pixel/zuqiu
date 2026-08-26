"""全局去水模块 (SOP Step 4/31 落地)
=====================================
Overround = Σ(1/odds_i)
去水公平概率(比例法): fair_i = (1/odds_i) / Overround
EV = FairProb × RawOdds − 1   ← 所有打星/best_bet 判定基于去水后公平 EV

支持市场:
  - h2h 独赢: 3 个赔率
  - totals 大小球 / spreads 让球: 2 个赔率

纯标准库。用法:
  from de_vig import devig_odds, fair_ev, fair_ev_from_model
  probs, orr = devig_odds([2.37, 2.83, 3.88])
  ev = fair_ev(probs[0], 2.37)
"""
import math


def overround(odds):
    """抽水率 = Σ(1/odds)。odds 为列表(2 或 3 个)。"""
    return sum(1.0 / o for o in odds)


def devig_odds(odds):
    """比例法去水: 返回 (去水后概率列表[和为1], overround)。"""
    orr = overround(odds)
    probs = [(1.0 / o) / orr for o in odds]
    return probs, orr


def fair_ev(prob, raw_odds):
    """公平 EV = 去水概率 × 原始赔率 − 1。"""
    return prob * raw_odds - 1.0


def model_fair_prob(model_prob, overround_val):
    """模型概率去水校正 = 模型概率 / Overround (防止系统性高估)。"""
    return model_prob / overround_val


def fair_ev_from_model(model_prob, raw_odds, overround_val):
    """基于模型概率的去水 EV = (模型概率/Overround) × 原始赔率 − 1。"""
    fair = model_fair_prob(model_prob, overround_val)
    return fair_ev(fair, raw_odds)


def devig_h2h(home_odds, draw_odds, away_odds):
    """独赢市场三赔去水 → (主/平/客公平概率, overround)。"""
    return devig_odds([home_odds, draw_odds, away_odds])


def devig_two_way(over_odds, under_odds):
    """大小球/让球两结果市场去水 → (over概率, under概率, overround)。"""
    probs, orr = devig_odds([over_odds, under_odds])
    return probs[0], probs[1], orr