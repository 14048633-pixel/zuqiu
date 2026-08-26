"""prediction_v2 ↔ 原系统桥接
=================================================
把新引擎（无手调系数 / 无泄漏 / 回测验证）接入原系统 Step 8(模型计算) 与 Step 31(EV打星)：

- 9 大联赛（英超/西甲/意甲/德甲/法甲/英冠/西乙/德乙/荷甲）
    → 用 prediction_v2 数据集特征（真实历史、严格只用开赛前数据）
- 小联赛（K2/中乙/J1/丹麦杯等）
    → 用原系统特征提取器从用户情报算攻防强度，套用同一 λ 公式
- 投注规则（依据 prediction_v2 回测）：
    * 默认只推「大小球2.5 小球」：模型-市场边际 >= 5% 且赔率 >= 2.00
    * 1X2 / 亚盘 / 大球：回测为负 → 标记"不推荐"

用法（原系统内部）：
    from predict_v2_bridge import PredictV2Bridge
    br = PredictV2Bridge()
    result = br.predict_from_record(match_data, analysis_record)
"""
import json
import importlib
import os
import sys
import types
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 足球竞猜模型训练/
V2_DIR = os.path.normpath(os.path.join(BASE, "prediction_v2"))
if os.path.join(BASE, "src", "features") not in sys.path:
    sys.path.insert(0, os.path.join(BASE, "src", "features"))


def _load_v2_api():
    """以独立包名加载 prediction_v2/src，避免与旧系统 src 包冲突。"""
    pkg_name = "_v2engine"
    if f"{pkg_name}.predict_api" in sys.modules:
        return sys.modules[f"{pkg_name}.predict_api"]
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [os.path.join(V2_DIR, "src")]
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg
    importlib.import_module(f"{pkg_name}.predict_api")
    return sys.modules[f"{pkg_name}.predict_api"]


_V2_API = None


def _api():
    global _V2_API
    if _V2_API is None:
        _V2_API = _load_v2_api()
    return _V2_API

EURO_LEAGUES = {"英超", "西甲", "意甲", "德甲", "法甲", "英冠", "西乙", "德乙", "荷甲"}

# 推荐规则（与 prediction_v2 回测口径一致）
OU_LINE = 2.5
EDGE_OU_UNDER = 0.05
MIN_ODDS = 2.00

# 逐注账本: v2 推荐自动入账, 赛后按比分结算对账(验证闭环)
LEDGER_PATH = os.environ.get("V2_LEDGER") or os.path.join(V2_DIR, "output", "live_bets.jsonl")

# 小联赛基准（主/客场均进球），优先读 strategy_data 真值文件
BASELINE_FILES = {
    "k2": ("strategy_data/k2_league_baseline.json", "base", ["home_goals", "away_goals"]),
    "j1": ("strategy_data/j1_odds_zones.json", "baseline", ["home_goals", "away_goals"]),
    "cl2": ("strategy_data/cl2_odds_zones.json", "baseline", ["avg_goals"]),
}
LEAGUE_NAME_KEYS = {
    "k2": ["韩国K2联赛", "K2联赛", "韩K2", "K联赛2", "K League 2", "K2"],
    "j1": ["J1", "J1联赛", "日本J1", "日职", "J联赛"],
    "cl2": ["中乙", "中乙联赛", "中国乙级"],
}
FALLBACK_BASELINE = {"home": 1.40, "away": 1.20}


def resolve_league_baseline(league: str, explicit: tuple = None):
    """返回 (home_avg, away_avg)。"""
    if explicit and explicit[0] and explicit[1]:
        return float(explicit[0]), float(explicit[1])
    for key, (fname, section, fields) in BASELINE_FILES.items():
        if not any(k in league for k in LEAGUE_NAME_KEYS[key]):
            continue
        path = os.path.join(BASE, fname)
        if not os.path.exists(path):
            break
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            base = data.get(section, {})
            if "home_goals" in base and "away_goals" in base:
                return float(base["home_goals"]), float(base["away_goals"])
            if "avg_goals" in base:
                avg = float(base["avg_goals"])
                return round(avg / 2 * 1.15, 3), round(avg / 2 * 0.85, 3)
        except Exception:
            break
    return FALLBACK_BASELINE["home"], FALLBACK_BASELINE["away"]


