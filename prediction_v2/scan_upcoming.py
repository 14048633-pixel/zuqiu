# -*- coding: utf-8 -*-
"""即将开赛批量扫描（数据缺口分层兜底版 v2）
数据源: football_data_recent(3季) + matches_2015_2025(2024/25,2025/26) + matches_2023_2024
兜底层级: 当季数据(1.0) > 上季(0.7) > 旧季(0.4,低置信) > 市场隐含λ(无独立信号) > 联赛基准(无盘口)
best_bet 仅允许: 双方均有 >=2024/25 赛季独立攻防数据的场次
"""
import json, io, os, sys, math, csv, collections, unicodedata, urllib.request, re
from datetime import datetime, timezone, timedelta

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src", "features"))
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
sys.path.insert(0, os.path.join(ROOT, "src", "strategy"))
sys.path.insert(0, os.path.join(ROOT, "src", "rules"))
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snapshot_guard import snapshot_staleness, is_future_snapshot

SNAPSHOT_STALE_HOURS = float(os.environ.get("ODDS_SNAPSHOT_STALE_HOURS", "12") or 12)
# 概率封顶校准(2026-08-17 101注实盘复盘): 模型概率>65%档系统性高估15-25pp(市场更准),
# 单腿概率压至 PROB_CAP, EV按封顶重算; 可用环境变量 PROB_CAP 覆盖 (0~1)
PROB_CAP = float(os.environ.get("PROB_CAP", "0.65") or 0.65)
# 联赛高价值档禁出(2026-08-17 star2拆解: 英冠/比甲/荷甲/智利甲/德乙/葡超/J1 标准+高价值档全负ROI)
HIGH_TIER_BAN_LEAGUES = set(x.strip() for x in os.environ.get("HIGH_TIER_BAN_LEAGUES",
    "英冠,比甲,荷甲,智利甲,德乙,葡超,J1").split(",") if x.strip())
# 让球主/小球 概率禁带: 原始概率∈[0.65,0.70) 实测命中仅21.9%, 不纳入候选
PROB_BAN_LO = float(os.environ.get("PROB_BAN_LO", "0.65") or 0.65)
PROB_BAN_HI = float(os.environ.get("PROB_BAN_HI", "0.70") or 0.70)
MAX_MKT_DIVERGENCE = float(os.environ.get("MAX_MKT_DIVERGENCE", "0.20"))
# ===== 平局预警(2026-08-19 3万场实证: 市场去水平局>=26% 平局率29.3% vs 基线26.1%; 买平ROI≈0 只降星/降仓/标注, 不出平局单) =====
DRAW_WARN_MIN = float(os.environ.get("DRAW_WARN_MIN", "0.26") or 0.26)        # 市场去水平局概率阈值
DRAW_WARN_STRONG = float(os.environ.get("DRAW_WARN_STRONG", "0.30") or 0.30)  # 强预警(平局率>=32%)
DRAW_WARN_STAKE_MULT = 0.5                                                     # 命中预警: 仓位减半
# ===== 2026-08-23 三条规则(43场复盘 M-20260823-01/02/03): ①平局预警26%+让球只用+号 ②小2.50高EV反向标记 ③整球盘2.50遇预警降星 =====
DRAW_WARN_HDP_PLUS_ONLY = True                                                # ① 平局预警激活时, 让球仅保留+号受让方(-号让球腿移除)
DRAW_WARN_TOTALS_LINE = 2.5                                                    # ③ 整球盘线: 2.50 遇预警降星
SMALL_250_HIGH_EV = float(os.environ.get("SMALL_250_HIGH_EV", "0.20") or 0.20) # ② 小2.50 高EV反向标记阈值(实证30-44%全错)
# 规则⑪(2026-08-27 300场复盘+账本实证): 低估区禁小球联赛 — 小球只在λ高估区推, 低估区(模型λ系统性偏低)禁小球
#   触发: ① league_calib ou_under_reverse=True(英冠/荷甲) ② 杯赛/资格赛实测λ低估区(300场复盘+近期扫描偏差) ③ 实测场均>配置基准(数据驱动)
#   实证: 300场复盘 英冠小球20%/荷甲0%/德国杯0%; 账本 英冠31%/荷甲22%/英联杯0%/欧冠0%; 08-27 AEK小2.50(4-0)/美洲小2.25(4-2) 出大全灭
LOW_EST_UNDER_BAN_SMALL = {"德国杯", "英联杯", "欧冠", "欧联杯", "欧协联"}
# ===== 2026-08-24 用户指令: 让球+/−方向按球队强弱判定(不统一客队; 受让方=弱队+号, 让球方=强队-号) =====
HDP_PLUS_BY_STRENGTH = True          # 方向按盘口强弱判定开关
HDP_BAN_DRAW = 0.0                   # 平手盘禁出(陷阱, 账本平手/浅受让-42%)
HDP_BAN_GIVE_DEEP = -1.0             # 让球方深盘让 hdp<=-1.0 禁出(穿盘率低, 账本深盘-33%)
HDP_BAN_RECEIVE_DEEP = 1.8           # 受让方深受让 hdp>=+1.8 禁出(账本+1.8/+2.0全亏)
# ===== 2026-08-24 规则⑧: 赔率高估区(账本831注实证: 主胜1.8-2.2真实28%/客胜2.2-2.8真实11%, 高估区受让+号赢盘72-78%) =====
FAV_HOME_OVEREST_LO = 1.8             # 主胜赔率高估区下界
FAV_HOME_OVEREST_HI = 2.2             # 主胜赔率高估区上界
FAV_AWAY_OVEREST_LO = 2.2             # 客胜赔率高估区下界
FAV_AWAY_OVEREST_HI = 2.8             # 客胜赔率高估区上界
OVEREST_RECEIVE_HDP_MAX = 0.8         # 仅浅受让 +0.0~+0.8 享受加权重
OVEREST_RECEIVE_STAR_BOOST = 1        # 高估区受让+号加星
OVEREST_RECEIVE_STAKE_MULT = 1.5      # 高估区受让+号仓位加成
OVEREST_GIVE_STAKE_MULT = 0.5         # 高估区让球-号降仓

from poisson_lambda import calc_lambdas, DEFAULT_LAM_MIN, DEFAULT_LAM_MAX, _to_float
import coach_quant as cq
from prob_calibration import dc_score_grid, apply_prob_calibration
from upset_engine_v2 import UpsetEngineV2

DIV_BY_LEAGUE = {"英超": "E0", "西甲": "SP1", "德甲": "D1", "意甲": "I1", "法甲": "F1",
                 "英冠": "E1", "德乙": "D2", "荷甲": "N1", "西乙": "SP2", "J1": "JP1", "中超": "C1", "葡超": "P1", "比甲": "B1", "英乙": "E3", "瑞超": "SW", "挪超": "NO", "巴甲": "BR", "阿甲": "AR", "美职": "ML", "土超": "TK", "墨超": "MX", "智利甲": "CH", "丹超": "DK", "意乙": "I2", "法乙": "F2",
                 # 快照英文联赛名 -> div (2026-08-21 修复: 此前英文名全部 div=None -> 跨联赛错配, 如哥甲Jaguares错配西乙Cordoba)
                 "Premier League": "E0", "Ligue 1": "F1", "Ligue 2": "F2",
                 "Segunda División": "SP2", "Trendyol Super Lig": "TK",
                 "Pro League": "B1", "Allsvenskan": "SW", "DFB Pokal": "D1",
                 "Ekstraklasa": "PL", "Parva Liga": "BG", "Liga Portugal 2": "P2",
                 "Veikkausliiga": "FI", "Superliga": "RO", "沙超": "SA", "哥甲": "CO"}
ALL_DIVS = ("E0", "E1", "E2", "E3", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "N2", "JP1", "C1", "P1", "B1", "SW", "NO", "BR", "AR", "ML", "TK", "MX", "CH", "DK",
             "CO", "BG", "P2", "FI", "PL", "RO", "SA")
