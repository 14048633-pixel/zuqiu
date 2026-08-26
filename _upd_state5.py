# -*- coding: utf-8 -*-
import io
p = r"D:\足球分析\SESSION_STATE.md"
s = io.open(p, encoding="utf-8").read()
add = """
## 大小球 同向/反向 实盘验证（2026-08-19, 74场已结算）
- 数据: 08-14~08-19 已完赛, scan模型OU概率+市场赔率+BSD赛果核对, 平注模型方向@市场赔率
- 全量74场: 命中55.4% ROI+2.9%
- 模型=市场同向(n46): 命中56.5% ROI-7.4% ← 跟市场方向不赚钱(水钱吃掉)
- 模型逆市场反向(n28): 命中53.6% ROI+19.8% ← 反向拿高赔
- 模型大球(n39): 命中64.1% ROI+19.0% ← 价值方向; 模型小球(n35): 45.7% ROI-15.1% ← 亏损方向
- 08-18那批16/20=80%为20场小样本+全同向运气; 拉长后同向仅56.5%
- 结论: OU记方向优先模型大球(尤其反向大); 小球方向降权; 待300场再定联赛名单
- 产物: analysis_records/ou_same_opp_settled_20260819.json/.md, _ou_same_opp_roi.py
"""
if "## 大小球 同向/反向 实盘验证" not in s:
    io.open(p, "w", encoding="utf-8").write(s + add)
    print("SESSION_STATE updated")
else:
    print("already exists")
