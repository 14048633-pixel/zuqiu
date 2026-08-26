"""Odds-API.io 备用赔率源适配器 (https://api.odds-api.io/v3)
================================================================
the-odds-api v4 与 Odds-API.io v3 的接口路径/响应结构不同, 不能只换 base_url:
  - 事件:  GET /v3/events?sport=football&league=<slug>&status=pending&limit=N
  - 赔率:  GET /v3/odds/multi?eventIds=1,2,3   (最多10场/请求, 计1次配额)
  - 联赛:  GET /v3/leagues?sport=football
  - 配额:  响应头 x-ratelimit-remaining / x-ratelimit-limit
本模块把 Odds-API.io 响应统一为系统快照行格式(与 live_odds.flatten_events 同列)。
纯标准库, 无第三方依赖; 所有函数只做 HTTP 请求/纯数据转换, 便于单测。
"""
import json
import urllib.parse
import urllib.request

BASE_URL = "https://api.odds-api.io/v3"
SPORT = "football"
ODDS_CHUNK = 10

# 中文联赛名 -> Odds-API.io league slug (与 live_odds.LEAGUE_SPORT_KEYS 同名单)
# 核对方法: python fetch_live_odds.py --sports  (打印 /v3/leagues 真实 slug)
LEAGUE_SLUGS = {
    "英超": "england-premier-league",
    "西甲": "spain-la-liga",
    "意甲": "italy-serie-a",
    "德甲": "germany-bundesliga",
    "法甲": "france-ligue-1",
    "英冠": "england-championship",
    "西乙": "spain-segunda-division",
    "德乙": "germany-2-bundesliga",
    "荷甲": "netherlands-eredivisie",
}

# 只保留系统核心三市场(与 the-odds-api 的 h2h,spreads,totals 对齐)
MARKET_MAP = {"ML": "h2h", "Spread": "spreads", "Totals": "totals"}
# 免费档仅 Bet365 + Unibet 两家返回赔率, 其余需付费(403); 可在 .env ODDS_BOOKMAKERS_2 覆盖
DEFAULT_BOOKMAKERS = "Bet365,Unibet"


def _quota_from_headers(headers):
    """Odds-API.io 配额头: x-ratelimit-limit / x-ratelimit-remaining。"""
    limit = headers.get("x-ratelimit-limit")
    remaining = headers.get("x-ratelimit-remaining")
    used = None
    try:
        if limit not in (None, "") and remaining not in (None, ""):
            used = int(limit) - int(remaining)
    except (TypeError, ValueError):
        used = None
    return {"used": used, "remaining": remaining}


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        quota = _quota_from_headers(resp.headers)
        return json.loads(resp.read().decode("utf-8")), quota


def fetch_sports_list(api_key, base_url=BASE_URL, timeout=30):
    """GET /v3/sports (公开, 用于配额预检) -> (sports_list, quota)。"""
    return _get_json(f"{base_url}/sports", timeout=timeout)


def fetch_leagues(api_key, base_url=BASE_URL, timeout=30):
    """GET /v3/leagues?sport=football -> (leagues, quota)。"""
    url = f"{base_url}/leagues?sport={SPORT}&apiKey={api_key}"
    return _get_json(url, timeout=timeout)


def fetch_events(api_key, league_slug, base_url=BASE_URL, limit=300, timeout=30):
    """GET /v3/events?status=pending&league=<slug> -> (events, quota)。"""
    params = urllib.parse.urlencode({
        "apiKey": api_key, "sport": SPORT, "league": league_slug,
        "status": "pending", "limit": int(limit),
    })
    return _get_json(f"{base_url}/events?{params}", timeout=timeout)


def fetch_odds_multi(api_key, event_ids, bookmakers=DEFAULT_BOOKMAKERS, base_url=BASE_URL, timeout=30):
    """GET /v3/odds/multi?eventIds=a,b,c&bookmakers=... (最多10场/请求) -> (odds_list, quota)。

    bookmakers 为必填参数(缺失返回400); 免费档只有 Bet365,Unibet, 可用 .env ODDS_BOOKMAKERS_2 覆盖。
    """
    if not event_ids:
        return [], {}
    ids = ",".join(str(e) for e in event_ids)
    params = urllib.parse.urlencode({
        "apiKey": api_key, "eventIds": ids,
        "bookmakers": bookmakers,
    })
    url = f"{base_url}/odds/multi?{params}"
    return _get_json(url, timeout=timeout)


