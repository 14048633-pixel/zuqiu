"""
足球预测系统 - 自动化SOP流程 + 记录保存
每次分析自动执行完整流程并保存记录
"""
import os
import json
import requests
import time
import math
from datetime import datetime
from dotenv import load_dotenv
from collect_strategy_data import DataCollector, STRATEGY_CONDITIONS
import sys
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
from over_under_ml_advanced import AdvancedOverUnderModel
from betting_strategy import OverUnderModel as OUModel
from rule_engine_v2 import FootballRuleEngineV2
from handicap_rules import HandicapRuleEngine
import numpy as np
from bet_validator import BetValidator

sys.path.insert(0, 'src/features')
from feature_extractor import MatchFeatureExtractor
from football_agent import FootballAnalysisAgent
from upset_engine import UpsetEngine
from upset_engine_v2 import UpsetEngineV2


def get_league_avg_goals(league_name):
    """获取联赛场均进球 (优先级: calibration.json 基线 > OUModel 联赛统计 > 2.8 默认).
    修复缺口: 西甲等五大联赛校准值(月度校准产物)未接入, 直接回落默认2.8导致λ偏差.
    """
    # 1. 月度校准基线优先 (calibration.json meta.baseline.league_avg, 形式约束: 未去水实战统计)
    try:
        cal_path = os.path.join("strategy_data", "calibration.json")
        if os.path.exists(cal_path):
            with open(cal_path, encoding="utf-8") as f:
                cal = json.load(f) or {}
            for lname, rec in cal.items():
                if lname in league_name or league_name in lname:
                    ba = (rec.get("meta") or {}).get("baseline") or {}
                    if ba.get("league_avg"):
                        return float(ba["league_avg"])
                    break
    except Exception:
        pass
    # 2. OUModel 联赛统计表
    try:
        ou = OUModel()
        stats = ou.league_stats.get(league_name)
        return stats.avg_goals if stats else 2.8
    except Exception:
        return 2.8

def get_league_odds_zones_path(league_name):
    """联赛名 → strategy_data/*_odds_zones.json 路径 (无匹配返回 None)."""
    _zones_map = [
        ("k2", ["韩国K2联赛", "K2联赛", "韩K2", "K联赛2", "K League 2", "K2"]),
        ("j1", ["J1", "J1联赛", "日本J1", "日职", "J联赛"]),
        ("cl2", ["中乙", "中乙联赛", "中国乙级"]),
        ("csl", ["中超", "中国足球协会超级联赛", "CSL"]),
        ("laliga", ["西甲", "西甲联赛", "西班牙甲级联赛", "La Liga", "laliga"]),
    ]
    for key, keys in _zones_map:
        if any(k in league_name for k in keys):
            path = os.path.join("strategy_data", "%s_odds_zones.json" % key)
            if os.path.exists(path):
                return path
    return None

def get_league_correct_coef(league_name):
    """联赛可配置攻防修正系数 (SOP Step8 v3): 读 odds_zones.json correct_coef, 缺省用默认值.
    次级联赛与顶级联赛分开调参, 避免一套系数系统性偏差; 修改后跑回归验证.
    """
    defaults = {
        "amateur_vs_pro_strong": 1.5,
        "amateur_vs_pro_weak": 0.7,
        "striker_miss": 0.8,
        "key_striker_out": 0.85,
        "weak_defense": 1.2,
        "form_good": 1.1,
        "away_weak": 0.85,
        "first_leg_conservative": 0.9,
        # 校准系数默认中性 (1.0=不修正); 经 calibrate_coeffs.py 拟合后写入 calibration.json
        "home_coef": 1.0,
        "away_coef": 1.0,
        "fatigue_coef": 1.0,
    }
    try:
        path = get_league_odds_zones_path(league_name)
        if path:
            with open(path, encoding="utf-8") as f:
                cc = json.load(f).get("correct_coef", {}) or {}
            for k, v in cc.items():
                if v is not None:
                    defaults[k] = v
    except Exception:
        pass
    # 合并离线校准结果 (calibration.json, 分联赛最优系数; 仅覆盖本联赛匹配项)
    try:
        cal_path = os.path.join("strategy_data", "calibration.json")
        if os.path.exists(cal_path):
            with open(cal_path, encoding="utf-8") as f:
                cal = json.load(f) or {}
            for lname, rec in cal.items():
                if lname in league_name or league_name in lname:
                    for k, v in (rec.get("coefs") or {}).items():
                        if v is not None:
                            defaults[k] = v
                    break
    except Exception:
        pass
    return defaults


def get_league_prob_calib(league_name):
    """概率后校准参数 (SOP Step8 v4): 读 calibration.json prob_calib.

    仅在校准启用 (enabled=True) 且联赛匹配时返回 {rho, shrink_power, bin_table}, 否则 None.
    """
    try:
        cal_path = os.path.join("strategy_data", "calibration.json")
        if not os.path.exists(cal_path):
            return None
        with open(cal_path, encoding="utf-8") as f:
            cal = json.load(f) or {}
        for lname, rec in cal.items():
            if lname in league_name or league_name in lname:
                pc = rec.get("prob_calib") or {}
                if pc.get("enabled") and pc.get("rho") is not None:
                    return {
                        "rho": float(pc.get("rho", 0.0)),
                        "shrink_power": float(pc.get("shrink_power", 1.0)),
                        "bin_table": pc.get("bin_table"),
                    }
                return None
    except Exception:
        pass
    return None


