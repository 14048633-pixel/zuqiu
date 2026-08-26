# -*- coding: utf-8 -*-
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
txt = open('analysis_records/tonight37_ledger_detail.txt', encoding='utf-8').read()
blocks = txt.split('▶ ')
rows = []
for b in blocks[1:]:
    lines = [l for l in b.strip().split('\n') if l.strip()]
    header = lines[0]
    m = re.search(r'(\d\d-\d\d \d\d:\d\d) (\S+) (.+?) vs (.+?)$', header)
    if not m: continue
    ko, lg, h, a = m.groups()
    for l in lines[1:]:
        mm = re.match(r'\s+(小球|大球)\(([-+0-9.]+)\)\s+概率(\d+)%\s+赔率([\d.]+)\s+EV([+-][\d.]+)%\s*(★\d+)?', l)
        if mm:
            side, line, prob, odds, ev = mm.group(1), mm.group(2), int(mm.group(3)), float(mm.group(4)), float(mm.group(5))
            star = mm.group(6) or ''
            rows.append(dict(ko=ko, lg=lg, h=h, a=a, side=side, line=line, prob=prob, odds=odds, ev=ev, star=star))
for r in rows:
    for m in d:
        if m['h'] == r['h'] and m['a'] == r['a'] and m['ko'] == r['ko']:
            for k in m:
                if k.startswith((r['side'],)):
                    r['hit'] = m[k]; break
            r['dw'] = m.get('draw_warn')
            r['score'] = m['score']
out = []
out.append('| 时间 | 对阵 | 比分 | 方向 | 概率 | 赔率 | EV | 星级 | 命中 |')
out.append('|---|---|---|---|---|---|---|---|---|')
for r in sorted(rows, key=lambda x: x['ko']):
    hv = '' if r.get('hit') is None else ('走水' if r['hit']=='push' else str(r['hit']))
    evs = ('%+.1f%%' % r['ev']) if r['ev'] >= 0 else ('%.1f%%' % r['ev'])
    sidecell = ('小' if r['side']=='小球' else '大') + r['line']
    if r.get('dw'): sidecell += '⚠️'
    out.append('| {} | {} vs {} | {} | {} | {}% | {} | {} | {} | {} |'.format(
        r['ko'], r['h'], r['a'], r['score'], sidecell, r['prob'], r['odds'], evs, r['star'], hv))
open('analysis_records/research/_tonight37_ou_ledger.md', 'w', encoding='utf-8').write('\n'.join(out))
print('\n'.join(out))
print()
# 统计
n=len(rows)
wins=[r for r in rows if r.get('hit')==True]
lose=[r for r in rows if r.get('hit')==False]
push=[r for r in rows if r.get('hit')=='push']
small=[r for r in rows if r['side']=='小球']
big=[r for r in rows if r['side']=='大球']
starred=[r for r in rows if r['star']]
sw=[r for r in small if r.get('hit')==True]; bw=[r for r in big if r.get('hit')==True]
ss=[r for r in starred if r['side']=='小球']; bs=[r for r in starred if r['side']=='大球']
ssw=[r for r in ss if r.get('hit')==True]; bsw=[r for r in bs if r.get('hit')==True]
ev_pos=[r for r in rows if r['ev']>0]
ev_pos_w=[r for r in ev_pos if r.get('hit')==True]
ev_neg=[r for r in rows if r['ev']<=0]
ev_neg_w=[r for r in ev_neg if r.get('hit')==True]
print('=== 统计 ===')
print('总腿:',n,' 命中:',len(wins),' 未中:',len(lose),' 走水:',len(push))
print('小球:',len(small),'命中',len(sw),f'({len(sw)/len(small):.0%})',' 大球:',len(big),'命中',len(bw),f'({len(bw)/len(big):.0%})')
print('星级:',len(starred),'命中',len([r for r in starred if r.get("hit")==True]))
print('  小球星级:',len(ss),'命中',len(ssw),f'({len(ssw)/len(ss):.0%})',' 大球星级:',len(bs),'命中',len(bsw),f'({len(bsw)/len(bs):.0%})')
print('EV>0:',len(ev_pos),'命中',len(ev_pos_w),f'({len(ev_pos_w)/len(ev_pos):.0%})',' EV<=0:',len(ev_neg),'命中',len(ev_neg_w),f'({len(ev_neg_w)/len(ev_neg):.0%})')
# 星级大球明细
print('星级大球:',[(r['h']+' vs '+r['a'],r['score'],r['hit']) for r in bs])
print('星级小球未中:',[(r['h']+' vs '+r['a'],r['score'],r['ev']) for r in ss if r.get('hit')!=True])
