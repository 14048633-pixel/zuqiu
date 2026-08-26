# WC2026 Dashboard - 项目概览

## 项目信息

- **名称**: World Cup 2026 Dashboard
- **作者**: AungCN
- **链接**: https://github.com/AungCN/WC2026_Dashboard
- **技术**: Python + Streamlit
- **许可**: MIT (免费使用)

## 功能页面

| 页面 | 功能 |
|------|------|
| 🟢 Live Scores | 实时比分、赛程、进球球员、小组排名 |
| 📰 News Feed | 最新世界杯新闻 (BBC, Guardian, ESPN) |
| 🔮 Match Predictions | 胜/平/负概率、最可能比分、红黄牌预测 |
| ⭐ Player Ratings | 48支球队球员评分预测 |

## 数据源 (全部免费)

| 数据源 | 提供数据 | 需要Key |
|--------|----------|---------|
| openfootball/worldcup.json | 赛程、比分 | ❌ |
| RSS新闻 | 最新文章 | ❌ |
| XGBoost模型 | 比赛预测 | ❌ |

## 目录结构

```
wc2026/
├── app.py                  ← 主入口
├── train_model.py          ← 训练模型 (可选)
├── pages/
│   ├── live_scores.py      ← 实时比分
│   ├── news_feed.py        ← 新闻聚合
│   ├── predictions.py      ← 比赛预测
│   └── player_ratings.py   ← 球员评分
└── utils/
    ├── api_client.py       ← 数据获取
    └── data_helpers.py     ← 辅助函数
```

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/AungCN/WC2026_Dashboard.git
cd WC2026_Dashboard/wc2026

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
streamlit run app.py
```

## ML模型

### XGBoost (比赛预测)

| 特征 | 说明 |
|------|------|
| FIFA排名差 | 球队实力对比 |
| 预期进球 (xG) | 进攻质量 |
| 历史交锋 | H2H记录 |
| 主场旅行疲劳 | 2026世界杯特色 |

### 自动训练

- 首次运行时自动训练
- 保存到 `models/saved/`
- 无需手动训练

## 与我们的系统对比

| 功能 | WC2026 Dashboard | 我们的系统 |
|------|------------------|------------|
| Streamlit界面 | ✅ | ✅ (app.py) |
| 实时比分 | ✅ | ✅ |
| 比赛预测 | ✅ | ✅ |
| xG数据 | ✅ | ✅ |
| 深度学习 | ❌ | ✅ (LSTM/Transformer) |
| 免费API | ✅ | ✅ (3个) |
| 多联赛支持 | ❌ (仅世界杯) | ✅ (五大联赛) |

## 集成建议

### 方案1: 直接使用

```bash
# 下载并运行
git clone https://github.com/AungCN/WC2026_Dashboard.git
cd WC2026_Dashboard/wc2026
pip install -r requirements.txt
streamlit run app.py
```

### 方案2: 集成我们的模型

```python
# 在 predictions.py 中添加

from final_system import FinalSystem

# 加载我们的模型
system = FinalSystem()
system.load_all()

# 替换预测函数
def predict_match(home, away):
    pred = system.predict_match(home, away)
    return {
        'home_win': pred['probabilities']['Home'],
        'draw': pred['probabilities']['Draw'],
        'away_win': pred['probabilities']['Away']
    }
```

### 方案3: 合并两个项目

```
football-prediction-system/
├── our_code/               # 我们的代码
├── wc2026_dashboard/       # WC2026 Dashboard
└── app.py                  # 统一入口
```

## 参考链接

- **项目**: https://github.com/AungCN/WC2026_Dashboard
- **在线演示**: 无 (需本地运行)
- **文档**: README.md
- **许可**: MIT
