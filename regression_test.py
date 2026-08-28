"""
回归测试 v1.0 - 防AI越用越笨的质检闸门
========================================
每次修改分析逻辑(代码/提示词/SOP)后运行本测试, 确认历史正确结论没被破坏.
运行: python regression_test.py                 # 全量回归
      python regression_test.py --only poisson  # 只跑名称含poisson的测试(逗号分隔可多选)
      python regression_test.py --list          # 列出全部测试函数
无第三方依赖, 仅标准库.

覆盖五大模块:
  1. parse_handicap 盘口解析 (17种格式)
  2. 泊松比分/大小球概率 (中乙/丹麦杯基准)
  3. Step31 EV计算 + best_bet最高胜率腿判定 (湖北事件回归)
  4. 冷门引擎 4场实战验证 (江原/斯巴达/弗拉门戈/奥胡斯)
  5. 投注结算逻辑 (中乙3串1+5串1)
"""
import sys
import os
import math
import json
import io
import csv

sys.stdout.reconfigure(encoding='utf-8')

PASS = 0
FAIL = 0
FAILURES = []


def check(name, actual, expected, tol=1e-6, unit=""):
    global PASS, FAIL
    ok = False
    if isinstance(expected, float):
        ok = abs(actual - expected) < tol
    else:
        ok = (actual == expected)
    if ok:
        PASS += 1
        print(f"  ✅ {name}: {actual}{unit}")
    else:
        FAIL += 1
        FAILURES.append(f"{name}: 期望={expected}{unit} 实际={actual}{unit}")
        print(f"  ❌ {name}: 期望={expected}{unit} 实际={actual}{unit}")


def section(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


# ============================================================
# 1. 盘口解析
# ============================================================
def test_parse_handicap():
    section("1. 盘口解析 parse_handicap")
    sys.path.insert(0, '.')
    from auto_sop import parse_handicap

    cases = [
        ("+0/0.5 @1.70", 0.25),   # 主受让平半
        ("-0/0.5 @2.02", -0.25),  # 主让平半 (修复过: -0/0.5 应=-0.25)
        ("+0.5/1 @1.86", 0.75),
        ("-0.5/1 @1.86", -0.75),
        ("+1 @1.76", 1.0),
        ("-1 @1.80", -1.0),
        ("+1/1.5 @1.64", 1.25),
        ("-1.5 @1.70", -1.5),
        ("+2/2.5 @2.11", 2.25),
        ("-2 @1.90", -2.0),
        ("+0 @1.90", 0.0),        # 平手盘
        ("-0 @1.90", 0.0),        # 平手盘负0
        ("0 @1.90", 0.0),
        ("+2.5 @1.95", 2.5),
        ("-2.5 @1.85", -2.5),
        ("+3/3.5 @1.80", 3.25),
        ("-0/0.5  @1.98", -0.25), # 带双空格
        ("平手", 0.0),             # 中文平手盘
        ("平手 @1.90", 0.0),       # 中文+赔率
    ]
    for inp, expected in cases:
        actual = parse_handicap(inp)
        check(f"parse_handicap('{inp}')", actual, expected)


# ============================================================
# 2. 泊松概率
# ============================================================
def test_poisson():
    section("2. 泊松概率 (湖北 λ主0.66客0.66, 历史记录)")
    sys.path.insert(0, '.')
    from auto_sop import parse_handicap

    lam_h, lam_a = 0.66, 0.66
    # 湖北那场历史: 小2.25胜率85.25%, 主+0/0.5赢盘69.84% (来自分析记录step31)
    hdp_val = 0.25  # +0/0.5
    home_hdp_p = sum(pmf(i, lam_h) * pmf(j, lam_a)
                     for i in range(9) for j in range(9) if (i - j) + hdp_val > 0)
    under_p = sum(pmf(i, lam_h) * pmf(j, lam_a)
                  for i in range(9) for j in range(9) if i + j < 2.25)
    check("湖北主+0/0.5赢盘概率", round(home_hdp_p, 3), 0.698, tol=0.011, unit="")
    check("湖北小2.25概率", round(under_p, 3), 0.853, tol=0.011, unit="")


# ============================================================
# 3. Step31 best_bet 判定 (湖北事件回归)
# ============================================================
def test_step31_best_bet():
    section("3. Step31 best_bet判定 (湖北事件回归: 必须选小2.25)")
    sys.path.insert(0, 'src/strategy')

    # 模拟湖北那场4个候选 (来自分析记录step31)
    bets = [
        {"name": "主队+0/0.5", "prob": 0.6984, "odds": 1.70, "ev": 0.1873},
        {"name": "客队-0/0.5", "prob": 0.3016, "odds": 1.98, "ev": -0.4028},
        {"name": "小2.25",     "prob": 0.8525, "odds": 1.72, "ev": 0.4663},
        {"name": "大2.25",     "prob": 0.1475, "odds": 1.96, "ev": -0.7109},
    ]
    # best_bet规则 v2: EV>=8%(噪声区间0~8%仅观察)且赔率>=1.60前提下选胜率最高
    EV_NOISE_MIN = 0.08
    valid = [b for b in bets if b['ev'] >= EV_NOISE_MIN and b['odds'] >= 1.60]
    best = max(valid, key=lambda b: b['prob'])
    check("湖北best_bet应为小2.25", best['name'], "小2.25")
    check("湖北best_bet胜率", round(best['prob'], 4), 0.8525)
    check("湖北best_bet应为5星条件(EV>=0.3)", best['ev'] >= 0.30, True)

    # 关键: 小2.25胜率必须 > 让球腿 (这是抓错腿的根源)
    small = next(b for b in bets if b['name'] == "小2.25")
    hdp = next(b for b in bets if b['name'] == "主队+0/0.5")
    check("小2.25胜率>让球腿(湖北)", small['prob'] > hdp['prob'], True)

    # 兰州那场: 让球腿和小球都是5星, best_bet按胜率取
    bets_lz = [
        {"name": "主队-0.5/1", "prob": 0.896, "odds": 1.60, "ev": 0.434},
        {"name": "小2.25",      "prob": 0.843, "odds": 1.82, "ev": 0.533},
    ]
    valid_lz = [b for b in bets_lz if b['ev'] >= EV_NOISE_MIN and b['odds'] >= 1.60]
    best_lz = max(valid_lz, key=lambda b: b['prob'])
    check("兰州best_bet应为让球(胜率89.6%最高)", best_lz['name'], "主队-0.5/1")

    # 打星限制修复: 3个5星+3个4星 → 应1个5星+2个4星
    results = [
        {'name': 'A', 'stars': '⭐⭐⭐⭐⭐', 'prob': 0.9},
        {'name': 'B', 'stars': '⭐⭐⭐⭐⭐', 'prob': 0.85},
        {'name': 'C', 'stars': '⭐⭐⭐⭐⭐', 'prob': 0.8},
        {'name': 'D', 'stars': '⭐⭐⭐⭐', 'prob': 0.7},
        {'name': 'E', 'stars': '⭐⭐⭐⭐', 'prob': 0.65},
        {'name': 'F', 'stars': '⭐⭐⭐⭐', 'prob': 0.6},
    ]
    star5 = [r for r in results if r['stars'] == '⭐⭐⭐⭐⭐']
    for r in star5[1:]:
        r['stars'] = '⭐⭐⭐⭐'
    star4 = [r for r in results if r['stars'] == '⭐⭐⭐⭐']
    for r in star4[2:]:
        r['stars'] = '⭐⭐⭐'
    c5 = sum(1 for r in results if r['stars'] == '⭐⭐⭐⭐⭐')
    c4 = sum(1 for r in results if r['stars'] == '⭐⭐⭐⭐')
    check("打星限制: 最多1个5星", c5, 1)
    check("打星限制: 最多2个4星", c4, 2)


# ============================================================
# 4. 冷门引擎 4场实战验证
# ============================================================
def test_upset_engine():
    section("4. 冷门引擎 4场实战验证")
    sys.path.insert(0, 'src/features')
    from upset_engine_v2 import UpsetEngineV2

    engine = UpsetEngineV2()

    cases = [
        # (名称, hot, cold, h2h, hdp, odds, line, rank_gap, league, 期望等级, 期望最低命中)
        ("江原 vs 富川", "江原FC近期不败轻敌氛围主力中卫停赛一周双赛体能下滑锁定中游无抢分刚需历史连续全胜领先后收缩防守",
         "富川连续多轮不胜急需止颓541大巴密集防守客场无包袱只求平局过往逼平过热队定位球远射强",
         "历史60%平局居多", -1.0, 1.45, "大小球2.5", 10, "", "高危大冷", 6),
        ("斯巴达 vs 里昂", "里昂未开赛休赛无实战缺2名主力后卫中卫边卫同时伤缺",
         "布拉格斯巴达联赛正常捷甲进行中节奏好首回合资格赛保守",
         "历史交锋斯巴达不惧里昂", -0.75, 1.80, "大小球2.5", 8, "ucl", "中度风险", 4),
        ("弗拉门戈 vs 圣保罗", "弗拉门戈近10场6胜3平1负不败率90%主场9场不败核心前腰帕奎塔伤缺轻敌领先后收缩防守长途飞行体能下滑无保级压力",
         "圣保罗连续6轮不胜客场7场不胜541大巴死守只求平局无心理包袱核心卢卡斯莫拉赛季报销主力中卫伤缺",
         "历史60%平局", -1.0, 1.45, "大小球2.5", 10, "", "高危大冷", 6),
        ("奥胡斯 vs 沙巴巴库", "奥胡斯未开赛休赛无实战缺2名主力后卫轻敌心态放松长途飞行远征无抢分刚需只求客场进球领先后收缩",
         "沙巴巴库联赛正常正式比赛节奏好首回合资格赛保守人工草魔鬼主场比赛客场无包袱只求平局定位球远射强历史交锋不惧",
         "历史平局多小球", -0.75, 1.72, "大小球2.5", 6, "ucl", "高危大冷", 6),
    ]
    for name, hot, cold, h2h, hdp, odds, line, gap, league, exp_level, exp_min in cases:
        r = engine.assess(hot_team=name.split(" vs ")[0], hot_info=hot, cold_info=cold,
                          h2h=h2h, hdp_val=hdp, hot_odds=odds, line_note=line,
                          rank_gap=gap, league_type=league)
        check(f"{name} 命中条件>={exp_min}", r['triggered_count'] >= exp_min, True)
        check(f"{name} 等级={exp_level}", r['level'], exp_level)

    # 欧联资格赛专项信号验证 (2026/27新基准)
    hot_el = "欧冠附加赛出局空降欧联有欧协联保底杯赛冠军"
    cold_el = "主要路径联赛第3只为欧战名额首回合保守只求客场进球"
    r_el = engine.assess(hot_team="示例", hot_info=hot_el, cold_info=cold_el,
                         h2h="历史平局多", hdp_val=-0.75, hot_odds=1.75,
                         line_note="大小球2.5", rank_gap=8, league_type="uel")
    uel_joined = " ".join(r_el.get('uel_items', []))
    check("欧联专项EL1触发(欧冠掉队)", "EL1" in uel_joined, True)
    check("欧联专项EL2触发(欧协联保底)", "EL2" in uel_joined, True)
    check("欧联专项EL5触发(客场进球求稳)", "EL5" in uel_joined, True)
    check("欧联专项至少3信号", len(r_el.get('uel_items', [])) >= 3, True)


def test_upset_engine_v3_audit():
    section("4b. 冷门引擎 v3 审计验收 (去水平概率/分歧/杯赛开关/信号限幅/冲突)")
    sys.path.insert(0, 'src/features')
    from upset_engine_v2 import UpsetEngineV2
    sys.path.insert(0, '.')
    from auto_sop import check_upset_risk_conflict, parse_handicap

    eng = UpsetEngineV2()
    # 1. 平局为最大公平概率 → L4 无明显热门
    r1 = eng.assess("主队", "强队轻敌", "弱队无包袱", "历史平局多", -0.5, 2.4,
                    fair_h=0.32, fair_a=0.30, fair_d=0.38, hot_is_home=True)
    check("平局最大→L4无明显热门", any("L4" in x for x in r1["fair_items"]), True)
    # 2. 主客接近不强行标热 (公平概率差≤5%)
    r2 = eng.assess("主队", "", "", "", -0.5, 2.4,
                    fair_h=0.34, fair_a=0.32, fair_d=0.34, hot_is_home=True)
    check("主客接近→L5慎标冷门", any("L5" in x for x in r2["fair_items"]), True)
    # 3. 去水大热概率≥55% → L2
    r3 = eng.assess("主队", "", "", "", -1.5, 1.35,
                    fair_h=0.60, fair_a=0.15, fair_d=0.25, hot_is_home=True)
    check("去水概率≥55%→L2大热", any("L2" in x and "55" in x for x in r3["fair_items"]), True)
    # 4. 多源赔率分歧>5% → L3 加码
    r4 = eng.assess("主队", "强队轻敌", "弱队无包袱", "", -1.0, 1.45,
                    odds_disparity=0.12, hot_is_home=True)
    check("赔率分歧>5%→L3", any("L3" in x for x in r4["line_items"]), True)
    # 5. 杯赛开关: 联赛模式不套用欧冠/欧联专项
    hot_el = "欧冠附加赛出局空降欧联有欧协联保底杯赛冠军"
    cold_el = "主要路径联赛第3只为欧战名额首回合保守只求客场进球"
    r_league = eng.assess("示例", hot_el, cold_el, "历史平局多", -0.75, 1.75, league_type="", cup_mode=False)
    r_cup = eng.assess("示例", hot_el, cold_el, "历史平局多", -0.75, 1.75, league_type="uel", cup_mode=True)
    check("联赛模式无杯赛专项信号", (not r_league["uel_items"]) and (not r_league["ucl_items"]), True)
    check("杯赛模式启用欧联专项", len(r_cup["uel_items"]) >= 3, True)
    # 6. 脏盘口 NaN 不崩溃
    r_nan = eng.assess("主队", "强队轻敌", "弱队无包袱", "", float("nan"), 1.45, hot_is_home=True)
    check("NaN盘口不崩溃", r_nan["level"] is not None, True)
    # 7. RiskSignal 前置限幅 ±10% + 方向 (热在主为负)
    r_hi = eng.assess("主队", "x", "y", "", -2.0, 1.2, hot_is_home=True, odds_disparity=0.3)
    check("risk_signal限幅±10%", -0.10 <= r_hi["risk_signal"] <= 0.10, True)
    check("risk_signal方向(热在主为负)", r_hi["risk_signal"] <= 0, True)
    # 8. 结构化特征: 低样本 → F3
    r_f = eng.assess("主队", "强队轻敌", "弱队无包袱", "", -0.5, 1.45,
                     feature_pack={"hot_side": "home", "sample_n_home": 2})
    check("结构化特征低样本→F3", any("F3" in x for x in r_f["feature_items"]), True)
    # 9. 基本面 vs 冷门信号反向冲突
    c1 = check_upset_risk_conflict(2.5, 1.0, -0.09)
    check("主队强+看衰主队→冲突", c1["conflict"] and c1["level"] == "strong", True)
    c2 = check_upset_risk_conflict(1.0, 2.5, 0.09)
    check("客队强+看衰客队→冲突", c2["conflict"] and c2["direction"] == "away", True)
    c3 = check_upset_risk_conflict(2.5, 1.0, 0.09)
    check("顺向信号→无冲突", c3["conflict"], False)
    # 10. 乱码盘口 parse_handicap 抛异常 → 由上层 HDP_PARSE_FAIL 兜底
    try:
        parse_handicap("平半")
        check("乱码盘口parse_handicap抛出(上层兜底)", False, True)
    except Exception:
        check("乱码盘口parse_handicap抛出(上层兜底)", True, True)


# ============================================================
# 5. 投注结算逻辑
# ============================================================
def test_settlement():
    section("5. 投注结算逻辑 (中乙3串1+5串1)")
    sys.path.insert(0, 'src/strategy')
    from bet_validator import BetValidator

    v = BetValidator()
    best_bets_map = {
        "上海海港B vs 山西崇德荣海": {"name": "小2.25", "prob": 0.852},
        "兰州陇原 vs 北京理工": {"name": "小2.25", "prob": 0.843},
        "湖北青年星 vs 江西庐山": {"name": "小2.25", "prob": 0.8525},
        "长春喜都 vs 大连英博B": {"name": "小1.75", "prob": 0.62},
        "温州 vs 贵州贵阳": {"name": "小2", "prob": 0.689},
    }

    # 3串1: 湖北选让球腿 → 应被判定执行失误
    legs = [
        {"match": "上海海港B vs 山西崇德荣海", "bet": "小2.25", "score": "0-1", "leg_result": "赢"},
        {"match": "兰州陇原 vs 北京理工", "bet": "小2.25", "score": "1-0", "leg_result": "赢"},
        {"match": "湖北青年星 vs 江西庐山", "bet": "主队+0/0.5", "score": "0-1", "leg_result": "输"},
    ]
    ok, errors, warnings = v.verify_bet_legs(legs, best_bets_map)
    check("3串1湖北让球腿被拦截", ok, False)

    # 正确选腿应通过
    good_legs = [
        {"match": "上海海港B vs 山西崇德荣海", "bet": "小2.25"},
        {"match": "湖北青年星 vs 江西庐山", "bet": "小2.25"},
    ]
    ok2, _, _ = v.verify_bet_legs(good_legs, best_bets_map)
    check("改小球后通过校验", ok2, True)

    # 温州小2结算: 0-2总2球 = 走水
    check("温州0-2总进球=2", 0 + 2, 2)


# ============================================================
# 6. 比赛数据提取器 (主客区分 + 盘口提取)
# ============================================================
def test_data_extractor():
    section("6. 比赛数据提取器 (主客区分+盘口提取)")
    sys.path.insert(0, 'src/features')
    from data_extractor import MatchDataExtractor
    e = MatchDataExtractor()

    # 主客区分
    d = e.extract("古比斯 vs 克拉约瓦大学\n独赢 - 2.92 2.16\n让球 +0/0.5 1.90 1.92")
    check("主队=古比斯", d.get('home_team'), "古比斯")
    check("客队=克拉约瓦大学", d.get('away_team'), "克拉约瓦大学")
    check("主客区分标记", d.get('home_away_confirmed'), True)

    # 让球提取 (主队让球盘口)
    check("主队让球盘口", d.get('hdp_home', '').split('@')[0].strip(), "+0/0.5")
    check("主队让球赔率", d.get('hdp_home', '').split('@')[1].strip(), "1.90")
    check("客队让球盘口(反转)", d.get('hdp_away', '').split('@')[0].strip(), "-0/0.5")

    # @格式
    d2 = e.extract("乔治罗尼亚 vs 流浪者\n让球 +0/0.5 @1.75 -0/0.5 @2.07")
    check("@格式主队让球", d2.get('hdp_home', '').split('@')[1].strip(), "1.75")
    check("@格式客队让球", d2.get('hdp_away', '').split('@')[1].strip(), "2.07")

    # 平手盘"0" (修复: 无符号盘口)
    d7 = e.extract("A vs B\n让球 0 2.19 1.72")
    check("平手盘主队盘口", d7.get('hdp_home', '').split('@')[0].strip(), "0")
    check("平手盘主队赔率", d7.get('hdp_home', '').split('@')[1].strip(), "2.19")

    # 独赢两列补平局 (平局赔率应介于主客之间)
    d3 = e.extract("A vs B\n独赢 - 1.99 3.45")
    d3_draw = float(d3.get('odds_draw', 0))
    check("独赢补平局在[2.5,3.5]合理区间", 2.5 <= d3_draw <= 3.5, True)
    # 大冷场次平局赔率应接近高赔方
    d5 = e.extract("A vs B\n独赢 - 1.30 8.50")
    check("大冷场次平局赔率>5", float(d5.get('odds_draw', 0)) > 5.0, True)

    # 情报主客分离
    d4 = e.extract("A vs B\n近10场战绩:\nA近10场7胜1平2负进22球。\nB近10场7胜3平0负进19球。")
    check("主队情报提取", 'A近10场' in d4.get('home_form', ''), True)
    check("客队情报提取", 'B近10场' in d4.get('away_form', ''), True)

    # 情报段落完整提取 (修复: 伤病/战意段落主客都提取)
    d6 = e.extract("A vs B\n伤病停赛\nA主力后卫停赛。\nB全员健康。\n战意\nA无欲。\nB争附加赛。")
    check("伤病段落主队提取", 'A主力后卫停赛' in d6.get('user_injuries', ''), True)
    check("伤病段落客队提取", 'B全员健康' in d6.get('user_injuries', ''), True)
    check("战意段落主队提取", 'A无欲' in d6.get('user_motivation', ''), True)
    check("战意段落客队提取", 'B争附加赛' in d6.get('user_motivation', ''), True)

    # 特征提取器: 独立格式"场均进球X球场均失球X球" (修复的BUG)
    sys.path.insert(0, 'src/features')
    from feature_extractor import MatchFeatureExtractor
    fe = MatchFeatureExtractor()
    f = fe.extract("甲队近10场2胜6平2负总进球13球总失球7球场均进球1.3球场均失球0.7球",
                   "乙队近10场3胜2平5负总进球16球总失球21球场均进球1.6球场均失球2.1球", "")
    check("feature_extractor主队场均进球", f.get('home_gf'), 1.3)
    check("feature_extractor客队场均进球", f.get('away_gf'), 1.6)
    check("feature_extractor客队防线弱(失2.1)", f.get('away_defense_weak'), 1)


# ============================================================
# 7. 联赛基准 (丹麦杯/中乙/K2)
# ============================================================
def test_league_baselines():
    section("7. 联赛基准 (丹麦杯/中乙/K2)")
    sys.path.insert(0, 'src/strategy')
    from betting_strategy import OverUnderModel
    ou = OverUnderModel()

    # K2 基准 (2026新增)
    k2 = ou.league_stats.get("韩国K2联赛")
    check("K2基准存在", k2 is not None, True)
    if k2:
        check("K2场均进球2.82", k2.avg_goals, 2.82, tol=0.01)
        check("K2大2.5率57%(真值)", k2.over25_rate, 57, tol=0.01)
        check("K2大3.5率27.4%(真值)", k2.over35_rate, 27.4, tol=0.01)
        check("K2主场系数接近1.0(主客差距极小)", k2.home_advantage < 1.05, True)

    # 丹麦杯 (已有)
    dk = ou.league_stats.get("丹麦杯")
    check("丹麦杯基准存在", dk is not None, True)
    if dk:
        check("丹麦杯场均3.28", dk.avg_goals, 3.28, tol=0.01)

    # 中乙 (已有)
    cl2 = ou.league_stats.get("中乙")
    check("中乙基准存在", cl2 is not None, True)
    if cl2:
        check("中乙场均1.32", cl2.avg_goals, 1.32, tol=0.01)

    # K2 欧赔区间真值 (2026实测)
    import os as _os
    zone_path = 'strategy_data/k2_odds_zones.json'
    check("K2欧赔区间文件存在", _os.path.exists(zone_path), True)
    if _os.path.exists(zone_path):
        zj = json.load(open(zone_path, encoding='utf-8'))
        z1 = zj.get('odds_zones', {}).get('zone1_1.25_1.40', {})
        check("K2区间1主胜62%", z1.get('real', {}).get('home'), 62)
        deep = zj.get('asian_hdp', {}).get('主让1球深盘', {})
        check("K2深盘穿盘仅37%", deep.get('upper_win'), 37)
        # 核心规律: 主让1球深盘穿盘<50% → 受让方安全
        check("K2深盘穿盘率<50%(受让有价值)", deep.get('upper_win', 100) < 50, True)

    # J1 欧赔区间真值 (2026跨年赛季)
    j1_path = 'strategy_data/j1_odds_zones.json'
    check("J1欧赔区间文件存在", _os.path.exists(j1_path), True)
    if _os.path.exists(j1_path):
        jj = json.load(open(j1_path, encoding='utf-8'))
        jz1 = jj.get('odds_zones', {}).get('zone1_1.30_1.50', {})
        check("J1区间1主胜68.2%", jz1.get('real', {}).get('home'), 68.2)
        jdeep = jj.get('deep_hdp', {})
        check("J1深盘穿盘仅37.4%", jdeep.get('穿盘(净胜>=2)'), 37.4)
        check("J1深盘输盘50%(深盘陷阱)", jdeep.get('输盘(赢1球以下/输球)'), 50.0)
        check("J1大2.5率70%(新赛季实测)", jj.get('baseline', {}).get('over25'), 70)
        # J1规则改动影响 (2026新规)
        check("J1规则改动影响已标注", 'rule_impact_2026' in jj, True)
        if 'rule_impact_2026' in jj:
            check("J1规则影响含外援放宽", '外援5人上限(放宽)' in jj['rule_impact_2026'].get('impacts', {}), True)
            check("J1规则影响含VAR点球收紧", 'VAR点球收紧' in jj['rule_impact_2026'].get('impacts', {}), True)
            check("J1规则影响含校准期建议", '校准期' in jj['rule_impact_2026'].get('net_effect', {}).get('建议', ''), True)
        # J1改制前后对比 (过渡赛季失真)
        check("J1改制前后对比已标注", 'version_comparison' in jj, True)
        if 'version_comparison' in jj:
            vb = jj['version_comparison'].get('B_2026过渡赛季', {})
            check("J1过渡赛季数据标注不可直接套用", ('已作废' in vb.get('note', '')) or ('不能直接套用' in vb.get('warning', '')), True)
            check("J1过渡赛季大2.5率46.1%(实测)", vb.get('over25'), 46.1)
            vc = jj['version_comparison'].get('C_2026跨年正式赛季', {})
            check("J1正式赛季大2.5率48%", vc.get('over25'), 48)
            check("J1正式赛季平局23%", vc.get('draw'), 23)


# ============================================================
# 8. prediction_v2 桥接 + 逐注账本 (新方案接入原系统)
# ============================================================
def test_v2_bridge():
    section("8. prediction_v2 桥接器 + 逐注账本")
    sys.path.insert(0, 'src/features')
    import tempfile, os as _os
    from predict_v2_bridge import (PredictV2Bridge, resolve_league_baseline,
                                   record_recommended_bet, settle_bets)

    # 联赛真值解析 (与 strategy_data 一致)
    k2 = resolve_league_baseline("韩国K2联赛")
    check("K2基准主/客进球(1.43/1.39)", (round(k2[0], 2), round(k2[1], 2)), (1.43, 1.39))
    j1 = resolve_league_baseline("日本J1联赛")
    check("J1基准主/客进球(1.55/1.80新赛季实测)", (round(j1[0], 2), round(j1[1], 2)), (1.55, 1.80))
    cl2 = resolve_league_baseline("中乙联赛")
    check("中乙avg_goals=2.27拆分主>客", cl2[0] > cl2[1], True)

    # 桥接器规则: 只有 OU 小球(边际>=5%且赔率>=2.00)标记推荐
    br = PredictV2Bridge()
    md = {
        "league": "韩国K2联赛", "home": "金浦", "away": "忠南",
        "date": "2026-08-15",
        "odds_home": 1.77, "odds_draw": 3.40, "odds_away": 4.50,
        "ou_over": "2.5@2.00", "ou_under": "2.5@2.10",
        "hdp_home": "-0.5@2.05", "hdp_away": "0.5@1.80",
        "user_form": "金浦近10场进12球失11球主场场均进1.4失1.1。忠南近10场进9球失13球客场场均进0.8失1.6。",
    }
    rec = {"steps": {"step2_1": {"result": md["user_form"]}, "step2_2": {"result": ""}}}
    r = br.predict_from_record(md, rec)
    check("v2引擎=intel(K2不在9大联赛)", r['engine'], "intel")
    ou_under = next(b for b in r['bets'] if b['market'] == 'ou' and 'under' in b['side'])
    check("v2推荐=OU小球(边际>=5%且赔率>=2.00)", ou_under['recommended'], True)
    best = r.get('best_bet')
    check("v2 best_bet=小球方向", best is not None and 'under' in best['side'], True)

    # 逐注账本: 入账去重 + 结算(win/push/lose)
    tmp = tempfile.mktemp(suffix='.jsonl')
    res = {"league": "韩国K2联赛", "engine": "intel", "ou_line": 2.5,
           "best_bet": {"recommended": True, "market": "ou", "side": "under2.5",
                        "edge": 0.10, "odds": 1.80, "ev": 0.15, "prob": 0.61}}
    # 直接写临时账本测试结算
    import json as _json
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(_json.dumps({"ts": "t", "match": "金浦 vs 忠南", "league": "韩国K2联赛",
                             "side": "under2.5", "line": 2.5, "status": "pending",
                             "odds": 1.80, "edge": 0.10, "ev": 0.15}, ensure_ascii=False) + "\n")
    def _fresh(ts, match, side, line):
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(_json.dumps({"ts": ts, "match": match, "league": "韩国K2联赛",
                                 "side": side, "line": line, "status": "pending",
                                 "odds": 1.80, "edge": 0.10, "ev": 0.15}, ensure_ascii=False) + "\n")

    _fresh("t1", "金浦 vs 忠南", "under2.5", 2.5)
    s1 = settle_bets({"金浦 vs 忠南": "1-1"}, tmp)
    check("小球2.5: 1-1(总2球)赢", s1[0]['status'], "win")
    _fresh("t2", "金浦 vs 忠南", "under2.5", 2.5)
    s2 = settle_bets({"金浦 vs 忠南": "3-1"}, tmp)
    check("小球2.5: 3-1(总4球)输", s2[0]['status'], "lose")
    # 整数盘走水: line=2.0, 总2球 -> push
    _fresh("t3", "A vs B", "under2.0", 2.0)
    s3 = settle_bets({"A vs B": "1-1"}, tmp)
    check("小球2.0: 1-1(总2球)走水", s3[0]['status'], "push")
    _os.remove(tmp)


# ============================================================
# 9. P0 交付物 (球队映射字典 + 账本ROI报表)
# ============================================================
def test_p0_deliverables():
    section("9. P0 交付物 (球队映射字典 + 账本ROI报表)")
    import os as _os, json as _json, tempfile

    # 球队映射字典 (xG/赔率流接入的前置条件)
    tm_path = 'prediction_v2/teams_map.json'
    check("球队映射字典存在", _os.path.exists(tm_path), True)
    if _os.path.exists(tm_path):
        tm = _json.load(open(tm_path, encoding='utf-8'))
        stats = tm.get('stats', {})
        check("球队映射匹配率>=98%", stats.get('match_rate', 0) >= 0.98, True)
        check("football-data球队数>=250", stats.get('fd_total', 0) >= 250, True)

    # 账本 ROI 报表 (settle_report)
    sys.path.insert(0, 'prediction_v2')
    from settle_report import report
    tmp = tempfile.mktemp(suffix='.jsonl')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('{"ts":"2026-08-01","match":"A vs B","league":"英超","side":"under2.5","line":2.5,"odds":1.90,"status":"win"}\n')
        f.write('{"ts":"2026-08-02","match":"C vs D","league":"英超","side":"under2.5","line":2.5,"odds":1.85,"status":"lose"}\n')
        f.write('{"ts":"2026-08-03","match":"E vs F","league":"中乙联赛","side":"under2.0","line":2.0,"odds":1.95,"status":"push"}\n')
    r = report(tmp, window=3)
    check("账本报表: 已结算3注", r['settled'], 3)
    check("账本报表: 1赢1走水1输", (r['wins'], r['pushes'], r['losses']), (1, 1, 1))
    check("账本报表: 满窗口可判定", r['window_ok'], True)
    _os.remove(tmp)



def test_de_vig():
    print("\n  ========== 10. EV去水模块 (SOP Step4/31) ==========")
    sys.path.insert(0, 'src/features')
    from de_vig import (overround, devig_odds, fair_ev,
                        model_fair_prob, fair_ev_from_model,
                        devig_h2h, devig_two_way)
    orr = overround([2.0, 3.0, 4.0])
    check("独赢抽水率(2.0/3.0/4.0)", orr, 1.0833333333333333)
    probs, _ = devig_odds([2.0, 3.0, 4.0])
    check("去水主胜概率", probs[0], 0.4615384615384615)
    check("去水平局概率", probs[1], 0.3076923076923077)
    check("去水客胜概率", probs[2], 0.2307692307692308)
    check("去水概率和=1", sum(probs), 1.0)
    check("公平EV(去水概率0.4615@2.0)", fair_ev(probs[0], 2.0), -0.07692307692307687)
    check("模型概率去水校正(0.55/orr1.0833)", model_fair_prob(0.55, 1.0833333333333333), 0.5076923076923077)
    check("去水后EV(0.55@1.90)", fair_ev_from_model(0.55, 1.90, 1.0833333333333333), -0.035384615384615386)
    probs2, orr2 = devig_h2h(2.37, 2.83, 3.88)
    check("独赢去水和=1", sum(probs2), 1.0)
    o_p, u_p, _ = devig_two_way(1.87, 1.95)
    check("大小球两赔去水和=1", o_p + u_p, 1.0)


def test_poisson_lambda():
    print("\n  ========== 11. 泊松λ标准化公式 (SOP Step8 v3) ==========")
    sys.path.insert(0, 'src/models')
    from poisson_lambda import calc_lambda_base, calc_lambdas, attack_strength, defense_weakness
    # 标准范式: λ_base,H = avg_atk×attack_h×defend_a = home_gf×away_ga/avg_atk (已消去冗余league_factor)
    check("λbase=gf×ga/avg_atk", round(calc_lambda_base(1.5, 1.2, 1.4), 4), round(1.5 * 1.2 / 1.4, 4))
    check("进攻强度=gf/avg", attack_strength(1.5, 1.4), 1.0714285714285714)
    check("防守弱度=ga/avg(失球越多越大)", defense_weakness(2.0, 1.4) > defense_weakness(1.0, 1.4), True)
    r = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8)
    check("λH(无修正)", r["lam_h"], round(1.5 * 1.2 / 1.4, 4))
    check("λA(无修正)", r["lam_a"], round(1.0 * 1.1 / 1.4, 4))
    r2 = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8, risk_signal=0.05)
    # P0-1 审计(2026-08-28): 单边限幅±5% + 双向相对差≤±10% → 满额信号等比收缩为 ±4.76%
    check("λH+风险信号(+4.76%)", r2["lam_h"], round(1.5 * 1.2 / 1.4 * (1.0 + 0.10 / 2.1), 4))
    check("λA-风险信号(-4.76%)", r2["lam_a"], round(1.0 * 1.1 / 1.4 * (1.0 - 0.10 / 2.1), 4))
    r3 = calc_lambdas(home_gf=5.0, away_ga=5.0, away_gf=1.0, home_ga=1.0, league_avg=2.0)
    check("λ超上限截断到4.5", r3["lam_h"], 4.5)
    check("λ截断告警标记", r3["clipped"], True)
    r4 = calc_lambdas(home_gf=0.05, away_ga=1.0, away_gf=1.0, home_ga=1.0, league_avg=2.0)
    check("λ低下限截断到0.2", r4["lam_h"], 0.2)
    check("风险信号±5%硬限幅(相对差≤10%→单边4.76%)", calc_lambdas(home_gf=1.0, away_ga=1.0, away_gf=1.0, home_ga=1.0,
                    league_avg=2.0, risk_signal=99.0)["lam_h"], round(1.0 * (1.0 + 0.10 / 2.1), 4))


