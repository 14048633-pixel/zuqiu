# -*- coding: utf-8 -*-
"""盘口源适配器: 统一赔率获取接口(近期均盘默认 + 实时盘口源模板)。

接口契约(Codex / 后续接入实时盘口源必须遵守):
    OddsSource.fetch(self, home, away, league, date, train=None, df=None) -> dict
        home/away: 本地规范球队名(数据源里不同时, 用 TEAM_MATCHER 映射)
        league:    本地规范联赛 key(如 E0/SP1/SWE; 数据源里不同时, 用 config.ODDS["league_map"])
        date:      pandas.Timestamp 比赛日期
        train:     历史 DataFrame(截断到比赛日之前, 可作兜底); df: 全量 DataFrame(可选)
    返回结构:
        {"odds": (h, d, a), "source": 源名, "estimated": False,
         "timestamp": ISO 时间, "note": 备注}
    异常约定:
        - 获取失败/响应异常 -> 抛 OddsFetchError(带原因), fetch_odds 会自动降级到近期均盘,
          绝不允许返回编造赔率。
        - 盘口未开/找不到比赛 -> 抛 OddsFetchError("not_found"), 同样降级。

接入一个新实时盘口源的步骤(完整手册见 ODDS_SOURCE_INTEGRATION.md):
    1. 继承 OddsSource, 设置 name/estimated=False, 实现 fetch()
    2. 用 normalize_team / TEAM_MATCHER 处理球队名差异
    3. 用 config.ODDS["league_map"] 处理联赛名差异
    4. 在 _SOURCES 注册
    5. 改 config.ODDS["default_source"] = 你的源名
    6. 跑 run_tests.py 全绿 + 用真实比赛单场验证(注意: 测试环境无网络, 自检不会打 live 源)
"""
from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import re
import statistics
import time
import unicodedata

from config import ODDS, ROOT

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


class OddsFetchError(Exception):
    """盘口获取失败(网络/未开赛/响应异常等)。由 fetch_odds 统一降级。"""


# ---------------------------------------------------------------------------
# 球队/联赛名归一化与匹配(对所有 live 源通用)
# ---------------------------------------------------------------------------

# 只去"俱乐部类型词缀"这类无区分信息的词; 保留有区分作用的词(city/united/real/
# athletic/wanderers 等)——否则 Man City 与 Man Utd 会归一化成同一词导致误配。
_STOPWORDS = {"fc", "f.c.", "f", "afc", "cf", "cfc", "club", "ac", "a.c.",
              "as", "sc", "sv", "bk", "if", "fk", "sk", "ss", "sd", "cd",
              "1", "2", "b",
              # 2026-08-30 扩充: 常见俱乐部类型/语言词缀(避免 SSC Napoli/AD Ceuta/
              # IK Start/KVC Westerlo/Royale Union/Deportivo de ... 等前缀残留)
              "ad", "ssc", "ik", "kvc", "royale", "de", "cp", "ud", "fcsa",
              "fotball", "futbol", "calcio", "sport", "sports", "il", "club de",
              "cfc", "cf", "dc", "st", "st.", "fk", "ks", "ts", "fsv", "vfl",
              "rb", "sb", "scp", "rc", "kv", "krc", "boldklub", "warszawa"}

_ROMAN_NUM = re.compile(r"\b(i{1,3}|iv|v|vi{1,3})\b", re.I)
_ALIAS_NUM = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5",
              "vi": "6", "vii": "7", "viii": "8"}

# 特殊字符 -> 拉丁基础字符(欧洲/南美队名通用; 组合重音先由 NFKD 消除)
_TRANS = {"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "å": "a", "Å": "A",
          "đ": "d", "Đ": "D", "ł": "l", "Ł": "L", "ß": "ss", "ı": "i",
          "İ": "I", "ş": "s", "Ş": "S", "ș": "s", "ț": "t", "ð": "d",
          "þ": "th"}


def normalize_team(name: str) -> str:
    """归一化球队名: NFKD去重音 -> 字符转换 -> 小写 -> 去停用词 -> 罗马数字转阿拉伯,
    用于跨源匹配。

    例: "Manchester United FC" -> "manchester united"; "FC Barcelona" -> "barcelona";
        "Tromsø IL" -> "tromso"; "SSC Napoli" -> "napoli"; "Widzew Łódź" -> "widzew lodz"
    """
    if not name:
        return ""
    # 1) 组合重音 -> 基础字符(é/ñ/ö/ü/á 等)
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    # 2) 字符级转换(ø/ł/ı/ş/æ/ß 等)
    s = "".join(_TRANS.get(c, c) for c in s)
    # 3) 小写 + 符号转空格
    s = s.lower().replace(".", " ").replace("-", " ")
    s = _ROMAN_NUM.sub(lambda m: _ALIAS_NUM.get(m.group(1).lower(), m.group(1)), s)
    # 4) 去停用词
    words = [w for w in s.split() if w and w not in _STOPWORDS]
    result = " ".join(words)
    # 5) 空字符串保护: 停用词全去除后为空(如 "Sport Club") -> 退回原始小写形式
    if not result:
        result = s.strip()
    return result


