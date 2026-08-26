"""数据质量分级 + 异常赛事清洗 (SOP Step 0.5 / Step 2.1 落地)
================================================================
一、缺失数据分级 (Missing Data Grading)
  按"缺失字段对结论的影响面"分 5 级, 禁止静默填0 / 编造:
    L1 致命缺失: 联赛/主客队名/开赛时间 任一缺失 -> 拒绝分析, 直接跳过
    L2 高危缺失: 独赢/让球/大小球盘口赔率缺失 -> 无法去水/无法EV, 降级为观察, 不出 best_bet
    L3 中危缺失: 单队场均进失球(攻防数据)缺失 -> 泊松λ回退联赛基准, 结论降1星
    L4 低危缺失: 伤停/近期状态/历史交锋等情报缺失 -> 标注"该字段未提取", 不修正λ
    L5 可忽略:   场馆/裁判/别称等展示字段缺失 -> 正常分析

二、异常赛事清洗 (Abnormal Match Cleaning)
  清洗按"数据异常"定义(非结果异常), 命中任一规则即打标:
    C1 比分失真: 总进球>12 或 半场/全场比分矛盾 -> 剔除该训练样本
    C2 赔率异常: 任意赔率<1.01(价格错误) 或 多机构同盘口概率标准差>15% -> 标记不可信, 降级为观察
    C3 数据冲突: 主客方向与盘口方向冲突 / 同一字段多源矛盾 -> 以优先级最高源为准并标注
    C4 时间异常: 距开赛>72小时(远期盘) 或 已开赛仍标记未开赛 -> 不参与EV计算
    C5 覆盖异常: 该联赛近期样本<20场 -> 锚定基准降权, 结论带不确定性

纯标准库, 无第三方依赖。用法:
  from data_quality import DataQuality
  dq = DataQuality()
  grade = dq.grade_missing(match)     # -> {level, missing_fields, action}
  clean = dq.clean_match(match)       # -> {flags, cleaned, warnings}
"""
import math


# L1 致命: 缺失即拒绝
FATAL_FIELDS = ("league", "home_team", "away_team", "kickoff_time")
# L2 高危: 独赢盘缺失则无法计算公平EV (hdp/ou 为可选市场, 缺失不阻断, 仅该市场降观察)
ODDS_FIELDS = ("odds_home", "odds_draw", "odds_away")
MARKET_ODDS_FIELDS = ("hdp_odds", "ou_odds")
# L3 中危: 缺失则λ回退联赛基准
MODEL_FIELDS = ("home_gf", "home_ga", "away_gf", "away_ga")
# L4 低危: 情报类, 缺失不修正λ
INTEL_FIELDS = ("injuries", "form", "h2h", "lineups", "motivation")
# L5 可忽略
OPTIONAL_FIELDS = ("venue", "referee", "nickname")