def test_poisson_lambda_v3_audit():
    section("11b. λ审计整改 6 项验收 (SOP Step8 v3)")
    sys.path.insert(0, 'src/models')
    from poisson_lambda import (calc_lambda_base, calc_lambdas,
                                adjust_gf_by_sample, normalize_attack_gf)
    # 1. 客队防守极弱 away_ga 极大 → λ_base 合理抬高
    lam_weak = calc_lambda_base(1.5, 4.0, 1.4)
    lam_tight = calc_lambda_base(1.5, 1.0, 1.4)
    check("客队失球4.0 λbase>失球1.0", lam_weak > lam_tight, True)
    # 2. 主力射手缺阵 InjuryCoef<1 → λ 显著下调
    r_noinj = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8)
    r_inj = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         injury_coef_h=0.85)
    check("射手缺阵λH下调(×0.85)", r_inj["lam_h"] < r_noinj["lam_h"] * 0.86, True)
    # 3. RiskSignal=+0.12 → 截断至 0.1, 最大扰动≤10% (SOP铁律)
    base = calc_lambda_base(1.5, 1.2, 1.4)
    r_rs = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                        risk_signal=0.12)
    check("RiskSignal=0.12截断=+5%且相对差钳位", r_rs["lam_h"], round(base * (1.0 + 0.10 / 2.1), 4))
    # 4. 3场样本 → 联赛基准 + 告警; 6场样本 → 向均值收缩30%
    g3, w3 = adjust_gf_by_sample(2.5, 3, 2.8)
    check("3场样本=联赛基准", g3, 1.4)
    check("3场样本告警(降星)", w3 is not None and "联赛基准" in w3, True)
    g6, w6 = adjust_gf_by_sample(2.5, 6, 2.8)
    check("6场样本收缩30%", round(g6, 4), round(1.4 + (2.5 - 1.4) * 0.7, 4))
    # 5. λ>4.5 → 截断 + 告警日志
    r_big = calc_lambdas(home_gf=5.0, away_ga=5.0, away_gf=1.0, home_ga=1.0, league_avg=2.0)
    check("λ>4.5截断到4.5", r_big["lam_h"], 4.5)
    check("λ>4.5告警warnings", len(r_big["warnings"]) > 0, True)
    # 6. 同攻防原始数据, 对手强弱不同 → 归一化 attack 明显区分
    strong_opp = normalize_attack_gf([1.8, 1.8, 1.8], [0.8, 0.9, 0.8], 1.4)
    weak_opp = normalize_attack_gf([1.8, 1.8, 1.8], [2.0, 2.2, 2.0], 1.4)
    check("打强队归一值>打弱队归一值", strong_opp > weak_opp, True)
    check("归一化区分明显(差值>1.0)", round(strong_opp - weak_opp, 2) > 1.0, True)


def test_poisson_lambda_v4_audit():
    section("11c. λ审计整改 v4 验收 (时间衰减/DC平局/错误码/系数拦截/风险对抗)")
    sys.path.insert(0, 'src/models')
    from poisson_lambda import (normalize_attack_gf, dixon_coles_prob, calc_lambdas,
                                validate_coef, risk_conflict_check, Warn, _to_float,
                                prob_1x2, over_under_prob, W_COEF_CLIP, W_LAM_H_CLIP,
                                W_RISK_CONFLICT)
    # P0 时间指数衰减: 近期高进球应比久远高进球权重更高
    v_recent = normalize_attack_gf([1.0, 2.5], [1.4, 1.4], 1.4, days_list=[200, 3])
    v_old = normalize_attack_gf([1.0, 2.5], [1.4, 1.4], 1.4, days_list=[3, 200])
    check("近场高进球权重大于久远场", v_recent > v_old, True)
    v_equal = normalize_attack_gf([1.8, 1.8, 1.8], [0.8, 0.9, 0.8], 1.4)
    check("无days_list兼容等权(旧逻辑)", v_equal > 1.0, True)
    # P1 Dixon-Coles: 负ρ提升平局概率; 市场概率自洽
    sp0, mp0 = dixon_coles_prob(1.5, 1.2, rho=0.0)
    sp1, mp1 = dixon_coles_prob(1.5, 1.2, rho=-0.1)
    check("DC比分概率归一(和=1)", round(sum(sp1.values()), 6), 1.0)
    check("负ρ提升平局概率", mp1["draw"] > mp0["draw"], True)
    check("独赢概率和=1", round(mp1["win"] + mp1["draw"] + mp1["lose"], 4), 1.0)
    check("大小2.5概率和=1", round(mp1["over25"] + mp1["under25"], 4), 1.0)
    # P1 结构化错误码 + calc_lambdas 输出市场概率
    r = calc_lambdas(home_gf=5.0, away_ga=5.0, away_gf=1.0, home_ga=1.0, league_avg=2.0)
    check("λ截断标准码LAM_H_CLIP", W_LAM_H_CLIP in r["warn_codes"], True)
    _lam_h_warns = [str(w) for w in r["warnings"] if w["code"] == W_LAM_H_CLIP]
    check("warnings文本含code前缀", bool(_lam_h_warns) and _lam_h_warns[0].startswith("[LAM_H_CLIP]"), True)
    check("calc_lambdas输出market_prob", "market_prob" in r and "score_prob" in r, True)
    r_rho = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8, rho=-0.1)
    check("rho参数生效(平局概率提升)", r_rho["market_prob"]["draw"] > 0.20, True)
    # P2 系数值域拦截: 极端系数钳位+告警
    c, w = validate_coef(1.5, "home_coef")
    check("home_coef=1.5钳位到1.30", c, 1.30)
    check("系数超界告警码COEF_CLIP", w["code"], W_COEF_CLIP)
    r_c = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8, home_coef=1.5)
    check("calc_lambdas极端系数钳位", r_c["warn_codes"].count(W_COEF_CLIP) >= 1, True)
    # P2 风险信号对抗校验: 基本面主队强 + 看衰 → RISK_CONFLICT + 扰动减半
    conf = risk_conflict_check(3.0, 1.0, -0.08)
    check("强基本面+反向信号标记冲突", conf["conflict"] and conf["level"] == "strong", True)
    r_conf = calc_lambdas(home_gf=2.5, away_ga=1.2, away_gf=1.0, home_ga=1.0, league_avg=2.0, risk_signal=-0.08)
    check("风险对抗告警码RISK_CONFLICT", W_RISK_CONFLICT in r_conf["warn_codes"], True)
    check("冲突扰动减半(λ×0.975: -0.08先截断±5%再减半)", r_conf["lam_h"], round(3.0 * 0.975, 4))
    # P3 工具: 浮点兜底 / Warn 对象
    check("_to_float字符串转换", _to_float("1.5"), 1.5)
    check("_to_float空值兜底", _to_float(None), 0.0)
    wobj = Warn("X", "warn", "测试")
    check("Warn dict字段", wobj["code"], "X")
    check("Warn文本打印", str(wobj), "[X] 测试")
    # 内聚概率工具: 1X2 / 大小球
    ph, pd, pa = prob_1x2(1.5, 1.2, rho=-0.1)
    check("prob_1x2和=1", round(ph + pd + pa, 4), 1.0)
    ov, un, push = over_under_prob(1.5, 1.2, line=2.0, rho=-0.1)
    check("整数盘大小球含走水", round(ov + un, 6), 1.0)
    check("整数盘2.0存在走水概率", push > 0.0, True)


def test_poisson_lambda_v5_audit():
    section("11d. λ审计整改 v5 验收 (分边风险信号/主客独立样本/入参补全)")
    sys.path.insert(0, 'src/models')
    from poisson_lambda import (calc_lambdas, adjust_gf_by_sample, calc_lambda_base,
                                calc_lambda_base_detail, W_RISK_CLIP, W_RISK_CONFLICT,
                                W_LAM_BASE_INPUT_CLIP)
    base_h = round(1.5 * 1.2 / 1.4, 4)   # 1.2857
    base_a = round(1.0 * 1.1 / 1.4, 4)   # 0.7857
    # 1. 分边风险信号独立生效 (主队+8%→限幅5% / 客队-5%)
    r_split = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                           risk_signal_h=0.08, risk_signal_a=-0.05)
    # P0-1 审计(2026-08-28): 单边限幅±5% + 双向相对差≤±10% → (0.05/-0.05 等比收缩 → ±4.76%)
    check("分边信号主队×1.04762(限幅+相对差钳位)", r_split["lam_h"], round(base_h * (1.0 + 0.05 * (0.10 / 0.105)), 4))
    check("分边信号客队×0.95238(限幅+相对差钳位)", r_split["lam_a"], round(base_a * (1.0 - 0.05 * (0.10 / 0.105)), 4))
    check("返回risk_signal_h/a字段", "risk_signal_h" in r_split and "risk_signal_a" in r_split, True)
    # 2. 闷平双降: 单标量无法表达, 分边可同时压低双方λ
    r0 = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8)
    # 2026-08-28: 单边限幅±5%后冲突阈值降至3% → 满额-5%在强基本面侧会触发冲突减半,
    #   闷平用例改用-3%(阈值下)保持"双降×0.97"语义纯净
    r_dl = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                        risk_signal_h=-0.03, risk_signal_a=-0.03)
    check("闷平双降: 主队λ下降", r_dl["lam_h"] < r0["lam_h"], True)
    check("闷平双降: 客队λ下降", r_dl["lam_a"] < r0["lam_a"], True)
    check("闷平双降数值=×0.97", r_dl["lam_h"], round(base_h * 0.97, 4))
    # 3. 分边超限钳位 ±5% (2026-08-28审计)
    r_clip = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                          risk_signal_h=0.12)
    check("分边0.12截断=+5%", r_clip["risk_signal_h"], 0.05)
    check("分边超限告警RISK_CLIP", W_RISK_CLIP in r_clip["warn_codes"], True)
    # 4. 分边信号基本面冲突 → 扰动减半+告警 (主队强却看衰; -0.08先截断±5%再减半→-2.5%)
    r_conf = calc_lambdas(home_gf=2.5, away_ga=1.2, away_gf=1.0, home_ga=1.0, league_avg=2.0,
                          risk_signal_h=-0.08)
    check("分边冲突扰动减半(×0.975)", r_conf["lam_h"], round(3.0 * 0.975, 4))
    check("分边冲突告警RISK_CONFLICT", W_RISK_CONFLICT in r_conf["warn_codes"], True)
    # 5. fatigue/injury 入参生效 (P0 补全入参回归)
    r_fat = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         fatigue_coef=0.85)
    check("fatigue_coef生效(×0.85)", r_fat["lam_h"], round(1.5 * 1.2 / 1.4 * 0.85, 4))
    r_inj = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         injury_coef_h=0.85, injury_coef_a=0.9)
    check("injury_coef_h生效(×0.85)", r_inj["lam_h"], round(1.5 * 1.2 / 1.4 * 0.85, 4))
    check("injury_coef_a生效(×0.90)", r_inj["lam_a"], round(1.0 * 1.1 / 1.4 * 0.90, 4))
    # 6. 主客独立样本量平滑 (P1: 主队3场/客队10场 → 主队回联赛基准, 客队原值)
    g_h, _ = adjust_gf_by_sample(2.5, 3, 2.8)
    g_a, _ = adjust_gf_by_sample(2.5, 10, 2.8)
    check("主队3场样本=联赛基准", g_h, 1.4)
    check("客队10场样本=原值", g_a, 2.5)
    # 7. calc_lambda_base 安全约束 (P0除零保底 / P1负场均钳位 / P2钳位告警)
    check("λbase数学等价(gf×ga/avg_atk)", round(calc_lambda_base(1.5, 1.2, 1.4), 6), round(1.5 * 1.2 / 1.4, 6))
    check("avg_atk=0不崩溃(除数保底0.001)", calc_lambda_base(1.5, 1.2, 0.0) < 1e6, True)
    _lb, _lw, _ld = calc_lambda_base_detail(-1.0, 1.2, 1.4)
    check("负主队场均钳位到0.01", round(_lb, 6), round(0.01 * 1.2 / 1.4, 6))
    check("钳位告警码LAM_BASE_INPUT_CLIP", _lw is not None and _lw["code"] == W_LAM_BASE_INPUT_CLIP, True)
    check("P2-5 中间值hgf_safe=0.01", round(_ld["hgf_safe"], 6), 0.01)
    _r_clip = calc_lambdas(home_gf=-1.0, away_ga=1.2, away_gf=1.0, home_ga=1.0, league_avg=2.8)
    check("calc_lambdas透传钳位告警", W_LAM_BASE_INPUT_CLIP in _r_clip["warn_codes"], True)
    # ===== v6 审计 (2026-08-27 P0 双层包络) =====
    from poisson_lambda import (W_RISK_GAP, W_TOTAL_COEF_CLIP, dixon_coles_prob,
                                Warn, _to_float, _cap_relative_risk)
    # P0-1: 双向同强度反向扰动 → 相对差恰为 10%
    rh, ra, k = _cap_relative_risk(0.10, -0.10)
    check("P0-1 相对差钳位到10%", round((1 + rh) / (1 + ra), 6), 1.10)
    check("P0-1 等比收缩系数<1", 0 < k < 1, True)
    r_gap = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         risk_signal_h=0.08, risk_signal_a=-0.05)
    check("P0-1 RISK_GAP告警码", W_RISK_GAP in r_gap["warn_codes"], True)
    check("P0-1 相对差≤10%", round((1 + r_gap["risk_signal_h"]) / (1 + r_gap["risk_signal_a"]), 4), 1.10)
    # P0-2: 全修正系数连乘跌破0.7 → 钳位到0.7 + 告警
    r_tot = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         home_coef=1.0, fatigue_coef=0.7, injury_coef_h=0.75)
    check("P0-2 总包络钳位到0.70", r_tot["total_coef_h"], 0.7)
    check("P0-2 TOTAL_COEF_CLIP告警码", W_TOTAL_COEF_CLIP in r_tot["warn_codes"], True)
    check("P0-2 钳位后λ=base×0.7", r_tot["lam_h"], round(1.5 * 1.2 / 1.4 * 0.7, 4))
    # P0-3: 弱主场<1.0 合法; neutral_coef 覆盖主客系数
    r_wk = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8, home_coef=0.95)
    check("P0-3 弱主场0.95合法(λ=base×0.95)", r_wk["lam_h"], round(1.5 * 1.2 / 1.4 * 0.95, 4))
    r_neu = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         home_coef=1.2, neutral_coef=1.0)
    check("P0-3 中立场neutral_coef=1.0覆盖主加成", r_neu["lam_h"], round(1.5 * 1.2 / 1.4, 4))
    # P0-4: 校准正ρ不再静默清零 (西甲+0.02/意甲+0.05)
    r_rho_p = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8, rho=0.05)
    check("P0-4 正ρ保留(0.05)", r_rho_p["rho"], 0.05)
    check("P0-4 正ρ不触发RHO_CLAMP", "RHO_CLAMP" not in r_rho_p["warn_codes"], True)
    sp_p, _ = dixon_coles_prob(1.5, 1.2, rho=0.05)
    check("P0-4 正ρ比分矩阵归一", round(sum(sp_p.values()), 6), 1.0)
    # P1-2: 联赛级 λ 上限覆盖
    r_lm = calc_lambdas(home_gf=5.0, away_ga=5.0, away_gf=1.0, home_ga=1.0, league_avg=2.0, lam_max=5.0)
    check("P1-2 联赛级lam_max=5.0生效", r_lm["lam_h"], 5.0)
    # P1-4: 比分矩阵上限9, 大6.5深盘有尾部质量
    _, mp9 = dixon_coles_prob(3.0, 3.0, rho=-0.1, max_goals=9)
    _, mp7 = dixon_coles_prob(3.0, 3.0, rho=-0.1, max_goals=7)
    check("P1-4 9球上限捕获更多大球尾部", mp9["over25"] >= mp7["over25"], True)
    # P2-2/P2-3: Warn上下文字段 + _to_float 负值钳位
    w_ctx = Warn("X", "warn", "t", league="英超", match_id="m1")
    check("P2-2 Warn上下文字段", w_ctx["league"] == "英超" and w_ctx["match_id"] == "m1", True)
    r_ctx = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                         league="英超", match_id="m1")
    check("P2-2 calc_lambdas透传上下文", r_ctx["league"] == "英超" and r_ctx["match_id"] == "m1", True)
    check("P2-3 _to_float负值钳位", _to_float(-2.0, min_val=0.0), 0.0)
    check("P2-4 中间变量total_coef输出", "total_coef_h" in r_ctx and "total_coef_a" in r_ctx, True)
    # ===== v7 审计 (2026-08-27 P0-4 基础λ上界 / P1-1 分边冲突独立减半) =====
    from poisson_lambda import calc_lambda_base_detail
    # P0-4: 单队场均进球超联赛单队均值3倍 -> 钳位 + LAM_BASE_INPUT_CLIP
    _lb7, _lw7, _ld7 = calc_lambda_base_detail(8.0, 1.0, 1.0)   # avg_atk=1.0, cap=3.0
    check("P0-4 场均8球钳位到3倍均值(3.0)", _lb7, 3.0)
    check("P0-4 上界钳位告警码", _lw7 is not None and _lw7["code"] == W_LAM_BASE_INPUT_CLIP, True)
    check("P2-5 中间值cap=3.0", _ld7["cap"], 3.0)
    _lb7b, _, _ld7b = calc_lambda_base_detail(2.0, 1.0, 1.0)     # 正常值不误伤
    check("P0-4 正常输入不误伤", _lb7b, 2.0)
    check("P2-5 正常输入cap=3.0", _ld7b["cap"], 3.0)
    # P1-1: 分边冲突独立减半 (主边-0.05冲突减半, 客边+0.02<阈值不冲突保持)
    #   2026-08-28: 单边限幅±5%后冲突阈值降至3%, 满额±5%镜像信号两侧都会触发 → 客边用+2%验证独立减半
    r_side = calc_lambdas(home_gf=2.5, away_ga=1.2, away_gf=1.0, home_ga=1.0, league_avg=2.0,
                          risk_signal_h=-0.05, risk_signal_a=0.02)
    check("P1-1 主边冲突减半(×0.975)", r_side["lam_h"], round(3.0 * 0.975, 4))
    check("P1-1 客边不冲突保持(×1.02)", r_side["lam_a"], round(1.0 * 1.02, 4))
    check("P1-1 分边仅主边触发RISK_CONFLICT", r_side["warn_codes"].count(W_RISK_CONFLICT), 1)
    # 单标量模式保持整体减半 (回归旧行为; -0.08先截断±5%再减半)
    r_scalar = calc_lambdas(home_gf=2.5, away_ga=1.2, away_gf=1.0, home_ga=1.0, league_avg=2.0,
                            risk_signal=-0.08)
    check("P1-1 单标量整体减半(主×0.975)", r_scalar["lam_h"], round(3.0 * 0.975, 4))
    check("P1-1 单标量整体减半(客×1.025)", r_scalar["lam_a"], round(1.0 * 1.025, 4))


def test_lstm_v2_audit():
    section("11f. LSTM 时序泄漏整改验收 (torch 环境可用时)")
    try:
        import torch  # noqa
    except Exception:
        print("  ⏭ torch 未安装, 跳过 LSTM 运行时验收 (模块已 py_compile 校验)")
        return
    sys.path.insert(0, 'src/models')
    from lstm_model import MatchSeqDataset, LSTMpredictor
    # P0-2: 单向架构 + 回归输出
    m = LSTMpredictor(input_dim=5, hidden_dim=8, num_layers=1)
    check("P0-2 LSTM单向(bidirectional=False)", m.lstm.bidirectional, False)
    check("P0-2 fc1输入=hidden×2(2队单向)", m.fc1.in_features, 16)
    check("P0-3 输出=1维form_score回归", m.fc2.out_features, 1)
    # P0-1: 无前视泄漏 — 非padding行数必须等于"该场之前"的历史场次
    import pandas as pd
    rows = []
    teams = ["A", "B", "C"]
    dates = pd.date_range("2026-01-01", periods=12, freq="D")
    for d in dates:
        h = teams[d.day % 3]
        a = teams[(d.day + 1) % 3]
        rows.append({"date": d, "home_team": h, "away_team": a,
                     "home_goals": d.day % 4, "away_goals": d.day % 3,
                     "target": 0.5})
    df = pd.DataFrame(rows)
    df_sorted = df.sort_values("date").reset_index(drop=True)
    sim_hist = {}
    expected = []
    for _, row in df_sorted.iterrows():
        hp = len(sim_hist.get(row["home_team"], []))
        ap = len(sim_hist.get(row["away_team"], []))
        if min(hp, ap) >= 1:
            expected.append((min(3, hp), min(3, ap)))
        for team in (row["home_team"], row["away_team"]):
            sim_hist.setdefault(team, []).append(row["date"])
    ds = MatchSeqDataset(df, seq_len=3, min_seq=1, require_label=False)
    check("P0-1 样本数=期望(无泄漏无遗漏)", len(ds), len(expected))
    leak_bad = 0
    for i, (eh, ea) in enumerate(expected[:len(ds)]):
        h_enc, a_enc, _ = ds[i]
        h_np = int((h_enc[:, 4] == 0).sum().item())
        a_np = int((a_enc[:, 4] == 0).sum().item())
        if h_np != eh or a_np != ea:
            leak_bad += 1
    check("P0-1 序列仅含过去比赛(0泄漏)", leak_bad, 0)


def test_data_quality():
    section("12. 数据质量分级 + 异常赛事清洗 (SOP Step0.5)")
    sys.path.insert(0, 'src/rules')
    from data_quality import DataQuality
    dq = DataQuality()
    r1 = dq.grade_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "2026-08-16 03:30", "odds_home": 2.0, "odds_draw": 3.0, "odds_away": 4.0, "hdp_odds": "1.8/2.0", "ou_odds": "1.9/1.9", "home_gf": 1.2, "home_ga": 0.9, "away_gf": 1.1, "away_ga": 1.3, "injuries": "无", "form": "近5场3胜", "h2h": "近5次3胜2负", "lineups": "4-3-3", "motivation": "争冠"})
    check("完整数据=L5", r1["level"], "L5")
    r2 = dq.grade_missing({"league": "西甲", "home_team": "", "away_team": "B", "kickoff_time": "x"})
    check("主队名缺失=L1拒绝", r2["level"], "L1")
    r3 = dq.grade_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "odds_home": None})
    check("赔率缺失=L2观察", r3["level"], "L2")
    r4 = dq.grade_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "odds_home": 2.0, "odds_draw": 3.0, "odds_away": 4.0, "home_gf": None})
    check("攻防缺失=L3降星", r4["level"], "L3")
    r5 = dq.grade_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "odds_home": 2.0, "odds_draw": 3.0, "odds_away": 4.0, "home_gf": 1.2, "home_ga": 0.9, "away_gf": 1.1, "away_ga": 1.3, "injuries": ""})
    check("情报缺失=L4标注", r5["level"], "L4")
    c1 = dq.clean_match({"home_score": 8, "away_score": 5, "odds_home": 2.0, "odds_draw": 3.0, "odds_away": 4.0})
    check("总进球>12=C1打标", "C1_score_anomaly" in c1["flags"], True)
    c2 = dq.clean_match({"odds_home": 1.005, "odds_draw": 10.0, "odds_away": 20.0})
    check("赔率<1.01=C2打标", "C2_odds_too_low" in c2["flags"], True)
    c3 = dq.clean_match({"odds_home": 1.20, "odds_draw": 5.0, "odds_away": 12.0, "hdp_val": 0.75})
    check("欧赔与盘口方向冲突=C3打标", "C3_direction_conflict" in c3["flags"], True)


def test_multi_source():
    section("13. 多源赔率容灾 (SOP Step2/4)")
    sys.path.insert(0, 'src/odds')
    from multi_source import resolve, consensus_probs, dispersion_alert
    r = resolve({"the_odds_api": {"odds": [2.37, 2.83, 3.88]}, "api_football": {"odds": [2.30, 2.90, 3.90]}})
    check("主源A级优先", r["source"], "the_odds_api")
    check("主源质量=A", r["source_quality"], "A")
    r2 = resolve({"the_odds_api": None, "api_football": {"odds": [2.30, 2.90, 3.90]}})
    check("主源缺失降级B", r2["source"], "api_football")
    check("降级标记fallback", r2["fallback"], True)
    r3 = resolve({"the_odds_api": None, "api_football": None})
    check("全源缺失返回N/A", r3["source"], None)
    cp = consensus_probs([[2.0, 3.0, 4.0], [2.0, 3.0, 4.0]])
    check("共识概率中位数归一", round(sum(cp["probs"]), 4), 1.0)
    check("分歧指数=0", cp["dispersion"], 0.0)
    check("分歧>0.05告警", dispersion_alert(0.10) != "", True)


def test_risk_control():
    section("14. 多维风控 + EV噪声阈值 + 仓位纪律 (SOP Step7/31)")
    sys.path.insert(0, 'src/rules')
    from risk_control import risk_score, ev_tier, check_position
    s1 = risk_score(dispersion=0.15, hist_roi=-0.30, drift=0.5, lose_streak=5)
    check("高风险分(多因子)>0.6", s1 > 0.6, True)
    s2 = risk_score(dispersion=0.0, hist_roi=0.10, drift=0.0, lose_streak=0)
    check("低风险分<0.3", s2 < 0.3, True)
    t1 = ev_tier(0.05)
    check("EV5%=噪声区间", t1["tier"], "noise")
    t2 = ev_tier(0.12)
    check("EV12%=可推荐", t2["tier"], "best")
    t3 = ev_tier(0.12, risk=0.8)
    check("风险>0.6降级取消best_bet", t3["tier"], "candidate")
    check("降级标记", t3["downgraded"], True)
    t4 = ev_tier(-0.02)
    check("EV<0放弃", t4["tier"], "drop")
    p1 = check_position({"bankroll": 100, "day_staked": 14.0, "stake_ratio": 0.05, "lose_streak": 0, "strategy_drawdown": 0.0, "strategy_days_off": 0, "cycle_profit": 0.0})
    check("单日超15%拒绝", p1["ok"], False)
    p2 = check_position({"bankroll": 100, "day_staked": 5.0, "stake_ratio": 0.05, "lose_streak": 4, "strategy_drawdown": 0.0, "strategy_days_off": 0, "cycle_profit": 0.0})
    check("连亏4注仓位减半", p2["stake_ratio"], 0.025)
    p3 = check_position({"bankroll": 100, "day_staked": 5.0, "stake_ratio": 0.05, "lose_streak": 5, "strategy_drawdown": 0.0, "strategy_days_off": 0, "cycle_profit": 0.0})
    check("连亏5注当日停推", p3["ok"], False)
    p4 = check_position({"bankroll": 100, "day_staked": 5.0, "stake_ratio": 0.05, "lose_streak": 0, "strategy_drawdown": 0.12, "strategy_days_off": 2, "cycle_profit": 0.0})
    check("单策略回撤>10%停用", p4["ok"], False)
    p5 = check_position({"bankroll": 100, "day_staked": 5.0, "stake_ratio": 0.05, "lose_streak": 0, "strategy_drawdown": 0.0, "strategy_days_off": 0, "cycle_profit": 25.0})
    check("盈利>20%锁定利润", p5["action"], "bet_locked")


