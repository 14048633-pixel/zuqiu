import os
"""
低级别联赛分析器 v2 — 时间衰减 + 贝叶斯收缩 + 主客拆分
"""
import urllib.request, urllib.error, json, urllib.parse
from math import exp, log, sqrt
from collections import defaultdict
from datetime import datetime, timezone

API_BASE = "https://api.infersports.dev/v1"
_HEADERS = {"User-Agent": "infersports-skill/1.0"}
TIMEOUT = 10

# ---- API-Football (fallback data source) ----
APIF_KEY = os.environ.get("FOOTBALL_API_KEY", "")
APIF_BASE = "https://v3.football.api-sports.io"
APIF_HEADERS = {"x-apisports-key": APIF_KEY}
_APIF_TEAM_CACHE = {}

LEAGUE_AVG_GOALS = 1.20
PRIOR_WEIGHT = 5
DECAY_HALFLIFE_DAYS = 30


def _get(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers=_HEADERS)
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    return json.loads(resp.read().decode("utf-8"))


def _post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{API_BASE}{path}", data=data,
                                 headers={**_HEADERS, "Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    return json.loads(resp.read().decode("utf-8"))


# ---- API-Football helpers ----

import time as _time

_APIF_LAST_CALL = 0.0
_APIF_MIN_INTERVAL = 1.2  # seconds between calls (free tier ~10/min)


def _apif_get(path):
    global _APIF_LAST_CALL
    elapsed = _time.time() - _APIF_LAST_CALL
    if elapsed < _APIF_MIN_INTERVAL:
        _time.sleep(_APIF_MIN_INTERVAL - elapsed)
    url = f"{APIF_BASE}{path}"
    req = urllib.request.Request(url, headers=APIF_HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        _APIF_LAST_CALL = _time.time()
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _time.sleep(6)
            resp = urllib.request.urlopen(req, timeout=5)
            _APIF_LAST_CALL = _time.time()
            return json.loads(resp.read().decode("utf-8"))
        raise
    except Exception:
        raise


def _search_apif_team(team_name):
    """Search team by name, return team_id or None. Caches results.
    Tries multiple search terms if initial search fails (e.g. 'Sogdiana Jizak' -> 'Sogdiana')."""
    normalized = team_name.lower().strip()
    if normalized in _APIF_TEAM_CACHE:
        return _APIF_TEAM_CACHE[normalized]
    try:
        for attempt in _search_terms(team_name):
            qs = urllib.parse.urlencode({"search": attempt})
            data = _apif_get(f"/teams?{qs}")
            for item in data.get("response", []):
                t = item.get("team", {})
                _APIF_TEAM_CACHE[t["name"].lower()] = t["id"]
            if data.get("results", 0) > 0:
                first = data["response"][0]["team"]
                tid = first["id"]
                _APIF_TEAM_CACHE[normalized] = tid
                return tid
    except Exception:
        pass
    return None


_NAME_ALIASES = {
    "fargona": "Fergana", "buxoro": "Bukhara",
    "xorazm": "Xorazm", "jizak": "Jizzax",
    "elimai": "Elimai",
    "general lamadrid(r)": "General Lamadrid",
    "victoriano arenas(r)": "Victoriano Arenas",
}


def _search_terms(name):
    """Generate search terms from a team name, from most to least specific."""
    terms = [name]
    # Try known aliases
    lower = name.lower().strip()
    if lower in _NAME_ALIASES:
        terms.append(_NAME_ALIASES[lower])
    parts = name.strip().split()
    if len(parts) > 1:
        terms.append(parts[0])
        terms.append(" ".join(parts[:2]))
    common_suffixes = ["FC", "United", "II", "U20", "W", "(W)", "(R)"]
    for sfx in common_suffixes:
        for p in [name, parts[0] if parts else ""]:
            cleaned = p.replace(sfx, "").strip()
            if cleaned and cleaned != p:
                terms.append(cleaned)
                # Also try alias of cleaned
                cl = cleaned.lower()
                if cl in _NAME_ALIASES:
                    terms.append(_NAME_ALIASES[cl])
    seen = set()
    return [t for t in terms if not (t.lower().strip() in seen or seen.add(t.lower().strip()))]


def _fetch_apif_fixtures(team_id, max_games=15):
    """
    Fetch recent finished fixtures for a team_id.
    1st pass: date-based query (last 120 days, works for 2026 free plan)
    2nd pass: if < 3 results, fallback to season=2024 (historical data)
    """
    results = []
    from datetime import date, timedelta
    import time
    today = date.today()

    # Pass 1: date-based (last 120 days in 30-day windows = 4 calls)
    for days_back in [0, 30, 60, 90]:
        start = (today - timedelta(days=days_back + 30)).isoformat()
        end = (today - timedelta(days=days_back)).isoformat()
        url = f"/fixtures?team={team_id}&from={start}&to={end}&status=FT"
        try:
            data = _apif_get(url)
            for f in data.get("response", []):
                goals = f.get("goals", {})
                fixture = f.get("fixture", {})
                teams = f.get("teams", {})
                results.append({
                    "home_team": teams.get("home", {}).get("name", ""),
                    "away_team": teams.get("away", {}).get("name", ""),
                    "score": {
                        "home": goals.get("home"),
                        "away": goals.get("away"),
                    },
                    "scheduled_at": fixture.get("date", ""),
                    "source": "api_football",
                })
                if len(results) >= max_games:
                    return results
            time.sleep(0.3)
        except Exception:
            pass

    # Pass 2: if not enough recent games, try 2024 season (free plan)
    if len(results) < 3:
        for season in ["2024", "2023"]:
            try:
                url = f"/fixtures?team={team_id}&season={season}&status=FT"
                data = _apif_get(url)
                for f in data.get("response", []):
                    goals = f.get("goals", {})
                    fixture = f.get("fixture", {})
                    teams = f.get("teams", {})
                    results.append({
                        "home_team": teams.get("home", {}).get("name", ""),
                        "away_team": teams.get("away", {}).get("name", ""),
                        "score": {
                            "home": goals.get("home"),
                            "away": goals.get("away"),
                        },
                        "scheduled_at": fixture.get("date", ""),
                        "source": "api_football_historical",
                    })
                    if len(results) >= max_games:
                        return results
                time.sleep(0.3)
            except Exception:
                pass

    return results


def fetch_recent_results_enhanced(team_name, limit=15, use_infersports=True):
    """Primary: InferSports. Fallback: API-Football if < 3 results."""
    results = []
    if use_infersports:
        results = fetch_recent_results(team_name, limit)

    if len(results) >= max(3, limit // 2):
        return results

    tid = _search_apif_team(team_name)
    if tid:
        existing = {(r.get("home_team", ""), r.get("away_team", ""),
                     r.get("score", {}).get("home"), r.get("score", {}).get("away"))
                    for r in results}
        apif_results = _fetch_apif_fixtures(tid, max_games=limit)
        for r in apif_results:
            key = (r["home_team"], r["away_team"], r["score"].get("home"), r["score"].get("away"))
            if key not in existing:
                results.append(r)
                existing.add(key)
    return results


# ---- Time decay ----

def _days_ago(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 30


def _decay_weight(days, halflife=DECAY_HALFLIFE_DAYS):
    return 0.5 ** (days / halflife)


# ---- Bayesian team stats with time decay ----

def _decay_for_source(source, days):
    """Different decay rates: recent matches decay fast, historical data decays slowly."""
    if source == "api_football_historical":
        return 0.5 ** (days / 365)
    return 0.5 ** (days / DECAY_HALFLIFE_DAYS)


def compute_stats_weighted(team_name, results, venue=None):
    """
    venue=None: all matches
    venue='home': only matches where team is home
    venue='away': only matches where team is away
    Returns dict with both raw and shrunken stats.
    """
    w_gf = w_ga = w_total = 0.0
    w_wins = w_draws = w_losses = 0.0
    w_cs = 0.0
    n = 0

    now = datetime.now(timezone.utc)
    for r in results:
        ht = r.get("home_team", "")
        at = r.get("away_team", "")
        sc = r.get("score", {})
        hs = sc.get("home")
        aws = sc.get("away")
        if hs is None or aws is None:
            continue

        is_home = ht.lower() == team_name.lower()
        if venue == 'home' and not is_home:
            continue
        if venue == 'away' and is_home:
            continue

        days = _days_ago(r.get("scheduled_at", ""))
        source = r.get("source", "infersports")
        w = _decay_for_source(source, days)

        if is_home:
            w_gf += hs * w
            w_ga += aws * w
            w_wins += w if hs > aws else 0
            w_draws += w if hs == aws else 0
            w_losses += w if hs < aws else 0
            w_cs += w if aws == 0 else 0
        else:
            w_gf += aws * w
            w_ga += hs * w
            w_wins += w if aws > hs else 0
            w_draws += w if aws == hs else 0
            w_losses += w if aws < hs else 0
            w_cs += w if hs == 0 else 0
        w_total += w
        n += 1

    if n == 0:
        return None

    # Time-weighted averages
    raw_gf = w_gf / w_total if w_total > 0 else 0
    raw_ga = w_ga / w_total if w_total > 0 else 0

    # Bayesian shrinkage toward league average
    shrink_n = w_total + PRIOR_WEIGHT
    gf_shrunken = (w_gf + PRIOR_WEIGHT * LEAGUE_AVG_GOALS) / shrink_n
    ga_shrunken = (w_ga + PRIOR_WEIGHT * LEAGUE_AVG_GOALS) / shrink_n

    return {
        "matches_raw": n,
        "effective_n": round(w_total, 2),
        "avg_goals_for": round(gf_shrunken, 3),
        "avg_goals_against": round(ga_shrunken, 3),
        "avg_goals_for_raw": round(raw_gf, 3),
        "avg_goals_against_raw": round(raw_ga, 3),
        "win_rate": round(w_wins / w_total if w_total > 0 else 0, 3),
        "draw_rate": round(w_draws / w_total if w_total > 0 else 0, 3),
        "loss_rate": round(w_losses / w_total if w_total > 0 else 0, 3),
        "clean_sheet_rate": round(w_cs / w_total if w_total > 0 else 0, 3),
        "ppg": round((w_wins * 3 + w_draws) / w_total if w_total > 0 else 0, 3),
        "total_goals_for": round(w_gf, 1),
        "total_goals_against": round(w_ga, 1),
    }


# ---- Poisson ----

def poisson_prob(lam, k):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return exp(-lam) * (lam ** k) / factorial(k)


def factorial(n):
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


def match_probs(lambda_h, lambda_a, max_goals=8, rho=0.0):
    """Dixon-Coles style low-score correction via rho"""
    probs = defaultdict(float)
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = poisson_prob(lambda_h, i) * poisson_prob(lambda_a, j)
            if rho != 0 and i <= 1 and j <= 1:
                tau = 1 + rho * (1 - lambda_h) * (1 - lambda_a)
                p *= tau
            probs["home"] += p if i > j else 0
            probs["draw"] += p if i == j else 0
            probs["away"] += p if i < j else 0
    total = probs["home"] + probs["draw"] + probs["away"]
    if total > 0:
        for k in probs:
            probs[k] /= total
    return dict(probs)


def top_scores(lambda_h, lambda_a, n=6, rho=0.0):
    scores = []
    for i in range(6):
        for j in range(6):
            p = poisson_prob(lambda_h, i) * poisson_prob(lambda_a, j)
            if rho != 0 and i <= 1 and j <= 1:
                tau = 1 + rho * (1 - lambda_h) * (1 - lambda_a)
                p *= tau
            scores.append(((i, j), p))
    scores.sort(key=lambda x: -x[1])
    return [{"score": f"{s[0][0]}-{s[0][1]}", "prob": round(s[1], 4)} for s in scores[:n]]


# ---- Prediction engine v2 ----

def predict_from_stats_v2(home_stats, away_stats):
    """
    v2 prediction using home/away-specific stats with attack/defense decomposition.
    Uses shrunken (Bayesian) averages for more robust estimates.
    """
    if not home_stats or not away_stats:
        return None

    home_attack = home_stats["avg_goals_for"]
    home_defense = home_stats["avg_goals_against"]
    away_attack = away_stats["avg_goals_for"]
    away_defense = away_stats["avg_goals_against"]

    lambda_h = home_attack * (away_defense / LEAGUE_AVG_GOALS) if LEAGUE_AVG_GOALS > 0 else home_attack
    lambda_a = away_attack * (home_defense / LEAGUE_AVG_GOALS) if LEAGUE_AVG_GOALS > 0 else away_attack

    lambda_h = max(lambda_h, 0.2)
    lambda_a = max(lambda_a, 0.2)

    rho = -0.04
    probs = match_probs(lambda_h, lambda_a, rho=rho)
    scores = top_scores(lambda_h, lambda_a, 6, rho=rho)

    return {
        "expected_goals_home": round(lambda_h, 3),
        "expected_goals_away": round(lambda_a, 3),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "top_scores": scores,
        "home_attack_rating": round(home_attack / LEAGUE_AVG_GOALS, 3),
        "home_defense_rating": round(home_defense / LEAGUE_AVG_GOALS, 3),
        "away_attack_rating": round(away_attack / LEAGUE_AVG_GOALS, 3),
        "away_defense_rating": round(away_defense / LEAGUE_AVG_GOALS, 3),
    }


# ---- Market odds ----

def fetch_market_odds(home_team, away_team):
    try:
        data = _post("/v1/mcp/get_sharp_line", {
            "query": f"{home_team} vs {away_team}",
            "market_type": "1x2",
            "format": "probability",
            "period": "full_time",
            "verbosity": "terse",
        })
        if data.get("status") == "ok":
            fair = data.get("fair_odds") or data.get("fair_line") or {}
            return {
                "fair_home": fair.get("home") or fair.get("1", 0),
                "fair_draw": fair.get("draw") or fair.get("X", 0),
                "fair_away": fair.get("away") or fair.get("2", 0),
                "source": data.get("source", ""),
            }
    except Exception:
        pass
    return None


# ---- Full analysis v2 ----

def analyze_match(home_team, away_team, recent_limit=15):
    home_results = fetch_recent_results_enhanced(home_team, recent_limit)
    away_results = fetch_recent_results_enhanced(away_team, recent_limit)

    home_overall = compute_stats_weighted(home_team, home_results)
    away_overall = compute_stats_weighted(away_team, away_results)
    home_at_home = compute_stats_weighted(home_team, home_results, venue='home')
    away_away = compute_stats_weighted(away_team, away_results, venue='away')

    home_final = home_at_home if (home_at_home and home_at_home["matches_raw"] >= 2) else home_overall
    away_final = away_away if (away_away and away_away["matches_raw"] >= 2) else away_overall

    poisson = predict_from_stats_v2(home_final, away_final)
    market = fetch_market_odds(home_team, away_team)

    # Blended: if market available, 60/40 Poisson/Market
    final_probs = dict(poisson["probabilities"]) if poisson else None
    source = "low_league_v2_poisson"
    if final_probs and market and market.get("fair_home"):
        mh, md, ma = market["fair_home"], market["fair_draw"], market["fair_away"]
        if mh and md and ma:
            source += "+market"
            final_probs = {
                "home": final_probs["home"] * 0.6 + mh * 0.4,
                "draw": final_probs["draw"] * 0.6 + md * 0.4,
                "away": final_probs["away"] * 0.6 + ma * 0.4,
            }
            total = sum(final_probs.values())
            if total > 0:
                for k in final_probs:
                    final_probs[k] /= total

    # Effective sample size (for confidence reporting)
    eff_n = min(
        home_final.get("effective_n", 0) if home_final else 0,
        away_final.get("effective_n", 0) if away_final else 0,
        home_overall.get("effective_n", 0) if home_overall else 0,
        away_overall.get("effective_n", 0) if away_overall else 0,
    )

    n_raw = min(
        home_final.get("matches_raw", 0) if home_final else 0,
        away_final.get("matches_raw", 0) if away_final else 0,
    )

    if n_raw >= 8:
        quality = "good"
    elif n_raw >= 3:
        quality = "limited"
    else:
        quality = "poor"

    # Future info: which venue split was used
    venue_note = None
    if home_at_home and home_at_home["matches_raw"] >= 2:
        venue_note = f"主队用了主场数据({home_at_home['matches_raw']}场)"
    if away_away and away_away["matches_raw"] >= 2:
        venue_note = (venue_note or "") + (f"客队用了客场数据({away_away['matches_raw']}场)")

    result = {
        "home_team": home_team,
        "away_team": away_team,
        "home_stats": home_final,
        "away_stats": away_final,
        "home_stats_all": home_overall,
        "away_stats_all": away_overall,
        "poisson_prediction": poisson,
        "probabilities": {k: round(v, 4) for k, v in final_probs.items()} if final_probs else None,
        "market_odds": market,
        "data_quality": quality,
        "effective_n": round(eff_n, 1),
        "n_raw": n_raw,
        "venue_split": venue_note,
        "source": source,
    }

    if poisson and market and market.get("fair_home"):
        probs = final_probs or poisson["probabilities"]
        for outcome, key in [("home", "fair_home"), ("draw", "fair_draw"), ("away", "fair_away")]:
            if market.get(key):
                edge = round((probs.get(outcome, 0) - market[key]) * 100, 1)
                result[f"edge_{outcome}_pct"] = edge

    return result


def fetch_recent_results(team_name, limit=15):
    qs = urllib.parse.urlencode({"team": team_name, "limit": limit})
    data = _get(f"/results?{qs}")
    return data if isinstance(data, list) else data.get("results", [])


# ---- Legacy v1 API (backward compatible) ----

def compute_team_stats(team_name, results):
    gf, ga = [], []
    wins = draws = losses = 0
    clean_sheets = 0
    for r in results:
        ht = r.get("home_team", "")
        at = r.get("away_team", "")
        sc = r.get("score", {})
        hs = sc.get("home")
        aws = sc.get("away")
        if hs is None or aws is None:
            continue
        is_home = ht.lower() == team_name.lower()
        if is_home:
            gf.append(hs)
            ga.append(aws)
            if hs > aws: wins += 1
            elif hs == aws: draws += 1
            else: losses += 1
            if aws == 0: clean_sheets += 1
        else:
            gf.append(aws)
            ga.append(hs)
            if aws > hs: wins += 1
            elif aws == hs: draws += 1
            else: losses += 1
            if hs == 0: clean_sheets += 1
    n = len(gf)
    if n == 0:
        return None
    avg_gf = sum(gf) / n
    avg_ga = sum(ga) / n
    return {
        "matches": n,
        "avg_goals_for": round(avg_gf, 3),
        "avg_goals_against": round(avg_ga, 3),
        "win_rate": round(wins / n, 3),
        "draw_rate": round(draws / n, 3),
        "loss_rate": round(losses / n, 3),
        "clean_sheet_rate": round(clean_sheets / n, 3),
        "ppg": round((wins * 3 + draws) / n, 3),
        "total_goals_for": sum(gf),
        "total_goals_against": sum(ga),
    }


def predict_from_stats(home_stats, away_stats):
    if not home_stats or not away_stats:
        return None
    league_avg = max((home_stats["avg_goals_for"] + away_stats["avg_goals_for"]) / 2, 0.5)
    home_attack = home_stats["avg_goals_for"] / league_avg if league_avg > 0 else 1.0
    home_defense = home_stats["avg_goals_against"] / league_avg if league_avg > 0 else 1.0
    away_attack = away_stats["avg_goals_for"] / league_avg if league_avg > 0 else 1.0
    away_defense = away_stats["avg_goals_against"] / league_avg if league_avg > 0 else 1.0
    lambda_h = max(home_attack * away_defense * league_avg, 0.3)
    lambda_a = max(away_attack * home_defense * league_avg, 0.3)
    probs = match_probs(lambda_h, lambda_a)
    scores = top_scores(lambda_h, lambda_a, 6)
    return {
        "expected_goals_home": round(lambda_h, 3),
        "expected_goals_away": round(lambda_a, 3),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "top_scores": scores,
        "home_attack_rating": round(home_attack, 3),
        "home_defense_rating": round(home_defense, 3),
        "away_attack_rating": round(away_attack, 3),
        "away_defense_rating": round(away_defense, 3),
    }


def analyze_match_v1(home_team, away_team, recent_limit=15):
    home_results = fetch_recent_results(home_team, recent_limit)
    away_results = fetch_recent_results(away_team, recent_limit)
    home_stats = compute_team_stats(home_team, home_results)
    away_stats = compute_team_stats(away_team, away_results)
    poisson = predict_from_stats(home_stats, away_stats)
    market = fetch_market_odds(home_team, away_team)
    result = {
        "home_team": home_team,
        "away_team": away_team,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "poisson_prediction": poisson,
        "market_odds": market,
        "data_quality": "good" if (home_stats and home_stats["matches"] >= 5 and away_stats and away_stats["matches"] >= 5) else "limited",
    }
    if poisson and market and market.get("fair_home"):
        probs = poisson["probabilities"]
        for outcome, key in [("home", "fair_home"), ("draw", "fair_draw"), ("away", "fair_away")]:
            if market.get(key):
                edge = round((probs[outcome] - market[key]) * 100, 1)
                result[f"edge_{outcome}_pct"] = edge
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        r = analyze_match(sys.argv[1], sys.argv[2])
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