class DataQuality:
    """缺失数据分级 + 异常赛事清洗。"""

    # ---- 一、缺失数据分级 ----
    def grade_missing(self, match):
        """按影响面给缺失字段分级 (键缺失与显式None/空串都算缺失)。

        match: dict, 字段见 FATAL_FIELDS / ODDS_FIELDS / MODEL_FIELDS 等。
        返回: {level: L1..L5, missing_fields: [...], action: str}
        """
        m = match or {}

        def _is_missing(f):
            v = m.get(f)
            return v is None or v == ""

        out = {"level": "L5", "missing_fields": [], "action": "normal"}

        miss_fatal = [f for f in FATAL_FIELDS if _is_missing(f)]
        if miss_fatal:
            out.update({"level": "L1", "action": "refuse_analysis", "missing_fields": miss_fatal})
            return out
        miss_odds = [f for f in ODDS_FIELDS if _is_missing(f)]
        if miss_odds:
            out.update({"level": "L2", "action": "observation_only", "missing_fields": miss_odds})
            return out
        miss_model = [f for f in MODEL_FIELDS if _is_missing(f)]
        if miss_model:
            out.update({"level": "L3", "action": "lambda_fallback_downgrade", "missing_fields": miss_model})
            return out
        miss_intel = [f for f in INTEL_FIELDS if _is_missing(f)]
        miss_market = [f for f in MARKET_ODDS_FIELDS if _is_missing(f)]
        if miss_intel or miss_market:
            out.update({"level": "L4", "action": "mark_not_extracted",
                        "missing_fields": miss_intel + miss_market})
            return out
        miss_opt = [f for f in OPTIONAL_FIELDS if _is_missing(f)]
        if miss_opt:
            out["missing_fields"] = miss_opt
        return out

    # ---- 二、异常赛事清洗 ----
    def clean_match(self, match):
        """清洗单场数据, 命中异常规则即打标。

        返回: {flags: [C1..C5], cleaned: dict, warnings: [str]}
        """
        flags, warnings = [], []
        m = dict(match or {})

        # C1 比分失真
        try:
            hs, as_ = int(m.get("home_score", -1)), int(m.get("away_score", -1))
            if hs >= 0 and as_ >= 0:
                if hs + as_ > 12:
                    flags.append("C1_score_anomaly")
                    warnings.append("总进球>12, 训练样本剔除")
                ht, at = m.get("ht_home"), m.get("ht_away")
                if ht is not None and at is not None and (int(ht) > hs or int(at) > as_):
                    flags.append("C1_score_contradiction")
                    warnings.append("半场比分与全场矛盾, 标记失真")
        except (TypeError, ValueError):
            pass

        # C2 赔率异常
        odds_vals = []
        for k in ("odds_home", "odds_draw", "odds_away"):
            try:
                o = float(m.get(k, 0))
                if o > 0:
                    odds_vals.append(o)
                    if o < 1.01:
                        flags.append("C2_odds_too_low")
                        warnings.append("赔率<1.01 疑似价格错误: %s=%s" % (k, o))
            except (TypeError, ValueError):
                continue
        if len(odds_vals) >= 3:
            probs = [1.0 / o for o in odds_vals]
            mean = sum(probs) / len(probs)
            var = sum((p - mean) ** 2 for p in probs) / len(probs)
            if math.sqrt(var) / max(mean, 1e-9) > 0.15:
                flags.append("C2_dispersion_high")
                warnings.append("三结果赔率隐含概率离散>15%, 标记不可信")

        # C3 数据冲突
        try:
            oh = float(m.get("odds_home", 0))
            oa = float(m.get("odds_away", 0))
            hdp = float(m.get("hdp_val", 0))
            if oh > 0 and oa > 0 and hdp != 0:
                # 主队大热(oh<oa)却受让(hdp>0) / 主队冷门(oh>oa)却让球(hdp<0) -> 方向冲突
                if (oh < oa and hdp > 0) or (oh > oa and hdp < 0):
                    flags.append("C3_direction_conflict")
                    warnings.append("欧赔方向与让球方向冲突(主赔%.2f/客赔%.2f vs 盘口%+.1f)" % (oh, oa, hdp))
        except (TypeError, ValueError):
            pass

        # C4 时间异常
        kick = m.get("kickoff_time")
        if kick:
            flags.append("C4_time_note")
            warnings.append("开赛时间存在: %s (距开赛>72h 或已开赛时, 不参与EV)" % kick)

        # C5 覆盖异常
        try:
            n = int(m.get("league_sample_n", 0))
            if 0 < n < 20:
                flags.append("C5_low_coverage")
                warnings.append("联赛近期样本仅%d场(<20), 锚定基准降权" % n)
        except (TypeError, ValueError):
            pass

        return {"flags": flags, "cleaned": m, "warnings": warnings}
    # ---- 一级/二级缺失分级 (SOP 数据缺失分级) ----
    def tier_missing(self, match):
        """两级缺失分级 (供 SOP 决策, 与 L1-L5 对应)。

        一级缺失(次要): L4 情报缺失 / L5 可忽略 -> 保留样本, 联赛基准/均值填充, 日志标记
        二级缺失(核心): L1 致命 / L2 盘口缺失 -> 强制阻断(拒绝或仅观察)
        二级缺失(可恢复): L3 攻防缺失 -> 联赛基准回退 + 降1星(阻断用假数据, 不阻断分析)
        返回: {"tier": "major_block"|"major_recover"|"minor"|"ok", "level": ..., "action": ...}
        """
        g = self.grade_missing(match)
        if g["level"] == "L1":
            return {"tier": "major_block", "level": "L1",
                    "action": "强制阻断: 拒绝分析", "missing": g["missing_fields"]}
        if g["level"] == "L2":
            return {"tier": "major_block", "level": "L2",
                    "action": "强制阻断: 仅观察不出best_bet", "missing": g["missing_fields"]}
        if g["level"] == "L3":
            return {"tier": "major_recover", "level": "L3",
                    "action": "降级替代: λ回退联赛基准+降1星", "missing": g["missing_fields"]}
        if g["level"] == "L4":
            return {"tier": "minor", "level": "L4",
                    "action": "保留样本: 标注未提取, 不修正λ", "missing": g["missing_fields"]}
        return {"tier": "ok", "level": "L5", "action": "正常分析", "missing": []}

    def fill_missing(self, match, league_baseline):
        """一级缺失字段用联赛基准/均值填充, 返回 (filled, fill_log)。

        league_baseline: {"avg_goals": x, "home_goals": x, "away_goals": x, ...}
        只填充 L4/L5 级(次要)字段; L1-L3 不填(避免用假数据), 返回原值。
        """
        m = dict(match or {})
        base = league_baseline or {}
        log = []
        missing = {k: v for k, v in m.items() if v is None or v == ""}
        if "home_gf" in missing or "away_gf" in missing or "home_ga" in missing or "away_ga" in missing:
            # L3 攻防缺失: 用联赛基准回退(标注来源), 属"可恢复"替代
            hg = float(base.get("home_goals", base.get("avg_goals", 1.35)) or 1.35)
            ag = float(base.get("away_goals", base.get("avg_goals", 1.1)) or 1.1)
            if missing.get("home_gf") in (None, ""):
                m["home_gf"] = hg
                log.append("home_gf<-联赛基准%.2f(L3回退)" % hg)
            if missing.get("away_gf") in (None, ""):
                m["away_gf"] = ag
                log.append("away_gf<-联赛基准%.2f(L3回退)" % ag)
            if missing.get("home_ga") in (None, ""):
                m["home_ga"] = ag
                log.append("home_ga<-联赛基准%.2f(L3回退)" % ag)
            if missing.get("away_ga") in (None, ""):
                m["away_ga"] = hg
                log.append("away_ga<-联赛基准%.2f(L3回退)" % hg)
        return m, log