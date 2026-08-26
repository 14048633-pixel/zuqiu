# -*- coding: utf-8 -*-
import sys, io, os, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:\足球分析'
scan = json.load(io.open(os.path.join(ROOT,'analysis_records','scan_next24h_20260825_1644.json'), encoding='utf-8'))
res  = json.load(io.open(os.path.join(ROOT,'analysis_records','results_scan_20260826_final2.json'), encoding='utf-8'))
res_by = {(r.get('home'), r.get('away')): r for r in res}
FINAL = ('post','finished','FT','AET','PEN')

def settle(leg, h, a):
    name = leg.get('name') or ''
    total = h + a
    if name.startswith('大') or name.startswith('小'):
        line = float(re.sub(r'[^0-9.]','', name.replace('大','').replace('小','')))
        r = ('win' if total > line else ('push' if total == line else 'lose')) if name.startswith('大') else ('win' if total < line else ('push' if total == line else 'lose'))
    elif name.startswith('1X2'):
        if '主胜' in name: r = 'win' if h > a else ('push' if h==a else 'lose')
        elif '客胜' in name: r = 'win' if h < a else ('push' if h==a else 'lose')
        else: r = 'win' if h==a else 'lose'
    else:
        return None
    odds = float(leg.get('odds') or 0)
    ret = {'win': odds, 'push': 1.0, 'lose': 0.0}[r]
    return r, round(ret-1,4), total

rows=[]
for m in scan:
    rr = res_by.get((m.get('home'), m.get('away')))
    score_s = rr.get('score') if rr else None
    status = rr.get('status') if rr else None
    base = dict(m)
    if not score_s:
        rows.append(dict(base, _tag='无数据')); continue
    try: h,a = map(int, score_s.split('-'))
    except Exception: h=a=0
    base['_h'], base['_a'], base['_score'], base['_status'] = h, a, score_s, status
    leg = m.get('best_bet'); is_best=True
    if not leg:
        d=m.get('direction'); dv=m.get('dir_ev') or 0
        if not d or dv<=0:
            rows.append(dict(base, _tag=('终局无腿' if status in FINAL else 'LIVE无腿'))); continue
        leg = next((b for b in (m.get('bets') or []) if b.get('name')==d), None)
        is_best=False
        if not leg:
            rows.append(dict(base, _tag=('终局无腿' if status in FINAL else 'LIVE无腿'))); continue
    if status in FINAL:
        s = settle(leg, h, a)
        if s is None:
            rows.append(dict(base, _tag='终局无腿')); continue
        r,pnl,total = s
        rows.append(dict(base, _leg=leg, _is_best=is_best, _res=r, _pnl=pnl, _total=total, _tag='终局'))
    else:
        rows.append(dict(base, _leg=leg, _is_best=is_best, _tag='LIVE'))

fin=[r for r in rows if r['_tag']=='终局']
live=[r for r in rows if r['_tag']=='LIVE']
fin_noleg=[r for r in rows if r['_tag']=='终局无腿']
live_noleg=[r for r in rows if r['_tag']=='LIVE无腿']
nod=[r for r in rows if r['_tag']=='无数据']
print('===== 08-26 共 68 场 | 终局 %d | 进行中 %d | 无数据 %d =====' % (len(fin)+len(fin_noleg), len(live)+len(live_noleg), len(nod)))
print()
bests=[r for r in fin if r.get('_is_best')]
pnl=sum(r['_pnl'] for r in bests)
print('===== BEST 4 结算 =====')
for r in sorted(bests, key=lambda x:x['ko_bjt'] or ''):
    leg=r['_leg']
    print('  %s %s | %s EV%+.1f%% | 比分 %s | %s | PnL %+.2f' % (
        r['ko_bjt'], r['league'], leg['name'], (leg.get('ev') or 0)*100, r['_score'], r['_res'].upper(), r['_pnl']))
print('  BEST合计: %d注, PnL %+.2f, ROI %+.1f%%' % (len(bests), pnl, pnl/len(bests)*100 if bests else 0))
print()
legfin=[r for r in fin if r.get('_leg')]
w=sum(1 for r in legfin if r['_res']=='win'); l=sum(1 for r in legfin if r['_res']=='lose'); p=sum(1 for r in legfin if r['_res']=='push')
print('===== 有腿终局 %d 场: 胜 %d / 负 %d / 走 %d (ROI %+.1f%%) =====' % (len(legfin), w, l, p, sum(r['_pnl'] for r in legfin)/len(legfin)*100 if legfin else 0))
for r in sorted(legfin, key=lambda x:x['ko_bjt'] or ''):
    leg=r['_leg']
    print('  %s %-5s %-20s vs %-20s | %-8s %+.1f%% | %s %s | %s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18],
        leg['name'], (leg.get('ev') or 0)*100, r['_score'], r['_res'].upper(), 'BEST' if r.get('_is_best') else '方向'))
print()
print('===== 终局无腿 %d 场(方向负EV/无方向) =====' % len(fin_noleg))
for r in sorted(fin_noleg, key=lambda x:x['ko_bjt'] or ''):
    d=r.get('direction') or '-'; dv=r.get('dir_ev')
    evs=('%+.1f%%'%(dv*100)) if dv is not None else '-'
    print('  %s %-5s %-20s vs %-20s | %-8s %-7s | %s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18], d, evs, r['_score']))
print()
print('===== 进行中 %d 场: 有腿 %d / 无腿 %d =====' % (len(live)+len(live_noleg), len(live), len(live_noleg)))
for r in sorted(live+live_noleg, key=lambda x:x['ko_bjt'] or ''):
    leg=r.get('_leg')
    print('  %s %-5s %-20s vs %-20s | 当前 %s (%s)%s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18], r['_score'], r['_status'],
        (' | 腿:%s' % leg['name']) if leg else ''))
print()
print('===== 无数据 %d 场 =====' % len(nod))
for r in nod:
    print('  %s %s %s vs %s' % (r['ko_bjt'], r['league'], r['home'], r['away']))
