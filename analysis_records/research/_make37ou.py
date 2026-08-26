# -*- coding: utf-8 -*-
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
txt = open('analysis_records/tonight_37_full_directions.txt', encoding='utf-8').read()
blocks = txt.split('▶ ')
rows = []
for b in blocks[1:]:
    lines = b.strip().split('\n')
    header = lines[0]
    m = re.search(r'(\d\d-\d\d \d\d:\d\d) (\S+) (.+?) vs (.+?) \[λ', header)
    if not m: continue
    ko, lg, h, a = m.groups()
    ou_line = next((l for l in lines if l.startswith('  大小球')), None)
    bt_line = next((l for l in lines if l.startswith('  比分TOP')), None)
    if not ou_line: continue
    mm = re.search(r'大小球\s+(\S+)\s+(\d+)%@([\d.]+)\s+EV([+-][\d.]+)%', ou_line)
    if not mm: continue
    side, prob, odds, ev = mm.group(1), int(mm.group(2)), float(mm.group(3)), float(mm.group(4))
    top = bt_line.replace('比分TOP ', '') if bt_line else ''
    rows.append(dict(ko=ko, lg=lg, h=h, a=a, side=side, prob=prob, odds=odds, ev=ev, top=top))
for r in rows:
    for m in d:
        if m['h'] == r['h'] and m['a'] == r['a'] and m['ko'] == r['ko']:
            hit = None
            for k in m:
                if k.startswith(('小球','大球')):
                    hit = m[k]; break
            r['hit'] = hit
            r['star'] = m.get('star_leg')
            r['dw'] = m.get('draw_warn')
out = []
out.append('| 时间 | 对阵 | 比分 | 方向 | 概率 | 赔率 | EV | 星级 | 命中 | 比分TOP |')
out.append('|---|---|---|---|---|---|---|---|---|---|')
for r in sorted(rows, key=lambda x: x['ko']):
    star = ''
    if r['star']:
        sl = r['star']
        star = ('小' if '小' in sl[0] else '大') + str(sl[1]) + '★'
    hv = '' if r['hit'] is None else ('走水' if r['hit']=='push' else str(r['hit']))
    evs = ('%+.1f%%' % r['ev']) if r['ev'] >= 0 else ('%.1f%%' % r['ev'])
    dw = '⚠️' if r['dw'] else ''
    sidecell = r['side'] + dw
    cell = '| {} | {} vs {} | {} | {} | {}% | {} | {} | {} | {} | {} |'.format(
        r['ko'], r['h'], r['a'], r['side'], sidecell, r['prob'], r['odds'], evs, star, hv, r['top'])
    out.append(cell)
open('analysis_records/research/_tonight37_ou_table.md', 'w', encoding='utf-8').write('\n'.join(out))
print('\n'.join(out))
