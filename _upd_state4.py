# -*- coding: utf-8 -*-
import io
ROOT = r"D:\足球分析"
fp = ROOT + r"\SESSION_STATE.md"
txt = io.open(fp, encoding="utf-8").read()
marker = "## 当前进度："
section = """## v3 λ 集成验证（✅ 本次完成, 2026-08-18 深夜）

### 结论：v3 暂不替换 raw λ 作 EV 主引擎
- 接入 46/46 覆盖；1X2 EV>5%：旧14 → v3 final 22 / euro 19
- **10 场 EV>50% 假正，多数逆市场方向**：Getafe/Partizan 客胜 EV+285%（市场主1.27/客10.69）、Motherwell/Freiburg 主胜 EV+109%、Górnik/Monaco 主胜 EV+87%
- 根因：①v2 收缩拉平精英防守（Getafe 主场失球 0.72→0.96）②融合压缩强度差（Partizan 客防 1.52→0.92）③跨联赛相对评级无法正确复合（西甲 vs 塞超差距 > coef 1.0 vs 0.88）
- 旧模型同样压缩（Getafe 主胜仅 41% vs 市场 75%），v3 加剧
- v3 价值保留：数据覆盖补齐 46/46 + 同联赛预测 + 交叉验证/风险信号
- 中期修复：跨联赛 level-gap 校准（λ × (对手coef/本队coef)²）+ 放开收缩 K（精英防守少拉向均值）
- 报告：`analysis_records/key46_v3_lambda_validate_20260818.md`；明细：`key46_v3_lambda_20260818_2357.json`

"""
if marker in txt:
    txt = txt.replace(marker, section + marker, 1)
old_line = None
for line in txt.splitlines():
    if line.startswith("> 最近更新"):
        old_line = line
        break
if old_line:
    txt = txt.replace(old_line, "> 最近更新：2026-08-19 凌晨（v3 λ 集成验证完成：46/46 覆盖但跨联赛压缩失真，v3 暂作数据覆盖/交叉验证，不替换 raw λ 主引擎）", 1)
io.open(fp, "w", encoding="utf-8").write(txt)
print("SESSION_STATE.md updated")
