# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"D:\足球分析\strategy_data\j1_odds_zones.json"
d = json.load(io.open(P, encoding="utf-8"))

d["updated"] = "2026-08-24"

# 30 场实测数据
d["calib_tracking_2026"] = {
    "note": "新赛季逐轮实测追踪(累计至2026-08-24, 3轮30场). 参数仍锁20场3.35上限; 60场后再重算 league_avg/rho/主客系数",
    "rounds": {
        "R1(8/7-9)": {"games": 10, "avg_goals": 3.60, "over25_pct": 70, "hw/dr/aw": [5, 1, 4]},
        "R2(8/14-15)": {"games": 10, "avg_goals": 3.10, "over25_pct": 70, "hw/dr/aw": [3, 3, 4]},
        "R3(8/21-23)": {"games": 10, "avg_goals": 2.90, "over25_pct": 50, "hw/dr/aw": [7, 2, 1]}
    },
    "cumulative_30": {
        "games": 30, "goals": 96, "avg_goals": 3.20,
        "home_goals_avg": 1.67, "away_goals_avg": 1.53,
        "over25_pct": 63.3, "over35_pct": 43.3, "btts_pct": 63.3,
        "home_win_pct": 50.0, "draw_pct": 20.0, "away_win_pct": 30.0
    },
    "signals": [
        "R3 场均2.90/大球50% 明显回落 -> 前两轮(3.60/3.10)抬高基线, 3.35 含高估成分, 新规大球中枢更可能在 3.0-3.2",
        "主胜50%/客胜30% 与 20场样本'客强主弱(主40客40)'相反 -> 主场优势未消失, 客强结论待证伪",
        "平局率 20% 稳定(6/30), 与基线一致",
        "比分集中 2-1(4)/0-1(3)/1-1(3)/1-0(3), 中位数3球",
        "队样本: 每队仅~3场(主场~1.5), 队级攻防不可用, 只可用联赛级基准"
    ],
    "action": "每周随轮次增量拉取(fetch_j1_results.py); 满60场(约第6轮)后重算 league_avg/rho 并回测验证"
}

# baseline note 更新(参数不动)
b = d.get("baseline", {})
b["note"] = ("2026-27新赛季累计30场实测(8/7-8/23): 场均3.20, 大2.5=63.3%, 主50/平20/客30; "
             "参数仍锁20场3.35作压力上限, 前10轮校准期, 60场后重算")
b["rule_basis_2026"] = ("2026-27跨年正式赛季累计30场实测(8/7-8/23), 当前唯一有效基准; "
                        "20场3.35已含R1高进球抬升, 30场回落到3.20, 见 calib_tracking_2026")
d["baseline"] = b

# metadata note
m = d.get("metadata", {})
m["note"] = "近3赛季+2026过渡赛季, sample_n为估算; 2026-08-21 冻结旧区间, 2026-08-24 更新至30场实测追踪(calib_tracking_2026), 满60场再重算"
m["rule_basis"] = ("旧规则样本(2023-2025自然年18队 + 2026过渡赛季分区制)。2026-27跨年新规(20队/外援5人/取消U23强制/VAR点球收紧)下, "
                   "旧区间真值前10-15轮校准期禁用; baseline 累计30场实测(3.20/大球63.3%)为当前参考, 参数锁20场3.35")
d["metadata"] = m

io.open(P, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
print("已更新 j1_odds_zones.json: updated=%s, calib_tracking_2026 已写入" % d["updated"])
