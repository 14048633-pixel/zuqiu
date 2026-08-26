"""
InferSports API 对接
实时赔率 + 公平概率 + 模型价值对比
"""
import requests
from typing import Optional

API_BASE = "https://api.infersports.dev"
TIMEOUT = 15


def _ok(v):
    return v is not None and v > 0


def get_fair_odds(query: str, market: str = "1x2", date: Optional[str] = None) -> dict:
    """获取 InferSports 去抽水公平概率"""
    body = {"query": query, "market_type": market, "format": "probability",
            "period": "full_time", "verbosity": "terse"}
    if date:
        body["date"] = date
    r = requests.post(f"{API_BASE}/v1/mcp/get_sharp_line", json=body,
                      headers={"Accept": "application/json"}, timeout=TIMEOUT)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}", "detail": r.text[:200]}
    data = r.json()
    if data.get("status") == "ambiguous":
        return {"error": "ambiguous", "suggestions": data.get("summary", "")}
    fair = data.get("fair_odds") or data.get("fair_line") or {}
    return {
        "fair_odds": {
            "home": fair.get("home") if _ok(fair.get("home")) else fair.get("1", 0),
            "draw": fair.get("draw") if _ok(fair.get("draw")) else fair.get("X", 0),
            "away": fair.get("away") if _ok(fair.get("away")) else fair.get("2", 0),
        },
        "event_id": data.get("event_id"),
        "home_team": data.get("home_team"),
        "away_team": data.get("away_team"),
    }


def compare_prob(query: str, model_prob: float, outcome: str = "home",
                 market: str = "1x2", date: Optional[str] = None) -> dict:
    """对比模型概率 vs InferSports 公平概率"""
    body = {
        "query": query, "external_prob": model_prob,
        "market_type": market, "outcome": outcome, "period": "full_time",
    }
    if date:
        body["date"] = date
    r = requests.post(f"{API_BASE}/v1/mcp/compare_prob", json=body,
                      headers={"Accept": "application/json"}, timeout=TIMEOUT)
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}
    return r.json()


def scan_today(sport: str = "football", market: str = "1x2",
               min_edge: float = 2, limit: int = 20,
               status: str = "scheduled") -> list:
    """扫描今日比赛的价值投注机会"""
    body = {
        "sport": sport, "only_signal": True, "limit": limit,
        "min_edge_pct": min_edge, "status": status,
    }
    if market:
        body["markets"] = [market]
    r = requests.post(f"{API_BASE}/v1/mcp/scan_slate", json=body,
                      headers={"Accept": "application/json"}, timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    data = r.json()
    return data.get("entries", [])


def match_detail(event_id: str) -> dict:
    """获取比赛详情"""
    r = requests.get(f"{API_BASE}/v1/events/{event_id}",
                     headers={"Accept": "application/json"}, timeout=TIMEOUT)
    if r.status_code != 200:
        return {}
    return r.json()


def get_value_bets(model_predictions: list) -> list:
    """
    对比模型概率 vs InferSports 公平概率, 找出价值投注.
    每场比赛只调 1 次 API, 三个结果本地算 edge.
    """
    if not model_predictions:
        return []

    results = []
    for p in model_predictions:
        home = p.get("home_team", "")
        away = p.get("away_team", "")
        if not home or not away:
            continue
        query = f"{home} vs {away}"

        try:
            fair = get_fair_odds(query)
            if "error" in fair:
                continue
            fo = fair.get("fair_odds", {})
            fair_home = fo.get("home", 0)
            fair_draw = fo.get("draw", 0)
            fair_away = fo.get("away", 0)
            if not fair_home and not fair_draw and not fair_away:
                continue
        except Exception:
            continue

        for outcome, label, prob_key, fair_prob in [
            ("home", "主胜", "prob_home", fair_home),
            ("draw", "平局", "prob_draw", fair_draw),
            ("away", "客胜", "prob_away", fair_away),
        ]:
            prob = p.get(prob_key, 0)
            if prob < 0.05 or not fair_prob:
                continue
            edge_pp = (prob - fair_prob) * 100
            if edge_pp > 2:
                results.append({
                    "home": home, "away": away, "bet": label,
                    "model_prob": round(prob, 3),
                    "fair_prob": round(fair_prob, 3),
                    "edge_pct": round(edge_pp, 1),
                })
    return results
