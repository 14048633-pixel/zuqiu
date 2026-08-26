# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\SESSION_STATE.md"
lines = io.open(P, encoding="utf-8").read().split("\n")

new_block = [
"## J1 新规样本收集（✅ 2026-08-24, 3轮30场完整）",
"- **数据**: data/raw/football_data/j1_2026_results.csv 30场(8/7-8/23); ESPN主+BSD(league_id=49)双源对账完全一致(比分全同, 无漏场)",
"- **30场实测**: 场均3.20 / 大2.5=63.3% / 大3.5=43.3% / 双方进球63.3% / 主50%平20%客30% / 主队1.67客队1.53",
"- **分轮**: R1 3.60球/大球70% -> R2 3.10/70% -> R3 2.90/50%(明显回落); 20场基线3.35含R1高进球抬升",
"- **信号**: '客强主弱(主40客40)'不成立(30场主50/客30); 主场优势未消失; 平局率稳定20%; 大球中枢大概率在3.0-3.2",
"- **不调参**: 队样本仅~3场, 参数锁20场3.35; 已写入 j1_odds_zones.json calib_tracking_2026(.bak_20260824_j1_30w)",
"- **下一步**: 每周增量跑 prediction_v2/fetch_j1_results.py; 满60场(约第6轮)后重算 league_avg/rho 并回测",
"",
]

# 更新最近更新行
for i, ln in enumerate(lines):
    if ln.startswith("> 最近更新"):
        lines[i] = "> 最近更新：2026-08-24 23:50（J1 新规样本收集至 3 轮 30 场，双源对账一致，参数锁定待 60 场）"
        break

# 在第一个 "## " 节之前插入
insert_at = None
for i, ln in enumerate(lines):
    if ln.startswith("## "):
        insert_at = i
        break
if insert_at is not None:
    lines[insert_at:insert_at] = new_block
else:
    lines.extend(new_block)

io.open(P, "w", encoding="utf-8").write("\n".join(lines))
print("SESSION_STATE.md 已更新")