_MATCH_LOG_FP = os.environ.get(
    "TEAM_MATCH_LOG_FP",
    os.path.join(str(ROOT), "analysis_records", "team_match_log.jsonl"))


class TeamMatcher:
    """数据源球队名 -> 本地规范名。
    匹配链: 中文别名(原样) -> 英文alias(归一化key) -> 归一化相等 -> 同义词 -> 模糊匹配(margin校验)。
    模糊匹配仅当最佳候选显著优于次佳(差>=0.08)时接受, 避免 Celta/Ceuta 这类误配。
    """

    def __init__(self, canonical: list[str], alias: dict[str, str] | None = None,
                 cn_alias: dict[str, str] | None = None,
                 synonyms: dict[str, str] | None = None,
                 log: bool = False):
        self.canonical = list(canonical)
        self.norm_index = {}
        for c in canonical:
            self.norm_index.setdefault(normalize_team(c), c)
        self.alias = {}
        for k, v in (alias or {}).items():
            self.alias[normalize_team(k)] = v
        self.cn_alias = dict(cn_alias or {})
        self.synonyms = dict(synonyms or {})
        self.log = log
        self._log_buf = []

    def _write_log(self, rec: dict) -> None:
        self._log_buf.append(rec)
        if not self.log:
            return
        try:
            with open(_MATCH_LOG_FP, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def flush_log(self) -> list[dict]:
        buf, self._log_buf = self._log_buf, []
        return buf

    def resolve(self, raw: str, threshold: float = 0.82,
                margin: float = 0.08) -> str | None:
        if not raw:
            return None
        stripped = str(raw).strip()
        # 1) 中文别名(原样 key, normalize 不改中文)
        if stripped in self.cn_alias:
            return self.cn_alias[stripped]
        key = normalize_team(stripped)
        # 2) 英文 alias(归一化 key)
        if key in self.alias:
            return self.alias[key]
        # 3) 归一化精确相等
        if key in self.norm_index:
            return self.norm_index[key]
        # 4) 同义词(如 "Ipswich" -> "Ipswich Town")
        if key in self.synonyms:
            return self.synonyms[key]
        # 5) 模糊匹配(归一化后) + 唯一性 margin 校验
        keys_all = list(self.norm_index)
        close = difflib.get_close_matches(key, keys_all, n=2, cutoff=threshold)
        if close:
            best = close[0]
            r_best = difflib.SequenceMatcher(None, key, best).ratio()
            if len(close) > 1:
                r_second = difflib.SequenceMatcher(None, key, close[1]).ratio()
                if r_best - r_second < margin:
                    self._write_log({"raw": stripped, "norm": key, "resolved": None,
                                     "reason": "fuzzy_not_unique",
                                     "cands": close, "top": r_best})
                    return None  # 候选不唯一, 拒绝, 避免误配
            out = self.norm_index[best]
            self._write_log({"raw": stripped, "norm": key, "resolved": out,
                             "reason": "fuzzy", "top": r_best})
            return out
        self._write_log({"raw": stripped, "norm": key, "resolved": None,
                         "reason": "not_found"})
        return None


# 全局球队匹配器: 由 data_loader 加载全部规范球队名后初始化(懒加载)
_TEAM_MATCHER = None


def team_matcher() -> TeamMatcher:
    global _TEAM_MATCHER
    if _TEAM_MATCHER is None:
        from data_loader import load_data
        df = load_data()
        teams = sorted(set(df["home"]) | set(df["away"]))
        _TEAM_MATCHER = TeamMatcher(teams, alias=ODDS["team_alias"],
                                    cn_alias=ODDS.get("cn_alias"),
                                    synonyms=ODDS.get("team_synonyms"),
                                    log=os.environ.get("TEAM_MATCH_LOG") == "1")
    return _TEAM_MATCHER


def map_league(source_league: str) -> str | None:
    """数据源联赛名 -> 本地规范 key。找不到返回 None(调用方降级)。"""
    return ODDS["league_map"].get(source_league)


# ---------------------------------------------------------------------------
# 源实现
# ---------------------------------------------------------------------------

class OddsSource:
    """盘口源基类。子类必须实现 fetch(), 遵守文件头契约。"""

    name = "base"
    estimated = False

    def fetch(self, home: str, away: str, league: str, date,
              train=None, df=None) -> dict:
        raise NotImplementedError


class RecentAvgSource(OddsSource):
    """近期均盘近似源(默认, 无外部依赖)。估计值, 仅供未来场次兜底。"""

    name = "recent"
    estimated = True

    def fetch(self, home, away, league, date, train=None, df=None) -> dict:
        floor = ODDS.get("overround_floor", 1.03)
        fallback = (2.5, 3.3, 2.9)
        if train is None or train.empty:
            return {"odds": fallback, "source": self.name, "estimated": True,
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "note": "无历史数据, 使用兜底赔率"}
        src = train[(train["league"] == league) &
                    ((train["home"] == home) | (train["away"] == home))].tail(6)
        if src.empty:
            odds = list(fallback)
        else:
            odds_h = src.apply(lambda r: r["odds_h"] if r["home"] == home else r["odds_a"], axis=1).mean()
            odds_a = src.apply(lambda r: r["odds_a"] if r["home"] == home else r["odds_h"], axis=1).mean()
            odds_d = src["odds_d"].mean()
            odds = [float(odds_h), float(odds_d), float(odds_a)]
        q = [1.0 / o for o in odds]
        s = sum(q)
        if s < floor:
            scale = floor / s
            odds = [o / scale for o in odds]
        return {"odds": tuple(odds), "source": self.name, "estimated": True,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                "note": "近期均盘近似, 请以实时盘口核实"}


_THEODDS_RESP_CACHE = {}  # 进程内缓存: url -> payload(全量响应), 批量预测避免逐场重复请求


class TheOddsAPISource(OddsSource):
    """TheOddsAPI 实时盘口源(https://the-odds-api.com)。

    2026-08-28 Codex 接入完成:
      - 请求: GET /v4/sports/{sport}/odds/?apiKey=..&regions=eu&markets=h2h&oddsFormat=decimal
      - 429 限流: 按 config.ODDS["retries"] 退避重试(2s 起步指数)
      - 解析: 队名匹配(TeamMatcher+team_alias+归一化兜底) -> 按 date(Asia/Shanghai)选场次
              -> 多 bookmaker h2h 均值
      - 失败一律 raise OddsFetchError, 由 fetch_odds 降级到 recent, 绝不编造赔率
    测试: python football_analyzer/odds_source.py --live 主队 客队 联赛key [日期]
    """

    name = "theoddsapi"
    estimated = False
    BASE = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    MARKETS = ["h2h"]

    def _api_key(self) -> str:
        key = os.environ.get("THE_ODDS_API_KEY", "")
        if not key:
            raise OddsFetchError("未配置 THE_ODDS_API_KEY(.env)")
        return key

    def fetch(self, home, away, league, date, train=None, df=None) -> dict:
        import urllib.error
        import urllib.parse
        import urllib.request

        # league 是本地规范 key, 反查数据源 sport key(league_map 是 数据源->本地, 需反转)
        inv = {v: k for k, v in ODDS["league_map"].items()}
        sport = inv.get(league)
        if not sport:
            raise OddsFetchError(f"联赛 {league} 未配置 league_map(需在 config.ODDS['league_map'] 补充)")
        url = self.BASE.format(sport=sport) + "?" + urllib.parse.urlencode({
            "apiKey": self._api_key(), "regions": "eu",
            "markets": ",".join(self.MARKETS), "oddsFormat": "decimal"})

        # 请求 + 429 限流退避重试
        retries = int(ODDS.get("retries", 2))
        timeout = int(ODDS.get("timeout", 10))
        payload = _THEODDS_RESP_CACHE.get(url)
        if payload is None:
            # 请求 + 429 限流退避重试
            retries = int(ODDS.get("retries", 2))
            timeout = int(ODDS.get("timeout", 10))
            last_err = None
            for attempt in range(retries + 1):
                try:
                    with urllib.request.urlopen(url, timeout=timeout) as r:
                        payload = json.loads(r.read().decode("utf-8", "replace"))
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        last_err = "HTTP 429 限流"
                        time.sleep(2 * (attempt + 1))
                        continue
                    raise OddsFetchError(f"TheOddsAPI HTTP {e.code}: {e.reason}")
                except Exception as e:
                    raise OddsFetchError(f"TheOddsAPI 请求失败: {e}")
            if payload is None:
                raise OddsFetchError(f"TheOddsAPI 请求失败: {last_err}")
            _THEODDS_RESP_CACHE[url] = payload
        if not isinstance(payload, list) or not payload:
            raise OddsFetchError(f"TheOddsAPI 联赛 {sport} 当前无 h2h 盘口(响应为空)")

        # 队名匹配: TeamMatcher(规范别名/归一/模糊) 优先, 失败回退归一化相等
        tm = None
        try:
            tm = team_matcher()
        except Exception:
            tm = None

        def _norm(name):
            return normalize_team(name or "")

        def _resolve_name(raw):
            if tm is not None:
                try:
                    r = tm.resolve(raw)
                    if r:
                        return r
                except Exception:
                    pass
            return _norm(raw)

        matched = []
        for gm in payload:
            h_raw = gm.get("home_team") or ""
            a_raw = gm.get("away_team") or ""
            if (_resolve_name(h_raw) == home and _resolve_name(a_raw) == away):
                matched.append(gm)
            elif (_norm(h_raw) == _norm(home) and _norm(a_raw) == _norm(away)):
                matched.append(gm)
        if not matched:
            raise OddsFetchError(
                f"未找到 {home} vs {away} 的盘口(TheOddsAPI {sport} 共 {len(payload)} 场, 队名匹配失败; "
                f"命名不同请补 config.ODDS['team_alias'])")

        # 按 date 选场次: 优先同日(Asia/Shanghai), 否则取最接近 date 的
        import pandas as pd
        try:
            target = pd.Timestamp(date)
        except Exception:
            target = None
        if len(matched) > 1 and target is not None:

            def _local_day(ct):
                try:
                    tt = pd.Timestamp(ct)
                    if tt.tzinfo is None:
                        tt = tt.tz_localize("UTC")
                    return tt.tz_convert("Asia/Shanghai").date()
                except Exception:
                    return None

            same = [g for g in matched if _local_day(g.get("commence_time")) == target.date()]
            if same:
                matched = same
            else:

                def _dist(g):
                    try:
                        tt = pd.Timestamp(g.get("commence_time"))
                        if tt.tzinfo is None:
                            tt = tt.tz_localize("UTC")
                        return abs((tt - pd.Timestamp(target)).total_seconds())
                    except Exception:
                        return float("inf")

                matched.sort(key=_dist)
        game = matched[0]
        commence = game.get("commence_time") or ""

        # h2h 盘口: 多机构取均值(口径写入 note)
        # the-odds-api h2h 的 outcome name 是球队名(如 "Crystal Palace")而非 Home/Draw/Away,
        # 用 game 的 home_team/away_team 识别主客, Draw 单独识别; 兼容 Home/Draw/Away 命名。
        home_name = game.get("home_team") or ""
        away_name = game.get("away_team") or ""
        prices = []
        for bk in game.get("bookmakers") or []:
            for m in bk.get("markets") or []:
                if (m.get("key") or "") != "h2h":
                    continue
                out = {}
                for o in m.get("outcomes") or []:
                    nm = str(o.get("name") or "")
                    if nm == home_name:
                        out["home"] = o.get("price")
                    elif nm == away_name:
                        out["away"] = o.get("price")
                    elif nm.lower() == "draw":
                        out["draw"] = o.get("price")
                    else:
                        out[nm] = o.get("price")
                hp = out.get("home") or out.get("Home")
                dp = out.get("draw") or out.get("Draw")
                ap = out.get("away") or out.get("Away")
                if hp and dp and ap:
                    try:
                        prices.append((float(hp), float(dp), float(ap)))
                    except (TypeError, ValueError):
                        continue
        if not prices:
            raise OddsFetchError(f"未找到 {home} vs {away} 的 h2h 盘口(TheOddsAPI 无有效 bookmaker)")
        n = len(prices)
        odds = tuple(round(sum(p[i] for p in prices) / n, 4) for i in range(3))
        if not all(o > 1.0 for o in odds):
            raise OddsFetchError(f"TheOddsAPI h2h 赔率异常: {odds}")
        return {"odds": odds, "source": self.name, "estimated": False,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "note": f"TheOddsAPI h2h {n}家均值; 开赛 {commence or '未知'}; sport={sport}"}


class _InferMCP:
    """InferSports MCP (streamable HTTP, 免费无key). 纯标准库实现, 不依赖第三方。"""

    BASE = "https://api.infersports.dev/mcp"

    def __init__(self):
        import http.cookiejar
        import urllib.request as _ur
        self._cj = http.cookiejar.CookieJar()
        self._op = _ur.build_opener(_ur.HTTPCookieProcessor(self._cj))
        self._ready = False

    def _post(self, payload):
        import urllib.request as _ur
        req = _ur.Request(self.BASE, data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Accept", "application/json")
        req.add_header("Content-Type", "application/json")
        with self._op.open(req, timeout=45) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    def _ensure(self):
        if self._ready:
            return
        self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "football-analyzer", "version": "1.0"}}})
        self._ready = True

    def call(self, name, args):
        self._ensure()
        try:
            j = self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                            "params": {"name": name, "arguments": args}})
            return json.loads(j["result"]["content"][0]["text"])
        except Exception:
            return {"status": "error"}


