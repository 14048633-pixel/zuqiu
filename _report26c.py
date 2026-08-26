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
        if name.startswith('大'):
            r = 'win' if total > line else ('push' if total == line else 'lose')
        else:
            r = 'win' if total < line else ('push' if total == line else 'lose')
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
    if not score_s:
        rows.append(dict(m, _tag='无数据')); continue
    try: h,a = map(int, score_s.split('-'))
    except Exception: h=a=0
    leg = m.get('best_bet'); is_best=True
    if not leg:
        d=m.get('direction'); dv=m.get('dir_ev') or 0
        if not d or dv<=0:
            rows.append(dict(m, _tag='终局无腿')); continue
        leg = next((b for b in (m.get('bets') or []) if b.get('name')==d), None)
        is_best=False
        if not leg:
            rows.append(dict(m, _tag='终局无腿')); continue
    if status in FINAL:
        s = settle(leg, h, a)
        if s is None:
            rows.append(dict(m, _tag='终局无腿')); continue
        r,pnl,total = s
        rows.append(dict(m, _leg=leg, _is_best=is_best, _res=r, _pnl=pnl, _total=total, _tag='终局'))
    else:
        rows.append(dict(m, _leg=leg, _is_best=is_best, _tag='LIVE'))

print('===== 08-26 共 %d 场 | 终局 %d | 进行中 %d | 无数据 %d =====' % (
    len(rows), sum(1 for r in rows if r['_tag']=='终局'),
    sum(1 for r in rows if r['_tag']=='LIVE'), sum(1 for r in rows if r['_tag']=='无数据')))

print()
print('===== BEST 4 结算 =====')
bests=[r for r in rows if r.get('_is_best') and r['_tag']=='终局']
pnl=0
for r in sorted(bests, key=lambda x:x['ko_bjt'] or ''):
    leg=r['_leg']; rr=res_by[(r['home'],r['away'])]
    pnl+=r['_pnl']
    print('  %s %s | %s EV%+.1f%% | %s | %s | PnL %+.2f' % (
        r['ko_bjt'], r['league'], leg['name'], (leg.get('ev') or 0)*100, rr['score'], r['_res'].upper(), r['_pnl']))
print('  BEST合计: %d 注, PnL %+.2f, ROI %+.1f%%' % (len(bests), pnl, pnl/len(bests)*100 if bests else 0))

print()
print('===== 终局 34 场方向对账(含BEST) =====')
fin=[r for r in rows if r['_tag']=='终局']
w=l=p=0
for r in sorted(fin, key=lambda x:x['ko_bjt'] or ''):
    rr=res_by[(r['home'],r['away'])]
    leg=r.get('_leg')
    if leg:
        mark={'win':'WIN','lose':'LOSE','push':'PUSH'}[r['_res']]
        if r['_res']=='win': w+=1
        elif r['_res']=='lose': l+=1
        else: p+=1
    else:
        mark='--'
    tag='BEST' if r.get('_is_best') else '方向'
    print('  %s %-5s %-20s vs %-20s | %-8s %+.1f%% | %s %s | %s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18],
        leg['name'] if leg else '-', (leg.get('ev') or 0)*100 if leg else 0, rr['score'], mark, tag))
print('  有腿终局: 胜 %d / 负 %d / 走 %d' % (w,l,p))

print()
print('===== 进行中 %d 场(有腿 %d) =====' % (
    sum(1 for r in rows if r['_tag']=='LIVE'), sum(1 for r in rows if r['_tag']=='LIVE' and r.get('_leg'))))
for r in sorted([r for r in rows if r['_tag']=='LIVE'], key=lambda x:x['ko_bjt'] or ''):
    rr=res_by[(r['home'],r['away'])]
    leg=r.get('_leg')
    print('  %s %-5s %-20s vs %-20s | 当前 %s (%s)%s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18], rr['score'], rr['status'],
        (' | 腿:%s' % leg['name']) if leg else ''))

print()
print('===== 无数据 6 场 =====')
for r in rows:
    if r['_tag']=='无数据':
        print('  %s %s %s vs %s' % (r['ko_bjt'], r['league'], r['home'], r['away']))
