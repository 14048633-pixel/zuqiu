import io
p = r'SESSION_STATE.md'
src = io.open(p, encoding='utf-8').read()
add = """

## 08-25 临场盘特征验证 + 只拉BEST临场盘（✅ 2026-08-25 00:5x）
- 回测(无泄漏重放, 复用 _replay_adj): 账本已结算BEST场次, 每场重放 最早赛前快照(早盘) vs 最晚赛前快照(临场)
- 结果: 临场有效盘(<=12h) BEST出单 27场 命中66.7% ROI+28.8%; 强临场(<=3h) 19场 63.2%/+24.7%;
  早盘过期->临场救回 22场 命中72.7% ROI+40.7% (对照 历史★出单51.9%/+0.3%)
- 结论: 临场盘特征有效(命中+15pp/ROI+28pp), 最大价值在救回被过期否决的好场次; 样本小需继续积累
- 关键背景: 历史快照大多距开赛100h+(早盘几乎全被盘口过期否决), 真临场盘此前稀缺
- 落地: prediction_v2/_pull_best_live.py 只拉BEST场次临场盘(BSD免费consensus现场fetch), 重算BEST腿EV
  - 今日8场: 6确认(Neom+50.1近似3.5线/Osasuna+23.7/Roma+9.6/Reims+22.2/GilVicente+41.5), 1掉出(Malmo小2.50 +12.8->-19.8), 1缺盘(Sport), 1无BSD(Everton)
  - 注意: 大3.00用BSD over_35(3.5线)近似已标注; 亚盘BSD无, 需API-Football补
- 文件: _replay_live_feature.py + _replay_live_feature_out.json; best_live_confirm_*.json; live_feature_report_20260825.md
- 下一步: 账本加 live_ev/delta_ev/live_snap 字段, 结算后按 临场确认vs掉出 分组验证
"""
io.open(p, 'w', encoding='utf-8').write(src + add)
print('SESSION_STATE.md updated')
