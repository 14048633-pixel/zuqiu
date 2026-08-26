# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout.reconfigure(encoding='utf-8')
d37 = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
def leg(m, prefix):
    for k in m:
        if k.startswith(prefix):
            v = m[k]
            return (k.split('(')[1].rstrip(')') if '(' in k else ''), ('✓' if v is True else ('✗' if v is False else '走水'))
    return '', ''
def find_star(m):
    sl = m.get('star_leg')
    if not sl: return ''
    return ('小' if '小' in sl[0] else '大') + str(sl[1]) + '★' + ('✓' if sl[2] else '✗')
rows=[]
for m in d37:
    _,x2 = leg(m,'1X2')
    ou,ouh = leg(m, ('小球' if any(k.startswith('小球') for k in m) else '大球'))
    hc,hch = leg(m,'让球')
    rows.append([m['ko'], m['lg'], m['h'], m['a'], m['score'], '⚠️' if m.get('draw_warn') else '', x2, ouh, hch, find_star(m)])
# 4场今天
rows.append(['08-21 08:30','南美杯','Botafogo','Cienciano','1-0','','✗(平局)','✓(小2.5)','✓(客+2.5)',''])
rows.append(['08-21 08:30','解放者杯','Corinthians','Rosario Central','1-0','','✗(客胜)','✓(小2.5)','✗(客+0.2)',''])
rows.append(['08-21 18:00','J1','Kashiwa Reysol','V-Varen Nagasaki','4-2','','✗(客胜)','✓(大2.5)','-',''])
rows.append(['08-21 18:30','J1','FC Tokyo','JEF United Chiba','2-0','','✗(客胜)','✗(大2.5)','-',''])
rows.sort(key=lambda r: r[0])
out=['# 08-21 统一对账表（41场）','','| 时间 | 联赛 | 主队 | 客队 | 比分 | 平警 | 1X2 | 大小球 | 让球 | 星级 |','|---|---|---|---|---|---|---|---|---|---|']
for r in rows:
    out.append('| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |'.format(*r))
res='\n'.join(out)
open('analysis_records/research/unified_settle_0821_41.md','w',encoding='utf-8').write(res)
print('已保存: analysis_records/research/unified_settle_0821_41.md  (%d场)' % len(rows))
print(res)