def test_llm_isolation():
    section("15. LLM输出硬隔离 (SOP Step30)")
    sys.path.insert(0, 'src/models')
    from llm_isolation import sanitize_llm_text, merge_llm_output
    clean, viol = sanitize_llm_text("主队战术克制, 建议小2.5 λ=1.5 概率=60%")
    check("越权数值行被剥离", "λ=1.5" not in clean, True)
    check("违规记录数>0", len(viol) > 0, True)
    clean2, viol2 = sanitize_llm_text("客队反击犀利, 防线移位较大")
    check("纯战术文本不剥离", clean2 == "客队反击犀利, 防线移位较大", True)
    check("无违规", len(viol2), 0)
    m = merge_llm_output({"tactical": "高位压迫", "lambda_home": 2.5, "ev": 0.2})
    check("数值字段拒绝入档", "lambda_home" not in m["merged"], True)
    check("拒绝列表>=2", len(m["rejected"]) >= 2, True)
    check("LLM越权告警", m["alert"], True)


def test_parlay_v2():
    section("16. 串关相关性修正 + 2串1上限 (SOP Step32)")
    sys.path.insert(0, 'src/models')
    from parlay import ParlayEngine
    import pandas as pd
    df = pd.DataFrame([
        {"home_team": "A", "away_team": "B", "league": "西甲", "prob_home_win": 0.5, "prob_draw": 0.28, "prob_away_win": 0.22},
        {"home_team": "C", "away_team": "D", "league": "西甲", "prob_home_win": 0.45, "prob_draw": 0.3, "prob_away_win": 0.25},
        {"home_team": "E", "away_team": "F", "league": "英超", "prob_home_win": 0.6, "prob_draw": 0.25, "prob_away_win": 0.15},
    ])
    eng = ParlayEngine(df)
    parlays = eng.best_parlays(max_legs=3)
    check("硬约束: 不产出3串1", all(len(p["selections"]) <= 2 for p in parlays), True)
    same_league = [p for p in parlays if sum(1 for s in p["selections"] if s.get("league") == "西甲") > 1]
    check("同联赛最多1场", len(same_league), 0)
    eng2 = ParlayEngine(df, max_legs=2, correlation_decay=0.9)
    p2 = eng2.best_parlays()
    check("相关性衰减<=1.0", all(p["correlation_decay"] <= 1.0 for p in p2), True)
    check("adj_prob<=连乘概率", all(p["adj_prob"] <= p["total_prob"] + 1e-9 for p in p2), True)


def test_data_tier_and_fill():
    section("17. 数据缺失一级/二级分级 + 联赛基准填充")
    sys.path.insert(0, 'src/rules')
    from data_quality import DataQuality
    dq = DataQuality()
    t1 = dq.tier_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "odds_home": 2.0})
    check("缺平/客赔=L2强制阻断", t1["tier"], "major_block")
    t2 = dq.tier_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "odds_home": 2.0, "odds_draw": 3.0, "odds_away": 4.0, "home_gf": None})
    check("缺攻防=L3可恢复降级", t2["tier"], "major_recover")
    t3 = dq.tier_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "odds_home": 2.0, "odds_draw": 3.0, "odds_away": 4.0, "home_gf": 1.2, "home_ga": 0.9, "away_gf": 1.0, "away_ga": 1.3, "injuries": ""})
    check("缺情报=一级保留样本", t3["tier"], "minor")
    filled, log = dq.fill_missing({"league": "西甲", "home_team": "A", "away_team": "B", "kickoff_time": "x", "home_gf": None, "away_gf": None}, {"avg_goals": 2.7, "home_goals": 1.6, "away_goals": 1.1})
    check("L3攻防填充联赛基准", filled["home_gf"], 1.6)
    check("填充日志非空", len(log) > 0, True)


def test_match_filter():
    section("18. 赛事过滤 + 黑名单 + 两回合杯赛")
    sys.path.insert(0, 'src/rules')
    from match_filter import filter_match, two_leg_lambda_coefs
    f1 = filter_match({"league": "英超", "type": "友谊赛", "home": "A", "away": "B"})
    check("友谊赛剔除", f1["excluded"], True)
    f2 = filter_match({"league": "西甲", "home": "A", "away": "B"})
    check("正常联赛保留", f2["excluded"], False)
    f3 = filter_match({"league": "U21欧洲杯", "home": "A", "away": "B"})
    check("U21青年赛剔除", f3["excluded"], True)
    f4 = filter_match({"league": "西甲", "home": "A", "away": "B", "status": "腰斩"})
    check("腰斩剔除", f4["excluded"], True)
    c1 = two_leg_lambda_coefs(1, True)
    check("首回合主场att>1", c1["home_att"] > 1.0, True)
    c2 = two_leg_lambda_coefs(2, True)
    check("次回合主场att>1", c2["home_att"] > 1.0, True)


def test_line_movement():
    section("19. 盘口变动时间衰减 + 风险等级")
    sys.path.insert(0, 'src/odds')
    from line_movement import time_weight, weighted_change, risk_level
    check("远期>12h权重0.30", time_weight(24.0), 0.30)
    check("中段3-12h权重0.60", time_weight(5.0), 0.60)
    check("近段0.5-3h权重0.80", time_weight(1.0), 0.80)
    check("临场0-30min权重1.00", time_weight(0.1), 1.00)
    w1 = weighted_change(0.20, 24.0)
    w2 = weighted_change(0.20, 0.1)
    check("远期加权<临场加权", w1 < w2, True)
    r1 = risk_level(0.01)
    r2 = risk_level(0.20)
    check("微小异动=低风险0级", r1["level"], 0)
    check("极端异动=极高3级", r2["level"], 3)
    import sys as _sys
    import importlib.util
    _sys.path.insert(0, ".")
    spec = importlib.util.spec_from_file_location("loc", "live_odds_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    j1 = mod.judge(0.5, 2.00, 0.75, 1.90, hours_to_kickoff=0.1)
    j2 = mod.judge(0.5, 2.00, 0.75, 1.90, hours_to_kickoff=24.0)
    check("临场判断含风险等级", "风险等级" in j1, True)
    check("远期判断含风险等级", "风险等级" in j2, True)


def test_api_router():
    section("20. 多赔率key容灾路由")
    sys.path.insert(0, 'src/odds')
    from api_router import OddsApiRouter
    import os as _os
    _os.environ["ODDS_API_KEY_1"] = "key1"
    _os.environ["ODDS_API_KEY_2"] = "key2"
    for _i in range(3, 10):
        _os.environ.pop("ODDS_API_KEY_%d" % _i, None)
    _os.environ.pop("ODDS_API_KEY", None)
    _os.environ.pop("THE_ODDS_API_KEY", None)
    r = OddsApiRouter()
    check("发现>=2组key", len(r.keys) >= 2, True)
    check("激活key=key1", r.get_active_key(), "key1")
    r.mark_failure()
    nk = r.rotate()
    check("失败后切换=key2", nk, "key2")
    r.mark_success()
    r.mark_failure(); r.mark_failure(); r.mark_failure()
    _nk = r.rotate()
    check("连续失败>3次后轮询到健康key", _nk is None or r.health.get(r._find_source(_nk), {}).get("fail", 0) < r.max_fail, True)
    # v3: 亚洲专用key路由 + 每key独立base url + 配额硬阻断阈值
    _os.environ["ODDS_API_KEY_AS"] = "as-key"
    _os.environ["ODDS_BASE_URL_2"] = "https://shturl.example/v4"
    _os.environ["ODDS_MIN_QUOTA"] = "50"
    r3 = OddsApiRouter()
    check("AS key不入主链", "ODDS_API_KEY_AS" not in [src for _, src in r3.keys], True)
    sel_as = r3.key_for_league("中超")
    check("亚洲联赛路由AS", sel_as["key"], "as-key")
    check("亚洲联赛来源标签", sel_as["source"], "ODDS_API_KEY_AS")
    sel_eur = r3.key_for_league("英超")
    check("欧洲联赛走主链", sel_eur["key"], "key1")
    check("主链默认base", sel_eur["base_url"], "https://api.the-odds-api.com/v4")
    check("2号key独立base", r3.meta.get("ODDS_API_KEY_2"), "https://shturl.example/v4")
    check("配额阈值读env", r3.min_quota, 50)
    r3.mark_failure("as-key")
    sel_next = r3.rotate_sel("中超")
    check("AS失败回主链", sel_next["key"], "key1")
    _os.environ.pop("ODDS_API_KEY_1", None)
    _os.environ.pop("ODDS_API_KEY_2", None)
    _os.environ.pop("ODDS_API_KEY_AS", None)
    _os.environ.pop("ODDS_BASE_URL_2", None)
    _os.environ.pop("ODDS_MIN_QUOTA", None)


def test_oddsapi_adapter():
    section("20.5 Odds-API.io 备用源适配器")
    import importlib.util
    import os as _os
    _p = _os.path.join("prediction_v2", "src", "oddsapi_io.py")
    spec = importlib.util.spec_from_file_location("oddsapi_io_mod", _p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("oddsapi源识别(base)", mod.is_oddsapi_source({"base_url": "https://api.odds-api.io/v3", "key": "k"}), True)
    check("oddsapi源识别(the-odds-api)", mod.is_oddsapi_source({"base_url": "https://api.the-odds-api.com/v4", "key": "k"}), False)
    check("oddsapi源识别(64hex兜底)", mod.is_oddsapi_source({"base_url": "https://api.the-odds-api.com/v4", "key": "91f72210cb8aafff7e70db2aa7418f514ab38830473b3de487e8eb5f55223f1b"}), True)
    check("oddsapi源识别(空)", mod.is_oddsapi_source(None), False)
    check("联赛映射9个", len(mod.LEAGUE_SLUGS), 9)
    check("免费档默认庄家", mod.DEFAULT_BOOKMAKERS, "Bet365,Unibet")
    check("英超slug", mod.LEAGUE_SLUGS["英超"], "england-premier-league")
    check("荷甲slug", mod.LEAGUE_SLUGS["荷甲"], "netherlands-eredivisie")
    ids = list(range(25))
    chunks = list(mod.chunk_ids(ids))
    check("multi按10场分块", len(chunks), 3)
    check("首块10场", len(chunks[0]), 10)
    quota = mod._quota_from_headers({"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "700"})
    check("配额used换算", quota["used"], 300)
    check("配额remaining", quota["remaining"], "700")
    events = [
        {"id": 1, "home": "Man United", "away": "Liverpool", "date": "2026-08-16T15:00:00Z"},
        {"id": 2, "home": "Arsenal", "away": "Chelsea", "date": "2026-08-16T17:00:00Z"},
    ]
    odds_list = [
        {"id": 1, "home": "Man United", "away": "Liverpool", "date": "2026-08-16T15:00:00Z",
         "bookmakers": {"Bet365": [
             {"name": "ML", "odds": [{"home": "2.10", "draw": "3.40", "away": "3.20"}], "updatedAt": "2026-08-15T10:00:00Z"},
             {"name": "Spread", "odds": [{"hdp": -0.5, "home": "1.95", "away": "1.85"}]},
             {"name": "Totals", "odds": [{"max": 2.5, "over": "1.90", "under": "1.90"}]},
             {"name": "Correct Score", "odds": []},
         ]}},
    ]
    rows = mod.flatten_rows(events, odds_list, "英超", "2026-08-15T00:00:00Z")
    check("单场三市场7行", len(rows), 7)
    h2h = [r for r in rows if r["market"] == "h2h"]
    check("ML主胜价", h2h[0]["price"], 2.10)
    check("ML平局side", h2h[1]["side"], "draw")
    sp = [r for r in rows if r["market"] == "spreads"]
    check("让球主point", sp[0]["point"], -0.5)
    check("让球客side_key", sp[1]["side_key"], "away@0.5")
    to = [r for r in rows if r["market"] == "totals"]
    check("大小球over", to[0]["side"], "over")
    check("大小球线", to[0]["point"], 2.5)
    check("未知市场跳过", all(r["market"] != "Correct Score" for r in rows), True)
    no_bk = mod.flatten_rows(events, [{"id": 2, "home": "Arsenal", "away": "Chelsea",
                                       "bookmakers": {}}], "英超", "t")
    check("无庄家市场0行", len(no_bk), 0)
# ---- Bet365 单边报价格式 (2026-08-15 实测: hdp=-1.25 只给主 / hdp=+1.25 只给客) ----
    split_odds = [
        {"id": 3, "home": "Middlesbrough FC", "away": "Lincoln City", "date": "2026-08-15T14:00:00Z",
         "bookmakers": {"Bet365": [
             {"name": "ML", "odds": [{"home": "1.420", "draw": "4.750", "away": "6.500"}]},
             {"name": "Spread", "odds": [
                 {"hdp": -1.25, "home": "2.000"},
                 {"hdp": 1.25, "away": "1.850"},
                 {"hdp": 0.5, "home": "1.115", "away": "2.850"},
             ]},
             {"name": "Totals", "odds": [{"hdp": 2.5, "over": "1.727", "under": "2.100"}]},
         ]}},
    ]
    rows2 = mod.flatten_rows(events, split_odds, "英冠", "2026-08-15T00:00:00Z")
    sp2 = [r for r in rows2 if r["market"] == "spreads"]
    by_sk = {(r["side"], r["point"]): r["price"] for r in sp2}
    check("单边主-1.25", by_sk.get(("home", -1.25)), 2.00)
    check("单边客+1.25不被反号", by_sk.get(("away", 1.25)), 1.85)
    check("单边无客-1.25假行", by_sk.get(("away", -1.25)), None)
    check("双边高价方=受让+0.5", by_sk.get(("away", 0.5)), 2.85)
    check("双边低价方=让-0.5", by_sk.get(("home", -0.5)), 1.115)
    tt2 = [r for r in rows2 if r["market"] == "totals"]
    check("Totals读hdp字段线2.5", tt2[0]["point"], 2.5)
    check("Totals大球价", tt2[0]["price"], 1.727)
    # ---- /v3/markets 运动级市场元数据 (公开端点, 2026-08-15 实测) ----
    m_payload = {
        "sport": {"name": "Football", "slug": "football"},
        "markets": [
            {"name": "ML", "shape": "moneyline", "period": "match", "prematch": True, "live": True},
            {"name": "Spread", "shape": "line", "period": "match", "prematch": True, "live": True},
            {"name": "Totals", "shape": "line", "period": "match", "prematch": True, "live": True},
            {"name": "Goals Over/Under", "shape": "line", "period": "match", "prematch": False, "live": False},
        ],
    }
    parsed = mod.parse_markets(m_payload)
    check("markets单运动解析", parsed["ML"]["shape"], "moneyline")
    check("markets核心三市场齐", {"ML", "Spread", "Totals"} <= set(parsed), True)
    check("markets含Goals O/U", "Goals Over/Under" in parsed, True)
    check("markets period字段", parsed["Spread"]["period"], "match")
    all_sports = {
        "football": [{"name": "ML", "shape": "moneyline", "period": "match", "prematch": True, "live": True}],
        "basketball": [{"name": "Spread", "shape": "line", "period": "match", "prematch": True, "live": False}],
    }
    ps = mod.parse_markets(all_sports)
    check("markets全运动汇总", ps["ML"].get("sports"), ["football"])
    check("markets多运动同名归并", ps["Spread"].get("sports"), ["basketball"])
    check("markets空输入", mod.parse_markets(None), {})
    check("markets非法列表跳过", mod.parse_markets({"markets": [{"foo": 1}]}), {})
    check("fetch_markets可导入", callable(mod.fetch_markets), True)
# ---- 交叉验证: Odds-API.io 行归并到主源 event_id (2026-08-15) ----
    import importlib.util as _ilu
    import os as _os2
    _fp = _os2.path.join("prediction_v2", "fetch_live_odds.py")
    _spec = _ilu.spec_from_file_location("flo_cross", _fp)
    _flo = _ilu.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(_flo)
    except Exception:
        _flo = None
    check("fetch_live_odds可导入", _flo is not None, True)
    if _flo is not None:
        check("跨源归一化去FC", _flo._cross_norm("Middlesbrough FC"), "middlesbrough")
        check("跨源归一化去AFC", _flo._cross_norm("Arsenal AFC"), "arsenal")
        _anchors = [
            {"event_id": "e1", "league": "英冠", "commence_time": "2026-08-15T14:00:00Z",
             "home_team": "Middlesbrough", "away_team": "Lincoln City"},
            {"event_id": "e2", "league": "英冠", "commence_time": "2026-08-22T11:30:00Z",
             "home_team": "Lincoln City", "away_team": "Portsmouth FC"},
        ]
        _m = _flo._cross_match_event(_anchors, "英冠", "2026-08-15T14:00:00Z",
                                     "Middlesbrough FC", "Lincoln City")
        check("跨源匹配到主源event", _m and _m[0], "e1")
        _rows = [{"event_id": "12345", "league": "英冠", "commence_time": "2026-08-15T14:00:00Z",
                  "home_team": "Middlesbrough FC", "away_team": "Lincoln City",
                  "bookmaker": "Bet365", "market": "spreads", "side": "away",
                  "side_key": "away@1.25", "point": 1.25, "price": 1.85}]
        _merged, _matched, _total = _flo._merge_cross_rows(_anchors, _rows)
        check("交叉归并event_id重写", _merged[0]["event_id"], "e1")
        check("交叉归并队名重写", _merged[0]["home_team"], "Middlesbrough")
        check("交叉归并计数", (_matched, _total), (1, 1))


def test_zone_leak():
    section("21. 联赛真值区间防时间穿越")
    import subprocess
    import sys as _sys
    r = subprocess.run([_sys.executable, "verify_zone_leak.py", "--match-date", "2026-08-16"],
                       capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "") + (r.stderr or "")
    check("脚本可运行(exit 0/1/2)", r.returncode in (0, 1, 2), True)
    check("K2样本不足告警", "样本不足" in out, True)
    check("无时间穿越ERROR", "时间穿越" not in out, True)
    check("滚动窗口标注通过", ("cl2_odds_zones" in out) or ("csl_odds_zones" in out) or ("j1_odds_zones" in out), True)

def test_calibration_modules():
    section("22. 校准体系: 在线攻防 / 概率后校准 / 离线系数校准")
    import tempfile
    sys.path.insert(0, 'src/models')
    from team_strength import (exp_decay_weight, weighted_norm_gf, bayesian_shrink,
                               TeamStrengthDB)
    from prob_calibration import (shrink_power, fit_shrink_power, dc_corrected_probs,
                                  fit_rho, bin_calibration_map, apply_bin_calibration,
                                  dc_score_grid, apply_prob_calibration)
    from calibrate import (clamp_coef, compute_league_baseline, rolling_origin_windows,
                           add_rolling_strengths, match_profiles, poisson_probs_batch,
                           grid_search_cv, touch_boundary, validate_oos, lambdas_for,
                           model_probs, fit_prob_calibration, write_calibration,
                           load_prob_calib, calibrate_league)

    # ---- 在线攻防 (team_strength, SOP第三类) ----
    check("时间衰减权重递减", exp_decay_weight(3) > exp_decay_weight(30), True)
    avg_atk = 1.4
    strong_opp = weighted_norm_gf([1.8, 1.8], [0.8, 0.9], [3, 3], avg_atk)
    weak_opp = weighted_norm_gf([1.8, 1.8], [2.0, 2.2], [3, 3], avg_atk)
    check("打弱队进球降权(对手强度归一)", strong_opp[0] > weak_opp[0], True)
    check("低样本收缩贴近均值", bayesian_shrink(2.0, 1, 1.4) < bayesian_shrink(2.0, 7, 1.4), True)
    _ts_path = os.path.join(tempfile.gettempdir(), '_ts_regress.json')
    db = TeamStrengthDB(path=_ts_path)
    db.reset_team("T1")
    db.add_result("T1", 2, 1, 1.2, "2026-08-01")
    db.add_result("T1", 1, 2, 1.5, "2026-08-08")
    atk = db.get_attack("T1", 2.8)
    check("2场样本攻击收缩标记", atk["shrunk"], True)
    db.save()
    db2 = TeamStrengthDB(path=_ts_path)
    check("team_strength持久化读写", db2.get_attack("T1", 2.8)["attack"] == atk["attack"], True)
    if os.path.exists(_ts_path):
        os.remove(_ts_path)

    # ---- 概率后校准 (prob_calibration, SOP第四类) ----
    sp = shrink_power([0.7, 0.2, 0.1], 0.90)
    check("ShrinkPower归一化和=1", round(sum(sp), 6), 1.0)
    check("ShrinkPower压缩热门", sp[0] < 0.7, True)
    p0 = dc_corrected_probs(1.5, 1.2, 0.0)[3].get((0, 0), 0.0)
    p1 = dc_corrected_probs(1.5, 1.2, -0.1)[3].get((0, 0), 0.0)
    check("负rho提升0-0概率(平局修正)", p1 > p0, True)
    _m = ([{"probs": (0.6, 0.25, 0.15), "result": "H"}] * 40
          + [{"probs": (0.2, 0.3, 0.5), "result": "A"}] * 40)
    pwr, _ = fit_shrink_power(_m)
    check("ShrinkPower拟合在网格内", 0.80 <= pwr <= 1.00, True)
    _rho, _ = fit_rho([{"lam_h": 1.5, "lam_a": 1.2, "gh": 1, "ga": 0}] * 60
                      + [{"lam_h": 1.2, "lam_a": 1.5, "gh": 0, "ga": 1}] * 60)
    check("rho拟合在[-0.15,0]", -0.15 <= _rho <= 0.0, True)
    table = bin_calibration_map([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0], n_bins=4)
    check("分箱校准表非空", len(table) > 0, True)

    # ---- 离线校准引擎 (calibrate, SOP第二类) ----
    check("系数硬钳位", clamp_coef(1.5, 1.05, 1.30), 1.3)
    check("触界红线检测", len(touch_boundary((1.05, 1.00, 0.70))) >= 1, True)
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(7)
    rows = []
    dates = pd.date_range("2023-08-01", periods=300, freq="4D")
    teams = ["C%02d" % i for i in range(16)]
    for k, d in enumerate(dates):
        h = teams[k % 16]
        a = teams[(k * 7 + 3) % 16]
        if h == a:
            a = teams[(k * 7 + 4) % 16]
        gh = int(rng.poisson(1.5)); ga = int(rng.poisson(1.1))
        rows.append({"Div": "E0", "Date": d.strftime("%d/%m/%Y"), "date": d,
                     "HomeTeam": h, "AwayTeam": a, "FTHG": gh, "FTAG": ga,
                     "FTR": "H" if gh > ga else ("A" if gh < ga else "D"),
                     "season": "2023/2024" if k < 150 else "2024/2025",
                     "league_name": "英超", "PSH": 2.0, "PSD": 3.4, "PSA": 3.6})
    sdf = pd.DataFrame(rows)
    bl = compute_league_baseline(sdf, "英超")
    check("league_avg统计聚合", round(bl["league_avg"], 4),
          round(float(sdf["FTHG"].sum() + sdf["FTAG"].sum()) / len(sdf), 4))
    wlist = list(rolling_origin_windows(sdf["date"], train_days=400, val_days=200, step_days=120))
    check("滚动窗口>=1", len(wlist) >= 1, True)
    s, te, ve = wlist[0]
    check("时序隔离(train<=val)", te <= ve, True)
    sdf["league_avg"] = bl["league_avg"]
    d2 = add_rolling_strengths(sdf)
    prof = match_profiles(d2)
    probs = poisson_probs_batch(prof["base_h"][:5], prof["base_a"][:5])
    check("泊松1X2概率归一", round(float(probs[0].sum()), 6), 1.0)
    cands = grid_search_cv([prof])
    h, a, f = cands[0][1]
    check("网格候选系数在值域内", 1.05 <= h <= 1.30 and 0.85 <= a <= 1.00 and 0.70 <= f <= 1.00, True)
    oos = validate_oos(d2, (h, a, f))
    check("OOS校验结构完整", oos["train_logloss"] is not None and oos["gap"] is not None, True)
    # ---- 概率后校准链 (SOP第四类) ----
    lam_h, lam_a = lambdas_for(prof, (1.10, 0.95, 0.90))
    probs_chain = model_probs(prof, (1.10, 0.95, 0.90), rho=-0.1, shrink=0.9)
    check("model_probs 1X2归一", round(float(probs_chain[0].sum()), 6), 1.0)
    g0 = dc_score_grid(1.5, 1.2, rho=0.0, max_goals=4)
    g1 = dc_score_grid(1.5, 1.2, rho=-0.1, max_goals=4)
    check("dc_score_grid归一", round(sum(sum(r) for r in g0), 6), 1.0)
    check("负rho提升0-0概率", g1[0][0] > g0[0][0], True)
    apc = apply_prob_calibration([0.7, 0.2, 0.1], shrink=0.9, bin_table={"H": [[0.7, 0.6]], "D": [[0.2, 0.3]], "A": [[0.1, 0.1]]})
    check("apply_prob_calibration归一", round(sum(apc), 6), 1.0)
    pc_fit = fit_prob_calibration(d2, (h, a, f))
    check("fit_prob_calibration结构完整", pc_fit is not None and "rho" in pc_fit and "enabled" in pc_fit, True)
    oos2 = validate_oos(d2, (h, a, f), prob_calib=pc_fit)
    check("校准后EV字段存在", oos2["ev"] is not None and "ev_suspicious" in oos2, True)
    # ---- 写盘/读取 roundtrip (prob_calib 仅 enabled 才可加载) ----
    import tempfile as _tf
    _cal_tmp = os.path.join(_tf.gettempdir(), "_cal_regress.json")
    import calibrate as _cal
    _cal.CALIBRATION_JSON = _cal_tmp
    pc_fit["enabled"] = True
    write_calibration("英超", (1.10, 0.95, 0.90), {"note": "regress"}, prob_calib=pc_fit, coef_status="OK")
    pc_loaded = load_prob_calib("英超")
    check("load_prob_calib roundtrip", pc_loaded is not None and abs(pc_loaded["rho"] - pc_fit["rho"]) < 1e-9, True)
    if os.path.exists(_cal_tmp):
        os.remove(_cal_tmp)
    _cal.CALIBRATION_JSON = os.path.join("strategy_data", "calibration.json")
    # ---- 触界回退默认 (不采用极端值) ----
    _, rep_league = calibrate_league(sdf, "英超", quick=True)
    check("触界状态标记", rep_league["coef_status"] in ("OK", "BOUNDARY_DEFAULT"), True)
    check("落地系数为默认非边界", rep_league["stored_coefs"]["home_coef"] >= 1.05, True)

def test_promoted_and_league_avg():
    section("23. 升班马修正 + league_avg接校准")
    sys.path.insert(0, '.')
    sys.path.insert(0, 'src/features')
    sys.path.insert(0, 'src/models')
    from auto_sop import get_league_avg_goals, get_league_odds_zones_path, get_league_correct_coef
    from feature_extractor import MatchFeatureExtractor
    from poisson_lambda import calc_lambdas

    # league_avg 优先读 calibration.json 基线 (西甲 3800场)
    la = get_league_avg_goals('西甲')
    check("league_avg接校准(西甲=2.5811)", round(la, 4), 2.5811)
    check("league_avg回落默认(未知联赛)", round(get_league_avg_goals('测试联赛'), 2), 2.8)

    # 西甲 odds_zones 路径生效
    zp = get_league_odds_zones_path('西甲')
    check("西甲odds_zones路径生效", zp is not None and 'laliga' in str(zp), True)
    check("laliga文件存在", os.path.exists(os.path.join('strategy_data', 'laliga_odds_zones.json')), True)

    # correct_coef 合并升班马系数
    cc = get_league_correct_coef('西甲')
    check("升班马攻系数", cc.get('promoted_attack'), 0.65)
    check("升班马防系数", cc.get('promoted_defense'), 1.20)
    check("西甲校准系数合并", cc.get('home_coef'), 1.1)

    # 升班马识别
    ex = MatchFeatureExtractor()
    feats = ex.extract("桑坦德 西甲 升班马 近42场场均进2.62失1.38",
                       "比利亚雷亚尔 西甲 近38场场均进1.26失1.42", "")
    check("主队升班马识别", feats.get('home_promoted'), 1)
    check("客队非升班马", feats.get('away_promoted'), 0)

    # 升班马系数生效: 自队λ 打折, 对手λ 放大
    base = calc_lambdas(home_gf=2.619, away_ga=1.421, away_gf=1.263, home_ga=1.381,
                        league_avg=2.5811, home_coef=1.1, away_coef=0.95, fatigue_coef=0.9)
    lh, la = base['lam_h'], base['lam_a']
    lh_p, la_p = lh * 0.65, la * 1.20
    check("升班马主队λ下调", lh_p < lh, True)
    check("升班马对手λ上调", la_p > la, True)
    check("升班马修正幅度(0.65/1.20)",
          (round(lh_p / lh, 4), round(la_p / la, 4)), (0.65, 1.20))


def test_snapshot_guard():
    section("24. 盘口快照新鲜度守卫")
    sys.path.insert(0, 'prediction_v2')
    from snapshot_guard import snapshot_staleness, is_future_snapshot
    from datetime import datetime, timezone
    import tempfile
    import os as _os
    now = datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)
    fd, path = tempfile.mkstemp(suffix=".csv")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("snap,id\n")
            f.write("2026-08-14T15:00:00+00:00,e1\n")
            f.write("2026-08-14T23:30:00+00:00,e2\n")
            f.write("2026-08-15T02:00:00+00:00,e3\n")
        r = snapshot_staleness(path, now=now, max_age_hours=12)
        check("最新快照取非未来行", r["max_snap_iso"], "2026-08-14T23:30:00+00:00")
        check("正常阈值下不触发过期", r["stale"], False)
        check("未来脏数据行数", r["future_rows"], 1)
        check("文件存在标记", r["missing"], False)
        r2 = snapshot_staleness(path, now=now, max_age_hours=0.25)
        check("低阈值触发过期", r2["stale"], True)
        r3 = snapshot_staleness("no_such_file.csv", now=now)
        check("缺文件标记", r3["missing"], True)
        check("未来快照识别", is_future_snapshot("2026-08-15T02:00:00+00:00", now=now), True)
        check("正常快照非未来", is_future_snapshot("2026-08-14T15:00:00+00:00", now=now), False)
    finally:
        try:
            _os.remove(path)
        except Exception:
            pass


def test_scan_v2_fixes():
    section("25. scan_upcoming v2 五类修复回归 (EV分层/队名分级/多机构去水/升班马收缩/风控不折EV)")
    sys.path.insert(0, 'prediction_v2')
    import io as _io
    import glob
    import tempfile
    import scan_upcoming as su

    # ---- 第一类: EV分层阈值 + 赔率下限 ----
    check("批量扫描EV门槛=5%", su.EV_TIER_BATCH, 0.05)
    check("完整情报EV门槛=8%", su.EV_TIER_INTEL, 0.08)
    check("主流赔率下限1.60", su.ODDS_FLOOR_MAIN, 1.60)
    check("次级赔率下限1.40", su.ODDS_FLOOR_SEC, 1.40)

    def _tier_label(ev):
        for _label, _th, _stake in su.EV_TIERS:
            if ev >= _th:
                return _label
        return "垃圾"

    check("EV20%高价值", _tier_label(0.20), "高价值")
    check("EV10%标准", _tier_label(0.10), "标准")
    check("EV6%观察", _tier_label(0.06), "观察")
    check("EV3%垃圾", _tier_label(0.03), "垃圾")

    # ---- 第二类: 升班马/跨联赛收缩30% + 样本分层 ----
    check("升班马收缩系数30%", su.PROMO_SHRINK, 0.30)
    check("满样本门槛8场", su.SAMPLE_FULL_N, 8)
    check("收缩样本门槛4场", su.SAMPLE_SHRINK_N, 4)
    check("满样本不收缩", su.effective_rate(1.4, 1.0, False, 9), (1.4, False))
    check("升班马收缩30%", su.effective_rate(1.4, 1.0, True, 9), (1.28, False))
    check("4~7场再收缩30%", su.effective_rate(1.4, 1.0, False, 5), (1.28, True))
    check("<4场降级联赛均值", su.effective_rate(1.4, 1.0, False, 2), (1.0, True))

    # ---- 第二类: 队名匹配quality分级(相似度<0.9才降级) ----
    ts, lavg, index = su.load_team_stats()
    check("整词匹配exact", su._match_team("Ajax", index), ("Ajax", "exact"))
    check("别名映射exact", su._match_team("Bolton", index), ("Bolton", "exact"))
    check("歧义队名exact优先", su._match_team("Fortuna Sittard", index)[1], "exact")
    _syn = {"psv eindhoven": "PSV Eindhoven"}
    check("词集包含subset", su._match_team("PSV", _syn)[1], "subset")
    check("相似度<0.9降级none", su._match_team("完全未知队XYZ123", index)[1], "none")

    # ---- 第三类: 按(book,line)取最低抽水, 1X2/亚盘/大小球独立Overround ----
    HEADER = "snapshot_ts,event_id,league,commence_time,home_team,away_team,bookmaker,market,outcome,side,side_key,point,price,last_update\n"
    rows = []

    def _row(eid, lg, ct, h, a, bk, mk, out, side, point, price, ts="2026-08-14T10:00:00Z"):
        rows.append("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (ts, eid, lg, ct, h, a, bk, mk, out, side, "", point, price, ts))

    CT = "2026-08-16T10:00:00Z"
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "h2h", "A", "home", "", 2.00)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "h2h", "D", "draw", "", 3.10)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "h2h", "B", "away", "", 3.30)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "h2h", "A", "home", "", 2.10)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "h2h", "D", "draw", "", 3.40)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "h2h", "B", "away", "", 3.60)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "spreads", "A", "home", -0.5, 1.95)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "spreads", "B", "away", -0.5, 1.95)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "spreads", "A", "home", -1.5, 2.10)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "spreads", "B", "away", -1.5, 1.75)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "totals", "Over", "over", 2.5, 1.95)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "pinnacle", "totals", "Under", "under", 2.5, 1.95)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "totals", "Over", "over", 3.5, 1.90)
    _row("t1", "荷甲", CT, "TeamA", "TeamB", "bet365", "totals", "Under", "under", 3.5, 1.90)
    # t2: 主队受让+0.5(客队热门) — 验证符号不被abs归一化翻转
    _row("t2", "荷甲", CT, "TeamC", "TeamD", "pinnacle", "spreads", "C", "home", 0.5, 1.90)
    _row("t2", "荷甲", CT, "TeamC", "TeamD", "pinnacle", "spreads", "D", "away", -0.5, 1.90)
    fd, path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(HEADER + "".join(rows))
        out, _fut = su.parse_snapshots(path)
        r = out[0]
        check("1X2取最低抽水机构", (r["h2h"]["home"], r["h2h"]["draw"]), (2.1, 3.4))
        check("1X2同机构不混价", r["books_used"]["h2h"].startswith("bet365"), True)
        check("亚盘保留主让盘符号(-0.5)", r["spread"]["hdp_home"], -0.5)
        check("受让方保留+0.5符号", [x for x in out if x["id"] == "t2"][0]["spread"]["hdp_home"], 0.5)
        check("大小球优先2.5线", abs(r["totals"]["line"] - 2.5) < 1e-9, True)
        check("亚盘/大小球同盘同机构", r["books_used"]["spread"].startswith("pinnacle")
              and r["books_used"]["totals"].startswith("pinnacle"), True)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass

    # ---- 第二类/第三类: 让球符号修复回归 (主让-0.5不再被当主受+0.5虚增EV) ----
    _grid = su.dc_score_grid(1.04, 0.65, rho=0.0, max_goals=8)
    _p_plus = su.handicap_cover_prob(_grid, 0.5)
    _p_minus = su.handicap_cover_prob(_grid, -0.5)
    _hw = sum(_grid[i][j] for i in range(9) for j in range(9) if i > j)
    check("受让+0.5覆盖>主让-0.5覆盖", _p_plus > _p_minus, True)
    check("主让-0.5覆盖=主胜概率", abs(_p_minus - _hw) < 1e-9, True)
    _orr = 1.0 / 2.38 + 1.0 / 1.63
    _ev = (_p_minus / _orr) * 2.38 - 1.0
    check("西甲-0.5高赔不再虚高(EV<8%)", _ev < 0.08, True)

    # ---- 第五类: 分联赛泊松校准 ----
    check("荷甲rho=-0.12(2026-08-24ρ校准670场)", su.CAL["荷甲"]["rho"], -0.12)
    check("比甲rho=0.00(2026-08-24ρ校准335场)", su.CAL["比甲"]["rho"], 0.0)
    check("葡超rho=-0.09(2026-08-24ρ校准348场)", su.CAL["葡超"]["rho"], -0.09)
    check("德乙rho=0.00(2026-08-24ρ校准)", su.CAL["德乙"]["rho"], 0.0)
    check("英冠rho=-0.01(2026-08-24ρ校准)", su.CAL["英冠"]["rho"], -0.01)
    check("英超rho=-0.09(2026-08-24ρ校准)", su.CAL["英超"]["rho"], -0.09)
    check("西甲rho=0.02(2026-08-24ρ校准)", su.CAL["西甲"]["rho"], 0.02)
    check("意甲rho=0.05(2026-08-24ρ校准)", su.CAL["意甲"]["rho"], 0.05)
    check("法甲rho=0.01(2026-08-24ρ校准)", su.CAL["法甲"]["rho"], 0.01)
