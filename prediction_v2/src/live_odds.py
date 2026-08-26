"""the-odds-api 临场赔率快照 + 初盘->临场变化特征（策略层专用）。

红线（SYSTEM_REVIEW 6.4）：赔率流只进策略/推理层，禁止进回测训练特征。
历史"初盘->临场"赔率流不可得，放进训练集必然引入未来函数/数据泄露。

术语：
  初盘   = 我方对某场比赛的第一份快照（不是庄家开盘价）
  临场   = 开赛前最近一份快照
  变化   = 临场价 - 初盘价（赔率下降=该方向被买入，上升=资金流出）

配额：the-odds-api 免费档 500 请求/月；9 联赛一轮 = 9 请求 ≈ 55 轮/月。
"""
import json
import os
import re

import pandas as pd

LEAGUE_SPORT_KEYS = {
    "英超": "soccer_epl",
    "西甲": "soccer_spain_la_liga",
    "意甲": "soccer_italy_serie_a",
    "德甲": "soccer_germany_bundesliga",
    "法甲": "soccer_france_ligue_one",
    "英冠": "soccer_efl_champ",
    "西乙": "soccer_spain_segunda_division",
    "德乙": "soccer_germany_bundesliga2",
    "荷甲": "soccer_netherlands_eredivisie",
    "J1": "soccer_japan_j_league",
    "中超": "soccer_china_superleague",
    "葡超": "soccer_portugal_primeira_liga",
    "比甲": "soccer_belgium_first_div",
    "英乙": "soccer_england_league2",
    "瑞超": "soccer_sweden_allsvenskan",
    "挪超": "soccer_norway_eliteserien",
    "巴甲": "soccer_brazil_campeonato",
    "阿甲": "soccer_argentina_primera_division",
    "美职": "soccer_usa_mls",
    "土超": "soccer_turkey_super_league",
    "墨超": "soccer_mexico_ligamx",
    "智利甲": "soccer_chile_campeonato",
    "丹超": "soccer_denmark_superliga",
    "意乙": "soccer_italy_serie_b",
    "法乙": "soccer_france_ligue_two",
}
DEFAULT_MARKETS = "h2h,spreads,totals"
DEFAULT_REGIONS = "eu"
API_BASE = "https://api.the-odds-api.com/v4"

# 常见队名差异（归一化后小写别名 -> 标准名，单向，避免环）
NAME_ALIASES = {
    "man united": "manchester united",
    "man utd": "manchester united",
    "man u": "manchester united",
    "man city": "manchester city",
    "tottenham hotspur": "tottenham",
    "spurs": "tottenham",
    "wolverhampton wanderers": "wolverhampton",
    "wolves": "wolverhampton",
    "west ham": "west ham united",
    "newcastle": "newcastle united",
    "brighton": "brighton and hove albion",
    "brighton hove albion": "brighton and hove albion",
    "leeds": "leeds united",
    "leicester": "leicester city",
    "athletic bilbao": "ath bilbao",
    "athletic club": "ath bilbao",
    "athletic club bilbao": "ath bilbao",
    "real betis": "betis",
    "cd leganes": "leganes",
    "rayo vallecano": "vallecano",
    "paris saint-germain": "paris saint germain",
    "psg": "paris saint germain",
    "olympique marseille": "marseille",
    "olympique lyonnais": "lyon",
    "as monaco": "monaco",
    "borussia dortmund": "dortmund",
    "bayern munich": "bayern",
    "bayern münchen": "bayern",
    "bayer leverkusen": "leverkusen",
    "borussia monchengladbach": "gladbach",
    "borussia m'gladbach": "gladbach",
    "hamburger sv": "hamburg",
    "vfb stuttgart": "stuttgart",
    "eintracht frankfurt": "frankfurt",
    "inter": "inter milan",
    "milan": "ac milan",
    "atletico": "atletico madrid",
    "villareal": "villarreal",
    "sheffield utd": "sheffield united",
    "west brom": "west bromwich albion",
    "west bromwich": "west bromwich albion",
    "stoke city": "stoke",
    "norwich city": "norwich",
    "leeds united": "leeds united",
    # 48h 临场匹配修复: 丹超/阿甲 全名->通用简称 (simpl 先 NFKD, 键用 ASCII)
    "sonderjyske fodbold": "sonderjyske",
    "gimnasia y esgrima mendoza": "gimnasia mendoza",
    # 跨源队名差异修复 (BSD短名 vs the-odds-api长名, 2026-08-22自检):
    # SJK Seinäjoki=SJK / Cracovia Kraków=KS Cracovia / Diriyah Club=Al Diriyah
    "sjk seinajoki": "sjk",
    "cracovia krakow": "ks cracovia",
    "diriyah club": "al diriyah",
}


