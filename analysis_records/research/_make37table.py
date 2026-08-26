# -*- coding: utf-8 -*-
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))

def leg_str(v):
    if v is True: return '✓'
    if v is False: return '✗'
    if v == 'push': return '走水'
    return str(v)

def line_of(k):
    m = re.search(r'\(([-+0-9.]+)\)', k)
    return m.group(1) if m else ''

def find(m, prefix):
    for k in m:
        if k.startswith(prefix):
            return k, m[k]
    return None, None

lines = ['| 时间 | 联赛 | 对阵 | 比分 | 平警 | 1X2 | 大小球 | 让球 | 星级 |',
         '|---|---|---|---|---|---|---|---|---|']
for m in d:
    ko, lg, h, a, sc = m['ko'], m['lg'], m['h'], m['a'], m['score']
    dw = '⚠️' if m.get('draw_warn') else ''
    x2 = ''
    for k in ('1X2主', '1X2客'):
        if k in m:
            x2 = ('主' if k == '1X2主' else '客') + leg_str(m[k])
    ou = ''
    for k in ('小球', '大球'):
        kk, v = find(m, k)
        if v is not None:
            ou = ('小' if k == '小球' else '大') + line_of(kk) + leg_str(v)
    hc = ''
    for k in ('让球主', '让球客'):
        kk, v = find(m, k)
        if v is not None:
            hc = ('主' if k == '让球主' else '客') + line_of(kk) + leg_str(v)
    star = ''
    if 'star_leg' in m:
        sl = m['star_leg']
        star = ('小' if '小' in sl[0] else '大') + str(sl[1]) + '★' + ('✓' if sl[2] else '✗')
    lines.append('| {} | {} | {} vs {} | {} | {} | {} | {} | {} | {} |'.format(ko, lg, h, a, sc, dw, x2, ou, hc, star))

open('analysis_records/research/_tonight37_table.md', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