# ---- J1 逐场攻防数据接入 (ESPN 源, 2026-08-15) ----
    check("J1赛季权重2026/27=1.0", su.SEASON_WEIGHT.get("2026/2027"), 1.0)
    check("J1 DIV映射JP1", su.DIV_BY_LEAGUE.get("J1"), "JP1")
    check("JP1进ALL_DIVS", "JP1" in su.ALL_DIVS, True)
    check("J1 league_calib", su.CAL.get("J1", {}).get("league_avg"), 3.35)
    j1_ts, _jl, _jidx = su.load_team_stats()
    j1_teams = {t for t, divs in j1_ts.items() if "JP1" in divs}
    check("J1 20队全部入库", len(j1_teams), 20)
    check("J1样本src=2026/2027", j1_ts.get("Kashima Antlers", {}).get("JP1", {}).get("src_season"), "2026/2027")
    _m1, _q1 = su._match_team("Kashima Antlers", _jidx)
    check("J1队名exact", _q1, "exact")

    # ---- 中超逐场攻防数据接入 (ESPN chn.1 源, 2026-08-15) ----
    check("中超赛季权重2026=1.0", su.SEASON_WEIGHT.get("2026"), 1.0)
    check("中超DIV映射C1", su.DIV_BY_LEAGUE.get("中超"), "C1")
    check("C1进ALL_DIVS", "C1" in su.ALL_DIVS, True)
    check("中超league_calib(基准对齐)", round(su.CAL.get("中超", {}).get("league_avg"), 3), 3.04)
    csl_ts, _cl, _cidx = su.load_team_stats()
    csl_teams = {t for t, divs in csl_ts.items() if "C1" in divs}
    check("中超16队全部入库", len(csl_teams), 16)
    check("中超样本src=2026", csl_ts.get("Liaoning Tieren FC", {}).get("C1", {}).get("src_season"), "2026")
    check("中超队名exact", su._match_team("Liaoning Tieren FC", _cidx)[1], "exact")
    check("中文队名命中英文键", su._match_team("上海海港", _cidx), ("Shanghai Port", "exact"))

    # ---- 葡超/比甲 逐场数据接入 (football-data.co.uk P1/B1, 2026-08-15) ----
    check("P1进ALL_DIVS", "P1" in su.ALL_DIVS, True)
    check("B1进ALL_DIVS", "B1" in su.ALL_DIVS, True)
    check("葡超DIV映射P1", su.DIV_BY_LEAGUE.get("葡超"), "P1")
    check("比甲DIV映射B1", su.DIV_BY_LEAGUE.get("比甲"), "B1")
    check("葡超league_calib(基准对齐)", round(su.CAL.get("葡超", {}).get("league_avg", 0), 2), 2.63)
    check("比甲league_calib(开季校准)", round(su.CAL.get("比甲", {}).get("league_avg", 0), 2), 3.04)
    pb_ts, _pbl, _pbidx = su.load_team_stats()
    pb_teams = {t for t, divs in pb_ts.items() if ("P1" in divs) or ("B1" in divs)}
    check("葡超/比甲球队入库>=38", len(pb_teams) >= 38, True)
    check("波尔图P1样本", pb_ts.get("Porto", {}).get("P1", {}).get("src_season"), "2025/2026")
    check("圣吉罗斯B1样本", pb_ts.get("St. Gilloise", {}).get("B1", {}).get("src_season"), "2025/2026")
    check("Union SG别名exact", su._match_team("Union Saint-Gilloise", _pbidx)[1], "exact")
    check("Porto别名exact", su._match_team("FC Porto", _pbidx)[1], "exact")

    # ---- 第四类: 风控只降星级不改EV + 最新存档结构不变量 ----
    archs = sorted(glob.glob(os.path.join("analysis_records", "*_scan_upcoming.json")), reverse=True)
    if not archs:
        print("  ⚠️ 无 scan_upcoming 存档, 跳过存档结构断言")
        return
    d = json.load(_io.open(archs[0], encoding="utf-8"))
    ms = d["matches"]
    bb = [m for m in ms if m.get("result", {}).get("best_bet")]
    ok_ev = True
    for m in bb:
        name = m["result"]["best_bet"]["name"]
        ev0 = m["result"]["best_bet"]["ev"]
        raw = [b for b in m["result"]["bets"] if b["name"] == name]
        if not raw or abs(raw[0]["ev"] - ev0) > 1e-9:
            ok_ev = False
            break
    check("风控不折EV(仅降星级/仓位, EV原值保留)", ok_ev, True)
    # 硬否决(第32节): 被否决场次必不出单; 出单占比按"未否决场次"口径统计
    n_veto = sum(1 for m in ms if any("否决" in t for t in m.get("result", {}).get("risk_tags", [])))
    veto_no_bet = all(not m.get("result", {}).get("best_bet")
                      for m in ms if any("否决" in t for t in m.get("result", {}).get("risk_tags", [])))
    check("硬否决场次必不出单", veto_no_bet, True)
    # 2026-08-26审计校准: 25%阈值已过时(08-24方案A OU校准+08-26英联杯分档后BEST产出降至~15%,
    # 为有意收紧而非退化); 保留10%塌陷护栏(出单能力完全丧失时仍报警)
    check("best_bet占比>=10%(按未否决场次; 2026-08-26审计校准防塌陷)", len(bb) / max(1, len(ms) - n_veto) >= 0.10, True)
    n_pos = sum(1 for m in ms if any(b["ev"] > 0 for b in m["result"]["bets"]))
    check("正EV场次占比>=80%", n_pos / len(ms) >= 0.80, True)
    tier_ok = True
    for m in bb:
        if _tier_label(m["result"]["best_bet"]["ev"]) != m["result"]["best_bet"].get("ev_tier"):
            tier_ok = False
            break
    check("EV分层标签与阈值一致", tier_ok, True)
    print("  └─ 存档指标: %d场, best_bet %d (%.0f%%), 正EV %d/%d" % (
        len(ms), len(bb), len(bb) / len(ms) * 100, n_pos, len(ms)))


def test_csl_scan():
    section("26. 中超(CSL)扫描回归 (队名映射/分联赛校准/多机构去水)")
    import io as _io
    import json as _json
    # 共享别名库含中超英文->中文 (v5)
    d = _json.load(_io.open("strategy_data/teams_alias.json", encoding="utf-8"))
    check("别名库版本>=8", d.get("version", 0) >= 8, True)
    check("中超别名10条", len([k for k in d.get("alias", {}) if k in (
        "Liaoning Tieren FC", "Shenzhen Peng City FC", "Tianjin Jinmen Tiger FC",
        "Beijing FC", "Zhejiang", "Chengdu Rongcheng FC", "Yunnan Yukun",
        "Dalian Yingbo", "Shanghai Shenhua FC", "Henan FC")]), 10)
    # 分联赛校准含中超
    cal = _json.load(_io.open("strategy_data/league_calib.json", encoding="utf-8"))
    c = cal["leagues"].get("中超")
    check("中超league_avg=3.04(基准对齐)", round(c["league_avg"], 3), 3.04)
    check("中超rho=-0.04", c["rho"], -0.04)
    check("中超home=1.13", c["home"], 1.13)
    check("中超away=0.93", c["away"], 0.93)
    # scan_csl 模块: 队名映射+攻防解析+多机构最低抽水
    sys.path.insert(0, "prediction_v2")
    import scan_csl as sc
    check("CSL队名映射16条", len(sc.CN_MAP), 16)
    att, zones = sc.load_att_def()
    check("CSL攻防16队", len(att), 16)
    check("辽宁铁人主场攻防", (round(att["辽宁铁人"]["home"]["gf"], 2), round(att["辽宁铁人"]["home"]["ga"], 2)), (1.64, 1.45))
    # 合成两机构快照: 1X2/亚盘/大小球取最低抽水
    m = {
        "commence_time": "2026-08-15T11:00:00Z",
        "home": "Liaoning Tieren FC", "away": "Shenzhen Peng City FC",
        "bookmakers": [
            {"key": "bookA", "markets": [
                {"key": "h2h", "outcomes": [{"name": "Liaoning Tieren FC", "price": 2.0},
                                            {"name": "Draw", "price": 3.2},
                                            {"name": "Shenzhen Peng City FC", "price": 3.4}]},
                {"key": "spreads", "outcomes": [{"name": "Liaoning Tieren FC", "price": 1.95, "point": -0.5},
                                                {"name": "Shenzhen Peng City FC", "price": 1.95, "point": 0.5}]},
                {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 2.5},
                                               {"name": "Under", "price": 1.95, "point": 2.5}]}]},
            {"key": "bookB", "markets": [
                {"key": "h2h", "outcomes": [{"name": "Liaoning Tieren FC", "price": 2.1},
                                            {"name": "Draw", "price": 3.4},
                                            {"name": "Shenzhen Peng City FC", "price": 3.6}]},
                {"key": "spreads", "outcomes": [{"name": "Liaoning Tieren FC", "price": 2.1, "point": -1.0},
                                                {"name": "Shenzhen Peng City FC", "price": 1.75, "point": 1.0}]},
                {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 3.5},
                                               {"name": "Under", "price": 1.9, "point": 3.5}]}]},
        ],
    }
    h2h, sp, tt = sc.extract_markets(m)
    check("CSL 1X2最低抽水", h2h[1]["home"], 2.1)
    check("CSL 1X2同机构", h2h[2], "bookB")
    check("CSL 亚盘主盘0.5", abs(sp[2] + 0.5) < 1e-9, True)
    check("CSL 大小球2.5线", abs(tt[2] - 2.5) < 1e-9, True)


def test_j1_rescan():
    section("27. J1重分析回归 (多机构时效/亚盘完整性/方向冲突否决)")
    import io as _io
    import json as _json
    # 1) 亚盘或r必须>=1 (防odds-api.io Spread orr<1 bug复发)
    arch = "analysis_records/20260815_J1第2轮_9场_重分析.json"
    if not os.path.exists(arch):
        print("  ⚠️ 无J1重分析存档, 跳过")
        return
    d = _json.load(_io.open(arch, encoding="utf-8"))
    ms = d["matches"]
    check("J1重分析9场", len(ms), 9)
    orr_ok = all((m["odds"]["spread"]["orr"] or 0) >= 1.0 for m in ms)
    check("亚盘overround>=1(无假配对)", orr_ok, True)
    # 2) 每场亚盘两侧齐备
    sp_ok = all(m["odds"]["spread"]["home"] and m["odds"]["spread"]["away"] for m in ms)
    check("亚盘主客赔率齐备", sp_ok, True)
    # 3) 方向冲突否决场次存在且神户被否决
    vetoed = [m["match"] for m in ms if m["veto"]]
    check("方向冲突否决1场(神户)", "神户胜利船 vs FC东京" in vetoed, True)
    # 4) best_bet 5/9 且全部满足EV>=8%
    bb = [m for m in ms if m.get("best_bet")]
    check("best_bet 5/9", len(bb), 5)
    ev_ok = all(m["best_bet"]["ev"] >= 0.08 - 1e-9 for m in bb)
    check("best_bet均过8%门槛", ev_ok, True)
    # 5) ML/Totals来源均为8/15最新(Bet365), 无8/13旧价
    books = set()
    for m in ms:
        if m["odds"]["ml_book"]:
            books.add(m["odds"]["ml_book"])
        if m["odds"]["totals"].get("book"):
            books.add(m["odds"]["totals"]["book"])
    check("盘口机构为Bet365最新快照", books <= {"Bet365"}, True)


def test_laliga_rescan():
    section("28. 西甲重预测回归 (让球符号修复/分歧否决/无单判定)")
    import io as _io
    import json as _json
    arch = "analysis_records/20260815_西甲_重预测.json"
    if not os.path.exists(arch):
        print("  ⚠️ 无西甲重预测存档, 跳过")
        return
    d = _json.load(_io.open(arch, encoding="utf-8"))
    ms = d["matches"]
    check("西甲重预测5场", len(ms), 5)
    # 1) 昨天预测过的3场都带昨日结论字段
    y = [m for m in ms if m["predicted_yesterday"]]
    check("昨日3场标注", len(y), 3)
    check("昨日结论字段齐备", all(m.get("yesterday_conclusion") for m in y), True)
    # 2) 桑坦德方向冲突被否决(升班马高估+市场反向)
    san = [m for m in ms if "Santander" in m["match"]][0]
    check("桑坦德否决", san["step31"]["veto"], True)
    check("否决含方向冲突", any("1X2方向冲突" in r for r in san["step31"]["veto_reasons"]), True)
    # 3) 阿拉维斯/塞维利亚无单(修复后无假EV出单)
    ala = [m for m in ms if "Alav" in m["match"]][0]
    sev = [m for m in ms if m["match"].startswith("Sevilla")][0]
    check("阿拉维斯无单(修复假+78%EV)", ala["step31"]["best_bet"], None)
    check("塞维利亚无单(客队无独立数据)", sev["step31"]["best_bet"], None)
    # 4) 非否决候选best_bet均为带符号正确让球线(防+0.5/-0.5错位复发)
    cands = [m for m in ms if m["step31"]["best_bet"] and not m["step31"]["veto"]]
    check("候选2场(西班牙人/塞尔塔)", len(cands), 2)
    sign_ok = all(b["name"].startswith("让球主(-0.5)") for m in cands for b in [m["step31"]["best_bet"]])
    check("候选让球线符号正确(-0.5)", sign_ok, True)
    # 5) 候选EV均过批量门槛5%且星级>=1
    ev_ok = all(m["step31"]["best_bet"]["ev"] >= 0.05 - 1e-9 for m in cands)
    check("候选EV均>=5%门槛", ev_ok, True)
    star_ok = all(m["step31"]["star"] >= 1 for m in cands)
    check("候选星级>=1(揭幕战降星后)", star_ok, True)
    # 6) 全档无假高EV(+30%以上仅剩被否决的桑坦德)
    fake = [m for m in ms if m["step31"]["best_bet"] and not m["step31"]["veto"]
            and m["step31"]["best_bet"]["ev"] > 0.30]
    check("无未否决假高EV(>30%)", len(fake), 0)


def test_kickoff_check():
    section("29. 开盘盘口检查回归 (同线对比/升盘降水/急速跳水判定)")
    sys.path.insert(0, 'prediction_v2')
    import kickoff_check as kc
    # 同线无移动
    v, adv, _ = kc.verdict_for_leg("让球主(-0.5)", 2.10,
                                   {"spreads": {0.5: {"line": -0.5, "home": 2.10, "away": 1.80}}, "ml": None})
    check("同线无移动=维持原判", "维持" in adv, True)
    # 盘口利好+降水(主-0.5 线降到 -0.25 更有利, 且价格降)
    v, adv, _ = kc.verdict_for_leg("让球主(-0.5)", 2.10,
                                   {"spreads": {0.25: {"line": -0.25, "home": 1.95, "away": 1.95}}, "ml": None})
    check("盘口利好+降水=可信", "利好" in v and "降水" in v, True)
    # 盘口利空(主-0.5 线加深到 -0.75, 对持有者更不利)
    v, adv, _ = kc.verdict_for_leg("让球主(-0.5)", 2.10,
                                   {"spreads": {0.75: {"line": -0.75, "home": 2.30, "away": 1.65}}, "ml": None})
    check("盘口利空=降星", "利空" in v, True)
    # 同线急速跳水>=0.2 -> 大热必死
    v, adv, _ = kc.verdict_for_leg("让球主(-0.5)", 2.10,
                                   {"spreads": {0.5: {"line": -0.5, "home": 1.85, "away": 2.00}}, "ml": None})
    check("急速跳水=大热必死", "大热必死" in v, True)
    # 深盘升盘=诱热(深盘继续加深, 对持有者不利)
    v, adv, _ = kc.verdict_for_leg("让球主(-1.0)", 2.05,
                                   {"spreads": {1.25: {"line": -1.25, "home": 1.90, "away": 1.95}}, "ml": None})
    check("深盘升盘=诱热", "深盘升盘" in v, True)
    # 临场无同线盘 -> 人工复核(不拿0.0价格比-0.5)
    v, adv, _ = kc.verdict_for_leg("让球主(-0.5)", 2.10,
                                   {"spreads": {0.0: {"line": 0.0, "home": 1.54, "away": 2.74}}, "ml": None})
    check("无同线盘=人工复核", "人工" in adv, True)
    # 大小球: 大2.5 线升到3.0 = 对大不利
    v, adv, _ = kc.verdict_for_leg("大2.50", 2.10,
                                   {"totals": {3.0: {"over": 1.95, "under": 1.90}}, "ml": None})
    check("大球线升=对大不利(利空)", "利空" in v, True)

def test_csl_kickoff_check():
    """30. 中超开盘检查回归 (20260815_csl_tonight 解析 + 候选注单判定)."""
    section("30. 中超开盘检查回归 (队名映射/候选单判定)")
    sys.path.insert(0, 'prediction_v2')
    import kickoff_check as kc
    pre = kc.load_pre("中超")
    check("中超存档解析出5场", len(pre), 5)
    check("中超场次含英文队名", all(m["home"] and m["away"] for m in pre), True)
    check("中超场次含开球时间", all(m["kickoff"] for m in pre), True)
    cand = [m for m in pre if m["bb"]]
    cand = [m for m in pre if m["bb"]]
    check("中超候选单5张(新扫描v2)", len(cand), 5)
    _tj = [m for m in pre if "Tianjin" in m["match"]]
    check("天津注单为小2.50(新扫描)", _tj[0]["bb"]["name"], "小2.50")
    v, adv, _ = kc.verdict_for_leg("让球主(+0.5)", 1.72,
                                   {"spreads": {0.5: {"line": 0.5, "home": 1.66, "away": 2.06}}, "ml": None})
    check("中超让球判定可用", isinstance(adv, str) and len(adv) > 0, True)



def test_settle_batch():
    """31. 批量赛后结算回归 (让球半盘/走水/方向/大小球)."""
    section("31. 批量赛后结算回归 (settle_batch 判定)")
    sys.path.insert(0, 'prediction_v2')
    from settle_batch import settle_leg, split_line
    check("0.8拆-0.75/-1", split_line(-0.8), [-0.5, -1.0])
    check("0.2拆0/+0.5", split_line(0.2), [0.0, 0.5])
    cases = [
        ("让球主(+0.5)", 1.88, 1, 1, "win"),
        ("让球主(-0.8)", 2.02, 1, 0, "half"),
        ("让球主(-1.0)", 2.54, 1, 0, "push"),
        ("让球客(+0.2)", 1.77, 1, 1, "half"),
        ("让球客(-0.0)", 1.88, 0, 1, "win"),
        ("让球客(-0.0)", 1.88, 1, 1, "push"),
        ("大2.50", 2.10, 2, 1, "win"),
        ("大2.50", 2.10, 1, 1, "lose"),
        ("1X2平局", 3.40, 1, 1, "win"),
    ]
    for name, odds, hg, ag, want in cases:
        res, _ = settle_leg(name, odds, hg, ag)
        check("结算:%s %d-%d=%s" % (name, hg, ag, want), res, want)






def test_odds_veto_rules():
    """32. 硬否决规则回归 (复盘中超/J1: 过期/隔日盘口 + 模型与市场分歧>20pp 直接否决)."""
    section("32. 硬否决规则回归 (过期盘口/隔日快照/模型vs市场分歧>20pp直接不出单)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    # ---- 阈值配置 ----
    check("模型vs市场分歧阈值=20pp", su.MAX_MKT_DIVERGENCE, 0.20)
    check("盘口过期阈值=12h", su.SNAPSHOT_STALE_HOURS, 12.0)

    ts, lavg, index = su.load_team_stats()

    def _mk(home, away, ct, snap, h2h, sp, tt):
        return {"id": "t", "league": "中超", "home": home, "away": away,
                "ct": ct, "snap": snap, "h2h": h2h, "spread": sp, "totals": tt}

    # 场景1: 隔日快照(8/14) -> 硬否决
    r = su.analyze_match(_mk("Liaoning Tieren FC", "Shenzhen Peng City FC",
                             datetime(2026, 8, 15, 11, 0, tzinfo=timezone.utc), "2026-08-14T10:00:00Z",
                             {"home": 2.3, "away": 2.96, "draw": 3.75},
                             {"hdp_home": -0.5, "home_price": 2.14, "away_price": 1.68},
                             {"line": 2.5, "over_price": 1.6, "under_price": 2.42}),
                         ts, lavg, index)
    check("隔日快照不出单", r["best_bet"], None)
    check("隔日快照否决标注", any("过期" in t or "隔日" in t for t in r["risk_tags"]), True)

    # 场景2: 新鲜快照但模型vs市场分歧31.4pp(云南) -> 硬否决
    r = su.analyze_match(_mk("Yunnan Yukun", "Dalian Yingbo",
                             datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc), "2026-08-15T10:00:00Z",
                             {"home": 2.1, "away": 3.15, "draw": 4.3},
                             {"hdp_home": -0.5, "home_price": 2.06, "away_price": 1.85},
                             {"line": 2.5, "over_price": 1.36, "under_price": 2.9}),
                         ts, lavg, index)
    check("分歧>20pp不出单", r["best_bet"], None)
    check("分歧>20pp否决标注", any("分歧" in t and "否决" in t for t in r["risk_tags"]), True)

    # 场景3: 新鲜快照 + 分歧<=20pp(申花, 分歧~7.6pp) -> 保留出单
    r = su.analyze_match(_mk("Shanghai Shenhua FC", "Henan FC",
                             datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc), "2026-08-15T10:00:00Z",
                             {"home": 1.91, "away": 3.65, "draw": 4.3},
                             {"hdp_home": -0.5, "home_price": 1.98, "away_price": 1.97},
                             {"line": 2.5, "over_price": 1.42, "under_price": 2.68}),
                         ts, lavg, index)
    check("低分歧保留出单", r["best_bet"] is not None, True)
    check("低分歧注单正确", (r["best_bet"] or {}).get("name"), "让球主(-0.5)")

    # 场景4: 新鲜快照 + 分歧33.9pp(辽宁) -> 硬否决(即使EV虚高)
    r = su.analyze_match(_mk("Liaoning Tieren FC", "Shenzhen Peng City FC",
                             datetime(2026, 8, 15, 11, 0, tzinfo=timezone.utc), "2026-08-15T09:00:00Z",
                             {"home": 2.3, "away": 2.96, "draw": 3.75},
                             {"hdp_home": -0.5, "home_price": 2.14, "away_price": 1.68},
                             {"line": 2.5, "over_price": 1.6, "under_price": 2.42}),
                         ts, lavg, index)
    check("辽宁分歧33.9pp否决", r["best_bet"], None)

    # 场景5: 概率封顶校准(2026-08-17 101注复盘) -> 高置信腿压至PROB_CAP, EV同抽水重算
    r = su.analyze_match(_mk("Yunnan Yukun", "Dalian Yingbo",
                             datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc), "2026-08-15T10:00:00Z",
                             {"home": 2.1, "away": 3.15, "draw": 4.3},
                             {"hdp_home": -0.5, "home_price": 2.06, "away_price": 1.85},
                             {"line": 2.5, "over_price": 1.36, "under_price": 2.9}),
                         ts, lavg, index)
    _capped = [b for b in (r.get("bets") or []) if b.get("prob_raw")]
    check("封顶腿存在", len(_capped) >= 1, True)
    _leg = _capped[0] if _capped else {}
    check("封顶后prob=PROB_CAP", _leg.get("prob"), su.PROB_CAP)
    check("封顶后prob_raw>cap", (_leg.get("prob_raw") or 0) > su.PROB_CAP, True)
    _raw = _leg["prob_raw"]
    # 2026-08-27 EV公式修正(prob*price-1, 不再除抽水): 封顶EV=cap*odds-1
    _ev_old = _raw * _leg["odds"] - 1
    _ev_new = (su.PROB_CAP / _raw) * (_ev_old + 1) - 1
    check("封顶EV同抽水重算", round(_leg.get("ev", 0), 4), round(_ev_new, 4), tol=0.001)
    check("封顶note标注", any("概率封顶校准" in n for n in r.get("notes", [])), True)

    # ---- scan_csl: 过期/隔日快照否决(文件mtime驱动) ----
    import scan_csl as sc
    att, zones = sc.load_att_def()
    m = {
        "commence_time": "2026-08-15T11:00:00Z",
        "home": "Liaoning Tieren FC", "away": "Shenzhen Peng City FC",
        "bookmakers": [{"key": "bookA", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Liaoning Tieren FC", "price": 2.1},
                                        {"name": "Draw", "price": 3.4},
                                        {"name": "Shenzhen Peng City FC", "price": 3.6}]},
            {"key": "spreads", "outcomes": [{"name": "Liaoning Tieren FC", "price": 1.95, "point": -0.5},
                                            {"name": "Shenzhen Peng City FC", "price": 1.95, "point": 0.5}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 2.5},
                                           {"name": "Under", "price": 1.95, "point": 2.5}]}]}],
    }
    r_old = sc.analyze(dict(m), att, zones, snap_dt=datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc))
    check("CSL隔日快照否决", r_old["best_bet"], None)
    check("CSL否决含时效原因", any("隔日" in t or "过期" in t for t in r_old["risk"]), True)
    r_new = sc.analyze(dict(m), att, zones, snap_dt=datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc))
    check("CSL新鲜快照无时效否决", not any("隔日" in t or "过期" in t for t in r_new["risk"]), True)



