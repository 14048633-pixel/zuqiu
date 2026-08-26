# -*- coding: utf-8 -*-
"""足球预测系统 162 条核心规则编号清册（v1.0，源自《足球预测分析系统_v1.docx》）

单一数据源：新规则接入、清册查询、自动化实现状态追踪都从这里读。
字段说明:
  id       规则编号
  name     规则名
  category 分类
  core     核心要点
  trigger  触发条件（文档原文精简）
  data     自动化所需数据字段（data.get 读取，缺省不触发）
  priority 优先级: 3=🔴🔴🔴 2=🔴🔴 1=🔴 0=普通
  status   implemented=已在代码实现 / missing=仅文档
"""
RULES = [
    dict(id="R1", name="退盘=降信心", category="盘口赔率信号", core="主队退盘说明机构对主队赢球信心下降", trigger="亚盘退盘≥0.25球", data=["odds_home", "odds_home_initial"], priority=1, status="implemented"),
    dict(id="R2", name="升水=不看好", category="盘口赔率信号", core="主队水位持续升高，主胜风险加大", trigger="水位连续2+时段升高", data=["odds_home", "odds_home_initial"], priority=0, status="implemented"),
    dict(id="R3", name="变盘方向即倾向", category="盘口赔率信号", core="盘口变化方向=机构真实倾向", trigger="盘口发生变动", data=["odds_home", "odds_home_initial"], priority=0, status="implemented"),
    dict(id="R4", name="生死盘防走水", category="盘口赔率信号", core="-1球生死盘需防平局或小胜", trigger="亚盘-1球", data=["handicap_line"], priority=0, status="implemented"),
    dict(id="R5", name="低水诱客陷阱", category="盘口赔率信号", core="客队低水+平赔下降=诱买客队", trigger="客队低水0.75+平赔下降", data=["away_water", "odds_draw", "odds_draw_initial"], priority=1, status="implemented"),
    dict(id="R6", name="欧亚矛盾同向看衰", category="盘口赔率信号", core="退盘+欧赔主胜升高双信号看衰主队，盘口双信号权重>基本面双信号权重", trigger="亚盘退盘+欧赔主胜↑", data=["handicap_line", "handicap_initial", "odds_home", "odds_home_initial"], priority=1, status="implemented"),
    dict(id="R7", name="平赔暴跌=资金涌平局", category="盘口赔率信号", core="平赔大幅下降0.20+，平局概率显著提升", trigger="平赔降≥0.20", data=["odds_draw", "odds_draw_initial"], priority=1, status="implemented"),
    dict(id="R8", name="阿森纳低水=保", category="盘口赔率信号", core="特定球队低水方向相对稳定", trigger="特定球队低水", data=["team"], priority=0, status="missing"),
    dict(id="R9", name="让步不足", category="盘口赔率信号", core="强队只让平手/0.25=机构不认为能赢", trigger="强队让平手/0.25", data=["home_elo", "away_elo", "odds_home"], priority=1, status="implemented"),
    dict(id="R30", name="平手盘+交锋碾压→客胜", category="盘口赔率信号", core="平手盘+交锋近6次主队0胜=客胜优先", trigger="①平手盘②交锋≤1胜③客队近况≥30%", data=["handicap_line", "h2h_home_wins"], priority=0, status="missing"),
    dict(id="R33", name="退盘+欧赔客胜最低=客胜", category="盘口赔率信号", core="平手盘+欧赔客胜三项最低=客胜优先", trigger="①平手盘②客胜<主胜③退主", data=["handicap_line", "odds_away", "odds_home"], priority=0, status="missing"),
    dict(id="R69", name="真硬不演盘口", category="盘口赔率信号", core="极低胜赔+平负双高=真信主胜", trigger="胜赔≤1.30+平≥4.0+负≥8.0", data=["odds_home", "odds_draw", "odds_away"], priority=1, status="implemented"),
    dict(id="R70", name="欧赔结构方向铁律", category="盘口赔率信号", core="高胜+低负=走客队", trigger="①主胜≥2.0②客胜≤主胜③客胜≤平赔", data=["odds_home", "odds_draw", "odds_away"], priority=1, status="implemented"),
    dict(id="R71", name="让球盘>胜平负精度", category="盘口赔率信号", core="让球盘专业玩家为主，更接近机构真实观点", trigger="始终适用", data=[], priority=1, status="implemented"),
    dict(id="R72", name="赔率引导逆向", category="盘口赔率信号", core="赔率被刻意引导→逆向操作", trigger="赔率变化有刻意痕迹", data=[], priority=0, status="missing"),
    dict(id="R73", name="临场双拉=噪音", category="盘口赔率信号", core="临场胜+平双降=散户跟风", trigger="①赛前2h内②胜+平同降0.05+③客胜↑", data=[], priority=0, status="missing"),
    dict(id="R79", name="临场修正须盘口确认", category="盘口赔率信号", core="修正方向与赔率方向矛盾→修正降权", trigger="①修正方向②赔率升水③变化>0.10", data=["correction_direction", "odds_home", "odds_home_initial"], priority=1, status="implemented"),
    dict(id="R93", name="外围收盘信号>中间分歧", category="盘口赔率信号", core="收盘前30分钟收敛方向才是真方向", trigger="收盘前30min让球+大小球同向", data=[], priority=0, status="missing"),
    dict(id="R101", name="SS信号降权条件", category="盘口赔率信号", core="打破条件存在时SS降A+", trigger="5家全退但有打破条件", data=[], priority=0, status="missing"),
    dict(id="R110", name="SS退盘→让负优先", category="盘口赔率信号", core="5家全退≥1盘级→让负仓位≥60%，最保守解读优先", trigger="①5家全退②让负<让平", data=["ss_recede_count", "odds_hdp_draw", "odds_hdp_loss"], priority=2, status="implemented"),
    dict(id="R112", name="赔率不变≠方向确认", category="盘口赔率信号", core="赔率稳定≠铁板，需检查赔率结构最低项", trigger="①波动≤0.05持续3+时段②非最低", data=["flat_periods", "odds_home", "odds_draw", "odds_away"], priority=1, status="implemented"),
    dict(id="R186", name="临场升盘确认", category="盘口赔率信号", core="退盘后升回=方向锁定，R186优先级>R170退盘修正", trigger="先退后升回到初盘或更高", data=["hdp_initial", "hdp_trough", "hdp_last"], priority=2, status="implemented"),
    dict(id="R63", name="换手平稳=市场共识", category="必发深度", core="Back/Lay价差<0.10+WoM 40-60%=真共识", trigger="价差<0.10且WoM 40-60%", data=["betfair_spread", "betfair_wom"], priority=0, status="missing"),
    dict(id="R64", name="深层Back大单=吃货", category="必发深度", core="深层大单+占比>40%=大资金看好", trigger="深层大单且占比>40%", data=["betfair_deep_back", "betfair_deep_share"], priority=0, status="missing"),
    dict(id="R65", name="卖方主动压价=不利", category="必发深度", core="WoM<35%+Lay挂单远超Back=看空", trigger="WoM<35%且Lay远超Back", data=["betfair_wom", "betfair_back_lay_ratio"], priority=0, status="missing"),
    dict(id="R66", name="盈利率异常=市场方向", category="必发深度", core="大小球盈利率偏离2倍标准差=顺市场", trigger="盈利率偏离2σ", data=["betfair_ou_profit"], priority=0, status="missing"),
    dict(id="R67", name="Back放量+高位挂单=硬吃", category="必发深度", core="买方高价位主动挂单=真金白银看好", trigger="买方高价位主动挂单", data=["betfair_back_volume"], priority=0, status="missing"),
    dict(id="R74", name="凯差离散度偏高=扭曲", category="必发深度", core="凯差偏离1.5倍标准差=赔率被扭曲", trigger="凯差偏离1.5σ", data=["kelly_dev"], priority=0, status="missing"),
    dict(id="R75", name="凯差热指低位=安全", category="必发深度", core="机构赔付风险可控=真实概率", trigger="凯差热指低位", data=["kelly_heat"], priority=0, status="missing"),
    dict(id="R76", name="中间价位空白=无人区", category="必发深度", core="Back/Lay中间空白=谁挂谁被吃", trigger="Back/Lay中间空白", data=["betfair_gap"], priority=1, status="missing"),
    dict(id="R77", name="量价背离=信号", category="必发深度", core="成交方向与赔率变化方向不一致=隐藏力量", trigger="成交方向与赔率变化背离", data=["betfair_volume", "odds_home", "odds_home_initial"], priority=0, status="missing"),
    dict(id="R78", name="大球深层买入=进球偏大", category="必发深度", core="O/U 3.5/4.5有买入=修正小球预期", trigger="O/U 3.5/4.5有买入", data=["betfair_over_deep"], priority=0, status="missing"),
    dict(id="R36", name="线索矛盾→警惕第三选项", category="庄家操纵", core="≥2维度互相矛盾=答案在盲区", trigger="≥2维度矛盾", data=[], priority=1, status="missing"),
    dict(id="R37", name="过于完美=诱盘信号", category="庄家操纵", core="热门选项数据完美但有表演感=诱盘", trigger="热门选项数据完美", data=[], priority=1, status="missing"),
    dict(id="R38", name="对立选项无支撑=主方向加强", category="庄家操纵", core="真热+对立选项连反抗都没有=主方向可信", trigger="真热+对立无支撑", data=[], priority=0, status="missing"),
    dict(id="R39", name="放量下行=强势确认", category="庄家操纵", core="成交放量+价位下行=买方压倒性优势", trigger="放量+价位下行", data=[], priority=0, status="missing"),
    dict(id="R58", name="庄家自救盘", category="庄家操纵", core="必发>80%集中+盘口不调整=庄家控盘", trigger="必发>80%集中+盘口不动", data=[], priority=0, status="missing"),
    dict(id="R59", name="控盘成本阈值", category="庄家操纵", core="顶级赛事操纵成本高概率低，友谊赛相反", trigger="友谊赛降低警惕档", data=["is_friendly"], priority=0, status="implemented"),
    dict(id="R60", name="多庄博弈盘", category="庄家操纵", core="多大资本抢夺控制权→先观察保守为好", trigger="多庄博弈", data=[], priority=0, status="missing"),
    dict(id="R96", name="诱盘验证三条件", category="庄家操纵", core="盘口持续受捧≠诱盘，需验证三条件(凯利>1.05/BTTS矛盾/基本面硬伤)至少1条", trigger="独赢赔率2-3时段连跌", data=["odds_fall_periods", "kelly_home", "btts_conflict", "fundamental_negative"], priority=1, status="implemented"),
    dict(id="R99", name="反向指标使用条件", category="庄家操纵", core="散户热度≠总是反向，三条件验证后判断", trigger="散户热度三条件验证", data=[], priority=0, status="missing"),
    dict(id="R10", name="伤病执行", category="基本面阵容", core="关键球员伤缺3人以上必须降级", trigger="关键伤缺≥3人", data=["key_injuries"], priority=1, status="implemented"),
    dict(id="R11", name="主场优势", category="基本面阵容", core="主场3+场不败+关键战，主场爆发力加权", trigger="主场3+场不败+关键战", data=["home_unbeaten_streak"], priority=0, status="missing"),
    dict(id="R12", name="决赛≠闷平", category="基本面阵容", core="决赛属性球队主场作战爆发力远超常规", trigger="决赛属性主场", data=["is_final"], priority=0, status="missing"),
    dict(id="R13", name="近5场胜率权重", category="基本面阵容", core="胜率≥60%方向+1级；≤30%对手方向+1级", trigger="近5场胜率≥60%或≤30%", data=["home_form_wr", "away_form_wr"], priority=0, status="missing"),
    dict(id="R14", name="交锋历史辅助", category="基本面阵容", core="近5次交锋4+次同方向+1级（仅辅助）", trigger="近5次交锋4+次同方向", data=["h2h_direction_count"], priority=0, status="missing"),
    dict(id="R28", name="双方防线烂≠平局安全", category="基本面阵容", core="两队防守都差→对攻大比分>沉闷平局", trigger="双方防守都差", data=["home_def_rating", "away_def_rating"], priority=0, status="missing"),
    dict(id="R31", name="终结者vs体系核心", category="基本面阵容", core="核心前锋缺席≠进攻崩塌，区分两类影响", trigger="核心前锋缺席", data=["missing_key_forward", "missing_system_core"], priority=0, status="missing"),
    dict(id="R83", name="额外动力≠进球效率", category="基本面阵容", core="战意提升≠进球效率提升，低效球队额外动力归零", trigger="低效球队+额外动力", data=["team_goal_efficiency"], priority=1, status="missing"),
    dict(id="R94", name="体能清算", category="基本面阵容", core="5维度评估体能扣分→映射进球预期调整", trigger="体能5维度扣分", data=["fitness_penalty"], priority=1, status="missing"),
    dict(id="R95", name="红牌=让平杀手", category="基本面阵容", core="红牌打破让平精确匹配，让平天然脆弱", trigger="红牌风险高", data=["red_card_risk"], priority=1, status="missing"),
    dict(id="R124", name="裁判风格量化", category="基本面阵容", core="严哨/宽松/主场哨/点球猎手4类→影响方向", trigger="裁判风格分类", data=["referee_style"], priority=1, status="implemented"),
    dict(id="R125", name="伤病位置权重", category="基本面阵容", core="门将-2>中卫-1.5>后腰-1>前锋-0.5，叠加×1.5，上限-3", trigger="伤病位置权重≥1", data=["injuries"], priority=2, status="implemented"),
    dict(id="R126", name="红牌/点球概率预判", category="基本面阵容", core="裁判红牌率×对抗激烈度×纪律风险→量化概率", trigger="红牌/点球概率高", data=["referee_red_rate", "aggression"], priority=1, status="missing"),
    dict(id="R137", name="xG/射门质量评估", category="基本面阵容", core="xG高没赢→反弹+0.5；xG低赢了→不可持续-0.5", trigger="xG与赛果偏差>0.5", data=["home_xg", "home_scored", "away_xg", "away_scored"], priority=1, status="implemented"),
    dict(id="R143", name="门将超预期评估", category="基本面阵容", core="PSxG-GA/90分级+场景化权重", trigger="门将超预期", data=["gk_psxg_ga"], priority=1, status="implemented"),
    dict(id="R24", name="友谊赛深盘穿盘陷阱", category="战意", core="非主场告别战穿盘率极低", trigger="友谊赛深盘", data=["is_friendly", "handicap_line"], priority=0, status="implemented"),
    dict(id="R25", name="壮行战/告别战", category="战意", core="主场告别战=全力大胜取悦球迷", trigger="主场告别战", data=["is_farewell"], priority=0, status="missing"),
    dict(id="R26", name="热身赛主场三定律", category="战意", core="主场+告别战→穿盘；主场+非告别+深盘→赢球输盘", trigger="热身赛主场三定律", data=["is_friendly", "is_farewell", "handicap_line"], priority=0, status="missing"),
    dict(id="R27", name="日职排位赛平局魔咒", category="战意", core="无欲无求排位赛1-1是默认比分", trigger="无欲无求排位赛", data=["league", "motivation"], priority=0, status="missing"),
    dict(id="R34", name="最后一热vs还有下一热", category="战意", core="最后一热方战意显著更高", trigger="最后一热", data=["warmup_last"], priority=0, status="missing"),
    dict(id="R35", name="双无资格主队=战意打折", category="战意", core="双方无缘世界杯→主场优势缩水", trigger="双方无参赛资格", data=["home_qualified", "away_qualified"], priority=0, status="missing"),
    dict(id="R40", name="世界杯参赛队=额外战意", category="战意", core="参赛队战意高于未参赛对手", trigger="参赛队vs未参赛", data=["home_qualified", "away_qualified"], priority=0, status="missing"),
    dict(id="R42", name="友谊赛轮换=战意断崖", category="战意", core="半场轮换3人+主力→专注度断崖", trigger="友谊赛轮换", data=["is_friendly", "is_rotated"], priority=0, status="implemented"),
    dict(id="R54", name="核心换人防守松动", category="战意", core="换下1-2个核心组织者影响>3个角色球员", trigger="换下核心组织者", data=["sub_core_mid"], priority=0, status="missing"),
    dict(id="R61", name="额外动力因子", category="战意", core="哈吉回归/首秀等额外动力需检查进球效率", trigger="额外动力+效率检查", data=["extra_motivation"], priority=0, status="missing"),
    dict(id="R68", name="世界杯资格必须核实", category="战意", core="不能凭印象判断", trigger="资格信息存疑", data=["qualification_confirmed"], priority=0, status="missing"),
    dict(id="R98", name="东道主首战=强方向锚", category="战意", core="77%历史胜率→主胜+2级", trigger="东道主首战", data=["is_host_opener"], priority=1, status="implemented"),
    dict(id="R111", name="首战生手vs老手", category="战意", core="≥20年未参赛+0人经验→虚假自信→降1级", trigger="20年未参赛+0经验", data=["first_appearance_years"], priority=1, status="missing"),
    dict(id="R116", name="首秀/里程碑战意加成", category="战意", core="核心球员世界杯首秀/百场→+0.5球", trigger="核心首秀/百场", data=["milestone_bonus"], priority=0, status="missing"),
    dict(id="R136", name="小组赛出线算术", category="战意", core="MD1赢→MD2保守+小球；MD1输→MD2激进+大球", trigger="小组赛第2轮", data=["group_md", "md1_result"], priority=1, status="implemented"),
    dict(id="R147", name="出线算术强制量化", category="战意", core="积分表推演+出线动机4档+战意不对称", trigger="出线动机4档", data=["qualification_motivation"], priority=2, status="implemented"),
    dict(id="R55", name="人情/默契球综合处理", category="人情心理", core="10大高风险场景+3类处理+统一降1级", trigger="10大高风险场景", data=["collusion_scene"], priority=1, status="missing"),
    dict(id="R57", name="次回合战意方向锁", category="人情心理", core="首回合净胜≥2球→大胜方躺平/大败方拼命", trigger="首回合净胜≥2球", data=["leg1_goal_diff"], priority=0, status="missing"),
    dict(id="R133", name="心理/情绪因子", category="人情心理", core="触底反弹+1/骄傲松懈-0.5/换帅+1/赛季末松懈-1", trigger="情绪因子事件", data=["psychology"], priority=0, status="missing"),
    dict(id="R139", name="国家队默契度/化学反应", category="人情心理", core="核心同源>5人+0.5/旅外拼凑>7人-0.5", trigger="默契度偏离", data=["chemistry"], priority=0, status="missing"),
    dict(id="R144", name="俱乐部羁绊分级", category="人情心理", core="S级≥3人同线→+1.0/A级→+0.5/B级→+0.3", trigger="俱乐部羁绊≥B级", data=["club_bond"], priority=1, status="missing"),
    dict(id="R85", name="气候Debuff", category="环境地理", core="湿热+欧洲队→进球预期×(1-Debuff)", trigger="湿热+欧洲队", data=["climate_debuff"], priority=1, status="missing"),
    dict(id="R86", name="高原Debuff", category="环境地理", core="墨西哥城2200m+低地队→下半场进球×0.7", trigger="高原2200m+低地队", data=["altitude"], priority=1, status="missing"),
    dict(id="R87", name="高温轻敌综合征", category="环境地理", core="湿热+T0/T1打T3+小组赛首轮→让胜-1级", trigger="高温+T0/T1 vs T3+首轮", data=["heat", "tier_gap", "group_md"], priority=1, status="missing"),
    dict(id="R88", name="战术克制权重", category="环境地理", core="V1克V4/V4克V3/V3克V2/V2克V1", trigger="战术克制环", data=["tactic_style"], priority=0, status="missing"),
    dict(id="R134", name="高原/气候适应梯度", category="环境地理", core="<3天×2；3-7天×1.5；7-14天×1；>14天归零", trigger="适应时间梯度", data=["acclimatize_days"], priority=1, status="missing"),
    dict(id="R135", name="雨战/风战量化", category="环境地理", core="小雨0/中雨传控-0.5/大雨-1/积水-1.5", trigger="雨战等级", data=["weather"], priority=1, status="missing"),
    dict(id="R140", name="东道主地理优势量化", category="环境地理", core="球迷比例+地理距离+文化适应", trigger="东道主优势", data=["geo_advantage"], priority=1, status="missing"),
    dict(id="R141", name="开赛时间与生物钟", category="环境地理", core="黄金时段0/下午-0.2/上午-0.3/深夜-0.5", trigger="非黄金时段", data=["kickoff_clock"], priority=1, status="missing"),
    dict(id="R145", name="歇大了效应", category="环境地理", core="休息>6天→进攻端-0.2级", trigger="休息>6天", data=["rest_days"], priority=1, status="implemented"),
    dict(id="R46", name="大小球锚定比分池", category="大小球", core="Under≥60%→{0-0,1-0,0-1,1-1}；Over≥60%→{2-1,1-2,…}", trigger="大小球概率≥60%", data=["ou_over_prob"], priority=1, status="implemented"),
    dict(id="R47", name="进球数赔率交叉验证", category="大小球", core="竞彩进球数+Pinnacle O/U+BTTS三方交叉", trigger="三方交叉验证", data=["ou_line", "ou_over_prob", "btts_prob"], priority=1, status="implemented"),
    dict(id="R48", name="大小球变盘=进球修正", category="大小球", core="O/U盘口升降直接反映进球预期修正", trigger="O/U盘口变动", data=["ou_line", "ou_line_initial"], priority=1, status="implemented"),
    dict(id="R91", name="BTTS反转=风险信号", category="大小球", core="BTTS否赔率从低点反弹≥0.10→弱队进球概率上升", trigger="BTTS否赔率反弹≥0.10", data=["btts_no_odds", "btts_no_low"], priority=0, status="missing"),
    dict(id="R106", name="角球/定位球=上半场杀手", category="大小球", core="对手高空优势+主队防空弱→上半场平局降级", trigger="高空优势+防空弱", data=["setpiece_gap"], priority=1, status="missing"),
    dict(id="R128", name="进球时间窗口", category="大小球", core="强队高峰45-70min/弱队75-90min/定位球60-80min", trigger="时间窗口特征", data=["goal_timing"], priority=1, status="missing"),
    dict(id="R138", name="半全场方向预测", category="大小球", core="强队半场平→平胜；高原疲劳→平胜/平平", trigger="半场平+强队", data=["ht_score"], priority=1, status="missing"),
    dict(id="R49", name="ELO→公平亚盘转换", category="量化模型", core="ELO差→公平盘对照表", trigger="ELO差存在", data=["home_elo", "away_elo", "odds_home"], priority=1, status="implemented"),
    dict(id="R50", name="公平盘vs实际盘差值", category="量化模型", core="≤0.25合理/0.25-0.5浅开/0.5+严重浅开", trigger="盘口差值", data=["odds_home", "fair_odds"], priority=1, status="implemented"),
    dict(id="R51", name="公平大小球vs实际盘", category="量化模型", core="公平值>实际0.5球=浅开→大球加分", trigger="公平OU-实际OU≥0.5", data=["ou_fair_line", "ou_line"], priority=1, status="implemented"),
    dict(id="R52", name="ELO评分体系", category="量化模型", core="差100≈64%胜率/差200≈76%/差300≈85%", trigger="ELO差>100", data=["home_elo", "away_elo"], priority=0, status="implemented"),
    dict(id="R89", name="档位压制系数", category="量化模型", core="T0-T3分档→让球基准线+爆冷概率", trigger="档位差≥2", data=["home_tier", "away_tier"], priority=1, status="implemented"),
    dict(id="R119", name="赔率偏差量化信号", category="量化模型", core="外围vs体彩偏差≥3%→+1级；≥5%→+2级", trigger="偏差≥3%", data=["odds_deviation"], priority=1, status="implemented"),
    dict(id="R120", name="熵差系数", category="量化模型", core="熵差>0.2可追+1级；<0.1胶着降级", trigger="熵差阈值", data=["entropy_diff"], priority=1, status="implemented"),
    dict(id="R121", name="疲劳量化评分", category="量化模型", core="双赛+0.5/跨洲+0.8/高温+0.3/差>0.5降级", trigger="疲劳评分>0.5", data=["fatigue"], priority=0, status="missing"),
    dict(id="R122", name="舆情反向量化", category="量化模型", core="热度差>15%冷门方+1级；>25%双重修正", trigger="热度差>15%", data=["sentiment_gap"], priority=0, status="missing"),
    dict(id="R127", name="赛程密度量化", category="量化模型", core="休息<3天+0.3/跨时区+<3天+0.5", trigger="休息<3天", data=["rest_days"], priority=0, status="implemented"),
    dict(id="R129", name="同日场次传染效应", category="量化模型", core="≥3场冷门→散户追冷→庄家反向", trigger="同日≥3场冷门", data=["daily_upsets"], priority=0, status="missing"),
    dict(id="R146", name="球风相似对手映射", category="量化模型", core="直接交锋40%+球风相似35%+同级25%", trigger="球风映射权重", data=["style_similarity"], priority=2, status="missing"),
    dict(id="R45", name="让负需排除赢1球区间", category="体彩专项", core="-1盘让负=客队不败或赢2+，赢1球=让平死区", trigger="-1盘让负", data=["handicap_line"], priority=1, status="implemented"),
    dict(id="R80", name="体彩让球≠亚盘严禁混用", category="体彩专项", core="无走水/让平独立高赔/必须写精确净胜球", trigger="始终适用", data=["settle_mode"], priority=1, status="implemented"),
    dict(id="R81", name="分析前查体彩盘口", category="体彩专项", core="部分赛事不开胜平负→推单必须基于开售玩法", trigger="未开胜平负玩法", data=["available_markets"], priority=1, status="implemented"),
    dict(id="R201", name="让球结算公式", category="体彩专项", core="让(-N)净胜球制，严禁手算必须代码验证", trigger="始终适用", data=["home_score", "away_score", "handicap_line"], priority=2, status="implemented"),
    dict(id="R62", name="友谊赛收兵=被扳平", category="比赛进程", core="领先1球+轮换→被扳平+20%（仅限友谊赛）", trigger="友谊赛领先1球+轮换", data=["is_friendly", "leading_by_1"], priority=0, status="implemented"),
    dict(id="R84", name="超级替补→收兵失效", category="比赛进程", core="壮行+超级替补在板凳→收兵逻辑失效", trigger="壮行+超级替补", data=["super_sub_bench"], priority=0, status="missing"),
    dict(id="R85b", name="收兵前打穿", category="比赛进程", core="进攻效率高→30min内2球+→收兵只是走流程", trigger="30min内2球+", data=["early_goals"], priority=0, status="missing"),
    dict(id="R92", name="收兵区分主力vs替补", category="比赛进程", core="替补进球≠收兵失败", trigger="替补进球", data=["goal_scorer_role"], priority=0, status="missing"),
    dict(id="R97", name="正赛替补深度", category="比赛进程", core="替补席质量→下半场进球预期+0.3球", trigger="替补深度好", data=["has_good_bench"], priority=0, status="implemented"),
    dict(id="R109", name="正赛绝平/绝杀风险", category="比赛进程", core="1球领先+对手定位球能力→绝平加权", trigger="1球领先+定位球强", data=["leading_by_1", "opponent_setpiece"], priority=1, status="implemented"),
    dict(id="R114", name="碾压退盘=避险", category="比赛进程", core="碾压≥3项+退盘+低水→让胜优先", trigger="碾压≥3项+退盘+低水", data=["crush_count", "hdp_recede", "home_water"], priority=1, status="missing"),
    dict(id="R115", name="半场平局≠全场平局", category="比赛进程", core="正赛强队半场0-0≠全场0-0", trigger="半场0-0+强队", data=["ht_draw"], priority=0, status="implemented"),
    dict(id="R18", name="值博率", category="资金风控", core="赔率<1.60不建议做胆", trigger="赔率<1.60", data=["odds_home", "odds_away"], priority=1, status="implemented"),
    dict(id="R19", name="串关陷阱", category="资金风控", core="3串以上数学期望为负", trigger="≥3串", data=["legs"], priority=0, status="missing"),
    dict(id="R100", name="矩阵跨方向对冲", category="资金风控", core="至少1注覆盖反面；分歧0-3级→对冲0%-30%", trigger="矩阵分歧", data=["dispute_level"], priority=0, status="missing"),
    dict(id="R108", name="矩阵单场集中度≤40%", category="资金风控", core="同一场>40%=一场意外系统性摧毁矩阵", trigger="单场仓位>40%", data=["match_stake_pct"], priority=1, status="implemented"),
    dict(id="R117", name="让平集中度≤50%", category="资金风控", core="同日让平≤50%；让胜<2.10时强制选让胜", trigger="让平占比>50%", data=["draw_bet_count", "total_bet_count"], priority=2, status="implemented"),
    dict(id="R118", name="碾压+低赔让胜不可逆", category="资金风控", core="碾压≥3项+让胜<1.80→让胜不可推翻", trigger="碾压≥3项+让胜<1.80", data=["crush_count", "odds_hdp_win"], priority=2, status="implemented"),
    dict(id="R132", name="连败资金缩减", category="资金风控", core="单日亏>100减半/连亏3日暂停", trigger="单日亏>100或连亏3日", data=["daily_pnl", "losing_days"], priority=1, status="implemented"),
    dict(id="R154", name="让平限流纪律", category="资金风控", core="每日让平≤2条，不进串关锚定腿", trigger="每日让平≥2条", data=["draw_bet_count"], priority=2, status="implemented"),
    dict(id="R15", name="置信度分级", category="分析纪律", core="高≥2维度+盘口/中1维度/低有分歧", trigger="维度计数", data=["signal_dims"], priority=0, status="missing"),
    dict(id="R16", name="不强制高置信", category="分析纪律", core="实力接近标低，不勉强", trigger="实力接近", data=["elo_gap"], priority=0, status="missing"),
    dict(id="R17", name="退盘美化禁令", category="分析纪律", core="退盘=降信心，如实标注", trigger="退盘出现", data=["hdp_recede"], priority=0, status="missing"),
    dict(id="R105", name="双面验证强制+净值量化", category="分析纪律", core="每条信号0-2分打分+正反净值+禁止敷衍反面", trigger="始终适用", data=[], priority=3, status="implemented"),
    dict(id="R107", name="全局优先级仲裁", category="分析纪律", core="5层优先级+同强度仲裁+保守方向优先", trigger="始终适用", data=[], priority=3, status="implemented"),
    dict(id="R113", name="数据降权6级标尺", category="分析纪律", core="热身赛/预选赛按对手FIFA+跨洲6级降权", trigger="非正赛降权", data=["match_weight"], priority=1, status="missing"),
    dict(id="R123", name="动态触发验证", category="分析纪律", core="每推单设TRIGGER_A/B，赛中条件满足→动态调整", trigger="TRIGGER触发", data=["trigger_a", "trigger_b"], priority=0, status="missing"),
    dict(id="R131", name="推单模板+7项强制勾选", category="分析纪律", core="12项必填+7项勾选未填=推单无效", trigger="始终适用", data=["r131_checked"], priority=2, status="missing"),
    dict(id="R142", name="执行强制锁", category="分析纪律", core="三道锁：勾选+强制触发+反向测试", trigger="始终适用", data=["r131_checked", "r142_forced", "r142_selfcheck"], priority=3, status="implemented"),
    dict(id="R148", name="爆冷路径专列", category="分析纪律", core="Opta 17%数据+爆冷概率三档+5条共性", trigger="爆冷概率三档", data=["upset_prob"], priority=3, status="missing"),
    dict(id="R156", name="信号强度量化评分", category="分析纪律", core="1-10分+3条核心依据+串关联动", trigger="始终适用", data=["signal_score"], priority=2, status="missing"),
    dict(id="R157", name="串关锚定腿纪律", category="分析纪律", core="锚定腿≥8分+方向限制胜/让胜+≤3组/≤4腿", trigger="锚定腿<8分", data=["anchor_score", "legs"], priority=2, status="missing"),
    dict(id="R167", name="泊松强信号保护", category="分析纪律", core="泊松≥50%严禁翻转，只降信号", trigger="泊松概率≥50%", data=["poisson_home", "poisson_draw", "poisson_away"], priority=2, status="implemented"),
    dict(id="R169", name="让球盘精度规则", category="分析纪律", core="让胜需预期净胜球≥1.5", trigger="预期净胜球<1.5", data=["exp_goal_diff"], priority=2, status="implemented"),
    dict(id="R82", name="壮行+收兵→让平", category="附录补充", core="执行优先级链：R84→R85b→R82→R62", trigger="壮行+收兵", data=["is_farewell", "leading_by_1"], priority=0, status="missing"),
    dict(id="R90", name="模式切换", category="附录补充", core="区分友谊赛/正赛，不同模式使用不同规则权重", trigger="始终适用", data=["league", "date", "home_elo", "away_elo"], priority=1, status="implemented"),
    dict(id="R104", name="碾压判定", category="附录补充", core="碾压≥3项→对方数据必须降权（执行锁第二道）", trigger="碾压≥3项", data=["crush_count"], priority=1, status="missing"),
    dict(id="R160", name="进球值/失球值攻防对位", category="附录补充", core="个人层三档分值+团队攻防+v53九步法→净攻防差", trigger="攻防对位模型", data=["player_attack_value", "player_defense_value"], priority=2, status="missing"),
    dict(id="R166", name="降级≠翻转", category="附录补充", core="修正信号强度不等于反转方向", trigger="始终适用", data=[], priority=2, status="missing"),
    dict(id="R170", name="退盘量化修正", category="附录补充", core="6.1修正管线步骤7，退盘量化修正λ", trigger="退盘", data=["hdp_recede"], priority=1, status="missing"),
    dict(id="R171", name="铁桶对手进攻修正", category="附录补充", core="铁桶对手进攻修正 S×0.70/A×0.80/B×0.85", trigger="对手铁桶", data=["opp_style"], priority=1, status="missing"),
    dict(id="R172", name="铁桶自身进攻修正", category="附录补充", core="铁桶自身进攻修正×0.60", trigger="自身铁桶", data=["own_style"], priority=1, status="missing"),
    dict(id="R174", name="λ下限保护", category="附录补充", core="λ_floor=0.40：avg_scored≥1.5且style≠纯弱型→λ最低0.40", trigger="λ<0.40", data=["lam_h", "lam_a"], priority=1, status="missing"),
    dict(id="R177", name="防守底线", category="附录补充", core="defense=max(avg_conceded, 0.50)/LEAGUE_AVG", trigger="防守<0.5", data=["avg_conceded"], priority=1, status="missing"),
    dict(id="R178", name="间歇期λ修正(韩职)", category="附录补充", core="韩职间歇后进球暴涨λ×1.3，R46暂停用盘口线", trigger="韩职间歇期", data=["league", "after_break"], priority=1, status="missing"),
    dict(id="R184", name="间歇期λ修正(芬瑞)", category="附录补充", core="芬超/瑞超间歇后骤降λ×0.70", trigger="芬瑞间歇期", data=["league", "after_break"], priority=1, status="missing"),
    dict(id="R215", name="盘路铁律(韩职)", category="附录补充", core="韩职96场60.4%小+56.2%下盘", trigger="韩职盘路", data=["league"], priority=0, status="missing"),
    dict(id="R261", name="双轨推单系统", category="附录补充", core="轨道A胜平负方向+轨道B让球方向，星级评定", trigger="始终适用", data=[], priority=2, status="missing"),
]