def feature_row_from_intel(league, home_form="", away_form="", h2h="",
                           league_avg=None):
    """从用户情报构建特征行（与 prediction_v2 λ 公式一致，无手调系数）。"""
    from feature_extractor import MatchFeatureExtractor
    fe = MatchFeatureExtractor()
    feats = fe.extract(home_form or "", away_form or "", h2h or "")
    lg_h, lg_a = resolve_league_baseline(league, league_avg)
    home_gf = feats.get("home_gf") or lg_h
    home_ga = feats.get("home_ga") or lg_a
    away_gf = feats.get("away_gf") or lg_a
    away_ga = feats.get("away_ga") or lg_h
    return {
        "league_avg_home": lg_h, "league_avg_away": lg_a,
        "att_home": max(home_gf / lg_h, 0.3),
        "def_home": max(home_ga / lg_a, 0.3),
        "att_away": max(away_gf / lg_a, 0.3),
        "def_away": max(away_ga / lg_h, 0.3),
    }


def record_recommended_bet(res: dict, match_data: dict) -> dict:
    """把 v2 推荐写入逐注账本(供赛后结算对账), 重复分析同一场不重复入账。"""
    best = res.get("best_bet") or {}
    if not best.get("recommended"):
        return None
    match_key = f"{match_data.get('home', '')} vs {match_data.get('away', '')}"
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "match": match_key,
        "league": res.get("league"),
        "engine": res.get("engine"),
        "market": best.get("market"),
        "side": best.get("side"),
        "line": res.get("ou_line"),
        "edge": best.get("edge"),
        "odds": best.get("odds"),
        "ev": best.get("ev"),
        "prob": best.get("prob"),
        "status": "pending",
    }
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    existing = []
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    existing.append(json.loads(ln))
    for e in existing:
        if (e.get("match") == match_key and e.get("league") == entry["league"]
                and e.get("side") == entry["side"] and e.get("status") == "pending"):
            return e
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def _settle_one(entry: dict, score: str) -> dict:
    """结算单注: score 形如 "2-1"。返回带 status 的条目。"""
    try:
        gh, ga = (int(x) for x in str(score).split("-")[:2])
    except Exception:
        return entry
    total = gh + ga
    line = float(entry.get("line", 2.5))
    side = str(entry.get("side", ""))
    if "under" in side:
        result = "win" if total < line else "push" if total == line else "lose"
    elif "over" in side:
        result = "win" if total > line else "push" if total == line else "lose"
    else:
        result = "skip"
    entry["status"] = result
    entry["score"] = str(score)
    entry["total_goals"] = total
    return entry


def settle_bets(score_map: dict, ledger_path: str = None) -> list:
    """按比分结算账本: score_map = {match_str: "2-1"}。

    小球2.5: 总进球<2.5 赢, =2.5 走水(整数盘), >2.5 输。
    结算后写回账本, 返回本次结算的条目列表。
    """
    path = ledger_path or LEDGER_PATH
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = [ln for ln in (l.strip() for l in f) if ln]
    entries = [json.loads(ln) for ln in lines]
    touched = 0
    for e in entries:
        if e.get("status") == "pending" and e.get("match") in score_map:
            _settle_one(e, str(score_map[e["match"]]))
            touched += 1
    if touched:
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return [e for e in entries if e.get("status") in ("win", "lose", "push")]


