# -*- coding: utf-8 -*-
import sys, io, os, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:\足球分析'
scan = json.load(io.open(os.path.join(ROOT,'analysis_records','scan_next24h_20260825_1644.json'), encoding='utf-8'))
res  = json.load(io.open(os.path.join(ROOT,'analysis_records','results_scan_20260826_final3.json'), encoding='utf-8'))
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
    else: return None
    odds = float(leg.get('odds') or 0)
    ret = {'win': odds, 'push': 1.0, 'lose': 0.0}[r]
    return r, round(ret-1,4)

fin=[]
for m in scan:
    rr = res_by.get((m.get('home'), m.get('away')))
    if not rr or not rr.get('score') or rr.get('status') not in FINAL: continue
    h,a = map(int, rr['score'].split('-'))
    leg = m.get('best_bet'); is_best=True
    if not leg:
        d=m.get('direction'); dv=m.get('dir_ev') or 0
        if d and dv>0:
            leg = next((b for b in (m.get('bets') or []) if b.get('name')==d), None)
            is_best=False
    res_leg=None; pnl=None
    if leg:
        s=settle(leg,h,a)
        if s: res_leg,pnl=s
    fin.append(dict(m, _rr=rr, _h=h, _a=a, _leg=leg, _is_best=is_best, _res=res_leg, _pnl=pnl))

fin.sort(key=lambda x:(x.get('ko_bjt') or ''))
print('===== 08-26 终局 %d 场 =====' % len(fin))
print()
print('--- A. 有腿 14 场(账本) ---')
for r in fin:
    if not r['_leg']: continue
    leg=r['_leg']; rr=r['_rr']
    mark={'win':'WIN','lose':'LOSE','push':'PUSH'}[r['_res']]
    print('  %-11s %-5s %-20s vs %-20s | %-8s %+5.1f%% | %s %s | %s | %+.2f' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18], leg['name'],
        (leg.get('ev') or 0)*100, rr['score'], mark, 'BEST' if r['_is_best'] else '方向', r['_pnl']))
print()
print('--- B. 无腿 47 场(方向+比分参考) ---')
for r in fin:
    if r['_leg']: continue
    rr=r['_rr']; d=r.get('direction') or '-'; dv=r.get('dir_ev')
    evs=('%+.1f%%'%(dv*100)) if dv is not None else '-'
    print('  %-11s %-5s %-20s vs %-20s | 方向%-8s %-7s | %s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:18], (r['away'] or '')[:18], d, evs, rr['score']))
