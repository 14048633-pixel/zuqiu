# 足球预测系统 - 完整迁移包 v2（含API + 所有数据）

## 包内容
完整足球预测系统全量迁移包，包含：
- **核心代码**：`auto_sop.py` / `collect_strategy_data.py` / `regression_test.py` / `src/`（模型/规则/特征/策略/Agent）
- **API 集成**：`prediction_v2/`（the-odds-api 实时盘口抓取 + 预测输出）、`collect_strategy_data.py`（football-data API）、`src/football_agent.py`（DeepSeek/豆包/Kimi/GLM）、`.env`（全部 API 密钥：FOOTBALL_API/DEEPSEEK/KIMI/DOUBAO/GLM/ODDS_API）、`_agents_skills/`（Volcengine API 技能，Codex 使用）
- **全部数据**：`data/`（raw/processed/backups/xg/db/odds_history 等，含 ML 训练数据）、`models/`（预训练模型）、`strategy_data/`（全部联赛区间真值/odds/结算/复盘，含 J1 2026 新数据）、`analysis_records/`（全部历史分析记录）、`prediction_v2/output/`
- **策略文档**：`SOP_30STEP.md` / `OPERATION_GUIDE.md` / `SESSION_STATE.md` / `AGENTS.md` / `DATA_FORMATS.md`
- **附属项目**：`MatchPredict` / `WC2026_Dashboard-main` / `world-cup-2026-predictor` / `ai-football-prediction-engine-world-cup-2026` / `upset_engine_migration`
- **素材与归档**：`videos/`（视频素材）、`archive/`（旧版脚本归档）、`images/`
- **优化说明**：`data/backups/`（旧项目导出 zip，约 228MB 冗余）已排除；其余数据保持全量

## 部署步骤（目标电脑）
### 1. 环境要求
- Windows 10/11，Python 3.10+（64位），磁盘空间 ≥ 4GB

### 2. 解压部署
解压本 ZIP 到目标目录，例如 `D:\football_system`（注意：`MANIFEST.txt` 在压缩包根目录）

### 3. 一键部署验证
**推荐：双击 `一键部署.bat`**（自动检查 Python → 跑部署验证 → 打开使用流程）
或手动运行：
```bat
python setup_verify.py
```
脚本自动：检查 Python 版本 → 安装全部依赖 → 验证核心模块导入 → 验证数据文件 → 跑回归测试。看到 `🎉 全部通过` 即部署成功。

### 4. API 密钥
- `.env` 已随包携带（DEEPSEEK/DOUBAO/KIMI/GLM/FOOTBALL_API/ODDS_API）
- 若迁移到新账号/新机器：直接编辑 `.env` 替换为你的新 key 即可
- 免费接口（the-odds-api）注意配额，见 `prediction_v2/fetch_live_odds.py`

### 5. 日常使用流程（重要）
完整使用手册见 **`使用流程.md`**（部署→赛前分析→盘口抓取→投注纪律→赛后结算→质检防退化 一条龙）。
快速入口：
```bat
python auto_sop.py 比赛数据.json     :: 赛前分析(30步SOP)
python regression_test.py           :: 改代码后必跑质检
python prediction_v2/settle_live.py "A vs B 1-1"  :: 赛后结算
```

### 6. 开始使用
```bat
python auto_sop.py        :: 启动自动化SOP分析
python regression_test.py :: 回归质检（改代码后必跑）
cd prediction_v2 && python fetch_live_odds.py :: 全量抓取实时盘口
```

## 包内结构（顶层）
```
auto_sop.py / collect_strategy_data.py / regression_test.py / setup_verify.py
.env                        全部API密钥
MANIFEST.txt                包内文件清单
strategy_data/              策略数据(odds_zones/结算/复盘/J1 2026新数据)
prediction_v2/              the-odds-api抓取 + 预测输出(含output数据)
analysis_records/           全部历史分析记录(含J1第2轮半全场)
src/                        核心模块
models/                     预训练模型
data/                       ML训练数据全量
videos/                     视频素材(非运行必需)
archive/                    旧版脚本归档(仅供参考)
_agents_skills/             Volcengine API技能(Codex用)
MatchPredict/ WC2026_Dashboard-main/ 附属Web项目
```

## 注意事项
- `.env` 含 API 密钥，请勿上传公开仓库/泄露
- 回归测试必须全绿，这是系统正确性的质检闸门
- 修改任何分析逻辑后重跑 `python regression_test.py`
- 本包为全量包（约 700MB 压缩），如需精简可删除 `videos/`、`archive/`、`data/backups/` 后再打包
