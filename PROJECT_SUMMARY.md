# 足球竞猜模型训练 - 项目总结

## 项目概述
基于机器学习的足球竞猜预测系统，结合实时赔率比较和多模型集成。

## 核心成果

### 1. 模型性能
| 模型 | 准确率 | 用途 |
|------|--------|------|
| 友谊赛模型 | 76.6% | 友谊赛1X2预测 |
| Over/Under | 59.70% | 大小球预测 |
| BTTS | 56.83% | 双方都进球预测 |
| 荷甲模型 | 55.95% | 联赛1X2预测 |

### 2. 投注策略
- **串关组合**: 2串1/3串1提高边际
- **价值投注**: 只在边际>5%时下注
- **分散风险**: 多联赛、多类型投注

### 3. 关键发现
1. 友谊赛模型准确率最高(76.6%)
2. Over/Under模型ROI最高(+40.60%)
3. 串关可以显著提高边际(从11%到24-38%)
4. 特征工程需要谨慎，添加更多特征不一定提高准确率

## 文件结构

### 核心脚本
- `train_friendly.py` - 训练友谊赛模型
- `train_advanced.py` - 高级模型训练(Over/Under, BTTS)
- `friendly_betting.py` - 友谊赛投注分析
- `parlay_betting.py` - 串关组合分析
- `live_betting_multi.py` - 多联赛实时投注

### 数据文件
- `data/raw/friendlys/club_friendlies_3.csv` - 462场友谊赛数据
- `data/raw/football_data/matches_2015_2025.csv` - 历史比赛数据
- `data/raw/football_data/football_data_recent.csv` - 最新比赛数据

### 模型文件
- `models/friendly_model.pkl` - 友谊赛模型
- `models/advanced_ou.pkl` - Over/Under模型
- `models/advanced_btts.pkl` - BTTS模型

### 投注记录
- `data/bets/bet_tracking.json` - 投注跟踪
- `data/bets/parlay_bets_20260724.json` - 今日串关投注

## 使用的工具
- **XGBoost**: 主要机器学习模型
- **Optuna**: 超参数优化
- **InferSports**: 实时赔率数据
- **Elo评分**: 球队实力评估

## 下一步计划
1. 跟踪今日投注结果
2. 优化模型参数
3. 扩展到更多联赛
4. 建立自动化投注系统

## 项目路径
`D:\ai\电脑庄家\足球竞猜模型训练`

## 导出文件
`data/project_export_20260724.zip` (230MB)
