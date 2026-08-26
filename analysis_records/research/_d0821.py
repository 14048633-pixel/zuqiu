# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout.reconfigure(encoding='utf-8')
# 08-21 预测窗口内 4 场方向（01:53 ah5 快照） + 结果
rows = [
 # 场次, 联赛, 方向摘要, 预测方向, 实际比分, 对账
 ('08:30','南美杯','Botafogo vs Cienciano','OU小2.5 53% EV+103% 否决 | HC客+2.5 EV+24% | 1X2平局24% EV+213%','1-0','FT'),
 ('08:30','解放者杯','Corinthians vs Rosario Central','OU小2.5 65% EV-12% | HC客+0.2 EV+18% | 1X2客胜28% EV+14% 否决','1-0','FT'),
 ('18:00','J1','Kashiwa vs Nagasaki','OU大2.5 58% EV-4% | 1X2客胜37% EV+72% [垃圾]','1-0','FT'),
 ('18:30','J1','FC Tokyo vs Chiba','OU大2.5 58% EV+0% | 1X2客胜37% EV+108% [垃圾]','1-0','FT'),
]
out=['| 时间 | 联赛 | 对阵 | 预测方向 | 比分 |','|---|---|---|---|---|']
for r in rows:
    out.append('| {} | {} | {} | {} | {} |'.format(*r))
res='\n'.join(out)
print(res)
open('analysis_records/research/_d0821_results.md','w',encoding='utf-8').write(res)
# 对账
print()
print('== 对账 ==')
# Botafogo 1-0: 小2.5✓(1球), 1X2平局✗(主胜), HC客+2.5✓(客队0失球? +2.5 客队盘 1-0 => 客+2.5 赢盘✓)
print('Botafogo 1-0: 小球✓ | 1X2平局✗ | 让球客+2.5✓')
# Corinthians 1-0: 小2.5✓, 1X2客胜✗(主胜), HC客+0.2: 客队0.2 受让 1-0 => 客-0.2? 客+0.2 输✗
print('Corinthians 1-0: 小球✓ | 1X2客胜✗ | 让球客+0.2✗')
# J1 两场 1-0: 大球✗, 1X2客胜✗(主胜)
print('Kashiwa 1-0: 大球✗ | 1X2客胜✗')
print('FC Tokyo 1-0: 大球✗ | 1X2客胜✗')
