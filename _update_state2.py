import io
p = r'SESSION_STATE.md'
src = io.open(p, encoding='utf-8').read()
add = """

## 08-25 扫描主盘源切换 BSD consensus（✅ 2026-08-25 00:2x）
- 目标: the-odds-api 额度耗尽, 扫描不再依赖付费盘源; BSD consensus(免费无限) 为主盘源, the-odds 降为临场重拉专用
- 改动 scan_upcoming.py (备份 .bak_20260825_001914):
  1) _load_pkg_attacks rec 增加 consensus+pulled_at 字段, 有consensus即建by_name索引
  2) 新增 bsd_odds_merge(events): by_id/by_name(同包主客交集) 匹配 match_package, 覆盖 1X2 为 BSD 共识价, snap 刷新为包拉取时间
  3) 大小球仅当无 totals 时用 BSD 2.5 补缺(BSD 无多线, 覆盖会丢3.0线+抽水口径不同致EV失真: Neom大3.00消失/GilVicente误否决)
  4) 平局预警双源并集: h2h_prev 保留 the-odds, 去水平局取 max(BSD, the-odds), 防源切换阈值临界跳变(Reims 25.7 vs 26.6 → star 1↔3)
- 验证: 34场全量对比 旧the-odds vs 新BSD 方向/EV/星级/否决 0 差异; 回归 900通过/1预存失败不变
- 效果: 全量扫描零 the-odds 消耗; the-odds 仅临场重拉 BEST 场次(9/1重置11×500次/月)
- 亚盘缺口: BSD 无亚盘, 保持已有快照/缺亚盘标注; 出单确认用 API-Football 免费100次/天补
- 扫描: analysis_records/scan_next24h_20260825_0021.json; BEST: best9_next24h_20260825_0021.md
"""
io.open(p, 'w', encoding='utf-8').write(src + add)
print('SESSION_STATE.md updated')