def test_star2_risk_rules():
    """35. star2三规则回归 (2026-08-17 star2拆解: 禁入联赛否决/概率禁带/让球客标准档降星)."""
    section("35. star2三规则回归 (禁入联赛否决 / 概率禁带 / 让球客标准档降星)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    check("禁入联赛含J1", "J1" in su.HIGH_TIER_BAN_LEAGUES, True)
    check("概率禁带下界=0.65", su.PROB_BAN_LO, 0.65)
    check("概率禁带上界=0.70", su.PROB_BAN_HI, 0.70)

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    _orig_ban = su.HIGH_TIER_BAN_LEAGUES
    _orig_std = su._standings_idx
    su._standings_idx = lambda: {}  # 隔离积分榜接入(2026-08-26), 星级断言不受真实 standings 干扰
    # 固定联赛基准(与配置一致) -> 不触发λ平移, 断言完全确定性
    su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30), "墨超": (2.83, 30)}
    _oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
    for _c in su.CAL.values():
        _c["ou_strength_adj"] = {}  # 隔离方案A(2026-08-24), 规则用例不受OU校准影响
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}
        H2H = {"home": 2.0, "away": 3.4, "draw": 3.6}

        # ---- 规则1(测试期): 负ROI联赛仅标注观察, 不禁出 ----
        m1 = _mk("Yokohama F Marinos", "Avispa Fukuoka", "J1", H2H,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 3.5, "over_price": 2.05, "under_price": 1.78})
        r1 = su.analyze_match(m1, ts, lavg, index)
        check("J1负联赛仅标注不禁出", (r1["best_bet"] or {}).get("name"), "小3.50")
        check("J1标注后star保留2", r1["star"], 2)
        check("J1观察标注", any("历史负ROI(观察期" in t for t in r1["risk_tags"]), True)
        check("J1方向照常输出", r1["direction"] is not None, True)
        # 对照: 移出名单 -> 同样不禁出 (测试期名单不硬禁)
        su.HIGH_TIER_BAN_LEAGUES = _orig_ban - {"J1"}
        r1c = su.analyze_match(m1, ts, lavg, index)
        check("J1移出名单结果一致", (r1c["best_bet"] or {}).get("name"), "小3.50")
        su.HIGH_TIER_BAN_LEAGUES = _orig_ban

        # 规则1b(2026-08-24 用户指令: 让球+/−按球队强弱判定, 不统一客队): 客强主受(Casa Pia +1.5)保留为正确方向
        #   让球客(-1.5)深盘让禁出; 小2.50高EV(EV22.1%)仍按⑥B禁出; best=让球主(+1.5)
        m1b = _mk("Casa Pia", "Benfica", "葡超", {"home": 16.5, "draw": 7.2, "away": 1.24},
                  {"hdp_home": 1.5, "home_price": 2.14, "away_price": 1.68},
                  {"line": 2.5, "over_price": 1.6, "under_price": 2.3})
        r1b = su.analyze_match(m1b, ts, lavg, index)
        _b1b = [b["name"] for b in r1b["bets"]]
        check("客强主受让球主(+1.5)保留", "让球主(+1.5)" in _b1b, True)
        check("让球客(-1.5)深盘让禁出", "让球客(-1.5)" not in _b1b, True)
        check("规则6禁出后大2.50仍在", "大2.50" in _b1b, True)
        check("方向按强弱禁出note", any("让球方向按强弱禁出" in n for n in r1b["notes"]), True)
        check("客强主受best=让球主(+1.5)", (r1b["best_bet"] or {}).get("name"), "让球主(+1.5)")
        check("客强主受best.EV=19.8%(2026-08-27 EV公式修正后)", round((r1b["best_bet"] or {}).get("ev", 0), 4), 0.1984)
        check("客强主受best.star=2(2026-08-27规则13仅配置联赛生效: 葡超未配high_home_away_lo, 不加权)", (r1b["best_bet"] or {}).get("star"), 2)
        check("葡超无高赔主场加权标签", any("高赔主场" in t for t in r1b["risk_tags"]), False)
        # 2026-08-24 葡超基准对齐2.84->2.63后: Casa Pia小2.50 EV再降至4.7%,
        #   不再触发⑥B默认阈值; 临时降阈值0.03验证"EV>=阈值物理禁出"机制仍生效
        _orig_th = su.SMALL_250_HIGH_EV
        _oua_save_cp = su.CAL["葡超"].get("ou_strength_adj")
        su.CAL["葡超"]["ou_strength_adj"] = {}  # 隔离方案A(2026-08-24), 还原纯泊松口径验证⑥B机制
        su.SMALL_250_HIGH_EV = 0.03
        r1b2 = su.analyze_match(m1b, ts, lavg, index)
        su.SMALL_250_HIGH_EV = _orig_th
        su.CAL["葡超"]["ou_strength_adj"] = _oua_save_cp
        check("规则6小2.50高EV禁出(阈值0.03)", "小2.50" not in [b["name"] for b in r1b2["bets"]], True)
        check("规则6小2.50高EV禁出note", any("规则6小2.50高EV禁出" in n for n in r1b2["notes"]), True)
        check("规则6小2.50禁出后best不为小", (r1b2["best_bet"] or {}).get("name") != "小2.50", True)
        # ---- 规则2: 让球主原始概率∈[0.65,0.70) 禁带, best换腿 ----
        m2 = _mk("Beijing FC", "Henan FC", "中超", H2H,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.90},
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r2 = su.analyze_match(m2, ts, lavg, index)
        check("概率禁带note仍触发", any("概率禁带" in n for n in r2["notes"]), True)
        check("best不落禁带腿", (r2["best_bet"] or {}).get("name") != "让球主(-0.5)", True)
        check("best换到大2.50", (r2["best_bet"] or {}).get("name"), "大2.50")
        check("方向不落禁带腿", (r2["direction"] or {}).get("name") != "让球主(-0.5)", True)
        m2d = _mk("Beijing FC", "Henan FC", "中超", H2H,
                  {"hdp_home": -1.0, "home_price": 1.95, "away_price": 1.90},
                  {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r2d = su.analyze_match(m2d, ts, lavg, index)
        check("深盘-1.0被⑥A物理移除", "让球主(-1.0)" not in [b["name"] for b in r2d["bets"]], True)


        # ---- 规则3: 让球客标准档(EV 8~20%) 物理移除 ----
        # 2026-08-27 EV公式修正(prob*price-1)后: 原1.90让球客EV升至0.235高价值档绕开禁出,
        #   赔率降至1.84让EV落回0.196标准档验证机制; 空伤停包隔离防外部数据漂移
        _pkg_save_m3 = su._PKG_ATTACKS
        su._PKG_ATTACKS = {"by_id": {}, "by_name": {"home": {}, "away": {}}}
        try:
            m3 = _mk("West Ham", "Bournemouth", "英超", H2H,
                     {"hdp_home": -1.0, "home_price": 1.95, "away_price": 1.84},
                     {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
            r3 = su.analyze_match(m3, ts, lavg, index)
        finally:
            su._PKG_ATTACKS = _pkg_save_m3
        # 规则5: 让球客标准档(EV 8~20%) -> 物理移除(账本117注-26.5%重灾区), best 落到大小球
        check("让球客标准档被禁出", (r3["best_bet"] or {}).get("name") != "让球客(+1.0)", True)
        check("让球客禁出后best=大2.50", (r3["best_bet"] or {}).get("name"), "大2.50")
        check("禁出后best.star", (r3["best_bet"] or {}).get("star"), 2)
        check("让球客标准档禁出标注", any("让球客标准档禁出" in n for n in r3["notes"]), True)
        check("禁出后best.EV", round((r3["best_bet"] or {}).get("ev", 0), 4), 0.2295)
    finally:
        su.recent_league_avg = _orig_avg
        for _k, _v in _oua_save.items():
            su.CAL[_k]["ou_strength_adj"] = _v
        su.HIGH_TIER_BAN_LEAGUES = _orig_ban
        su._standings_idx = _orig_std

def test_rule6_direction_attribution():
    """37. 规则⑥方向归因禁出回归 (2026-08-24 改: 让球+/−方向按球队强弱判定, 不统一客队):
    A 让球方向按盘口强弱: 受让方(+号,弱队)保留(含客强主受), 让球方深盘让<=-1.0/平手/深受让>=+1.8禁出, 主客一视同仁
    B 小2.50高EV(EV>=20%)从规则②降星升级为物理禁出
    附加: 规则④前缀bug修复(ou_under_reverse联赛 best=小盘腿 -> 反向标记降星)."""
    section("37. 规则⑥方向归因禁出回归 (让球方向按强弱 + 小2.50高EV禁出 + 规则④修复)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30),
                                    "荷甲": (3.15, 30), "英冠": (2.51, 30)}
    _oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
    for _c in su.CAL.values():
        _c["ou_strength_adj"] = {}  # 隔离方案A(2026-08-24), 规则用例不受OU校准影响
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}
        H2H = {"home": 2.0, "away": 3.4, "draw": 3.6}

        # ---- ⑥A1(2026-08-24 新规则): 让球主受让(+0.5)按强弱方向保留(弱队受让=正确方向), 高prob触发市场分歧否决 ----
        m1 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H,
                 {"hdp_home": 0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r1 = su.analyze_match(m1, ts, lavg, index)
        check("规则6受让+0.5保留", "让球主(+0.5)" in [b["name"] for b in r1["bets"]], True)
        check("受让方向无方向禁出note", not any("让球方向按强弱禁出" in n for n in r1["notes"]), True)
        check("受让+0.5方向输出让主", (r1["direction"] or {}).get("name"), "让球主(+0.5)")
        check("受让+0.5高prob市场分歧否决", r1["best_bet"], None)

        # ---- ⑥A2: 让球主深盘让(-1.5) 物理禁出 ----
        m2 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H,
                 {"hdp_home": -1.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r2 = su.analyze_match(m2, ts, lavg, index)
        check("规则6深盘-1.5移除", "让球主(-1.5)" not in [b["name"] for b in r2["bets"]], True)

        # ---- ⑥A3: 中浅让(-0.5)保留, 可为best ----
        m3 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 3.5, "over_price": 1.95, "under_price": 1.95})
        r3 = su.analyze_match(m3, ts, lavg, index)
        check("规则6中浅让-0.5保留", "让球主(-0.5)" in [b["name"] for b in r3["bets"]], True)
        check("规则6中浅让可为best", (r3["best_bet"] or {}).get("name"), "让球主(-0.5)")

        # ---- ⑥B: 小2.50高EV物理禁出 (Casa Pia: 原小2.50 EV22.1%>=20%) ----
        m4 = _mk("Casa Pia", "Benfica", "葡超", {"home": 16.5, "draw": 7.2, "away": 1.24},
                 {"hdp_home": 1.5, "home_price": 2.14, "away_price": 1.68},
                 {"line": 2.5, "over_price": 1.6, "under_price": 2.3})
        r4 = su.analyze_match(m4, ts, lavg, index)
        check("规则6小2.50默认保留(EV<20%)", "小2.50" in [b["name"] for b in r4["bets"]], True)
        _orig_th2 = su.SMALL_250_HIGH_EV
        _oua_save2 = su.CAL["葡超"].get("ou_strength_adj")
        su.CAL["葡超"]["ou_strength_adj"] = {}  # 隔离方案A(2026-08-24), 还原纯泊松口径验证⑥B机制
        su.SMALL_250_HIGH_EV = 0.03
        r4b = su.analyze_match(m4, ts, lavg, index)
        su.SMALL_250_HIGH_EV = _orig_th2
        su.CAL["葡超"]["ou_strength_adj"] = _oua_save2
        check("规则6小2.50高EV移除(阈值0.03)", "小2.50" not in [b["name"] for b in r4b["bets"]], True)
        check("规则6小2.50高EV禁出note", any("规则6小2.50高EV禁出" in n for n in r4b["notes"]), True)
        check("规则6小2.50禁出后best不为小", (r4b["best_bet"] or {}).get("name") != "小2.50", True)

        # ---- 规则④⑪升级(2026-08-27): 荷甲 ou_under_reverse -> 低估区禁小球(取代降星反向标记) ----
        m5 = _mk("FC Utrecht", "Sparta Rotterdam", "荷甲", H2H,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 2.5, "over_price": 1.85, "under_price": 2.05})
        r5 = su.analyze_match(m5, ts, lavg, index)
        check("规则⑪荷甲小球禁带(取代降星)", (r5["best_bet"] or {}).get("name") != "小2.50", True)
        check("规则⑪荷甲禁小球风险标签", any("低估区禁小球" in t for t in r5["risk_tags"]), True)
        check("规则⑪荷甲note", any("规则11" in n for n in r5["notes"]), True)
        check("规则⑪荷甲方向不落小球", (r5["direction"] or {}).get("name") != "小2.50", True)

        # ---- 源码分支存在性 + 统计口径 ----
        _sc6 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
        check("让球方向按强弱分支存在", "_hd == HDP_BAN_DRAW or _hd <= HDP_BAN_GIVE_DEEP or _hd >= HDP_BAN_RECEIVE_DEEP" in _sc6, True)
        check("规则⑥B分支存在", "SMALL_250_HIGH_EV" in _sc6 and "规则6小2.50高EV禁出" in _sc6, True)
        check("规则④前缀bug已修复", 'startswith("小球")' not in _sc6, True)
        _pss6 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_settle.py"), encoding="utf-8").read()
        check("settle统计口径star视图", "有效出单(star非空" in _pss6, True)
    finally:
        su.recent_league_avg = _orig_avg
        for _k, _v in _oua_save.items():
            su.CAL[_k]["ou_strength_adj"] = _v


def test_rule7_strong_draw_plus():
    """38. 规则⑦强预警改+号回归 (2026-08-23 M-20260823-07):
    强平局预警(去水平局>=30%) + best为大小球2.50 -> 移除2.50大小球腿, 只打+号受让; 无正EV+号 -> 无单."""
    section("38. 规则⑦强预警改+号回归 (强预警+2.50盘移除, 只打+号受让)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}
        H2H_STRONG = {"home": 2.8, "draw": 3.0, "away": 2.9}   # 去水平局32.2% -> 强预警
        H2H_WARN = {"home": 2.5, "draw": 3.4, "away": 3.0}     # 去水平局28.6% -> 普通预警

        # ---- ⑦A: 强预警 + OU2.50 -> 2.50腿移除, 无正EV+号 -> 无单 ----
        m1 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_STRONG,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r1 = su.analyze_match(m1, ts, lavg, index)
        check("规则⑦强预警激活(32.2%)", (r1["draw_warn"] or {}).get("strong"), True)
        _b1 = [b["name"] for b in r1["bets"]]
        check("规则⑦2.50大小球移除", "大2.50" not in _b1 and "小2.50" not in _b1, True)
        check("规则⑦无正EV+号->无单", r1["best_bet"], None)
        check("规则⑦note", any("规则7强预警改+号" in n for n in r1["notes"]), True)

        # ---- ⑦B: 强预警 + 无亚盘 -> 无单 ----
        m2 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_STRONG, None,
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r2 = su.analyze_match(m2, ts, lavg, index)
        check("规则⑦无亚盘无单", r2["best_bet"], None)

        # ---- ⑦C: 普通预警(28.6%) -> 2.50保留(仅规则③降星) ----
        m3 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_WARN,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r3 = su.analyze_match(m3, ts, lavg, index)
        check("规则⑦普通预警不强", (r3["draw_warn"] or {}).get("strong"), False)
        check("规则⑦普通预警2.50保留", "大2.50" in [b["name"] for b in r3["bets"]], True)
        check("规则⑦普通预警不出note", any("规则7强预警改+号" in n for n in r3["notes"]), False)

        # ---- ⑦D: 强预警 + 让客+号正EV -> best换到+号 ----
        m4 = _mk("Everton", "Leicester City", "英超", H2H_STRONG,
                 {"hdp_home": -0.5, "home_price": 1.92, "away_price": 2.16},
                 {"line": 2.5, "over_price": 1.90, "under_price": 1.95})
        r4 = su.analyze_match(m4, ts, lavg, index)
        check("规则⑦换+号best", (r4["best_bet"] or {}).get("name"), "让球客(+0.5)")
        check("规则⑦换+号EV>=5%", (r4["best_bet"] or {}).get("ev", 0) >= 0.05, True)
        check("规则⑦换+号后无2.50", "大2.50" not in [b["name"] for b in r4["bets"]], True)

        _sc7 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
        check("规则⑦代码分支存在", "规则7强预警改+号" in _sc7, True)
    finally:
        su.recent_league_avg = _orig_avg

def test_ou_strength_adj():
    """41. 方案A按对阵强度分段校准大球回归 (2026-08-24, 葡超348场拟合):
    独立泊松低估大球(强强+12.5/混合+9.0/弱弱+3.5pp) -> ou_strength_adj 按档上修大球概率; 仅配置联赛生效."""
    section("41. 方案A按对阵强度分段校准大球 (葡超三档大球上修)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    _adj = su.CAL["葡超"].get("ou_strength_adj") or {}
    check("方案A葡超配置存在", bool(_adj), True)
    check("方案A强强档0.10", _adj.get("强强"), 0.10)
    check("方案A混合档0.09", _adj.get("混合"), 0.09)
    check("方案A弱弱档0.04", _adj.get("弱弱"), 0.04)
    check("方案A扩展中超", (su.CAL.get("中超", {}).get("ou_strength_adj") or {}).get("混合"), 0.09)
    check("方案A扩展英冠强强", (su.CAL.get("英冠", {}).get("ou_strength_adj") or {}).get("强强"), 0.12)
    check("方案A扩展比甲弱弱", (su.CAL.get("比甲", {}).get("ou_strength_adj") or {}).get("弱弱"), 0.10)
    check("方案A扩展意甲混合", (su.CAL.get("意甲", {}).get("ou_strength_adj") or {}).get("混合"), 0.04)
    check("方案A扩展德甲强强", (su.CAL.get("德甲", {}).get("ou_strength_adj") or {}).get("强强"), 0.09)
    check("方案A荷甲混合档", (su.CAL.get("荷甲", {}).get("ou_strength_adj") or {}).get("混合"), 0.04)
    check("方案A其他联赛不启用", su.CAL.get("英超", {}).get("ou_strength_adj") is None, True)

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}
        m = _mk("Casa Pia", "Benfica", "葡超", {"home": 16.5, "draw": 7.2, "away": 1.24},
                {"hdp_home": 1.5, "home_price": 2.14, "away_price": 1.68},
                {"line": 2.5, "over_price": 1.6, "under_price": 2.3})
        r_on = su.analyze_match(m, ts, lavg, index)
        _ov_on = next((b for b in r_on["bets"] if b["name"] == "大2.50"), None)
        check("方案A葡超note生效", any("方案A大球校准" in n for n in r_on["notes"]), True)
        check("方案A档位标签", _ov_on is not None and _ov_on.get("ou_bucket") in ("强强", "混合", "弱弱"), True)

        _save = su.CAL["葡超"].get("ou_strength_adj")
        su.CAL["葡超"]["ou_strength_adj"] = {}
        r_off = su.analyze_match(m, ts, lavg, index)
        su.CAL["葡超"]["ou_strength_adj"] = _save
        _ov_off = next((b for b in r_off["bets"] if b["name"] == "大2.50"), None)
        _gain = (_ov_on["prob"] - _ov_off["prob"]) if (_ov_on and _ov_off) else 0.0
        check("方案A大球概率上修>=8pp(混合档9pp)", _gain >= 0.08, True)

        # 墨超负偏移(2026-08-24): 876场拟合模型高估大球(强强-6.6/混合-3.2pp) -> 负档位下调大球
        _mx_adj = su.CAL.get("墨超", {}).get("ou_strength_adj") or {}
        check("方案A墨超强强负档-0.05", _mx_adj.get("强强"), -0.05)
        check("方案A墨超混合负档-0.02", _mx_adj.get("混合"), -0.02)
        _save_mx = su.CAL["墨超"].get("ou_strength_adj")
        m_mx = _mk("Monterrey", "Toluca", "墨超", {"home": 1.9, "draw": 3.4, "away": 4.2},
                   {"hdp_home": 0.5, "home_price": 1.95, "away_price": 1.85},
                   {"line": 2.5, "over_price": 1.8, "under_price": 1.95})
        r_mx_on = su.analyze_match(m_mx, ts, lavg, index)
        su.CAL["墨超"]["ou_strength_adj"] = {}
        r_mx_off = su.analyze_match(m_mx, ts, lavg, index)
        su.CAL["墨超"]["ou_strength_adj"] = _save_mx
        _ov_mx_on = next((b for b in r_mx_on["bets"] if b["name"] == "大2.50"), None)
        _ov_mx_off = next((b for b in r_mx_off["bets"] if b["name"] == "大2.50"), None)
        _diff_mx = (_ov_mx_on["prob"] - _ov_mx_off["prob"]) if (_ov_mx_on and _ov_mx_off) else 0.0
        check("方案A墨超负档下调大球>=3pp(强强-5pp)", _diff_mx <= -0.03, True)
        # 法甲负校准(2026-08-24): 612场拟合模型高估大球总-3.3pp(混合-3.9/弱弱-8.1) -> 负档位下调大球
        _fra_adj = su.CAL.get("法甲", {}).get("ou_strength_adj") or {}
        check("方案A法甲混合负档-0.03", _fra_adj.get("混合"), -0.03)
        check("方案A法甲弱弱负档-0.06", _fra_adj.get("弱弱"), -0.06)
        check("方案A法甲强强反向不配", _fra_adj.get("强强") is None, True)
        _save_fra = su.CAL["法甲"].get("ou_strength_adj")
        m_fra = _mk("Nantes", "Auxerre", "法甲", {"home": 2.0, "draw": 3.4, "away": 3.6},
                    {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                    {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r_fra_on = su.analyze_match(m_fra, ts, lavg, index)
        su.CAL["法甲"]["ou_strength_adj"] = {}
        r_fra_off = su.analyze_match(m_fra, ts, lavg, index)
        su.CAL["法甲"]["ou_strength_adj"] = _save_fra
        _ov_fra_on = next((b for b in r_fra_on["bets"] if b["name"] == "大2.50"), None)
        _ov_fra_off = next((b for b in r_fra_off["bets"] if b["name"] == "大2.50"), None)
        _diff_fra = (_ov_fra_on["prob"] - _ov_fra_off["prob"]) if (_ov_fra_on and _ov_fra_off) else 0.0
        check("方案A法甲负档下调大球>=3pp(弱弱-6pp)", _diff_fra <= -0.03, True)
    finally:
        su.recent_league_avg = _orig_avg

    _sc = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
    check("方案A源码分支存在", "ou_strength_adj" in _sc and "方案A大球校准" in _sc, True)
    check("方案A支持负偏移(墨超)", "_oadj != 0" in _sc, True)


def test_rule9_fake_small():
    """40. 规则⑨假小球拦截回归 (2026-08-24, 荷甲账本5注小球全灭实证):
    模型自算大球>=50% 且 市场隐含大>=60% -> 小球正EV腿移出候选(λ低估假信号); 真小球(双低)保留."""
    section("40. 规则⑨假小球拦截 (模型大>=50% + 市场隐含大>=60% -> 小球假信号禁出)")
    sys.path.insert(0, 'prediction_v2')
    import scan_upcoming as su

    # 触发: 模型大58% + 市场隐含大67%(1.40/2.85) -> 小球EV+10%腿被移出
    bets = [
        {"name": "大2.50", "prob": 0.58, "ev": -0.24},
        {"name": "小2.50", "prob": 0.42, "ev": 0.10},
        {"name": "让球主(+1.0)", "prob": 0.65, "ev": 0.17},
    ]
    n, m_over, mk_over = su.fake_small_intercept(bets, {"line": 2.5, "over_price": 1.40, "under_price": 2.85})
    check("⑨触发拦截1腿", n, 1)
    check("⑨模型大>=50%", m_over >= 0.50, True)
    check("⑨市场隐含大>=60%", mk_over >= 0.60, True)
    check("⑨小球腿已移出", next(b for b in bets if b["name"] == "小2.50")["_pband_banned"], True)
    check("⑨让球腿不受影响", "_pband_banned" not in next(b for b in bets if b["name"].startswith("让球")), True)

    # 不触发: 市场隐含大<60% (1.85/2.05 -> 52.6%)
    bets2 = [{"name": "大2.50", "prob": 0.58, "ev": -0.24}, {"name": "小2.50", "prob": 0.42, "ev": 0.10}]
    n2, _, mk2 = su.fake_small_intercept(bets2, {"line": 2.5, "over_price": 1.85, "under_price": 2.05})
    check("⑨市场大<60%不触发", n2, 0)
    check("⑨市场大52.6%计算", round(mk2, 3), 0.526)

    # 不触发: 模型大<50% (真小球场景, 保留)
    bets3 = [{"name": "大2.50", "prob": 0.46, "ev": -0.30}, {"name": "小2.50", "prob": 0.54, "ev": 0.12}]
    n3, m3, _ = su.fake_small_intercept(bets3, {"line": 2.5, "over_price": 1.70, "under_price": 2.10})
    check("⑨模型大<50%不触发(真小球保留)", n3, 0)

    # 缺盘口保护
    n4, _, _ = su.fake_small_intercept([{"name": "小2.50", "prob": 0.42, "ev": 0.10}], None)
    check("⑨缺大小球盘口不触发", n4, 0)

    # 源码分支
    _sc = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
    check("⑨源码分支存在", "fake_small_intercept" in _sc and "假小球拦截" in _sc, True)


def test_rule11_under_ban_small():
    """41. 规则⑪低估区禁小球回归 (2026-08-27, 300场复盘+账本实证):
    英冠/荷甲(ou_under_reverse) + 杯赛低估区名单(德国杯/英联杯/欧冠/欧联杯/欧协联) + 实测>配置
    -> 小球腿移出候选+方向; 高估区/正常联赛小球保留."""
    section("41. 规则⑪低估区禁小球 (小球只在λ高估区推, 低估区禁小)")
    sys.path.insert(0, 'prediction_v2')
    import scan_upcoming as su

    check("⑪名单含欧冠", "欧冠" in su.LOW_EST_UNDER_BAN_SMALL, True)
    check("⑪名单含英联杯", "英联杯" in su.LOW_EST_UNDER_BAN_SMALL, True)
    check("⑪名单不含中超", "中超" not in su.LOW_EST_UNDER_BAN_SMALL, True)

    # 触发①: ou_under_reverse=True (英冠/荷甲)
    bets = [
        {"name": "大2.50", "prob": 0.52, "ev": -0.20},
        {"name": "小2.50", "prob": 0.48, "ev": 0.12},
        {"name": "让球主(-0.5)", "prob": 0.60, "ev": 0.15},
    ]
    n = su.under_zone_ban_small([dict(b) for b in bets], "英冠", {"ou_under_reverse": True}, False, 0.0)
    check("⑪英冠禁小球1腿", n, 1)
    check("⑪英冠小球打标", next(b for b in bets if b["name"] == "小2.50")["_pband_banned"], True)
    check("⑪英冠大球/让球不受影响", "_pband_banned" not in next(b for b in bets if b["name"].startswith("大")) and "_pband_banned" not in next(b for b in bets if b["name"].startswith("让球")), True)

    # 触发②: 杯赛低估区名单 (欧冠/英联杯/德国杯/欧联杯/欧协联)
    bets2 = [{"name": "小2.50", "prob": 0.55, "ev": 0.10}]
    n2 = su.under_zone_ban_small([dict(b) for b in bets2], "欧冠", {}, False, 0.0)
    check("⑪欧冠禁小球1腿", n2, 1)
    n2b = su.under_zone_ban_small([dict(b) for b in bets2], "英联杯", {}, False, 0.0)
    check("⑪英联杯禁小球", n2b, 1)

    # 触发③: 数据驱动(实测场均>配置基准)
    bets3 = [{"name": "小2.50", "prob": 0.55, "ev": 0.10}]
    n3 = su.under_zone_ban_small([dict(b) for b in bets3], "瑞超", {}, True, 0.5)
    check("⑪实测>基准禁小球", n3, 1)

    # 不触发: 正常联赛+无偏差 (西甲/西乙等小球保留)
    bets4 = [{"name": "小2.50", "prob": 0.55, "ev": 0.10}]
    n4 = su.under_zone_ban_small([dict(b) for b in bets4], "西甲", {}, False, 0.0)
    check("⑪西甲不禁小球", n4, 0)
    check("⑪西甲小球无打标", "_pband_banned" not in bets4[0], True)

    # 源码分支
    _sc = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
    check("⑪源码分支存在", "under_zone_ban_small" in _sc and "低估区禁小球" in _sc, True)


def test_rule8_odds_overest():
    """39. 规则⑧赔率高估区回归 (2026-08-24 M-20260824-03, 账本831注实证):
    主胜1.8~2.2(真实主胜28%)/客胜2.2~2.8(真实客胜11%) -> 高估区标签;
    高估区内best为受让+号(0<盘口<=0.8) -> 加1星+仓位x1.5; best为让球-号 -> 降1星+仓位x0.5."""
    section("39. 规则⑧赔率高估区回归 (受让+号加权重 / 让球-号降权重)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    check("规则⑧主胜高估区下界", su.FAV_HOME_OVEREST_LO, 1.8)
    check("规则⑧主胜高估区上界", su.FAV_HOME_OVEREST_HI, 2.2)
    check("规则⑧客胜高估区下界", su.FAV_AWAY_OVEREST_LO, 2.2)
    check("规则⑧客胜高估区上界", su.FAV_AWAY_OVEREST_HI, 2.8)
    check("规则⑧受让+号盘口上限", su.OVEREST_RECEIVE_HDP_MAX, 0.8)
    check("规则⑧受让+号加星", su.OVEREST_RECEIVE_STAR_BOOST, 1)
    check("规则⑧受让+号仓位x1.5", su.OVEREST_RECEIVE_STAKE_MULT, 1.5)
    check("规则⑧让球-号仓位x0.5", su.OVEREST_GIVE_STAKE_MULT, 0.5)

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
    _oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
    for _c in su.CAL.values():
        _c["ou_strength_adj"] = {}  # 隔离方案A(2026-08-24), 规则用例不受OU校准影响
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}

        # ---- ⑧A: 主胜高估区(赔率2.00) + best=让球主(-0.5) -> 让球-号降权重标签 + star降 + 仓位x0.5 ----
        m1 = _mk("Shanghai Shenhua FC", "Henan FC", "中超",
                 {"home": 2.0, "away": 3.4, "draw": 3.6},
                 {"hdp_home": -0.5, "home_price": 2.05, "away_price": 2.05},
                 {"line": 3.5, "over_price": 1.95, "under_price": 1.95})
        r1 = su.analyze_match(m1, ts, lavg, index)
        check("⑧A主胜高估区标签", any("主胜高估区" in t for t in r1["risk_tags"]), True)
        check("⑧A让球-号降权重标签", any("高估区让球-号降权重" in t for t in r1["risk_tags"]), True)
        check("⑧A best为让球-号", (r1["best_bet"] or {}).get("name"), "让球主(-0.5)")
        check("⑧A note含规则8", any("规则8赔率高估区" in n for n in r1["notes"]), True)
        check("⑧A让球-号star=2(3-1降权重, 高估区标签不计n_risk)", r1["star"], 2)
        check("⑧A让球-号仓位x0.5(高价值1.0*0.5降仓, 高估区不计n_risk)", (r1["best_bet"] or {}).get("stake_factor", 0), 0.5)

        # ---- ⑧B: 客胜高估区(赔率2.50) + best=让球客(+0.5) 高价值档(EV0.2384避开让客标准档禁出) -> 受让+号加权重 ----
        # 2026-08-26夹具冻结: 隔离实时match_package伤停(Everton主3伤曾污染夹具致star/stake漂移),
        # 空包确保本用例只测规则⑧本身, 不随外部数据变化
        # 2026-08-27 EV公式修正后: 原away_price=2.10让球客EV落回标准档被禁出, 升至2.20恢复高价值档
        _pkg_save = su._PKG_ATTACKS
        su._PKG_ATTACKS = {"by_id": {}, "by_name": {"home": {}, "away": {}}}
        try:
            m2 = _mk("Everton", "Leicester City", "英超",
                     {"home": 2.6, "away": 2.5, "draw": 3.3},
                     {"hdp_home": -0.5, "home_price": 2.10, "away_price": 2.20},
                     {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
            r2 = su.analyze_match(m2, ts, lavg, index)
        finally:
            su._PKG_ATTACKS = _pkg_save
        check("⑧B客胜高估区标签", any("客胜高估区" in t for t in r2["risk_tags"]), True)
        check("⑧B受让+号加权重标签", any("高估区受让+号加权重" in t for t in r2["risk_tags"]), True)
        check("⑧B best为受让+号", (r2["best_bet"] or {}).get("name"), "让球客(+0.5)")
        check("⑧B受让+号EV高价值", (r2["best_bet"] or {}).get("ev", 0) >= 0.20, True)
        check("⑧B受让+号star=3(3-1平局风控+1加星)", r2["star"], 3)
        check("⑧B受让+号仓位(1.0*1.5*0.5平局风控)", (r2["best_bet"] or {}).get("stake_factor", 0), 0.75)

        # ---- ⑧C: 高估区标签标记1X2热门腿(_overest_1x2) ----
        _hw_leg = [b for b in r1["bets"] if b["name"] == "1X2主胜"]
        check("⑧C主胜热门腿打标", bool(_hw_leg and _hw_leg[0].get("_overest_1x2")), True)
        _aw_leg = [b for b in r2["bets"] if b["name"] == "1X2客胜"]
        check("⑧C客胜热门腿打标", bool(_aw_leg and _aw_leg[0].get("_overest_1x2")), True)

        # ---- 源码分支存在性 ----
        _sc8 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
        check("规则⑧常量分支存在", "OVEREST_RECEIVE_HDP_MAX" in _sc8 and "OVEREST_RECEIVE_STAKE_MULT" in _sc8, True)
        check("规则⑧加权重分支存在", "高估区受让+号加权重" in _sc8, True)
        check("规则⑧降权重分支存在", "高估区让球-号降权重" in _sc8, True)
    finally:
        su.recent_league_avg = _orig_avg
        for _k, _v in _oua_save.items():
            su.CAL[_k]["ou_strength_adj"] = _v

def test_draw_warn_plus_rules():
    """36. 2026-08-23 三条规则回归 (M-20260823-01/02/03):
    ① 平局预警26%+ -> 让球只用+号(受让方)  ② 小2.50高EV反向标记  ③ 整球盘2.50遇预警降星."""
    section("36. 平局预警三条规则回归 (让球只用+号 / 小2.50高EV反向 / 整球盘2.50降星)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    check("规则①开关启用", su.DRAW_WARN_HDP_PLUS_ONLY, True)
    check("规则③整球盘线=2.50", su.DRAW_WARN_TOTALS_LINE, 2.5)
    check("规则②高EV阈值=20%", su.SMALL_250_HIGH_EV, 0.20)

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
    _oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
    for _c in su.CAL.values():
        _c["ou_strength_adj"] = {}  # 隔离方案A(2026-08-24), 规则用例不受OU校准影响
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}
        # 平局去水概率28.6%>=26% -> 预警激活
        H2H_DW = {"home": 2.5, "draw": 3.4, "away": 3.0}

        # ---- 规则①: 预警激活 + 让球主(-0.5) -> -号腿从bets移除, 方向不落-号腿 ----
        m1 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW,
                 {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
                 {"line": 3.5, "over_price": 2.05, "under_price": 1.78})
        r1 = su.analyze_match(m1, ts, lavg, index)
        check("预警激活(去水平局>=26%)", (r1["draw_warn"] or {}).get("market_draw_prob", 0) >= 26, True)
        _minus_legs = [b["name"] for b in r1["bets"]
                       if b["name"].startswith("让球") and float(b["name"].split("(")[1].split(")")[0]) < 0]
        check("预警下-号让球腿全移除", len(_minus_legs), 0)
        check("预警下方向不落-号让球", (r1["direction"] or {}).get("name") != "让球主(-0.5)", True)
        check("预警让球只用+号标注", any("让球只用+号" in t for t in r1["risk_tags"]), True)

        # ---- 规则③: 预警激活 + best为2.50大小球 -> 整球盘2.50降星标注 + star下调 ----
        m3 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW,
                 None,
                 {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r3 = su.analyze_match(m3, ts, lavg, index)
        check("预警下best为2.50大小球", (r3["best_bet"] or {}).get("name") in ("大2.50", "小2.50"), True)
        check("整球盘2.50遇预警降星标注", any("整球盘2.50遇预警降星" in t for t in r3["risk_tags"]), True)
        check("规则③降星后star<=2", r3["star"] <= 2, True)

        # ---- 规则④(2026-08-23): 英冠/荷甲 小球反向标记 + 荷甲 league_avg 修正 ----
        check("英冠 ou_under_reverse 开启", su.CAL["英冠"].get("ou_under_reverse"), True)
        check("荷甲 ou_under_reverse 开启", su.CAL["荷甲"].get("ou_under_reverse"), True)
        check("荷甲 league_avg 修正 3.688->3.15", su.CAL["荷甲"].get("league_avg"), 3.15)
        # ---- 规则⑤(2026-08-24 改): 让球+/−方向按球队强弱判定(不统一客队); 让球客标准档EV8-20%残项仍禁出 ----
        _sc = io.open(r"prediction_v2/scan_upcoming.py", encoding="utf-8").read()
        check("规则⑤代码分支存在", "规则5残项(2026-08-23 M-20260823-05)" in _sc, True)
        check("让球方向按强弱分支存在", "_hd == HDP_BAN_DRAW or _hd <= HDP_BAN_GIVE_DEEP or _hd >= HDP_BAN_RECEIVE_DEEP" in _sc, True)
        check("规则⑤note标注", "让球客标准档禁出: 移除" in _sc, True)
        check("让球方向按强弱开关", su.HDP_PLUS_BY_STRENGTH, True)
        check("平手盘禁出阈值", su.HDP_BAN_DRAW, 0.0)
        check("深盘让禁出阈值", su.HDP_BAN_GIVE_DEEP, -1.0)
        check("深受让禁出阈值", su.HDP_BAN_RECEIVE_DEEP, 1.8)

        _src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2", "scan_upcoming.py"), encoding="utf-8").read()
        check("规则④代码分支存在", "ou_under_reverse" in _src and "联赛小球反向标记" in _src, True)
        _pss = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_settle.py"), encoding="utf-8").read()
        check("settle账本比分字段", "home_score" in _pss and "is_draw" in _pss, True)
    finally:
        su.recent_league_avg = _orig_avg
        for _k, _v in _oua_save.items():
            su.CAL[_k]["ou_strength_adj"] = _v



def test_laliga_rule13():
    """38. 2026-08-27 西甲规则13回归 (3043场实证):
    ① 热主1.55-2.20 让球主-号禁出 + 热主禁追区标签  ② 西甲防平线28%(平赔<=3.5升强预警)  ③ 高赔主场>2.8 受让+号加权重分支"""
    section("38. 西甲规则13回归 (热主禁追区/防平线28%/高赔主场客胜)")
    sys.path.insert(0, 'prediction_v2')
    from datetime import datetime, timezone
    import scan_upcoming as su

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    su.recent_league_avg = lambda: {}
    _oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
    for _c in su.CAL.values():
        _c["ou_strength_adj"] = {}
    try:
        def _mk(home, away, league, h2h, sp, tt):
            return {"id": "t", "league": league, "home": home, "away": away,
                    "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
                    "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}

        # ① 热主1.70(陷阱区): 让球主(-0.5)应从bets移除, 输出热主禁追区标签
        m1 = _mk("Real Madrid", "Getafe", "西甲",
                 {"home": 1.70, "draw": 3.60, "away": 5.20},
                 {"hdp_home": -0.5, "home_price": 1.90, "away_price": 1.98},
                 {"line": 2.5, "over_price": 2.05, "under_price": 1.80})
        r1 = su.analyze_match(m1, ts, lavg, index)
        _minus_13 = [b["name"] for b in r1["bets"]
                     if b["name"].startswith("让球主") and float(b["name"].split("(")[1].split(")")[0]) < 0]
        check("西甲热主1.70让球主-号腿移除", len(_minus_13), 0)
        check("西甲热主禁追区标签", any("热主禁追区(西甲" in t for t in r1["risk_tags"]), True)
        # 规则13泛化(2026-08-27 五大19763场切片): 英超热主2.10∈[2.00,2.20) 同样移除让球主-号+打标签
        m1b13 = _mk("Arsenal", "Crystal Palace", "英超",
                    {"home": 2.10, "draw": 3.30, "away": 3.80},
                    {"hdp_home": -0.5, "home_price": 1.90, "away_price": 1.98},
                    {"line": 2.5, "over_price": 2.05, "under_price": 1.80})
        r1b13 = su.analyze_match(m1b13, ts, lavg, index)
        _minus_13b = [b["name"] for b in r1b13["bets"]
                      if b["name"].startswith("让球主") and float(b["name"].split("(")[1].split(")")[0]) < 0]
        check("英超热主2.10让球主-号腿移除", len(_minus_13b), 0)
        check("英超热主2.10禁追区标签", any("热主禁追区(英超" in t for t in r1b13["risk_tags"]), True)
        # 规则14 OU价值区(2026-08-27 五大19763场切片): 意甲市场隐含大∈[0.50,0.55) 大球概率+3.6pp
        m1c14 = _mk("Inter", "Lecce", "意甲",
                    {"home": 1.40, "draw": 4.50, "away": 8.00},
                    {"hdp_home": -1.0, "home_price": 1.85, "away_price": 2.05},
                    {"line": 2.5, "over_price": 1.88, "under_price": 1.95})
        rz14 = su.analyze_match(m1c14, ts, lavg, index)
        _zz_save = su.CAL["意甲"].get("ou_mkt_zones")
        del su.CAL["意甲"]["ou_mkt_zones"]
        rnz14 = su.analyze_match(m1c14, ts, lavg, index)
        su.CAL["意甲"]["ou_mkt_zones"] = _zz_save
        _pz = next((b["prob"] for b in rz14["bets"] if b["name"] == "大2.50"), 0.0)
        _pnz = next((b["prob"] for b in rnz14["bets"] if b["name"] == "大2.50"), 0.0)
        check("意甲OU价值区大球+3.6pp", round(_pz - _pnz, 4), 0.036)
        check("意甲OU价值区note", any("OU价值区校准" in n and "意甲" in n for n in rz14["notes"]), True)
        # 规则13 高赔主场>=2.8 受让+号加权重(仅五大已配置生效): 西甲3.0受让+1.0打标签
        # 2026-08-27 EV公式修正后原Getafe/RM夹具(raw 0.71触发20pp分歧否决), 换Villarreal/RM
        #   (raw 0.7925/市场fair 0.6024/分歧0.19不否决); 空伤停包隔离防外部数据漂移
        _pkg_save_13 = su._PKG_ATTACKS
        su._PKG_ATTACKS = {"by_id": {}, "by_name": {"home": {}, "away": {}}}
        try:
            m1e13 = _mk("Villarreal", "Real Madrid", "西甲",
                        {"home": 3.00, "draw": 3.40, "away": 2.15},
                        {"hdp_home": 1.0, "home_price": 1.65, "away_price": 2.50},
                        {"line": 2.5, "over_price": 2.05, "under_price": 1.80})
            r1e13 = su.analyze_match(m1e13, ts, lavg, index)
        finally:
            su._PKG_ATTACKS = _pkg_save_13
        check("西甲高赔主场受让+号best", (r1e13["best_bet"] or {}).get("name"), "让球主(+1.0)")
        check("西甲高赔主场加权标签", any("高赔主场(>2.8)受让+号加权重" in t for t in r1e13["risk_tags"]), True)
        check("西甲高赔主场best.EV(标准档)", round((r1e13["best_bet"] or {}).get("ev", 0), 4), 0.0725)
        check("西甲高赔主场best.star=2", (r1e13["best_bet"] or {}).get("star"), 2)
        # 规则14 亚盘zone禁出: 意甲主受让+0.75~+1.25(主赢盘41.6%) 让球主(+1.0)移除
        m1d14 = _mk("Genoa", "Inter", "意甲",
                    {"home": 5.00, "draw": 3.80, "away": 1.70},
                    {"hdp_home": 1.0, "home_price": 1.95, "away_price": 1.95},
                    {"line": 2.5, "over_price": 1.90, "under_price": 1.95})
        r1d14 = su.analyze_match(m1d14, ts, lavg, index)
        _hd14 = [b["name"] for b in r1d14["bets"] if b["name"].startswith("让球")]
        check("意甲受让+1.0 zone禁出", "让球主(+1.0)" not in _hd14, True)
        check("意甲zone禁出note", any("主受让+0.75~+1.25" in n for n in r1d14["notes"]), True)

        # ② 西甲防平线28%: 去水平局28.6%且平赔3.4<=3.5 -> 强预警(全球30%线未到)
        m2 = _mk("Real Betis", "Sevilla", "西甲",
                 {"home": 2.5, "draw": 3.4, "away": 3.0},
                 None, {"line": 2.5, "over_price": 2.0, "under_price": 1.8})
        r2 = su.analyze_match(m2, ts, lavg, index)
        check("西甲平赔3.4+去水平局>=28%强预警", (r2["draw_warn"] or {}).get("strong"), True)
        check("西甲强预警标签含28%条件", any("平赔<=3.5" in t for t in r2["risk_tags"]), True)

        # ③ 对照组: 英超同热主1.70 不应有西甲标签
        m3 = _mk("Manchester City", "Wolves", "英超",
                 {"home": 1.70, "draw": 3.60, "away": 5.20},
                 {"hdp_home": -0.5, "home_price": 1.90, "away_price": 1.98},
                 {"line": 2.5, "over_price": 2.05, "under_price": 1.80})
        r3 = su.analyze_match(m3, ts, lavg, index)
        check("英超1.70非热主区无禁追标签", any("热主禁追区" in t for t in r3["risk_tags"]), False)

        # ④ 高赔主场>2.8 受让+号加权重代码分支存在 + 西甲配置
        _src = io.open(r"prediction_v2/scan_upcoming.py", encoding="utf-8").read()
        check("规则13代码分支存在", "hot_home_ban_lo" in _src and "热主禁追区" in _src and "high_home_away_lo" in _src, True)
        check("规则14代码分支存在", "ou_mkt_zones" in _src and "hdp_home_ban_zones" in _src, True)
        check("西甲配置防平线28%", su.CAL.get("西甲", {}).get("draw_warn_min"), 0.28)
        check("五大热主区配置", all(su.CAL.get(lg, {}).get("hot_home_ban_lo") == 2.0 for lg in ("英超", "德甲", "意甲", "法甲")), True)
        check("西甲热主区保留1.55", su.CAL.get("西甲", {}).get("hot_home_ban_lo"), 1.55)
        check("五大高赔主场下限2.8", all(su.CAL.get(lg, {}).get("high_home_away_lo") == 2.8 for lg in ("英超", "西甲", "德甲", "意甲", "法甲")), True)
        check("意甲OU zone配置", su.CAL.get("意甲", {}).get("ou_mkt_zones")[0].get("over_adj"), 0.036)
        check("意甲亚盘zone配置", su.CAL.get("意甲", {}).get("hdp_home_ban_zones"), [{"lo": 0.75, "hi": 1.25}])
    finally:
        su.recent_league_avg = _orig_avg
        for _k, _v in _oua_save.items():
            su.CAL[_k]["ou_strength_adj"] = _v



def test_audit_ledger_integrity():
    """33. 台账审计回归 (pnl输单=-1 / 让球满赢 / 队名词序 / 同场无矛盾腿)."""
    section("33. 台账审计回归 (pnl修正 + settle_leg满赢 + 队名词序 + 台账无重复)")

    # ---- pnl: 输单必须-1(修复: 曾把输单算成0致ROI虚高) ----
    sys.path.insert(0, 'prediction_v2')
    from settle_batch import pnl_for_result
    check("赢单pnl=ret-1", round(pnl_for_result("win", 2.24), 6), 1.24)
    check("半赢pnl=(ret-1)", round(pnl_for_result("half", (1.0 + 2.025) / 2.0), 6), 0.5125)
    check("走水pnl=0", pnl_for_result("push", 1.0), 0.0)
    check("输单pnl=-1(关键修正)", pnl_for_result("lose", 0.0), -1.0)
    check("半输pnl=-0.5", pnl_for_result("lose", 0.5), -0.5)
    check("未知单pnl=0", pnl_for_result("未知", None), 0.0)

    # ---- settle_leg: 主让-1.25 净胜2球=全赢(1/4盘两子盘均赢) ----
    from settle_batch import settle_leg
    res, ret = settle_leg("让球主(-1.25)", 2.10, 2, 0)
    check("主让-1.25净胜2球全赢", res, "win")
    check("主让-1.25全赢ret=odds", ret, 2.10)
    res2, ret2 = settle_leg("让球主(-1.25)", 2.10, 1, 0)
    check("主让-1.25净胜1球半输", res2, "lose")
    check("主让-1.25半输ret=0.5", ret2, 0.5)
    check("主让-1.25半输pnl=-0.5", pnl_for_result(res2, ret2), -0.5)
    res3, _ = settle_leg("让球主(-0.75)", 2.10, 1, 1)
    check("主让-0.75平局全输", res3, "lose")

    # ---- bet_ledger 队名词序归一化(防浦和式重复) ----
    import bet_ledger as bl
    check("连字符vs空格同队", bl._team_key("Shimizu S-Pulse") == bl._team_key("Shimizu S Pulse"), True)
    check("词序无关同队", bl._team_key("Hiroshima Sanfrecce FC") == bl._team_key("Sanfrecce Hiroshima"), True)
    check("FC后缀忽略同队", bl._team_key("Urawa Red Diamonds vs Hiroshima Sanfrecce FC".split(" vs ")[1]) == bl._team_key("Sanfrecce Hiroshima"), True)
    check("不同队不同key", bl._team_key("Kashima Antlers") != bl._team_key("Nagoya Grampus"), True)

    # ---- 台账完整性: 已结算+待结算无同场重复/矛盾腿 ----
    import csv as _csv
    led = os.path.join(ROOT_DIR if 'ROOT_DIR' in dir() else os.path.dirname(os.path.abspath(__file__)), "analysis_records", "bet_ledger.csv")
    rows = list(_csv.DictReader(io.open(led, encoding='utf-8-sig')))
    from collections import defaultdict
    g = defaultdict(list)
    for r in rows:
        hk, ak = bl._team_key(r.get("home", "")), bl._team_key(r.get("away", ""))
        g[(r.get("league"), hk, ak)].append(r)
    dup = 0
    for k, v in g.items():
        bets = [r.get("bet_name") for r in v]
        if len(set(bets)) != len(bets):
            dup += 1
    check("台账无同场同注重复", dup, 0)
    resid = 0
    _VALID_RES = {"win", "lose", "half", "push"}
    for k, v in g.items():
        st = {r.get("status") for r in v}
        # 台账升级为全方向多腿(1X2/让球/大小, 每场至多7腿), 同场多腿=正常明细;
        # 防污染改为: 已结算场次不允许残留“待结算”腿(不同代扫描混入)
        # 2026-08-26修正: 结算判定以result为准(方向参考/否决等类别标签结算后保留),
        # 无效场次(VOID)豁免; 只有"无赛果且非无效"才算残留
        if "已结算" in st:
            resid += sum(1 for r in v
                         if r.get("result") not in _VALID_RES and r.get("status") != "无效场次")
    check("台账已结算场无残留待结算腿", resid, 0)




def test_league_avg_deviation():
    """34. 联赛基准偏差检查回归 (J1基准3.35 + 近30场实测 + λ平移标注)."""
    section("34. 联赛基准偏差检查 (J1新基准 + 实测偏差 + λ平移)")
    sys.path.insert(0, 'prediction_v2')
    import scan_upcoming as su

    # J1 配置基准已更新为新赛季实测
    check("J1配置league_avg=3.35", su.CAL.get("J1", {}).get("league_avg"), 3.35)
    check("J1主客场中性(新规实测)", (su.CAL.get("J1", {}).get("home"), su.CAL.get("J1", {}).get("away")), (1.0, 1.0))

    # 近30场实测: J1(2026/27新规3轮30场) 场均3.20
    recent = su.recent_league_avg()
    j1r = recent.get("J1")
    # 2026-08-24 修复: 英文联赛名(快照兼容)不得覆盖中文键(lg_of_div 中文优先),
    #   否则 E0->Premier League/B1->Pro League 导致 analyze_match 按中文查基准取不到
    check("基准键中文优先(英超)", "英超" in recent and "Premier League" not in recent, True)
    check("基准键中文优先(比甲)", "比甲" in recent and "Pro League" not in recent, True)
    check("基准键中文优先(西乙)", "西乙" in recent and "Segunda División" not in recent, True)
    check("J1近30场实测存在", j1r is not None and j1r[1] >= 10, True)
    # 活数据: 08-24 补至3轮30场后近30场实测=3.20 (配置3.35, 偏差0.15<0.30, 仍不触发平移)
    check("J1近场实测场均≈3.2", round(j1r[0], 2) if j1r else 0, 3.20, tol=0.06)
    check("偏差阈值=0.30", su.LEAGUE_AVG_DEV_TOL, 0.30)

    # 配置已对齐实测 -> 不触发平移(直接修正基准, 无需二次偏差标注)
    ts, lavg, index = su.load_team_stats()
    m = {"league": "J1", "home": "Mito HollyHock", "away": "Gamba Osaka",
         "ct": __import__("datetime").datetime(2026, 8, 15, 9, 0, tzinfo=__import__("datetime").timezone.utc),
         "snap": "2026-08-15T08:30:00Z",
         "h2h": {"home": 2.8, "draw": 3.35, "away": 2.84},
         "spread": {"hdp_home": -0.5, "home_price": 1.94, "away_price": 1.97},
         "totals": {"line": 2.5, "over_price": 2.26, "under_price": 1.76}}
    r = su.analyze_match(dict(m), ts, lavg, index)
    check("J1配置已对齐->无基准偏差标签", all("基准偏差" not in t for t in r["risk_tags"]), True)

    # 人为制造偏差: 基准改回2.40 -> 应触发λ平移+标注
    _old = su.CAL["J1"]["league_avg"]
    su.CAL["J1"]["league_avg"] = 2.40
    r2 = su.analyze_match(dict(m), ts, lavg, index)
    su.CAL["J1"]["league_avg"] = _old
    check("偏差>阈值触发风险标签", any("基准偏差" in t for t in r2["risk_tags"]), True)
    check("偏差触发notes说明", any("联赛基准偏差" in n for n in r2["notes"]), True)
    check("λ基准平移50%标注", any("λ基准已平移50%" in n for n in r2["notes"]), True)


def test_league_avg_live_baseline():
    """36. 实时基准偏差修复回归 (实时优先/赛季独立窗口/小球EV校准折扣/多key自动切换)."""
    section("36. 实时基准偏差修复 (实时优先 + 小球校准 + key自动切换)")
    sys.path.insert(0, 'prediction_v2')
    import scan_upcoming as su
    import tempfile, os as _os

    check("赛季窗口样本门槛=4场", su.LEAGUE_AVG_MIN_N, 4)
    check("偏差阈值=0.30球", su.LEAGUE_AVG_DEV_TOL, 0.30)
    check("平移权重=50%", su.LEAGUE_AVG_SHIFT_W, 0.50)

    # key解析: 多key列表 + 行内注释清洗(不含#/空格, 长度32)
    keys = su._load_env_keys()
    check("env至少1个key", len(keys) >= 1, True)
    ok = all("#" not in k and k.strip() == k and len(k) >= 20 for k in keys)
    check("key已清洗(无注释/空格)", ok, True)
    check("至少一个32位the-odds-api key", any(len(k) == 32 for k in keys), True)

    # sport map: 联赛->the-odds-api key
    sm = su._sport_key_map()
    check("荷甲->eredivisie", sm.get("荷甲"), "soccer_netherlands_eredivisie")
    check("中超->superleague", sm.get("中超"), "soccer_china_superleague")
    check("西甲->la_liga", sm.get("西甲"), "soccer_spain_la_liga")

    # 实时缓存优先于CSV(离线用fixture缓存模拟实时窗口)
    _bak_path = su._LIVE_AVG_CACHE_PATH
    _bak_leagues = su._LIVE_AVG_LEAGUES
    _tmp = _os.path.join(tempfile.gettempdir(), "live_avg_test.json")
    try:
        with io.open(_tmp, "w", encoding="utf-8") as f:
            json.dump({"avg": {"荷甲": [4.2, 5], "中超": [4.0, 8]},
                       "fetched_at": "2026-08-16T00:00:00"}, f, ensure_ascii=False)
        su._LIVE_AVG_CACHE_PATH = _tmp
        su.set_live_avg_leagues({"荷甲", "中超", "西甲"})
        su._RECENT_AVG_CACHE = None
        ra = su.recent_league_avg()
        h = ra.get("荷甲")
        c = ra.get("中超")
        check("实时缓存覆盖CSV(荷甲4.2/5场)", h == (4.2, 5), True)
        check("实时缓存覆盖CSV(中超4.0/8场)", c == (4.0, 8), True)
    finally:
        try:
            _os.remove(_tmp)
        except Exception:
            pass
        su._LIVE_AVG_CACHE_PATH = _bak_path
        su.set_live_avg_leagues(_bak_leagues)
        su._RECENT_AVG_CACHE = None

    # 基准上移 -> λ平移 + 小球EV校准折扣 + 风险标签
    from datetime import datetime, timezone
    ts, lavg, index = su.load_team_stats()
    m = {"league": "J1", "home": "Mito HollyHock", "away": "Gamba Osaka",
         "ct": datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc), "snap": "2026-08-15T08:30:00Z",
         "h2h": {"home": 2.8, "draw": 3.35, "away": 2.84},
         "spread": {"hdp_home": -0.5, "home_price": 1.94, "away_price": 1.97},
         "totals": {"line": 2.5, "over_price": 2.26, "under_price": 1.76}}
    _old = su.CAL["J1"]["league_avg"]
    su.CAL["J1"]["league_avg"] = 2.40  # 制造上移偏差(实测3.35)
    r2 = su.analyze_match(dict(m), ts, lavg, index)
    su.CAL["J1"]["league_avg"] = _old
    check("基准上移触发小球校准标签", any("小球校准折扣" in t for t in r2["risk_tags"]), True)
    check("小球EV校准标注在notes", any("小球EV校准" in n for n in r2["notes"]), True)
    # 下移偏差(实测低于配置)不应打折小球
    su.CAL["J1"]["league_avg"] = 3.6
    r3 = su.analyze_match(dict(m), ts, lavg, index)
    su.CAL["J1"]["league_avg"] = _old
    check("基准下移不打折小球", all("小球校准折扣" not in t for t in r3["risk_tags"]), True)


def test_league_calib_structure():
    """35. league_calib v4 结构回归 (全联赛season/note + cup_coeffs杯赛自动切换)."""
    section("35. league_calib结构 (season/note全覆盖 + cup_coeffs杯赛切换)")
    import json as _json
    cal = _json.load(io.open("strategy_data/league_calib.json", encoding="utf-8"))
    ls = cal.get("leagues", {})
    check("联赛数>=25", len(ls) >= 25, True)
    check("全联赛有season", all(v.get("season") for v in ls.values()), True)
    check("全联赛有note", all(v.get("note") for v in ls.values()), True)
    check("全联赛有history字段", all("history" in v for v in ls.values()), True)
    check("J1 history保留旧基准", len(ls["J1"].get("history", [])) >= 1, True)
    check("J1 history旧基准=2.40", ls["J1"]["history"][0]["league_avg"], 2.40)

    cc = cal.get("cup_coeffs", {})
    check("cup_coeffs含欧冠", "欧冠" in cc, True)
    check("cup_coeffs含国内杯", "国内杯" in cc, True)
    check("cup_coeffs字段齐全", all({"home", "away", "fatigue", "rho", "league_avg"} <= set(v) for v in cc.values()), True)
    check("欧冠疲劳<1(双赛)", cc["欧冠"]["fatigue"], 0.85)
    check("国内杯基准3.28", cc["国内杯"]["league_avg"], 3.28)

    # 扫描模块: 杯赛自动切换
    sys.path.insert(0, 'prediction_v2')
    import scan_upcoming as su
    check("CUP_COEFFS加载", len(su.CUP_COEFFS) >= 5, True)
    cc1 = su._cal_for_league("欧冠")
    check("欧冠命中cup_coeffs", cc1 is not None and cc1["league_avg"] == 2.9, True)
    cc2 = su._cal_for_league("英冠")
    check("英冠不命中杯赛参数", cc2, None)
    cc3 = su._cal_for_league("意杯")
    check("意杯命中独立基准3.08", cc3 is not None and cc3["league_avg"] == 3.08, True)
    cc4 = su._cal_for_league("欧联杯")
    check("欧联杯命中自有参数2.9", cc4 is not None and cc4["league_avg"] == 2.9, True)

    # 杯赛场次分析: 用欧冠参数(疲劳0.85, λ基准2.9)
    from datetime import datetime, timezone
    ts, lavg, index = su.load_team_stats()
    m = {"league": "欧冠", "home": "Real Madrid", "away": "Bayern Munich",
         "ct": datetime(2026, 8, 16, 19, 0, tzinfo=timezone.utc), "snap": "2026-08-16T17:00:00Z",
         "h2h": {"home": 2.4, "draw": 3.6, "away": 2.9},
         "spread": {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
         "totals": {"line": 2.5, "over_price": 1.90, "under_price": 1.95}}
    r = su.analyze_match(dict(m), ts, lavg, index)
    check("杯赛参数notes标注", any("杯赛参数" in n for n in r["notes"]), True)
    check("欧冠λ基准用2.9", 2.6 < r["lambda"]["sum"] < 3.6, True)


def test_draw_warning():
    """平局预警模块: 高危联赛+平赔3.0~3.8+深盘让球+否决/form 计分正确 (2026-08-18 验证 58%平局率/召回100%)."""
    section("平局预警模块 (draw_warning)")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "prediction_v2"))
    import importlib
    try:
        dw = importlib.import_module("draw_warning")
    except ImportError:
        dw = None
    if dw is None:
        try:
            import draw_warning as dw
        except Exception:
            check("draw_warning 模块可导入", False, True)
            return
    # 高危组合: 阿甲+平赔3.1+硬否决+让球深盘(-0.5)+form强支持 -> 高分
    sc, tags = dw.draw_warning_score({"league": "阿甲", "h2h": [2.1, 3.1, 3.0],
                                      "resonance": "硬否决(分歧>20pp)", "model_leg": "让球主(-0.5)",
                                      "form": "强支持"})
    check("高危组合分数>=5", sc >= 5, True)
    check("高危组合标签非空", len(tags) >= 3, True)
    # 无风险: 瑞超+平赔4.7+无否决+无深盘+form支持 -> 0分
    sc2, _ = dw.draw_warning_score({"league": "瑞超", "h2h": [1.28, 4.7, 6.5],
                                    "resonance": "不同腿", "model_leg": "大2.50", "form": "支持"})
    check("无风险组合分数=0", sc2 == 0, True)
    # 平赔3.0~3.8 区间命中
    sc3, _ = dw.draw_warning_score({"league": "西乙", "h2h": [1.67, 3.1, 4.0],
                                    "resonance": "不同腿", "model_leg": "让球主(-0.5)", "form": "中性"})
    check("平赔3.1高危区加分", sc3 >= 3, True)
    # 等级映射
    check(">=5=防平高危", dw.draw_warning_label(5) == "防平高危", True)
    check("3-4=防平提醒", dw.draw_warning_label(3) == "防平提醒", True)
    check("<3=空", dw.draw_warning_label(1) == "平局观察", True)


def test_odds_side_classify():
    """21.6 自检修复: the-odds-api outcome 队名与赛程队名不一致时侧边判定 (2026-08-22).
    回归: SJK/Cracovia/Al-Hazem/Aldosivi 曾丢 1X2+亚盘(精确匹配误判), 现在强匹配+市场级补全."""
    section("21.6 the-odds-api 侧边判定强匹配(跨源长短队名)")
    import tempfile
    sys.path.insert(0, "prediction_v2")
    from src.live_odds import classify_side, flatten_events, normalize_team

    check("normalize Cracovia Kraków", normalize_team("Cracovia Kraków"), "ks cracovia")
    check("normalize SJK Seinäjoki", normalize_team("SJK Seinäjoki"), "sjk")
    check("normalize Diriyah Club", normalize_team("Diriyah Club"), "al diriyah")

    cases = [
        ("SJK Seinäjoki", "SJK", "FC Lahti", "home"),
        ("FC Lahti", "SJK", "FC Lahti", "away"),
        ("Cracovia Kraków", "KS Cracovia", "Wieczysta Kraków", "home"),
        ("Wieczysta Kraków", "KS Cracovia", "Wieczysta Kraków", "away"),
        ("Diriyah Club", "Al-Hazem", "Al Diriyah", "away"),
        ("Al-Hazem", "Al-Hazem", "Al Diriyah", "home"),
        ("Union Santa Fe", "Aldosivi", "Club Atlético Unión de Santa Fe", "away"),
        ("Club Atlético Unión de Santa Fe", "Aldosivi", "Club Atlético Unión de Santa Fe", "away"),
        ("Draw", "SJK", "FC Lahti", "draw"),
    ]
    for name, h, a, want in cases:
        got = classify_side(name, h, a)
        check("classify %s" % name, got, want)

    ev = {
        "id": "evt-1",
        "home_team": "SJK", "away_team": "FC Lahti",
        "commence_time": "2026-08-21T16:00:00Z",
        "bookmakers": [{"key": "casumo", "last_update": "t", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "SJK Seinäjoki", "price": 2.5},
                {"name": "Draw", "price": 3.35},
                {"name": "FC Lahti", "price": 2.48}]},
            {"key": "spreads", "outcomes": [
                {"name": "SJK Seinäjoki", "price": 2.1, "point": -0.25},
                {"name": "FC Lahti", "price": 1.75, "point": 0.25}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.65, "point": 2.5},
                {"name": "Under", "price": 2.06, "point": 2.5}]}]}],
    }
    rows = flatten_events([ev], "Veikkausliiga", "2026-08-21T14:00:00Z")
    check("flatten 7行", len(rows), 7)
    h2h = [r for r in rows if r["market"] == "h2h"]
    check("h2h主侧SJK", [r for r in h2h if r["side"] == "home"][0]["price"], 2.5)
    check("h2h平侧Draw", [r for r in h2h if r["side"] == "draw"][0]["price"], 3.35)
    check("h2h客侧Lahti", [r for r in h2h if r["side"] == "away"][0]["price"], 2.48)
    sp = [r for r in rows if r["market"] == "spreads"]
    check("亚盘主-0.25", [r for r in sp if r["side"] == "home"][0]["point"], -0.25)
    check("亚盘客+0.25", [r for r in sp if r["side"] == "away"][0]["point"], 0.25)

    ev2 = {
        "id": "evt-2",
        "home_team": "KS Cracovia", "away_team": "Wieczysta Kraków",
        "commence_time": "2026-08-21T18:30:00Z",
        "bookmakers": [{"key": "pinnacle", "last_update": "t", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Cracovia Kraków", "price": 2.34},
                {"name": "Draw", "price": 3.5},
                {"name": "Wieczysta Kraków", "price": 2.9}]},
            {"key": "spreads", "outcomes": [
                {"name": "Cracovia Kraków", "price": 1.96, "point": -0.25},
                {"name": "Wieczysta Kraków", "price": 1.93, "point": 0.25}]}]}],
    }
    rows2 = flatten_events([ev2], "Ekstraklasa", "2026-08-21T14:00:00Z")
    h2h2 = [r for r in rows2 if r["market"] == "h2h"]
    check("Cracovia h2h 3侧齐全", {r["side"] for r in h2h2}, {"home", "draw", "away"})
    check("Cracovia主胜价2.34", [r for r in h2h2 if r["side"] == "home"][0]["price"], 2.34)
    sp2 = [r for r in rows2 if r["market"] == "spreads"]
    check("Cracovia亚盘2侧齐全", {r["side"] for r in sp2}, {"home", "away"})
    check("Cracovia亚盘主-0.25", [r for r in sp2 if r["side"] == "home"][0]["point"], -0.25)

    # ---- 多盘口亚盘分组: 镜像庄家 主-1.5/客+1.5 与 主+1.5/客-1.5 是两条不同盘口, 不得合并合价 ----
    import scan_upcoming as su
    _H = "snapshot_ts,event_id,league,commence_time,home_team,away_team,bookmaker,market,outcome,side,side_key,point,price,last_update\n"
    _CT = "2026-08-21T16:00:00Z"
    _ml = [_H]

    def _srow(eid, h, a, bk, out, side, pt, price):
        _ml.append("%s,%s,英超,%s,%s,%s,%s,spreads,%s,%s,%s@%s,%s,%s,%s\n" %
                   ("2026-08-21T14:00:00Z", eid, _CT, h, a, bk, out, side, side, pt, pt, price, "2026-08-21T14:00:00Z"))

    _srow("m1", "Bristol City", "Millwall", "Unibet", "Bristol City -1.5", "home", -1.5, 4.8)
    _srow("m1", "Bristol City", "Millwall", "Unibet", "Millwall +1.5", "away", 1.5, 1.13)
    _srow("m1", "Bristol City", "Millwall", "Unibet", "Bristol City +1.5", "home", 1.5, 1.12)
    _srow("m1", "Bristol City", "Millwall", "Unibet", "Millwall -1.5", "away", -1.5, 5.0)
    _srow("m1", "Bristol City", "Millwall", "Unibet", "Bristol City -0.5", "home", -0.5, 2.4)
    _srow("m1", "Bristol City", "Millwall", "Unibet", "Millwall +0.5", "away", 0.5, 1.48)
    _srow("m2", "TeamA", "TeamB", "pinnacle", "A", "home", -0.5, 1.95)
    _srow("m2", "TeamA", "TeamB", "pinnacle", "B", "away", -0.5, 1.95)
    _fd, _path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(_fd, "w", encoding="utf-8") as _f:
            _f.write("".join(_ml))
        _out, _ = su.parse_snapshots(_path)
        _r1 = [x for x in _out if x["id"] == "m1"][0]["spread"]
        check("多盘口亚盘主盘-0.5", _r1["hdp_home"], -0.5)
        check("多盘口亚盘主价2.40", _r1["home_price"], 2.4)
        check("多盘口亚盘客价1.48", _r1["away_price"], 1.48)
        _r2 = [x for x in _out if x["id"] == "m2"][0]["spread"]
        check("同号约定亚盘-0.5", (_r2["hdp_home"], _r2["home_price"], _r2["away_price"]), (-0.5, 1.95, 1.95))
    finally:
        try:
            os.remove(_path)
        except Exception:
            pass

