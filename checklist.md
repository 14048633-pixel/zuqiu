# 预测流程数据清单

## 已使用 ✅

### 历史数据 (TeamStats)
- [x] 近10场胜负平
- [x] 场均进球/失球
- [x] 大2.5率
- [x] 双方进球率
- [x] 历史对阵 (H2H)

### 伤病数据 (DeepSeek)
- [x] 缺阵球员
- [x] 位置 (DEF/MID/FWD)
- [x] 影响程度 (HIGH/MEDIUM/LOW)
- [x] 关键球员缺阵数

### 阵型分析 (FormationModel)
- [x] 阵型对决
- [x] 进攻/防守/中场评分
- [x] 阵型优势

### 赔率
- [x] 主胜/平/客赔率
- [x] 隐含概率

### 模型预测
- [x] GoalExpert: 大小球
- [x] FormExpert: 胜平负

---

## 未使用 ❌

### MLS数据中有但没用的
- [ ] 半场比分 (home_goals_ht, away_goals_ht)
- [ ] 射门/射正 (home_shots_total, etc.)
- [ ] 角球 (home_corners, etc.)
- [ ] 黄牌/红牌 (home_yellow_cards, etc.)
- [ ] xG (home_xg, away_xg) ← 赛后数据，不能提前知道
- [ ] 控球率 (home_possession, etc.)
- [ ] 犯规 (home_fouls, etc.)
- [ ] 越位 (home_offsides, etc.)
- [ ] 传球成功率 (home_pass_accuracy, etc.)

### 欧洲数据中有但没用的
- [ ] Elo评分 (home_elo, away_elo)
- [ ] 近3/5/10场状态 (w3, w5, w10系列)
- [ ] 衰减权重 (decay系列)
- [ ] 强度调整 (sos系列)
- [ ] 休息天数 (rest_days)
- [ ] 密集赛程 (congestion_7d, 14d)
- [ ] 清洁_sheet率 (clean_sheet_rate_decay)
- [ ] 主客场进球差异 (gf_home, gf_away)

### 完全没有的数据
- [ ] 天气条件
- [ ] 旅行距离
- [ ] 动机 (保级/争冠/无欲无求)
- [ ] 教练变化
- [ ] 球迷氛围
- [ ] 裁判数据

---

## 优先级建议

### 高优先级 (应该加入)
1. **半场比分** - 中场休息时可获得，影响下半场预测
2. **射门数据** - 反映进攻威胁
3. **角球/犯规** - 反映比赛节奏
4. **休息天数** - 体能影响
5. **主客场差异** - 主队主场进球 vs 客队客场失球

### 中优先级 (可选)
6. Elo评分 - 长期实力
7. 近3/5/10场细分状态
8. 清洁_sheet率

### 低优先级 (难以获取)
9. 天气
10. 旅行距离
11. 动机
12. 教练变化