# NFKD 不分解的字符(ø/å/æ 等)直接 ascii-ignore 会丢失 -> 先手动音译
_TRANSLIT = {
    "ø":"o","Ø":"O","å":"a","Å":"A","æ":"ae","Æ":"AE","ö":"o","Ö":"O","ü":"u","Ü":"U",
    "ä":"a","Ä":"A","ë":"e","ï":"i","ÿ":"y","ß":"ss","đ":"d","Đ":"D","ł":"l","Ł":"L",
    "á":"a","à":"a","â":"a","ã":"a","Á":"A","À":"A","Â":"A","Ã":"A",
    "é":"e","è":"e","ê":"e","É":"E","È":"E","Ê":"E",
    "í":"i","ì":"i","î":"i","Í":"I","Ì":"I","Î":"I",
    "ó":"o","ò":"o","ô":"o","õ":"o","Ó":"O","Ò":"O","Ô":"O","Õ":"O",
    "ú":"u","ù":"u","û":"u","Ú":"U","Ù":"U","Û":"U",
    "ý":"y","Ý":"Y","ñ":"n","Ñ":"N",
    "œ":"oe","Œ":"OE","þ":"th","Þ":"TH","ð":"d","Ð":"D","ç":"c","Ç":"C","ñ":"n","Ñ":"N",
    "š":"s","Š":"S","ž":"z","Ž":"Z","č":"c","Č":"C","ć":"c","Ć":"C","ę":"e","Ę":"E",
    "ą":"a","Ą":"A","ś":"s","Ś":"S","ź":"z","Ź":"Z","ń":"n","Ń":"N","ı":"i","İ":"i",
    "ğ":"g","Ğ":"G","ş":"s","Ş":"S",
}

def transliterate(s):
    """非 ASCII 音译: ø->o, å->a, æ->ae 等 (NFKD 无法分解的单字符)。"""
    return "".join(_TRANSLIT.get(ch, ch) for ch in str(s))

def normalize_team(name):
    """归一化队名用于匹配（音译、小写、去标点、查别名）。"""
    if name is None:
        return ""
    s = transliterate(name)
    s = "".join(ch for ch in str(s).strip().lower() if ch.isalnum() or ch.isspace())
    s = " ".join(s.split())
    return NAME_ALIASES.get(s, s)