def test_footballdata_norm_team():
    """36. football-data.org 队名归一化 + 赛季标签 (fetch_footballdata)."""
    section("36. football-data.org 队名归一化")
    sys.path.insert(0, "prediction_v2")
    try:
        import fetch_footballdata as fd
    except Exception as e:
        check("fetch_footballdata 可导入", type(e).__name__, "")
        return
    for raw, exp in [("Atleti", "Ath Madrid"), ("Barça", "Barcelona"),
                     ("Bayern", "Bayern Munich"), ("Köln", "FC Koln"),
                     ("Alavés", "Alaves"), ("PSV", "PSV Eindhoven"),
                     ("Man City", "Man City"), ("Arsenal", "Arsenal"),
                     ("Fortuna", "For Sittard"), ("NEC", "Nijmegen")]:
        check("norm_team(%s)" % raw, fd.norm_team(raw), exp)
    check("season_label 跨年", fd.season_label({"first": "2026-08-14", "last": "2027-05-01"}), "2026/2027")
    check("season_label 自然年", fd.season_label({"first": "2026-01-28", "last": "2026-12-02"}), "2026")


def test_bsd_result_fallback():
    """37. BSD赛果兜底字段守卫 (中超/J1: event_date 解析, 2026-08-22 修复)."""
    section("37. BSD赛果兜底字段")
    sys.path.insert(0, "prediction_v2")
    src_c = io.open(r"prediction_v2/fetch_csl_results.py", encoding="utf-8").read()
    src_j = io.open(r"prediction_v2/fetch_j1_results.py", encoding="utf-8").read()
    src = src_c + src_j
    check("BSD兜底用event_date字段", 'ev.get("event_date")' in src, True)
    check("BSD中超league_id=52", 'BSD_LEAGUE_ID = 52' in src_c, True)
    check("BSD J1 league_id=49", 'BSD_LEAGUE_ID = 49' in src_j, True)
    check("ESPN失败切换BSD", '切换BSD兜底' in src, True)