class PredictV2Bridge:
    """供 auto_sop Step 8/31 调用的新引擎入口。"""

    def __init__(self, cfg_path=None):
        import yaml
        self.cfg_path = cfg_path or os.path.join(V2_DIR, "config.yaml")
        with open(self.cfg_path, encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

    # ---------------- 对外主入口 ----------------
    def predict_from_record(self, match_data: dict, analysis_record: dict) -> dict:
        league = str(match_data.get("league", ""))
        home = match_data.get("home_en") or match_data.get("home", "")
        away = match_data.get("away_en") or match_data.get("away", "")
        date = str(match_data.get("date") or datetime.now().strftime("%Y-%m-%d"))[:10]

        odds = self._parse_odds(match_data)
        ou = self._parse_ou(match_data)  # (line, over_odds, under_odds) 或 None
        ah = self._parse_ah(match_data)

        if league in EURO_LEAGUES:
            try:
                row = _api().feature_row_from_dataset(league, home, away, date, self.cfg)
                engine = "dataset"
            except Exception:
                row = self._intel_row(match_data, analysis_record, league)
                engine = "intel"
        else:
            row = self._intel_row(match_data, analysis_record, league)
            engine = "intel"

        ou_line = ou[0] if ou else OU_LINE
        res = _api().score_feature_row(row, odds=odds, ou_line=ou_line,
                                       ou=(ou[1], ou[2]) if ou else None,
                                       ah=ah, cfg=self.cfg)
        res["engine"] = engine
        res["league"] = league
        res["league_avg"] = (float(row["league_avg_home"]), float(row["league_avg_away"]))
        self._apply_rules(res)
        return res

    # ---------------- 规则 ----------------
    def _apply_rules(self, res: dict):
        """依据回测给每个候选打标：只推 OU 小球(边际>=5%, 赔率>=2.00)。"""
        best = None
        line_is_25 = abs(float(res.get("ou_line", OU_LINE)) - OU_LINE) < 1e-9
        for b in res.get("bets", []):
            b["recommended"] = False
            b["note"] = "回测为负或不满足条件, 不推荐"
            if b["market"] == "ou" and "under" in b["side"]:
                if not line_is_25:
                    b["note"] = f"回测仅验证小球2.5线, 本场盘口为{res.get('ou_line')}, 无回测支撑, 不推荐"
                elif b["edge"] >= EDGE_OU_UNDER and b["odds"] >= MIN_ODDS:
                    b["recommended"] = True
                    b["note"] = "回测正期望(小球2.5 边际>=5%): 可投, 1/4凯利, 单注<=5%本金"
                    stars = 5 if b["edge"] >= 0.10 else 4 if b["edge"] >= 0.075 else 3
                    b["stars"] = "⭐" * stars
                    if best is None or b["edge"] > best["edge"]:
                        best = b
            else:
                b["note"] = "回测为负(1X2/亚盘/大球), 不推荐"
        res["best_bet"] = best
        res["recommendation"] = (
            f"新方案推荐: 小球{res.get('ou_line')} 边际{best['edge']:+.1%} 赔率{best['odds']:.2f} "
            f"EV={best['ev']:+.1%} {best.get('stars','')}"
            if best else "新方案: 无满足条件(仅小球2.5 边际>=5%)的推荐, 建议观望"
        )

    # ---------------- 解析 ----------------
    def _parse_odds(self, d):
        try:
            oh, od, oa = float(d["odds_home"]), float(d["odds_draw"]), float(d["odds_away"])
            if min(oh, od, oa) > 1.0:
                return oh, od, oa
        except Exception:
            return None
        return None

    def _parse_ou(self, d):
        """返回 (line, over_odds, under_odds) 或 None; 支持 2/2.5=2.25 复合盘。"""
        def odds_of(v):
            try:
                return float(str(v).split("@")[1].strip())
            except Exception:
                return None
        o = odds_of(d.get("ou_over", "")); u = odds_of(d.get("ou_under", ""))
        if not (o and u):
            return None
        line_str = str(d.get("ou_over", "")).split("@")[0].strip()
        try:
            if "/" in line_str:
                p1, p2 = line_str.split("/")[:2]
                line = (float(p1) + float(p2)) / 2
            else:
                line = float(line_str)
        except Exception:
            line = OU_LINE
        return line, o, u

    def _parse_ah(self, d):
        def odds_of(v):
            try:
                return float(str(v).split("@")[1].strip())
            except Exception:
                return None
        hdp = str(d.get("hdp_home", "")).split("@")[0].strip()
        try:
            line = self._parse_handicap(hdp)
            h, a = odds_of(d.get("hdp_home", "")), odds_of(d.get("hdp_away", ""))
            if h and a:
                return line, h, a
        except Exception:
            return None
        return None

    @staticmethod
    def _parse_handicap(hdp_str):
        """与 auto_sop.parse_handicap 相同口径。"""
        hdp_str = str(hdp_str).strip()
        if not hdp_str or "平手" in hdp_str:
            return 0.0
        if "/" in hdp_str:
            p1 = hdp_str.split("/")[0].split("@")[0].strip()
            p2 = hdp_str.split("/")[1].split("@")[0].strip()
            sign = -1 if p1.startswith("-") else 1
            v1 = float(p1.replace("+", "").replace("-", ""))
            v2 = float(p2.replace("+", "").replace("-", ""))
            return sign * (v1 + v2) / 2
        return float(hdp_str.split("@")[0].strip())

    def _intel_row(self, match_data, analysis_record, league):
        step2_1 = analysis_record.get("steps", {}).get("step2_1", {}).get("result", "") or ""
        step2_2 = analysis_record.get("steps", {}).get("step2_2", {}).get("result", "") or ""
        user_form = match_data.get("user_form", "") or ""
        text = user_form or step2_1
        home_txt, away_txt = self._split_home_away(text)
        return feature_row_from_intel(league, home_txt, away_txt, step2_2)

    @staticmethod
    def _split_home_away(text):
        """按句号分离主客情报块（与 auto_sop._split_home_away_text 同口径）。"""
        segs = [s for s in text.split("。") if s.strip()]
        if len(segs) < 2:
            return text, ""
        data_kw = ["胜", "平", "负", "进球", "失球", "场均", "射门", "射正", "不败", "总进", "总失"]
        data_segs = [s for s in segs if any(k in s for k in data_kw)]
        if len(data_segs) >= 2:
            return data_segs[0], data_segs[1]
        if data_segs:
            return data_segs[0], ""
        return segs[0], segs[1] if len(segs) > 1 else ""
# test-write
