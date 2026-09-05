# -*- coding: utf-8 -*-
"""全局配置：路径、联赛映射、模型与策略参数。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA = {
    "json": ROOT / "data" / "raw" / "football_data" / "football_data_collected.json",
    "recent_csv": ROOT / "data" / "raw" / "football_data" / "football_data_recent.csv",
    "espn_dir": ROOT / "data" / "raw" / "espn",
    "combined_eu_mls": ROOT / "data" / "raw" / "combined_eu_mls.csv",
}

# football-data.co.uk Div -> 中文联赛名
DIV_CN = {
    "E0": "英超", "E1": "英冠", "E2": "英甲", "E3": "英乙",
    "SP1": "西甲", "SP2": "西乙",
    "D1": "德甲", "D2": "德乙",
    "I1": "意甲", "I2": "意乙",
    "F1": "法甲", "F2": "法乙",
    "N1": "荷甲", "P1": "葡超", "T1": "土超",
}

# 中文联赛名 -> 规范 key（统一多源命名）
CN_CANON = {
    "英超": "E0", "英冠": "E1", "英甲": "E2", "英乙": "E3",
    "西甲": "SP1", "西乙": "SP2",
    "德甲": "D1", "德乙": "D2",
    "意甲": "I1", "意乙": "I2",
    "法甲": "F1", "法乙": "F2",
    "荷甲": "N1", "葡超": "P1", "土超": "T1",
    "比利时甲": "B1", "巴西甲": "BR", "希腊超": "G1",
    "瑞士超": "CH", "丹麦超": "DNK", "奥地利超": "AUT",
    "挪威超": "NO1", "瑞典超": "SWE", "罗马尼亚甲": "ROU", "波兰超": "POL",
    "苏超": "SC1", "俄超": "RU1", "墨超": "MX1", "日职": "JP1",
    "美职联": "MLS", "韩K": "KR1", "澳超": "AUS",
}

FEATURES = {
    "form_window": 5,
    "min_matches": 3,
    "h2h_window": 5,
    "decay_halflife": 60,
}

MODEL = {
    "test_days": 60,
    "train_days": 730,
    "min_train": 500,
    # 联赛级主场优势校准: MLS 近年主胜率(44.2%)低于全史(49.6%), 下调主场λ (2026-08-29)
       "league_home_adj": {"MLS": 0.92, "KR1": 1.07,
                           "N1": 0.97, "B1": 0.97, "P1": 0.98, "JP1": 0.95},
    # 泊松攻防强度时间衰减半衰期(天)。刻意与 FEATURES.decay_halflife(60) 不同:
    # 泊松聚合长期攻防强度用长半衰期, 特征捕捉近期状态用短半衰期。
    # 实测统一为 60 使回测 ROI 恶化约 1.1pp(2026-08-28), 故各自独立配置。
    "poisson_half_life": 200,
    # ===== 双轨实验开关 (2026-09-03) =====
    # 默认全部 False: 生产路径与旧版完全一致, 实验新模型不污染主链路。
    # 开启后请走实验函数壳, 跑完 walk-forward A/B + 回归全绿再决定切换。
    "strength_v2": False,   # 旧占位壳(实验,数值=旧输出); 真开关见 strength_v2_leagues
    "elo_pi": False,        # penaltyblog Pi 评分替代 Elo -> elo.pi_history(占位=Elo)
    # 联赛级白名单路由(2026-09-03 A/B 结论): 命中净正/RPS 胜出的联赛走 fit_league_opp.
    # 覆盖方式: 环境变量 STRENGTH_V2_LEAGUES=逗号分隔 或直接改此表(空表=全旧).
    # 开: 五大+比甲+沙超+英甲+土超+挪超+瑞超+丹超+K1+阿甲+墨超+中超; 不开: MLS/POL/E3(浅).
    "strength_v2_leagues": [
        "E0", "SP1", "D1", "I1", "F1", "B1", "SAU",
        "E2", "T1", "NO1", "SWE", "DNK", "KR1", "ARG", "MX1", "CH",
    ],
    "xgb": {
        "n_estimators": 200, "max_depth": 4, "learning_rate": 0.03,
        "subsample": 0.7, "colsample_bytree": 0.8, "min_child_weight": 1,
        "reg_lambda": 1.0, "objective": "binary:logistic",
        "eval_metric": "logloss", "n_jobs": 4,
    },
}

STRATEGY = {
    "min_edge": 0.03,
    "min_ev": 0.01,          # 亚盘最小期望收益(单位本金), 见 ah_backtest.py
    "kelly_fraction": 0.25,
    "max_stake_pct": 0.05,
    "daily_loss_stop": 0.20,
    "max_parlay_legs": 6,
    "min_prob": 0.35,
    "max_corr": 0.25,
    "poisson_goals_cap": 4.5,
    "conf_n_eff_k": 10.0,   # 连续仓位调制半饱和常数: n_eff=k 时仓位减半
}

SEARCH = {
    # 后端: "ark" = 方舟模型联网问答(推荐, 用 ARK_API_KEY);
    #       "search_infinity" = 联网搜索控制台 WebSearch API(需单独创建 Key)
    "backend": "ark",
    "count": 5,
    "max_queries": 4,
    "per_query_sleep": 1.0,
    "time_range": "OneWeek",
    "auth_level": 0,
    "query_rewrite": True,
    "ark": {
        "max_output_tokens": 2048,
    },
}

ODDS = {
    # 默认盘口源: "recent"(近期均盘近似) / 接入后改为 live 源名(如 "theoddsapi")
    "default_source": "composite",  # 2026-08-28 多源混合(theoddsapi+infersports+bsd 共识); 全失败降级 recent
    # 多源混合顺序(composite 源依次查询; 可按配额/覆盖调整)
    "composite_sources": ["theoddsapi", "infersports", "bsd"],
    # 兜底补充源: 前序源全失败才查(API-Football 100次/天, 省配额)
    "composite_fill": ["apifootball"],
    # 本地规范联赛 key -> API-Football 联赛 id(标准 id)
    "apifb_league_map": {
        "E0": 39, "E1": 40, "E2": 41, "E3": 42,
        "SP1": 140, "SP2": 141,
        "D1": 78, "D2": 79,
        "I1": 135, "I2": 136,
        "F1": 61, "F2": 62,
        "N1": 88, "P1": 94, "T1": 203,
        "B1": 144, "BR": 71, "G1": 197,
        "CH": 180, "DNK": 119, "AUT": 218,
        "NO1": 103, "SWE": 113, "POL": 106,
        "SC1": 179, "RU1": 235, "MX1": 262,
        "JP1": 98, "MLS": 253, "KR1": 292, "AUS": 188,
    },
    # 估计赔率最小 overround(兜底用, 防止估计概率过满)
    "overround_floor": 1.03,
    # live 源 API 超时(秒)与重试次数
    "timeout": 30,
    "retries": 2,
    # TheOddsAPI 球队名 -> 本地规范球队名(football-data 缩写风格; 实测无法自动匹配时补)
    "team_alias": {
        # 英超 E0
        "Manchester City": "Man City",
        "Manchester United": "Man United",
        "Tottenham Hotspur": "Tottenham",
        "West Ham United": "West Ham",
        "Wolverhampton Wanderers": "Wolves",
        "Wolves": "Wolves",
        "Brighton & Hove Albion": "Brighton",
        "Brighton and Hove Albion": "Brighton",
        "Nottingham Forest": "Nott'm Forest",
          "Newcastle United": "Newcastle",
          # 丹超 DNK (2026-09-03: BSD 名 -> football-data 本地名, 修复 AGF/FCK 类"无数据"误报)
          "AGF": "Aarhus",
          "Aalborg BK": "Aalborg",
          "FC København": "FC Copenhagen",
          "FC Nordsjælland": "Nordsjaelland",
          "FC Midtjylland": "Midtjylland",
          "Brøndby IF": "Brondby",
          "Viborg FF": "Viborg",
          "Silkeborg IF": "Silkeborg",
          "SønderjyskE": "Sonderjyske",
          "Vejle BK": "Vejle",
          "Lyngby BK": "Lyngby",
          "Odense BK": "Odense",
          "Esbjerg fB": "Esbjerg",
          "FC Helsingør": "Helsingor",
          # 西甲 SP1
        "Athletic Bilbao": "Ath Bilbao",
        "Atletico Madrid": "Ath Madrid",
        "Espanyol": "Espanol",
        "Real Sociedad": "Sociedad",
        "Rayo Vallecano": "Vallecano",
        # 德甲 D1
        "Eintracht Frankfurt": "Ein Frankfurt",
        "FC Cologne": "FC Koln",
        "Koln": "FC Koln",
        "Cologne": "FC Koln",
        "Borussia Monchengladbach": "M'gladbach",
        "Borussia Mönchengladbach": "M'gladbach",
        "Bayer Leverkusen": "Leverkusen",
        # 意甲 I1
        "AC Milan": "Milan",
        "Inter Milan": "Inter",
        # 法甲 F1
        "Paris Saint Germain": "Paris SG",
        "Paris Saint-Germain": "Paris SG",
        "Saint Etienne": "St Etienne",
        "Saint-Etienne": "St Etienne",
        "Olympique Lyonnais": "Lyon",
        "Stade Brestois": "Brest",
        "Stade Brestois 29": "Brest",
        # 巴甲 BR
        "Atlético Mineiro": "Atletico-MG",
        "Atletico Mineiro": "Atletico-MG",
        # 德甲 D1(补充)
        "Hamburger SV": "Hamburg",
        # MLS
        "LA Galaxy": "Los Angeles Galaxy",
        # 中超 CH
        "Zhejiang": "Zhejiang Professional",
        "Henan FC": "Henan Songshan Longmen",
        # BSD 全名 -> 本地规范名(2026-08-30 扫描队名修复)
        "Olympique de Marseille": "Marseille",
        "SSC Napoli": "Napoli",
        "Tromsø IL": "Tromso",
        "Sandefjord Fotball": "Sandefjord",
        "IK Start": "Start",
        "Aalesunds FK": "Aalesund",
        "Kasımpaşa": "Kasimpasa",
        "Widzew Łódź": "Widzew Lodz",
        "AD Ceuta": "Ceuta",
        "KVC Westerlo": "Westerlo",
        "SV Zulte Waregem": "Waregem",
        "CF Estrela Amadora": "Estrela",
        "Deportivo de A Coruña": "La Coruna",
        "Royale Union Saint-Gilloise": "St. Gilloise",
        "Başakşehir FK": "Buyuksehyr",
        # 2026-08-30 build_team_master 补充
        "1. FC Köln": "FC Koln",
        "1. FSV Mainz 05": "Mainz",
        "Wolverhampton": "Wolves",
        "Shenzhen Peng City": "Shenzhen Xinpengcheng",
        "Deportivo Alavés": "Alaves",
        "Grenoble Foot 38": "Grenoble",
        "Sporting Gijón": "Sp Gijon",
        "Standard Liège": "Standard",
        "JEF United Chiba": "JEF United Ichihara-Chiba",
        "Tokyo Verdy": "Tokyo Verdy 1969",
        "Santos Laguna": "Santos",
        "Albacete Balompié": "Albacete",
        "Viborg FF": "Viborg",
        "Sønderjyske Fodbold": "Sonderjyske",
        "Rodez AF": "Rodez",
        "Stade Lavallois": "Laval",
        "USL Dunkerque": "Dunkerque",
        "RC Sporting Charleroi": "Charleroi",
        "KRC Genk": "Genk",
        "RSC Anderlecht": "Anderlecht",
        # 2026-08-30 杯赛/欧战队伍: 本地对应联赛名确认
        "FK Csíkszereda Miercurea Ciuc": "Csikszereda M. Ciuc",
        "Sepsi OSK Sfântu Gheorghe": "Sepsi Sf. Gheorghe",
        "CFR 1907 Cluj": "CFR Cluj",
        "Universitatea Craiova": "Univ. Craiova",
        "FC Petrolul Ploiești": "Petrolul",
        "SC Oțelul Galați": "Otelul",
        "Eintracht Braunschweig": "Braunschweig",
        "VfL Bochum 1848": "Bochum",
        "SK Rapid Wien": "SK Rapid",
        "Asteras Aktor": "Asteras Tripolis",
        "Hokkaido Consadole Sapporo": "Consadole Sapporo",
        "Çaykur Rizespor": "Rizespor",
        "KAA Gent": "Gent",
        "Jagiellonia Białystok": "Jagiellonia",
        "Willem II Tilburg": "Willem II",
    },
    # 中文队名 -> 本地规范名(匹配链第一级; 覆盖高频队伍)
    "cn_alias": {
        "曼城": "Man City", "曼联": "Man United", "阿森纳": "Arsenal",
        "切尔西": "Chelsea", "利物浦": "Liverpool", "热刺": "Tottenham",
        "托特纳姆": "Tottenham", "皇马": "Real Madrid", "皇家马德里": "Real Madrid",
        "巴萨": "Barcelona", "巴塞罗那": "Barcelona", "马竞": "Ath Madrid",
        "马德里竞技": "Ath Madrid", "塞维利亚": "Sevilla", "尤文": "Juventus",
        "尤文图斯": "Juventus", "国米": "Inter", "国际米兰": "Inter",
        "AC米兰": "Milan", "米兰": "Milan", "那不勒斯": "Napoli",
        "罗马": "Roma", "拉齐奥": "Lazio", "亚特兰大": "Atalanta",
        "瓦伦西亚": "Valencia", "毕尔巴鄂": "Ath Bilbao", "贝蒂斯": "Real Betis",
        "比利亚雷亚尔": "Villarreal", "拜仁": "Bayern Munich", "拜仁慕尼黑": "Bayern Munich",
        "多特": "Dortmund", "多特蒙德": "Dortmund", "莱比锡": "RB Leipzig",
        "勒沃库森": "Bayer Leverkusen", "法兰克福": "Eintracht Frankfurt",
        "巴黎": "Paris SG", "巴黎圣日耳曼": "Paris SG", "马赛": "Marseille",
        "里昂": "Lyon", "摩纳哥": "Monaco", "阿贾克斯": "Ajax",
        "波尔图": "Porto", "本菲卡": "Benfica", "费内巴切": "Fenerbahce",
        "狼队": "Wolves", "纽卡": "Newcastle", "西汉姆": "West Ham",
        "埃弗顿": "Everton", "阿斯顿维拉": "Aston Villa", "布莱顿": "Brighton",
        "水晶宫": "Crystal Palace", "莱斯特城": "Leicester",
        "南安普顿": "Southampton", "伯恩茅斯": "Bournemouth",
        "富勒姆": "Fulham", "伊普斯维奇": "Ipswich Town",
        "布莱克本": "Blackburn", "诺丁汉森林": "Nott'm Forest",
    },
    # TheOddsAPI sport key -> 本地规范 key(CN_CANON 的 key, 如 E0/SP1/SWE)
    "league_map": {
        "soccer_epl": "E0", "soccer_efl_champ": "E1",
        "soccer_england_league1": "E2", "soccer_england_league2": "E3",
        "soccer_spain_la_liga": "SP1", "soccer_spain_segunda_division": "SP2",
        "soccer_germany_bundesliga": "D1", "soccer_germany_bundesliga2": "D2",
        "soccer_italy_serie_a": "I1", "soccer_italy_serie_b": "I2",
        "soccer_france_ligue_one": "F1", "soccer_france_ligue_two": "F2",
        "soccer_netherlands_eredivisie": "N1", "soccer_portugal_primeira_liga": "P1",
        "soccer_turkey_super_league": "T1", "soccer_belgium_first_div": "B1",
        "soccer_brazil_campeonato": "BR", "soccer_greece_super_league": "G1",
        "soccer_switzerland_superleague": "CH", "soccer_denmark_superliga": "DNK",
        "soccer_austria_bundesliga": "AUT", "soccer_norway_eliteserien": "NO1",
        "soccer_sweden_allsvenskan": "SWE", "soccer_poland_ekstraklasa": "POL",
        "soccer_spl": "SC1", "soccer_russia_premier_league": "RU1",
        "soccer_mexico_ligamx": "MX1", "soccer_japan_j_league": "JP1",
        "soccer_usa_mls": "MLS", "soccer_korea_kleague1": "KR1",
        "soccer_china_superleague": "CH",
    },
}
