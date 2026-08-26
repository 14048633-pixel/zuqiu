"""多赔率 API 容灾路由 (SOP Step2 落地 v3)
================================================================
解决"赔率源单一依赖"的工程层:
  - 主链:   ODDS_API_KEY_1..N (最多9组), 兼容旧 ODDS_API_KEY / THE_ODDS_API_KEY / config.json
  - 亚洲专用: ODDS_API_KEY_AS (J1/K2/中超/中乙 等联赛优先使用)
  - 每 key 可配独立 base url: ODDS_BASE_URL 全局默认, ODDS_BASE_URL_<i> 单 key 覆盖, ODDS_BASE_URL_AS
  - 配额硬阻断阈值: ODDS_MIN_QUOTA (默认50), 供抓取器预检使用
来源顺序: 环境变量 -> config.json -> .env(dotenv)
用法:
  from api_router import OddsApiRouter
  router = OddsApiRouter(project_root=...)
  sel = router.key_for_league("中超")   # 亚洲联赛 -> AS key
  key, base = sel["key"], sel["base_url"]
  try:
      ... 用 key+base 请求 ...
      router.mark_success(sel["key"])
  except Exception:
      sel = router.rotate_sel("中超")    # AS失败回主链 / 主链失败轮询下一个key
纯标准库, dotenv 可选。
"""
import os
import json

MAX_KEYS = 20
DEFAULT_BASE = "https://api.the-odds-api.com/v4"
DEFAULT_MIN_QUOTA = 50
ASIAN_LEAGUE_HINTS = ("J1", "K2", "中超", "中乙", "J联赛", "K联赛", "韩K", "日职", "日乙")


def _env_int(name, default):
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


def _is_asian_league(league):
    if not league:
        return False
    l = str(league)
    return any(h in l for h in ASIAN_LEAGUE_HINTS)


def _load_env(roots):
    try:
        from dotenv import load_dotenv
        for r in roots:
            p = os.path.join(r, ".env")
            if os.path.exists(p):
                load_dotenv(p, override=False)
    except Exception:
        pass


class OddsApiRouter:
    """多 key 轮询路由 + 亚洲联赛专用 key + 每 key 独立 base url。"""

    def __init__(self, base_dir=None, project_root=None, max_fail=3):
        roots = [r for r in (base_dir, project_root, os.getcwd()) if r]
        _load_env(roots)
        self.min_quota = _env_int("ODDS_MIN_QUOTA", DEFAULT_MIN_QUOTA)
        default_base = os.environ.get("ODDS_BASE_URL", "").strip() or DEFAULT_BASE
        keys = []
        meta = {}
        # 1) 多 key: ODDS_API_KEY_1..N (每 key 可配 ODDS_BASE_URL_<i>)
        for i in range(1, MAX_KEYS + 1):
            v = os.environ.get("ODDS_API_KEY_%d" % i, "").strip()
            if v:
                src = "ODDS_API_KEY_%d" % i
                keys.append((v, src))
                meta[src] = os.environ.get("ODDS_BASE_URL_%d" % i, "").strip() or default_base
        # 2) 兼容旧单 key
        if not keys:
            for k in ("ODDS_API_KEY", "THE_ODDS_API_KEY"):
                v = os.environ.get(k, "").strip()
                if v:
                    keys.append((v, k))
                    meta[k] = default_base
                    break
        # 3) config.json
        if not keys:
            for root in roots:
                p = os.path.join(root, "config.json")
                if os.path.exists(p):
                    try:
                        with open(p, encoding="utf-8") as f:
                            cfg = json.load(f)
                        v = str(cfg.get("odds_api_key", "")).strip()
                        if v and v != "YOUR_KEY_HERE":
                            keys.append((v, "config.json"))
                            meta["config.json"] = default_base
                            break
                    except Exception:
                        pass
        self.keys = keys
        self.meta = meta
        self._idx = 0
        self.max_fail = int(max_fail)
        self.health = {s: {"ok": 0, "fail": 0} for _, s in keys}
        # 亚洲赛事专用 key (不进入主链 keys, 避免破坏轮询语义)
        self.asian = None
        av = os.environ.get("ODDS_API_KEY_AS", "").strip()
        if av:
            self.asian = {
                "key": av,
                "source": "ODDS_API_KEY_AS",
                "base_url": os.environ.get("ODDS_BASE_URL_AS", "").strip() or default_base,
            }
            self.health.setdefault("ODDS_API_KEY_AS", {"ok": 0, "fail": 0})

    def available(self):
        return len(self.keys) > 0

    def get_active_key(self):
        if not self.keys:
            return None
        return self.keys[self._idx][0]

    def active_source(self):
        if not self.keys:
            return None
        return self.keys[self._idx][1]

    def _primary_sel(self):
        """主链当前激活 key 的选择 dict。"""
        if not self.keys:
            return None
        k, s = self.keys[self._idx]
        return {"key": k, "source": s, "base_url": self.meta.get(s, DEFAULT_BASE)}

    def key_for_league(self, league=None):
        """按联赛选 key: 亚洲联赛且配置了 AS key -> AS; 否则主链当前激活。"""
        if league is not None and _is_asian_league(league) and self.asian:
            return dict(self.asian)
        return self._primary_sel()

    def _find_source(self, key):
        for v, s in self.keys:
            if v == key:
                return s
        if self.asian and self.asian["key"] == key:
            return "ODDS_API_KEY_AS"
        return self.active_source()

    def mark_success(self, key=None):
        src = self._find_source(key)
        if src in self.health:
            self.health[src]["ok"] += 1

    def mark_failure(self, key=None):
        src = self._find_source(key)
        if src in self.health:
            self.health[src]["fail"] += 1

    def rotate(self):
        """主链切换到下一个 key; 返回新 key, 全部不可用返回 None。"""
        if not self.keys:
            return None
        start = self._idx
        for _ in range(len(self.keys)):
            self._idx = (self._idx + 1) % len(self.keys)
            if self.health.get(self.active_source(), {}).get("fail", 0) < self.max_fail:
                return self.get_active_key()
            if self._idx == start:
                break
        return None

    def rotate_sel(self, league=None):
        """失败后的下一个选择 dict: AS key 失败 -> 回主链; 主链失败 -> 轮询下一个主链 key。"""
        if league is not None and _is_asian_league(league) and self.asian \
                and self.health.get("ODDS_API_KEY_AS", {}).get("fail", 0) > 0:
            return self._primary_sel()
        nk = self.rotate()
        if nk is None:
            return None
        return self._primary_sel()

    def summary(self):
        return {s: dict(h) for s, h in self.health.items()}