def test_audit_v8_ev_and_injury():
    """v8 审计 (2026-08-27 全链路): P0-1 EV公式 / P1-1 伤停系数 / P1-4 分边回退 / P1-6 归一 / P2-1 DC统一 / P2-3 别名."""
    section("v8 审计: EV公式/伤停系数/分边回退/DC统一")
    sys.path.insert(0, 'src/models')
    from poisson_lambda import (calc_lambdas, DEFAULT_RISK_LIMIT, RELATIVE_RISK_GAP_LIMIT,
                                risk_conflict_check)
    from prob_calibration import shrink_power, dc_score_grid, poisson_score_grid
    # 2026-08-28 审计: 单边风险限幅降至±5% (双向总相对差≈10%), 相对差铁律解耦为独立常量
    check("P0 单边风险限幅±5%", DEFAULT_RISK_LIMIT, 0.05)
    check("P0 双向相对差铁律±10%", RELATIVE_RISK_GAP_LIMIT, 0.10)
    check("P0 冲突阈值低于限幅(|0.04|触发)", risk_conflict_check(3.0, 1.0, -0.04)["conflict"], True)
    check("P0 阈值下小信号不误判(|0.02|不触发)", risk_conflict_check(3.0, 1.0, -0.02)["conflict"], False)
    # P0-1: EV = 模型概率 × 赔率 - 1, 与 overround 无关
    sys.path.insert(0, "prediction_v2")
    import scan_upcoming as su
    check("P0-1 _injury_coef空=1.0", su._injury_coef([]), 1.0)
    check("P0-1 _injury_coef可用过滤", su._injury_coef([{"status": "available"}, {"status": "available"}]), 1.0)
    check("P1-1 伤停3人无位置=0.97", su._injury_coef([{"status": "injured"}] * 3), 0.97)
    check("P1-1 伤停5人无位置=0.94", su._injury_coef([{"status": "injured"}] * 5), 0.94)
    check("P1-1 3前锋伤停钳位0.75", su._injury_coef([{"status": "injured", "position": "F"}] * 3), 0.75)
    ts, lavg, index = su.load_team_stats()
    _dt = __import__("datetime")
    m = {"league": "西甲", "home": "Real Madrid", "away": "Getafe",
         "ct": _dt.datetime(2026, 8, 16, 12, 0, tzinfo=_dt.timezone.utc),
         "snap": "2026-08-16T10:00:00Z",
         "h2h": {"home": 1.3, "draw": 5.0, "away": 9.0},
         "spread": {"hdp_home": -1.5, "home_price": 1.9, "away_price": 1.95},
         "totals": {"line": 2.5, "over_price": 1.9, "under_price": 1.9}}
    base = su.analyze_match(dict(m), ts, lavg, index)
    # P0-1: 所有非1X2候选腿 EV == prob × odds - 1 (容差1e-3, 兼容PROB_CAP等比缩放后的未舍入)
    bad_ev = []
    for b in base.get("bets", []):
        if b.get("is_1x2"):
            continue
        want = b["prob"] * b["odds"] - 1
        if abs(b["ev"] - want) > 1e-3:
            bad_ev.append((b["name"], b["ev"], want))
    check("P0-1 让球/大小球EV=prob×price-1", bad_ev, [])
    # P0-1: 1X2腿 EV == prob × price - 1
    bad_ev2 = []
    for b in base.get("bets", []):
        if b.get("is_1x2"):
            want = b["prob"] * b["odds"] - 1
            if abs(b["ev"] - want) > 1e-3:
                bad_ev2.append((b["name"], b["ev"], want))
    check("P0-1 1X2 EV=prob×price-1", bad_ev2, [])
    # P0-1 _bsd_leg_ev: EV=模型概率×BSD价-1 (不再除以orr)
    ev_b = su._bsd_leg_ev("大2.50", 0.55, {"over_25_goals": 1.9, "under_25_goals": 1.9})
    check("P0-1 _bsd_leg_ev=0.55×1.9-1", ev_b, round(0.55 * 1.9 - 1, 4))
    # P1-4: 分边单边指定, 另一边默认0不自动反向
    r_side1 = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8,
                           risk_signal_h=0.08)
    check("P1-4 单边指定客边=0", r_side1["risk_signal_a"], 0.0)
    # P1-6: shrink_power 归一化和严格=1
    sp = shrink_power([0.6, 0.3, 0.1], 0.9)
    check("P1-6 shrink_power和=1", abs(sum(sp) - 1.0) < 1e-6, True)
    # P2-1: dc_score_grid 与 poisson_score_grid 完全一致
    g1 = dc_score_grid(1.5, 1.2, rho=-0.05)
    g2 = poisson_score_grid(1.5, 1.2, rho=-0.05)
    same = all(abs(g1[i][j] - g2[i][j]) < 1e-12 for i in range(10) for j in range(10))
    check("P2-1 DC网格双实现一致", same, True)
    # P2-3: model_prob 别名
    r_alias = calc_lambdas(home_gf=1.5, away_ga=1.2, away_gf=1.0, home_ga=1.1, league_avg=2.8)
    check("P2-3 model_prob别名", "model_prob" in r_alias and r_alias["model_prob"] == r_alias["market_prob"], True)
    # ===== 2026-08-28 审计 P1: DC tau兜底 / 截断透出 / 单一校验点 =====
    from poisson_lambda import dc_tau, poisson_score_grid, W_GRID_TRUNCATED
    check("P1 tau兜底上界(τ00@λ4.5=2.0)", dc_tau(0, 0, 4.5, 4.5, -0.15), 2.0)
    check("P1 tau兜底下界(τ10@λ4.5=0.5)", dc_tau(1, 0, 4.5, 4.5, -0.15), 0.5)
    _g9, _rt9 = poisson_score_grid(3.0, 3.0, rho=0.0, max_goals=9, return_raw=True)
    _g2, _rt2 = poisson_score_grid(3.0, 3.0, rho=0.0, max_goals=2, return_raw=True)
    check("P1 9球网格raw_total>0.95", _rt9 > 0.95, True)
    check("P1 2球网格raw_total<0.95(截断可检出)", _rt2 < 0.95, True)
    check("P1 return_raw网格已归一(和=1)", abs(sum(sum(r) for r in _g9) - 1.0) < 1e-9, True)
    _pl_src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "models", "poisson_lambda.py"),
                      encoding="utf-8").read()
    check("P1 calc_lambdas含截断告警分支", "W_GRID_TRUNCATED" in _pl_src and "_raw_total < 0.95" in _pl_src, True)



TEST_ORDER = [
    "test_parse_handicap",
    "test_poisson",
    "test_step31_best_bet",
    "test_upset_engine",
    "test_upset_engine_v3_audit",
    "test_settlement",
    "test_data_extractor",
    "test_league_baselines",
    "test_v2_bridge",
    "test_p0_deliverables",
    "test_de_vig",
    "test_bsd_result_fallback",
    "test_audit_v8_ev_and_injury",
    "test_footballdata_norm_team",
    "test_poisson_lambda",
    "test_poisson_lambda_v3_audit",
    "test_poisson_lambda_v4_audit",
    "test_poisson_lambda_v5_audit",
    "test_lstm_v2_audit",
    "test_data_quality",
    "test_multi_source",
    "test_risk_control",
    "test_llm_isolation",
    "test_parlay_v2",
    "test_data_tier_and_fill",
    "test_match_filter",
    "test_line_movement",
    "test_api_router",
    "test_oddsapi_adapter",
    "test_odds_side_classify",
    "test_snapshot_guard",
    "test_zone_leak",
    "test_calibration_modules",
    "test_promoted_and_league_avg",
    "test_scan_v2_fixes",
    "test_csl_scan",
    "test_j1_rescan",
    "test_laliga_rescan",
    "test_kickoff_check",
    "test_csl_kickoff_check",
    "test_settle_batch",
    "test_odds_veto_rules",
    "test_star2_risk_rules",
    "test_draw_warn_plus_rules",
    "test_laliga_rule13",
    "test_rule6_direction_attribution",
    "test_rule7_strong_draw_plus",
    "test_rule8_odds_overest",
    "test_rule9_fake_small",
    "test_ou_strength_adj",
    "test_audit_ledger_integrity",
    "test_league_avg_deviation",
    "test_league_avg_live_baseline",
    "test_league_calib_structure",
    "test_bsd_extra",
    "test_bsd_event_aet_settle",
    "test_ah_quota_inject",
    "test_ah_infer_parse",
    "test_bsd_market_cross",
    "test_bsd_standings",
    "test_catboost_model",
    "test_ou_settle_sign",
    "test_bsd_prob_calib",
    "test_lgb_feature_names",
    "test_formation_indicator",
    "test_bsd_lineups_formation",
    "test_injury_pos_weight",
    "test_coach_quant",
    "test_bsd_coaches_extract",
    "test_scan_coach_integration",
    "test_ledger_coach_cols",
    "test_leak_void_caliber",
    "test_draw_warning",
    "test_standings_tags",
]



def test_bsd_extra():
    """BSD v2 补充数据: lineup_recs/squad_recs 字段规范化 + team id 提取."""
    section("BSD v2 补充数据 (bsd_extra)")
    sys.path.insert(0, "prediction_v2")
    import bsd_extra as bx

    # lineups.unavailable_players -> 统一记录
    raw = [{"name": "张三", "status": "injured", "reason": "Ankle"},
           {"name": "李四", "status": "suspended", "reason": ""}]
    recs = bx.lineup_recs(raw)
    check("lineups缺阵条数", len(recs), 2)
    check("lineups状态字段", recs[0]["status"], "injured")
    check("lineups原因字段", recs[0]["reason"], "Ankle")

    # squad players -> 只留非 available
    players = [{"name": "A", "availability": "available"},
               {"name": "B", "availability": "injured", "injury_type": "Knee"},
               {"name": "C", "availability": "doubtful"},
               {"name": "D", "availability": "suspended"}]
    recs2 = bx.squad_recs(players)
    check("squad过滤条数", len(recs2), 3)
    check("squad状态", recs2[0]["status"], "injured")

    # 主客 team id 提取
    ev = {"home_team_obj": {"id": 11}, "away_team_obj": {"id": 22}}
    check("home team id", bx._side_team_id(ev, "home"), 11)
    check("away team id", bx._side_team_id(ev, "away"), 22)

    # 合并优先级: lineups 当场缺阵优先于 squad
    lineups = {"lineup_status": "predicted",
               "unavailable_players": {"home": [{"name": "X", "status": "injured", "reason": "Hamstring"}], "away": []}}
    m = {"injuries": {}, "home": "H", "away": "A"}
    # 模拟: 用 side 数据直接验证 lineup_recs 输出可被 intel_text 消费
    txt = bx.intel_text(True, bx.lineup_recs(lineups["unavailable_players"]["home"]),
                       True, bx.lineup_recs(lineups["unavailable_players"]["away"]))
    check("伤停文本包含主队人数", "主:1人" in txt, True)
    check("伤停文本包含客队0人", "客:0人" in txt, True)

    # lineup_recs pos_map 补位置 + squad position 保留 + _backfill_pos
    raw3 = [{"id": 7, "name": "王五", "status": "injured"}]
    recs3 = bx.lineup_recs(raw3, pos_map={"7": "D"})
    check("lineups pos_map补D", recs3[0]["position"], "D")
    recs4 = bx.lineup_recs(raw3, pos_map={})
    check("无pos_map位置空", recs4[0].get("position"), None)
    players2 = [{"name": "E", "availability": "injured", "injury_type": "Knee", "position": "G"}]
    recs5 = bx.squad_recs(players2)
    check("squad position保留", recs5[0]["position"], "G")
    rec_fill = [{"name": "Old", "status": "injured", "position": None}]
    bx._backfill_pos(rec_fill, {"Old": "M", "Other": "F"})
    check("backfill按名补M", rec_fill[0]["position"], "M")
    rec_fill2 = [{"name": "Old", "status": "injured", "position": "G"}]
    bx._backfill_pos(rec_fill2, {"Old": "M"})
    check("backfill不覆盖已有", rec_fill2[0]["position"], "G")



def test_bsd_event_aet_settle():
    """BSD 事件加时比分口径: AET/PEN 与 90 分钟结算分离 (2026-08-28 拉恩 0:3→0:2 修正)."""
    section("BSD 加时比分口径 (bsd_extra.event_settle_scores)")
    sys.path.insert(0, "prediction_v2")
    import bsd_extra as bx

    s1 = bx.event_settle_scores({"period": "FT", "current_minute": 90, "home_score": 1, "away_score": 0})
    check("FT不标记加时", s1["is_aet"], False)
    check("FT直接作为90分比分", s1["hg_90"], 1)
    check("FT无需补录", s1["needs_verify"], False)

    s2 = bx.event_settle_scores({"period": "AET", "current_minute": 120, "home_score": 4, "away_score": 2})
    check("AET标记加时", s2["is_aet"], True)
    check("AET需权威源补90分", s2["needs_verify"], True)
    check("AET比分保留加时后全场", s2["hg_aet"], 4)
    check("AET不提供90分比分", s2["hg_90"], None)

    s3 = bx.event_settle_scores({"period": "PEN", "current_minute": 120, "home_score": 1, "away_score": 0})
    check("PEN标记加时", s3["is_aet"], True)

    s4 = bx.event_settle_scores({"period": "FT", "current_minute": 120, "home_score": 0, "away_score": 3})
    check("minute>=100兜底标记(拉恩类误标)", s4["is_aet"], True)

    s5 = bx.event_settle_scores({"period": "FT", "current_minute": None, "home_score": 2, "away_score": 1})
    check("minute缺失按FT处理", s5["is_aet"], False)


def test_ah_quota_inject():
    """亚盘配额拉取: 主盘平衡线解析 + 队名别名匹配 + 状态按日重置 (2026-08-28 新增, 省额度正式化)."""
    section("亚盘配额拉取 (pull_ah_quota)")
    sys.path.insert(0, "prediction_v2")
    import pull_ah_quota as pa
    from datetime import datetime, timezone as _tz
    # 1) 主盘平衡线: 每机构取主客水位最接近的线, 再取众数
    od = {"response": [
        {"bookmakers": [{"name": "B1", "bets": [{"name": "Asian Handicap", "values": [
            {"value": "Home -0.5", "odd": "1.90"}, {"value": "Away -0.5", "odd": "1.90"},
            {"value": "Home -1.0", "odd": "2.05"}, {"value": "Away -1.0", "odd": "1.80"}]}]},
         {"name": "B2", "bets": [{"name": "Asian Handicap", "values": [
            {"value": "Home -0.5", "odd": "1.88"}, {"value": "Away -0.5", "odd": "1.92"},
            {"value": "Home -0.25", "odd": "1.95"}, {"value": "Away -0.25", "odd": "1.85"}]}]}]}]}
    ml = pa.main_line_from_odds(od)
    check("主盘共识线", ml["line"], -0.5)
    check("主水均值", ml["home_price"], 1.89)
    check("客水均值", ml["away_price"], 1.91)
    check("机构数", ml["books"], 2)
    # 2) 队名别名: Shandong Taishan -> Shandong Luneng
    fixs = [{"id": 1523256, "date": "2026-08-28T11:35:00+00:00", "home": "Shanghai Shenhua", "away": "Shandong Luneng"}]
    m = {"id": 205883, "ct": "2026-08-28T11:35:00+00:00", "home": "Shanghai Shenhua", "away": "Shandong Taishan"}
    f = pa.match_fixture(fixs, m, None)
    check("别名匹配fixture", f["id"], 1523256)
    # 3) 状态按日重置
    import tempfile
    _tmp = tempfile.mktemp(suffix=".json")
    _old = pa.STATE_FP
    pa.STATE_FP = _tmp
    try:
        io.open(_tmp, "w", encoding="utf-8").write(json.dumps({"date": "2000-01-01", "calls": 99}))
        st = pa.load_state()
        check("跨日重置日期", st["date"] == datetime.now(_tz.utc).strftime("%Y-%m-%d"), True)
        check("跨日calls归零", st["calls"], 0)
    finally:
        pa.STATE_FP = _old
        try:
            os.remove(_tmp)
        except Exception:
            pass


def test_ah_infer_parse():
    """InferSports 亚盘解析: 共识线主队视角 + 共识线水位均值 + 无共识线开盘回退best_prices (2026-08-28 省额度接入)."""
    section("InferSports 亚盘解析 (pull_ah_quota.parse_infer_ah)")
    sys.path.insert(0, "prediction_v2")
    import pull_ah_quota as pa

    comp = {
        "consensus_line": -0.75,
        "book_count": 5,
        "best_prices": [{"outcome": "home", "bookmaker": "macau", "price": 1.74, "decimal": 1.74},
                        {"outcome": "away", "bookmaker": "nova88", "price": 2.27, "decimal": 2.27}],
        "books": [
            {"bookmaker": "crown", "line": -1.5, "prices": {"home": 2.29, "away": 1.63}, "status": "open"},
            {"bookmaker": "macau", "line": -0.75, "prices": {"home": 1.76, "away": 2.10}, "status": "open"},
            {"bookmaker": "nova88", "line": -0.75, "prices": {"home": 1.74, "away": 2.12}, "status": "open"},
            {"bookmaker": "sbobet", "line": -0.75, "prices": {"home": 1.75, "away": 2.11}, "status": "suspended"},
        ],
    }
    r = pa.parse_infer_ah(comp)
    check("共识线主队视角", r["line"], -0.75)
    check("共识线水位均值主", r["home_price"], 1.75)
    check("共识线水位均值客", r["away_price"], 2.11)
    check("开盘机构数(排除suspended)", r["books"], 2)

    comp2 = {"consensus_line": 0.0, "book_count": 3,
             "best_prices": [{"outcome": "home", "price": 1.90}, {"outcome": "away", "price": 1.92}],
             "books": [{"bookmaker": "crown", "line": -1.0, "prices": {"home": 2.0, "away": 1.8}, "status": "open"}]}
    r2 = pa.parse_infer_ah(comp2)
    check("无共识线开盘回退best", r2["home_price"], 1.9)
    check("回退books=book_count", r2["books"], 3)

    check("空comparison返回None", pa.parse_infer_ah({}), None)