CAL = {
    "英超": {"league_avg": 2.8719, "rho": 0.0, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "西甲": {"league_avg": 2.5811, "rho": 0.0, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "德甲": {"league_avg": 3.1654, "rho": -0.04, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9, "lam_max": 5.0},
    "意甲": {"league_avg": 2.6968, "rho": -0.07, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "法甲": {"league_avg": 2.7624, "rho": -0.05, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
}

SEASON_WEIGHT = {"2026/2027": 1.0, "2026": 1.0, "2025/2026": 1.0, "2024/2025": 0.7, "2023/2024": 0.4,
                 "2022/2023": 0.2, "2021/2022": 0.1}
SRC_TAG = {"2026/2027": "cur", "2026": "cur", "2025/2026": "cur", "2024/2025": "prev",
           "2023/2024": "old", "2022/2023": "old", "2021/2022": "old"}
INDEP_MIN_WEIGHT = 0.7  # >=2024/25 才视为独立攻防，允许出 best_bet

# ===== 第一类: 过滤门槛分层 =====
EV_TIER_BATCH = 0.05     # 纯数据批量扫描(无伤停/轮换情报): 有效EV门槛, 0~5%放弃
EV_TIER_INTEL = 0.08     # 完整情报(伤停/轮换/多盘齐全): 原标准
ODDS_FLOOR_MAIN = 1.60   # 主流联赛赔率下限
ODDS_FLOOR_SEC = 1.40    # 次级联赛赔率下限
SECONDARY_LEAGUES = {"英冠", "德乙", "荷甲", "西乙", "英乙", "瑞超", "挪超", "巴甲", "阿甲", "美职", "土超", "墨超", "智利甲", "丹超", "意乙", "法乙",
                      "Ekstraklasa", "Parva Liga", "Liga Portugal 2", "Veikkausliiga", "Superliga", "沙超", "哥甲"}
EV_TIERS = [("高价值", 0.20, 1.0), ("标准", 0.08, 0.7), ("观察", 0.05, 0.3), ("垃圾", 0.0, 0.0)]
HAS_INTEL = False        # 批量纯数据扫描=False(用batch门槛); 人工补伤停情报后=True(intel门槛)

# ===== BSD市场基准交叉验证 (Step8 λ / Step31 双口径EV) =====
BSD_LAM_DEV_TOL = 0.5    # 我们λ vs BSD expected_goals 单侧偏差>0.5球 -> 标"模型独立观点"
BSD_OU_LINES = {1.5: "over_15_goals", 2.5: "over_25_goals", 3.5: "over_35_goals"}
BSD_CONF_SUPPORT = 0.60   # BSD同方向且conf>=0.60 -> 共识支持(保留出单)
BSD_CONF_DIVERGE = 0.45   # BSD同方向但conf<0.45 或 反向 -> 降星+分歧标签
BSD_PRED_OU = {1.5: "prob_over_15", 2.5: "prob_over_25", 3.5: "prob_over_35"}

# ===== 第二类: 升班马/跨联赛攻防收缩 + 样本分层 =====
PROMO_SHRINK = 0.30      # 升班马/降级队/跨联赛数据: 攻防向联赛均值收缩30%
SAMPLE_FULL_N = 8        # >=8场 原始攻防完整使用
SAMPLE_SHRINK_N = 4      # 4~7场 收缩30%保留自有数据; <4场 才降级联赛基准

def effective_rate(x, avg, xd, n):
    # 攻防修正链(模块级, 供回归测试): 升班马/跨联赛收缩30% -> 样本分层(>=8原始/4-7收缩30%/<4联赛基准). 返回(值, 低样本标记)
    v = avg + (x - avg) * (1.0 - PROMO_SHRINK) if xd else x
    low = False
    if n is not None:
        if n < SAMPLE_SHRINK_N:
            v, low = avg, True
        elif n < SAMPLE_FULL_N:
            v, low = avg + (v - avg) * 0.7, True
    return round(v, 3), low

# ===== 第五类: 分联赛泊松校准(单源配置, 可被 league_calib.json 覆盖) =====
_CAL_DEFAULT = {
    "英超": {"league_avg": 2.8719, "rho": 0.0,   "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "西甲": {"league_avg": 2.5811, "rho": 0.0,   "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "德甲": {"league_avg": 3.1654, "rho": -0.04, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "意甲": {"league_avg": 2.6968, "rho": -0.07, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "法甲": {"league_avg": 2.7624, "rho": -0.05, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "英冠": {"league_avg": 2.6051, "rho": -0.05, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "德乙": {"league_avg": 2.9314, "rho": -0.05, "shrink": 0.8, "home": 1.08, "away": 0.95, "fatigue": 0.9},
    "荷甲": {"league_avg": 3.1765, "rho": 0.0,   "shrink": 0.8, "home": 1.05, "away": 0.95, "fatigue": 0.9, "lam_max": 5.2},
    "西乙": {"league_avg": 2.6320, "rho": -0.04, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 0.9},
    "J1": {"league_avg": 3.35, "rho": 0.0, "shrink": 0.8, "home": 1.0, "away": 1.0, "fatigue": 0.9},
    "中超": {"league_avg": 3.035, "rho": -0.04, "shrink": 0.8, "home": 1.13, "away": 0.93, "fatigue": 1.0},
    "葡超": {"league_avg": 2.68, "rho": -0.05, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 1.0},
    "比甲": {"league_avg": 2.68, "rho": -0.05, "shrink": 0.8, "home": 1.1, "away": 0.95, "fatigue": 1.0},
}

def handicap_cover_prob(grid, hdp):
    """主队让球覆盖概率(hdp带符号: 负=主让, 正=主受). 整数盘走盘计0.5.
    修复abs归一化丢失符号, 把主让-0.5当主受+0.5算导致EV虚高的问题."""
    def _p(cond):
        n = len(grid)
        return sum(grid[i][j] for i in range(n) for j in range(n) if cond(i, j))
    if abs(abs(hdp) - round(abs(hdp))) < 0.01:
        push = _p(lambda i, j: abs((i - j) + hdp) < 0.01)
        return _p(lambda i, j: (i - j) + hdp > 0) + push * 0.5
    return _p(lambda i, j: (i - j) + hdp > 0)

def _load_league_calib():
    """加载 strategy_data/league_calib.json (分联赛校准, 第五类); 缺失时回退内置默认."""
    _p = os.path.join(ROOT, "strategy_data", "league_calib.json")
    if not os.path.exists(_p):
        return dict(_CAL_DEFAULT)
    try:
        _d = json.load(io.open(_p, encoding="utf-8")).get("leagues", {})
    except Exception:
        return dict(_CAL_DEFAULT)
    out = dict(_CAL_DEFAULT)
    out.update({k: dict(v) for k, v in _d.items() if isinstance(v, dict)})
    return out

# 联赛基准偏差检查(第五类): 配置league_avg vs 近30场实测, 偏差>0.3球 -> λ基准向实测平移50%
LEAGUE_AVG_DEV_TOL = 0.30
LEAGUE_AVG_SHIFT_W = 0.50
LEAGUE_AVG_RECENT_N = 30
LEAGUE_AVG_MIN_N = 4          # 赛季初降门槛: 当前赛季样本>=4场即启用(原10, 防新赛季高进球被旧数据稀释)
_LIVE_AVG_CACHE_PATH = os.path.join(ROOT, "data", "raw", "football_data", "live_recent_avg.json")
_LIVE_AVG_MAX_AGE_MIN = 240   # 实时基准缓存有效期(分钟), 防烧the-odds-api额度
_LIVE_AVG_TIMEOUT = 8
_LIVE_AVG_LEAGUES = None      # 本次扫描涉及联赛集合(main设置); None=不拉实时(回归/离线兜底)

CAL = _load_league_calib()

def _load_cup_coeffs():
    """加载 league_calib.json 的 cup_coeffs 组(杯赛主客场/疲劳/ρ); 缺失返回空."""
    _p = os.path.join(ROOT, "strategy_data", "league_calib.json")
    try:
        _d = json.load(io.open(_p, encoding="utf-8")).get("cup_coeffs", {})
        return {k: dict(v) for k, v in _d.items() if isinstance(v, dict)}
    except Exception:
        return {}

CUP_COEFFS = _load_cup_coeffs()

def _cal_for_league(lg):
    """杯赛自动切换: 先匹配具体杯赛(cup_coeffs 内同名/包含), 未命中且含"杯"才走国内杯兜底.
    顺序重要: 欧联杯/欧协联杯/意杯等有独立参数必须优先命中, 否则会被国内杯 3.28 抢先."""
    for key, cc in CUP_COEFFS.items():
        if key != "国内杯" and (key in lg or lg in key):
            return dict(cc)
    if "杯" in lg and "国内杯" in CUP_COEFFS:
        return dict(CUP_COEFFS["国内杯"])
    return None

_RECENT_AVG_CACHE = None


def _load_env_keys():
    """the-odds-api keys 优先级列表(1/2/3/旧): 环境变量优先, 兜底解析 .env, 去除行内注释."""
    def _clean(v):
        v = v.strip()
        if "#" in v:  # 行内注释 (如 "key   # 主源")
            v = v.split("#", 1)[0].strip()
        return v
    keys = []
    for k in ("ODDS_API_KEY_1", "ODDS_API_KEY_2", "ODDS_API_KEY_3", "ODDS_API_KEY"):
        v = os.environ.get(k)
        if v and _clean(v):
            keys.append(_clean(v))
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        try:
            for line in io.open(p, encoding="utf-8"):
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                if k in ("ODDS_API_KEY_1", "ODDS_API_KEY_2", "ODDS_API_KEY_3", "ODDS_API_KEY"):
                    cv = _clean(v)
                    if cv and cv not in keys:
                        keys.append(cv)
        except Exception:
            pass
    return keys


def _pick_working_key():
    """探测第一个有额度的key(真实scores请求, 额度耗尽会401), 进程内记忆. 全失败返回""."""
    if getattr(_pick_working_key, "_key", None):
        return _pick_working_key._key
    probe_url = "https://api.the-odds-api.com/v4/sports/soccer_epl/scores/?apiKey=%s&daysFrom=1&dateFormat=iso"
    for k in _load_env_keys():
        try:
            req = urllib.request.Request(probe_url % k, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                resp.read(1024)
            _pick_working_key._key = k
            return k
        except Exception:
            continue
    return ""


def _sport_key_map():
    """联赛名 -> the-odds-api sport key(用于实时比分拉取). 优先读 live_odds, 失败用内置兜底表."""
    mp = {}
    try:
        from src.live_odds import LEAGUE_SPORT_KEYS
        mp = dict(LEAGUE_SPORT_KEYS)
    except Exception:
        mp = {"英超": "soccer_epl", "西甲": "soccer_spain_la_liga", "意甲": "soccer_italy_serie_a",
              "德甲": "soccer_germany_bundesliga", "法甲": "soccer_france_ligue_one", "英冠": "soccer_efl_champ",
              "西乙": "soccer_spain_segunda_division", "德乙": "soccer_germany_bundesliga2",
              "荷甲": "soccer_netherlands_eredivisie", "J1": "soccer_japan_j_league", "中超": "soccer_china_superleague",
              "葡超": "soccer_portugal_primeira_liga", "比甲": "soccer_belgium_first_div", "英乙": "soccer_england_league2",
              "瑞超": "soccer_sweden_allsvenskan", "挪超": "soccer_norway_eliteserien", "巴甲": "soccer_brazil_campeonato",
              "阿甲": "soccer_argentina_primera_division", "美职": "soccer_usa_mls", "土超": "soccer_turkey_super_league",
              "墨超": "soccer_mexico_ligamx", "智利甲": "soccer_chile_campeonato", "丹超": "soccer_denmark_superliga",
              "意乙": "soccer_italy_serie_b", "法乙": "soccer_france_ligue_two"}
    return {k: v for k, v in mp.items()}


def set_live_avg_leagues(leagues):
    """main扫描前指定本次涉及的联赛, 实时基准只拉这些(省API额度); 回归/离线不设置则只走CSV."""
    global _LIVE_AVG_LEAGUES
    _LIVE_AVG_LEAGUES = set(leagues) if leagues else None


def _csv_recent_league_avg():
    """本地CSV近30场实测场均(当前赛季权重=1.0): {联赛: (场均, 场次)}. 兜底层."""
    files = [
        os.path.join(ROOT, "data", "raw", "football_data", "football_data_recent.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "matches_2015_2025.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "matches_2023_2024.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "api_supplement_2024_2025.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "api_supplement_2025_2026.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "j1_2026_results.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "csl_2026_results.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "supplement_P1_B1.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "bsd_batch_20260821.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "supplement_bsd_2026_2027_b1n1p1.csv"),
    ]
    _espn_dir = os.path.join(ROOT, "data", "raw", "football_data")
    if os.path.isdir(_espn_dir):
        for _f in sorted(os.listdir(_espn_dir)):
            if _f.startswith("espn_") and _f.endswith("_results.csv"):
                files.append(os.path.join(_espn_dir, _f))
            if _f.startswith("footballdata_") and _f.endswith("_results.csv"):
                files.append(os.path.join(_espn_dir, _f))
    div_goals = collections.defaultdict(list)
    for fp in files:
        if not os.path.exists(fp):
            continue
        with io.open(fp, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                div = (row.get("Div") or "").strip()
                if div not in ALL_DIVS:
                    continue
                season = (row.get("season") or row.get("Season") or "").strip()
                if SEASON_WEIGHT.get(season) != 1.0:
                    continue
                try:
                    hg, ag = int(float(row["FTHG"])), int(float(row["FTAG"]))
                except Exception:
                    continue
                div_goals[div].append(hg + ag)
    # 中文联赛名优先: 英文名(快照兼容)不得覆盖中文键, 否则 analyze_match 按中文查基准取不到(E0->Premier League/B1->Pro League bug)
    lg_of_div = {}
    for _k, _v in DIV_BY_LEAGUE.items():
        if _v not in lg_of_div or any("\u4e00" <= _c <= "\u9fff" for _c in _k):
            lg_of_div[_v] = _k
    out = {}
    for div, gs in div_goals.items():
        lg = lg_of_div.get(div)
        if not lg:
            continue
        recent = gs[-LEAGUE_AVG_RECENT_N:]
        if len(recent) >= LEAGUE_AVG_MIN_N:
            out[lg] = (round(sum(recent) / len(recent), 3), len(recent))
    return out


def _live_recent_league_avg():
    """the-odds-api /scores 近2天完赛 -> 当前赛季独立窗口实测场均(样本>=4启用).

    只拉本次扫描涉及的联赛(_LIVE_AVG_LEAGUES); 4小时缓存文件复用防烧额度;
    任何失败/超时静默跳过, 返回None走CSV兜底.
    """
    if _LIVE_AVG_LEAGUES is None:
        return None
    try:
        cached = {}
        if os.path.exists(_LIVE_AVG_CACHE_PATH):
            _age_min = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(_LIVE_AVG_CACHE_PATH))).total_seconds() / 60
            if _age_min < _LIVE_AVG_MAX_AGE_MIN:
                _d = json.load(io.open(_LIVE_AVG_CACHE_PATH, encoding="utf-8"))
                cached = {k: (v[0], v[1]) for k, v in _d.get("avg", {}).items()}
        missing = set(_LIVE_AVG_LEAGUES) - set(cached)  # 缓存缺失的联赛补拉合并
        if not missing:
            return cached
        key = _pick_working_key()
        if not key:
            return cached or None
        sk_map = _sport_key_map()
        out = dict(cached)
        for lg in sorted(missing):
            sk = sk_map.get(lg)
            if not sk:
                continue
            url = "https://api.the-odds-api.com/v4/sports/%s/scores/?apiKey=%s&daysFrom=2&dateFormat=iso" % (sk, key)
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=_LIVE_AVG_TIMEOUT) as resp:
                    evs = json.loads(resp.read().decode("utf-8"))
            except Exception:
                continue
            goals = []
            for e in evs:
                if not e.get("completed"):
                    continue
                sc = {s.get("name"): s.get("score") for s in (e.get("scores") or [])}
                try:
                    hg, ag = int(sc.get(e.get("home_team"), "")), int(sc.get(e.get("away_team"), ""))
                except Exception:
                    continue
                goals.append(hg + ag)
            if len(goals) >= LEAGUE_AVG_MIN_N:
                out[lg] = (round(sum(goals) / len(goals), 3), len(goals))
        try:
            with io.open(_LIVE_AVG_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"avg": {k: list(v) for k, v in out.items()},
                           "fetched_at": datetime.now().isoformat()}, f, ensure_ascii=False)
        except Exception:
            pass
        return out or None
    except Exception:
        return None


def recent_league_avg():
    """联赛实测场均(基准偏差检查): 实时优先(the-odds-api当前赛季窗口) -> 本地CSV兜底. 模块级缓存."""
    global _RECENT_AVG_CACHE
    if _RECENT_AVG_CACHE is not None:
        return _RECENT_AVG_CACHE
    out = {}
    try:
        _csv = _csv_recent_league_avg()
        if _csv:
            out.update(_csv)
        _live = _live_recent_league_avg()
        if _live:
            out.update(_live)  # 实时优先覆盖CSV
    except Exception:
        pass
    _RECENT_AVG_CACHE = out
    return out


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("-", " ").replace(".", " ").replace("'", " ").replace("&", " ")
    return " ".join(s.split())

def _load_aliases():
    p = os.path.join(ROOT, "strategy_data", "teams_alias.json")
    if not os.path.exists(p):
        return {}
    try:
        return json.load(io.open(p, encoding="utf-8")).get("alias", {})
    except Exception:
        return {}

ALIAS = _load_aliases()

def _resolve_alias(name):
    return ALIAS.get(name, name)

def _parse_date(s):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt)
        except Exception:
            pass
    return None

def load_team_stats():
    """合并多数据源: football_data_recent(3季) + matches_2015_2025 + matches_2023_2024"""
    files = [
        os.path.join(ROOT, "data", "raw", "football_data", "football_data_recent.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "matches_2015_2025.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "matches_2023_2024.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "api_supplement_2024_2025.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "api_supplement_2025_2026.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "j1_2026_results.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "csl_2026_results.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "supplement_P1_B1.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "bsd_batch_20260821.csv"),
        os.path.join(ROOT, "data", "raw", "football_data", "supplement_bsd_2026_2027_b1n1p1.csv"),
    ]
    _espn_dir = os.path.join(ROOT, "data", "raw", "football_data")
    if os.path.isdir(_espn_dir):
        for _f in sorted(os.listdir(_espn_dir)):
            if _f.startswith("espn_") and _f.endswith("_results.csv"):
                files.append(os.path.join(_espn_dir, _f))
            if _f.startswith("footballdata_") and _f.endswith("_results.csv"):
                files.append(os.path.join(_espn_dir, _f))
    agg = {}
    lavg_raw = collections.defaultdict(list)
    seen = set()
    for fp in files:
        if not os.path.exists(fp):
            continue
        with io.open(fp, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                season = (row.get("season") or row.get("Season") or "").strip()
                w = SEASON_WEIGHT.get(season)
                if not w:
                    continue
                div = (row.get("Div") or "").strip()
                if div not in ALL_DIVS:
                    continue
                h, a = row["HomeTeam"], row["AwayTeam"]
                key = (season, div, h, a, row.get("Date") or "")
                if key in seen:
                    continue
                seen.add(key)
                try:
                    hg, ag = int(float(row["FTHG"])), int(float(row["FTAG"]))
                except Exception:
                    continue
                if fp.endswith("football_data_recent.csv") and season == "2025/2026":
                    lavg_raw[div].append(hg + ag)
                def acc(team, gf, ga, is_home):
                    r = agg.setdefault(team, {}).setdefault(div, {
                        "home_gf": [0.0, 0.0], "home_ga": [0.0, 0.0],
                        "away_gf": [0.0, 0.0], "away_ga": [0.0, 0.0],
                        "best_w": 0.0, "best_season": ""})
                    if is_home:
                        r["home_gf"][0] += gf * w; r["home_gf"][1] += w
                        r["home_ga"][0] += ga * w; r["home_ga"][1] += w
                    else:
                        r["away_gf"][0] += gf * w; r["away_gf"][1] += w
                        r["away_ga"][0] += ga * w; r["away_ga"][1] += w
                    if w > r["best_w"]:
                        r["best_w"] = w; r["best_season"] = season
                acc(h, hg, ag, True)
                acc(a, ag, hg, False)
    def avg(v):
        return round(v[0] / v[1], 3) if v[1] > 0 else 0.0
    out = {}
    for team, divs in agg.items():
        for div, r in divs.items():
            out.setdefault(team, {})[div] = {
                "home_gf": avg(r["home_gf"]), "home_ga": avg(r["home_ga"]),
                "away_gf": avg(r["away_gf"]), "away_ga": avg(r["away_ga"]),
                "n_home": round(r["home_gf"][1], 1), "n_away": round(r["away_gf"][1], 1),
                "src_w": r["best_w"], "src_season": r["best_season"],
                "src_tag": SRC_TAG.get(r["best_season"], "old") if r["best_w"] > 0 else None,
            }
    index = {}
    for t in out:
        index.setdefault(_norm(t), t)
    for alias, std in ALIAS.items():
        index.setdefault(_norm(alias), std)
        index.setdefault(_norm(std), std)
        # 中文别名值 -> 英文标准键(仅当英文键本身是真实数据键时), 支持中文队名输入命中数据
        if (index.get(_norm(alias)) == alias
                and any("\u4e00" <= ch <= "\u9fff" for ch in std)):
            index[_norm(std)] = alias
    lavg = {d: round(sum(v) / len(v), 4) for d, v in lavg_raw.items() if v}
    return out, lavg, index


def _injury_coef(recs):
    """伤停修正系数 (2026-08-27审计P1-1): 1.0=无影响, 下限0.75.
    - 有 position 字段时按位置加权: F/M 攻击端核心伤停影响更大
    - 无位置数据 (当前BSD包) 按人数渐进, 替代旧的">=3一刀切0.96"
    公式: coef = 1.0 - loss * 0.4, 钳位 [0.75, 1.0] (对齐审计方案)."""
    recs = [r for r in (recs or []) if r.get("status") not in ("available", "returning", "doubtful_returning")]
    n = len(recs)
    if n == 0:
        return 1.0
    _ATK_POS = ("F", "M", "FW", "MF", "AM", "ST", "W", "SS")
    pos_atk = sum(1 for r in recs if str(r.get("position") or "").upper() in _ATK_POS)
    if pos_atk:
        loss = min(1.0, pos_atk / max(n, 1) * 1.5)   # 攻击位权重: 全员攻击位伤停=全损
    else:
        # 无位置数据: 人数渐进 0-2:1.0 / 3-4:0.97 / 5-6:0.94 / 7+:0.91
        loss = 0.0 if n <= 2 else 0.075 if n <= 4 else 0.15 if n <= 6 else 0.225
    return max(0.75, min(1.0, 1.0 - loss * 0.4))


def _load_pkg_attacks():
    """match_package/*.json -> {"by_id": {event_id: rec}, "by_name": {"home": {队名: rec}, "away": {队名: rec}}}
    rec = {home, away, home_inj_n, away_inj_n, home_inj, away_inj, home_inj_recs, away_inj_recs}
    供本地攻防库缺失/陈旧的场次增强注入 (PKG_BOOST); by_name 兼容双数据源(event_id 不同)场次."""
    import glob
    by_id, by_name = {}, {"home": {}, "away": {}}
    for fp in glob.glob(os.path.join(ROOT, "analysis_records", "match_package", "*.json")):
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
        except Exception:
            continue
        att = d.get("attack") or {}
        h, a = att.get("home") or {}, att.get("away") or {}
        inj = d.get("injuries") or {}
        hi = inj.get("home") or []; ai = inj.get("away") or []
        rec = {
            "home": (h.get("stats") or {}) if h.get("have") else None,
            "away": (a.get("stats") or {}) if a.get("have") else None,
            "home_inj_n": len(hi), "away_inj_n": len(ai),
            "home_inj": [x.get("name") or x.get("short_name") for x in hi][:6],
            "away_inj": [x.get("name") or x.get("short_name") for x in ai][:6],
            "home_inj_recs": hi, "away_inj_recs": ai,
            "consensus": (d.get("odds") or {}).get("consensus") or {},
            "pulled_at": d.get("pulled_at"),
        }
        if d.get("id") is not None:
            _eid = str(d["id"])
            by_id[int(d["id"])] = rec
            by_id[_eid] = rec
            if _eid.startswith("apifb"):
                by_id[_eid[5:]] = rec
        if rec["home"] or rec["consensus"]:
            _hk = _norm(d.get("home") or "")
            by_name["home"].setdefault(_hk, []).append(rec)
            _hk2 = _norm(_resolve_alias(d.get("home") or "")) or _hk
            if _hk2 and _hk2 != _hk:
                by_name["home"].setdefault(_hk2, []).append(rec)
        if rec["away"] or rec["consensus"]:
            _ak = _norm(d.get("away") or "")
            by_name["away"].setdefault(_ak, []).append(rec)
            _ak2 = _norm(_resolve_alias(d.get("away") or "")) or _ak
            if _ak2 and _ak2 != _ak:
                by_name["away"].setdefault(_ak2, []).append(rec)
    return {"by_id": by_id, "by_name": by_name}

_PKG_ATTACKS = None
def pkg_attacks():
    global _PKG_ATTACKS
    if _PKG_ATTACKS is None:
        _PKG_ATTACKS = _load_pkg_attacks()
    return _PKG_ATTACKS


def _load_match_info_map():
    """加载最新 matches_info_*.json -> {(league, home, away): info}。"""
    import glob
    pat = os.path.join(ROOT, "analysis_records", "matches_info_*.json")
    fs = sorted(glob.glob(pat))
    if not fs:
        return {}
    try:
        d = json.load(io.open(fs[-1], encoding="utf-8"))
        return {(m["league"], m["home"], m["away"]): m for m in d.get("matches", [])}
    except Exception:
        return {}


def _bsd_leg_ev(name, prob, cons):
    """方向腿名 -> BSD consensus 双口径EV (prob*price-1, 2026-08-27审计P0-1修正去水口径).
    prob 为模型绝对概率, 本身无抽水; 除以 overround 属双重折扣, 已移除. 映射不到返回 None."""
    try:
        if name.startswith("1X2主胜") and cons.get("home_win"):
            _p, _ops = cons["home_win"], [cons.get("draw"), cons.get("away_win")]
        elif name.startswith("1X2平局") and cons.get("draw"):
            _p, _ops = cons["draw"], [cons.get("home_win"), cons.get("away_win")]
        elif name.startswith("1X2客胜") and cons.get("away_win"):
            _p, _ops = cons["away_win"], [cons.get("home_win"), cons.get("draw")]
        elif name[:1] in ("大", "小"):
            _line = float(name[1:])
            _mk = BSD_OU_LINES.get(_line)
            if not _mk:
                return None
            _up = cons.get(_mk)
            _dn = cons.get(_mk.replace("over", "under"))
            if not _up or not _dn:
                return None
            if name.startswith("大"):
                _p, _ops = _up, [_dn]
            else:
                _p, _ops = _dn, [_up]
        else:
            return None
        _ops = [o for o in _ops if o]
        if not _p or not _ops:
            return None
        return round(prob * _p - 1, 4)
    except Exception:
        return None


def _bsd_dir_agree(name, pred):
    """我方方向 vs BSD预测方向: True(同向)/False(反向)/None(无法判断).
    1X2/让球用 match_result.predicted(H/D/A); 大小球用 over_under prob_over_X(0-100)."""
    if not name:
        return None
    try:
        mk = (pred.get("markets") or {})
        mr = mk.get("match_result") or {}
        bsd_pred = mr.get("predicted")
        ou = mk.get("over_under") or {}
        if name.startswith("1X2"):
            for _k, _v in (("主胜", "H"), ("平局", "D"), ("客胜", "A")):
                if _k in name:
                    return (bsd_pred == _v) if bsd_pred else None
            return None
        if name.startswith(("大", "小")):
            try:
                _line = float(name[1:])
            except Exception:
                return None
            _key = BSD_PRED_OU.get(_line)
            if not _key or ou.get(_key) is None:
                return None
            _over_p = ou[_key]
            return _over_p >= 50.0 if name.startswith("大") else _over_p < 50.0
        if name.startswith("让球"):
            if not bsd_pred:
                return None
            if "主" in name:
                return bsd_pred == "H"
            if "客" in name:
                return bsd_pred == "A"
            return None
    except Exception:
        return None
    return None


def _bsd_downgrade(r, tag, note=None):
    """BSD风控降星: 只降星级/加标签, 不改EV原值. 同时同步 best_bet.star 与 r.star."""
    if tag and tag not in r.get("risk_tags", []):
        r.setdefault("risk_tags", []).append(tag)
    if note:
        r.setdefault("notes", []).append(note)
    if r.get("star"):
        r["star"] = max(1, r["star"] - 1)
    _bb = r.get("best_bet")
    if _bb and _bb.get("star"):
        _bb["star"] = max(1, _bb["star"] - 1)


def _formation_profile(f):
    """阵型字符串 -> {'def': 后卫数, 'fwd': 前锋数, 'tend': -1防守/0均衡/+1进攻}; 无法解析返 None."""
    if not f:
        return None
    try:
        parts = [int(x) for x in str(f).strip().split("-") if x.strip().isdigit()]
        if len(parts) < 3:
            return None
        nb, fw = parts[0], parts[-1]
        tend = 0
        if nb >= 5:
            tend -= 1
        if nb <= 3:
            tend += 1
        if fw >= 2:
            tend += 1
        if fw <= 1:
            tend -= 1
        return {"def": nb, "fwd": fw, "tend": tend}
    except Exception:
        return None


def _formation_check(r, info):
    """阵型指标(1d): 当场阵型优先, 教练偏好兜底 -> 攻防倾向标签 + 缺失标注.
    返回 formation dict; 只加标签/notes, 不改EV(与第四类风控一致)."""
    lu = (info or {}).get("bsd_lineups") or {}
    f_cur = lu.get("formation") or {}
    coach = lu.get("coach") or {}
    out = {"home": None, "away": None, "src": "none", "tend": 0, "missing": []}
    profiles = {}
    for side in ("home", "away"):
        f = (f_cur.get(side) or "").strip() or (coach.get(side) or "").strip()
        if not f:
            out["missing"].append(side)
            continue
        p = _formation_profile(f)
        if p is None:
            out["missing"].append(side)
            continue
        out[side] = f
        profiles[side] = p
        out["tend"] += p["tend"]
    if not profiles:
        r.setdefault("risk_tags", []).append("阵型未提取")
        out["src"] = "none"
        return out
    out["src"] = "cur" if any((f_cur.get(s) or "").strip() for s in ("home", "away")) else "coach"
    _fs = "阵型:主%s/客%s" % (out["home"] or "-", out["away"] or "-")
    r.setdefault("notes", []).append(_fs + "(%s)" % ("当场" if out["src"] == "cur" else "教练偏好"))
    _tag = None
    if out["tend"] >= 2:
        _tag = "阵型对攻倾向(+%d)" % out["tend"]
    elif out["tend"] <= -2:
        _tag = "阵型防守倾向(%d)" % out["tend"]
    if _tag and _tag not in r.get("risk_tags", []):
        r.setdefault("risk_tags", []).append(_tag)
    if out["missing"]:
        r.setdefault("risk_tags", []).append("阵型缺失:%s" % "/".join(out["missing"]))
    return out


INJ_POS_CRIT = {"G": 1, "D": 2, "F": 2, "M": 3}   # 各位置缺阵触发阈值: 门将1/后防2/锋线2(降星), 中场3(仅提示)
INJ_POS_NAMES = {"G": "门将", "D": "后防", "F": "锋线", "M": "中场"}


def _injury_pos_check(r, info):
    """伤停按位置加权(1d): 缺阵位置分布 -> 关键位置标签.
    门将缺1/后防缺2/锋线缺2 触发"伤停关键位置"降星(仅降星+标签, 不改EV, 同第四类风控);
    中场缺3 仅提示不降星; 伤停有记录但位置未知标注覆盖缺口.
    返回 dict(home/away各位置人数, unknown)."""
    inj = (info or {}).get("injuries") or {}
    out = {"home": {}, "away": {}, "unknown": 0}
    for side in ("home", "away"):
        recs = inj.get(side) or []
        if not recs:
            continue
        cnt = collections.Counter()
        unknown = 0
        for x in recs:
            p = (x.get("position") or "").strip().upper()
            if p in ("G", "D", "M", "F"):
                cnt[p] += 1
            else:
                unknown += 1
        out[side] = dict(cnt)
        out["unknown"] += unknown
        side_cn = "主队" if side == "home" else "客队"
        if unknown:
            r.setdefault("notes", []).append("%s伤停%d人位置未知(非BSD源), 位置加权未覆盖" % (side_cn, unknown))
        if cnt.get("M", 0) >= INJ_POS_CRIT["M"]:
            r.setdefault("notes", []).append("%s中场缺阵%d人(仅提示, 不降星)" % (side_cn, cnt["M"]))
        crit = [INJ_POS_NAMES[p] for p in ("G", "D", "F") if cnt.get(p, 0) >= INJ_POS_CRIT[p]]
        if crit:
            _tag = "伤停关键位置(%s:%s)" % (side_cn, "/".join(crit))
            _d = "/".join("%s缺%d" % (INJ_POS_NAMES[p], cnt[p]) for p in ("G", "D", "F", "M") if cnt.get(p))
            _bsd_downgrade(r, _tag, "%s%s(位置加权, 仅降星不改EV)" % (side_cn, _d))
    return out


def _bsd_cross_check(r, info):
    """BSD市场基准交叉验证:
    1) λ: 我们λ vs BSD expected_goals 单侧偏差>0.5 -> 标"模型独立观点"(Step8)
    2) 双口径EV: 方向腿用BSD consensus去水重算 ev_bsd(Step31)
    3) BSD recommendations 全false 且 我们best EV<阈值 -> 无单(市场无价值+EV不足)
    4) [1a] BSD置信度交叉验证: 同向conf>=0.60保留; 反向或conf<0.45降星(不改EV)
    返回 bsd dict(eg/lam_dev/ev/recs); 修改 r[risk_tags]/r[notes]/r[best_bet]."""
    pred = (info or {}).get("bsd_prediction") or {}
    odds = (info or {}).get("bsd_odds") or {}
    eg = pred.get("expected_goals") or {}
    cons = odds.get("consensus") or {}
    recs = pred.get("recommendations") or {}
    out = {"eg": {"home": eg.get("home"), "away": eg.get("away")},
           "recs": recs, "ev": None, "lam_dev": None,
           "conf": pred.get("confidence"), "agree": None, "support": None}
    if eg.get("home") is None:
        return out
    lam_h, lam_a = r["lambda"]["home"], r["lambda"]["away"]
    dev_h, dev_a = abs(lam_h - eg["home"]), abs(lam_a - eg["away"])
    out["lam_dev"] = {"home": round(dev_h, 2), "away": round(dev_a, 2),
                      "our": [round(lam_h, 2), round(lam_a, 2)], "bsd": [eg["home"], eg["away"]]}
    if max(dev_h, dev_a) > BSD_LAM_DEV_TOL:
        _tag = "λ与BSD市场分歧(我们%.2f/%.2f vs BSD%.2f/%.2f, Δ最大%.2f)" % (
            lam_h, lam_a, eg["home"], eg["away"], max(dev_h, dev_a))
        _bsd_downgrade(r, _tag, "模型独立观点: 我们λ偏离BSD市场EG(市场λ), 属我方攻防模型独立信号, 人工复核")
    _conf = pred.get("confidence")
    if _conf is not None:
        _bb = r.get("best_bet")
        if _bb:
            _agree = _bsd_dir_agree(_bb["name"], pred)
            out["agree"] = _agree
            if _agree is True and _conf >= BSD_CONF_SUPPORT:
                r.setdefault("notes", []).append("BSD共识支持(同向conf=%.2f>=%.2f)" % (_conf, BSD_CONF_SUPPORT))
                out["support"] = True
            elif _agree is False:
                _mr = ((pred.get("markets") or {}).get("match_result") or {})
                _bsd_downgrade(r, "BSD方向分歧(BSD预测:%s)" % _mr.get("predicted", "?"),
                               "BSD与我们方向相反, 已降星(不改EV), 人工复核")
                out["support"] = False
            elif _agree is True and _conf < BSD_CONF_DIVERGE:
                _bsd_downgrade(r, "BSD低置信支持(conf=%.2f<%.2f)" % (_conf, BSD_CONF_DIVERGE),
                               "BSD同向但置信度低于%.2f, 已降星(不改EV)" % BSD_CONF_DIVERGE)
                out["support"] = False
    di = r.get("direction")
    if di and cons:
        ev_bsd = _bsd_leg_ev(di["name"], di["prob"], cons)
        out["ev"] = ev_bsd
        if ev_bsd is not None:
            di["ev_bsd"] = ev_bsd
            di["ev_gap"] = round(di["ev"] - ev_bsd, 3)
    _val_flags = [recs.get(k) for k in ("bet_favorite", "over_15", "over_25", "over_35", "btts", "winner")]
    if recs and not any(_val_flags):
        bb = r.get("best_bet")
        if bb and bb.get("ev", 1.0) < EV_TIER_BATCH:
            r["best_bet"] = None
            _t = "BSD市场无价值+我方EV<5%"
            if _t not in r.get("risk_tags", []):
                r.setdefault("risk_tags", []).append(_t)
    return out


def parse_snapshots(path=None):
    p = path or os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    rows = []
    future_skipped = 0
    now_utc = datetime.now(timezone.utc)
    with io.open(p, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for x in r:
            if not x:
                continue
            if is_future_snapshot(x[0], now=now_utc):
                future_skipped += 1
                continue
            rows.append(x)
    def parse(ct):
        try:
            return datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except Exception:
            return None
    _cts = [parse(x[3]) for x in rows if parse(x[3])]
    start = min(_cts) if _cts else datetime(2026, 8, 15, 0, 0, tzinfo=timezone.utc)
    end = max(_cts) if _cts else datetime(2026, 8, 17, 0, 0, tzinfo=timezone.utc)
    events = {}
    for row in rows:
        ct = parse(row[3])
        if ct and start <= ct <= end:
            key = (row[1], row[4], row[5])
            ev = events.setdefault(key, {"lg": row[2], "ct": ct, "snap": row[0], "odds": collections.defaultdict(list)})
            ev["snap"] = row[0]
            ev["odds"][(row[6], row[7])].append(row)
    # 合并API-Football亚盘孤儿事件(apifb{fid})到同场the-odds(32hex)/BSD(数字)事件:
    # AH行event_id与h2h事件不一致(如apifb1607201 vs f818...), 不归并则亚盘永远孤儿导致"缺亚盘"
    def _nm(s):
        s = unicodedata.normalize('NFKD', s or '')
        s = ''.join(c for c in s if not unicodedata.combining(c))
        return re.sub(r'[^a-z0-9]+', '', s.lower())
    _keys = list(events.keys())
    _orphans = [k for k in _keys if str(k[0]).startswith('apifb')]
    for _ok in _orphans:
        _oe = events[_ok]
        _cands = []
        for _k2 in _keys:
            if _k2 == _ok or str(_k2[0]).startswith('apifb'):
                continue
            _e2 = events[_k2]
            if abs((_e2['ct'] - _oe['ct']).total_seconds()) > 6 * 3600:
                continue
            _hn, _an = _nm(_ok[1]), _nm(_ok[2])
            _h2, _a2 = _nm(_k2[1]), _nm(_k2[2])
            if _hn and _h2 and _an and _a2:
                _mk = lambda x, y: x == y or x in y or y in x
                if not (_mk(_hn, _h2) and _mk(_an, _a2)):
                    continue
            else:
                # 中文等非拉丁队名norm后为空: 仅允许大小写不敏感精确匹配
                if _ok[1].lower() != _k2[1].lower() or _ok[2].lower() != _k2[2].lower():
                    continue
            _cands.append(_k2)
        if _cands:
            _exact = [c for c in _cands if _nm(_ok[1]) == _nm(c[1]) and _nm(_ok[2]) == _nm(c[2])]
            for _k2 in (_exact or _cands):
                for (_bk, _mk2), _lst in _oe['odds'].items():
                    events[_k2]['odds'][(_bk, _mk2)].extend(_lst)
                if _oe['snap'] > events[_k2]['snap']:
                    events[_k2]['snap'] = _oe['snap']
            del events[_ok]
    def _group_by_line(rows, market, side_col=9, line_col=11, price_col=12):
        """按 (book, line) 分组, 返回 {line: {book: {side: price}}} — 杜绝多盘口线混算Overround.
        spreads 存在两种符号约定:
          - the-odds-api 镜像约定: 主-1.5/客+1.5 -> 按 带符号主让线 归组(客侧取反),
            防止 主-1.5/客+1.5 与 主+1.5/客-1.5 两条不同盘口被 abs 合并合价污染;
          - 旧数据/同号约定: 主-0.5/客-0.5 -> 保持 abs 归组(两侧同盘)。
        按 (快照, 事件, 庄家) 自动检测约定。"""
        conv = {}
        if market == "spreads":
            _grp = collections.defaultdict(dict)
            for x in rows:
                try:
                    _lf = float(x[line_col])
                except (TypeError, ValueError):
                    continue
                _grp[(x[0], x[1], x[6], abs(_lf))][(x[side_col] or "").lower()] = _lf
            for (_ts, _eid, _bk, _al), _sides in _grp.items():
                if "home" in _sides and "away" in _sides:
                    conv.setdefault(_bk, set()).add(
                        "same" if _sides["home"] == _sides["away"] else "mirror")
        g = {}
        for x in rows:
            raw_line = x[line_col] if x[line_col] != "" else ""
            if market in ("spreads", "totals") and raw_line == "":
                continue  # 无point的盘口行(odds-api缺失)跳过, 防归入假线"0"产生错线EV
            line = raw_line if raw_line != "" else "0"
            try:
                line_f = float(line)
            except Exception:
                line_f = None
            if market in ("spreads", "totals") and line_f is None:
                continue
            if market == "asian_handicap":
                key = line_f  # 亚盘: 主队侧带符号线, 避免主-0.5与主+0.5相反线共键
            elif market == "spreads" and line_f is not None:
                if conv.get(x[6]) == {"same"}:
                    key = abs(line_f)  # 同号约定: 主客同盘
                else:
                    # 镜像约定: 客侧取反得到同一主让线键
                    _sd = (x[side_col] or "").lower()
                    key = line_f if _sd == "home" else -line_f
            else:
                key = line_f if line_f is not None else line
            try:
                price = float(x[price_col])
            except Exception:
                continue
            side = x[side_col].lower()
            d = g.setdefault(key, {}).setdefault(x[6] or "any", {})
            d[side] = price
            if market in ("spreads", "asian_handicap") and line_f is not None:
                d["_line_" + side] = line_f
        return g

    def _pick_lowest_orr_line(groups, want_line=None):
        """选抽水最低的 (line, book, orr); totals优先2.5线, spread优先主盘(最接近±0.5)."""
        cands = []
        for line, by_book in groups.items():
            for bk, prices in by_book.items():
                prices_only = {k: v for k, v in prices.items() if not str(k).startswith("_")}
                if len(prices_only) < 2:
                    continue
                try:
                    o = sum(1.0 / v for v in prices_only.values())
                except Exception:
                    continue
                cands.append((line, bk, o, prices))
        if not cands:
            return None
        if want_line is not None:
            exact = [c for c in cands if c[0] == want_line]
            if exact:
                cands = exact
        if want_line is not None:
            cands.sort(key=lambda c: (abs(c[0] - want_line), c[2]))
        else:
            # 主盘选择: 两侧价格最接近平衡(隐含概率最接近50/50)的主线优先, 同平衡取抽水最低;
            # 修复亚盘镜像线(主-0.5 vs 主+0.5)误选次线bug(天狼星旧选主+0.5 1.31/3.49),
            # 且避免抽水差0.0007的深盘(-0.75)盖过主流-0.5线
            def _imbalance(prices):
                only = {k: v for k, v in prices.items() if not str(k).startswith("_")}
                if not only:
                    return 1.0
                return max(abs(1.0 / v - 0.5) for v in only.values())
            cands.sort(key=lambda c: (_imbalance(c[3]), c[2]))
        return cands[0]

    out = []
    for (eid, h, a), ev in sorted(events.items(), key=lambda kv: kv[1]["ct"]):
        rec = {"id": eid, "league": ev["lg"], "home": h, "away": a, "ct": ev["ct"], "snap": ev["snap"],
               "h2h": None, "spread": None, "totals": None, "books_used": {}}
        all_rows = collections.defaultdict(list)
        for (bk, mk), rows in ev["odds"].items():
            all_rows[mk].extend(rows)
        # 1X2 同样按 (book,line) 分组取最低抽水机构, 杜绝多机构混价污染去水 (第三类)
        h2h_groups = _group_by_line(all_rows.get("h2h", []), "h2h")
        c = _pick_lowest_orr_line(h2h_groups, want_line=0.0)
        if c and len(c[3]) >= 3:
            _line, _bk, _orr, _prices = c
            rec["h2h"] = {"home": _prices.get("home"), "draw": _prices.get("draw"),
                          "away": _prices.get("away")}
            rec["books_used"]["h2h"] = "%s(line=%s,orr=%.3f)" % (_bk, _line, _orr)
        # 亚盘优先(API-Football asian_handicap, 带符号主队线), 无亚盘回退欧盘 spreads
        _ah_rows = all_rows.get("asian_handicap", [])
        if _ah_rows:
            sp_groups = _group_by_line(_ah_rows, "asian_handicap")
        else:
            sp_groups = _group_by_line(all_rows.get("spreads", []), "spreads")
        c = _pick_lowest_orr_line(sp_groups, want_line=None)
        if c:
            line, bk, orr, prices = c
            hdp_home = prices.get("_line_home")
            if hdp_home is None and prices.get("_line_away") is not None:
                hdp_home = -prices["_line_away"]
            if hdp_home is None:
                hdp_home = line
            rec["spread"] = {"hdp_home": hdp_home, "home_price": prices.get("home"), "away_price": prices.get("away")}
            rec["books_used"]["spread"] = "%s(line=%s,orr=%.3f)" % (bk, line, orr)
        tt_groups = _group_by_line(all_rows.get("totals", []), "totals")
        c = _pick_lowest_orr_line(tt_groups, want_line=2.5)
        if c:
            line, bk, orr, prices = c
            rec["totals"] = {"line": line, "over_price": prices.get("over"), "under_price": prices.get("under")}
            rec["books_used"]["totals"] = "%s(line=%s,orr=%.3f)" % (bk, line, orr)
        out.append(rec)
    return out, future_skipped

def bsd_odds_merge(events):
    """BSD consensus 免费盘源 -> 覆盖 1X2/大小球 (扫描主盘源, the-odds-api 降为临场专用).
    命中 match_package 的场次: h2h/totals 用 BSD 共识价, snap 更新为包拉取时间, 防过期误否决.
    返回覆盖场次数. 亚盘(让球)BSD 不提供, 保持原快照或缺亚盘标注."""
    try:
        _pa = pkg_attacks()
    except Exception:
        return 0
    _bn = _pa.get("by_name") or {}
    _bid = _pa.get("by_id") or {}
    n = 0

    def _cands(d, names):
        out = []
        for nm in names:
            if nm and d.get(nm):
                out.extend(d[nm])
        if out:
            return out
        for nm in names:
            if not nm:
                continue
            ws = set(nm.split())
            for _k, _vs in d.items():
                wk = set(_k.split())
                if ws and wk and (ws <= wk or wk <= ws):
                    small, big = (ws, wk) if len(ws) <= len(wk) else (wk, ws)
                    if len(small) == 1 or len(small) / len(big) >= 0.6:
                        out.extend(_vs)
        return out

    for m in events:
        try:
            _pkg = None
            _eid = str(m.get("id") or "")
            _stripped = _eid[5:] if _eid.startswith("apifb") else _eid
            _pkg = _bid.get(_eid) or _bid.get(_stripped)
            try:
                if _pkg is None:
                    _pkg = _bid.get(int(_stripped or 0))
            except Exception:
                pass
            if _pkg is None:
                _nh = _norm(m.get("home") or "")
                _na = _norm(m.get("away") or "")
                _nh2 = _norm(_resolve_alias(m.get("home") or "")) or _nh
                _na2 = _norm(_resolve_alias(m.get("away") or "")) or _na
                _hc = _cands(_bn.get("home") or {}, [_nh, _nh2])
                _ac = _cands(_bn.get("away") or {}, [_na, _na2])
                _both = [r for r in _hc if r in _ac]
                _pkg = _both[0] if _both else None
                if _pkg is None and _hc and _ac:
                    _pkg = _hc[0]
            if not _pkg:
                continue
            cons = _pkg.get("consensus") or {}
            changed = False
            # 1X2: BSD 共识价为主源优先覆盖(the-odds 降为临场专用)
            if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
                if m.get("h2h") and "h2h_prev" not in m:
                    m["h2h_prev"] = dict(m["h2h"])
                m["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
                m.setdefault("books_used", {})["h2h"] = "bsd_consensus"
                changed = True
            # 大小球: 仅当无 totals 时用 BSD 2.5 补缺. BSD 只有 2.5 单线,
            # 覆盖会丢掉原市场线(如3.00)且抽水口径不同致EV失真(Neom大3.00消失/GilVicente误否决)
            if not m.get("totals") and cons.get("over_25_goals") and cons.get("under_25_goals"):
                m["totals"] = {"line": 2.5, "over_price": cons["over_25_goals"], "under_price": cons["under_25_goals"]}
                m.setdefault("books_used", {})["totals"] = "bsd_consensus(2.5)"
                changed = True
            if changed and _pkg.get("pulled_at"):
                m["snap"] = _pkg["pulled_at"]
                n += 1
        except Exception:
            continue
    return n


def match_stats(team, div, team_stats, index):
    t, q = _match_team(team, index)
    rec = team_stats.get(t, {}) if t else {}
    if div and div in rec:
        r = rec[div]
        if r.get("src_w", 0.0) >= INDEP_MIN_WEIGHT:
            return r, div, False, r["src_w"], False, q
        # 本联赛数据陈旧(<0.7): 优先选其他联赛的独立新数据(升班马/降级队场景)
        best = None
        for d2, r2 in rec.items():
            if d2 == div:
                continue
            if r2.get("src_w", 0.0) >= INDEP_MIN_WEIGHT and (best is None or r2["src_w"] > best[0]):
                best = (r2["src_w"], d2)
        if best:
            d2 = best[1]
            return rec[d2], d2, True, rec[d2]["src_w"], (d2 != div), q
        return r, div, False, r["src_w"], False, q
    for d2 in ("SP2", "E1", "D2", "E2", "N2"):
        if d2 in rec and rec[d2].get("src_w", 0.0) >= INDEP_MIN_WEIGHT:
            return rec[d2], d2, True, rec[d2]["src_w"], (d2 != div), q
    best = None
    for d2, r in rec.items():
        if r.get("src_w", 0.0) >= INDEP_MIN_WEIGHT and (best is None or r["src_w"] > best[0]):
            best = (r["src_w"], d2)
    if best:
        d2 = best[1]
        return rec[d2], d2, True, rec[d2].get("src_w", 0.0), (d2 != div), q
    return None, None, False, 0.0, False, q

def _match_team(team, index):
    """队名匹配分级: exact(整词/别名) > subset(词集包含) > fuzzy(相似度>=0.9) > none(降级标注).
    返回 (标准队名 或 None, 匹配质量). 相似度<0.9 才降级, 不静默替换 (第二类).
    先按原始名匹配(数据源/盘口英文标准名), 再走别名解析——防止英文标准名被别名提前转中文后
    与 team_stats 英文键失配(中超别名英文->中文场景)."""
    raw = str(team)
    n0 = _norm(raw)
    n1 = _norm(_resolve_alias(raw))
    if n0 in index:
        return index[n0], "exact"
    if n1 in index:
        return index[n1], "exact"
    n = n0 or n1
    if not n:
        return None, "none"
    ws = set(n.split())
    for k, name in index.items():
        if set(k.split()) == ws:
            return name, "exact"
    for k, name in index.items():
        wk = set(k.split())
        if ws and wk and (ws <= wk or wk <= ws):
            # 词集比例保护: 单词缩写(如PSV)允许; 多词需小集合/大集合 >= 0.6,
            # 防 York City 误配 New York City FC 等跨联赛歧义
            small, big = (ws, wk) if len(ws) <= len(wk) else (wk, ws)
            if len(small) == 1 or len(small) / len(big) >= 0.6:
                return name, "subset"
    try:
        from difflib import SequenceMatcher
    except Exception:
        return None, "none"
    best_k, best_r = None, 0.0
    for k, name in index.items():
        r = SequenceMatcher(None, n, k).ratio()
        if r > best_r:
            best_r, best_k = r, k
    if best_k is not None and best_r >= 0.9:
        return index[best_k], "fuzzy"
    return None, "none"

def implied_lambdas_from_odds(m, league_avg, rho):
    """无独立攻防时，用去水市场赔率反推主客λ（仅参考，不产生独立信号）"""
    h2h = m.get("h2h") or {}
    if not h2h.get("home"):
        return None
    s = 1.0 / h2h["home"] + 1.0 / h2h["draw"] + 1.0 / h2h["away"]
    p_h = (1.0 / h2h["home"]) / s
    p_d = (1.0 / h2h["draw"]) / s
    tt = m.get("totals")
    line = None
    p_over = None
    if tt and tt.get("line") is not None and tt.get("over_price"):
        line = float(tt["line"])
        p_over = (1.0 / tt["over_price"]) / (1.0 / tt["over_price"] + 1.0 / tt["under_price"])
    def probs(lh, la):
        g = dc_score_grid(lh, la, rho=rho, max_goals=9)
        win = sum(g[i][j] for i in range(10) for j in range(10) if i > j)
        drw = sum(g[i][j] for i in range(10) for j in range(10) if i == j)
        over = None
        if line is not None:
            if abs(line - round(line)) < 0.01:
                push = sum(g[i][j] for i in range(10) for j in range(10) if abs(i + j - line) < 0.01)
                over = sum(g[i][j] for i in range(10) for j in range(10) if i + j > line) + push * 0.5
            else:
                over = sum(g[i][j] for i in range(10) for j in range(10) if i + j > line)
        return win, drw, over
    def cost(p):
        lh, la = p
        win, drw, over = probs(lh, la)
        e = (win - p_h) ** 2 + (drw - p_d) ** 2
        if over is not None:
            e += (over - p_over) ** 2
        return e
    cands = [(0.3 + i * 0.1, 0.3 + j * 0.1) for i in range(35) for j in range(35)]
    lh, la = min(cands, key=cost)
    for step in (0.02, 0.01, 0.005):
        local = [(lh + dh * step, la + da * step) for dh in (-1, 0, 1) for da in (-1, 0, 1)]
        local = [(x, y) for x, y in local if 0.2 <= x <= 4.5 and 0.2 <= y <= 4.5]
        b = min(local, key=cost)
        if cost(b) < cost((lh, la)):
            lh, la = b
    return max(0.2, min(4.5, lh)), max(0.2, min(4.5, la))


def calc_dir_consistency(bets):
    """方向组一致性（固定规则 v1.1, 2026-08-21 固化, 不得改动）。
    每组取 EV 最高的正EV腿作为组方向; 组内无正EV则取EV最高腿(标注负值, 不参与一致)。
    等级定义（写死）:
      '三向一致'          : 1X2/让球/大小球 三组均正EV, 且 主胜+让主+大 或 客胜+让客+大
      '主向稳胜'          : 1X2主胜+让球主(均正EV)+小球正EV
      '客向稳胜'          : 1X2客胜+让球客(均正EV)+小球正EV
      '主向一致(胜负亚盘)' : 主胜+让主均正EV, 大小球无正EV
      '客向一致(胜负亚盘)' : 客胜+让客均正EV, 大小球无正EV
      '主向分歧'          : 1X2与亚盘反向 (胜负与亚盘打架)
      '平局主导'          : 1X2方向为平局
      '无正EV'            : 三组均无正EV
    """
    groups = {"1X2": [], "让球": [], "大小球": []}
    for b in bets or []:
        n = b.get("name", "")
        if n.startswith("1X2"):
            groups["1X2"].append(b)
        elif n.startswith("让球"):
            groups["让球"].append(b)
        elif n.startswith("大") or n.startswith("小"):
            groups["大小球"].append(b)

    def pick(g):
        if not g:
            return None
        pos = [b for b in g if b.get("ev", 0) > 0]
        return max(pos, key=lambda b: b.get("ev", -9)) if pos else None

    def pick_any(g):
        if not g:
            return None
        return max(g, key=lambda b: b.get("ev", -9))

    h = pick(groups["1X2"])   # 1X2 组方向(仅正EV)
    a = pick(groups["让球"])   # 让球 组方向(仅正EV)
    o = pick(groups["大小球"]) # 大小球 组方向(仅正EV)
    hd = pick_any(groups["1X2"])
    ad = pick_any(groups["让球"])
    od = pick_any(groups["大小球"])

    def evd(b):
        return round((b.get("ev") or 0) * 100, 1) if b else None

    out = {"groups": {
        "1X2": {"dir": hd["name"] if hd else None, "ev": evd(hd)},
        "让球": {"dir": ad["name"] if ad else None, "ev": evd(ad)},
        "大小球": {"dir": od["name"] if od else None, "ev": evd(od)},
    }, "level": "无正EV"}

    if not hd or not ad or not od:
        return out
    hdn = hd["name"].replace("1X2", "")
    adn = ad["name"].replace("让球", "")
    odn = od["name"]
    if hdn == "平局":
        out["level"] = "平局主导"
        return out
    # 胜负与亚盘同向判定
    if hdn == "主胜" and adn.startswith("主"):
        align = "主向"
    elif hdn == "客胜" and adn.startswith("客"):
        align = "客向"
    else:
        out["level"] = "主向分歧"
        return out
    if h and a and o:
        if odn.startswith("大"):
            out["level"] = "三向一致"
        else:
            out["level"] = align + "稳胜"
    elif h and a:
        out["level"] = align + "一致(胜负亚盘)"
    else:
        out["level"] = "无正EV"
    return out



def fake_small_intercept(bets, tt):
    """规则⑨(2026-08-24): 假小球拦截 — 模型自算大球>=50% 却出现小球正EV = λ低估假信号.
    触发: 任一 小球腿 ev>0 且 模型P(大2.5)>=50% 且 市场隐含大>=60%.
    处置: 小球腿 _pband_banned 移出候选(不出单/不输出方向); 真小球(λ和市场双低)不受影响.
    返回: (ban_count, model_over, mkt_over).
    实证: 荷甲账本5注小球全灭(高进球联赛逆市场推小=系统性错误)."""
    model_over = None
    for _b in bets:
        if _b["name"].startswith("大"):
            model_over = _b.get("prob")
            break
    mkt_over = None
    if tt and tt.get("over_price") and tt.get("under_price"):
        try:
            _op, _up = float(tt["over_price"]), float(tt["under_price"])
            if _op > 0 and _up > 0:
                mkt_over = (1.0 / _op) / (1.0 / _op + 1.0 / _up)
        except Exception:
            pass
    ban = 0
    if model_over is not None and mkt_over is not None and model_over >= 0.50 and mkt_over >= 0.60:
        for _b in bets:
            if _b["name"].startswith("小") and _b.get("ev", 0) > 0:
                _b["_pband_banned"] = True
                ban += 1
    return ban, model_over, mkt_over


def under_zone_ban_small(bets, lg, cal, league_avg_shifted, base_dev):
    """规则⑪(2026-08-27 300场复盘+账本实证): 低估区禁小球.
    低估区 = 模型λ系统性偏低(实际进球常高于模型) -> 小球是陷阱, 移出候选+方向.
    触发: ① league_calib ou_under_reverse=True(英冠/荷甲) ② 杯赛/资格赛实测λ低估区名单
          ③ 实测场均>配置基准(league_avg_shifted且base_dev>0, 数据驱动).
    实证: 300场复盘 英冠小球20%/荷甲0%/德国杯0%; 账本 英冠31%/荷甲22%/英联杯0%/欧冠0%;
          08-27 AEK小2.50(4-0)/美洲小2.25(4-2) 出大全灭(采列1-1为BSD修正比分, 小2.50命中).
    返回: 被禁小球腿数(小球队打 _pband_banned 标记)."""
    zone = bool((cal or {}).get("ou_under_reverse")) or any(_k in lg for _k in LOW_EST_UNDER_BAN_SMALL) \
        or (league_avg_shifted and base_dev > 0)
    if not zone:
        return 0
    n = 0
    for _b in bets:
        if _b["name"].startswith("小"):
            _b["_pband_banned"] = True
            n += 1
    return n


# ===== 积分榜接入 (2026-08-26 M-20260826-01): BSD standings 位置区间标签 + 星级微调 (不改EV) =====
_STANDINGS_IDX = None
def _standings_idx():
    """全联赛积分榜索引 {team_key: {league,pos,total,pts,played,form}}; BSD官方优先, 6h缓存."""
    global _STANDINGS_IDX
    if _STANDINGS_IDX is not None:
        return _STANDINGS_IDX
    out = {}
    try:
        import _batch_match_info as bmi
        for _lg in bmi.BSD_LEAGUE_ID:
            try:
                _d = bmi.bsd_standings(_lg)
            except Exception:
                _d = {}
            _total = len(_d)
            for _k, _r in _d.items():
                try:
                    out[_k] = {"league": _lg, "pos": int(_r.get("position") or 0),
                               "total": _total, "pts": int(_r.get("pts") or 0),
                               "played": int(_r.get("played") or 0),
                               "form": (_r.get("form") or "")}
                except Exception:
                    pass
    except Exception:
        pass
    _STANDINGS_IDX = out
    return out


def _standings_find(name):
    if not name:
        return None
    try:
        import _batch_match_info as bmi
        _idx = _standings_idx()
        _k = bmi.team_key(name)
        if _k in _idx:
            return _idx[_k]
        _ws = set(str(name).lower().replace("-", " ").split())
        for _kk, _v in _idx.items():
            _wk = set(_kk.replace("-", " ").split())
            if _ws and _wk and (_ws <= _wk or _wk <= _ws):
                return _v
    except Exception:
        pass
    return None


def _standings_zone(pos, total):
    if not pos or not total or total < 4:
        return None
    if pos <= 3:
        return "争冠/升级"
    if pos > total * 0.8:
        return "保级"
    return "中游"



def analyze_match(m, team_stats, lavg, index):
    lg = m["league"]
    div = DIV_BY_LEAGUE.get(lg)
    cal = _cal_for_league(lg) or CAL.get(lg, {"league_avg": lavg.get(div, 2.6), "rho": 0.0, "shrink": 1.0,
                       "home": 1.0, "away": 1.0, "fatigue": 1.0})
    league_avg = cal["league_avg"]
    note = []
    _cup_key = None
    if _cal_for_league(lg):
        for _k in CUP_COEFFS:
            if _k in lg or lg in _k:
                _cup_key = _k
                break
        note.append("杯赛参数: %s(league_avg=%.2f home=%.2f away=%.2f fatigue=%.2f rho=%.2f)" % (
            _cup_key, cal.get("league_avg"), cal.get("home", 1.0), cal.get("away", 1.0),
            cal.get("fatigue", 1.0), cal.get("rho", 0.0)))
    # 联赛基准偏差检查: 配置 vs 近30场实测, 偏差>阈值 -> λ基准向实测平移(防规则改动/基准漂移)
    _league_avg_shifted = False
    _base_dev = 0.0
    _recent_info = recent_league_avg().get(lg)
    if _recent_info and abs(_recent_info[0] - league_avg) > LEAGUE_AVG_DEV_TOL:
        _old_avg = league_avg
        _base_dev = round(_recent_info[0] - _old_avg, 3)
        league_avg = round(_old_avg + _base_dev * LEAGUE_AVG_SHIFT_W, 3)
        _league_avg_shifted = True
        note.append("联赛基准偏差: %s 配置%.2f vs 近%d场实测%.2f (Δ%+.2f), λ基准已平移%.0f%% -> %.2f" % (
            lg, _old_avg, _recent_info[1], _recent_info[0], _base_dev,
            LEAGUE_AVG_SHIFT_W * 100, league_avg))
    h_rec, h_div, h_fb, h_w, h_xd, h_q = match_stats(m["home"], div, team_stats, index)
    a_rec, a_div, a_fb, a_w, a_xd, a_q = match_stats(m["away"], div, team_stats, index)
    # ---- 数据包BSD攻防增强注入 (PKG_BOOST): match_package 已拉 BSD 攻防, 本地库缺失/陈旧时启用 ----
    _pkg = None
    if os.environ.get("PKG_BOOST", "1") != "0":
        try:
            _pa = pkg_attacks()
            _pkg = None
            try:
                _eid = str(m.get("id") or "")
                _eid_stripped = _eid[5:] if _eid.startswith("apifb") else _eid
                _pkg = _pa["by_id"].get(_eid) or _pa["by_id"].get(_eid_stripped)
                if _pkg is None:
                    _pkg = _pa["by_id"].get(int(_eid_stripped or 0))
            except Exception:
                _pkg = None
            if not _pkg:
                _bn = _pa["by_name"]
                _nh, _na = _norm(m["home"]), _norm(m["away"])
                _nh2 = _norm(_resolve_alias(m["home"])) or _nh
                _na2 = _norm(_resolve_alias(m["away"])) or _na

                def _pkg_cands(d, names):
                    out = []
                    for n in names:
                        if n and d.get(n):
                            out.extend(d[n])
                    if out:
                        return out
                    for n in names:
                        if not n:
                            continue
                        ws = set(n.split())
                        for _k, _vs in d.items():
                            wk = set(_k.split())
                            if ws and wk and (ws <= wk or wk <= ws):
                                small, big = (ws, wk) if len(ws) <= len(wk) else (wk, ws)
                                if len(small) == 1 or len(small) / len(big) >= 0.6:
                                    out.extend(_vs)
                    return out

                _hc = _pkg_cands(_bn["home"], [_nh, _nh2])
                _ac = _pkg_cands(_bn["away"], [_na, _na2])
                # 同名队多包时, 优先同一包同时匹配主客(防跨场错配: Botafogo 旧包223326)
                _both = [r for r in _hc if r in _ac]
                _pkg = _both[0] if _both else None
                if _pkg is None and _hc and _ac:
                    _pkg = {"home": _hc[0]["home"], "away": _ac[0]["away"],
                            "home_inj_n": _hc[0].get("home_inj_n", 0), "away_inj_n": _ac[0].get("away_inj_n", 0),
                            "home_inj": _hc[0].get("home_inj", []), "away_inj": _ac[0].get("away_inj", []),
                            "home_inj_recs": _hc[0].get("home_inj_recs", []),
                            "away_inj_recs": _ac[0].get("away_inj_recs", [])}
        except Exception:
            _pkg = None
    _pkg_inj_notes = []
    if _pkg:
        # 本地匹配质量 exact 时保留本地(BSD补充伤停); subset/fuzzy/none 时用 BSD 精确 team_id 攻防覆盖, 消除跨联赛错配
        _need_h = h_rec is None or h_w < INDEP_MIN_WEIGHT or h_q in ("subset", "fuzzy", "none")
        _need_a = a_rec is None or a_w < INDEP_MIN_WEIGHT or a_q in ("subset", "fuzzy", "none")
        if _need_h and _pkg.get("home"):
            h_rec = dict(_pkg["home"]); h_rec["src_w"] = 1.0; h_rec["src_tag"] = "bsd"
            h_w = 1.0
            h_fb = h_xd = False; h_div = None
            h_q = "exact"
        if _need_a and _pkg.get("away"):
            a_rec = dict(_pkg["away"]); a_rec["src_w"] = 1.0; a_rec["src_tag"] = "bsd"
            a_w = 1.0
            a_fb = a_xd = False; a_div = None
            a_q = "exact"
        if _pkg.get("home_inj_n", 0) >= 3:
            _pkg_inj_notes.append("主队伤停%d人(如%s)" % (_pkg["home_inj_n"], ",".join(_pkg.get("home_inj") or [])[:36]))
        if _pkg.get("away_inj_n", 0) >= 3:
            _pkg_inj_notes.append("客队伤停%d人(如%s)" % (_pkg["away_inj_n"], ",".join(_pkg.get("away_inj") or [])[:36]))
        if _pkg_inj_notes:
            note.append("数据包伤停: " + "; ".join(_pkg_inj_notes))
    indep = (h_rec is not None and a_rec is not None
             and h_w >= INDEP_MIN_WEIGHT and a_w >= INDEP_MIN_WEIGHT)
    avg_atk = league_avg / 2.0
    # P1-2 审计: 联赛级 λ 钳位 (league_calib.json 可选 lam_min/lam_max; 缺省用全局兜底)
    _lmin = _to_float(cal.get("lam_min"), DEFAULT_LAM_MIN)
    _lmax = _to_float(cal.get("lam_max"), DEFAULT_LAM_MAX)
    if _lmin >= _lmax:
        _lmin, _lmax = DEFAULT_LAM_MIN, DEFAULT_LAM_MAX

    def _eff_rate(x, avg, xd, n):
        return effective_rate(x, avg, xd, n)

    hgf_eff = hga_eff = agf_eff = aga_eff = None
    h_low = a_low = False
    if h_rec:
        hgf_eff, h_low = _eff_rate(h_rec["home_gf"], avg_atk, h_xd, h_rec.get("n_home"))
        hga_eff, _ = _eff_rate(h_rec["home_ga"], avg_atk, h_xd, h_rec.get("n_home"))
        h_src = h_rec.get("src_tag") or "?"
    else:
        h_src = "?"
    if a_rec:
        agf_eff, a_low = _eff_rate(a_rec["away_gf"], avg_atk, a_xd, a_rec.get("n_away"))
        aga_eff, _ = _eff_rate(a_rec["away_ga"], avg_atk, a_xd, a_rec.get("n_away"))
        a_src = a_rec.get("src_tag") or "?"
    else:
        a_src = "?"

    # 教练量化修正(BSD 教练历史统计归一, 纯数值无AI主观): 主客攻防 gf/ga 乘修正系数
    #   强防守教练(低ga) -> def<1 -> 压低对手λ; 执教<80场按样本衰减修正力度
    _cm = m.get("coach_mods") or {}
    if _cm:
        if h_rec:
            hgf_eff = hgf_eff * _cm.get("h_atk", 1.0)
            hga_eff = hga_eff * _cm.get("h_def", 1.0)
        if a_rec:
            agf_eff = agf_eff * _cm.get("a_atk", 1.0)
            aga_eff = aga_eff * _cm.get("a_def", 1.0)
        _ct = cq.mod_text(_cm)
        if _ct:
            note.append(_ct)
    elif m.get("coach_missing"):
        note.append("教练数据未提取(BSD缓存无该教练/联赛池退化)")

    # 德国杯第一轮客队进攻放大 (r1_away_boost): BSD 1148场实测 R1客均2.83球 >> 泊松基准,
    #   强弱悬殊大球被系统性低估; league_avg 在λ公式中为分母(升基准反降λ), 故用攻防侧放大
    if _cup_key == "德国杯" and cal.get("r1_away_boost") and agf_eff is not None:
        _r1_win = cal.get("r1_window")
        _d_str = None
        try:
            _d_str = m["ct"].date().isoformat()
        except Exception:
            _d_str = str(m.get("ct"))[:10]
        if _r1_win and _d_str and _r1_win[0] <= _d_str <= _r1_win[1]:
            agf_eff = round(agf_eff * cal["r1_away_boost"], 3)
            note.append("德国杯第一轮客队进攻放大×%.2f(BSD实测R1客均2.83球, 强弱悬殊大球)" % cal["r1_away_boost"])

    if h_rec and a_rec:
        # 双方有独立数据: 标准泊松 (含收缩后的攻防)
        if h_fb:
            note.append("主队数据来自%s" % h_div)
        if a_fb:
            note.append("客队数据来自%s" % a_div)
        if h_xd:
            note.append("主队跨联赛用%s数据(快照联赛与数据联赛不符), 攻防收缩%d%%" % (h_div, int(PROMO_SHRINK * 100)))
        if a_xd:
            note.append("客队跨联赛用%s数据(快照联赛与数据联赛不符), 攻防收缩%d%%" % (a_div, int(PROMO_SHRINK * 100)))
        if h_low:
            note.append("主队样本偏少, 攻防向联赛均值收缩")
        if a_low:
            note.append("客队样本偏少, 攻防向联赛均值收缩")
        if h_w < INDEP_MIN_WEIGHT:
            note.append("主队攻防仅旧赛季(%s), 低置信" % h_rec.get("src_season"))
        if a_w < INDEP_MIN_WEIGHT:
            note.append("客队攻防仅旧赛季(%s), 低置信" % a_rec.get("src_season"))
        _inj_h = _injury_coef(_pkg.get("home_inj_recs")) if _pkg else 1.0
        _inj_a = _injury_coef(_pkg.get("away_inj_recs")) if _pkg else 1.0
        lam_res = calc_lambdas(home_gf=hgf_eff, away_ga=aga_eff, away_gf=agf_eff, home_ga=hga_eff,
                               league_avg=league_avg, home_coef=cal["home"], away_coef=cal["away"],
                               fatigue_coef=cal["fatigue"], injury_coef_h=_inj_h, injury_coef_a=_inj_a,
                               risk_signal_h=0.0, risk_signal_a=0.0, rho=cal["rho"],
                               lam_min=_lmin, lam_max=_lmax)
        lam_h, lam_a = lam_res["lam_h"], lam_res["lam_a"]
    else:
        # 一方缺数据: 只降级缺侧, 保留有数据侧真实攻防 (修复"整场丢弃"bug)
        implied = implied_lambdas_from_odds(m, league_avg, cal["rho"])
        _inj_h = _injury_coef(_pkg.get("home_inj_recs")) if _pkg else 1.0
        _inj_a = _injury_coef(_pkg.get("away_inj_recs")) if _pkg else 1.0
        if h_rec:
            lam_h = max(_lmin, min(_lmax, hgf_eff * (aga_eff if a_rec else avg_atk) / avg_atk
                                   * cal["home"] * cal["fatigue"] * _inj_h))
        else:
            lam_h = max(_lmin, min(_lmax, (implied[0] if implied else league_avg / 2) * _inj_h))
        if a_rec:
            lam_a = max(_lmin, min(_lmax, agf_eff * (hga_eff if h_rec else avg_atk) / avg_atk
                                   * cal["away"] * cal["fatigue"] * _inj_a))
        else:
            lam_a = max(_lmin, min(_lmax, (implied[1] if implied else league_avg / 2) * _inj_a))
        if h_rec is None and a_rec is None:
            note.append("双方无独立攻防, 用市场隐含λ/联赛基准(无独立信号, 不出单)")
            if implied:
                h_src = a_src = "market"
            else:
                h_src = a_src = "baseline"
        else:
            if h_rec is None:
                note.append("主队无近期独立数据, λ用市场隐含/基准(仅该侧降级)")
                h_src = "market" if implied else "baseline"
            if a_rec is None:
                note.append("客队无近期独立数据, λ用市场隐含/基准(仅该侧降级)")
                a_src = "market" if implied else "baseline"
    if h_q in ("subset", "fuzzy"):
        note.append("主队队名模糊匹配(%s), 低置信" % h_q)
    if a_q in ("subset", "fuzzy"):
        note.append("客队队名模糊匹配(%s), 低置信" % a_q)
    if not indep:
        note.append("非独立数据场次, best_bet禁用")
    grid = dc_score_grid(lam_h, lam_a, rho=cal["rho"], max_goals=9)
    def P(cond):
        return sum(grid[i][j] for i in range(10) for j in range(10) if cond(i, j))
    raw = [P(lambda i, j: i > j), P(lambda i, j: i == j), P(lambda i, j: i < j)]
    cal_probs = apply_prob_calibration(list(raw), shrink=cal["shrink"]) if cal["shrink"] != 1.0 else list(raw)
    h2h = m.get("h2h") or {}
    overround_1x2 = None
    fair = None
    if h2h.get("home"):
        s = 1 / h2h["home"] + 1 / h2h["draw"] + 1 / h2h["away"]
        overround_1x2 = s
        fair = [(1 / h2h["home"]) / s, (1 / h2h["draw"]) / s, (1 / h2h["away"]) / s]
    # ---- 平局预警(2026-08-19 3万场实证): 市场去水平局概率>=26% 提前计算, 供规则①让球+号过滤/规则③降星使用 ----
    # 双源并集: BSD consensus(主源) 与 the-odds 旧快照(h2h_prev) 去水平局取更高, 防源切换导致阈值临界跳变
    draw_warn = None
    _dw_prob = fair[1] if fair else 0.0
    _h2h_prev = m.get("h2h_prev") or {}
    if _h2h_prev.get("home"):
        try:
            _s2 = 1 / _h2h_prev["home"] + 1 / _h2h_prev["draw"] + 1 / _h2h_prev["away"]
            _dw_prob = max(_dw_prob, (1 / _h2h_prev["draw"]) / _s2)
        except Exception:
            pass
    # 规则13(2026-08-27 西甲3043场实证): 西甲防平预警线 26%->28%(平赔3.0-3.5平局率30-34% vs 基准26.5%);
    #   平赔<=3.5 且去水平局>=28% 升强预警(奥萨苏纳0-0/瓦伦西亚0-0实证)
    _dw_min = float(cal.get("draw_warn_min", DRAW_WARN_MIN)) if lg == "西甲" else DRAW_WARN_MIN
    _dw_strong = float(cal.get("draw_warn_strong", DRAW_WARN_STRONG)) if lg == "西甲" else DRAW_WARN_STRONG
    if _dw_prob >= _dw_min:
        _dw_strong_f = _dw_prob >= _dw_strong
        if lg == "西甲" and h2h.get("draw") and h2h["draw"] <= 3.5 and _dw_prob >= _dw_min:
            _dw_strong_f = True
        draw_warn = {"market_draw_prob": round(_dw_prob * 100, 1), "strong": _dw_strong_f}
    bets = []
    sp = m.get("spread")
    if sp and sp.get("home_price") and sp.get("away_price"):
        hdp = sp["hdp_home"]
        home_cov = handicap_cover_prob(grid, hdp)
        away_cov = 1 - home_cov
        bets.append({"name": "让球主(%+.1f)" % hdp, "prob": round(home_cov, 4), "odds": sp["home_price"],
                     "ev": round(home_cov * sp["home_price"] - 1, 4)})
        bets.append({"name": "让球客(%+.1f)" % (-hdp), "prob": round(away_cov, 4), "odds": sp["away_price"],
                     "ev": round(away_cov * sp["away_price"] - 1, 4)})
    tt = m.get("totals")
    if tt and tt.get("line"):
        line = tt["line"]
        if abs(line - round(line)) < 0.01:
            push = P(lambda i, j: abs(i + j - line) < 0.01)
            under_p = P(lambda i, j: i + j < line) + push * 0.5
            over_p = P(lambda i, j: i + j > line) + push * 0.5
        else:
            under_p = P(lambda i, j: i + j < line)
            over_p = 1 - under_p
        bets.append({"name": "小%.2f" % line, "prob": round(under_p, 4), "odds": tt["under_price"],
                     "ev": round(under_p * tt["under_price"] - 1, 4)})
        bets.append({"name": "大%.2f" % line, "prob": round(over_p, 4), "odds": tt["over_price"],
                     "ev": round(over_p * tt["over_price"] - 1, 4)})
    # 方案A(2026-08-24): 按对阵强度分段校准大球 — 葡超348场拟合: 独立泊松低估大球(强强+12.5/混合+9.0/弱弱+3.5pp)
    #   触发: 联赛配置 ou_strength_adj {档位: 大球概率修正量(正=上修, 负=下调, 墨超876场实证模型高估大球强强-6.6/混合-3.2pp)};
    #   按双方攻击指数分档(强强>=1.05 / 弱弱<=0.95 / 其余混合)
    _ou_adj = (cal.get("ou_strength_adj") or {}) if cal else {}
    if _ou_adj:
        try:
            _a_atk = league_avg / 2.0
            _hi = (hgf_eff or 0.0) / _a_atk if _a_atk > 0 else 1.0
            _ai = (agf_eff or 0.0) / _a_atk if _a_atk > 0 else 1.0
            if _hi >= 1.05 and _ai >= 1.05:
                _obucket = "强强"
            elif _hi <= 0.95 and _ai <= 0.95:
                _obucket = "弱弱"
            else:
                _obucket = "混合"
            _oadj = float(_ou_adj.get(_obucket, 0.0) or 0.0)
            if _oadj != 0:
                for _b in bets:
                    if _b.get("ev_pre_ou_adj") is None:
                        _b["ev_pre_ou_adj"] = _b["ev"]
                    if _b["name"].startswith("大"):
                        _po = min(0.95, max(0.05, _b["prob"] + _oadj))
                        _b["ev"] = round((_po / _b["prob"]) * (_b["ev"] + 1.0) - 1.0, 4)
                        _b["prob"] = round(_po, 4)
                        _b["ou_bucket"] = _obucket
                    elif _b["name"].startswith("小"):
                        _pu = max(0.05, min(0.95, _b["prob"] - _oadj))
                        _b["ev"] = round((_pu / _b["prob"]) * (_b["ev"] + 1.0) - 1.0, 4)
                        _b["prob"] = round(_pu, 4)
                        _b["ou_bucket"] = _obucket
                _o_dir = "+" if _oadj > 0 else ""
                note.append("方案A大球校准: %s档 大球概率%s%.0fpp(%s, 分档拟合实证)" % (_obucket, _o_dir, _oadj * 100, lg))
        except Exception:
            pass
    # 规则14(2026-08-27 五大19763场切片实证): OU市场价值区 — 按市场隐含大2.5概率区间校准大/小球概率
    #   偏差=实际大球率-市场隐含: 法甲0.50-0.60 +3.5pp/意甲0.50-0.55 +3.6pp(0.60+ -3.7pp追大亏)/
    #   西甲0.55-0.60 +3.2pp/德甲0.60-0.70 +3.0pp; 英超≈有效市场不配. 与方案A同机制, 校准后EV重算.
    _ou_zones = cal.get("ou_mkt_zones") or []
    if _ou_zones and tt and tt.get("line"):
        try:
            _ovp, _unp = float(tt["over_price"]), float(tt["under_price"])
            if _ovp > 1 and _unp > 1:
                _imp_over = (1.0 / _ovp) / (1.0 / _ovp + 1.0 / _unp)
                _z = None
                for _zo in _ou_zones:
                    if float(_zo.get("imp_lo", 0.0)) <= _imp_over < float(_zo.get("imp_hi", 1.0)):
                        _z = _zo
                        break
                if _z:
                    _zadj = float(_z.get("over_adj", 0.0) or 0.0)
                    if _zadj != 0:
                        for _b in bets:
                            if _b.get("ev_pre_ou_adj") is None:
                                _b["ev_pre_ou_adj"] = _b["ev"]
                            if _b["name"].startswith("大"):
                                _po = min(0.95, max(0.05, _b["prob"] + _zadj))
                                _b["ev"] = round((_po / _b["prob"]) * (_b["ev"] + 1.0) - 1.0, 4)
                                _b["prob"] = round(_po, 4)
                                _b["ou_mkt_zone"] = "%.2f-%.2f" % (float(_z["imp_lo"]), float(_z["imp_hi"]))
                            elif _b["name"].startswith("小"):
                                _pu = max(0.05, min(0.95, _b["prob"] - _zadj))
                                _b["ev"] = round((_pu / _b["prob"]) * (_b["ev"] + 1.0) - 1.0, 4)
                                _b["prob"] = round(_pu, 4)
                                _b["ou_mkt_zone"] = "%.2f-%.2f" % (float(_z["imp_lo"]), float(_z["imp_hi"]))
                        note.append("OU价值区校准: %s 市场隐含大%.0f%%∈[%.0f%%-%.0f%%] 大球%s%.0fpp(19763场切片实证)" % (
                            lg, _imp_over * 100, float(_z["imp_lo"]) * 100, float(_z["imp_hi"]) * 100,
                            "+" if _zadj > 0 else "", _zadj * 100))
        except Exception:
            pass
    if h2h.get("home") and overround_1x2:
        for label, prob, price in (("主胜", cal_probs[0], h2h["home"]),
                                   ("平局", cal_probs[1], h2h["draw"]),
                                   ("客胜", cal_probs[2], h2h["away"])):
            e = prob * price - 1
            bets.append({"name": "1X2" + label, "prob": round(prob, 4), "odds": price,
                         "ev": round(e, 4), "is_1x2": True})
    # 第五类: 基准偏差联动小球 —— 实测进球高于配置时, 小球概率系统性虚高, 小盘EV按偏差比例校准打折(非风控折损)
    if _league_avg_shifted and _base_dev > 0:
        _under_disc = 1 - min(0.5, _base_dev * 0.5)
        for b in bets:
            if b["name"].startswith("小"):
                b["ev"] = round(b["ev"] * _under_disc, 4)
        note.append("小球EV校准: 基准上移Δ%+.2f球, 小盘EV×%.2f(防小球虚高)" % (_base_dev, _under_disc))
    # 概率封顶校准: >65%单腿压至PROB_CAP, EV=(p_new/p_old)*(ev_old+1)-1 同抽水重算
    _n_capped = 0
    for b in bets:
        if b["prob"] > PROB_CAP:
            _raw = b["prob"]
            b["prob"] = PROB_CAP
            b["ev"] = (PROB_CAP / _raw) * (b["ev"] + 1.0) - 1.0
            b["prob_raw"] = _raw
            _n_capped += 1
    if _n_capped:
        note.append("概率封顶校准: %d腿概率>%.0f%%压至%.0f%%(实测高置信档高估, EV同抽水重算)" % (_n_capped, PROB_CAP * 100, PROB_CAP * 100))

    # 规则2: 让球主/小球 且原始概率∈[0.65,0.70) 不纳入候选(历史命中仅21.9%)
    _n_pband = 0
    for b in bets:
        _p_raw = b.get("prob_raw") or b["prob"]
        if PROB_BAN_LO <= _p_raw < PROB_BAN_HI and (b["name"].startswith("让球主") or b["name"].startswith("小")):
            b["_pband_banned"] = True
            _n_pband += 1
    if _n_pband:
        note.append("概率禁带: %d腿让球主/小球概率∈[%.0f%%,%.0f%%)实测高估, 不纳入候选" % (
            _n_pband, PROB_BAN_LO * 100, PROB_BAN_HI * 100))

    # 规则①(2026-08-23 M-20260823-01): 平局预警26%+ -> 让球只用+号(受让方), 移除-号让球腿(平局直接吃盘)
    _n_dw_hdp = 0
    if draw_warn and DRAW_WARN_HDP_PLUS_ONLY:
        _keep = []
        for b in bets:
            if b["name"].startswith(("让球主", "让球客")):
                try:
                    _h = float(b["name"].split("(")[1].split(")")[0])
                    if _h < 0:
                        _n_dw_hdp += 1
                        continue
                except Exception:
                    pass
            _keep.append(b)
        if _n_dw_hdp:
            bets = _keep
            note.append("平局预警(去水平局%.0f%%)→让球只用+号(受让方), 移除%d个-号让球腿" % (draw_warn["market_draw_prob"], _n_dw_hdp))

    # 规则5/6A(2026-08-24 用户指令: 让球+/−方向按球队强弱判定, 不统一客队):
    #   +/- 由盘口强弱决定: 让球方(强队, hdp<0) 仅保留中浅让 -0.8~-0.2; 深盘让 hdp<=-1.0 禁出(穿盘率低, 账本-33%)
    #   受让方(弱队, hdp>0) 为正确方向保留(含"客强主受"让球主+号, 原⑥A按主/客标签误杀); 深受让 hdp>=+1.8 禁出(账本全亏)
    #   平手盘(0.0) 禁出(陷阱)
    _n_hdp_dir_ban = 0
    _keep_dir = []
    for _b in bets:
        if _b["name"].startswith(("让球主", "让球客")):
            try:
                _hd = float(_b["name"].split("(")[1].split(")")[0])
            except Exception:
                _hd = 0.0
            _zone_ban = False
            for _zb in (cal.get("hdp_home_ban_zones") or []):
                try:
                    if float(_zb.get("lo", 0.0)) <= _hd <= float(_zb.get("hi", 0.0)):
                        _zone_ban = True
                        break
                except Exception:
                    pass
            if _zone_ban:
                _n_hdp_dir_ban += 1
                continue
            if _hd == HDP_BAN_DRAW or _hd <= HDP_BAN_GIVE_DEEP or _hd >= HDP_BAN_RECEIVE_DEEP:
                _n_hdp_dir_ban += 1
                continue
        _keep_dir.append(_b)
    if _n_hdp_dir_ban:
        bets = _keep_dir
        _hdp_ban_notes = []
        for _zb in (cal.get("hdp_home_ban_zones") or []):
            _hdp_ban_notes.append("主受让+%.2f~+%.2f(19763场切片实证主赢盘41.6%%)" % (
                float(_zb.get("lo", 0.0)), float(_zb.get("hi", 0.0))))
        note.append("让球方向按强弱禁出: 移除%d腿(平手/深盘让<=-1.0/深受让>=+1.8%s; 保留让球方-0.2~-0.8与受让方+号; 主客一视同仁)" % (
            _n_hdp_dir_ban, (", " + " ".join(_hdp_ban_notes)) if _hdp_ban_notes else ""))
    # 规则13(2026-08-27 西甲3043场实证 → 同日泛化五大): 热主价值陷阱区
    #   西甲[1.55,2.20) 主胜仅48-54%/平30%+; 五大19763场切片 主胜2.00-2.20 实际仅40.8(英超)-48.6%(法甲)% 隐含≈50%+抽水必亏
    #   处置: 让球主-号(主队让球)腿移出候选; 受让+号/客胜/大小球方向保留(方向自动转反向, 毕尔巴鄂1-3/奥萨苏纳0-0实证)
    _hot_home_lo = float(cal.get("hot_home_ban_lo") or cal.get("laliga_hot_home_lo") or 0.0)
    _hot_home_hi = float(cal.get("hot_home_ban_hi") or cal.get("laliga_hot_home_hi") or 0.0)
    _laliga_hot = bool(h2h.get("home") and _hot_home_lo and _hot_home_hi
                       and _hot_home_lo <= h2h["home"] < _hot_home_hi)
    if _laliga_hot:
        _keep_hot, _n_hot = [], 0
        for _b in bets:
            if _b["name"].startswith("让球主"):
                try:
                    _hh = float(_b["name"].split("(")[1].split(")")[0])
                except Exception:
                    _hh = 0.0
                if _hh < 0:
                    _n_hot += 1
                    continue
            _keep_hot.append(_b)
        if _n_hot:
            bets = _keep_hot
            note.append("规则13热主禁追(%s): 主胜%.2f∈[%.2f,%.2f), 移除%d个让球主-号腿(五大19763场切片: 主胜2.00-2.20实际40.8-48.6%%/西甲1.55-2.20平30%%+)" % (
                lg, h2h["home"], _hot_home_lo, _hot_home_hi, _n_hot))

    # 规则5残项(2026-08-23 M-20260823-05): 让球客标准档EV8-20%仍禁出(账本18注-26.5%, 独立于方向)
    _n_away_ban = 0
    _keep5 = []
    for _b in bets:
        if _b["name"].startswith("让球客"):
            _ev5 = _b.get("ev", 0.0)
            if 0.08 <= _ev5 < 0.20:
                _n_away_ban += 1
                continue
        _keep5.append(_b)
    if _n_away_ban:
        bets = _keep5
        note.append("让球客标准档禁出: 移除%d腿(EV8-20%%: 账本18注-26.5%%)" % _n_away_ban)


    # 规则6(2026-08-23 M-20260823-06): 方向归因重灾区禁出(账本star非空161腿实证)
    #   A 让球主方向部分已并入上方"让球方向按强弱禁出"(不再按主/客标签一刀切, 主受按强弱保留)
    #   B 小2.50高价值档(EV>=20%): 升级规则②, 从降星改为物理禁出(高价值档24注-2.60/-10.8%, 南安普顿+37/西汉姆+35/蒙特利尔+44全错)
    _n_small250_ban = 0
    _keep6 = []
    for _b6 in bets:
        _n6 = _b6["name"]
        if _n6.startswith("小") and abs(float(_n6[1:]) - DRAW_WARN_TOTALS_LINE) < 0.01 and _b6.get("ev_pre_ou_adj", _b6.get("ev", 0.0)) >= SMALL_250_HIGH_EV:
            _n_small250_ban += 1
            continue
        _keep6.append(_b6)
    if _n_small250_ban:
        bets = _keep6
        note.append("规则6小2.50高EV禁出(按方案A校准前EV): 移除%d腿(EV>=%.0f%%, 高价值档24注-10.8%%, 升级规则②反向标记->禁出)" % (_n_small250_ban, SMALL_250_HIGH_EV * 100))


    # 规则7(2026-08-23 M-20260823-07): 强平局预警(去水平局>=30%) + 大小球2.50盘 -> 移除2.50大小球腿, 改打+号受让
    #   依据: 平局专杀2.50盘(0-0/1-1低分平局吃大球); 强预警场次让客+号多数负EV -> 无正EV+号则无单
    if draw_warn and draw_warn.get("strong"):
        _n7 = 0
        _keep7 = []
        for _b7 in bets:
            if _b7["name"].startswith(("大", "小")):
                try:
                    if abs(float(_b7["name"][1:]) - DRAW_WARN_TOTALS_LINE) < 0.01:
                        _n7 += 1
                        continue
                except Exception:
                    pass
            _keep7.append(_b7)
        if _n7:
            bets = _keep7
            note.append("规则7强预警改+号: 强平局预警>=%.0f%%+2.50大小球盘移除%d腿, 只打+号受让(无正EV+号则无单)" % (DRAW_WARN_STRONG * 100, _n7))

    def ev_tier_label(ev):
        for _label, _th, _stake in EV_TIERS:
            if ev >= _th:
                return _label, _stake
        return "垃圾", 0.0

    # 规则⑨(2026-08-24): 假小球拦截 — 模型自算大球>=50% 却出现小球正EV = λ低估假信号
    #   触发: 任一 小球腿 ev>0 且 模型P(大2.5)>=50% 且 市场隐含大>=60%
    #   处置: 该小球腿 _pband_banned 移出候选(不出单/不输出方向); 真小球(λ和市场双低)不受影响
    #   实证: 荷甲账本5注小球全灭(高进球联赛逆市场推小=系统性错误)
    _fake_small_ban, _model_over, _mkt_over = fake_small_intercept(bets, tt)
    # 规则⑪(2026-08-27): 低估区禁小球 — 移出候选+方向(不出单/不输出方向)
    _under_ban_small = under_zone_ban_small(bets, lg, cal, _league_avg_shifted, _base_dev)
    ev_min = EV_TIER_INTEL if HAS_INTEL else EV_TIER_BATCH
    odds_floor = ODDS_FLOOR_MAIN if lg not in SECONDARY_LEAGUES else ODDS_FLOOR_SEC
    valid = [b for b in bets if not b.get("is_1x2") and not b.get("_pband_banned")
             and b["ev"] >= ev_min and b["odds"] >= odds_floor]
    best = max(valid, key=lambda b: b["prob"]) if (valid and indep) else None
    hot_home = fair[0] >= fair[2] if fair else True
    hot_team = m["home"] if hot_home else m["away"]
    hdp_val = sp["hdp_home"] if sp else 0.0
    hot_odds = h2h.get("home", 2.5) if hot_home else h2h.get("away", 2.5)
    feature_pack = {"lam_base_diff": round(lam_h - lam_a, 3), "home_injury_weight": 1.0,
                    "away_injury_weight": 1.0, "fatigue_level": cal["fatigue"],
                    "sample_n_home": 38, "sample_n_away": 38,
                    "hot_side": "home" if hot_home else "away"}
    _snap_date = None
    _snap_day_prev = False
    try:
        _sd = datetime.fromisoformat(str(m["snap"]).replace("Z", "+00:00"))
        if _sd.tzinfo is None:
            _sd = _sd.replace(tzinfo=timezone.utc)
        snap_age_h = round((m["ct"] - _sd).total_seconds() / 3600.0, 1)
        _snap_date = _sd.date().isoformat()
        _snap_day_prev = _sd.date() < m["ct"].date()
    except Exception:
        snap_age_h = None
    upset = UpsetEngineV2().assess(hot_team, "", "", "", hdp_val, hot_odds, line_note="", league_type="",
                                   fair_h=fair[0] if fair else None, fair_a=fair[2] if fair else None,
                                   fair_d=fair[1] if fair else None, odds_disparity=0.0,
                                   cup_mode=False, feature_pack=feature_pack, hot_is_home=hot_home)
    lam_sum = round(lam_h + lam_a, 2)
    # 第四类: 风控标签只降星级/仓位, 不修改EV原值
    risk_tags = []
    warn_codes = []
    # P1-4 审计(2026-08-27): effective_rate 样本分层收缩联动 λ 层告警码
    if h_low or a_low:
        _sl_side = ("主" if h_low else "") + ("/客" if a_low else "")
        _sl_tag = "样本不足(%s队, 攻防收缩30%%)" % _sl_side
        if _sl_tag not in risk_tags:
            risk_tags.append(_sl_tag)
        warn_codes.append("SAMPLE_LOW")
    if not HAS_INTEL:
        _has_bsd_inj = bool(_pkg) and (_pkg.get("home_inj_n", 0) + _pkg.get("away_inj_n", 0)) > 0
        if not _has_bsd_inj:
            risk_tags.append("纯数据无伤病情报")
    if _pkg and (_pkg.get("home_inj_n", 0) >= 3 or _pkg.get("away_inj_n", 0) >= 3):
        risk_tags.append("伤停>2人(主%d/客%d)" % (_pkg.get("home_inj_n", 0), _pkg.get("away_inj_n", 0)))
    if not (sp and sp.get("home_price") and sp.get("away_price")):
        risk_tags.append("缺亚盘")
    if not (tt and tt.get("line")):
        risk_tags.append("缺大小球")
    if lam_sum > 4.0:
        risk_tags.append("λ过高(%.2f)" % lam_sum)
    if _league_avg_shifted:
        risk_tags.append("联赛基准偏差(λ已平移)")
    if _league_avg_shifted and _base_dev > 0:
        risk_tags.append("小球校准折扣")
    if not indep:
        risk_tags.append("非独立数据")
    if h_rec is None or a_rec is None:
        risk_tags.append("队名/数据缺失")
    if h_q in ("subset", "fuzzy") or a_q in ("subset", "fuzzy"):
        risk_tags.append("队名模糊匹配")
    if _fake_small_ban:
        risk_tags.append("假小球拦截(%d腿: 模型大%.0f%%>=50%%+市场隐含大>=60%%, λ低估假信号)" % (_fake_small_ban, (_model_over or 0) * 100))
        note.append("规则9: 假小球拦截 %d 腿 — 模型自算大球>=50%%却出小球正EV, λ低估假信号, 移出候选(300场复盘验证)" % _fake_small_ban)
    if _under_ban_small:
        _ub_tag = "低估区禁小球(%d腿: %s, 小球只在λ高估区推)" % (_under_ban_small, lg)
        if _ub_tag not in risk_tags:
            risk_tags.append(_ub_tag)
        note.append("规则11: 低估区禁小球 %d 腿 — %s 小球为陷阱, 移出候选+方向(300场复盘英冠20%%/荷甲0%%/德国杯0%%+账本英冠31%%/荷甲22%%/英联杯0%%/欧冠0%%)" % (_under_ban_small, lg))
    # ---- 平局预警(2026-08-19 3万场实证): 市场去水平局概率>=26% -> 平局预警标签(只降星/降仓/标注, 不出平局单) ----
    if draw_warn:
        _dw_tag = "平局预警(市场去水平局>=%.0f%%)" % (DRAW_WARN_MIN * 100)
        if draw_warn["strong"]:
            if lg == "西甲" and draw_warn["market_draw_prob"] < DRAW_WARN_STRONG * 100:
                _dw_tag = "平局预警-强(西甲: 去水平局%.0f%% 且平赔<=3.5)" % draw_warn["market_draw_prob"]
            else:
                _dw_thr = (_dw_strong if lg == "西甲" else DRAW_WARN_STRONG)
                _dw_tag = "平局预警-强(市场去水平局>=%.0f%%)" % (_dw_thr * 100)
        if _dw_tag not in risk_tags:
            risk_tags.append(_dw_tag)
        if _n_dw_hdp:
            _dw_plus_tag = "平局预警→让球只用+号(受让方)"
            if _dw_plus_tag not in risk_tags:
                risk_tags.append(_dw_plus_tag)
    if _laliga_hot:
        _tg13c = "热主禁追区(%s: 主胜%.2f∈[%.2f,%.2f))" % (
            lg, h2h["home"], _hot_home_lo, _hot_home_hi)
        if _tg13c not in risk_tags:
            risk_tags.append(_tg13c)
    # 规则②(2026-08-23 M-20260823-02): 小2.50高EV反向标记(实证南安普顿+37/西汉姆+35/蒙特利尔+44全错) -> 打反向标签, 自动降星降仓
    _small250_hi = [b for b in bets if b["name"].startswith("小")
                    and abs(float(b["name"][1:]) - DRAW_WARN_TOTALS_LINE) < 0.01
                    and b["ev"] >= SMALL_250_HIGH_EV]
    if _small250_hi:
        _mx = max(b["ev"] for b in _small250_hi)
        _tag = "小球2.50高EV反向标记(+%.0f%%)" % (_mx * 100)
        if _tag not in risk_tags:
            risk_tags.append(_tag)
        note.append("小球2.50高EV反向标记: 小2.50 EV>=%.0f%% (%d腿, 最高+%.0f%%), 实证3例全错, 反向信号" % (
            SMALL_250_HIGH_EV * 100, len(_small250_hi), _mx * 100))
    # 规则⑧(2026-08-24 账本实证): 赔率高估区标签
    #   主胜1.8~2.2: 真实主胜28%(隐含50%), 平38/客34, 66%平局预警, 受让+号赢盘72% vs 让球-号28%
    #   客胜2.2~2.8: 真实客胜11%(隐含40%), 平50, 94%平局预警, 受让+号赢盘78%, 平手17%
    _overest_tag = None
    if h2h.get("home") and FAV_HOME_OVEREST_LO <= h2h["home"] < FAV_HOME_OVEREST_HI:
        _overest_tag = "主胜高估区(赔率%.2f: 真实主胜28%%, 平局预警下押受让+号)" % h2h["home"]
    elif h2h.get("away") and FAV_AWAY_OVEREST_LO <= h2h["away"] < FAV_AWAY_OVEREST_HI:
        _overest_tag = "客胜高估区(赔率%.2f: 真实客胜11%%, 押受让+号/避平手)" % h2h["away"]
    if _overest_tag:
        if _overest_tag not in risk_tags:
            risk_tags.append(_overest_tag)
        for _b8 in bets:
            if _b8.get("is_1x2") and ((_overest_tag.startswith("主胜") and _b8["name"] == "1X2主胜")
                                      or (_overest_tag.startswith("客胜") and _b8["name"] == "1X2客胜")):
                _b8["_overest_1x2"] = True
        note.append("规则8赔率高估区: %s (1X2热门方向降权参考, 让球押受让+号)" % _overest_tag)

    # ---- 硬否决(复盘中超/J1统一规则): ①过期/隔日盘口 ②模型与市场分歧>阈值 ----
    veto_reason = None
    if best:
        if snap_age_h is not None and snap_age_h > SNAPSHOT_STALE_HOURS:
            veto_reason = "盘口过期(距开赛%.0fh>阈值%.0fh)" % (snap_age_h, SNAPSHOT_STALE_HOURS)
        elif _snap_day_prev:
            veto_reason = "盘口为隔日快照(%s)" % _snap_date
        else:
            _mkt_fair = None
            _name = best["name"]
            try:
                if _name.startswith("让球") and sp and sp.get("home_price") and sp.get("away_price"):
                    _opp = sp["away_price"] if "主" in _name else sp["home_price"]
                    _orr = 1.0 / best["odds"] + 1.0 / _opp
                    _mkt_fair = (1.0 / best["odds"]) / _orr
                elif _name.startswith(("大", "小")) and tt and tt.get("line"):
                    _opp = tt["under_price"] if _name.startswith("大") else tt["over_price"]
                    _orr = 1.0 / best["odds"] + 1.0 / _opp
                    _mkt_fair = (1.0 / best["odds"]) / _orr
            except Exception:
                _mkt_fair = None
            _praw = best.get("prob_raw") or best["prob"]
            if _mkt_fair is not None and _praw - _mkt_fair > MAX_MKT_DIVERGENCE:
                veto_reason = "模型与市场分歧>%dpp(模型%.0f%% vs 市场%.0f%%)" % (
                    int(MAX_MKT_DIVERGENCE * 100), _praw * 100, _mkt_fair * 100)
    if veto_reason:
        _vt = veto_reason + "->否决"
        if _vt not in risk_tags:
            risk_tags.append(_vt)
        best = None
    # ---- 方向输出: 无论是否否决, 都给模型最高概率侧 + 胜平负方向 (仅标注, 不阻断) ----
    direction = None
    if bets:
        _d_pick = max([b for b in bets if not b.get("is_1x2") and not b.get("_pband_banned")]
                     or [b for b in bets if not b.get("_pband_banned")] or bets, key=lambda b: b["prob"])
        _d_mkt = None
        _dn = _d_pick["name"]
        try:
            if _dn.startswith("让球") and sp and sp.get("home_price") and sp.get("away_price"):
                _opp = sp["away_price"] if "主" in _dn else sp["home_price"]
                _o = 1.0 / _d_pick["odds"] + 1.0 / _opp
                _d_mkt = round((1.0 / _d_pick["odds"]) / _o, 4)
            elif _dn.startswith(("大", "小")) and tt and tt.get("line"):
                _opp = tt["under_price"] if _dn.startswith("大") else tt["over_price"]
                _o = 1.0 / _d_pick["odds"] + 1.0 / _opp
                _d_mkt = round((1.0 / _d_pick["odds"]) / _o, 4)
        except Exception:
            _d_mkt = None
        _wdl_names = ("主胜", "平局", "客胜")
        _wdl_i = max(range(3), key=lambda i: cal_probs[i])
        direction = {
            "name": _dn, "prob": round(_d_pick["prob"], 4), "odds": _d_pick["odds"],
            "ev": _d_pick["ev"], "market_fair": _d_mkt,
            "wdl_name": _wdl_names[_wdl_i],
            "wdl_prob": round(cal_probs[_wdl_i], 4),
            "wdl_market_fair": round(fair[_wdl_i], 4) if fair else None,
            "vetoed": bool(veto_reason), "veto_reason": veto_reason,
            "draw_warn": draw_warn,
        }
    if best:
        _tier, _stake = ev_tier_label(best["ev"])
        # 高估区标签(规则⑧)为方向性信息(实证受让+号加权重/让球-号降权重), 不计入n_risk扣星
        # 样本不足(攻防已收缩30%入λ)同为信息性标签, 不再二次扣星(审计P1-1: 收缩即告警, 双罚失真)
        n_risk = len([t for t in risk_tags if t != "纯数据无伤病情报" and "样本不足" not in t and "高估区" not in t])
        star = 3 if best["ev"] >= 0.20 else 2 if best["ev"] >= 0.08 else 1
        star = max(1, star - (1 if n_risk >= 1 else 0) - (1 if n_risk >= 3 else 0))
        # 平局预警降级(3万场实证): 市场去水平局>=26% 且 best为"平局会吃掉的方向腿" -> 降1星+仓位减半
        #   只针对 1X2主/客胜 与 让球负盘方(让球主hdp<0/让球客hdp<0); 普通大小球腿仅标注不降仓(平局不伤OU),
        #   但规则③(2026-08-23)例外: 整球盘2.50 遇预警降星(2.50高EV小球反向3例全错, EV失真)
        _dw_side = False
        if best["name"].startswith(("1X2主胜", "1X2客胜")):
            _dw_side = True
        elif best["name"].startswith(("让球主", "让球客")):
            try:
                _h = float(best["name"].split("(")[1].split(")")[0])
                _dw_side = _h < 0  # 让球负盘方: 平局直接吃盘
            except Exception:
                pass
        if draw_warn and _dw_side:
            star = max(1, star - 1)
            _stake *= DRAW_WARN_STAKE_MULT
        # 规则③(2026-08-23 M-20260823-03): 整球盘2.50遇预警降星(平局预警下2.50大小球EV失真)
        if draw_warn and best["name"].startswith(("大", "小")):
            try:
                if abs(float(best["name"][1:]) - DRAW_WARN_TOTALS_LINE) < 0.01:
                    star = max(1, star - 1)
                    _stake *= DRAW_WARN_STAKE_MULT
                    _dw_t_tag = "整球盘2.50遇预警降星"
                    if _dw_t_tag not in risk_tags:
                        risk_tags.append(_dw_t_tag)
            except Exception:
                pass
# 规则4(2026-08-23): 英冠/荷甲 小球反向标记(210场复盘: 大小球命中25%, 英冠大4/小12, 荷甲全小7场命中28.6%) -> 小球降星+仓位减半
        if cal.get("ou_under_reverse") and best["name"].startswith("小"):
            star = max(1, star - 1)
            _stake *= 0.5
            _ur_tag = "联赛小球反向标记(%s实证: 小球为反向, 勿追小球)" % lg
            if _ur_tag not in risk_tags:
                risk_tags.append(_ur_tag)
            note.append("规则4: %s 小球反向标记(实证命中<30%%, 降星仓位减半)" % lg)
        # 规则⑧(2026-08-24): 高估区让球方向权重(受让+号加星加仓, 让球-号降仓; 账本实证受让72-78% vs 让球22-28%)
        if _overest_tag and best["name"].startswith(("让球主", "让球客")):
            try:
                _hb8 = float(best["name"].split("(")[1].split(")")[0])
            except Exception:
                _hb8 = 0.0
            if 0.0 < _hb8 <= OVEREST_RECEIVE_HDP_MAX:
                star = min(3, star + OVEREST_RECEIVE_STAR_BOOST)
                _stake *= OVEREST_RECEIVE_STAKE_MULT
                _oe_tag = "高估区受让+号加权重(实证赢盘72-78%%)"
            elif _hb8 < 0:
                star = max(1, star - 1)
                _stake *= OVEREST_GIVE_STAKE_MULT
                _oe_tag = "高估区让球-号降权重(实证赢盘22-28%%)"
            else:
                _oe_tag = None
            if _oe_tag and _oe_tag not in risk_tags:
                risk_tags.append(_oe_tag)
        # 规则13(2026-08-27 西甲3043场实证 → 同日泛化五大19763场): ①热主区受让+号加星加仓(主胜仅40.8-48.6%, 反向受让);
        #   ②高赔主场(>=high_home_away_lo)受让+号加星加仓(五联赛主胜>=2.50后客胜>主胜, 受让+1走水保底)
        # 2026-08-27 改为仅配置生效(五大已配2.80), 去掉全局2.80默认: 证据仅来自五大19763场切片,
        #   默认套用到J1/荷甲/土超等无实证联赛会虚高星级(实盘扫描曾误打22场), 见SESSION_STATE
        _laliga_high_lo = float(cal.get("high_home_away_lo") or cal.get("laliga_high_home_boost_lo") or 0.0)
        if _laliga_high_lo > 0 and best["name"].startswith("让球主"):
            try:
                _h13 = float(best["name"].split("(")[1].split(")")[0])
            except Exception:
                _h13 = 0.0
            if _h13 > 0:
                if h2h.get("home") and h2h["home"] >= _laliga_high_lo:
                    star = min(3, star + 1)
                    _stake *= 1.3
                    _tg13b = "%s高赔主场(>%.1f)受让+号加权重(五大19763场切片: 客胜>主胜)" % (lg, _laliga_high_lo)
                    if _tg13b not in risk_tags:
                        risk_tags.append(_tg13b)
                elif _laliga_hot:
                    star = min(3, star + 1)
                    _stake *= 1.3
                    _tg13 = "%s热主区受让+号加权重(主胜仅40.8-48.6%%, 反向受让)" % lg
                    if _tg13 not in risk_tags:
                        risk_tags.append(_tg13)
        best["star"] = star
        best["ev_tier"] = _tier
        best["stake_factor"] = _stake * (0.5 if n_risk >= 1 else 1.0) * (0.5 if n_risk >= 3 else 1.0)
        # 规则1(测试期): 负ROI联赛仅标注观察, 不禁出(300场walk-forward后再定禁入名单)
        if star >= 2 and lg in HIGH_TIER_BAN_LEAGUES:
            _ob_tag = "联赛%s历史负ROI(观察期, 300场后定禁入)" % lg
            if _ob_tag not in risk_tags:
                risk_tags.append(_ob_tag)
        elif best and best["name"].startswith("让球客") and 0.08 <= best["ev"] < 0.20:
            # 规则3: 让球客标准档降星(历史6注-53.6%)
            star = max(1, star - 1)
            best["star"] = star
            if "让球客标准档降星" not in risk_tags:
                risk_tags.append("让球客标准档降星")
    else:
        _tier, _stake, star = ("否决" if veto_reason else "垃圾"), 0.0, 0

    # ---- 积分榜接入 (2026-08-26 M-20260826-01): 位置区间标签 + 星级微调 (不改EV原值) ----
    _sh = _sa = None
    try:
        _sh_r = _standings_find(m.get("home"))
        _sa_r = _standings_find(m.get("away"))
        def _std_brief(s):
            if not s:
                return None
            return {"league": s["league"], "pos": s["pos"], "total": s["total"],
                    "pts": s["pts"], "played": s["played"], "form": s["form"],
                    "zone": _standings_zone(s["pos"], s["total"])}
        _sh = _std_brief(_sh_r)
        _sa = _std_brief(_sa_r)
    except Exception:
        pass
    if _sh or _sa:
        for _side, _s in (("主队", _sh), ("客队", _sa)):
            if _s and _s["zone"]:
                _t = "%s%s(第%d/%d, 积%d, 近%s)" % (_side, _s["zone"], _s["pos"], _s["total"], _s["pts"], _s["form"] or "-")
                if _t not in risk_tags:
                    risk_tags.append(_t)
        if star >= 1 and best:
            _hz = _sh and _sh["zone"]; _az = _sa and _sa["zone"]
            if _hz == "保级" and _az != "保级":
                star = min(3, star + 1)
                best["star"] = star
                if "保级区主场抢分(+1星)" not in risk_tags:
                    risk_tags.append("保级区主场抢分(+1星)")
                note.append("积分榜: 主队保级区(第%d/%d)主场抢分, 星级+1, 防守/小球倾向" % (_sh["pos"], _sh["total"]))
            if _hz == "中游" and _az == "中游" and _sh["played"] >= 8 and _sa["played"] >= 8:
                star = max(1, star - 1)
                best["star"] = star
                if "中游无欲无求(-1星)" not in risk_tags:
                    risk_tags.append("中游无欲无求(-1星)")
                note.append("积分榜: 双方中游无欲无求(低战意), 星级-1, 攻防向均值收缩提示")
            if _hz == "争冠/升级" or _az == "争冠/升级":
                note.append("积分榜: %s有争冠/升级诉求, 攻击倾向放大提示(不改EV)" % ("主队" if _hz == "争冠/升级" else "客队"))
        for _side, _s in (("主队", _sh), ("客队", _sa)):
            if _s:
                note.append("积分榜%s: %s第%d/%d 积%d分 近%d场 form=%s" % (
                    _side, _s["league"], _s["pos"], _s["total"], _s["pts"], _s["played"], _s["form"] or "-"))
    _standings_out = {"home": _sh, "away": _sa}

    return {"lambda": {"home": round(lam_h, 2), "away": round(lam_a, 2), "sum": lam_sum},
            "wdl": {"home": round(cal_probs[0] * 100, 1), "draw": round(cal_probs[1] * 100, 1),
                    "away": round(cal_probs[2] * 100, 1)},
            "market_fair": {"home": round(fair[0] * 100, 1) if fair else None,
                            "draw": round(fair[1] * 100, 1) if fair else None,
                            "away": round(fair[2] * 100, 1) if fair else None},
            "data_src": {"home": h_src, "away": a_src},
            "snap_age_h": snap_age_h,
            "bets": bets, "best_bet": best, "direction": direction, "dir_consistency": calc_dir_consistency(bets),
            "star": star, "ev_tier": _tier, "risk_tags": risk_tags, "warn_codes": warn_codes, "draw_warn": draw_warn,
            "upset": {"hot": hot_team, "level": upset["level"], "count": upset["triggered_count"],
                      "signals": upset["hot_items"] + upset["cold_items"] + upset["line_items"]
                      + upset["fair_items"] + upset["feature_items"]},
            "notes": note,
            "standings": _standings_out}

if __name__ == "__main__":
    team_stats, lavg, index = load_team_stats()
    events, future_skipped = parse_snapshots()
    BJT = timezone(timedelta(hours=8))

    _snap_path = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    _stale = snapshot_staleness(_snap_path, max_age_hours=SNAPSHOT_STALE_HOURS)
    if _stale["missing"]:
        print("❌ 盘口快照文件缺失: %s" % _snap_path)
    elif _stale["stale"]:
        print("⚠️ 盘口快照已过期: 最新 %s (距今 %.1f 小时 > 阈值 %s), 按旧盘口计算, 信号仅参考。" % (
            _stale["max_snap_iso"], _stale["age_hours"], SNAPSHOT_STALE_HOURS))
    else:
        print("✔ 盘口快照新鲜: 最新 %s (距今 %.1f 小时), 阈值 %s 小时。" % (
            _stale["max_snap_iso"], _stale["age_hours"], SNAPSHOT_STALE_HOURS))
    if future_skipped:
        print("⚠️ 剔除未来时间戳脏快照 %d 行(时钟异常/脏数据)。" % future_skipped)
    if _stale["future_rows"]:
        print("⚠️ 快照文件另有 %d 行未来时间戳(未计入新鲜度)。" % _stale["future_rows"])
    try:
        set_live_avg_leagues({m["league"] for m in events})
    except Exception:
        pass
    info_map = _load_match_info_map()
    _coach_cache = cq.load_cache()
    results = []
    try:
        _merged_n = bsd_odds_merge(events)
        if _merged_n:
            print("✔ BSD consensus 免费盘源覆盖 %d 场 (1X2/大小球), the-odds-api 降为临场专用。" % _merged_n)
    except Exception:
        pass
    for m in events:
        _info = info_map.get((m["league"], m["home"], m["away"]))
        _cm = cq.match_mods(_coach_cache, _info, m["league"]) if (_info and _coach_cache) else {}
        m["coach_mods"] = _cm
        if _info and not _cm and _info.get("bsd_coaches"):
            m["coach_missing"] = True
        r = analyze_match(m, team_stats, lavg, index)
        if _info:
            r["info"] = _info
            r["coach"] = _cm
            r["bsd"] = _bsd_cross_check(r, _info)
            r["formation"] = _formation_check(r, _info)
            r["injury_pos"] = _injury_pos_check(r, _info)
        m["result"] = r
        results.append(m)
        bj = m["ct"].astimezone(BJT)
        bb = r["best_bet"]
        bb_s = ("%s %.0f%% @%.2f EV%+.1f%% ★%d[%s]" % (bb["name"], bb["prob"] * 100, bb["odds"],
                bb["ev"] * 100, bb.get("star", 0), bb.get("ev_tier", "?"))) if bb else "-无正EV-"
        di = r.get("direction")
        if di:
            mk_s = ("市场%.0f%%" % (di["market_fair"] * 100)) if di.get("market_fair") is not None else "市场-"
            dir_s = "%s %.0f%%@%.2f(%s)" % (di["name"], di["prob"] * 100, di["odds"], mk_s)
            if di.get("vetoed"):
                dir_s += " ⛔否决"
            if di.get("wdl_name"):
                wmk = ("市场%.0f%%" % (di["wdl_market_fair"] * 100)) if di.get("wdl_market_fair") is not None else "市场-"
                dir_s += " | %s %.0f%%(%s)" % (di["wdl_name"], di["wdl_prob"] * 100, wmk)
            if di.get("draw_warn"):
                dir_s += " ⚠平局预警(市场%.0f%%)" % di["draw_warn"]["market_draw_prob"]
        else:
            dir_s = "-无盘口-"
        risk_s = (" 风险:%s" % ",".join(r["risk_tags"])) if r["risk_tags"] else ""
        info_s = ""
        if r.get("info"):
            inf = r["info"]
            def _brief(side):
                it = inf.get(side + "_info")
                es = inf.get(side + "_espn")
                if not it or not es:
                    return "无数据"
                f5 = it.get("form5") or []
                form = "".join(x.split()[1] for x in f5) if f5 else "无近5"
                rk = ("R%d" % it["rank"]) if it.get("rank") else "R-"
                return "%s近5:%s" % (rk, form)
            hb, ab = _brief("home"), _brief("away")
            h2 = inf.get("h2h") or []
            h2s = ("; ".join(h2[-2:])) if h2 else "无"
            info_s = " 情报[主:%s 客:%s 交锋:%s]" % (hb, ab, h2s)
            inj = inf.get("injuries")
            if inj:
                def _pos_brief(side):
                    _rs = inj.get(side) or []
                    if not _rs:
                        return "0"
                    _c = collections.Counter((x.get("position") or "?").upper() for x in _rs)
                    return "%d(%s)" % (len(_rs), "/".join("%s%d" % (k, v) for k, v in sorted(_c.items())))
                info_s += " 伤停[主%s客%s]" % (_pos_brief("home"), _pos_brief("away"))
        formation_s = ""
        _fm = r.get("formation") or {}
        if _fm.get("home") or _fm.get("away"):
            formation_s = " 阵型[主%s/客%s%s]" % (_fm.get("home") or "-", _fm.get("away") or "-", "/当场" if _fm.get("src")=="cur" else "/偏好")
        bsd_s = ""
        _bsd = r.get("bsd") or {}
        if _bsd.get("lam_dev"):
            _d = _bsd["lam_dev"]
            bsd_s = " BSDλΔmax%.2f" % max(_d["home"], _d["away"])
        if _bsd.get("conf") is not None:
            _ag = {True: "同向", False: "反向", None: "-"}.get(_bsd.get("agree"))
            _sp = {True: "✓支持", False: "✗降星", None: ""}.get(_bsd.get("support"))
            bsd_s += " BSDconf%.0f%%%s%s" % (_bsd["conf"] * 100, _ag, _sp)
        if _bsd.get("ev") is not None:
            bsd_s += " EVb%+.1f%%" % (_bsd["ev"] * 100)
        print("%s %-4s %s vs %s | λ%.2f/%.2f | 源[%s/%s] | 方向[%s] | BEST[%s] | 冷门:%s(%d)%s%s%s%s" % (
            bj.strftime("%m-%d %H:%M"), m["league"], m["home"], m["away"],
            r["lambda"]["home"], r["lambda"]["away"], r["data_src"]["home"], r["data_src"]["away"],
            dir_s, bb_s, r["upset"]["level"], r["upset"]["count"], risk_s, info_s, formation_s, bsd_s))

    src_cnt = collections.Counter()
    tier_cnt = collections.Counter()
    for m in results:
        src_cnt[m["result"]["data_src"]["home"]] += 1
        src_cnt[m["result"]["data_src"]["away"]] += 1
        tier_cnt[m["result"]["ev_tier"]] += 1
    print("\n数据覆盖(主客合计%d个队位): %s" % (len(results) * 2, dict(src_cnt)))
    n_bet = sum(1 for m in results if m["result"]["best_bet"])
    print("可出best_bet场次: %d / %d (门槛: EV>=%.0f%% %s, 赔率>=%s)" % (
        n_bet, len(results), EV_TIER_BATCH * 100, "批量无情报" if not HAS_INTEL else "完整情报",
        ODDS_FLOOR_SEC if any(m["league"] in SECONDARY_LEAGUES for m in results) else ODDS_FLOOR_MAIN))
    print("EV分级分布: %s" % dict(tier_cnt))
    n_pos = sum(1 for m in results if any(b["ev"] > 0 for b in m["result"]["bets"]))
    print("正EV场次: %d / %d" % (n_pos, len(results)))
    _old_snaps = [m for m in results
                  if m["result"].get("snap_age_h") is not None and m["result"]["snap_age_h"] > SNAPSHOT_STALE_HOURS]
    if _old_snaps:
        print("⚠️ %d 场盘口过期(距开赛>%.0fh), 已否决出单。" % (len(_old_snaps), SNAPSHOT_STALE_HOURS))
    n_veto = sum(1 for m in results if any("否决" in t for t in m["result"].get("risk_tags", [])))
    if n_veto:
        print("⚠️ %d 场触发硬否决(过期/隔日盘口或模型与市场分歧>%.0fpp)。" % (n_veto, MAX_MKT_DIVERGENCE * 100))

    out_path = os.path.join(ROOT, "analysis_records", datetime.now().strftime("%Y%m%d_scan_upcoming.json"))
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump({"timestamp": "2026-08-15", "type": "全量扫描(即将开赛39场)",
                   "note": "数据: snapshots.csv(8/13-8/14快照, 多机构取最低抽水)+多源攻防(当季/上季/旧季衰减)+市场隐含兜底; 无伤停/情报文本, 纯数据扫描; EV为各市场独立去水后公平EV; best_bet口径=批量EV>=5%(完整情报>=8%)且主流赔率>=1.60/次级>=1.40选胜率最高腿, 且双方均需独立攻防数据; 升班马/跨联赛攻防收缩30%%; 队名相似度<0.9降级标注; 风控标签只降星级不改EV; 硬否决: 过期/隔日盘口与模型vs市场分歧>20pp直接不出单(复盘中超/J1统一规则); BSD市场基准交叉: λ偏差>0.5球标模型独立观点降星, 方向腿BSD共识去水双口径EV, BSD无价值标记+我方EV<5%无单; BSD置信度交叉验证(1a): 同向conf>=60%保留出单标注共识支持, 反向或同向conf<45%降星加分歧/低置信标签(不改EV)",
                   "stale": {"max_snap_iso": _stale["max_snap_iso"], "age_hours": _stale["age_hours"],
                             "stale": _stale["stale"], "missing": _stale["missing"],
                             "future_rows": _stale["future_rows"],
                             "threshold_hours": SNAPSHOT_STALE_HOURS},
                   "matches": [{k: (m[k].isoformat() if k == "ct" else m[k]) for k in ("id", "league", "home", "away", "ct", "snap", "result")} for m in results]},
                  f, ensure_ascii=False, indent=1)
    print("\nsaved:", out_path)
