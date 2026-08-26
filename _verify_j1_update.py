# -*- coding: utf-8 -*-
import io, json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(io.open(r"D:\足球分析\strategy_data\j1_odds_zones.json", encoding="utf-8"))
print("baseline.note:", d["baseline"]["note"][:100])
print()
t = d["calib_tracking_2026"]["cumulative_30"]
print("cum30:", {k: t[k] for k in ("games","goals","avg_goals","over25_pct","home_win_pct","draw_pct","away_win_pct")})
print("rounds:", list(d["calib_tracking_2026"]["rounds"].keys()))
s = io.open(r"D:\足球分析\SESSION_STATE.md", encoding="utf-8").read()
print()
print("SESSION 更新行:", [ln for ln in s.split(chr(10)) if ln.startswith("> 最近更新")][0][:80])
print("J1节存在:", "## J1 新规样本收集" in s)
