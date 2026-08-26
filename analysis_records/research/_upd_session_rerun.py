import io, json
p = r"D:\足球分析\SESSION_STATE.md"
src = io.open(p, encoding="utf-8").read()
new_block = """# 会话状态

> 最近更新：2026-08-21 23:10（08-22 凌晨 27 场最新赔率完整重算）

## 08-22 凌晨 27 场 完整重算（✅ 本次完成, 2026-08-21 晚）
- 任务: 用最新赔率(odds_live_0822_matched_final.json, pulled=2026-08-21T14:34:28Z)重跑完整模型链, 不再用"旧概率×新赔率"近似
- 方法: 新赔率 -> `analysis_records/research/snapshots_live_0822.csv`(6300行, 与snapshots.csv同格式) -> `scan_upcoming.parse_snapshots` + `analyze_match` 完整重算(含λ/WDL/封顶/EV/星级/硬否决)
- 结果: 27场 -> 出单11场 / 正EV 22场 / 硬否决7场(模型vs市场分歧>20pp)
- 出单Top: SJK小2.50 +35.5%★2｜Cherno More让球客+27.1%★3｜Betis让球主-0.5 +24.4%★1｜Hansa大3.50 +22.3%｜Córdoba让球主+20.8%★2
- 硬否决(EV>5%但分歧): Dunkerque让球客+24.5% / Tondela+22.0% / Arsenal+21.2% / Erzurumspor+19.8% / Jaguares+17.2% / Estudiantes+15.8% / Pau+12.4%
- 输出: `analysis_records/research/rerun_0822_live.json` + `rerun_0822_live.md`(678行完整链路)
- 回归: 736/0 全绿
"""
# 只替换第一个 "# 会话状态" 到第一个 "## " 之间的头部
i = src.find("# 会话状态")
j = src.find("\n## ", i)
src = src[:i] + new_block.rstrip() + "\n" + src[j:]
io.open(p, "w", encoding="utf-8").write(src)
print("SESSION_STATE updated")
