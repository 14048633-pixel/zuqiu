# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
# 手工汇总（来源: API-Football 2026-08-20/21 两次调用 + LDU点球详情）
rows = [
 ('08-21 02:00','沙超','Al-Fayha','Al-Hilal','0-3','完赛'),
 ('08-21 02:30','友谊赛','Atlético Sanluqueño','Antoniano','?','API未收录'),
 ('08-21 03:00','英甲','Sheffield Wednesday','Bradford City','0-1','完赛'),
 ('08-21 06:00','南美杯','Olimpia','Vasco da Gama','1-4','完赛'),
 ('08-21 06:00','南美杯','Macará','Santos','0-0','完赛'),
 ('08-21 06:00','解放者杯','LDU Quito','Mirassol','0-0','点球5-4(主胜晋级)'),
 ('08-21 06:30','巴乙','Athletic Club','CRB','0-2','完赛'),
 ('08-21 07:00','哥伦杯','Real Cundinamarca','Int. Bogotá','-','延期(PST)'),
 ('08-21 07:00','哥伦杯','Atlético Nacional','Deportivo Cali','-','延期(PST)'),
 ('08-21 07:30','巴乙','Novorizontino','América Mineiro','3-0','完赛'),
 ('08-21 08:30','南美杯','Botafogo','Cienciano','?','进行中'),
 ('08-21 08:30','解放者杯','Corinthians','Rosario Central','?','进行中'),
]
out=['| 时间 | 联赛 | 对阵 | 比分 | 状态 |','|---|---|---|---|---|']
for r in rows:
    out.append('| {} | {} | {} vs {} | {} | {} |'.format(*r))
res='\n'.join(out)
print(res)
open('analysis_records/research/_remaining_summary.md','w',encoding='utf-8').write(res)