def finalize_poisson_probs(poisson_result, lam_h, lam_a, league_name, max_goals=6):
    """概率后校准 + 重算比分/大小球 (SOP Step8 v4).

    Dixon-Coles ρ 修正比分矩阵 → 1X2 概率 → ShrinkPower → 分箱校准;
    就地更新 poisson_result 的 prob_home/draw/away/top5_scores/over_*。
    """
    try:
        pc = get_league_prob_calib(league_name)
        rho = pc["rho"] if pc else 0.0
        sys.path.insert(0, 'src/models')
        from prob_calibration import dc_score_grid, apply_prob_calibration
        grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=max_goals)
        probs_raw = [
            sum(grid[i][j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i > j),
            sum(grid[i][j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i == j),
            sum(grid[i][j] for i in range(max_goals + 1) for j in range(max_goals + 1) if i < j),
        ]
        probs_cal = probs_raw
        if pc:
            probs_cal = apply_prob_calibration(
                probs_raw, shrink=pc["shrink_power"], bin_table=pc["bin_table"])
            poisson_result["prob_calib_note"] = (
                "ρ=%s Shrink=%s 分箱校准 已启用" % (pc["rho"], pc["shrink_power"]))
        poisson_result["prob_home"] = round(probs_cal[0], 4)
        poisson_result["prob_draw"] = round(probs_cal[1], 4)
        poisson_result["prob_away"] = round(probs_cal[2], 4)
        poisson_result["probs_raw"] = [round(x, 4) for x in probs_raw]
        poisson_result["rho"] = rho
        scores = []
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                scores.append({"score": "%d-%d" % (i, j), "prob": round(grid[i][j] * 100, 1)})
        scores.sort(key=lambda x: x["prob"], reverse=True)
        poisson_result["top5_scores"] = scores[:5]
        def _over(line):
            return round(sum(grid[i][j] for i in range(max_goals + 1) for j in range(max_goals + 1)
                             if i + j > line) * 100, 1)
        poisson_result["over_15"] = _over(1.5)
        poisson_result["over_25"] = _over(2.5)
        poisson_result["over_35"] = _over(3.5)
        poisson_result["btts"] = round(sum(grid[i][j] for i in range(1, max_goals + 1)
                                           for j in range(1, max_goals + 1)) * 100, 1)
    except Exception:
        pass
    return poisson_result

load_dotenv()

# 自定义JSON编码器，处理numpy类型
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
KIMI_API_KEY = os.getenv('KIMI_API_KEY')
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')
FOOTBALL_API_HOST = "https://v3.football.api-sports.io"
ARK_API_KEY = os.getenv('DOUBAO_API_KEY')
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_ENDPOINT_ID = os.getenv('DOUBAO_ENDPOINT_ID')
GLM_ENDPOINT_ID = os.getenv('GLM_ENDPOINT_ID')

RECORDS_DIR = "analysis_records"
os.makedirs(RECORDS_DIR, exist_ok=True)

# 中文队名 → 英文队名 (代码对账/API查询用英文)
TEAM_NAME_EN = {
    "欧雷": "SfB Oure FA",
    "弗雷德里西亚": "FC Fredericia",
    "维比": "Viby IF",
    "ASA阿晓斯": "ASA Aarhus",
    "根图夫特宠格德": "Gentofte-Vangede IF",
    "厄华特": "Hillerød",
    "FC南海岸": "FC Sydkysten",
    "伊绍伊IF": "Ishøj IF",
    "灵斯泰德": "Ringsted IF",
    "费林": "Fremad Vallensbæk",
    "布隆索伊": "Brønshøj BK",
    "科治": "HB Køge",
    "霍尔斯特布罗": "Holstebro BK",
    "奥尔堡": "Aalborg BK",
    "科尔丁BK": "Kolding BK",
    "奈斯比": "Næstved",
}


def to_en_name(name):
    """中文队名转英文, 已是英文则原样返回"""
    if not name:
        return name
    if name in TEAM_NAME_EN:
        return TEAM_NAME_EN[name]
    return name


def check_upset_risk_conflict(lam_h, lam_a, risk_signal, diff_threshold=0.6, min_signal=0.07):
    """基本面 λ 差 vs 冷门 RiskSignal 反向冲突检测 (Step29.5 P2 风控降级).

    主队显著占优(λ差>阈值)却看衰主队 / 客队显著占优却看衰客队 → 标记冲突,
    上层 Step31 对强冲突自动全腿降 1 星. 返回 dict: conflict/level/direction/msg.
    """
    try:
        lh, la, rs = float(lam_h), float(lam_a), float(risk_signal)
    except (TypeError, ValueError):
        return {"conflict": False, "level": "none", "direction": None, "msg": None}
    base_diff = lh - la
    if base_diff > diff_threshold and rs < -min_signal:
        return {"conflict": True, "level": "strong", "direction": "home",
                "msg": "基本面λ差%.2f与冷门信号%+.2f严重反向(看衰主队) → 风控降级" % (base_diff, rs)}
    if base_diff < -diff_threshold and rs > min_signal:
        return {"conflict": True, "level": "strong", "direction": "away",
                "msg": "基本面λ差%.2f与冷门信号%+.2f严重反向(看衰客队) → 风控降级" % (base_diff, rs)}
    return {"conflict": False, "level": "none", "direction": "home" if base_diff >= 0 else "away", "msg": None}


def parse_handicap(hdp_str):
    """
    解析让球盘口, 返回主队让球值 (负=主队让球, 正=主队受让)
    处理: "+2.5", "-0/0.5", "+0/0.5", "-1", "+0.5/1" 等
    """
    hdp_str = str(hdp_str).strip()
    if not hdp_str:
        return 0.0
    # 中文"平手"=0
    if '平手' in hdp_str:
        return 0.0
    if '/' in hdp_str:
        parts = hdp_str.split('/')
        p1 = parts[0].split('@')[0].strip()
        p2 = parts[1].split('@')[0].strip()
        sign1 = -1 if p1.startswith('-') else 1
        v1 = float(p1.replace('+', '').replace('-', ''))
        v2 = float(p2.replace('+', '').replace('-', ''))
        return sign1 * (v1 + v2) / 2
    else:
        val_str = hdp_str.split('@')[0].strip()
        return float(val_str)


def poisson_pmf(k, lam):
    """泊松分布概率质量函数"""
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def predict_score_poisson(odds_home, odds_draw, odds_away, max_goals=6, h2h_avg_goals=None):
    """
    基于泊松分布预测比分概率矩阵
    通过赔率反推lambda，再用泊松分布计算每个比分概率
    
    参数:
        h2h_avg_goals: 历史交锋场均进球数，用于修正lambda
    """
    # 赔率转隐含概率
    prob_home = 1 / odds_home
    prob_draw = 1 / odds_draw
    prob_away = 1 / odds_away
    total = prob_home + prob_draw + prob_away
    prob_home /= total
    prob_draw /= total
    prob_away /= total

    # 用牛顿法解lambda (基于BivariatePoisson的简化)
    # 目标: P(主胜)=prob_home, P(平)=prob_draw, P(客胜)=prob_away
    lam_home = 1.0
    lam_away = 1.0

    for _ in range(50):
        # 计算当前lambda下的概率
        p_home = 0
        p_draw = 0
        p_away = 0
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                p = poisson_pmf(i, lam_home) * poisson_pmf(j, lam_away)
                if i > j:
                    p_home += p
                elif i == j:
                    p_draw += p
                else:
                    p_away += p

        # 计算误差
        err_h = p_home - prob_home
        err_a = p_away - prob_away

        # 梯度下降更新
        lam_home -= 0.05 * err_h
        lam_away -= 0.05 * err_a

        # 防止lambda为负
        lam_home = max(0.3, lam_home)
        lam_away = max(0.3, lam_away)

    # 如果有历史交锋数据，修正lambda
    if h2h_avg_goals and h2h_avg_goals > 0:
        odds_total = lam_home + lam_away
        # 如果历史交锋进球数高于赔率预期，向上修正
        if h2h_avg_goals > odds_total * 1.1:  # 历史高于赔率预期10%以上
            correction = h2h_avg_goals / odds_total
            lam_home *= correction
            lam_away *= correction

    # 生成比分概率矩阵
    score_matrix = []
    for i in range(max_goals + 1):
        row = []
        for j in range(max_goals + 1):
            p = poisson_pmf(i, lam_home) * poisson_pmf(j, lam_away)
            row.append(round(p * 100, 1))
        score_matrix.append(row)

    # 获取TOP5比分
    scores = []
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            scores.append({
                "score": f"{i}-{j}",
                "prob": score_matrix[i][j]
            })
    scores.sort(key=lambda x: x["prob"], reverse=True)
    top5 = scores[:5]

    # 大小球概率 (边界修正: 大2.5 = 总进球 > 2.5 即 ≥3)
    over_25 = sum(score_matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if i+j > 2.5)
    over_15 = sum(score_matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if i+j > 1.5)
    over_35 = sum(score_matrix[i][j] for i in range(max_goals+1) for j in range(max_goals+1) if i+j > 3.5)

    return {
        "lambda_home": round(lam_home, 2),
        "lambda_away": round(lam_away, 2),
        "top5_scores": top5,
        "over_15": round(over_15, 1),
        "over_25": round(over_25, 1),
        "over_35": round(over_35, 1),
        "btts": round(sum(score_matrix[i][j] for i in range(1, max_goals+1) for j in range(1, max_goals+1)), 1),
    }

# 基础必填字段
BASE_KEYS = ['home', 'away', 'league', 'odds_home', 'odds_draw', 'odds_away',
             'hdp_home', 'hdp_away', 'ou_over', 'ou_under']

# 比赛状态: pre_match(开赛前), in_play(比赛中), finished(已结束)
STATUS_OPTIONS = ['pre_match', 'in_play', 'finished']


class APIFootball:
    """API-Football实时数据查询 (免费版100次/天)"""
    
    def __init__(self):
        self.headers = {'x-apisports-key': FOOTBALL_API_KEY}
        self.base_url = FOOTBALL_API_HOST
        self.league_cache = {}  # 缓存联赛ID
    
    def _get(self, endpoint, params=None):
        """发送GET请求"""
        try:
            url = f"{self.base_url}/{endpoint}"
            resp = requests.get(url, headers=self.headers, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            pass
        return None
    
    def search_team(self, team_name):
        """搜索球队"""
        data = self._get('teams', {'search': team_name})
        if data and data['results'] > 0:
            return data['response'][0]['team']
        return None
    
    def search_league(self, league_name):
        """搜索联赛"""
        data = self._get('leagues', {'search': league_name})
        if data and data['results'] > 0:
            return data['response'][0]['league']
        return None
    
    def get_fixtures(self, league_id, date=None, team_id=None):
        """获取比赛列表"""
        params = {'league': league_id, 'season': 2025}
        if date:
            params['date'] = date
        if team_id:
            params['team'] = team_id
        data = self._get('fixtures', params)
        if data:
            return data['response']
        return []
    
    def get_odds(self, fixture_id):
        """获取赔率"""
        data = self._get('odds', {'fixture': fixture_id})
        if data and data['results'] > 0:
            return data['response'][0]
        return None
    
    def get_standings(self, league_id, season=2025):
        """获取积分榜"""
        data = self._get('standings', {'league': league_id, 'season': season})
        if data and data['results'] > 0:
            return data['response'][0]['league']['standings'][0]
        return []
    
    def get_team_form(self, team_id, last=5):
        """获取球队近期战绩"""
        data = self._get('fixtures', {'team': team_id, 'last': last})
        if data:
            return data['response']
        return []
    
    def get_h2h(self, team1_id, team2_id):
        """获取历史交锋"""
        data = self._get('fixtures/headtohead', {'h2h': f'{team1_id}-{team2_id}'})
        if data:
            return data['response']
        return []
    
    def query_match(self, home_name, away_name):
        """查询比赛完整信息"""
        result = {
            'home_team': None,
            'away_team': None,
            'league': None,
            'fixtures': [],
            'h2h': [],
            'available': False
        }
        
        # 搜索球队
        home = self.search_team(home_name)
        away = self.search_team(away_name)
        
        if home:
            result['home_team'] = home
        if away:
            result['away_team'] = away
        
        if not home or not away:
            return result
        
        # 获取历史交锋
        h2h = self.get_h2h(home['id'], away['id'])
        result['h2h'] = h2h[:5]  # 最近5场
        
        result['available'] = True
        return result


class FootballPredictor:
    def __init__(self):
        self.analysis_record = {}
        self.context = ""
        self.match_status = ""
        self.data_collector = DataCollector()
        self.data_quality = "high"  # 数据质量: high/low
        self.confidence_adjustment = 0  # 置信度调整
        self.api_football = APIFootball()  # API-Football实例
        self.ml_model = AdvancedOverUnderModel()  # ML大小球模型
        self._init_ml_model()  # 初始化ML模型
        self._v2_bridge = None  # prediction_v2 新引擎桥接器
        self._v2_result = None  # Step8.5 新引擎结果
        # 规则引擎
        try:
            self.rule_engine = FootballRuleEngineV2()
            self.handicap_engine = HandicapRuleEngine()
            print("  [规则引擎] V2规则引擎 + 让球引擎已加载")
        except Exception as e:
            self.rule_engine = None
            self.handicap_engine = None
            print(f"  [规则引擎] 加载失败: {e}")
        # 特征提取器 (从情报提取关键指标)
        try:
            self.feature_extractor = MatchFeatureExtractor()
            print("  [特征提取器] 已加载")
        except Exception as e:
            self.feature_extractor = None
            print(f"  [特征提取器] 加载失败: {e}")
        # 足球分析Agent (LLM战术分析)
        try:
            self.agent = FootballAnalysisAgent()
            print("  [足球Agent] 战术分析Agent已加载")
        except Exception as e:
            self.agent = None
            print(f"  [足球Agent] 加载失败: {e}")
        # 比赛数据提取器 (从用户原始数据提取, 强制主客区分)
        try:
            from data_extractor import MatchDataExtractor
            self.data_extractor = MatchDataExtractor()
            print("  [数据提取器] 比赛数据提取器已加载 (强制主客区分)")
        except Exception as e:
            self.data_extractor = None
            print(f"  [数据提取器] 加载失败: {e}")
        # 冷门条件计数引擎 (纯数据触发)
        try:
            self.upset_engine = UpsetEngineV2()  # v2完整框架
            print("  [冷门引擎] 冷门识别引擎v2已加载")
        except Exception as e:
            self.upset_engine = None
            print(f"  [冷门引擎] 加载失败: {e}")
        # 投注校验器 (防止选错腿: 串关必须用best_bet)
        try:
            self.bet_validator = BetValidator()
            print("  [投注校验] 投注校验器已加载 (串关强制best_bet最高胜率腿)")
        except Exception as e:
            self.bet_validator = None
            print(f"  [投注校验] 加载失败: {e}")

    def _init_ml_model(self):
        """初始化ML大小球模型"""
        try:
            data_path = "data/raw/mls_matches.csv"
            if os.path.exists(data_path):
                self.ml_model.train(data_path, model_type="xgboost")
                print(f"  [ML模型] XGBoost模型已加载 (MAE={self.ml_model.metrics.get('mae', 0):.3f})")
            else:
                print(f"  [ML模型] 训练数据不存在: {data_path}")
        except Exception as e:
            print(f"  [ML模型] 初始化失败: {e}")

    def set_real_data(self, home_form, away_form, h2h, injuries, motivation, analysis):
        """设置真实数据（用户提供的）"""
        self.analysis_record['real_data'] = {
            'home_form': home_form,
            'away_form': away_form,
            'h2h': h2h,
            'injuries': injuries,
            'motivation': motivation,
            'analysis': analysis
        }

    def _build_rule_data(self, data):
        """构建规则引擎输入数据"""
        try:
            odds_home = float(data['odds_home'])
            odds_draw = float(data['odds_draw'])
            odds_away = float(data['odds_away'])
        except Exception:
            odds_home, odds_draw, odds_away = 0, 0, 0

        # 让球解析
        hdp_value = 0
        try:
            hdp_str = data.get('hdp_home', '')
            if '/' in hdp_str:
                parts = hdp_str.split('/')
                n1 = float(parts[0].split('@')[0].strip().replace('+', ''))
                n2 = float(parts[1].split('@')[0].strip().replace('+', ''))
                hdp_value = (n1 + n2) / 2
            else:
                hdp_value = float(hdp_str.split('@')[0].strip().replace('+', ''))
        except Exception:
            pass

        # 从用户数据提取场均进失球
        home_gf = away_gf = 1.5
        try:
            import re
            s = data.get('user_form', '')
            # 提取 场均进X失Y
            m = re.findall(r'场均进(\d+\.?\d*)失(\d+\.?\d*)', s)
            if len(m) >= 2:
                home_gf = float(m[0][0])
                home_ga = float(m[0][1])
                away_gf = float(m[1][0])
                away_ga = float(m[1][1])
        except Exception:
            pass

        rule_data = {
            'home_team': data['home'],
            'away_team': data['away'],
            'odds_home': odds_home,
            'odds_draw': odds_draw,
            'odds_away': odds_away,
            'handicap_line': hdp_value,
            'odds_hdp_win': odds_home,
            'odds_hdp_draw': odds_draw,
            'odds_hdp_lose': odds_away,
            'home_gf': home_gf,
            'away_gf': away_gf,
            'home_ga': home_ga if 'home_ga' in dir() else 1.5,
            'away_ga': away_ga if 'away_ga' in dir() else 1.5,
            'home_elo': 1500,
            'away_elo': 1500,
            'pinnacle_home': odds_home,
            'pinnacle_draw': odds_draw,
            'pinnacle_away': odds_away,
            'odds_home_initial': odds_home,
            'odds_draw_initial': odds_draw,
            'odds_away_initial': odds_away,
        }
        # 联网情报 -> 情报类规则字段 (R10/R98/R124/R127/R136/R143/R145/R147)
        try:
            from intel_parser import parse_web_intel
            step26 = {}
            if hasattr(self, 'analysis_record'):
                step26 = self.analysis_record.get('steps', {}).get('step2_6', {}) or {}
            intel_text = str(step26.get('result', '')) if isinstance(step26, dict) else ''
            intel_fields = parse_web_intel(intel_text, data) if intel_text else {}
            if intel_fields:
                rule_data.update(intel_fields)
                if isinstance(step26, dict):
                    step26['intel_fields'] = intel_fields
        except Exception:
            pass
        return rule_data

    def deepseek_query(self, prompt, max_retries=3, compress_context=False):
        """调用DeepSeek API (带重试和上下文压缩)"""
        # 如果需要压缩上下文，先调用压缩API
        if compress_context and len(self.context) > 1000:
            self.context = self._compress_context(self.context)

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的足球分析师，严格按照SOP流程分析比赛。输出不要使用emoji，不要使用加粗格式。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
                response.raise_for_status()
                return response.json()['choices'][0]['message']['content']
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  [重试 {attempt+1}/{max_retries}] {e}")
                    time.sleep(2)
                else:
                    raise

    def _compress_context(self, context, max_length=1000):
        """压缩上下文到指定长度"""
        if len(context) <= max_length:
            return context

        # 策略1: 保留最后一部分 (最近的信息更重要)
        compressed = "...\n" + context[-max_length:]

        # 策略2: 提取关键信息
        lines = context.split('\n')
        key_lines = []
        for line in lines:
            # 保留包含关键信息的行
            if any(kw in line for kw in ['比分', '赔率', '盘口', '让球', '推荐', '结论', '状态']):
                key_lines.append(line)

        if key_lines:
            compressed = '\n'.join(key_lines[-20:])  # 最后20行关键信息

        return compressed

    def analyze(self, match_data):
        """完整SOP分析流程"""

        # Step 0.5: 若传入 raw_text, 用数据提取器转为结构化数据并强制主客区分
        if match_data.get('raw_text') and self.data_extractor:
            raw_text = match_data.pop('raw_text')
            print("  [数据提取器] 从用户原始数据提取比赛数据...")
            extracted = self.data_extractor.extract(raw_text)
            if extracted.get('home_team'):
                match_data['home'] = extracted['home_team']
                match_data['away'] = extracted['away_team']
                print(f"  提取主客: {match_data['home']} vs {match_data['away']}")
                # 合并盘口 (仅填充缺失)
                for k in ['odds_home', 'odds_draw', 'odds_away', 'hdp_home', 'hdp_away',
                          'ou_over', 'ou_under', 'user_form', 'user_h2h',
                          'user_injuries', 'user_motivation', 'user_analysis']:
                    if k not in match_data and extracted.get(k):
                        match_data[k] = extracted[k]
                # 主客确认标记
                match_data['home_away_confirmed'] = True
            else:
                print("  ⚠️ 数据提取器未识别主客队, 使用原输入")

        # 验证基础字段
        missing = [k for k in BASE_KEYS if k not in match_data]
        if missing:
            raise ValueError(f"缺少字段: {missing}")

        # 验证比赛状态
        self.match_status = match_data.get('status', '').lower()
        if self.match_status not in STATUS_OPTIONS:
            raise ValueError(f"status必须是: {STATUS_OPTIONS}")

        # 比赛中/已结束需要额外字段
        if self.match_status in ['in_play', 'finished']:
            if 'current_score' not in match_data:
                raise ValueError("比赛中/已结束必须提供 current_score (当前比分)")
            if 'minute' not in match_data:
                raise ValueError("比赛中/已结束必须提供 minute (进行时间)")

        self.analysis_record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "match": f"{match_data['home']} vs {match_data['away']}",
            "home": match_data['home'],
            "away": match_data['away'],
            "home_en": match_data.get('home_en') or to_en_name(match_data['home']),
            "away_en": match_data.get('away_en') or to_en_name(match_data['away']),
            "league": match_data['league'],
            "match_status": self.match_status,
            "steps": {}
        }
        self.context = ""

        print("=" * 70)
        print("  足球预测分析系统 - 自动化SOP流程")
        print("=" * 70)

        # Step 0: 比赛状态确认
        self._step0_status_confirm(match_data)

        # 根据比赛状态执行不同流程
        if self.match_status == 'pre_match':
            self._pre_match_flow(match_data)
        elif self.match_status == 'in_play':
            self._in_play_flow(match_data)
        elif self.match_status == 'finished':
            self._finished_flow(match_data)

        # 检查并记录策略数据
        self._check_and_record_strategy(match_data)

        self._save_record()
        return self.analysis_record

    def _step0_status_confirm(self, data):
        """Step 0: 比赛状态确认 (必须第一个执行)"""
        print("\n" + "=" * 70)
        print("  Step 0: 比赛状态确认")
        print("=" * 70)

        status_text = {
            'pre_match': '开赛前',
            'in_play': '比赛中',
            'finished': '已结束'
        }
        print(f"  比赛状态: {status_text[self.match_status]}")
        print(f"  比赛: {data['home']} vs {data['away']}")
        print(f"  联赛: {data['league']}")

        if self.match_status in ['in_play', 'finished']:
            print(f"  当前比分: {data['current_score']}")
            print(f"  进行时间: {data['minute']}分钟")

        print(f"  主胜赔率: {data['odds_home']}")
        print(f"  平局赔率: {data['odds_draw']}")
        print(f"  客胜赔率: {data['odds_away']}")
        print(f"  让球盘口: 主{data['hdp_home']} / 客{data['hdp_away']}")
        print(f"  大小球: 大{data['ou_over']} / 小{data['ou_under']}")

        # 确认盘口数值
        print("\n  [盘口确认]")
        print(f"  主队让球: {data['hdp_home']}")
        print(f"  客队让球: {data['hdp_away']}")

        self.analysis_record['steps']['step0'] = {
            "status": self.match_status,
            "current_score": data.get('current_score', 'N/A'),
            "minute": data.get('minute', 'N/A'),
            "hdp_home": data['hdp_home'],
            "hdp_away": data['hdp_away']
        }

        # 基础上下文 (不含分析结果，避免过长)
        self.context = f"比赛状态: {status_text[self.match_status]}\n"
        self.context += f"比赛: {data['home']} vs {data['away']}\n"
        self.context += f"联赛: {data['league']}\n"
        if self.match_status in ['in_play', 'finished']:
            self.context += f"当前比分: {data['current_score']}\n"
            self.context += f"进行时间: {data['minute']}分钟\n"
        self.context += f"主胜赔率: {data['odds_home']}\n"
        self.context += f"平局赔率: {data['odds_draw']}\n"
        self.context += f"客胜赔率: {data['odds_away']}\n"
        self.context += f"让球盘口: 主{data['hdp_home']} / 客{data['hdp_away']}\n"
        self.context += f"大小球: 大{data['ou_over']} / 小{data['ou_under']}\n"

    def _pre_match_flow(self, data):
        """开赛前分析流程"""
        print("\n  [开赛前分析模式]")

        # 基础信息
        self._step1_match_info(data)
        self._step2_odds_baseline(data)

        # 数据收集 (只保留关键结论，不追加到context)
        step2_1 = self._step2_1_recent_form(data)
        step2_2 = self._step2_2_head_to_head(data)
        step2_3 = self._step2_3_injuries(data)
        step2_5 = self._step2_5_formation(data)
        step2_6 = self._step2_6_web_intel(data)

        # 在线验证DeepSeek数据
        step2_1_verified, data_quality, confidence_adj = self._step2_4_verify_online(data, step2_1, "近期状态")
        self.data_quality = data_quality
        self.confidence_adjustment = confidence_adj

        # 将关键结论压缩后加入context
        self.context += f"状态: {step2_1_verified}\n"
        self.context += f"交锋: {step2_2}\n"
        self.context += f"伤停: {step2_3}\n"
        self.context += f"阵型: {step2_5}\n"
        # 伤停/阵型无数据时用联网情报补充 (豆包 web_search, 仅赛前信息)
        if ("无数据" in str(step2_3) or "无数据" in str(step2_5)) and "无数据" not in str(step2_6):
            self.context += f"联网情报: {str(step2_6)[:300]}\n"

        # 分析决策
        self._step3_mode_switch(data)
        self._step4_odds_deviation(data)
        self._step5_handicap_analysis(data)
        self._step6_dual_verification(data)
        self._step7_risk_control(data)

        # Step 7.5: Agent风险信号前置 (供Step8修正λ)
        self._agent_risk_signals(data)

        self._step8_final_decision(data)

        # Step 8.5: 新引擎(prediction_v2)交叉验证 (回测纪律: 仅小球2.5边际>=5%为正期望)
        self._step8_5_v2_engine(data)

        # Step 29.5: 冷门识别 (欧冠/杯赛专项, 内置流程)
        self._upset_assessment(data)

        # Step 30: Agent战术分析
        self._agent_tactical_analysis(data)

        # Step 31: EV计算+打星 (流程铁律: 一步都不能跳)
        self._step31_ev_calc(data)

    def _in_play_flow(self, data):
        """比赛中分析流程"""
        print("\n  [比赛中分析模式]")

        # 基础信息
        self._step1_match_info(data)
        self._step2_odds_baseline(data)

        # 数据收集
        step2_1 = self._step2_1_recent_form(data)
        step2_2 = self._step2_2_head_to_head(data)
        step2_3 = self._step2_3_injuries(data)
        step2_5 = self._step2_5_formation_live(data)

        # 在线验证DeepSeek数据
        step2_1_verified, data_quality, confidence_adj = self._step2_4_verify_online(data, step2_1, "近期状态")
        self.data_quality = data_quality
        self.confidence_adjustment = confidence_adj

        # 将关键结论压缩后加入context
        self.context += f"状态: {step2_1_verified}\n"
        self.context += f"交锋: {step2_2}\n"
        self.context += f"伤停: {step2_3}\n"
        self.context += f"阵型: {step2_5}\n"
        # 伤停/阵型无数据时用联网情报补充 (豆包 web_search, 仅赛前信息)
        if ("无数据" in str(step2_3) or "无数据" in str(step2_5)) and "无数据" not in str(step2_6):
            self.context += f"联网情报: {str(step2_6)[:300]}\n"

        # 实时分析 (补全完整步骤)
        self._step3_live_handicap_check(data)
        self._step4_live_settlement(data)
        self._step5_mode_switch_live(data)
        self._step6_odds_deviation_live(data)
        self._step7_dual_verification_live(data)
        self._step8_risk_control_live(data)
        self._step9_final_decision_live(data)

    def _finished_flow(self, data):
        """已结束比赛复盘流程"""
        print("\n  [已结束复盘模式]")

        # 基础信息
        self._step1_match_info(data)
        self._step2_odds_baseline(data)

        # 数据收集
        step2_1 = self._step2_1_recent_form(data)
        step2_2 = self._step2_2_head_to_head(data)
        step2_3 = self._step2_3_injuries(data)
        step2_5 = self._step2_5_formation(data)
        step2_6 = self._step2_6_web_intel(data)

        # 在线验证DeepSeek数据
        step2_1_verified, data_quality, confidence_adj = self._step2_4_verify_online(data, step2_1, "近期状态")
        self.data_quality = data_quality
        self.confidence_adjustment = confidence_adj

        # 将关键结论压缩后加入context
        self.context += f"状态: {step2_1_verified}\n"
        self.context += f"交锋: {step2_2}\n"
        self.context += f"伤停: {step2_3}\n"
        self.context += f"阵型: {step2_5}\n"
        # 伤停/阵型无数据时用联网情报补充 (豆包 web_search, 仅赛前信息)
        if ("无数据" in str(step2_3) or "无数据" in str(step2_5)) and "无数据" not in str(step2_6):
            self.context += f"联网情报: {str(step2_6)[:300]}\n"

        # 复盘分析
        self._step3_result_review(data)
        self._step4_review_analysis(data)
        self._step5_review_lessons(data)

    def _step1_match_info(self, data):
        """Step 1: 获取比赛信息"""
        print("\n" + "=" * 70)
        print("  Step 1: 获取比赛信息")
        print("=" * 70)
        print(f"  比赛: {data['home']} vs {data['away']}")
        print(f"  联赛: {data['league']}")
        if self.match_status in ['in_play', 'finished']:
            print(f"  当前比分: {data['current_score']}")
            print(f"  进行时间: {data['minute']}分钟")

        self.analysis_record['steps']['step1'] = {
            "home": data['home'],
            "away": data['away'],
            "home_en": data.get('home_en', ''),
            "away_en": data.get('away_en', ''),
            "league": data['league']
        }

    def _step2_odds_baseline(self, data):
        """Step 2: 建立赔率基线"""
        print("\n" + "=" * 70)
        print("  Step 2: 建立赔率基线")
        print("=" * 70)
        print(f"  全场独赢: 主{data['odds_home']} / 平{data['odds_draw']} / 客{data['odds_away']}")
        print(f"  全场让球: 主{data['hdp_home']} / 客{data['hdp_away']}")
        print(f"  全场大小: 大{data['ou_over']} / 小{data['ou_under']}")

        self.analysis_record['steps']['step2'] = {
            "odds_home": data['odds_home'],
            "odds_draw": data['odds_draw'],
            "odds_away": data['odds_away'],
            "hdp_home": data['hdp_home'],
            "hdp_away": data['hdp_away'],
            "ou_over": data['ou_over'],
            "ou_under": data['ou_under']
        }

    def _step2_1_recent_form(self, data):
        """Step 2.1: 近期状态 (优先用户数据)"""
        print("\n" + "=" * 70)
        print("  Step 2.1: 近期状态分析")
        print("=" * 70)

        # 铁律：用户提供的数据优先，禁止AI编造
        if data.get('user_form'):
            result = data['user_form']
            print(f"  [用户数据] {result}")
            self.analysis_record['steps']['step2_1'] = {"result": result, "source": "user_provided"}
            return result[:200] if len(result) > 200 else result

        # API-Football 大比赛验证
        if FOOTBALL_API_KEY:
            try:
                match_info = self.api_football.query_match(to_en_name(data['home']), to_en_name(data['away']))
                if match_info['available'] and match_info.get('last_home') and match_info.get('last_away'):
                    result = f"主队近5场: {match_info['last_home']}\n客队近5场: {match_info['last_away']}"
                    print(f"  [API数据] {result}")
                    self.analysis_record['steps']['step2_1'] = {"result": result, "source": "api_verified"}
                    return result
            except Exception as e:
                print(f"  [API查询失败] {e}")

        # 无数据：明确标注，不编造
        result = "无数据 (用户未提供近期状态)"
        print(f"  {result}")
        self.analysis_record['steps']['step2_1'] = {"result": result, "source": "no_data"}
        return result

    def _step2_2_head_to_head(self, data):
        """Step 2.2: 历史交锋 (优先用户数据)"""
        print("\n" + "=" * 70)
        print("  Step 2.2: 历史交锋分析")
        print("=" * 70)

        # 铁律：用户提供的数据优先
        if data.get('user_h2h'):
            result = data['user_h2h']
            print(f"  [用户数据] {result}")
            self.analysis_record['steps']['step2_2'] = {"result": result, "source": "user_provided"}
            return result[:200] if len(result) > 200 else result

        # API-Football 大比赛验证
        if FOOTBALL_API_KEY:
            try:
                match_info = self.api_football.query_match(to_en_name(data['home']), to_en_name(data['away']))
                if match_info['available']:
                    h2h_count = len(match_info.get('h2h', []))
                    if h2h_count > 0:
                        last = match_info['h2h'][0]
                        result = f"历史交锋: {h2h_count}场, 最近: {last['fixture']['date'][:10]} {last['goals']['home']}-{last['goals']['away']}"
                        print(f"  [API数据] {result}")
                        self.analysis_record['steps']['step2_2'] = {"result": result, "source": "api_verified"}
                        return result
            except Exception as e:
                print(f"  [API查询失败] {e}")

        # 无数据
        result = "无数据 (用户未提供历史交锋)"
        print(f"  {result}")
        self.analysis_record['steps']['step2_2'] = {"result": result, "source": "no_data"}
        return result

    def _step2_3_injuries(self, data):
        """Step 2.3: 伤病停赛 (优先用户数据)"""
        print("\n" + "=" * 70)
        print("  Step 2.3: 伤病停赛分析")
        print("=" * 70)

        # 铁律：用户提供的数据优先
        if data.get('user_injuries'):
            result = data['user_injuries']
            print(f"  [用户数据] {result}")
            self.analysis_record['steps']['step2_3'] = {"result": result, "source": "user_provided"}
            return result[:200] if len(result) > 200 else result

        # API-Football 大比赛验证
        if FOOTBALL_API_KEY:
            try:
                match_info = self.api_football.query_match(to_en_name(data['home']), to_en_name(data['away']))
                if match_info['available'] and match_info.get('injuries'):
                    result = match_info['injuries']
                    print(f"  [API数据] {result}")
                    self.analysis_record['steps']['step2_3'] = {"result": result, "source": "api_verified"}
                    return result
            except Exception as e:
                print(f"  [API查询失败] {e}")

        # 无数据
        result = "无数据 (用户未提供伤病停赛)"
        print(f"  {result}")
        self.analysis_record['steps']['step2_3'] = {"result": result, "source": "no_data"}
        return result

    def _step2_5_formation(self, data):
        """Step 2.5: 阵型分析 (优先用户数据)"""
        print("\n" + "=" * 70)
        print("  Step 2.5: 阵型分析")
        print("=" * 70)

        # 铁律：用户提供的数据优先
        if data.get('user_formation'):
            result = data['user_formation']
            print(f"  [用户数据] {result}")
            self.analysis_record['steps']['step2_5'] = {"result": result, "source": "user_provided"}
            return result[:200] if len(result) > 200 else result

        # 无数据
        result = "无数据 (用户未提供阵型)"
        print(f"  {result}")
        self.analysis_record['steps']['step2_5'] = {"result": result, "source": "no_data"}
        return result

    def _step2_6_web_intel(self, data):
        """Step 2.6: 联网情报 (豆包 web_search: 伤停/首发/临场新闻)

        铁律: 仅赛前可获取信息, 不进回测训练特征; 只做情报参考,
        最终数值仍以模型为准。缓存: 当天同一场比赛不重复搜索。
        关闭: 环境变量 DOUBAO_WEB_INTEL=0
        """
        print("\n" + "=" * 70)
        print("  Step 2.6: 联网情报 (豆包 web_search)")
        print("=" * 70)

        if os.getenv('DOUBAO_WEB_INTEL', '1') != '1':
            result = "已关闭 (DOUBAO_WEB_INTEL=0)"
            print(f"  {result}")
            self.analysis_record['steps']['step2_6'] = {"result": result, "source": "disabled"}
            return result

        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            'prediction_v2', 'src'))
            from web_search import doubao_web_search
        except Exception as e:
            result = f"web_search 模块不可用: {e}"
            print(f"  {result}")
            self.analysis_record['steps']['step2_6'] = {"result": result, "source": "module_error"}
            return result

        home_en = data.get('home_en') or to_en_name(data['home'])
        away_en = data.get('away_en') or to_en_name(data['away'])
        league = data.get('league', '')
        date_str = data.get('date', '')
        cache_key = f"{str(home_en).lower()}|{str(away_en).lower()}|{str(league).lower()}"

        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_path = os.path.join(base_dir, 'prediction_v2', 'output', 'web_intel_cache.json')
        cache = {}
        try:
            if os.path.isfile(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
        except Exception:
            cache = {}

        today = datetime.now().strftime('%Y-%m-%d')
        hit = cache.get(cache_key)
        if hit and str(hit.get('ts', '')).startswith(today):
            result = hit.get('result', '')
            print(f"  [缓存命中] {result[:120]}...")
            self.analysis_record['steps']['step2_6'] = {**hit, "source": "web_search_cache"}
            return result

        query = f"{home_en} vs {away_en} ({league}) {date_str} injury suspension expected lineup team news"
        r = doubao_web_search(query, max_output_tokens=1200, timeout=240)
        if not r.get('ok'):
            result = f"联网搜索失败: {r.get('error', '')} {str(r.get('text', ''))[:120]}"
            print(f"  {result}")
            self.analysis_record['steps']['step2_6'] = {"result": result, "source": "web_search_error"}
            return result

        result = str(r.get('text', ''))[:800]
        print(f"  [联网情报] {result[:200]}...")
        entry = {
            "result": result,
            "sources": r.get('sources', []),
            "searches": r.get('searches', []),
            "usage": r.get('usage', {}),
            "ts": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            cache[cache_key] = entry
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
        except Exception as e:
            print(f"  [缓存写入失败] {e}")

        self.analysis_record['steps']['step2_6'] = {**entry, "source": "web_search"}
        return result

    def _step2_5_formation_live(self, data):
        """Step 2.5: 阵型分析 (比赛中)"""
        print("\n" + "=" * 70)
        print("  Step 2.5: 阵型分析 (比赛中)")
        print("=" * 70)

        prompt = f"""基于以下比赛实时信息，分析阵型:

{self.context}

请简洁回答 (不超过100字):
1. 主客队阵型对比
2. 阵型对当前比分的影响
3. 阵型对下半场的影响"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step2_5'] = {"result": result}

        return result[:200] if len(result) > 200 else result

    def _step2_4_verify_online(self, data, deepseek_data, data_type):
        """Step 2.4: 在线验证DeepSeek数据 (API-Football实时数据)"""
        print("\n" + "=" * 70)
        print("  Step 2.4: 在线验证 (API-Football)")
        print("=" * 70)

        # 优先使用API-Football获取实时数据
        if FOOTBALL_API_KEY:
            try:
                match_info = self.api_football.query_match(to_en_name(data['home']), to_en_name(data['away']))
                
                if match_info['available']:
                    # 获取到实时数据
                    verification = []
                    
                    # 验证球队是否存在
                    if match_info['home_team']:
                        verification.append(f"主队 {data['home']}: 已确认 (ID:{match_info['home_team']['id']})")
                    else:
                        verification.append(f"主队 {data['home']}: 未找到")
                    
                    if match_info['away_team']:
                        verification.append(f"客队 {data['away']}: 已确认 (ID:{match_info['away_team']['id']})")
                    else:
                        verification.append(f"客队 {data['away']}: 未找到")
                    
                    # 验证历史交锋
                    h2h_count = len(match_info['h2h'])
                    verification.append(f"历史交锋: {h2h_count}场记录")
                    
                    if h2h_count > 0:
                        # 显示最近交锋
                        last_match = match_info['h2h'][0]
                        home_goals = last_match['goals']['home']
                        away_goals = last_match['goals']['away']
                        match_date = last_match['fixture']['date'][:10]
                        verification.append(f"最近交锋: {match_date} {home_goals}-{away_goals}")
                    
                    verify_text = "\n".join(verification)
                    print(f"  [API-Football验证]\n{verify_text}")
                    
                    # 判断数据质量
                    teams_found = match_info['home_team'] and match_info['away_team']
                    if teams_found and h2h_count > 0:
                        data_quality = "high"
                        confidence_adj = 10
                        status = "api_verified"
                    elif teams_found:
                        data_quality = "medium"
                        confidence_adj = 0
                        status = "api_teams_only"
                    else:
                        data_quality = "low"
                        confidence_adj = -10
                        status = "api_partial"
                    
                    self.analysis_record['steps']['step2_4'] = {
                        "deepseek_data": deepseek_data,
                        "api_verification": verify_text,
                        "h2h_count": h2h_count,
                        "status": status,
                        "data_quality": data_quality,
                        "confidence_adjustment": confidence_adj,
                        "note": "API-Football实时数据验证"
                    }
                    return verify_text, data_quality, confidence_adj
                else:
                    print("  [API-Football] 未找到比赛数据(可能是低级别联赛)")
            except Exception as e:
                print(f"  [API-Football异常] {str(e)}")

        # 降级: 使用火山引擎模型验证 (GLM-5.2 比Doubao更快响应)
        if ARK_API_KEY and GLM_ENDPOINT_ID:
            try:
                prompt = f"""评估比赛数据合理性:
比赛: {data['home']} vs {data['away']}
联赛: {data['league']}
数据: {deepseek_data[:200]}

返回: 合理/部分合理/不合理 + 简短说明"""

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ARK_API_KEY}"
                }
                payload = {
                    "model": GLM_ENDPOINT_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300
                }

                resp = requests.post(f"{ARK_API_URL}/chat/completions", json=payload, headers=headers, timeout=120)
                if resp.status_code == 200:
                    model_result = resp.json()['choices'][0]['message']['content']
                    print(f"  [GLM评估] {model_result[:300]}...")

                    if "不合理" in model_result or "不确定" in model_result:
                        data_quality = "low"
                        confidence_adj = -15
                        status = "volc_unsure"
                    else:
                        data_quality = "medium"
                        confidence_adj = -5
                        status = "volc_plausible"

                    self.analysis_record['steps']['step2_4'] = {
                        "deepseek_data": deepseek_data,
                        "volc_evaluation": model_result,
                        "status": status,
                        "data_quality": data_quality,
                        "confidence_adjustment": confidence_adj,
                        "note": "火山引擎GLM评估"
                    }
                    return model_result, data_quality, confidence_adj
            except Exception as e:
                print(f"  [火山引擎异常] {str(e)}")

        # 尝试使用Doubao (备用)
        if ARK_API_KEY and DOUBAO_ENDPOINT_ID:
            try:
                prompt = f"""评估比赛数据合理性:
比赛: {data['home']} vs {data['away']}
联赛: {data['league']}
数据: {deepseek_data[:200]}

返回: 合理/部分合理/不合理 + 简短说明"""

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {ARK_API_KEY}"
                }
                payload = {
                    "model": DOUBAO_ENDPOINT_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 300
                }

                resp = requests.post(f"{ARK_API_URL}/chat/completions", json=payload, headers=headers, timeout=30)
                if resp.status_code == 200:
                    doubao_result = resp.json()['choices'][0]['message']['content']
                    print(f"  [Doubao评估] {doubao_result[:300]}...")

                    if "不合理" in doubao_result or "不确定" in doubao_result:
                        data_quality = "low"
                        confidence_adj = -15
                        status = "doubao_unsure"
                    else:
                        data_quality = "medium"
                        confidence_adj = -5
                        status = "doubao_plausible"

                    self.analysis_record['steps']['step2_4'] = {
                        "deepseek_data": deepseek_data,
                        "doubao_evaluation": doubao_result,
                        "status": status,
                        "data_quality": data_quality,
                        "confidence_adjustment": confidence_adj,
                        "note": "豆包评估"
                    }
                    return doubao_result, data_quality, confidence_adj
            except Exception as e:
                print(f"  [Doubao异常] {str(e)}")

        # 降级: 使用Kimi知识库验证

        # 降级: 使用Kimi知识库验证
        if KIMI_API_KEY:
            try:
                prompt = f"""基于你的知识库, 评估以下足球比赛数据的合理性:

比赛: {data['home']} vs {data['away']}
联赛: {data['league']}

DeepSeek提供的数据:
{deepseek_data}

请评估:
1. 这个联赛是否存在? (你的知识截止2023年)
2. 数据是否合理?
3. 你能确认这些信息吗?

返回格式:
评估结果: 合理/部分合理/不合理
置信度: 高/中/低
说明: (简短说明)"""

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {KIMI_API_KEY}"
                }
                payload = {
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }

                resp = requests.post(KIMI_API_URL, json=payload, headers=headers, timeout=30)
                if resp.status_code == 200:
                    kimi_result = resp.json()['choices'][0]['message']['content']
                    print(f"  [Kimi评估] {kimi_result[:300]}...")
                    print("  [注意] Kimi知识截止2023年, 无法验证2026年实时数据")

                    if "不合理" in kimi_result or "不确定" in kimi_result:
                        data_quality = "low"
                        confidence_adj = -20
                        status = "kimi_unsure"
                    else:
                        data_quality = "medium"
                        confidence_adj = -10
                        status = "kimi_plausible"

                    self.analysis_record['steps']['step2_4'] = {
                        "deepseek_data": deepseek_data,
                        "kimi_evaluation": kimi_result,
                        "status": status,
                        "data_quality": data_quality,
                        "confidence_adjustment": confidence_adj,
                        "note": "Kimi知识库评估"
                    }
                    return kimi_result, data_quality, confidence_adj
            except Exception as e:
                print(f"  [Kimi异常] {str(e)}")

        # 降级: 使用豆包知识库验证
        if DOUBAO_API_KEY and DOUBAO_ENDPOINT_ID:
            try:
                prompt = f"""基于你的知识库, 评估以下足球比赛数据的合理性:

比赛: {data['home']} vs {data['away']}
联赛: {data['league']}

DeepSeek提供的数据:
{deepseek_data}

请评估:
1. 这个联赛是否存在?
2. 数据是否合理?
3. 你能确认这些信息吗?

返回格式:
评估结果: 合理/部分合理/不合理
置信度: 高/中/低
说明: (简短说明)"""

                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DOUBAO_API_KEY}"
                }
                payload = {
                    "model": DOUBAO_ENDPOINT_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }

                resp = requests.post(f"{DOUBAO_API_URL}/chat/completions", json=payload, headers=headers, timeout=60)
                if resp.status_code == 200:
                    doubao_result = resp.json()['choices'][0]['message']['content']
                    print(f"  [豆包评估] {doubao_result[:300]}...")

                    if "不合理" in doubao_result or "不确定" in doubao_result:
                        data_quality = "low"
                        confidence_adj = -15
                        status = "doubao_unsure"
                    else:
                        data_quality = "medium"
                        confidence_adj = -5
                        status = "doubao_plausible"

                    self.analysis_record['steps']['step2_4'] = {
                        "deepseek_data": deepseek_data,
                        "doubao_evaluation": doubao_result,
                        "status": status,
                        "data_quality": data_quality,
                        "confidence_adjustment": confidence_adj,
                        "note": "豆包知识库评估"
                    }
                    return doubao_result, data_quality, confidence_adj
            except Exception as e:
                print(f"  [豆包异常] {str(e)}")

        # 最终降级: 未验证
        print("  [降级] 使用DeepSeek数据(未验证)")
        print("  [数据质量] LOW - 未验证")
        print("  [置信度调整] -15%")

        self.analysis_record['steps']['step2_4'] = {
            "deepseek_data": deepseek_data,
            "verified_data": "未验证 - 无法获取实时数据",
            "status": "unverified",
            "data_quality": "low",
            "confidence_adjustment": -15
        }

        return deepseek_data, "low", -15

    def _step3_mode_switch(self, data):
        """Step 3: R90模式切换"""
        print("\n" + "=" * 70)
        print("  Step 3: R90模式切换")
        print("=" * 70)

        prompt = f"""基于以下比赛信息，判断是友谊赛还是正赛:

{self.context}

请简洁回答:
1. 模式: 正赛/友谊赛
2. 理由"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step3'] = {"result": result}

    def _step4_odds_deviation(self, data):
        """Step 4: R119赔率偏差 (规则引擎计算)"""
        print("\n" + "=" * 70)
        print("  Step 4: R119赔率偏差分析")
        print("=" * 70)

        rule_data = self._build_rule_data(data)
        rule_result = self.rule_engine.analyze_match(rule_data) if self.rule_engine else None

        if rule_result:
            signals = rule_result['signals']
            # 收集相关规则信号
            r119 = [s for s in signals if s.rule_id == 'R119']
            r120 = [s for s in signals if s.rule_id == 'R120']
            r1_3 = [s for s in signals if s.rule_id in ['R1', 'R2', 'R3']]

            lines = []
            if r119:
                for s in r119:
                    lines.append(f"  R119: {s.reason} (强度{s.strength:+d}, 置信{s.confidence:.0%})")
            else:
                lines.append("  R119: 无显著赔率偏差 (<3%)")

            if r120:
                for s in r120:
                    lines.append(f"  R120: {s.reason}")
            else:
                lines.append("  R120: 赔率确定性不高")

            for s in r1_3:
                lines.append(f"  {s.rule_id}: {s.reason}")

            # 情报类规则 (联网情报驱动)
            intel_ids = ['R10', 'R98', 'R124', 'R127', 'R136', 'R143', 'R145', 'R147']
            for s in signals:
                if s.rule_id in intel_ids:
                    lines.append(f"  {s.rule_id} {s.name}: {s.reason} (强度{s.strength:+d})")

            result = "\n".join(lines)
            # 判断方向
            direction = rule_result['direction']
            result += f"\n  规则引擎方向: {'主' if direction=='home' else '客' if direction=='away' else '平'} (总强度{rule_result['total_strength']:+d})"
            self.analysis_record['steps']['step4'] = {"result": result, "signals": [s.rule_id for s in signals], "total_strength": rule_result['total_strength']}
            print(f"  {result}")
        else:
            print("  [规则引擎不可用]")

    def _step5_handicap_analysis(self, data):
        """Step 5: 让球盘分析 (规则引擎计算)"""
        print("\n" + "=" * 70)
        print("  Step 5: 让球盘分析")
        print("=" * 70)

        rule_data = self._build_rule_data(data)
        hdp_result = self.handicap_engine.analyze_handicap(rule_data) if self.handicap_engine else None

        if hdp_result:
            direction_map = {'hdp_win': '让胜', 'hdp_draw': '让平', 'hdp_lose': '让负'}
            direction = hdp_result['direction']
            signals = hdp_result['signals']

            lines = []
            for s in signals:
                lines.append(f"  [{s.rule_id}] {s.name}: {s.reason}")

            lines.append(f"\n  推荐方向: {direction_map.get(direction, direction)}")
            lines.append(f"  触发规则数: {hdp_result['n_signals']}")

            result = "\n".join(lines)
            self.analysis_record['steps']['step5'] = {"result": result, "direction": direction}
            print(f"  {result}")
        else:
            print("  [让球引擎不可用]")

    def _step6_dual_verification(self, data):
        """Step 6: R105双面验证"""
        print("\n" + "=" * 70)
        print("  Step 6: R105双面验证")
        print("=" * 70)

        prompt = f"""基于以下完整分析信息，对推荐进行双面验证:

{self.context}

请简洁回答:
1. 正方信号 (利好)
2. 反方信号 (利空)
3. 净值判断
4. 结论"""

        result = self.deepseek_query(prompt, compress_context=True)
        print(f"  {result}")
        self.analysis_record['steps']['step6'] = {"result": result}

    def _step7_risk_control(self, data):
        """Step 7: R117/R118风控"""
        print("\n" + "=" * 70)
        print("  Step 7: R117/R118风控检查")
        print("=" * 70)

        prompt = f"""基于以下完整分析信息，进行风控检查:

{self.context}

请简洁回答:
1. R117: 让平集中度检查
2. R118: 碾压判定
3. 风险提示"""

        result = self.deepseek_query(prompt, compress_context=True)
        print(f"  {result}")
        self.analysis_record['steps']['step7'] = {"result": result}

    def _split_home_away_text(self, text: str) -> tuple:
        """按句号分割文本, 分离主客队信息块 (返回 home_block, away_block)
        依赖 step2_1 的 user_form 顺序: 主队在前, 客队在后
        跳过标题句(如"近10场战绩"等无球队数据的行)
        """
        home_block = ''
        away_block = ''
        segs = [s for s in text.split('。') if s.strip()]
        if len(segs) >= 2:
            # 跳过标题句: 不含球队数据特征(胜平负/进球/场次)的句
            data_kw = ['胜', '平', '负', '进球', '失球', '场均', '射门', '射正', '不败', '总进', '总失']
            def is_data(seg):
                return any(k in seg for k in data_kw)
            data_segs = [s for s in segs if is_data(s)]
            if len(data_segs) >= 2:
                home_block = data_segs[0]
                away_block = data_segs[1]
            elif data_segs:
                home_block = data_segs[0]
            else:
                home_block = segs[0]
                away_block = segs[1] if len(segs) > 1 else ''
        return home_block, away_block

    def _agent_risk_signals(self, data):
        """Step 7.5: Agent风险信号前置 (结构化, 供Step8修正λ)"""
        self._risk_signals = None
        if not self.agent:
            return
        try:
            print("\n" + "=" * 70)
            print("  Step 7.5: Agent风险信号前置 (供λ修正)")
            print("=" * 70)
            # 从特征提取器拿场均进球供Agent参考
            stats = {}
            feats = self.analysis_record.get('steps', {}).get('step2_1', {}).get('features', {})
            if feats:
                stats['lambda_home'] = feats.get('home_gf')
                stats['lambda_away'] = feats.get('away_gf')
                stats['over25_prob'] = 0.55

            signals = self.agent.risk_signals(
                data.get('user_form', ''),
                data.get('user_form', ''),
                data.get('user_h2h', ''),
                data.get('user_injuries', ''),
                data.get('user_motivation', ''),
                stats,
            )
            self._risk_signals = signals
            self.analysis_record['agent_risk_signals'] = signals
            print(f"  Agent风险信号: "
                  f"主攻{signals['home_attack_risk']:.1f} 客攻{signals['away_attack_risk']:.1f} "
                  f"主防{signals['home_defense_risk']:.1f} 客防{signals['away_defense_risk']:.1f} "
                  f"闷平{signals['deadlock_prob']:.1f} 主场失效{signals['home_adv_lost']:.1f} "
                  f"方向: {signals['direction']}")
        except Exception as e:
            print(f"  [Agent风险信号失败] {e}")
            self._risk_signals = None

    def _step8_final_decision(self, data):
        """Step 8: 最终判断 (让球 + 大小球 + 比分)"""
        print("\n" + "=" * 70)
        print("  Step 8: 最终综合判断")
        print("=" * 70)

        # ML大小球预测
        ml_result = None
        try:
            # 解析大小球盘口
            ou_line = 2.5
            if '@' in str(data['ou_over']):
                ou_parts = data['ou_over'].split('@')
                ou_str = ou_parts[0].strip()
                # 处理 2/2.5 或 3/3.5 这种复合盘口
                if '/' in ou_str:
                    ou_parts2 = ou_str.split('/')
                    ou_line = (float(ou_parts2[0]) + float(ou_parts2[1])) / 2
                else:
                    ou_line = float(ou_str)
            
            # 从step2_1和step2_2提取xG数据
            home_xg = None
            away_xg = None
            
            # 尝试从近期状态提取xG
            step2_1_text = self.analysis_record.get('steps', {}).get('step2_1', {}).get('result', '')
            import re
            xg_matches = re.findall(r'xG[=:]\s*(\d+\.?\d*)', step2_1_text)
            if len(xg_matches) >= 2:
                home_xg = float(xg_matches[0])
                away_xg = float(xg_matches[1])
            
            # 使用ML模型预测 (league_avg_goals用真实联赛场均)
            league_avg = get_league_avg_goals(data['league'])
            ml_result = self.ml_model.predict(
                home_xg=home_xg,
                away_xg=away_xg,
                odds_home=float(data['odds_home']),
                odds_draw=float(data['odds_draw']),
                odds_away=float(data['odds_away']),
                league_avg_goals=league_avg,
                league=data['league'],
            )
            
            # 计算实际盘口的大/小球概率 (修复: 用over_prob_for_line计算对应盘口概率)
            over_line_prob = ml_result.over_prob_for_line(ou_line)
            under_line_prob = ml_result.under_prob_for_line(ou_line)
            
            print(f"\n  [ML大小球预测]")
            print(f"  预测总进球: {ml_result.predicted_total_goals:.2f}")
            print(f"  大{ou_line}概率: {over_line_prob:.1%}")
            print(f"  小{ou_line}概率: {under_line_prob:.1%}")
            print(f"  大3.5概率: {ml_result.over35_prob:.1%}")
            print(f"  小3.5概率: {ml_result.under35_prob:.1%}")
            print(f"  信心: {'⭐' * ml_result.confidence}")
            print(f"  模型类型: {ml_result.model_type}")
            
        except Exception as e:
            print(f"  [ML预测异常] {e}")

        # 泊松比分预测
        try:
            odds_h = float(data['odds_home'])
            odds_d = float(data['odds_draw'])
            odds_a = float(data['odds_away'])
            
            # 从step2_1提取近期进失球数据，计算场均进球
            h2h_avg = None
            step2_1_text = self.analysis_record.get('steps', {}).get('step2_1', {}).get('result', '')
            step2_2_text = self.analysis_record.get('steps', {}).get('step2_2', {}).get('result', '')
            
            import re
            # 优先从历史交锋提取
            if '场均进球' in step2_2_text or '总进球' in step2_2_text:
                nums = re.findall(r'(\d+\.?\d*)\s*球', step2_2_text)
                if nums:
                    h2h_avg = float(nums[0])
            
            # 从近期战绩提取进失球，如 "进6球失5球" (仅当明确为场均数据时使用)
            goals_for = re.findall(r'进(\d+)球', step2_1_text)
            goals_against = re.findall(r'失(\d+)球', step2_1_text)
            # 只有明确写"场均进X失Y"才用累计数算场均
            # 说明: "近10场进18球失10球"是累计数, 不是场均! 直接用会严重放大λ
            # 只有 h2h_avg 完全缺失时才用累计数粗略估算, 且必须除以实际场次
            if goals_for and goals_against and h2h_avg is None:
                # 尝试从文本提取"近N场"场次
                n_match = re.search(r'近\s*(\d+)\s*场', step2_1_text)
                n_games = int(n_match.group(1)) if n_match else 5
                # 每队场次: 文本是两队数据拼接, 场次数取文本提到的场次
                total_goals = sum(int(x) for x in goals_for) + sum(int(x) for x in goals_against)
                total_matches = max(n_games, 1)  # 累计进球/场次 = 场均总进球
                per_match_avg = total_goals / total_matches
                # 只能用于交叉验证参考, 不做主λ依据
                # 若明显不合理(>6球/场)则丢弃
                if 0.5 <= per_match_avg <= 6.0:
                    h2h_avg = per_match_avg

            # 优先使用用户提供的真实场均进失球 (格式: 场均进X失Y)
            # 兼容多种格式:
            #   A) "场均进1.7失0.6"  (紧凑)
            #   B) "场均进球1.7球场均失球0.6球"  (独立字段)
            #   C) "场均进球1.7 场均失球0.6"
            home_gf = away_gf = home_ga = away_ga = None
            gf_ga = re.findall(r'场均进(\d+\.?\d*)失(\d+\.?\d*)', step2_1_text)
            if len(gf_ga) >= 2:
                home_gf, home_ga = float(gf_ga[0][0]), float(gf_ga[0][1])
                away_gf, away_ga = float(gf_ga[1][0]), float(gf_ga[1][1])
            else:
                # 按主客文本块分别提取 (紧凑格式 "场均进X失Y" 或 独立字段 "场均进球X球")
                import re as _re
                home_block, away_block = self._split_home_away_text(step2_1_text)
                # 主队: 先紧凑格式, 再独立字段
                m_h = _re.search(r'场均进(\d+\.?\d*)失(\d+\.?\d*)', home_block)
                if m_h:
                    home_gf, home_ga = float(m_h.group(1)), float(m_h.group(2))
                else:
                    m_gf = _re.search(r'场均进球\s*(\d+\.?\d*)\s*球', home_block)
                    m_ga = _re.search(r'场均失球\s*(\d+\.?\d*)\s*球', home_block)
                    if m_gf:
                        home_gf = float(m_gf.group(1))
                    if m_ga:
                        home_ga = float(m_ga.group(1))
                # 客队
                m_a = _re.search(r'场均进(\d+\.?\d*)失(\d+\.?\d*)', away_block)
                if m_a:
                    away_gf, away_ga = float(m_a.group(1)), float(m_a.group(2))
                else:
                    m_gf = _re.search(r'场均进球\s*(\d+\.?\d*)\s*球', away_block)
                    m_ga = _re.search(r'场均失球\s*(\d+\.?\d*)\s*球', away_block)
                    if m_gf:
                        away_gf = float(m_gf.group(1))
                    if m_ga:
                        away_ga = float(m_ga.group(1))

            if home_gf and away_gf:
                # 用真实攻防数据计算λ (标准范式: 主队λ=主队进攻×客队防守弱度)
                league_avg = get_league_avg_goals(data['league'])
                avg_atk = league_avg / 2
                # 联赛可配置修正系数 (SOP Step8 v3: odds_zones correct_coef + calibration.json 校准结果)
                cc = get_league_correct_coef(data['league'])
                # 线上滚动攻防优先 (SOP第三类): team_strength.json 有可靠数据则覆盖情报场均
                # P0审计: 覆盖前数值安全钳位+数据冲突告警; 移除"not shrunk"限制 (滚动库收缩仍优于原始情报)
                _lam_warnings = []              # 统一结构化告警 (SOP Step8 v4, 复盘按 code 分组)
                _lam_data_source = "info_text"  # 数据源分级: ts_high_conf / ts_low_conf / info_text
                try:
                    sys.path.insert(0, 'src/models')
                    from team_strength import TeamStrengthDB
                    _ts = TeamStrengthDB().get_team_strengths(str(data.get('home', '')), str(data.get('away', '')), league_avg)
                    if _ts.get('usable') and _ts.get('sample_n', 0) >= 4:
                        _ts_h_gf = max(0.01, min(4.0, _ts['home_attack'] * avg_atk))
                        _ts_h_ga = max(0.01, min(4.0, _ts['home_defend'] * avg_atk))
                        _ts_a_gf = max(0.01, min(4.0, _ts['away_attack'] * avg_atk))
                        _ts_a_ga = max(0.01, min(4.0, _ts['away_defend'] * avg_atk))
                        # 情报与滚动库差值过大 → 数据冲突告警 (复盘区分 λ 来源)
                        if abs(_ts_h_gf - home_gf) > 0.4 or abs(_ts_a_gf - away_gf) > 0.4:
                            _lam_warnings.append({"code": "TS_DATA_CONFLICT", "level": "warn",
                                "msg": "滚动攻防库与情报场均偏差过大: 情报HG=%.2f/AG=%.2f, 库HG=%.2f/AG=%.2f"
                                       % (home_gf, away_gf, _ts_h_gf, _ts_a_gf)})
                            print("    [WARN] 滚动攻防库与情报场均偏差过大 → 已标记数据冲突")
                        home_gf, home_ga = _ts_h_gf, _ts_h_ga
                        away_gf, away_ga = _ts_a_gf, _ts_a_ga
                        _ts_n = _ts.get('sample_n', 0)
                        _lam_data_source = "ts_high_conf" if _ts_n >= 8 else "ts_low_conf"
                        _lam_warnings.append({"code": "TS_OVERWRITE", "level": "info",
                            "msg": "已用滚动加权攻防库覆盖情报场均 (样本%d场, %s)" % (_ts_n, _lam_data_source)})
                        print(f"    [INFO] 使用 team_strength 在线滚动攻防 (样本{_ts_n}场, 数据源={_lam_data_source})")
                except Exception as _ts_e:
                    _lam_warnings.append({"code": "TS_FALLBACK", "level": "warn",
                        "msg": "滚动攻防库查询失败, 回退情报场均: %s" % _ts_e})
                # 样本量兜底 (SOP Step2.1 v3): ≥8场原值 / 4-7场向联赛均值收缩30% / <4场联赛基准+降星告警
                # P1审计: 主客样本量独立 (sample_n_home / sample_n_away), 四方攻防全部平滑
                low_sample_warns = []
                sample_n = sample_n_home = sample_n_away = 8
                try:
                    sys.path.insert(0, 'src/models')
                    from poisson_lambda import adjust_gf_by_sample
                    _hb = _ab = step2_1_text
                    try:
                        _hb = home_block or step2_1_text
                    except NameError:
                        pass
                    try:
                        _ab = away_block or step2_1_text
                    except NameError:
                        pass
                    _n_h = re.search(r'近\s*(\d+)\s*场', _hb)
                    _n_a = re.search(r'近\s*(\d+)\s*场', _ab)
                    sample_n_home = int(_n_h.group(1)) if _n_h else 8
                    sample_n_away = int(_n_a.group(1)) if _n_a else 8
                    sample_n = max(sample_n_home, sample_n_away)
                    home_gf, _w1 = adjust_gf_by_sample(home_gf, sample_n_home, league_avg)
                    home_ga, _w2 = adjust_gf_by_sample(home_ga, sample_n_home, league_avg)
                    away_gf, _w3 = adjust_gf_by_sample(away_gf, sample_n_away, league_avg)
                    away_ga, _w4 = adjust_gf_by_sample(away_ga, sample_n_away, league_avg)
                    for _w in (_w1, _w2, _w3, _w4):
                        if _w:
                            low_sample_warns.append(_w)
                            _lam_warnings.append({"code": "SAMPLE_SHRINK", "level": "warn", "msg": _w})
                            print(f"    ⚠️ {_w}")
                except Exception:
                    pass
                # 标准化泊松λ (SOP Step8 v4, src/models/poisson_lambda.py)
                #  λ_base,H = avg_atk×attack_h×defend_a = home_gf×away_ga/avg_atk; λ∈[0.2,4.5] 超界截断告警
                #  P0审计: 补全 fatigue/injury/risk 分边入参; λ结果写回 lam_h/lam_a (此前缺失→整个泊松分支失效)
                _lam_res = None
                # Step7.5 Agent风险信号 → 分边扰动 (进 calc_lambdas 模型内应用: 硬限幅±10%, 与市场方向矛盾降权50%)
                _sig_h = 0.0
                _sig_a = 0.0
                _agent_note = ""
                _rs = getattr(self, '_risk_signals', None)
                if _rs:
                    try:
                        _agent_dir = _rs.get('direction', 'unknown')
                        _market_home = (odds_h < odds_a)
                        _rs_weight = 1.0
                        if _agent_dir in ('home', 'away'):
                            _market_align = (_market_home and _agent_dir == 'home') or ((not _market_home) and _agent_dir == 'away')
                            if not _market_align:
                                _rs_weight = 0.5
                                print(f"    [WARN] Agent方向[{_agent_dir}]与盘口市场方向矛盾 → 信号降权50%")
                        if _rs.get('home_attack_risk', 0) > 0.3:
                            _sig_h -= _rs['home_attack_risk'] * _rs_weight
                            _agent_note += f" Agent:主攻-{_rs['home_attack_risk']:.0%}"
                        if _rs.get('away_attack_risk', 0) > 0.3:
                            _sig_a -= _rs['away_attack_risk'] * _rs_weight
                            _agent_note += f" Agent:客攻-{_rs['away_attack_risk']:.0%}"
                        if _rs.get('home_defense_risk', 0) > 0.3:
                            _sig_a += _rs['home_defense_risk'] * _rs_weight
                            _agent_note += f" Agent:主防+{_rs['home_defense_risk']:.0%}"
                        if _rs.get('away_defense_risk', 0) > 0.3:
                            _sig_h += _rs['away_defense_risk'] * _rs_weight
                            _agent_note += f" Agent:客防+{_rs['away_defense_risk']:.0%}"
                        if _rs.get('deadlock_prob', 0) > 0.4:
                            _sig_h -= _rs['deadlock_prob'] * _rs_weight
                            _sig_a -= _rs['deadlock_prob'] * _rs_weight
                            _agent_note += f" Agent:闷平-{_rs['deadlock_prob']:.0%}"
                        if _rs.get('home_adv_lost', 0) > 0.3:
                            _sig_h -= _rs['home_adv_lost'] * _rs_weight
                            _agent_note += f" Agent:主场失效-{_rs['home_adv_lost']:.0%}"
                        self._risk_weight = _rs_weight
                    except Exception:
                        pass
                try:
                    sys.path.insert(0, 'src/models')
                    from poisson_lambda import calc_lambdas
                    _rho_pl = 0.0
                    try:
                        _pc_pl = get_league_prob_calib(data['league'])
                        _rho_pl = _pc_pl['rho'] if _pc_pl else 0.0
                    except Exception:
                        pass
                    _lam_res = calc_lambdas(
                        home_gf=home_gf, away_ga=away_ga,
                        away_gf=away_gf, home_ga=home_ga,
                        league_avg=league_avg,
                        home_coef=cc.get('home_coef', 1.0),
                        away_coef=cc.get('away_coef', 1.0),
                        fatigue_coef=cc.get('fatigue_coef', 1.0),
                        injury_coef_h=cc.get('injury_coef_h', 1.0),
                        injury_coef_a=cc.get('injury_coef_a', 1.0),
                        risk_signal_h=_sig_h, risk_signal_a=_sig_a,
                        rho=_rho_pl)
                    # P0关键修复: calc_lambdas 的 λ 写回本地变量 (此前缺失→特征修正/Agent/概率全部失效)
                    lam_h = _lam_res['lam_h']
                    lam_a = _lam_res['lam_a']
                    if _lam_res.get('risk_conflict', {}).get('conflict'):
                        self._risk_conflict = _lam_res['risk_conflict']
                    for _w in _lam_res.get('warnings_detail', []):
                        _lam_warnings.append(_w)
                        if _w.get('level') != 'info':
                            print(f"    [WARN] {_w['msg']}")
                except Exception as _le:
                    _lam_warnings.append({"code": "LAM_CALC_ERROR", "level": "error",
                        "msg": "λ计算异常: %s, 降级使用基础λ(含主客/疲劳系数)" % _le})
                    # P0审计: 降级兜底保留主客/疲劳修正, 不再退回纯基础λ
                    lam_h = home_gf * away_ga / avg_atk * cc.get('home_coef', 1.0) * cc.get('fatigue_coef', 1.0)
                    lam_a = away_gf * home_ga / avg_atk * cc.get('away_coef', 1.0) * cc.get('fatigue_coef', 1.0)

                # 【特征修正】用情报中的关键指标修正λ (解决数据蕴含方向但模型没用)
                feature_note = ""
                if self.feature_extractor:
                    try:
                        # 拆分主客情报 (用统一方法, 处理"。。"双句号空段问题)
                        home_txt, away_txt = self._split_home_away_text(step2_1_text)
                        feats = self.feature_extractor.extract(home_txt, away_txt, step2_2_text)
                        self.analysis_record['steps']['step2_1']['features'] = feats

                        # 1. 业余vs职业断层 → 强队λ放大, 弱队λ缩小
                        if feats.get('amateur_vs_pro') == 1:
                            # 主业余客职业: 客队λ放大
                            lam_a *= cc['amateur_vs_pro_strong']
                            lam_h *= cc['amateur_vs_pro_weak']
                            feature_note += " 业余vs职业→客队λ放大"
                        elif feats.get('pro_vs_amateur') == 1:
                            lam_h *= cc['amateur_vs_pro_strong']
                            lam_a *= cc['amateur_vs_pro_weak']
                            feature_note += " 职业vs业余→主队λ放大"

                        # 2. 锋线哑火 → 进攻λ缩小
                        if feats.get('home_attack_disabled'):
                            lam_h *= cc['striker_miss']
                            feature_note += " 主队锋线哑火"
                        if feats.get('away_attack_disabled'):
                            lam_a *= cc['striker_miss']
                            feature_note += " 客队锋线哑火"

                        # 3. 防线弱 → 对手λ放大
                        if feats.get('home_defense_weak'):
                            lam_a *= cc['weak_defense']
                            feature_note += " 主队防线弱"
                        if feats.get('away_defense_weak'):
                            lam_h *= cc['weak_defense']
                            feature_note += " 客队防线弱"

                        # 4. 状态差 → 好的队λ放大
                        form_diff = feats.get('form_diff', 0)
                        if form_diff > 0.3:
                            lam_h *= cc['form_good']
                            feature_note += " 主队状态优"
                        elif form_diff < -0.3:
                            lam_a *= cc['form_good']
                            feature_note += " 客队状态优"

                        # 5. 关键球员缺阵
                        if feats.get('attack_key_out'):
                            lam_h *= cc['key_striker_out'] if 'home' in feats and feats.get('defense_key_out') else 0.9
                            feature_note += " 关键射手缺阵"
                        # 5.2 升班马修正 (SOP Step8 v3.1): 次级联赛升级队攻防强度打折, 防线更漏
                        #     系数存 odds_zones correct_coef: promoted_attack(自队λ) / promoted_defense(对手λ)
                        if feats.get('home_promoted'):
                            lam_h *= cc.get('promoted_attack', 1.0)
                            lam_a *= cc.get('promoted_defense', 1.0)
                            feature_note += " 主队升班马(攻×%.2f/对手λ×%.2f)" % (cc.get('promoted_attack', 1.0), cc.get('promoted_defense', 1.0))
                        if feats.get('away_promoted'):
                            lam_a *= cc.get('promoted_attack', 1.0)
                            lam_h *= cc.get('promoted_defense', 1.0)
                            feature_note += " 客队升班马(攻×%.2f/对手λ×%.2f)" % (cc.get('promoted_attack', 1.0), cc.get('promoted_defense', 1.0))
                        # 5.5/6. 疲劳与Agent风险信号已移入 calc_lambdas 模型内应用 (SOP Step8 v4)
                        #     疲劳系数 fatigue_coef 由联赛配置统一生效; Agent分边扰动在 calc_lambdas
                        #     内硬限幅±10% + 基本面冲突减半, 避免双重修正
                        if _agent_note:
                            feature_note += _agent_note
                        if _lam_res:
                            _rh = _lam_res.get('risk_signal_h', 0.0)
                            _ra = _lam_res.get('risk_signal_a', 0.0)
                            if _rh or _ra:
                                feature_note += f" Agent扰动H{_rh:+.0%}/A{_ra:+.0%}(限±10%)"
                            if _lam_res.get('risk_conflict', {}).get('conflict'):
                                feature_note += " 风险对抗降级"
                    except Exception as e:
                        pass

                # 用赔率反推概率作交叉验证
                prob_h = 1/odds_h; prob_d = 1/odds_d; prob_a = 1/odds_a
                total = prob_h + prob_d + prob_a
                # λ硬截断 [0.2,4.5] (SOP Step8 v3): 不再全局缩放回联赛均值, 避免抹平伤停/主场/Agent修正
                if not (0.2 <= lam_h <= 4.5) or not (0.2 <= lam_a <= 4.5):
                    print(f"    ⚠️ λ超出[0.2,4.5]已截断: H={lam_h:.2f} A={lam_a:.2f}")
                lam_h = max(0.2, min(4.5, lam_h))
                lam_a = max(0.2, min(4.5, lam_a))
                poisson_result = predict_score_poisson(odds_h, odds_d, odds_a, h2h_avg_goals=None)
                poisson_result['lambda_home'] = round(lam_h, 2)
                poisson_result['lambda_away'] = round(lam_a, 2)
                poisson_result['feature_note'] = feature_note.strip()
                poisson_result['lam_warnings'] = _lam_warnings
                poisson_result['data_source'] = _lam_data_source
                poisson_result['sample_n_home'] = sample_n_home
                poisson_result['sample_n_away'] = sample_n_away
                if low_sample_warns:
                    poisson_result['low_sample_warns'] = low_sample_warns
                    poisson_result['sample_n'] = sample_n
                if _lam_res:
                    if _lam_res.get('market_prob'):
                        poisson_result['dc_market_prob'] = _lam_res['market_prob']
                        poisson_result['dc_rho'] = _lam_res.get('rho', 0.0)
                    if _lam_res.get('warn_codes'):
                        poisson_result['dc_warn_codes'] = _lam_res['warn_codes']
                # 统一告警入复盘记录 (按 code 分组统计各类异常占比)
                self.analysis_record.setdefault('steps', {}).setdefault('step2_1', {})
                self.analysis_record['steps']['step2_1']['poisson_warnings'] = _lam_warnings
                self.analysis_record['steps']['step2_1']['data_source'] = _lam_data_source
                # 概率后校准 + 用最终λ重算比分矩阵/大小球 (SOP Step8 v4)
                finalize_poisson_probs(poisson_result, lam_h, lam_a, data['league'], max_goals=6)
            else:
                poisson_result = predict_score_poisson(odds_h, odds_d, odds_a, h2h_avg_goals=h2h_avg)
                # 【情报修正λ】无"场均进X失Y"精确数据时, 用特征提取器+联赛基准修正赔率反推的λ
                # 解决: 纯赔率λ忽略用户情报(主场不败/防线残缺/首回合保守)导致高估进球
                if poisson_result and self.feature_extractor:
                    try:
                        lam_h = poisson_result['lambda_home']
                        lam_a = poisson_result['lambda_away']
                        # 拆分主客情报 (用统一方法, 处理"。。"双句号空段问题)
                        home_txt, away_txt = self._split_home_away_text(step2_1_text)
                        feats = self.feature_extractor.extract(home_txt, away_txt, step2_2_text)
                        self.analysis_record['steps']['step2_1']['features'] = feats

                        feature_note = ""
                        # 联赛可配置修正系数 (SOP Step8 v3: 各联赛 odds_zones.json correct_coef)
                        cc = get_league_correct_coef(data['league'])
                        feature_note = ""
                        # 首回合/资格赛保守 → 双方进球↓
                        if '首回合' in (home_txt + away_txt) or '资格赛' in data.get('league', '') or '保守' in (home_txt + away_txt):
                            lam_h *= cc['first_leg_conservative']
                            lam_a *= cc['first_leg_conservative']
                            feature_note += " 首回合/资格赛保守"
                        # 状态差 → 状态好的队λ放大
                        form_diff = feats.get('form_diff', 0)
                        if form_diff > 0.3:
                            lam_h *= cc['form_good']
                            feature_note += " 主队状态优"
                        elif form_diff < -0.3:
                            lam_a *= cc['form_good']
                            feature_note += " 客队状态优"
                        # 防线残缺 → 对手λ↑
                        if feats.get('home_defense_weak'):
                            lam_a *= cc['weak_defense']
                            feature_note += " 主队防线弱"
                        if feats.get('away_defense_weak'):
                            lam_h *= cc['weak_defense']
                            feature_note += " 客队防线弱"
                        # 锋线哑火 → 进攻λ↓
                        if feats.get('home_attack_disabled'):
                            lam_h *= cc['striker_miss']
                            feature_note += " 主队锋线哑火"
                        if feats.get('away_attack_disabled'):
                            lam_a *= cc['striker_miss']
                            feature_note += " 客队锋线哑火"
                        # 客场胜率低 → 客队λ↓ (文本含"客场"且"不胜/惨败/胜率")
                        if re.search(r'客场.{0,8}(胜率\s*低|1-5|惨败|不胜|弱)', away_txt):
                            lam_a *= cc['away_weak']
                            feature_note += " 客队客场弱"

                        # Agent风险信号修正 (Step7.5前置, 结构化信号, 含盘口交叉校验)
                        #    铁律: LLM只输出定性描述, 扰动幅度硬限幅 ±10%, 禁止 0.3-0.35 系数
                        rs = getattr(self, '_risk_signals', None)
                        lam_h_pre_agent = lam_h
                        lam_a_pre_agent = lam_a
                        if rs:
                            market_direction = 'home' if odds_h < odds_a else 'away'
                            agent_dir = rs.get('direction', 'unknown')
                            market_home = (odds_h < odds_a)
                            agent_home = (agent_dir == 'home')
                            agent_away = (agent_dir == 'away')
                            rs_weight = 1.0
                            if agent_dir in ('home', 'away') and agent_dir != 'unknown':
                                market_align = (market_home and agent_home) or (not market_home and agent_away)
                                if not market_align:
                                    rs_weight = 0.5
                                    print(f"    ⚠️ Agent方向[{agent_dir}]与盘口市场方向[{market_direction}]矛盾 → 信号降权50%")
                            # 汇总有符号扰动 (正=利好对应λ, 负=利空), 硬限幅 ±10% (SOP铁律)
                            sig_h = 0.0
                            sig_a = 0.0
                            if rs.get('home_attack_risk', 0) > 0.3:
                                sig_h -= rs['home_attack_risk'] * rs_weight
                                feature_note += f" Agent:主攻-{rs['home_attack_risk']:.0%}"
                            if rs.get('away_attack_risk', 0) > 0.3:
                                sig_a -= rs['away_attack_risk'] * rs_weight
                                feature_note += f" Agent:客攻-{rs['away_attack_risk']:.0%}"
                            if rs.get('home_defense_risk', 0) > 0.3:
                                sig_a += rs['home_defense_risk'] * rs_weight
                                feature_note += f" Agent:主防+{rs['home_defense_risk']:.0%}"
                            if rs.get('away_defense_risk', 0) > 0.3:
                                sig_h += rs['away_defense_risk'] * rs_weight
                                feature_note += f" Agent:客防+{rs['away_defense_risk']:.0%}"
                            if rs.get('deadlock_prob', 0) > 0.4:
                                sig_h -= rs['deadlock_prob'] * rs_weight
                                sig_a -= rs['deadlock_prob'] * rs_weight
                                feature_note += f" Agent:闷平-{rs['deadlock_prob']:.0%}"
                            if rs.get('home_adv_lost', 0) > 0.3:
                                sig_h -= rs['home_adv_lost'] * rs_weight
                                feature_note += f" Agent:主场失效-{rs['home_adv_lost']:.0%}"
                            # 硬限幅 ±10% (SOP Step8 v3 铁律: Agent扰动最大 ±10% λ)
                            sig_h = max(-0.10, min(0.10, sig_h))
                            sig_a = max(-0.10, min(0.10, sig_a))
                            lam_h = lam_h_pre_agent * (1 + sig_h)
                            lam_a = lam_a_pre_agent * (1 + sig_a)
                            if sig_h or sig_a:
                                feature_note += f" Agent扰动H{sig_h:+.0%}/A{sig_a:+.0%}(限±10%)"

                        # λ硬截断 [0.2,4.5] (SOP Step8 v3): 不再按总进球全局缩放, 避免抹平特征修正
                        if not (0.2 <= lam_h <= 4.5) or not (0.2 <= lam_a <= 4.5):
                            print(f"    ⚠️ λ超出[0.2,4.5]已截断: H={lam_h:.2f} A={lam_a:.2f}")
                        lam_h = max(0.2, min(4.5, lam_h))
                        lam_a = max(0.2, min(4.5, lam_a))

                        poisson_result['lambda_home'] = round(lam_h, 2)
                        poisson_result['lambda_away'] = round(lam_a, 2)
                        poisson_result['feature_note'] = feature_note.strip()

                        # 概率后校准 + 用最终λ重算比分矩阵/大小球 (SOP Step8 v4)
                        finalize_poisson_probs(poisson_result, lam_h, lam_a, data['league'], max_goals=6)
                    except Exception:
                        pass
        except Exception as e:
            import traceback
            print(f"  [泊松预测异常] {e}")
            traceback.print_exc()
            poisson_result = None

        # 让球+大小球推荐 (模型计算, 替代LLM)
        try:
            # 解析让球: 用统一函数处理, 修复"-0/0.5"方向错误
            hdp_str = data.get('hdp_home', '')
            hdp_val = parse_handicap(hdp_str)
            # hdp_val>0 表示主队受让(加球), <0 表示主队让球
            home_give = hdp_val < 0  # 主队是否让球
            # 原始盘口显示 (如 +0.5/1)
            hdp_display = hdp_str.split('@')[0].strip() if '@' in hdp_str else hdp_str.strip()
            
            # 泊松让球结算: 主队结算 = 主队净胜球 + 受让数
            if poisson_result:
                lam_h = poisson_result['lambda_home']
                lam_a = poisson_result['lambda_away']
                _rho_rec = 0.0
                try:
                    _pc_rec = get_league_prob_calib(str(data.get('league', '')))
                    _rho_rec = _pc_rec['rho'] if _pc_rec else 0.0
                except Exception:
                    pass
                sys.path.insert(0, 'src/models')
                from prob_calibration import dc_score_grid as _dcg_rec
                _grid_rec = _dcg_rec(lam_h, lam_a, rho=_rho_rec, max_goals=8)
                # 主队结算 = (主队进球 - 客队进球) + hdp_val, >0 主队赢盘
                # 含走水处理 (整盘/半球盘); 与 Step31 共用 ρ 修正网格, 口径一致
                hdp_full = sum(_grid_rec[i][j] for i in range(9) for j in range(9) if (i-j) + hdp_val > 0)
                hdp_half = sum(_grid_rec[i][j] for i in range(9) for j in range(9) if abs((i-j) + hdp_val) < 0.01)
                hdp_win_p = hdp_full + hdp_half * 0.5
                hdp_lose_p = 1 - hdp_win_p
                hdp_dir = "让胜" if hdp_win_p >= 0.5 else "让负"
            else:
                hdp_win_p = hdp_lose_p = 0.5
                hdp_dir = "观望"
            
            # 大小球
            if ml_result:
                over_p = over_line_prob
                under_p = under_line_prob
            else:
                over_p = under_p = 0.5
            
            # 综合推荐
            recommendation = f"【让球推荐】\n方向: {hdp_dir}\n"
            recommendation += f"主队{hdp_display}赢盘概率: {hdp_win_p:.1%} | 输盘: {hdp_lose_p:.1%}\n"
            recommendation += f"\n【大小球推荐】\n"
            recommendation += f"大{ou_line}概率: {over_p:.1%} | 小{ou_line}概率: {under_p:.1%}\n"
            if over_p >= 0.55:
                recommendation += f"方向: 大球 [{'%.1f'%ou_line}]"
            elif under_p >= 0.55:
                recommendation += f"方向: 小球 [{'%.1f'%ou_line}]"
            else:
                recommendation += f"方向: 观望 (概率接近50%)"
            recommendation += f"\n\n【核心依据】\n- 泊松λ: 主{poisson_result['lambda_home'] if poisson_result else 'N/A'} 客{poisson_result['lambda_away'] if poisson_result else 'N/A'}\n"
            recommendation += f"- ML预测总进球: {ml_result.predicted_total_goals:.2f}球\n"
            recommendation += f"- 让球盘: 主队{hdp_display} → 赢盘概率{hdp_win_p:.1%}"
            if poisson_result and poisson_result.get('feature_note'):
                recommendation += f"\n- 特征修正: {poisson_result['feature_note']}"
            llm_result = recommendation
        except Exception as e:
            llm_result = f"[模型推荐计算失败] {e}"
        print(f"  {llm_result}")

        # 组合结果
        final_result = llm_result
        
        # 添加ML预测结果
        if ml_result:
            ml_text = f"\n\n【ML大小球预测】\n"
            ml_text += f"预测总进球: {ml_result.predicted_total_goals:.2f}\n"
            ml_text += f"大2.5: {ml_result.over25_prob:.1%} | 小2.5: {ml_result.under25_prob:.1%}\n"
            ml_text += f"大3.5: {ml_result.over35_prob:.1%} | 小3.5: {ml_result.under35_prob:.1%}\n"
            ml_text += f"信心: {'⭐' * ml_result.confidence}\n"
            ml_text += f"模型类型: {ml_result.model_type}"
            final_result += ml_text
            print(ml_text)
        
        # 添加泊松预测结果
        if poisson_result:
            print(f"\n  [泊松比分预测]")
            print(f"  主队期望进球(λ): {poisson_result['lambda_home']}")
            print(f"  客队期望进球(λ): {poisson_result['lambda_away']}")
            print(f"  TOP5比分:")
            for s in poisson_result['top5_scores']:
                print(f"    {s['score']}: {s['prob']}%")
            print(f"  大1.5: {poisson_result['over_15']}% | 大2.5: {poisson_result['over_25']}% | 大3.5: {poisson_result['over_35']}%")
            print(f"  双方进球(BTTS): {poisson_result['btts']}%")
            if 'prob_home' in poisson_result:
                cal_note = poisson_result.get('prob_calib_note', '')
                print(f"  胜平负(校准后): 主{poisson_result['prob_home']:.1%} 平{poisson_result['prob_draw']:.1%} 客{poisson_result['prob_away']:.1%}"
                      + (f" [{cal_note}]" if cal_note else ""))

            poisson_text = f"\n\n【泊松比分预测】\n"
            poisson_text += f"主队λ={poisson_result['lambda_home']}, 客队λ={poisson_result['lambda_away']}\n"
            poisson_text += "TOP5: " + ", ".join([f"{s['score']}({s['prob']}%)" for s in poisson_result['top5_scores']])
            poisson_text += f"\n大2.5: {poisson_result['over_25']}% | BTTS: {poisson_result['btts']}%"
            final_result += poisson_text

        self.analysis_record['steps']['step8'] = {
            "result": llm_result,
            "ml_prediction": {
                "predicted_total_goals": ml_result.predicted_total_goals if ml_result else None,
                "over25_prob": ml_result.over25_prob if ml_result else None,
                "under25_prob": ml_result.under25_prob if ml_result else None,
                "confidence": ml_result.confidence if ml_result else None,
                "model_type": ml_result.model_type if ml_result else None,
            } if ml_result else None,
            "poisson": poisson_result
        }

        # 保存供Step 31复用
        self._step8_ml_result = ml_result
        self._step8_poisson_result = poisson_result
        self._step8_ou_line = ou_line
        self._step31_best_bet = None

    def _upset_assessment(self, data):
        """冷门识别v3 (纯数据触发, 无主观判断)

        P0: 平赔+去水公平概率判定热门 / 亚盘脏数据兜底 / 多源赔率分歧加码
        P1: 结构化攻防/伤停/样本特征入引擎; 杯赛专项开关
        P2: RiskSignal 前置限幅±10%; 基本面反向冲突降级标记
        """
        if not self.upset_engine:
            return
        try:
            print("\n" + "=" * 70)
            print("  冷门识别 v3 (数据触发)")
            print("=" * 70)
            parse_warnings = []

            # P0-2: 亚盘解析空值/脏数据兜底 (空/平半/乱码 → 0.0 平手 + 告警)
            hdp_str = data.get('hdp_home', '')
            try:
                hdp_val = parse_handicap(hdp_str)
                if hdp_val is None or not isinstance(hdp_val, (int, float))                         or hdp_val != hdp_val or hdp_val in (float('inf'), float('-inf')):
                    raise ValueError("非数值")
            except Exception:
                hdp_val = 0.0
                parse_warnings.append({"code": "HDP_PARSE_FAIL",
                                       "msg": "让球解析失败, 原始盘口: %r, 已平手兜底(冷门权重降低)" % str(hdp_str)})
                print("    [WARN] 让球解析失败, 已平手兜底: %r" % str(hdp_str))

            # P0-1: 平赔参与 + 独赢市场去水 → 公平概率
            fair_h = fair_d = fair_a = None
            try:
                _oh = float(data['odds_home'])
                _oa = float(data['odds_away'])
                _od = float(data.get('odds_draw') or 0)
                if _oh > 1 and _oa > 1 and _od > 1:
                    _over = 1.0 / _oh + 1.0 / _od + 1.0 / _oa
                    fair_h = (1.0 / _oh) / _over
                    fair_d = (1.0 / _od) / _over
                    fair_a = (1.0 / _oa) / _over
            except Exception:
                pass

            # 判断热门方 (去水公平概率优先; 平局为最大概率时不强行标热)
            home_txt, away_txt = self._split_home_away_text(data.get('user_form', ''))
            if fair_h is not None and fair_a is not None and fair_d is not None:
                _max_fair = max(fair_h, fair_d, fair_a)
                if fair_d == _max_fair:
                    hot_home = fair_h >= fair_a   # 平局为最大 → 不标热, 取较优方评估
                else:
                    hot_home = fair_h > fair_a
            else:
                try:
                    hot_home = float(data['odds_home']) <= float(data['odds_away'])
                except Exception:
                    hot_home = True
            hot_team = data['home'] if hot_home else data['away']
            cold_team = data['away'] if hot_home else data['home']
            hot_info = home_txt if hot_home else away_txt
            cold_info = away_txt if hot_home else home_txt
            hot_odds = float(data['odds_home']) if hot_home else float(data['odds_away'])

            # 大小球盘口
            line_note = str(data.get('ou_over', '')) + str(data.get('ou_under', ''))

            # P1-3: 判断联赛类型 (仅杯赛/资格赛启用欧足联专项)
            league = str(data.get('league', ''))
            if any(k in league for k in ['欧联', 'Europa', '欧洲联赛']):
                league_type = 'uel'
            elif any(k in league for k in ['欧冠', '冠军联赛', 'UCL']):
                league_type = 'ucl'
            elif any(k in league for k in ['欧协联', 'Conference', '欧会']):
                league_type = 'uefa'
            elif '资格赛' in league:
                league_type = 'uefa'
            else:
                league_type = ''
            cup_mode = league_type in ('ucl', 'uel', 'uefa')

            # P0-3: 多源赔率分歧度
            try:
                odds_disparity = float(data.get('odds_disparity', 0.0) or 0.0)
            except (TypeError, ValueError):
                odds_disparity = 0.0

            # P1-2: 结构化量化特征 (伤停/疲劳/样本量/攻防差)
            feature_pack = {}
            step8 = getattr(self, '_step8_poisson_result', None) or {}
            _lam_h = step8.get('lambda_home')
            _lam_a = step8.get('lambda_away')
            if _lam_h is not None and _lam_a is not None:
                feature_pack['lam_base_diff'] = float(_lam_h) - float(_lam_a)
            cc_up = get_league_correct_coef(data.get('league', ''))
            feature_pack['home_injury_weight'] = float(cc_up.get('injury_coef_h', 1.0))
            feature_pack['away_injury_weight'] = float(cc_up.get('injury_coef_a', 1.0))
            feature_pack['fatigue_level'] = float(cc_up.get('fatigue_coef', 1.0))
            feature_pack['sample_n_home'] = int(step8.get('sample_n_home') or 0)
            feature_pack['sample_n_away'] = int(step8.get('sample_n_away') or 0)
            feature_pack['hot_side'] = 'home' if hot_home else 'away'

            result = self.upset_engine.assess(
                hot_team, hot_info, cold_info,
                data.get('user_h2h', ''), hdp_val, hot_odds,
                line_note=line_note, league_type=league_type,
                fair_h=fair_h, fair_a=fair_a, fair_d=fair_d,
                odds_disparity=odds_disparity, cup_mode=cup_mode,
                feature_pack=feature_pack, hot_is_home=hot_home,
            )

            # P2-3: RiskSignal 前置硬限幅 ±10% (引擎已限幅, 此处双保险)
            risk_signal = max(-0.10, min(0.10, float(result.get('risk_signal', 0.0) or 0.0)))
            result['risk_signal'] = round(risk_signal, 4)

            # P2-1: 基本面 vs 冷门信号反向冲突 → 风控降级标记 (Step31 自动降星)
            if _lam_h is not None and _lam_a is not None and risk_signal != 0.0:
                try:
                    _conf = check_upset_risk_conflict(_lam_h, _lam_a, risk_signal)
                    if _conf.get('conflict'):
                        self._risk_conflict = _conf
                        parse_warnings.append({"code": "RISK_CONFLICT", "msg": _conf["msg"]})
                        print("    [WARN] " + _conf["msg"])
                except Exception:
                    pass

            self.analysis_record['upset_assessment'] = result
            self.analysis_record['upset_warnings'] = parse_warnings

            league_label = {'ucl': '欧冠专项', 'uel': '欧联专项', 'uefa': '欧足联专项'}.get(league_type, '常规')
            print(f"  热门方: {result['hot_team']} (赔率{hot_odds:.2f})")
            print(f"  联赛类型: {league_label} | 杯赛模式: {cup_mode}")
            if result.get('fair_probs') and result['fair_probs'].get('home') is not None:
                _fp_ = result['fair_probs']
                print(f"  去水公平概率: 主{_fp_['home']:.2f} 平{_fp_['draw']:.2f} 客{_fp_['away']:.2f} | 赔率分歧: {result.get('odds_disparity', 0):.2f}")
            print(f"  命中条件: {result['triggered_count']}个")
            for _key, _label in (('hot_items', '强队隐患'), ('cold_items', '弱队优势'), ('line_items', '盘赔信号'),
                                 ('fair_items', '去水盘赔信号'), ('feature_items', '结构化特征'),
                                 ('env_items', '场地加分'), ('h2h_items', '交锋信号'),
                                 ('ucl_items', '欧冠专项'), ('uel_items', '欧联专项')):
                if result.get(_key):
                    print(f"  {_label}: {'、'.join(result[_key])}")
            if result['exclusions']:
                print(f"  [WARN] 排除误区: {'、'.join(result['exclusions'])}")
            print(f"  ★ 冷门等级: {result['level']} → {result['recommendation']}")
            if risk_signal:
                print(f"  RiskSignal: {risk_signal:+.0%} (限幅±10%, 方向看衰热门方)")
        except Exception as e:
            import traceback
            print(f"  [冷门引擎失败] {e}")
            traceback.print_exc()

    def _agent_tactical_analysis(self, data):
        """足球Agent战术分析 (LLM定性 + 模型定量数据)"""
        if not self.agent:
            return
        try:
            print("\n" + "=" * 70)
            print("  足球Agent战术分析")
            print("=" * 70)
            # 从step8取模型结果 (含λ/比分/场均进球/转化率)
            model_result = {}
            step8 = self.analysis_record.get('steps', {}).get('step8', {})
            if step8.get('poisson'):
                model_result['lambda'] = {
                    'home': step8['poisson'].get('lambda_home'),
                    'away': step8['poisson'].get('lambda_away'),
                }
                model_result['top5_scores'] = step8['poisson'].get('top5_scores')
                ov25 = step8['poisson'].get('over_25')
                if ov25 is not None:
                    model_result['over25_prob'] = ov25 / 100.0
            # 从step2_1提取场均进球/转化率
            step2_1 = self.analysis_record.get('steps', {}).get('step2_1', {}).get('result', '')
            feats = self.analysis_record.get('steps', {}).get('step2_1', {}).get('features', {})
            if feats:
                model_result['home_avg_goals'] = feats.get('home_gf')
                model_result['home_avg_ga'] = feats.get('home_ga')
                model_result['away_avg_goals'] = feats.get('away_gf')
                model_result['away_avg_ga'] = feats.get('away_ga')
                # 射正转化率: 从文本正则提取
                import re as _re
                conv = _re.findall(r'射正转化率\s*(\d+\.?\d*)\s*%', step2_1)
                if len(conv) >= 2:
                    model_result['home_conv'] = float(conv[0])
                    model_result['away_conv'] = float(conv[1])
            # 取最优投注
            result_text = step8.get('result', '')
            model_result['best_bet'] = result_text[:200]

            report = self.agent.analyze(data, model_result)
            self.analysis_record['agent_tactical'] = report.get('tactical', {})
            print(self.agent.format_report(report))
        except Exception as e:
            print(f"  [Agent分析失败] {e}")

    def _step8_5_v2_engine(self, data):
        """Step 8.5: 新引擎(prediction_v2)交叉验证.

        9大联赛用数据集特征(无泄漏), 小联赛用用户情报+联赛真值;
        投注纪律来自 prediction_v2 回测: 仅"大小球2.5 小球"(边际>=5%, 赔率>=2.00)为正期望,
        1X2/亚盘/大球回测为负 -> 一律标记不推荐.
        """
        print("\n" + "=" * 70)
        print("  Step 8.5: 新引擎(prediction_v2)交叉验证")
        print("=" * 70)
        try:
            sys.path.insert(0, 'src/features')
            from predict_v2_bridge import PredictV2Bridge
            if self._v2_bridge is None:
                self._v2_bridge = PredictV2Bridge()
            res = self._v2_bridge.predict_from_record(data, self.analysis_record)
            self._v2_result = res
            self.analysis_record['steps']['step8_5_v2_engine'] = res
            # 推荐自动入账(逐注账本, 供赛后结算对账)
            try:
                from predict_v2_bridge import record_recommended_bet
                record_recommended_bet(res, data)
            except Exception:
                pass

            print(f"  引擎: {res['engine']} | 联赛: {res['league']} | λ主={res['lam_h']} λ客={res['lam_a']}")
            print(f"  胜平负: {res['p_home']:.1%}/{res['p_draw']:.1%}/{res['p_away']:.1%} | "
                  f"大{res['ou_line']}: {res['p_over']:.1%} / 小{res['ou_line']}: {1 - res['p_over']:.1%}")
            print("  候选(模型概率 vs 市场去水概率):")
            for b in res.get('bets', []):
                mark = "  <-- 推荐" if b.get('recommended') else ""
                print(f"    {b['market']:>4} {b['side']:<14} "
                      f"模型{b['prob']:.1%} 市场{b['market_prob']:.1%} "
                      f"边际{b['edge']:+.1%} 赔率{b['odds']:.2f} EV={b['ev']:+.1%}{mark}")
            print(f"  >>> {res.get('recommendation', '')}")
            print("  Step 8.5 完成 ✅")
        except Exception as e:
            import traceback
            print(f"  [Step8.5 v2引擎异常] {e}")
            self._v2_result = None

    def _step31_ev_calc(self, data):
        print("\n" + "=" * 70)
        print("  Step 31: EV计算 + 打星")
        print("=" * 70)

        ml_result = getattr(self, '_step8_ml_result', None)
        poisson_result = getattr(self, '_step8_poisson_result', None)
        ou_line = getattr(self, '_step8_ou_line', 2.5)

        try:
            # 解析让球: 用统一函数处理
            hdp_str = data.get('hdp_home', '')
            hdp_val = parse_handicap(hdp_str)
            # 原始盘口显示 (如 +0.5/1)
            hdp_display = hdp_str.split('@')[0].strip() if '@' in hdp_str else hdp_str.strip()
            hdp_away_display = str(data.get('hdp_away', '')).split('@')[0].strip() if '@' in str(data.get('hdp_away', '')) else str(data.get('hdp_away', ''))

            # 解析大小球赔率 (大/小)
            ou_over_odds = 1.90
            ou_under_odds = 1.90
            try:
                ou_over_str = data.get('ou_over', '')
                ou_under_str = data.get('ou_under', '')
                if '@' in ou_over_str:
                    ou_over_odds = float(ou_over_str.split('@')[1].strip())
                if '@' in ou_under_str:
                    ou_under_odds = float(ou_under_str.split('@')[1].strip())
            except Exception:
                pass

            # 解析让球赔率 (主队受让 / 客队让球)
            hdp_home_odds = 1.90
            hdp_away_odds = 1.90
            try:
                hdp_home_str = data.get('hdp_home', '')
                hdp_away_str = data.get('hdp_away', '')
                if '@' in hdp_home_str:
                    hdp_home_odds = float(hdp_home_str.split('@')[1].strip())
                if '@' in hdp_away_str:
                    hdp_away_odds = float(hdp_away_str.split('@')[1].strip())
            except Exception:
                pass

            # 泊松比分矩阵
            if poisson_result:
                lam_h = poisson_result['lambda_home']
                lam_a = poisson_result['lambda_away']
            elif ml_result:
                # 用ML预测反推λ
                total = ml_result.predicted_total_goals
                lam_h = total * 0.3
                lam_a = total * 0.7
            else:
                lam_h = lam_a = 1.5

            _rho_step31 = 0.0
            try:
                _pc31 = get_league_prob_calib(str(data.get('league', '')))
                _rho_step31 = _pc31['rho'] if _pc31 else 0.0
            except Exception:
                pass
            sys.path.insert(0, 'src/models')
            from prob_calibration import dc_score_grid as _dc_grid
            _grid31 = _dc_grid(lam_h, lam_a, rho=_rho_step31, max_goals=8)
            def prob_cond(cond):
                return sum(_grid31[i][j] for i in range(9) for j in range(9) if cond(i, j))

            # 候选投注: 主队受让赢盘 / 客队让球赢盘 / 小球 / 大球
            hdp_is_int = abs(abs(hdp_val) - round(abs(hdp_val))) < 0.01
            if hdp_is_int:
                # 整盘让球: 净胜=盘口 → 走水(退款)
                hdp_push_p = prob_cond(lambda i, j: abs(abs((i-j) + hdp_val) - 0) < 0.01)
                home_hdp_p = prob_cond(lambda i, j: (i-j) + hdp_val > 0) + hdp_push_p * 0.5
            else:
                home_hdp_p = prob_cond(lambda i, j: (i-j) + hdp_val > 0)   # 主队+2.5赢盘
            away_hdp_p = 1 - home_hdp_p                                # 客队-2.5赢盘

            # 大小球整盘: 总进球 = 盘口 → 走水(退款), 算50%权重
            is_int_line = abs(ou_line - round(ou_line)) < 0.01
            if is_int_line:
                push_p = prob_cond(lambda i, j: abs(i+j - ou_line) < 0.01)
                under_p = prob_cond(lambda i, j: i+j < ou_line) + push_p * 0.5
                over_p = prob_cond(lambda i, j: i+j > ou_line) + push_p * 0.5
            else:
                under_p = prob_cond(lambda i, j: i+j < ou_line)
                over_p = 1 - under_p

            # 分市场去水 (SOP Step31 v2): 让球盘/大小球盘抽水率不同, 禁止统一计算
            hdp_orr = 1.0
            ou_orr = 1.0
            try:
                if hdp_home_odds > 1.0 and hdp_away_odds > 1.0:
                    hdp_orr = 1.0 / hdp_home_odds + 1.0 / hdp_away_odds
                if ou_over_odds > 1.0 and ou_under_odds > 1.0:
                    ou_orr = 1.0 / ou_over_odds + 1.0 / ou_under_odds
            except Exception:
                pass
            bets = [
                (f"主队{hdp_display}", home_hdp_p, hdp_home_odds, hdp_orr),
                (f"客队{hdp_away_display}", away_hdp_p, hdp_away_odds, hdp_orr),
                (f"小{ou_line}", under_p, ou_under_odds, ou_orr),
                (f"大{ou_line}", over_p, ou_over_odds, ou_orr),
            ]

            # EV计算 (去水后公平EV = 模型概率/Overround × 原始赔率 - 1)
            results = []
            for name, prob, odds, orr in bets:
                ev = ((prob / orr) * odds - 1) if orr > 1.0 else (prob * odds - 1)
                stars = 0
                if ev >= 0.30: stars = 5
                elif ev >= 0.20: stars = 4
                elif ev >= 0.10: stars = 3
                elif ev >= 0.0: stars = 2
                star_str = "⭐" * stars if stars > 0 else "❌放弃"
                results.append({"name": name, "prob": round(prob, 4), "odds": odds, "ev": round(ev, 4), "stars": star_str})

            # 打星限制: 每场最多1个5星, 最多2个4星
            # 注意: 5星降级后要重新统计4星, 防止超限
            star5 = [r for r in results if r['stars'] == '⭐⭐⭐⭐⭐']
            # 5星只保留1个, 其余降4星
            for r in star5[1:]:
                r['stars'] = '⭐⭐⭐⭐'
            # 重新统计4星(含5星降级下来的), 最多2个
            star4 = [r for r in results if r['stars'] == '⭐⭐⭐⭐']
            for r in star4[2:]:
                r['stars'] = '⭐⭐⭐'
            # 低样本场次 (<4场, 攻防改用联赛基准): 全腿降1星 (SOP Step2.1 v3 风控)
            low_sample_warns = (poisson_result or {}).get('low_sample_warns') or []
            low_sample_note = ""
            if low_sample_warns:
                for r in results:
                    cur = r['stars'].count('⭐') if r['stars'] != '❌放弃' else 0
                    cur = max(0, cur - 1)
                    r['stars'] = ("⭐" * cur) if cur > 0 else "❌放弃"
                low_sample_note = "\n  ⚠️ 低样本告警: %s → 全腿降1星" % low_sample_warns[0]

            # 基本面 vs 风险信号强冲突 → 全腿降1星 (SOP审计项3 风控降级)
            risk_conflict = getattr(self, '_risk_conflict', None)
            risk_conflict_note = ""
            if risk_conflict and risk_conflict.get('level') == 'strong':
                for r in results:
                    _cur = r['stars'].count('⭐') if r['stars'] != '❌放弃' else 0
                    _cur = max(0, _cur - 1)
                    r['stars'] = ("⭐" * _cur) if _cur > 0 else "❌放弃"
                risk_conflict_note = "\n  ⚠️ 基本面与风险信号强冲突(风控降级) → 全腿降1星"

            # 最优投注判定 v2: EV噪声阈值(0~8%仅观察) + 胜率优先
            # p1: 串关必须全中才赢 → 胜率优先于EV
            # p2: EV≥8%(去水后)且赔率≥1.60前提下, 选胜率最高的选项
            # 注意: 不能只看星级, 星级按EV划分, 但串关核心是胜率
            EV_NOISE_MIN = 0.08
            valid = [r for r in results if r['ev'] >= EV_NOISE_MIN and r['odds'] >= 1.60]
            if valid:
                best = max(valid, key=lambda r: r['prob'])
                best['is_best'] = True
                best_note = (f"\n  ★★★ 最高胜率腿(best_bet): {best['name']} "
                             f"胜率{best['prob']:.1%} 赔率{best['odds']:.2f} EV={best['ev']:+.1%} ★★★"
                             f"\n  规则: 串关胜率优先, 在EV≥8%(去水后)且赔率≥1.60前提下选胜率最高腿")
            else:
                best = None
                best_note = ("\n  ℹ️ 无满足 EV≥8%(去水后) 且赔率≥1.60 的腿 → 本场不出best_bet, 全部仅观察")

            # K2欧赔区间校验 (2026实测真值): 标注区间规律, 提示深盘/冷门平局风险
            league = str(data.get('league', ''))
            if any(k in league for k in ['K2', 'K联赛2', '韩国K2', 'K League 2']):
                try:
                    oh = float(data.get('odds_home', 0))
                    zone_note = ''
                    if 1.25 <= oh <= 1.40:
                        zone_note = "K2区间1(超低赔): 主胜62%但深盘穿盘仅37%, 受让方+1.5更有价值"
                    elif 1.41 <= oh <= 1.75:
                        zone_note = "K2区间2(低赔): 主胜48%但平局30%, 强队主场难稳定赢盘"
                    elif 1.76 <= oh <= 2.25:
                        zone_note = "K2区间3(中庸): 胜平负均分, 平局价值最高"
                    elif 2.26 <= oh <= 2.80:
                        zone_note = "K2区间4(偏高): 客队更强但平局35%, 冷门平局高发"
                    elif oh > 2.80:
                        zone_note = "K2区间5(高赔): 客胜50%但平局32%, 客队不败+防平"
                    if zone_note:
                        best_note += f"\n  ⚠️ {zone_note}"
                except Exception:
                    pass

            self._step31_best_bet = best

            # ---- 新引擎(v2)对齐: 回测纪律, 实盘以v2推荐为准 ----
            final_best = None
            v2_note = ""
            v2 = getattr(self, '_v2_result', None)
            if not v2:
                v2 = self.analysis_record.get('steps', {}).get('step8_5_v2_engine') or {}
            v2_best = v2.get('best_bet') if isinstance(v2, dict) else None
            if v2_best and v2_best.get('recommended'):
                side = str(v2_best.get('side', ''))
                name = ("小" + side.replace('under', '')) if side.startswith('under') else side
                final_best = {
                    "name": name,
                    "prob": v2_best.get('prob'),
                    "odds": v2_best.get('odds'),
                    "ev": v2_best.get('ev'),
                    "edge": v2_best.get('edge'),
                    "engine": "v2",
                    "rule": "prediction_v2回测: 仅大小球2.5小球(边际>=5%,赔率>=2.00)为正期望; 1X2/亚盘/大球回测为负"
                }
                v2_note = (f"\n  ⚠️ 新引擎(v2)交叉验证: 推荐 {name} 边际{v2_best.get('edge', 0):+.1%} "
                           f"赔率{v2_best.get('odds', 0):.2f} EV={v2_best.get('ev', 0):+.1%} —— 实盘以v2为准(回测验证)")
                if best is not None and best['name'] != name:
                    v2_note += f"\n     旧引擎best_bet={best['name']} 与新引擎不一致 → 按新方案纪律改用v2推荐"
                self._step31_best_bet = final_best
            elif best is not None:
                final_best = {
                    "name": best['name'],
                    "prob": best['prob'],
                    "odds": best['odds'],
                    "ev": best['ev'],
                    "engine": "legacy",
                    "rule": "旧引擎: EV≥8%(去水后)且赔率≥1.60前提下选胜率最高腿; v2无满足条件推荐(仅小球2.5边际>=5%)"
                }
                v2_note = "\n  ℹ️ 新引擎(v2)无满足条件推荐(仅小球2.5 边际>=5%且赔率>=2.00), 维持旧引擎best_bet"
            else:
                final_best = {
                    "name": None, "prob": None, "odds": None, "ev": None,
                    "engine": "none",
                    "rule": "无满足EV≥8%(去水后)且赔率≥1.60的腿, 本场不出best_bet"
                }
                v2_note = "\n  ℹ️ 本场无满足EV≥8%的腿, 不产生best_bet"

            # 输出
            print("  " + "-" * 60)
            print("  候选投注(按胜率/EV排序):")
            for r in sorted(results, key=lambda x: -x['prob']):
                mark = " ← 最高胜率腿" if r.get('is_best') else ""
                print(f"  {r['name']:<18} 概率{r['prob']:.1%} 赔率{r['odds']:.2f} EV={r['ev']:+.1%} {r['stars']}{mark}")
            print(best_note)
            print(v2_note)
            if risk_conflict_note:
                print(risk_conflict_note)
            if low_sample_note:
                print(low_sample_note)

            self.analysis_record['steps']['step31_ev_calc'] = {
                "poisson_lambda": {"home": lam_h, "away": lam_a},
                "low_sample_warns": low_sample_warns,
                "risk_conflict": (getattr(self, '_risk_conflict', None)
                                  if getattr(self, '_risk_conflict', None) else None),
                "bets": results,
                "best_bet": (None if best is None else {
                    "name": best['name'],
                    "prob": best['prob'],
                    "odds": best['odds'],
                    "ev": best['ev'],
                    "rule": "串关胜率优先: EV≥8%(去水后)且赔率≥1.60前提下选胜率最高腿"
                }),
                "final_best_bet": final_best,
                "v2_engine": {
                    "engine": (v2 or {}).get('engine'),
                    "recommendation": (v2 or {}).get('recommendation'),
                    "best_bet": (v2 or {}).get('best_bet'),
                },
                "strategy_note": "基于真实攻防数据泊松计算EV，使用用户提供的实际盘口赔率，EV<0放弃。串关选场必须用best_bet(最高胜率腿)。新引擎(prediction_v2)回测: 仅小球2.5边际>=5%为正期望, 实盘以其推荐为准"
            }
        except Exception as e:
            import traceback
            print(f"  [Step31异常] {e}")
            traceback.print_exc()
            self.analysis_record['steps']['step31_ev_calc'] = {"error": str(e)}

    def _step3_live_handicap_check(self, data):
        """Step 3: 比赛中 - 盘口变化检查"""
        print("\n" + "=" * 70)
        print("  Step 3: 比赛中盘口变化检查")
        print("=" * 70)

        prompt = f"""基于以下比赛信息，分析当前盘口:

{self.context}

请简洁回答:
1. 盘口变化原因
2. 当前盘口是否合理"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step3'] = {"result": result}

    def _step4_live_settlement(self, data):
        """Step 4: 比赛中 - R201实时结算"""
        print("\n" + "=" * 70)
        print("  Step 4: R201实时结算")
        print("=" * 70)

        # 解析当前比分
        try:
            score_parts = data['current_score'].split('-')
            home_goals = int(score_parts[0].strip())
            away_goals = int(score_parts[1].strip())
        except:
            print("  [错误] 无法解析比分格式，应为 X-X")
            return

        # 解析让球数
        hdp_str = data['hdp_home']
        try:
            # 提取数字部分，处理 -0.5/1 这种格式
            if '/' in hdp_str:
                parts = hdp_str.split('/')
                num1 = float(parts[0].replace('@', '').strip())
                num2 = float(parts[1].split('@')[0].strip())
                hdp_value = (num1 + num2) / 2
            else:
                hdp_value = float(hdp_str.split('@')[0].strip())
        except:
            print(f"  [错误] 无法解析让球盘口: {hdp_str}")
            return

        # 计算R201
        home_net = home_goals - away_goals  # 主队净胜球
        home_settlement = home_net - hdp_value  # 主队让球结算
        away_settlement = -home_net + hdp_value  # 客队让球结算

        print(f"  当前比分: {data['current_score']}")
        print(f"  主队让球: {hdp_value}")
        print(f"  主队净胜球: {home_net}")
        print(f"  主队结算: {home_net} - {hdp_value} = {home_settlement:.2f}")
        print(f"  客队结算: {-home_net} + {hdp_value} = {away_settlement:.2f}")

        if home_settlement > 0:
            print(f"  当前状态: 主队让胜")
        elif home_settlement < 0:
            print(f"  当前状态: 主队让负")
        else:
            print(f"  当前状态: 走水")

        self.analysis_record['steps']['step4'] = {
            "current_score": data['current_score'],
            "hdp_value": hdp_value,
            "home_net": home_net,
            "home_settlement": home_settlement,
            "away_settlement": away_settlement
        }

    def _step5_live_recommendation(self, data):
        """Step 5: 比赛中 - 实时推荐"""
        print("\n" + "=" * 70)
        print("  Step 5: 比赛中实时推荐")
        print("=" * 70)

        prompt = f"""基于以下比赛实时信息，给出推荐:

{self.context}

请简洁回答:
1. 推荐方向: 让胜/让平/让负
2. 置信度"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step5'] = {"result": result}

    def _step5_mode_switch_live(self, data):
        """Step 5: 比赛中 - R90模式切换"""
        print("\n" + "=" * 70)
        print("  Step 5: R90模式切换")
        print("=" * 70)

        prompt = f"""基于以下比赛信息，判断是友谊赛还是正赛:

{self.context}

请简洁回答:
1. 模式: 正赛/友谊赛
2. 理由"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step5_mode'] = {"result": result}

    def _step6_odds_deviation_live(self, data):
        """Step 6: 比赛中 - R119赔率偏差"""
        print("\n" + "=" * 70)
        print("  Step 6: R119赔率偏差分析")
        print("=" * 70)

        prompt = f"""基于以下比赛和赔率信息，分析赔率偏差:

{self.context}

请简洁回答:
1. 赔率结构是否合理
2. R119判定 (偏差>=3%->+1级，>=5%->+2级)"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step6'] = {"result": result}

    def _step7_dual_verification_live(self, data):
        """Step 7: 比赛中 - R105双重验证"""
        print("\n" + "=" * 70)
        print("  Step 7: R105双重验证")
        print("=" * 70)

        prompt = f"""基于以下完整分析信息，对推荐进行双面验证:

{self.context}

请简洁回答:
1. 正方信号 (利好)
2. 反方信号 (利空)
3. 净值判断
4. 结论"""

        result = self.deepseek_query(prompt, compress_context=True)
        print(f"  {result}")
        self.analysis_record['steps']['step7'] = {"result": result}

    def _step8_risk_control_live(self, data):
        """Step 8: 比赛中 - R117/R118风控"""
        print("\n" + "=" * 70)
        print("  Step 8: R117/R118风控检查")
        print("=" * 70)

        prompt = f"""基于以下完整分析信息，进行风控检查:

{self.context}

请简洁回答:
1. R117: 让平集中度检查
2. R118: 碾压判定
3. 风险提示"""

        result = self.deepseek_query(prompt, compress_context=True)
        print(f"  {result}")
        self.analysis_record['steps']['step8'] = {"result": result}

    def _step9_final_decision_live(self, data):
        """Step 9: 比赛中 - 最终综合判断"""
        print("\n" + "=" * 70)
        print("  Step 9: 最终综合判断")
        print("=" * 70)

        # ML大小球预测
        ml_result = None
        try:
            # 解析大小球盘口
            ou_line = 2.5
            if '@' in str(data['ou_over']):
                ou_parts = data['ou_over'].split('@')
                ou_str = ou_parts[0].strip()
                # 处理 2/2.5 或 3/3.5 这种复合盘口
                if '/' in ou_str:
                    ou_parts2 = ou_str.split('/')
                    ou_line = (float(ou_parts2[0]) + float(ou_parts2[1])) / 2
                else:
                    ou_line = float(ou_str)
            
            # 使用ML模型预测 (league_avg_goals用真实联赛场均)
            league_avg = get_league_avg_goals(data['league'])
            ml_result = self.ml_model.predict(
                odds_home=float(data['odds_home']),
                odds_draw=float(data['odds_draw']),
                odds_away=float(data['odds_away']),
                league_avg_goals=league_avg,
                league=data['league'],
            )
            
            # 计算实际盘口的大/小球概率 (修复: 用对应盘口概率)
            over_line_prob = ml_result.over_prob_for_line(ou_line)
            under_line_prob = ml_result.under_prob_for_line(ou_line)
            
            print(f"\n  [ML大小球预测]")
            print(f"  预测总进球: {ml_result.predicted_total_goals:.2f}")
            print(f"  大{ou_line}概率: {over_line_prob:.1%}")
            print(f"  小{ou_line}概率: {under_line_prob:.1%}")
            print(f"  信心: {'⭐' * ml_result.confidence}")
            
        except Exception as e:
            print(f"  [ML预测异常] {e}")

        prompt = f"""综合以下所有分析，给出最终推荐:

{self.context}

请简洁回答:
1. 让球方向: 让胜/让平/让负
2. 让球赔率
3. 大小球方向: 大球/小球
4. 大小球赔率
5. 置信度 (1-5星)
6. 核心依据 (3条)"""

        result = self.deepseek_query(prompt, compress_context=True)
        print(f"  {result}")
        
        # 组合结果
        final_result = result
        
        # 添加ML预测结果
        if ml_result:
            ml_text = f"\n\n【ML大小球预测】\n"
            ml_text += f"预测总进球: {ml_result.predicted_total_goals:.2f}\n"
            ml_text += f"大2.5: {ml_result.over25_prob:.1%} | 小2.5: {ml_result.under25_prob:.1%}\n"
            ml_text += f"大3.5: {ml_result.over35_prob:.1%} | 小3.5: {ml_result.under35_prob:.1%}\n"
            ml_text += f"信心: {'⭐' * ml_result.confidence}\n"
            ml_text += f"模型类型: {ml_result.model_type}"
            final_result += ml_text
            print(ml_text)

        self.analysis_record['steps']['step9'] = {
            "result": result,
            "ml_prediction": {
                "predicted_total_goals": ml_result.predicted_total_goals if ml_result else None,
                "over25_prob": ml_result.over25_prob if ml_result else None,
                "under25_prob": ml_result.under25_prob if ml_result else None,
                "confidence": ml_result.confidence if ml_result else None,
            } if ml_result else None,
        }
        
        # 输出最终推荐汇总
        print("\n" + "=" * 70)
        print("  最终推荐汇总")
        print("=" * 70)
        print(f"  {final_result}")
        print("=" * 70)

    def _step3_result_review(self, data):
        """Step 3: 已结束 - 结果复盘"""
        print("\n" + "=" * 70)
        print("  Step 3: 结果复盘")
        print("=" * 70)

        # 解析最终比分
        try:
            score_parts = data['current_score'].split('-')
            home_goals = int(score_parts[0].strip())
            away_goals = int(score_parts[1].strip())
        except:
            print("  [错误] 无法解析比分格式，应为 X-X")
            return

        # 解析让球数
        hdp_str = data['hdp_home']
        try:
            if '/' in hdp_str:
                parts = hdp_str.split('/')
                num1 = float(parts[0].replace('@', '').strip())
                num2 = float(parts[1].split('@')[0].strip())
                hdp_value = (num1 + num2) / 2
            else:
                hdp_value = float(hdp_str.split('@')[0].strip())
        except:
            print(f"  [错误] 无法解析让球盘口: {hdp_str}")
            return

        # 计算最终结算
        home_net = home_goals - away_goals
        home_settlement = home_net - hdp_value

        print(f"  最终比分: {data['current_score']}")
        print(f"  主队让球: {hdp_value}")
        print(f"  主队净胜球: {home_net}")
        print(f"  主队结算: {home_net} - {hdp_value} = {home_settlement:.2f}")

        if home_settlement > 0:
            result_text = "主队让胜"
        elif home_settlement < 0:
            result_text = "主队让负"
        else:
            result_text = "走水"

        print(f"  最终结果: {result_text}")

        self.analysis_record['steps']['step3'] = {
            "final_score": data['current_score'],
            "hdp_value": hdp_value,
            "home_net": home_net,
            "home_settlement": home_settlement,
            "result": result_text
        }

    def _step4_review_analysis(self, data):
        """Step 4: 复盘 - 赛前分析验证"""
        print("\n" + "=" * 70)
        print("  Step 4: 赛前分析验证")
        print("=" * 70)

        # 解析最终比分
        try:
            score_parts = data['current_score'].split('-')
            home_goals = int(score_parts[0].strip())
            away_goals = int(score_parts[1].strip())
        except:
            return

        # 解析让球数
        hdp_str = data['hdp_home']
        try:
            if '/' in hdp_str:
                parts = hdp_str.split('/')
                num1 = float(parts[0].replace('@', '').strip())
                num2 = float(parts[1].split('@')[0].strip())
                hdp_value = (num1 + num2) / 2
            else:
                hdp_value = float(hdp_str.split('@')[0].strip())
        except:
            return

        home_net = home_goals - away_goals
        home_settlement = home_net - hdp_value

        prompt = f"""复盘比赛: {data['home']} vs {data['away']}
最终比分: {data['current_score']}
让球盘口: {hdp_value}
结算结果: {home_settlement:.2f}

基于最终结果，分析:
1. 赛前分析哪些判断正确
2. 赛前分析哪些判断错误
3. 主要原因分析"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step4'] = {"result": result}

    def _step5_review_lessons(self, data):
        """Step 5: 复盘 - 经验教训"""
        print("\n" + "=" * 70)
        print("  Step 5: 经验教训")
        print("=" * 70)

        prompt = f"""复盘比赛: {data['home']} vs {data['away']}
最终比分: {data['current_score']}

总结经验教训:
1. 本次分析的主要收获
2. 需要改进的地方
3. 对未来分析的建议"""

        result = self.deepseek_query(prompt)
        print(f"  {result}")
        self.analysis_record['steps']['step5'] = {"result": result}

    def build_best_bets_map(self, matches):
        """
        从Step31结果构建 {场次: best_bet} 映射, 供投注校验用.
        matches: [{"match": "湖北 vs 江西", "step31": {...}或best_bet_dict}, ...]
        """
        bb_map = {}
        for m in matches:
            match = m.get('match', '')
            bb = m.get('final_best_bet') or m.get('best_bet')
            if not bb and isinstance(m.get('steps'), dict):
                s31 = m['steps'].get('step31_ev_calc') or {}
                bb = s31.get('final_best_bet') or s31.get('best_bet')
            if bb:
                bb_map[match] = bb
        return bb_map

    def verify_bet_legs(self, legs, matches=None):
        """
        投注前校验: 每条腿必须等于该场best_bet(最高胜率腿).
        返回: (ok, errors, warnings)
        """
        if not self.bet_validator:
            return True, [], ["投注校验器未加载, 跳过校验"]
        bb_map = self.build_best_bets_map(matches or [])
        if not bb_map:
            return True, [], ["没有best_bet数据, 跳过校验"]
        return self.bet_validator.verify_bet_legs(legs, bb_map)

    def _save_record(self):
        """保存分析记录 (文件名用英文队名, 便于代码对账)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rec = self.analysis_record
        # 优先用英文队名生成文件名, 无英文则用中文
        home_name = rec.get('home_en') or rec.get('home', '')
        away_name = rec.get('away_en') or rec.get('away', '')
        if not home_name or not away_name:
            home_name, away_name = rec.get('match', 'vs').split(' vs ') if ' vs ' in rec.get('match', '') else (home_name, away_name)
        # 清理文件名非法字符 (含空格)
        import re
        home_safe = re.sub(r'[\\/:*?"<>|\s]', '_', home_name)
        away_safe = re.sub(r'[\\/:*?"<>|\s]', '_', away_name)
        match_name = f"{home_safe}_{away_safe}"
        filename = f"{RECORDS_DIR}/{timestamp}_{match_name}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)

        print(f"\n{'=' * 70}")
        print(f"  记录已保存: {filename}")
        print(f"{'=' * 70}")

    def _check_and_record_strategy(self, match_data):
        """检查并记录策略数据"""
        odds_home = float(match_data['odds_home'])

        # 解析让球数 (复用统一parse_handicap, 避免重复逻辑出错)
        hdp_str = match_data['hdp_home']
        try:
            hdp_value = parse_handicap(hdp_str)
        except Exception:
            hdp_value = 0

        # 准备结果数据
        result_data = {
            'final_score': match_data.get('current_score', 'N/A'),
            'total_goals': 0,
            'hdp_result': '待定',
            'ou_result': '待定',
            'prediction': self.analysis_record.get('steps', {}).get('step8', {}).get('result', 'N/A'),
            'confidence': '待定'
        }

        # 自动补全英文队名 (代码对账用)
        match_data['home_en'] = to_en_name(match_data.get('home', match_data.get('home_en', '')))
        match_data['away_en'] = to_en_name(match_data.get('away', match_data.get('away_en', '')))

        # 如果有比分，计算进球数
        if '-' in str(result_data['final_score']):
            try:
                score_parts = str(result_data['final_score']).split('-')
                total = int(score_parts[0]) + int(score_parts[1])
                result_data['total_goals'] = total
            except:
                pass

        # 获取真实数据（从analysis_record中）
        real_data = self.analysis_record.get('real_data', None)

        # 保存数据（所有比赛都保存）
        self.data_collector.add_match(match_data, result_data, real_data)
        
        # 检查是否满足策略条件
        odds_met = odds_home <= STRATEGY_CONDITIONS['rules']['odds_home_max']
        hdp_met = hdp_value <= STRATEGY_CONDITIONS['rules']['handicap_min']

        if odds_met and hdp_met:
            print(f"\n  [策略触发] 满足条件: 主胜{odds_home} < 1.20, 让球{hdp_value} < -2")
            print(f"  [策略建议] 追大球")
        
        print(f"\n  [数据已保存] {match_data['home']} vs {match_data['away']}")


def main():
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            match = json.load(f)
    else:
        # 测试数据 - 比赛中
        match = {
            'home': '科萨',
            'away': '绿盾',
            'league': '所罗门群岛超级联赛',
            'status': 'in_play',
            'current_score': '0-2',
            'minute': '45+',
            'odds_home': '11.00',
            'odds_draw': '5.70',
            'odds_away': '1.06',
            'hdp_home': '+0/0.5 @1.76',
            'hdp_away': '-0/0.5 @2.02',
            'ou_over': '3.5 @1.83',
            'ou_under': '3.5 @1.95',
        }

    predictor = FootballPredictor()
    predictor.analyze(match)


if __name__ == "__main__":
    main()