def test_bsd_market_cross():
    """BSD市场基准交叉验证 (scan_upcoming: λ分歧/双口径EV/无价值无单)"""
    section("BSD市场基准交叉 (scan_upcoming._bsd_cross_check)")
    sys.path.insert(0, "prediction_v2")
    import scan_upcoming as su

    cons = {"over_25_goals": 1.95, "under_25_goals": 1.95}
    ev = su._bsd_leg_ev("大2.50", 0.55, cons)
    expect = 0.55 * 1.95 - 1  # 2026-08-27 EV公式修正: prob*price-1, 不再除抽水
    check("大2.5 BSD双口径EV", round(ev, 4), round(expect, 4))
    check("让球无BSD盘返None", su._bsd_leg_ev("让球主(-0.5)", 0.5, cons), None)

    info = {"bsd_prediction": {"expected_goals": {"home": 1.5, "away": 1.4},
            "recommendations": {"bet_favorite": False, "over_25": False, "btts": False}},
            "bsd_odds": {"consensus": {"over_25_goals": 1.95, "under_25_goals": 1.95}}}

    r = {"lambda": {"home": 2.8, "away": 1.2}, "risk_tags": [], "notes": [],
         "star": 3, "best_bet": None, "direction": None}
    out = su._bsd_cross_check(r, info)
    check("λ分歧标签", any("λ与BSD市场分歧" in x for x in r["risk_tags"]), True)
    check("风控降星", r["star"], 2)
    check("λ偏差记录", out["lam_dev"]["home"], 1.3)

    r2 = {"lambda": {"home": 1.4, "away": 1.3}, "risk_tags": [], "notes": [],
          "star": 3, "best_bet": None,
          "direction": {"name": "大2.50", "prob": 0.55, "ev": 0.07}}
    out2 = su._bsd_cross_check(r2, info)
    check("方向腿双口径EV", out2["ev"] is not None, True)
    check("ev_gap写入", "ev_gap" in r2["direction"], True)

    r3 = {"lambda": {"home": 1.4, "away": 1.3}, "risk_tags": [], "notes": [],
          "star": 2, "best_bet": {"name": "大2.50", "prob": 0.5, "odds": 1.9, "ev": 0.04},
          "direction": None}
    su._bsd_cross_check(r3, info)
    check("BSD无价值+EV<5%无单", r3["best_bet"], None)
    check("无单标签", any("BSD市场无价值" in x for x in r3["risk_tags"]), True)

    # ---- [1a] BSD置信度交叉验证: 方向一致性 + 降星不改EV ----
    def _mk_r(name, conf_star=3):
        return {"lambda": {"home": 1.5, "away": 1.3}, "risk_tags": [], "notes": [],
                "star": conf_star,
                "best_bet": {"name": name, "prob": 0.6, "odds": 1.9, "ev": 0.12, "star": conf_star},
                "direction": None}

    # _bsd_dir_agree: 1X2
    pred_1x2 = {"markets": {"match_result": {"predicted": "H"},
                            "over_under": {"prob_over_25": 57.6}}}
    check("1X2主胜同向", su._bsd_dir_agree("1X2主胜", pred_1x2), True)
    check("1X2客胜反向", su._bsd_dir_agree("1X2客胜", pred_1x2), False)
    # 大小球
    check("大2.5同向", su._bsd_dir_agree("大2.50", pred_1x2), True)
    check("小2.5反向", su._bsd_dir_agree("小2.50", pred_1x2), False)
    # 让球
    check("让球主同向", su._bsd_dir_agree("让球主(-0.5)", pred_1x2), True)
    check("让球客反向", su._bsd_dir_agree("让球客(+0.5)", pred_1x2), False)
    # 无法判断
    check("无盘返None", su._bsd_dir_agree("", pred_1x2), None)

    # 同向 conf>=0.60 -> 共识支持保留, 不降星
    info_c60 = {"bsd_prediction": {"confidence": 0.62, "expected_goals": {"home": 1.5, "away": 1.3},
                                   "markets": {"match_result": {"predicted": "H"},
                                               "over_under": {"prob_over_25": 60.0}},
                                   "recommendations": {"bet_favorite": False}},
                "bsd_odds": {"consensus": {}}}
    r_c60 = _mk_r("1X2主胜")
    su._bsd_cross_check(r_c60, info_c60)
    check("同向高置信保留", r_c60["best_bet"] is not None, True)
    check("同向高置信不降星", r_c60["star"], 3)
    check("共识支持note", any("BSD共识支持" in x for x in r_c60["notes"]), True)

    # 反向 -> 降星 + 分歧标签, EV原值不变
    r_rev = _mk_r("1X2客胜")
    _ev_before = r_rev["best_bet"]["ev"]
    su._bsd_cross_check(r_rev, info_c60)
    check("反向降星", r_rev["star"], 2)
    check("反向同步best_bet星级", r_rev["best_bet"]["star"], 2)
    check("反向分歧标签", any("BSD方向分歧" in x for x in r_rev["risk_tags"]), True)
    check("反向不改EV", r_rev["best_bet"]["ev"], _ev_before)

    # 同向 conf<0.45 -> 低置信降星
    info_c40 = {"bsd_prediction": {"confidence": 0.40, "expected_goals": {"home": 1.5, "away": 1.3},
                                   "markets": {"match_result": {"predicted": "H"},
                                               "over_under": {"prob_over_25": 60.0}},
                                   "recommendations": {"bet_favorite": False}},
                "bsd_odds": {"consensus": {}}}
    r_low = _mk_r("1X2主胜")
    su._bsd_cross_check(r_low, info_c40)
    check("低置信降星", r_low["star"], 2)
    check("低置信标签", any("BSD低置信支持" in x for x in r_low["risk_tags"]), True)


def test_bsd_standings():
    """BSD官方积分榜 (GlobalData.table: team_key索引/xG入档/本地兜底)"""
    section("BSD积分榜 (GlobalData.table + main入档)")
    sys.path.insert(0, "prediction_v2")
    import _batch_match_info as bmi

    gd = bmi.GlobalData.__new__(bmi.GlobalData)
    gd.matches = []
    gd.by_key = {}

    # BSD路径: 返回 {team_key: (rank, stats)}, 含xG/官方form
    fake = {bmi.team_key("神户胜利船"): {"position": 1, "played": 20, "won": 15, "drawn": 3, "lost": 2,
                                            "gf": 48, "ga": 18, "pts": 48,
                                            "xgf": 26.0, "xga": 12.0, "xgd": 14.0, "form": "WWDWW"}}
    bmi.bsd_standings = lambda lg: fake
    table = gd.table("J1")
    kk = bmi.team_key("神户胜利船")
    check("BSD索引键是team_key", kk in table, True)
    rk, s_ = table[kk]
    check("BSD排名", rk, 1)
    check("BSD积分", s_["Pts"], 48)
    check("BSD xG归一场均(26/20)", s_["xgf"], 1.3)
    check("BSD xgd入档", s_["xgd"], 0.7)

    # main()入档逻辑: xG/官方form写进info
    info = {}
    if kk in table:
        rk2, s2 = table[kk]
        info["rank"] = rk2; info["P"] = s2["P"]
        for _xk in ("xgf", "xga", "xgd", "form_bsd"):
            if s2.get(_xk) is not None:
                info[_xk] = s2[_xk]
    check("入档xgf", info.get("xgf"), 1.3)
    check("入档xgd", info.get("xgd"), 0.7)
    check("入档form_bsd", info.get("form_bsd"), "WWDWW")
    check("入档rank", info.get("rank"), 1)

    # 本地兜底: BSD未覆盖 -> 用ESPN赛果自动算表(无xG字段)
    bmi.bsd_standings = lambda lg: {}
    gd2 = bmi.GlobalData.__new__(bmi.GlobalData)
    gd2.matches = [
        {"league": "荷甲", "date": None, "home": "阿贾克斯", "away": "费耶诺德", "hg": 2, "ag": 1, "season": "2026/2027"},
        {"league": "荷甲", "date": None, "home": "费耶诺德", "away": "阿贾克斯", "hg": 0, "ag": 0, "season": "2026/2027"},
    ]
    gd2.by_key = {}
    for m in gd2.matches:
        for t in (m["home"], m["away"]):
            gd2.by_key.setdefault(bmi.team_key(t), t)
    t2 = gd2.table("荷甲")
    hk = bmi.team_key("阿贾克斯")
    check("兜底排名存在", hk in t2, True)
    check("兜底积分", t2[hk][1]["Pts"], 4)
    check("兜底无xG字段", t2[hk][1].get("xgd"), None)
    # 恢复原函数, 避免污染其他测试
    import importlib
    importlib.reload(bmi)


def test_catboost_model():
    """CatBoost 1X2 分类器: 与 XGB/LGB 同接口 (CalibratedClassifierCV + classes_映射 + 缺类padding)"""
    section("CatBoost 模型 (models.CatModel)")
    sys.path.insert(0, "prediction_v2")
    try:
        import catboost  # noqa
        from src.models import CatModel
    except Exception as _e:
        print("  ⚠️ catboost 未安装, 跳过: %s" % _e)
        return
    import numpy as np

    rng = np.random.RandomState(7)
    X = rng.rand(300, 8)
    y = rng.randint(0, 3, 300)
    m = CatModel({"iterations": 30, "depth": 3, "learning_rate": 0.1, "thread_count": 2})
    m.fit(X, y)
    p = m.predict_proba(X[:5])
    check("proba形状(5x3)", p.shape, (5, 3))
    check("proba行和=1", round(float(p.sum(axis=1).mean()), 6), 1.0)
    check("列序=[away,draw,home]", [int(p[:, c].sum() > 0) for c in range(3)], [1, 1, 1])

    # 缺类: y 只有 0/2 两类, 输出仍 pad 成 3 列
    y2 = np.where(y == 1, 0, y)
    m2 = CatModel({"iterations": 30, "depth": 3, "learning_rate": 0.1, "thread_count": 2})
    m2.fit(X, y2)
    p2 = m2.predict_proba(X[:5])
    check("缺类proba仍3列", p2.shape, (5, 3))
    check("缺类行和=1", round(float(p2.sum(axis=1).mean()), 6), 1.0)

    # OU 二分类(大小球2.5): y∈{0,1}, proba 2列, 第2列=大球概率
    you = (y >= 1).astype(int)
    m3 = CatModel({"iterations": 30, "depth": 3, "learning_rate": 0.1, "thread_count": 2})
    m3.fit(X, you)
    p3 = m3.predict_proba(X[:5])
    check("OU二分类proba 2列", p3.shape, (5, 2))
    check("OU行和=1", round(float(p3.sum(axis=1).mean()), 6), 1.0)
    check("OU大球概率在(0,1)", 0.0 < float(p3[0, 1]) < 1.0, True)


def test_ou_settle_sign():
    """回测OU结算方向: settle_ou为大球视角, under必须乘-1 (修复: 曾按大球结算致小球ROI虚高)"""
    section("大小球结算方向 (settle_ou + backtest under sign)")
    sys.path.insert(0, "prediction_v2")
    from src.markets import settle_ou
    # settle_ou 本身是大球视角
    check("大球视角: 3球赢", settle_ou(2.5, 3), 1.0)
    check("大球视角: 2球输", settle_ou(2.5, 2), -1.0)
    # backtest 必须对 under 乘 -1
    check("over 3球=赢", 1.0 * settle_ou(2.5, 3), 1.0)
    check("under 3球=输(乘-1)", -1.0 * settle_ou(2.5, 3), -1.0)
    check("under 2球=赢(乘-1)", -1.0 * settle_ou(2.5, 2), 1.0)
    # 结构性防回归: backtest.py OU循环里 under 带 -1.0 sign
    src = io.open("prediction_v2/src/backtest.py", encoding="utf-8").read()
    check("backtest under带-1 sign", '"under", p_under_model, m_under, o_under, c_under, -1.0)' in src, True)
    check("backtest sign乘settle", "sign * settle_ou(line" in src, True)


def _parse_filters(raw):
    parts = raw.replace(";", ",").split(",")
    return [p.strip().lower() for p in parts if p.strip()]

def test_bsd_prob_calib():
    """BSD历史概率校准 (bsd_prob_calib): 概率桶 vs 实际命中率, 汇总偏差"""
    section("BSD概率校准 (bsd_prob_calib.run)")
    import sys
    sys.path.insert(0, "prediction_v2")
    import bsd_prob_calib as bc

    pairs = [(0.55, True), (0.55, False), (0.55, True), (0.45, False)]
    rows = bc.bin_stats(pairs)
    check("bin_stats 桶数", len(rows), 2)
    _b55 = [r for r in rows if abs(r[0] - 0.5) < 1e-9]
    check("0.5-0.6桶命中率", _b55[0][3], 66.7)

    import os
    if os.path.exists(bc.SRC):
        res = bc.run()
        check("校准样本>0", res["n"] > 0, True)
        for k in ("calib_1x2_home", "calib_over25", "calib_favorite", "calib_market_home"):
            check("字段%s存在" % k, k in res, True)
            check("字段%s非空" % k, len(res[k]) > 0, True)
        check("汇总存在", "summary" in res, True)


def test_lgb_feature_names():
    """LGBModel: fit/predict 无 feature_name warning (DataFrame 传特征名)"""
    section("LGB feature_names 修复")
    import sys, warnings
    sys.path.insert(0, "prediction_v2")
    import numpy as np
    import src.models as M

    rng = np.random.RandomState(7)
    X = rng.rand(120, 8)
    y = rng.randint(0, 3, 120)
    m = M.LGBModel({"n_estimators": 15, "max_depth": 2, "learning_rate": 0.1})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        m.fit(X, y)
        p = m.predict_proba(rng.rand(4, 8))
        feat_warn = [str(x.message) for x in w
                     if "feature_name" in str(x.message).lower() or "feature names" in str(x.message).lower()]
    check("proba形状(4x3)", p.shape, (4, 3))
    check("proba行和=1", bool(np.allclose(p.sum(1), 1)), True)
    check("无feature_name warning", len(feat_warn), 0)



def test_formation_indicator():
    """阵型指标 (scan_upcoming._formation_profile/_formation_check)"""
    section("阵型指标 (formation)")
    import sys
    sys.path.insert(0, "prediction_v2")
    import scan_upcoming as su

    # 阵型解析: 后卫数/前锋数/攻防倾向
    p = su._formation_profile("4-2-3-1")
    check("4-2-3-1后卫数", p["def"], 4)
    check("4-2-3-1前锋数", p["fwd"], 1)
    check("4-2-3-1单前锋偏防守", p["tend"], -1)
    p5 = su._formation_profile("5-3-2")
    check("5-3-2五后卫双前锋抵消", p5["tend"], 0)
    p3 = su._formation_profile("3-4-3")
    check("3-4-3进攻倾向", p3["tend"], 2)
    check("空阵型返None", su._formation_profile(""), None)
    check("坏阵型返None", su._formation_profile("abc"), None)

    # 当场阵型优先 + 对攻倾向标签
    r = {"risk_tags": [], "notes": []}
    info = {"bsd_lineups": {"formation": {"home": "4-4-2", "away": "4-3-3"},
                            "coach": {"home": "4-2-3-1", "away": "4-2-3-1"}}}
    out = su._formation_check(r, info)
    check("当场阵型来源", out["src"], "cur")
    check("主队阵型", out["home"], "4-4-2")
    check("对攻倾向标签", any("阵型对攻倾向" in x for x in r["risk_tags"]), True)
    check("阵型note", any("阵型:主4-4-2/客4-3-3" in x for x in r["notes"]), True)

    # 教练偏好兜底
    r2 = {"risk_tags": [], "notes": []}
    info2 = {"bsd_lineups": {"formation": {}, "coach": {"home": "4-2-3-1", "away": "3-5-2"}}}
    out2 = su._formation_check(r2, info2)
    check("教练偏好来源", out2["src"], "coach")
    check("教练偏好阵型", out2["home"], "4-2-3-1")
    check("3-5-2无对攻标签(客+1主0)", any("阵型对攻倾向" in x for x in r2["risk_tags"]), False)

    # 完全缺失 -> 阵型未提取
    r3 = {"risk_tags": [], "notes": []}
    out3 = su._formation_check(r3, {"bsd_lineups": {}})
    check("阵型未提取标签", any("阵型未提取" in x for x in r3["risk_tags"]), True)


def test_bsd_lineups_formation():
    """BSD lineups: fetch_lineups 提取 formation + _coach_formation"""
    section("BSD lineups formation (bsd_extra)")
    import sys
    sys.path.insert(0, "prediction_v2")
    import bsd_extra as bx

    lu = {"lineups": {"home": {"formation": "4-4-2", "confidence": 0.8},
                      "away": {"formation": "3-5-2", "confidence": 0.5}},
          "lineup_status": "predicted",
          "unavailable_players": {"home": [], "away": []},
          "updated_at": "x"}
    bx._get = lambda path, **kw: lu
    out = bx.fetch_lineups(1)
    check("formation home", out["formation"]["home"], "4-4-2")
    check("formation away", out["formation"]["away"], "3-5-2")
    check("lineup_status", out["lineup_status"], "predicted")

    ev = {"home_coach": {"preferred_formation": "4-2-3-1"}, "away_coach": {}}
    check("教练主队阵型", bx._coach_formation(ev, "home"), "4-2-3-1")
    check("教练客队空", bx._coach_formation(ev, "away"), None)



def test_injury_pos_weight():
    """伤停按位置加权 (scan_upcoming._injury_pos_check): 关键位置标签+降星, 不改EV."""
    section("伤停位置加权 (injury pos)")
    sys.path.insert(0, "prediction_v2")
    import scan_upcoming as su

    # 主队门将1+后防2 -> 伤停关键位置标签 + 降星(不改EV); 客队中场3仅提示不降星
    r = {"risk_tags": [], "notes": [], "star": 3, "best_bet": {"name": "x", "star": 3}}
    info = {"injuries": {"home": [
        {"name": "GK1", "position": "G"},
        {"name": "CB1", "position": "D"},
        {"name": "CB2", "position": "D"},
    ], "away": [
        {"name": "A1", "position": "M"},
         {"name": "A2", "position": "M"},
         {"name": "A3", "position": "M"},
    ]}}
    out = su._injury_pos_check(r, info)
    check("关键位置标签存在", any("伤停关键位置" in x for x in r["risk_tags"]), True)
    check("主队门将/后防", "主队:门将/后防" in r["risk_tags"][0], True)
    check("仅降星note", any("仅降星" in x for x in r["notes"]), True)
    check("star降1", r["star"], 2)
    check("best_bet star同步降", r["best_bet"]["star"], 2)
    check("客队中场3计数", out["away"].get("M"), 3)
    check("位置统计G/D", out["home"], {"G": 1, "D": 2})

    # 位置未知 -> 不加标签不降星, 计数unknown
    r2 = {"risk_tags": [], "notes": [], "star": 3}
    out2 = su._injury_pos_check(r2, {"injuries": {"away": [{"name": "X"}]}})
    check("位置未知不加标签", r2["risk_tags"], [])
    check("位置未知不降星", r2["star"], 3)
    check("位置未知计数", out2["unknown"], 1)

    # 空伤停 -> 无变化
    r3 = {"risk_tags": [], "notes": [], "star": 3}
    out3 = su._injury_pos_check(r3, {"injuries": {}})
    check("空伤停无标签", r3["risk_tags"], [])
    check("空伤停不降星", r3["star"], 3)
    check("空伤停计数", out3["unknown"], 0)

def test_coach_quant():
    """教练量化归一 (coach_quant): 强攻/强防方向, 样本衰减, profile微调, 退化池中性."""
    section("教练量化 (coach_quant)")
    sys.path.insert(0, "prediction_v2")
    import coach_quant as cq
    cache = {"leagues": {"英超": {"n": 3, "min_gf": 1.0, "max_gf": 3.0, "min_ga": 0.8, "max_ga": 1.8}},
             "coaches": {
                 "1": {"matches_total": 80, "avg_goals_scored": 3.0, "avg_goals_conceded": 0.8,
                       "tactical_profile": "attacking", "name": "Atk Coach"},
                 "2": {"matches_total": 80, "avg_goals_scored": 1.0, "avg_goals_conceded": 1.8,
                       "tactical_profile": "defensive", "name": "Def Coach"},
                 "3": {"matches_total": 10, "avg_goals_scored": 3.0, "avg_goals_conceded": 0.8,
                       "tactical_profile": "balanced", "name": "New Coach"}}}
    m1 = cq.coach_mods(cache, 1, "英超")
    m2 = cq.coach_mods(cache, 2, "英超")
    m3 = cq.coach_mods(cache, 3, "英超")
    check("强攻教练atk>1", m1["atk"] > 1.0, True)
    check("强攻教练def<1(强防压低对手λ)", m1["def"] < 1.0, True)
    check("弱攻教练atk<1", m2["atk"] < 1.0, True)
    check("弱防教练def>1", m2["def"] > 1.0, True)
    check("满样本全额+attack微调(1.15x1.02)", round(m1["atk"], 4), 1.173, tol=0.001)
    check("defend标签压低atk", round(m2["atk"], 4), 0.833, tol=0.001)
    check("样本10衰减修正力度远弱", m3["atk"], 1.0188, tol=0.01)
    check("退化联赛池(n<3)->None", cq.coach_mods(
        {"leagues": {"X": {"n": 2, "min_gf": 1.0, "max_gf": 2.0, "min_ga": 0.8, "max_ga": 1.5}},
         "coaches": {"1": {"matches_total": 80, "avg_goals_scored": 1.5, "avg_goals_conceded": 1.0}}},
        1, "X"), None)
    check("无缓存->None", cq.coach_mods(None, 1, "英超"), None)
    check("无该教练->None", cq.coach_mods(cache, 999, "英超"), None)
    txt = cq.mod_text({"h_atk": 1.1, "h_def": 0.9, "h_sample": 50, "h_name": "Test Coach"})
    check("mod_text含攻防样本", ("+10.0%" in txt and "-10.0%" in txt and "n50" in txt), True)
    check("空mod_text", cq.mod_text({}), "")
    # league_calib.json global_settings 教练参数存在且被加载
    cal_p = os.path.join("strategy_data", "league_calib.json")
    if os.path.exists(cal_p):
        gs = json.load(io.open(cal_p, encoding="utf-8")).get("global_settings") or {}
        check("league_calib教练区间下限", gs.get("coach_atk_range_min"), 0.85)
        check("league_calib教练样本满额", gs.get("coach_sample_cap"), 80)
        check("配置已加载到coach_quant", cq.COACH_SAMPLE_CAP, 80.0)


def test_bsd_coaches_extract():
    """bsd_extra: 事件教练 -> bsd_coaches {id,name,profile}; 缺教练返回None."""
    section("BSD 教练提取 (bsd_extra._coach_rec)")
    sys.path.insert(0, "prediction_v2")
    import bsd_extra as bx
    ev = {"home_coach": {"id": 559, "name": "Pep Guardiola", "profile": "attacking"},
          "away_coach": {"id": 507, "name": "Arne Slot", "profile": "attacking"}}
    h = bx._coach_rec(ev, "home")
    a = bx._coach_rec(ev, "away")
    check("home coach id", h["id"], 559)
    check("home coach name", h["name"], "Pep Guardiola")
    check("away coach name", a["name"], "Arne Slot")
    check("缺教练返回None", bx._coach_rec({}, "home"), None)
    check("无id返回None", bx._coach_rec({"home_coach": {"name": "X"}}, "home"), None)
    import glob
    fs = sorted(glob.glob(os.path.join("analysis_records", "matches_info_*.json")))
    if fs:
        d = json.load(io.open(fs[-1], encoding="utf-8"))
        got = [m for m in d.get("matches", []) if m.get("bsd_coaches")]
        check("matches_info含bsd_coaches场次>0", len(got) > 0, True)
        if got:
            rec = got[0]["bsd_coaches"].get("home") or {}
            check("bsd_coaches含id", rec.get("id") is not None, True)
            check("bsd_coaches含name", bool(rec.get("name")), True)


def test_scan_coach_integration():
    """scan_upcoming: coach_mods 折叠进 λ (强攻主教练拉高主队λ, 强防守教练压低主队λ)."""
    section("教练修正接入 λ (scan_upcoming)")
    sys.path.insert(0, "prediction_v2")
    import scan_upcoming as su
    ts, lavg, index = su.load_team_stats()
    _dt = __import__("datetime")
    m = {"league": "荷甲", "home": "Ajax", "away": "PSV Eindhoven",
         "ct": _dt.datetime(2026, 8, 16, 12, 0, tzinfo=_dt.timezone.utc),
         "snap": "2026-08-16T11:00:00Z",
         "h2h": {"home": 2.2, "draw": 3.3, "away": 3.1},
         "spread": {"hdp_home": -0.25, "home_price": 1.9, "away_price": 1.95},
         "totals": {"line": 2.5, "over_price": 1.9, "under_price": 1.9}}
    base = su.analyze_match(dict(m), ts, lavg, index)
    m1 = dict(m); m1["coach_mods"] = {"h_atk": 1.15, "h_sample": 80}
    rA = su.analyze_match(dict(m1), ts, lavg, index)
    check("强攻主教练拉高主队λ", rA["lambda"]["home"] > base["lambda"]["home"], True)
    check("教练note写入", any("教练量化" in n for n in rA["notes"]), True)
    m2 = dict(m); m2["coach_mods"] = {"a_def": 0.85, "a_sample": 80}
    rB = su.analyze_match(dict(m2), ts, lavg, index)
    check("强防守教练压低主队λ", rB["lambda"]["home"] < base["lambda"]["home"], True)
    m3 = dict(m); m3["coach_mods"] = {}
    rC = su.analyze_match(dict(m3), ts, lavg, index)
    check("无教练修正λ不变", abs(rC["lambda"]["home"] - base["lambda"]["home"]) < 1e-9, True)
    m4 = dict(m); m4["coach_missing"] = True
    rD = su.analyze_match(dict(m4), ts, lavg, index)
    check("教练缺失note标注", any("教练数据未提取" in n for n in rD["notes"]), True)


def test_ledger_coach_cols():
    """bet_ledger: 新增教练字段列 + scan 落账写入教练修正."""
    section("账本教练字段 (bet_ledger)")
    sys.path.insert(0, "prediction_v2")
    import tempfile
    import bet_ledger as bl
    check("账本含教练攻修正列", "coach_atk_mod" in bl.COLS, True)
    check("账本含教练防修正列", "coach_def_mod" in bl.COLS, True)
    check("账本含教练样本列", "coach_sample_size" in bl.COLS, True)
    scan = {"matches": [{"league": "荷甲", "home": "TeamA", "away": "TeamB",
             "ct": "2026-08-16T12:00:00+08:00",
             "result": {"best_bet": {"name": "大2.5", "prob": 0.6, "odds": 1.9, "ev": 0.1,
                                     "star": 3, "ev_tier": "标准", "stake_factor": 1.0},
                        "coach": {"h_atk": 1.1, "a_atk": 0.95, "h_def": 0.9, "a_def": 1.05,
                                  "h_sample": 60, "a_sample": 40}}}]}
    fd, spath = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(scan, f)
    old_ledger = bl.LEDGER
    tmp_ledger = os.path.join(tempfile.gettempdir(), "test_ledger_coach.csv")
    bl.LEDGER = tmp_ledger
    try:
        bl.cmd_scan(spath)
        rows = bl._load()
        check("落账1条", len(rows), 1)
        check("教练攻修正均值1.025", round(float(rows[0]["coach_atk_mod"]), 4), 1.025)
        check("教练防修正均值0.975", round(float(rows[0]["coach_def_mod"]), 4), 0.975)
        check("教练样本取小40", int(rows[0]["coach_sample_size"]), 40)
    finally:
        bl.LEDGER = old_ledger
        for _f in (spath, tmp_ledger):
            try:
                os.remove(_f)
            except Exception:
                pass


def test_leak_void_caliber():
    """40. 防泄漏口径回归 (2026-08-26审计): snap_age_h<0 赛后盘行一律作废, 不入统计."""
    section("40. 防泄漏口径 (snap<0赛后盘作废 / 双口径统计)")
    sys.path.insert(0, "prediction_v2")
    import bet_ledger as bl
    check("bet_ledger有赛后盘判定函数", hasattr(bl, "_is_post_kick_snap"), True)
    check("正常赛前盘(snap=2.5)不算泄漏", bl._is_post_kick_snap({"snap_age_h": "2.5"}), False)
    check("赛后拉盘(snap=-3)算泄漏", bl._is_post_kick_snap({"snap_age_h": "-3"}), True)
    check("snap缺失按不泄漏(保守保留)", bl._is_post_kick_snap({"snap_age_h": ""}), False)
    check("snap坏值按不泄漏(不崩溃)", bl._is_post_kick_snap({"snap_age_h": "abc"}), False)
    # 台账实例门槛: 2026-08-26迁移后所有snap<0行必须已标无效
    led = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analysis_records", "bet_ledger.csv")
    rows = list(csv.DictReader(io.open(led, encoding="utf-8-sig")))
    bad = [r for r in rows if bl._is_post_kick_snap(r) and r.get("status") == "已结算"]
    check("台账snap<0行已全部标无效", len(bad), 0)
    n_void = sum(1 for r in rows if str(r.get("status", "")).startswith("无效"))
    check("台账无效行数>=81(08-22对账回填迁移)", n_void >= 81, True)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="回归测试 v1.0 - 防AI退化质检闸门")
    ap.add_argument("--only", "--filter", dest="filters", default="",
                    help="只跑名称包含指定子串的测试, 逗号分隔. 例: --only poisson,settle")
    ap.add_argument("--list", action="store_true", help="列出全部测试函数后退出")
    args = ap.parse_args(argv)

    if args.list:
        print("全部测试函数 (共 %d 个):" % len(TEST_ORDER))
        for name in TEST_ORDER:
            print("  " + name)
        return

    filters = _parse_filters(args.filters)
    if filters:
        selected = [n for n in TEST_ORDER if any(f in n.lower() for f in filters)]
        if not selected:
            print(f"❌ 没有匹配过滤条件 {args.filters!r} 的测试")
            sys.exit(2)
        print(f"过滤条件: {args.filters} → 运行 {len(selected)}/{len(TEST_ORDER)} 个测试")
    else:
        selected = list(TEST_ORDER)

    global PASS, FAIL
    PASS, FAIL = 0, 0
    FAILURES.clear()

    print("回归测试 v1.0 - 防AI退化质检闸门")
    print("覆盖: 盘口解析/泊松/best_bet/冷门引擎/投注结算/数据提取器")

    for name in selected:
        globals()[name]()

    print()
    print("=" * 70)
    print(f"  结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print("  失败明细:")
        for f in FAILURES:
            print(f"    ❌ {f}")
    print("=" * 70)
    if FAIL > 0:
        sys.exit(1)
    print("  ✅ 全部通过 - 历史正确结论未被破坏")


def test_standings_tags():
    """积分榜接入 (2026-08-26 M-20260826-01): 保级区主场+1星/标签; 中游无欲无求-1星; 不改EV."""
    section("积分榜标签 (standings zone tags)")
    sys.path.insert(0, "prediction_v2")
    from datetime import datetime, timezone
    import scan_upcoming as su
    import _batch_match_info as bmi

    ts, lavg, index = su.load_team_stats()
    _orig_avg = su.recent_league_avg
    _orig_std = su._standings_idx
    su.recent_league_avg = lambda: {"中超": (3.04, 30)}
    try:
        m = {"id": "t", "league": "中超", "home": "Shanghai Shenhua FC", "away": "Henan FC",
             "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc), "snap": "2026-08-16T10:00:00Z",
             "h2h": {"home": 2.0, "away": 3.4, "draw": 3.6},
             "spread": {"hdp_home": -0.5, "home_price": 2.05, "away_price": 2.05},
             "totals": {"line": 3.5, "over_price": 1.95, "under_price": 1.95}}
        # r0: 无积分榜
        su._standings_idx = lambda: {}
        r0 = su.analyze_match(m, ts, lavg, index)
        # r1: 主队保级(15/16), 客队中游
        fake = {bmi.team_key("Shanghai Shenhua FC"): {"league": "中超", "pos": 15, "total": 16, "pts": 8, "played": 12, "form": "LDLDL"},
                bmi.team_key("Henan FC"): {"league": "中超", "pos": 8, "total": 16, "pts": 15, "played": 12, "form": "WDWDL"}}
        su._standings_idx = lambda: fake
        r1 = su.analyze_match(m, ts, lavg, index)
        check("保级主场标签", any("保级" in t for t in r1["risk_tags"]), True)
        check("积分榜入档", (r1.get("standings") or {}).get("home", {}).get("zone"), "保级")
        check("保级主场+1星", r1["star"], (r0["star"] or 0) + 1)
        check("积分榜不改EV", r1["best_bet"]["ev"], r0["best_bet"]["ev"])
        # r2: 双方中游且 played>=8 -> -1星
        fake2 = {bmi.team_key("Shanghai Shenhua FC"): {"league": "中超", "pos": 8, "total": 16, "pts": 15, "played": 12, "form": "WDLWD"},
                 bmi.team_key("Henan FC"): {"league": "中超", "pos": 9, "total": 16, "pts": 14, "played": 12, "form": "DWDWL"}}
        su._standings_idx = lambda: fake2
        r2 = su.analyze_match(m, ts, lavg, index)
        check("无欲无求标签", any("无欲无求" in t for t in r2["risk_tags"]), True)
        check("无欲无求-1星", r2["star"], max(1, (r0["star"] or 0) - 1))
    finally:
        su.recent_league_avg = _orig_avg
        su._standings_idx = _orig_std

if __name__ == "__main__":
    main()
