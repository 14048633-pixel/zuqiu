# ODDS_SOURCE_INTEGRATION.md — 实时盘口源接入手册（给 Codex）

> 目标：把 `football_analyzer/odds_source.py` 里的实时盘口源从**模板**变成**可用实现**。
> 你只需要按本文档填真实 API 调用，其余（降级、映射、测试、接入 analyze）都已写好。

## 0. 现状

- 系统当前默认盘口源 `recent` = 近期均盘近似（`config.ODDS["default_source"]="recent"`），
  **估计值**。未来场次因赔率不可信，星级上限被压到 3 星（见 `analyze.py` `_rating`）。
- `odds_source.py` 已有：
  - `OddsSource` 基类 + `fetch_odds` 统一入口（live 源失败**自动降级**到 recent，绝不编造赔率）
  - 球队名归一化/匹配工具 `normalize_team` / `TeamMatcher`（跨源球队名差异通用）
  - `TheOddsAPISource` 示例 live 源（含 `[Codex TODO]` 标注待填处）

## 1. 接口契约（必须遵守）

```python
class YourSource(OddsSource):
    name = "your_source"      # 唯一源名, 与 config.ODDS["default_source"] 对应
    estimated = False         # live 源必须是 False, 否则星级继续降级

    def fetch(self, home, away, league, date, train=None, df=None) -> dict:
        # home/away: 本地规范球队名; league: 本地规范 key(E0/SP1/SWE...)
        # date: pandas.Timestamp 比赛日期
        # 返回:
        #   {"odds": (odds_h, odds_d, odds_a), "source": self.name,
        #    "estimated": False, "timestamp": "<ISO>", "note": "..."}
        ...
```

**异常约定（重要）**：
- 任何失败（网络、超时、盘口未开、找不到比赛、解析失败）→ `raise OddsFetchError("原因")`。
- `fetch_odds` 捕获后自动降级到 recent，并在 `note`/`fallback_from` 标注。
- **绝不允许返回编造/猜测的赔率**。宁可降级。

## 2. 接入步骤

### 步骤 1：实现源类

在 `odds_source.py` 里基于 `TheOddsAPISource` 模板实现（或新建一个 `OddsSource` 子类），
把 `[Codex TODO]` 标注处填完：
- API endpoint、鉴权（API key 从环境变量读，**不要硬编码**，参考 `_api_key()` 写法）
- 请求参数（sport/region/markets），按 `date` 过滤赛程
- 响应 JSON 解析 → 提取 `(odds_h, odds_d, odds_a)`
- 限流（429）退避、超时（用 `config.ODDS["timeout"]`）

### 步骤 2：球队名映射

数据源球队名 ≠ 本地规范名。两种处理：
1. 先在 `resolve` 前用 `normalize_team` 归一化（已内置，处理了 FC/United/罗马数字等差异）
2. 归一化仍匹配不上的，写进 `config.ODDS["team_alias"]`，如
   `{"Arsenal FC": "Arsenal", "Man United": "Manchester United"}`

调试方法：`python football_analyzer/odds_source.py --live Arsenal Chelsea E0 2026-08-30`
会打印源返回结果。先用这个看数据源真实命名，再补 alias。

### 步骤 3：联赛映射

数据源联赛名 → 本地规范 key，写进 `config.ODDS["league_map"]`，如
`{"soccer_epl": "E0", "soccer_spain_la_liga": "SP1", "soccer_sweden_allsvenskan": "SWE"}`。
`fetch_odds` 会用 `{本地key → 数据源sport}` 反查。

### 步骤 4：注册并切换

```python
_SOURCES["your_source"] = YourSource   # 注册
# config.py: ODDS["default_source"] = "your_source"   # 切换默认
```

### 步骤 5：验证（必做）

```bash
# 1) 真实比赛单场调试(打印源返回)
python football_analyzer/odds_source.py --live "主队" "客队" 联赛key 日期 [源名]

# 2) 单场分析确认 estimated=False + 星级不再降级(>=4 星)
python football_analyzer/analyze.py "主队" "客队" 联赛key 日期

# 3) 回归(离线自检不碰 live 源, 必须全绿)
python football_analyzer/run_tests.py
```

## 3. 注意事项

- **测试环境无网络**：`run_tests.py` 的 `odds_source` 自检只测 recent 源、映射工具、
  降级逻辑，**不会**请求 live 源。live 源正确性靠步骤 5 的真实调用验证。
- **时区**：比赛日期按本地时间（Asia/Shanghai）。给 API 的日期参数注意转换。
- **初盘 vs 临场**：`date` 之前的盘口才有效；若源能区分开盘/收盘价，优先取最接近开赛的。
- **key 安全**：API key 只放 `.env` / 环境变量，不进代码、不进 git。
- **多盘口聚合**：若源返回多家 bookmaker，可自行决定取均值或某一家；在 `note` 里注明口径。
- **不要伪造**：接口返回什么就传什么。宁可降级 recent，也不要填假设值——降级路径有标注，
  造假会污染 `tracker.py` 的实盘追踪统计。

## 4. 交付检查清单

- [ ] 源类实现完整，无 `[Codex TODO]` 残留
- [ ] API key 从环境变量读取
- [ ] 失败路径全部 `raise OddsFetchError`（不静默、不造假）
- [ ] `config.ODDS["team_alias"]` / `league_map` 覆盖已用联赛
- [ ] `fetch_odds(..., source="your_source")` 真实比赛返回正确赔率
- [ ] `analyze.py` 单场分析 `odds_estimated=False`
- [ ] `run_tests.py` ALL GREEN
- [ ] 在 `CHANGELOG.md` 登记接入记录 + `SESSION_STATE.md` 更新
