# football_analyzer — 新一代足球量化分析系统

基于旧系统数据源重写的完整分析流程，修复旧系统已确认的底层缺陷，全部逻辑可复现、可回归验证。

## 架构

```
football_analyzer/
  config.py            全局配置(路径/联赛映射/模型与策略参数)
  data_loader.py       多源加载与标准化(JSON + 足彩网 + ESPN)
  devig.py             SHIN 去水 + 牛顿最小二乘 λ 反推
  asian_handicap.py    亚盘结算(0/0.25/0.5/0.75…) + 蒙特卡洛 EV
  elo.py               修正时间衰减的 ELO(按球队上次比赛间隔衰减)
  features.py          严格日期截断的滚动特征(防未来泄露)
  model.py             泊松攻防强度 + XGBoost 1X2 + Platt 校准
  backtest.py          严格 walk-forward 回测 + 校准诊断
  strategy.py          EV / 凯利 / 风控 / 串关相关性控制
  analyze.py           单场分析入口 + Markdown 报告
  ark_search.py        火山方舟模型联网问答(默认后端, 伤停/首发/战意)
  search.py            SearchInfinity 联网搜索 API(备选后端)
  odds_source.py       盘口源适配器(近期均盘默认, 实时盘口源预留)
  tracker.py           实盘推荐追踪闭环(落库/结算/统计)
  run_tests.py         回归测试(全绿入口)
```

## 数据源

| 来源 | 规模 | 内容 |
|------|------|------|
| `data/raw/football_data/football_data_collected.json` | 42,498 场 / 24 联赛 / 2012-2026 | 比分、半场、射门、射正、角球、牌、欧赔 |
| `data/raw/football_data/football_data_recent.csv` | 10,134 场 / 9 联赛 | 足彩网格式，含初/临盘、亚盘、大小球 |
| `data/raw/espn/*.csv` | 各联赛近3季 | 仅比分(补缺) |

主源为 JSON；足彩网用于初/临盘与亚盘；联赛名统一映射为规范 key(修复旧系统"同联赛两套命名"导致去重失败的问题)。

## 使用

```bash
# 单场分析(历史可加日期，未来默认今天)
python football_analyzer/analyze.py Arsenal Chelsea E0 2024-04-23
python football_analyzer/analyze.py "主队" "客队" "联赛key"
# 沙箱/只读环境: 纯 stdout 输出, 不写任何盘(报告+追踪)
python football_analyzer/analyze.py Arsenal Chelsea E0 --no-save
# 只关追踪、保留报告落盘
python football_analyzer/analyze.py Arsenal Chelsea E0 --no-track

# 联网情报检索(默认开启; 配置了 Key 即自动启用)
# 关闭: 追加 --no-search; 显式指定 Key: --api-key xxx
python football_analyzer/analyze.py Arsenal Chelsea E0 --no-search
python football_analyzer/ark_search.py "阿森纳 伤停 首发 预测 英超" --max-queries 2

# 回测
python -c "import sys; sys.path.insert(0,'football_analyzer'); from data_loader import load_master; from features import build_features; from backtest import walk_forward; df=build_features(load_master(include_espn=False)); bets,s=walk_forward(df); print(s['roi'], s['calibration'])"

# 回归测试
python football_analyzer/run_tests.py
```

联赛 key: `E0`英超 `E1`英冠 `E2`英甲 `SP1`西甲 `SP2`西乙 `D1`德甲 `D2`德乙 `I1`意甲 `I2`意乙 `F1`法甲 `F2`法乙 `N1`荷甲 `P1`葡超 `T1`土超 `B1`比甲 `BR`巴甲 `G1`希超 `CH`瑞士超 `DNK`丹超 `AUT`奥超 `NO1`挪超 `SWE`瑞超 `ROU`罗甲 `POL`波超

## 修复的旧系统缺陷

| 缺陷 | 旧系统 | 新系统 |
|------|--------|--------|
| λ 反推 | 伪梯度迭代，偏差 18~31pp | scipy 最小二乘 + 收敛断言，误差 0 |
| SHIN 去水 | 与比例法混用、不一致 | 统一 SHIN，与 penaltyblog 对照 maxdiff=0 |
| 亚盘结算 | 0.25/0.75 半赢当全赢 | 正确分半结算，负盘口对称递归 |
| ELO 衰减 | 锚定"今天"导致未来依赖 | 按球队上次比赛间隔衰减 |
| ML 切分 | 随机切分 | 严格时间切分 + walk-forward |
| 未来泄露 | 回测未按日期截断 | 特征因果构建 + 每折冻结参数 |
| 联赛混淆 | 球队画像跨联赛 | (league, team) 复合键 |
| 串关 | 无去水、无相关性控制 | SHIN 去水 + 相关性准入 + 凯利 |