def _token_overlap(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def resolve_api_key(base_dir=None, project_root=None):
    """key 解析顺序: 环境变量 -> config.json -> .env(dotenv) -> FOOTBALL_API_KEY(待验证)。"""
    for k in ("ODDS_API_KEY", "THE_ODDS_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v, k
    roots = [r for r in (base_dir, project_root, os.getcwd()) if r]
    for root in roots:
        p = os.path.join(root, "config.json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    cfg = json.load(f)
                v = str(cfg.get("odds_api_key", "")).strip()
                if v and v != "YOUR_KEY_HERE":
                    return v, "config.json"
            except Exception:
                pass
    try:
        from dotenv import load_dotenv
        for root in roots:
            p = os.path.join(root, ".env")
            if os.path.exists(p):
                load_dotenv(p, override=False)
    except Exception:
        pass
    for k in ("ODDS_API_KEY", "THE_ODDS_API_KEY", "FOOTBALL_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            tag = k if k != "FOOTBALL_API_KEY" else "FOOTBALL_API_KEY(可能是API-Football key, 需 --test 验证)"
            return v, tag
    return None, None


def fetch_sports_list(api_key, base_url=API_BASE, timeout=30):
    """GET /v4/sports/ -> (sports_list, quota_headers)。base_url 可指向备用源(如 shturl 兼容网关)。"""
    import urllib.request
    url = f"{base_url}/sports/?apiKey={api_key}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        quota = {
            "used": resp.headers.get("x-requests-used"),
            "remaining": resp.headers.get("x-requests-remaining"),
        }
        return json.loads(resp.read().decode("utf-8")), quota


def fetch_league_odds(api_key, sport_key, markets=DEFAULT_MARKETS,
                      regions=DEFAULT_REGIONS, base_url=API_BASE, timeout=30):
    """GET /sports/{sport}/odds -> (events_list, quota_headers)。base_url 可指向备用源。"""
    import urllib.request
    url = (f"{base_url}/sports/{sport_key}/odds"
           f"?apiKey={api_key}&regions={regions}&markets={markets}"
           f"&oddsFormat=decimal&dateFormat=iso")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        quota = {
            "used": resp.headers.get("x-requests-used"),
            "remaining": resp.headers.get("x-requests-remaining"),
        }
        return json.loads(resp.read().decode("utf-8")), quota


def _extract_point(text):
    m = re.search(r"(\d+(?:\.\d+)?)", str(text))
    return float(m.group(1)) if m else None


def _tokens(s):
    return set(s.split()) if s else set()


def classify_side(name, home, away):
    """把 the-odds-api 的 outcome 名归一到 home/away/draw。

    匹配分级: 精确 > draw > 包含(双向, 长度>=4防短串误撞) > 词元子集 > 词元重叠(需严格胜出)。
    无法可靠判定返回 None —— 由 flatten_events 在市场级做三选/双边补全, 绝不静默归客/归平。
    """
    no = normalize_team(name)
    nh = normalize_team(home)
    na = normalize_team(away)
    if not no:
        return None
    if no == nh:
        return "home"
    if no == na:
        return "away"
    low = str(name).strip().lower()
    if low in ("draw", "x", "tie", "平局"):
        return "draw"
    def _contain(short, long):
        return len(short) >= 4 and len(long) >= 4 and short in long
    # 包含: 全称/简称互换 (SJK Seinäjoki vs SJK / FC Porto vs Porto FC)
    if _contain(nh, no):
        return "home"
    if _contain(na, no):
        return "away"
    if _contain(no, nh):
        return "home"
    if _contain(no, na):
        return "away"
    to, th, ta = _tokens(no), _tokens(nh), _tokens(na)
    # 词元子集: Union Santa Fe ⊂ Club Atlético Unión de Santa Fe
    if th and to and th <= to and len(th) <= len(to) * 1.5:
        return "home"
    if ta and to and ta <= to and len(ta) <= len(to) * 1.5:
        return "away"
    if to and th and to <= th and len(to) <= len(th) * 1.5:
        return "home"
    if to and ta and to <= ta and len(to) <= len(ta) * 1.5:
        return "away"
    # 词元重叠: 取 min 分母, 需严格胜出防同城歧义
    # (Cracovia Kraków 对 KS Cracovia / Wieczysta Kraków 均 0.5 -> 判 None, 交市场级补全)
    def _score(a, b):
        if not a or not b:
            return 0.0
        return len(a & b) / min(len(a), len(b))
    sh, sa = _score(to, th), _score(to, ta)
    if sh >= 0.6 and sh > sa:
        return "home"
    if sa >= 0.6 and sa > sh:
        return "away"
    return None


def _classify_outcome(event_row, market, outcome, point=None):
    """把 the-odds-api 的 outcome 归一到 (side, point)。"""
    outcome = str(outcome)
    if market == "h2h":
        return classify_side(outcome, event_row.get("home_team"), event_row.get("away_team")), None
    if market == "totals":
        lo = outcome.lower()
        # the-odds-api 的 totals outcome 名是 Over/Under, 数字在 point 参数里;
        # 兼容旧数据(outcome 带数字, 如 "Over 2.5")时回退 _extract_point
        if lo.startswith("over"):
            pt = point if point is not None else _extract_point(outcome)
            return "over", pt
        if lo.startswith("under"):
            pt = point if point is not None else _extract_point(outcome)
            return "under", pt
        return "totals", None
    if market == "spreads":
        pt = float(point) if point is not None else None
        return classify_side(outcome, event_row.get("home_team"), event_row.get("away_team")), pt
    return market, None


def _complete_market_side(mrows, market):
    """市场级补全未识别侧, 防止队名歧义导致 1X2/亚盘 静默丢失或错配:
    - h2h: 恰好3个outcome且仅1个未识别 -> 补剩余侧; 否则丢弃未识别行(宁可缺盘不污染)。
    - spreads: 同|point|恰好2个且1个已识别 -> 另一侧即剩余方。
    返回处理后行列表(原地修改 side)。
    """
    if not mrows:
        return mrows
    if market == "h2h":
        known = [r for r in mrows if r["side"] is not None]
        unk = [r for r in mrows if r["side"] is None]
        if len(unk) == 1 and len(mrows) == 3:
            used = {r["side"] for r in known}
            miss = {"home", "draw", "away"} - used
            if len(miss) == 1:
                unk[0]["side"] = miss.pop()
                return mrows
        return known
    if market == "spreads":
        out = [r for r in mrows if r["side"] is not None]
        for r in (x for x in mrows if x["side"] is None):
            pt = r.get("point")
            grp = ([x for x in out if x.get("point") is not None and abs(x["point"]) == abs(pt)]
                   if pt is not None else [])
            if len(grp) == 1:
                r["side"] = "away" if grp[0]["side"] == "home" else "home"
                out.append(r)
        return out
    return mrows


def flatten_events(events, league, snapshot_ts):
    """把一次抓取的 events JSON 展开成长期格式行。"""
    rows = []
    for ev in events or []:
        eid = ev.get("id")
        home, away = ev.get("home_team"), ev.get("away_team")
        ct = ev.get("commence_time")
        erow = {"home_team": home, "away_team": away}
        for bk in ev.get("bookmakers", []):
            bkey = bk.get("key") or bk.get("title")
            bk_ts = bk.get("last_update") or ""
            for m in bk.get("markets", []):
                mk = m.get("key")
                mrows = []
                for oc in m.get("outcomes", []):
                    side, pt = _classify_outcome(erow, mk, oc.get("name"), oc.get("point"))
                    mrows.append({
                        "snapshot_ts": snapshot_ts, "event_id": str(eid),
                        "league": league, "commence_time": ct,
                        "home_team": home, "away_team": away,
                        "bookmaker": bkey, "market": mk, "outcome": oc.get("name"),
                        "side": side, "side_key": None, "point": pt,
                        "price": oc.get("price"), "last_update": bk_ts,
                    })
                for r in _complete_market_side(mrows, mk):
                    if r["side"] is None:
                        continue
                    r["side_key"] = f"{r['side']}@{r['point']}" if r["point"] is not None else r["side"]
                    rows.append(r)
    return rows

def snapshots_path(base_dir=None):
    base_dir = base_dir or os.getcwd()
    return os.path.join(base_dir, "output", "odds_snapshots", "snapshots.csv")


def append_snapshots(path, rows):
    """追加快照行到 CSV（含表头自动创建）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df = pd.DataFrame(rows)
    if os.path.exists(path):
        old = pd.read_csv(path, dtype={"event_id": str})
        df = pd.concat([old, df], ignore_index=True)
    df.to_csv(path, index=False)
    return len(df)


def load_snapshots(path=None):
    """读取快照 CSV；文件不存在返回空 DataFrame。"""
    path = path or snapshots_path()
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"event_id": str})
    for c in ("snapshot_ts", "commence_time", "last_update"):
        if c in df.columns:
            # pandas 3.x 对 Z/无Z 混合序列整体失败: 先统一去 Z, 再按 UTC 提升
            df[c] = pd.to_datetime(df[c].astype(str).str.replace("Z", "", regex=False),
                                   errors="coerce", utc=True)
    return df


def movement_table(df, bookmakers=("pinnacle",)):
    """按 event 汇总 初盘->临场 变化（每庄家/市场/方向 first/last/move）。"""
    if df is None or df.empty:
        return pd.DataFrame()
    recs = []
    for eid, g in df.groupby("event_id"):
        g = g.copy()
        base = g.iloc[0]
        rec = {
            "event_id": eid, "league": base.get("league"),
            "commence_time": base.get("commence_time"),
            "home_team": base.get("home_team"), "away_team": base.get("away_team"),
            "n_snapshots": int(g["snapshot_ts"].nunique()),
            "first_ts": g["snapshot_ts"].min(), "last_ts": g["snapshot_ts"].max(),
        }
        ko = pd.to_datetime(base.get("commence_time"), errors="coerce")
        if pd.notna(ko):
            rec["hours_to_kickoff_first"] = round((ko - rec["first_ts"]).total_seconds() / 3600, 2)
            rec["hours_to_kickoff_last"] = round((ko - rec["last_ts"]).total_seconds() / 3600, 2)
        for bk in bookmakers:
            sub = g[g["bookmaker"] == bk]
            if sub.empty:
                continue
            for (mk, sk), sg in sub.groupby(["market", "side_key"]):
                sg = sg.sort_values("snapshot_ts")
                first_px = float(sg["price"].iloc[0])
                last_px = float(sg["price"].iloc[-1])
                pcol = f"{bk}_{mk}_{sk}"
                rec[f"{pcol}_first"] = round(first_px, 3)
                rec[f"{pcol}_last"] = round(last_px, 3)
                rec[f"{pcol}_move"] = round(last_px - first_px, 3)
        recs.append(rec)
    return pd.DataFrame(recs)


def judge_text(rec, bookmaker="pinnacle"):
    """把变化行翻译成一句中文判断。"""
    if rec is None:
        return "无临场赔率快照（未抓取或该场无数据）"
    parts = []
    for col, v in rec.items():
        if col.startswith(f"{bookmaker}_") and col.endswith("_move") and v is not None:
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if v != v or abs(v) < 0.01:  # 跳过 NaN 与无变化
                continue
            key = col[len(bookmaker) + 1:-5]
            parts.append(f"{key} {'↓' if v < 0 else '↑'} {v:+.3f}")
    if not parts:
        return "临场赔率无显著变化（±0.01 内）"
    return "；".join(parts)


def match_event(movement_df, league, home, away, fuzzy=True):
    """按 联赛+主客队名 找对应场次的变化行。"""
    if movement_df is None or movement_df.empty:
        return None
    df = movement_df
    if "league" in df.columns:
        df = df[df["league"] == league]
    if df.empty:
        return None
    nh, na = normalize_team(home), normalize_team(away)
    for _, r in df.iterrows():
        if normalize_team(r.get("home_team")) == nh and normalize_team(r.get("away_team")) == na:
            return r
    if fuzzy:
        best, best_score = None, 0.0
        for _, r in df.iterrows():
            sh = _token_overlap(nh, normalize_team(r.get("home_team")))
            sa = _token_overlap(na, normalize_team(r.get("away_team")))
            score = (sh + sa) / 2
            if score > best_score:
                best, best_score = r, score
        if best is not None and best_score >= 0.5:
            return best
    return None
