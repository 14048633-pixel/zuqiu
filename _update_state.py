import io, datetime
p = r'SESSION_STATE.md'
src = io.open(p, encoding='utf-8').read()
add = """

## 08-24 伤停补拉 + 队名匹配修复（✅ 2026-08-24 23:2x）
- BSD match_package 补拉: 未来24h 34场中20场命中(伤停+教练+阵型), 8场BEST中6场有BSD伤停, 2场BSD无伤停记录(Reims/Sport), 1场BSD无事件(智利甲Everton)
- 修复 scan_upcoming.py 队名匹配bug: 快照 Atletico Paranaense vs BSD Athletico 不匹配导致 Botafogo 伤停包(主6/客4)注入失败
  - by_name 回退加 别名解析(_resolve_alias) + token子集匹配
  - by_name 改存候选列表, 优先"同一包同时匹配主客"(修 Botafogo 旧包223326 主伤4 顶掉 7224 的错配)
  - 结果: Botafogo λ 2.71->2.60, 方向 大2.50(EV+6.1)->小2.50(EV-2.4), BEST掉出; 9场->8场
- 标签语义: 有BSD伤停数据(任一侧>=1人)不再标"纯数据无伤病情报"; 仅BSD无事件/无伤停记录场次保留
- 备份: prediction_v2/scan_upcoming.py.bak_20260824_231600
- 回归: 900通过/1预存失败(best_bet占比>=25%)不变
- 最终BEST 8场: best9_next24h_20260824_2321.md; 扫描 scan_next24h_20260824_2321.json
- 额度告警: the-odds-api key 1/2/3/4/10/11 已401, 5~9号余量35~45次, 接近耗尽
"""
io.open(p, 'w', encoding='utf-8').write(src + add)
print('SESSION_STATE.md updated')