class InferSportsSource(OddsSource):
    """InferSports 免费 MCP 源: 1x2 sharp line (多亚庄聚合, 无需 key)。

    2026-08-28 接入: find_match 按队名+时间贴近匹配, get_sharp_line 取 1x2 best_prices。
    """

    name = "infersports"
    estimated = False

    def fetch(self, home, away, league, date, train=None, df=None):
        import pandas as pd
        try:
            target = pd.Timestamp(date)
        except Exception:
            target = None
        c = _InferMCP()
        q = "%s vs %s" % (home, away)
        d = c.call("find_match", {"query": q})
        m = d.get("match") if d.get("status") in ("matched", "ambiguous") else None
        if not m:
            raise OddsFetchError(f"InferSports 未找到 {home} vs {away}")
        if target is not None:
            try:
                st = pd.Timestamp(m.get("scheduled_at", ""))
                if abs((st - target).total_seconds()) > 12 * 3600:
                    raise OddsFetchError(
                        f"InferSports 时间不匹配({m.get('scheduled_at')} vs {target})")
            except OddsFetchError:
                raise
            except Exception:
                pass
        g = c.call("get_sharp_line", {"query": q, "market_type": "1x2", "period": "full_time",
                                      "format": "decimal", "verbosity": "full"})
        if g.get("status") != "ok":
            raise OddsFetchError(f"InferSports 1x2 无盘: {str(g.get('_error') or g.get('summary') or g)[:160]}")
        comp = g.get("comparison") or {}
        bp = {x.get("outcome"): x.get("price") for x in (comp.get("best_prices") or [])}
        hp, dp, ap = bp.get("home"), bp.get("draw"), bp.get("away")
        try:
            odds = (float(hp), float(dp), float(ap))
        except (TypeError, ValueError):
            raise OddsFetchError(f"InferSports 1x2 赔率缺失: {bp}")
        if not all(o and o > 1 for o in odds):
            raise OddsFetchError(f"InferSports 1x2 赔率异常: {odds}")
        books = comp.get("book_count")
        return {"odds": odds, "source": self.name, "estimated": False,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "note": f"InferSports sharp 1x2({books or '?'}家)"}


