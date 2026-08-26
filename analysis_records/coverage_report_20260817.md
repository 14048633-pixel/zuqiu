# 数据覆盖缺口报告 (2026-08-17)

- 球队目录 team_catalog.json: 1070 条 (含别名 136 条, 联赛映射 66 条)
- BSD 历史攻防兜底: 142 队 / 905 场 (保甲+希腊超+欧冠)
- BSD 队名未匹配攻防数据: 347 个

## 未匹配分布(按推测国家/联赛)
- 其他/未分类: 191
- 美国USL: 69
- 日本下位: 25
- 沙特: 15
- 保加利亚: 12
- 罗马尼亚: 7
- 波兰: 7
- 突尼斯: 7
- 希腊: 6
- 克罗地亚: 5
- 葡萄牙低级别: 3

## 欧冠资格赛 12 场关键覆盖
- Levski Sofia / AEK Athens: BSD保甲/希腊超攻防已接入 ✔
- GNK Dinamo Zagreb: BSD欧冠历史攻防已接入 ✔ (克罗地亚联赛无独立源)
- Viking FK: 挪超ESPN数据 ✔
- 教练缓存: 22位中20位覆盖, 缺口=Guido Pagliuca(Empoli)/Alessandro Diamanti(Cesena)
- 伤停: BSD有名单但位置大多未知(伤停球员不在预测首发), 需squad补位

## 待办
- 教练缓存补拉: Empoli/Cesena 两客帅(BSD managers按联赛拉取)
- 伤停位置: 从BSD squad接口按球员id补位(已评估, 缓存不齐)
- the-odds-api 额度: 剩1请求, 下月恢复; 当前盘口源=BSD consensus