def chunk_ids(ids, size=ODDS_CHUNK):
    for i in range(0, len(ids), size):
        yield ids[i:i + size]


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _side_key(side, point):
    return f"{side}@{point}" if point is not None else side


def flatten_rows(events, odds_list, league, snapshot_ts):
    """把 events + odds/multi 响应展开成系统快照行(列与 live_odds.flatten_events 一致)。"""
    ev = {str(e.get("id")): e for e in (events or []) if e.get("id") is not None}
    rows = []
    for od in odds_list or []:
        eid = str(od.get("id"))
        base = ev.get(eid, {})
        home = od.get("home") or base.get("home")
        away = od.get("away") or base.get("away")
        ct = od.get("date") or base.get("date")
        if not home or not away:
            continue
        for bk_name, markets in (od.get("bookmakers") or {}).items():
            for m in markets or []:
                mk = MARKET_MAP.get(m.get("name"))
                if not mk:
                    continue
                bk_ts = m.get("updatedAt") or ""
                if mk == "spreads":
                    # Bet365 平盘为"单边报价": hdp=-1.25 只给主、hdp=+1.25 只给客,
                    # 不能再默认 hdp=主队让球(否则客队+1.25被记成-1.25, EV符号错乱)。
                    # 检测: 该市场任一行只有单边价格 -> 按"报价方自身让球"解析;
                    # 双边行则高价方为受让方(hdp=受让方让球)。
                    # 注: 整个市场只展开一次, 不能在逐行循环内重复展开(否则行数暴增)。
                    sp_raw = [(_f(x.get("hdp")), _f(x.get("home")), _f(x.get("away"))) for x in (m.get("odds") or [])]
                    sp_split = any(h is not None and ((ph is None) != (pa is None)) for h, ph, pa in sp_raw)
                    for hdp, p_h, p_a in sp_raw:
                        if hdp is None:
                            continue
                        if sp_split:
                            if p_h is not None and p_a is None:
                                rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                             "commence_time": ct, "home_team": home, "away_team": away,
                                             "bookmaker": bk_name, "market": "spreads", "outcome": f"{home} {hdp}",
                                             "side": "home", "side_key": _side_key("home", hdp), "point": hdp,
                                             "price": p_h, "last_update": bk_ts})
                            elif p_a is not None and p_h is None:
                                rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                             "commence_time": ct, "home_team": home, "away_team": away,
                                             "bookmaker": bk_name, "market": "spreads", "outcome": f"{away} {hdp}",
                                             "side": "away", "side_key": _side_key("away", hdp), "point": hdp,
                                             "price": p_a, "last_update": bk_ts})
                            else:
                                # 双边行: hdp=受让方让球, 高价方为受让方
                                if (p_a or 0) > (p_h or 0):
                                    recv_side, recv_pt, recv_price = "away", hdp, p_a
                                    giv_side, giv_pt, giv_price = "home", -hdp, p_h
                                else:
                                    recv_side, recv_pt, recv_price = "home", hdp, p_h
                                    giv_side, giv_pt, giv_price = "away", -hdp, p_a
                                for side, pt, price in ((recv_side, recv_pt, recv_price), (giv_side, giv_pt, giv_price)):
                                    if price is None:
                                        continue
                                    rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                                 "commence_time": ct, "home_team": home, "away_team": away,
                                                 "bookmaker": bk_name, "market": "spreads",
                                                 "outcome": f"{home if side == 'home' else away} {pt}",
                                                 "side": side, "side_key": _side_key(side, pt), "point": pt,
                                                 "price": price, "last_update": bk_ts})
                        else:
                            # 标准双边格式: hdp=主队让球 (Unibet / Bet365 no-latency)
                            pt_h, pt_a = hdp, -hdp
                            rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                         "commence_time": ct, "home_team": home, "away_team": away,
                                         "bookmaker": bk_name, "market": "spreads", "outcome": f"{home} {hdp}",
                                         "side": "home", "side_key": _side_key("home", pt_h), "point": pt_h,
                                         "price": p_h, "last_update": bk_ts})
                            rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                         "commence_time": ct, "home_team": home, "away_team": away,
                                         "bookmaker": bk_name, "market": "spreads", "outcome": f"{away} {+pt_a if pt_a is not None else ''}",
                                         "side": "away", "side_key": _side_key("away", pt_a), "point": pt_a,
                                         "price": p_a, "last_update": bk_ts})
                    continue
                for o in m.get("odds") or []:
                    if mk == "h2h":
                        p_h, p_d, p_a = _f(o.get("home")), _f(o.get("draw")), _f(o.get("away"))
                        rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                     "commence_time": ct, "home_team": home, "away_team": away,
                                     "bookmaker": bk_name, "market": "h2h", "outcome": home,
                                     "side": "home", "side_key": "home", "point": None,
                                     "price": p_h, "last_update": bk_ts})
                        rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                     "commence_time": ct, "home_team": home, "away_team": away,
                                     "bookmaker": bk_name, "market": "h2h", "outcome": "Draw",
                                     "side": "draw", "side_key": "draw", "point": None,
                                     "price": p_d, "last_update": bk_ts})
                        rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                     "commence_time": ct, "home_team": home, "away_team": away,
                                     "bookmaker": bk_name, "market": "h2h", "outcome": away,
                                     "side": "away", "side_key": "away", "point": None,
                                     "price": p_a, "last_update": bk_ts})
                    elif mk == "totals":
                        # Bet365/Unibet 真实数据用 hdp 字段, 文档示例用 max; 两者都兼容
                        line = _f(o.get("max"))
                        if line is None:
                            line = _f(o.get("hdp"))
                        p_o, p_u = _f(o.get("over")), _f(o.get("under"))
                        rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                     "commence_time": ct, "home_team": home, "away_team": away,
                                     "bookmaker": bk_name, "market": "totals", "outcome": f"Over {line}",
                                     "side": "over", "side_key": _side_key("over", line), "point": line,
                                     "price": p_o, "last_update": bk_ts})
                        rows.append({"snapshot_ts": snapshot_ts, "event_id": eid, "league": league,
                                     "commence_time": ct, "home_team": home, "away_team": away,
                                     "bookmaker": bk_name, "market": "totals", "outcome": f"Under {line}",
                                     "side": "under", "side_key": _side_key("under", line), "point": line,
                                     "price": p_u, "last_update": bk_ts})
    return rows