class BSDSource(OddsSource):
    """BSD 免费共识源: v1 events 按队名匹配 + v2 /events/{id}/odds/ 共识价。"""

    name = "bsd"
    estimated = False
    API = "https://sports.bzzoiro.com/api"

    def _headers(self):
        key = os.environ.get("BZZOIRO_API_KEY", "")
        if not key:
            raise OddsFetchError("未配置 BZZOIRO_API_KEY(.env)")
        return {"Authorization": "Token " + key, "Accept": "application/json",
                "User-Agent": "Mozilla/5.0"}

    def fetch(self, home, away, league, date, train=None, df=None):
        import requests
        import pandas as pd
        target = pd.Timestamp(date)
        # 本地日(Asia/Shanghai) -> UTC 窗口
        try:
            tz = dt.timezone(dt.timedelta(hours=8))
            day_start = dt.datetime(target.year, target.month, target.day, 0, 0, tzinfo=tz)
            day_end = day_start + dt.timedelta(days=1) - dt.timedelta(seconds=1)
            d_from = day_start.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            d_to = day_end.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            d_from = target.strftime("%Y-%m-%d") + "T00:00:00Z"
            d_to = target.strftime("%Y-%m-%d") + "T23:59:59Z"
        headers = self._headers()
        timeout = int(ODDS.get("timeout", 10))
        evs = []
        try:
            off = 0
            while True:
                r = requests.get(self.API + "/events/", params={
                    "date_from": d_from, "date_to": d_to, "limit": 50, "offset": off,
                    "full": "true"}, headers=headers, timeout=timeout)
                if r.status_code != 200:
                    raise OddsFetchError(f"BSD events HTTP {r.status_code}")
                res = r.json().get("results") or []
                evs += res
                if len(res) < 50:
                    break
                off += 50
        except OddsFetchError:
            raise
        except Exception as e:
            raise OddsFetchError(f"BSD events 请求失败: {e}")
        if not evs:
            raise OddsFetchError(f"BSD {target.date()} 无事件")
        # 队名匹配
        tm = None
        try:
            tm = team_matcher()
        except Exception:
            tm = None

        def _res(raw):
            if tm is not None:
                try:
                    r = tm.resolve(raw)
                    if r:
                        return r
                except Exception:
                    pass
            return normalize_team(raw or "")

        ev = None
        for e in evs:
            h = e.get("home_team") or e.get("home") or ""
            a = e.get("away_team") or e.get("away") or ""
            if _res(h) == home and _res(a) == away:
                ev = e
                break
        if ev is None:
            raise OddsFetchError(f"BSD 未找到 {home} vs {away}({target.date()})")
        eid = ev.get("id")
        try:
            r = requests.get("https://sports.bzzoiro.com/api/v2/events/%s/odds/" % eid,
                             headers=headers, timeout=timeout)
            if r.status_code != 200:
                raise OddsFetchError(f"BSD odds HTTP {r.status_code}")
            cons = r.json().get("odds") or {}
        except OddsFetchError:
            raise
        except Exception as e:
            raise OddsFetchError(f"BSD odds 请求失败: {e}")
        try:
            odds = (float(cons["home_win"]), float(cons["draw"]), float(cons["away_win"]))
        except (KeyError, TypeError, ValueError):
            raise OddsFetchError(f"BSD {home} vs {away} 共识赔率缺失: {cons}")
        if not all(o and o > 1 for o in odds):
            raise OddsFetchError(f"BSD 共识赔率异常: {odds}")
        return {"odds": odds, "source": self.name, "estimated": False,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "note": f"BSD 共识; event_id={eid}"}


