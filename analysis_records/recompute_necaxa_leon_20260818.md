# Necaxa vs León — form_score 重算（BSD 数据覆盖）

日期: 2026-08-18 | 模型: LSTM v2 (lstm_form_model_v2.npz)

## 做了什么
1. 从 BSD /api/v2/events/{id}/stats/ 拉取两队最近场次的逐场射门/射正/xG（14 场，墨超 league 19/20）
2. 覆盖层: form_phase0/bsd_mx_overrides.json
3. 去重: 本地历史池同场双源重复行清掉 10 行
4. 填充: 7 行原本全 0 的射门/xG 替换为 BSD 真实值

## 结果
| 队伍 | 旧 form | 新 form | 变化 | 说明 |
|---|---|---|---|---|
| Club Necaxa (主) | 0.333 | 0.396 | +0.063 | 近5场从全0补齐真实数据, 状态仍偏低 |
| Club León (客) | 0.608 | 0.645 | +0.037 | xG部分换源微调, 状态依旧强势 |

差异: -0.275 -> -0.249 (客队仍明显占优)

## 数据质量影响
- 旧 0.333 被"近5场射门/xG 全缺填0"严重压低, 属于数据缺失假象
- 新 0.396 基于真实射门: 07-17(2-1, xG2.42) / 07-26(2-1, xG3.0) 进攻不差, 08-03 客场 1-3 拖累
- León 0.645 数据完整度最高, 可信度高于 Necaxa

## 文件
- 覆盖层: form_phase0/bsd_mx_overrides.json
- 重算脚本: form_phase0/_recompute_form_bsd.py (独立运行, 不污染 analyze_48h_v2)
