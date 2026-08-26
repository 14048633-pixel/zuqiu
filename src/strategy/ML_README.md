# 大小球ML模型说明文档

## 一、模型概述

### 1.1 模型类型
- **类型**：增强版规则+统计模型
- **输入**：比赛特征（xG、射门、赔率等）
- **输出**：总进球数预测、大/小球概率、信心等级

### 1.2 模型文件
- `over_under_ml.py` - ML大小球预测模型
- `betting_strategy.py` - 完整策略引擎

---

## 二、模型架构

### 2.1 特征工程

| 特征 | 说明 | 权重 |
|------|------|------|
| total_xg | 总预期进球 | 高 |
| xg_diff | 预期进球差 | 中 |
| total_shots | 总射门数 | 中 |
| shots_diff | 射门差 | 低 |
| total_shots_on_target | 总射正 | 高 |
| home_possession | 主场控球率 | 低 |
| odds_home/draw/away | 赔率 | 中 |

### 2.2 预测逻辑

```python
1. 计算联赛场均进球
2. ML模型预测总进球数
3. 规则模型判断盘口与联赛平均的关系
4. 综合两者给出推荐
5. 计算期望值和信心等级
```

### 2.3 信心等级计算

| 条件 | 信心 |
|------|------|
| 预测与盘口差距>1球 | ⭐⭐⭐⭐⭐ |
| 预测与盘口差距>0.75球 | ⭐⭐⭐⭐ |
| 预测与盘口差距>0.5球 | ⭐⭐⭐ |
| 预测与盘口差距>0.25球 | ⭐⭐ |
| 预测与盘口差距≤0.25球 | ⭐ |

---

## 三、使用示例

### 3.1 基础使用

```python
from over_under_ml import EnhancedOverUnderModel

model = EnhancedOverUnderModel()

result = model.predict(
    league="中超",
    ou_line=3.0,
    ou_odds_over=1.84,
    ou_odds_under=2.00,
    home_xg=1.2,
    away_xg=0.8,
)

print(f"推荐: {result['recommendation']}")
print(f"预测总进球: {result['predicted_total_goals']}")
print(f"大2.5概率: {result['over25_prob']:.1%}")
print(f"信心: {'⭐' * result['confidence']}")
```

### 3.2 输出说明

```python
{
    "recommendation": "小球",           # 推荐方向
    "confidence": 4,                    # 信心等级(1-5)
    "predicted_total_goals": 2.3,       # 预测总进球数
    "over25_prob": 0.434,              # 大2.5球概率
    "under25_prob": 0.566,             # 小2.5球概率
    "over35_prob": 0.215,              # 大3.5球概率
    "under35_prob": 0.785,             # 小3.5球概率
    "league_avg": 2.6,                 # 联赛场均进球
    "line_ratio": 1.15,                # 盘口/联赛场均比值
    "expected_value": 0.341,           # 期望值
    "features_used": ["total_xg", ...] # 使用的特征
}
```

---

## 四、测试结果

### 4.1 河南队 vs 大连英博（中超）
- **推荐**: 小球
- **预测总进球**: 2.3球
- **大2.5概率**: 43.4%
- **小2.5概率**: 56.6%
- **信心**: ⭐⭐⭐⭐
- **期望值**: 34.1%

### 4.2 迈阿密国际B vs 查塔努加（MLS Next Pro）
- **推荐**: 观望
- **预测总进球**: 3.06球
- **大2.5概率**: 68.0%
- **小2.5概率**: 32.0%
- **信心**: ⭐
- **期望值**: 0.0%

---

## 五、待改进

| 项目 | 说明 | 优先级 |
|------|------|--------|
| 加入球队历史数据 | 近期进/失球 | 高 |
| 加入主客场差异 | 主场进球多10% | 中 |
| 使用sklearn训练 | 更精确的模型 | 高 |
| 加入天气因素 | 雨天进球少 | 低 |
| 加入伤病信息 | 关键球员缺阵 | 低 |

---

## 六、集成到策略引擎

```python
from betting_strategy import StrategyEngine, MatchType
from over_under_ml import EnhancedOverUnderModel

# 初始化
engine = StrategyEngine()
ml_model = EnhancedOverUnderModel()

# ML预测
ml_result = ml_model.predict(
    league="中超",
    ou_line=3.0,
    ou_odds_over=1.84,
    ou_odds_under=2.00,
    home_xg=1.2,
    away_xg=0.8,
)

# 策略引擎分析
analysis = engine.analyze_match(
    match_name="河南队 vs 大连英博",
    league="中超",
    match_type=MatchType.DOMESTIC,
    odds_home=1.80,
    odds_draw=3.85,
    odds_away=3.65,
    ou_line=3.0,
    ou_odds_over=1.84,
    ou_odds_under=2.00,
    hdp_line=-0.5,
    hdp_odds_home=1.80,
    hdp_odds_away=2.06,
)

# 综合判断
if ml_result['recommendation'] == analysis.ou_recommendation.value:
    print("ML和策略引擎一致，高信心推荐")
else:
    print("ML和策略引擎不一致，需人工判断")
```