## 诚实的回测结论

严格 walk-forward(无任何未来泄露)下，纯公开数据 + 1X2 模型 **无法稳定击败市场**:
- 19,171 注，ROI ≈ -11%，命中率 34%
- 校准诊断显示模型系统性过度自信(>70% 档实际命中仅 68%)——这正是负 EV 的来源
- 旧系统宣称的 "+240% ROI" 系未来信息泄露所致，新系统已按真实口径重新评估

这也意味着：真正可持续的优势需要额外信息(实时伤停、首发、盘口变动、内部模型)，而非仅靠历史比分与射门数据。

## 联网情报检索(火山引擎)

`analyze.py` 在模型分析之外，通过火山引擎联网能力抓取赛前情报(伤停/停赛/首发预测/战意轮换)，附加为报告第 6 节，帮助人工判断模型算不出的部分(轮换、突发伤病、战意)。情报仅作参考，不打进模型概率。

**默认后端: 方舟模型联网问答(`ark`, 推荐)**
- 原理: 方舟 Responses API 内置 `web_search` 工具，模型自己检索并返回带引用来源的摘要(实测可返回标题/URL/来源/发布时间)。
- 配置: `.env` 写入 `ARK_API_KEY=ark-...`(方舟 Key)与 `ARK_ENDPOINT_ID=ep-...`(支持 web_search 的推理接入点)。
- 实测: 2026-08-13 已验证，用户提供的 `ark-` Key + 现有豆包端点返回真实伤停情报(阿森纳廷贝尔/萨利巴伤缺)及 6 条引用。
- 临时指定: `python football_analyzer/analyze.py ... --api-key ark-... --endpoint ep-...`

**备选后端: SearchInfinity 联网搜索 API(`search_infinity`)**
- 在[联网搜索控制台](https://console.volcengine.com/search-infinity/api-key)创建 Key，`.env` 写入 `WEB_SEARCH_API_KEY=你的Key`。
- 或 AK/SK: `.env` 写入 `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`。
- 免费额度每月 500 次; 错误码 `10403` = Key 无效(常见为误用方舟 Key), `10406` = 额度耗尽, `700429` = 限流(已内置降频)。

**重要**: 方舟 Key(`ark-`)与联网搜索控制台 Key 是两套产品，互不通用。`config.py` 的 `SEARCH["backend"]` 控制使用哪个后端。

## 实盘追踪闭环(tracker.py)

`analyze.py` 分析后自动把推荐落库到 `strategy_data/live_tracker.json`(可用 `--no-track` 关闭)：

```bash
# 手动结算(比赛结束后回填比分)
python football_analyzer/tracker.py settle 2026-08-28_E0_Arsenal_vs_Chelsea 2 0
# 查看统计(累计命中率/ROI/按赔率来源与星级分组)
python football_analyzer/tracker.py report
```

规则: 记录必含赔率(缺赔率标记 `odds_missing`, 不参与 ROI)；`odds_source=estimated`(近期均盘近似)与 `live`(实时盘口)分组统计；**样本 < 100 条不出结论**。

## 盘口源适配器(odds_source.py)

统一赔率获取入口 `fetch_odds(...)`，默认 `recent` 源 = 近期均盘近似(估计值，未来场次星级降为 3 星上限)。已内置：
- `OddsSource` 基类契约 + live 源失败**自动降级**到 recent(绝不返回编造赔率)
- 球队名归一化/跨源匹配工具(`normalize_team`/`TeamMatcher`，含 alias 表)
- `TheOddsAPISource` 实时盘口源**示例模板**(含 `[Codex TODO]` 待填 API 调用)

**接入实时盘口源(Codex)**：完整接入手册见 `football_analyzer/ODDS_SOURCE_INTEGRATION.md`——
按 5 步填 API 调用 + 球队/联赛映射(写入 `config.ODDS["team_alias"]`/`["league_map"]`)，注册后改
`config.ODDS["default_source"]` 切换。接入后 `estimated=False`，星级不再降级、EV/边际全部可信。

## 已知限制

- JSON 欧赔无初盘/临场区分；`analyze.py` 未来场次使用近期均盘近似，需实时盘口核实(实时盘口源待接入)
- 泊松未加 Dixon-Coles 低分修正；XGB 特征未含伤停/轮换/战意(联网情报仅作报告参考，未量化进模型)
- 亚盘 EV 为固定水位 1.95 的模型估值，实际以实时水位结算为准
- 低级别联赛样本稀疏，新队无历史时特征回退为联赛均值
