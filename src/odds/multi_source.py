"""多源赔率容灾 + 共识去水 (SOP Step 2 / Step 4 落地)
================================================================
一、解决"赔率源单一依赖"的 3 层设计:
  1. 源优先级 (source_priority):
       A 级: the-odds-api 聚合(Pinnacle/Matchbook 等顶级锐盘)
       B 级: API-Football 官方赔率
       C 级: 本地历史快照(prediction_v2/output/odds_snapshots)
       D 级: 用户手工盘口(标注 source_quality=manual)
  2. 共识计算 (consensus): 同一市场多机构去水概率取中位数,
       返回 共识概率 + 分歧指数(概率标准差) + 参与机构数。
       分歧指数>0.05 -> 标红(盘口分歧大, 降级为观察)
  3. 降级补位 (resolve): 主源缺失/异常时按 B->C->D 顺序补位,
       任何补位都写 source_quality 标签, 缺失源不静默填0。

二、与 de_vig.py 的关系:
  de_vig 负责"单机构单市场去水", 本模块负责"多机构选优/共识",
  两者串联: resolve() 得到权威赔率 -> devig() 得到公平概率。
"""
import math


# 源优先级 (值越小越权威)
SOURCE_PRIORITY = {
    "the_odds_api": 0,
    "api_football": 1,
    "snapshot": 2,
    "manual": 3,
}
SOURCE_LABEL = {v: k for k, v in SOURCE_PRIORITY.items()}


def source_priority(source):
    """返回源优先级数字, 未知源按 D 级处理。"""
    return SOURCE_PRIORITY.get(str(source).lower(), 3)


def consensus_probs(odds_list):
    """多机构同一市场去水概率共识。

    入参: 每行一家机构的赔率列表, 如 [[2.37, 2.83, 3.88], [2.35, 3.25, 3.34]]
    返回: {probs: 中位数去水概率, dispersion: 概率标准差均值, n_sources}
    """
    if not odds_list:
        return {"probs": [], "dispersion": 0.0, "n_sources": 0}
    n_outcomes = len(odds_list[0])
    devigged = []
    for row in odds_list:
        inv = [1.0 / max(o, 1e-9) for o in row]
        s = sum(inv)
        devigged.append([p / s for p in inv])
    probs = []
    for col in range(n_outcomes):
        vals = sorted(r[col] for r in devigged)
        med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        probs.append(round(med, 4))
    # 分歧指数 = 各结果概率标准差的均值
    disp_vals = []
    for col in range(n_outcomes):
        vals = [r[col] for r in devigged]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        disp_vals.append(math.sqrt(var))
    dispersion = round(sum(disp_vals) / len(disp_vals), 4)
    return {"probs": probs, "dispersion": dispersion, "n_sources": len(devigged)}


def resolve(source_odds):
    """降级补位: 从 {source: odds} 中选最优可用源。

    source_odds: {source_name: {"odds": [...], "market": "h2h"}} 或 {"the_odds_api": None}
    返回: {"source": str, "odds": [...], "source_quality": "A".."D", "fallback": bool}
    """
    candidates = []
    for src, payload in (source_odds or {}).items():
        if payload is None:
            continue
        odds = payload.get("odds") if isinstance(payload, dict) else payload
        if not odds or all(o is None or o <= 0 for o in odds):
            continue
        candidates.append((source_priority(src), src, list(odds)))
    if not candidates:
        return {"source": None, "odds": [], "source_quality": "N/A", "fallback": True}
    candidates.sort(key=lambda x: x[0])
    rank, src, odds = candidates[0]
    return {
        "source": src,
        "odds": odds,
        "source_quality": chr(ord("A") + rank) if rank <= 3 else "D",
        "fallback": rank > 0,
    }


def dispersion_alert(dispersion, threshold=0.05):
    """分歧指数超阈值 -> 盘口分歧大, 返回告警文本。"""
    if dispersion > threshold:
        return "盘口分歧大(dispersion=%.3f>%.2f), 降级为观察, 不参与best_bet" % (dispersion, threshold)
    return ""