def _consensus_odds(results):
    """多源 (source, odds) -> {odds: 各结果原始赔率中位数, dispersion: 去水概率标准差均值, sources}。

    dispersion>0.05 视为盘口分歧(与 multi_source.py 口径一致)。纯函数, 供自检离线测试。
    """
    if not results:
        return None
    n_out = len(results[0][1])
    raw, devigged = [], []
    for _, odds in results:
        raw.append(list(odds))
        inv = [1.0 / max(o, 1e-9) for o in odds]
        s = sum(inv)
        devigged.append([p / s for p in inv])
    med_raw = []
    for col in range(n_out):
        vals = sorted(r[col] for r in raw)
        med_raw.append(vals[len(vals) // 2] if len(vals) % 2
                       else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2)
    disp = []
    for col in range(n_out):
        vals = [r[col] for r in devigged]
        disp.append(statistics.pstdev(vals))
    return {"odds": tuple(round(o, 4) for o in med_raw),
            "dispersion": round(sum(disp) / len(disp), 4),
            "sources": [s for s, _ in results]}


_APIFB_DATE_CACHE = {}


class ApiFootballSource(OddsSource):
    """API-Football 兜底源: Match Winner(1X2)。配额 100次/天, 排 composite_fill 兜底。"""

    name = "apifootball"
    estimated = False
    BASE = "https://v3.football.api-sports.io"

    def _key(self):
        key = os.environ.get("FOOTBALL_API_KEY", "")
        if not key:
            raise OddsFetchError("未配置 FOOTBALL_API_KEY(.env)")
        return key

    def fetch(self, home, away, league, date, train=None, df=None):
        import urllib.error
        import urllib.parse
        import urllib.request
        import pandas as pd
        target = pd.Timestamp(date)
        date_str = target.strftime("%Y-%m-%d")
        lid = (ODDS.get("apifb_league_map") or {}).get(league)
        headers = {"x-apisports-key": self._key()}
        timeout = int(ODDS.get("timeout", 10))

        # 1) 赛程: API-Football 按 UTC 日期分组, 北京 00:00-08:00 的比赛归属前一天 UTC,
        #    因此同时拉「本地日 + 前一天 UTC」两天(各自按日缓存, 每日期只拉 1 次)。
        date_strs = [date_str, (target - pd.Timedelta(days=1)).strftime("%Y-%m-%d")]
        for ds in date_strs:
            if ds in _APIFB_DATE_CACHE:
                continue
            url = self.BASE + "/fixtures?" + urllib.parse.urlencode({"date": ds})
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                    body = json.loads(r.read().decode("utf-8", "replace"))
            except Exception as e:
                raise OddsFetchError(f"API-Football fixtures 请求失败: {e}")
            if body.get("errors"):
                raise OddsFetchError(f"API-Football fixtures 错误: {body['errors']}")
            _APIFB_DATE_CACHE[ds] = body.get("response") or []
        fixtures = _APIFB_DATE_CACHE[date_strs[0]] + _APIFB_DATE_CACHE[date_strs[1]]

        # 队名匹配(TeamMatcher/归一化)
        tm = None
        try:
            tm = team_matcher()
        except Exception:
            tm = None

        def _res(raw):
            if tm is not None:
                try:
                    r = tm.resolve(raw)
                    if r:
                        return r
                except Exception:
                    pass
            return normalize_team(raw or "")

        fx = None
        for f in fixtures:
            h = ((f.get("teams") or {}).get("home") or {}).get("name") or ""
            a = ((f.get("teams") or {}).get("away") or {}).get("name") or ""
            f_lg = (f.get("league") or {}).get("id")
            if lid and f_lg and f_lg != lid:
                continue
            if _res(h) == home and _res(a) == away:
                fx = f
                break
        if fx is None:
            raise OddsFetchError(f"API-Football 未找到 {home} vs {away}({date_str})")
        fid = (fx.get("fixture") or {}).get("id")

        # 2) Match Winner 赔率
        url = self.BASE + "/odds?" + urllib.parse.urlencode({"fixture": fid})
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            raise OddsFetchError(f"API-Football odds 请求失败: {e}")
        prices = []
        for b in body.get("response") or []:
            for bk in b.get("bookmakers") or []:
                for bet in bk.get("bets") or []:
                    if bet.get("name") not in ("Match Winner", "1X2"):
                        continue
                    out = {v.get("value"): v.get("odd") for v in bet.get("values") or []}
                    hp, dp, ap = out.get("Home"), out.get("Draw"), out.get("Away")
                    if hp and dp and ap:
                        try:
                            prices.append((float(hp), float(dp), float(ap)))
                        except (TypeError, ValueError):
                            continue
        if not prices:
            raise OddsFetchError(f"API-Football {home} vs {away} 无 Match Winner 盘")
        n = len(prices)
        odds = tuple(round(sum(p[i] for p in prices) / n, 4) for i in range(3))
        if not all(o and o > 1 for o in odds):
            raise OddsFetchError(f"API-Football 赔率异常: {odds}")
        return {"odds": odds, "source": self.name, "estimated": False,
                "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "note": f"API-Football Match Winner {n}家均值; fixture={fid}"}


class CompositeSource(OddsSource):
    """多源混合: 依次查 config.ODDS["composite_sources"], >=2 源取去水中位数共识,
    单源直接使用, 全失败抛 OddsFetchError(由 fetch_odds 降级 recent, 不编造)。"""

    name = "composite"
    estimated = False

    def fetch(self, home, away, league, date, train=None, df=None):
        subs = ODDS.get("composite_sources") or ["theoddsapi", "infersports", "bsd"]
        fills = ODDS.get("composite_fill") or []  # 兜底源: 前序源全失败才查(省配额)
        results, errs = [], []

        def _try(sname):
            cls = _SOURCES.get(sname)
            if cls is None or cls is CompositeSource:
                return
            try:
                r = cls().fetch(home, away, league, date, train=train, df=df)
                if r.get("estimated"):
                    return
                results.append((sname, tuple(r["odds"])))
            except Exception as e:
                # 2026-09-03 修复: 原只捕获 OddsFetchError, infersports 抛未包装
                # URLError(SSL) 会逃逸并拖垮整个 composite(即使 theoddsapi 已成功)。
                errs.append("%s: %s" % (sname, e))

        for sname in subs:
            _try(sname)
        if not results:
            for sname in fills:
                _try(sname)
        ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if not results:
            raise OddsFetchError("多源全部失败: " + ("; ".join(errs) if errs else "无可用源"))
        fail_txt = ("; 失败: " + "; ".join(errs)) if errs else ""
        if len(results) == 1:
            sname, odds = results[0]
            return {"odds": odds, "source": "composite(%s)" % sname, "estimated": False,
                    "timestamp": ts, "note": "复合源单源命中(%s)%s" % (sname, fail_txt)}
        c = _consensus_odds(results)
        note = "复合源共识(%d源: %s); 分歧指数=%.3f" % (len(c["sources"]), ",".join(c["sources"]), c["dispersion"])
        if c["dispersion"] > 0.05:
            note += " ⚠盘口分歧"
        note += fail_txt
        return {"odds": c["odds"], "source": "composite", "estimated": False,
                "timestamp": ts, "note": note}


# 注册表: 新增源在此注册(name -> 类)
_SOURCES: dict[str, type[OddsSource]] = {
    "recent": RecentAvgSource,
    "theoddsapi": TheOddsAPISource,
    "infersports": InferSportsSource,
    "bsd": BSDSource,
    "apifootball": ApiFootballSource,
    "composite": CompositeSource,
}


def fetch_odds(home: str, away: str, league: str, date,
               train=None, df=None, source: str | None = None) -> dict:
    """统一盘口获取入口。

    source: 显式指定源名; 缺省用 config.ODDS["default_source"]。
    live 源失败时自动降级到近期均盘(绝不返回编造赔率), 并在 note 标注降级来源。
    """
    source = source or ODDS.get("default_source", "recent")
    cls = _SOURCES.get(source)
    if cls is None:
        raise ValueError(f"未知盘口源: {source}(已注册: {sorted(_SOURCES)})")
    try:
        return cls().fetch(home, away, league, date, train=train, df=df)
    except OddsFetchError as e:
        if source == "recent":
            raise
        out = RecentAvgSource().fetch(home, away, league, date, train=train, df=df)
        out["note"] = f"live源({source})失败: {e}; 已降级为近期均盘"
        out["fallback_from"] = source
        return out


def fetch_odds_live(home: str, away: str, league: str, date,
                    train=None, df=None, source: str = "theoddsapi") -> dict:
    """强制走指定 live 源(不降级), 供接入调试用: python odds_source.py --live 主 客 联赛key。"""
    cls = _SOURCES.get(source)
    if cls is None:
        raise ValueError(f"未知盘口源: {source}")
    return cls().fetch(home, away, league, date, train=train, df=df)


def _self_test() -> None:
    import pandas as pd
    # 1) 近期均盘源 + overround 下限
    train = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"]),
        "league": ["E0"] * 4,
        "home": ["Arsenal", "Chelsea", "Arsenal", "Liverpool"],
        "away": ["X", "Y", "Z", "Arsenal"],
        "odds_h": [1.6, 2.1, 1.5, 3.0],
        "odds_d": [4.0, 3.4, 4.2, 3.2],
        "odds_a": [5.5, 3.6, 6.0, 2.4],
    })
    # 显式指定 recent, 保证自检离线(不依赖 default_source, 不碰 live 源)
    out = fetch_odds("Arsenal", "Chelsea", "E0", pd.Timestamp("2024-01-29"), train=train, source="recent")
    assert out["source"] == "recent" and out["estimated"] is True
    assert all(o > 1 for o in out["odds"])
    assert sum(1.0 / o for o in out["odds"]) >= ODDS["overround_floor"] - 1e-9
    # 2) 球队名归一化 + 匹配
    assert normalize_team("Manchester United FC") == "manchester united"
    assert normalize_team("FC Barcelona") == "barcelona"
    assert normalize_team("Villarreal CF") == "villarreal"
    # 关键: Man City 与 Man Utd 必须归一化成不同词(避免误配)
    assert normalize_team("Manchester City") != normalize_team("Manchester United")
    m = TeamMatcher(["Manchester United", "Barcelona", "Real Madrid"],
                    alias={"MUFC": "Manchester United"})
    assert m.resolve("FC Barcelona") == "Barcelona"      # 归一化相等
    assert m.resolve("MUFC") == "Manchester United"      # alias 表
    assert m.resolve("Barcelone") == "Barcelona"         # 拼写变体(模糊匹配)
    assert m.resolve("Nonexistent FC") is None
    # 3) 未知源报错
    try:
        fetch_odds("A", "B", "E0", pd.Timestamp("2024-01-01"), train=train, source="nope")
        assert False, "应报错"
    except ValueError:
        pass
    # 4) live 源未接 API key -> 降级到 recent(note 标注)
    os.environ.pop("THE_ODDS_API_KEY", None)
    out2 = fetch_odds("Arsenal", "Chelsea", "E0", pd.Timestamp("2024-01-29"),
                      train=train, source="theoddsapi")
    assert out2["source"] == "recent"
    assert out2.get("fallback_from") == "theoddsapi"
    # 5) 多源共识(纯函数, 离线)
    import statistics
    res = _consensus_odds([("a", (2.0, 3.0, 4.0)), ("b", (2.1, 3.2, 3.6))])
    assert res["sources"] == ["a", "b"]
    assert 2.0 <= res["odds"][0] <= 2.1 and res["odds"][2] >= 3.6
    assert 0.0 <= res["dispersion"] <= 0.2
    res2 = _consensus_odds([("a", (2.0, 3.0, 4.0)), ("b", (2.0, 3.0, 4.0))])
    assert res2["dispersion"] == 0.0
    res3 = _consensus_odds([("a", (2.0, 3.0, 4.0))])
    assert res3["sources"] == ["a"] and res3["odds"] == (2.0, 3.0, 4.0)
    assert _consensus_odds([]) is None
    # 6) 多源注册: apifootball 已注册且为兜底 fill
    assert "apifootball" in _SOURCES
    assert "apifootball" in ODDS.get("composite_fill", [])
    print("== odds_source 自检通过 ==")


def main(argv=None) -> int:
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "--live" and len(argv) >= 4:
        from data_loader import load_data
        home, away, league = argv[1], argv[2], argv[3]
        date = argv[4] if len(argv) > 4 else None
        from config import DATA
        import pandas as pd
        date = pd.Timestamp(date) if date else pd.Timestamp.today().normalize()
        df = load_data()
        train = df[df["date"] < date]
        src = argv[5] if len(argv) > 5 else "theoddsapi"
        out = fetch_odds_live(home, away, league, date, train=train, df=df, source=src)
        print(out)
        return 0
    _self_test()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