# 已实现规则ID集合
IMPLEMENTED = {r["id"] for r in RULES if r["status"] == "implemented"}


def by_id(rule_id):
    """按编号查规则。"""
    for r in RULES:
        if r["id"] == rule_id:
            return r
    return None


def by_category(category=None):
    """按分类过滤（缺省返回全部）。"""
    if category is None:
        return list(RULES)
    return [r for r in RULES if r["category"] == category]


def summary():
    """分类统计：总数/已实现/缺失。"""
    cats = {}
    for r in RULES:
        c = cats.setdefault(r["category"], {"total": 0, "implemented": 0})
        c["total"] += 1
        if r["status"] == "implemented":
            c["implemented"] += 1
    return cats


def missing_high_priority(min_priority=1):
    """缺失的高优先级规则列表。"""
    return [r for r in RULES if r["status"] == "missing" and r["priority"] >= min_priority]


if __name__ == "__main__":
    s = summary()
    n_total = sum(v["total"] for v in s.values())
    n_impl = sum(v["implemented"] for v in s.values())
    print(f"规则总数: {n_total}, 已实现: {n_impl}, 缺失: {n_total - n_impl}")
    for cat, v in s.items():
        print(f"  {cat}: {v['total']}条 (已实现 {v['implemented']})")
    print("\n缺失高优先级:")
    for r in missing_high_priority(1):
        print(f"  {r['id']} [{r['priority']}星] {r['name']}")