def is_oddsapi_source(sel):
    """判断一个 key 选择 dict 是否指向 Odds-API.io (v3, 需走适配器)。

    识别规则: base_url 含 odds-api.io, 或 key 为 64 位 hex(the-odds-api key 为 32 位 hex)。
    """
    if not sel:
        return False
    base = str(sel.get("base_url") or "")
    key = str(sel.get("key") or "")
    if "odds-api.io" in base:
        return True
    return len(key) == 64 and all(c in "0123456789abcdef" for c in key.lower())


def fetch_bookmakers(api_key, base_url=BASE_URL, timeout=30):
    """GET /v3/bookmakers -> 有效庄家清单 [{name, active}] (用于核对可用源)。"""
    return _get_json(f"{base_url}/bookmakers?apiKey={api_key}", timeout=timeout)



def fetch_markets(sport=SPORT, base_url=BASE_URL, timeout=30):
    """GET /v3/markets -> 运动级市场元数据 (公开端点, 无需 apiKey)。

    返回 (payload, quota):
      - 带 sport 参数: {"sport": {...}, "markets": [{name, shape, period, prematch, live}, ...]}
      - 不带 sport:    {sport_slug: [markets...], ...} (全运动汇总)
    用于核对某运动支持的市场名(ML/Spread/Totals 等)与 shape, 不消耗配额(无配额头)。
    """
    if sport:
        url = f"{base_url}/markets?sport={sport}"
    else:
        url = f"{base_url}/markets"
    return _get_json(url, timeout=timeout)


def parse_markets(payload):
    """把 /v3/markets 响应规范化为 {市场名: {shape, period, prematch, live}}。

    兼容两种返回: 单运动 {"markets": [...]} 与全运动 {sport_slug: [...]}。
    """
    out = {}
    if not isinstance(payload, dict):
        return out
    entries = payload.get("markets")
    if isinstance(entries, list):
        for m in entries:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            out[m["name"]] = {
                "shape": m.get("shape"),
                "period": m.get("period"),
                "prematch": m.get("prematch"),
                "live": m.get("live"),
            }
        return out
    for slug, ms in payload.items():
        if slug == "sport" or not isinstance(ms, list):
            continue
        for m in ms:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            out.setdefault(m["name"], {}).setdefault("sports", []).append(slug)
    return out
