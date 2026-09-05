# -*- coding: utf-8 -*-
"""统计新系统 live_tracker.json 追踪状态"""
import json, io
from collections import Counter

p = r'D:\发家致富\strategy_data\live_tracker.json'
d = json.load(io.open(p, encoding='utf-8'))
print('总记录数:', len(d))
print('状态分布:', dict(Counter(r.get('status') for r in d)))
print('盘口源分布:', dict(Counter(r.get('odds_source') for r in d)))
print('星级分布:', dict(Counter(r.get('stars') for r in d)))
print('日期范围:', min(r.get('date') for r in d), '->', max(r.get('date') for r in d))
print()
print('=== 各日期条数 ===')
for dt, c in sorted(Counter(r.get('date') for r in d).items()):
    print(' ', dt, c)
print()
settled = [r for r in d if r.get('status') == 'settled' and r.get('profit_pct') is not None]
print('已结算且带收益:', len(settled))
if settled:
    ps = [r['profit_pct'] for r in settled]
    print('  命中数(profit>0):', sum(1 for x in ps if x > 0), '/', len(ps))
    print('  平均收益%%: %.2f' % (sum(ps)/len(ps)))
    print('  收益明细:', [round(x,1) for x in ps][:30])
print()
print('=== 未结算(open) 最后5条 ===')
for r in [x for x in d if x.get('status')=='open'][-5:]:
    print(' ', r.get('date'), r.get('league'), r.get('home'), 'vs', r.get('away'), r.get('pick'), r.get('stars'),'星')
