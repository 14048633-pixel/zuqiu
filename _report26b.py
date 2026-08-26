# -*- coding: utf-8 -*-
import sys, io, os, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:\足球分析'
scan = json.load(io.open(os.path.join(ROOT,'analysis_records','scan_next24h_20260825_1644.json'), encoding='utf-8'))
res  = json.load(io.open(os.path.join(ROOT,'analysis_records','results_scan_20260826_final2.json'), encoding='utf-8'))
res_by = {(r.get('home'), r.get('away')): r for r in res}
FINAL = ('post','finished','FT','AET','PEN')
out=[]
for m in scan:
    rr = res_by.get((m.get('home'), m.get('away')))
    score = rr.get('score') if rr else None
    status = rr.get('status') if rr else None
    if not score: tag='无数据'
    elif status in FINAL: tag='终局'
    else: tag='LIVE'
    leg = m.get('best_bet')
    legname = (leg or {}).get('name') or ''
    if not leg and m.get('direction') and (m.get('dir_ev') or 0)>0:
        legname = m.get('direction')
    out.append((m.get('ko_bjt'), m.get('league'), m.get('home'), m.get('away'),
                legname, m.get('direction'), m.get('dir_ev'), score, tag, status))
out.sort(key=lambda x:(x[0] or ''))
for o in out:
    ko, lg, h, a, legname, d, dv, score, tag, st = o
    evs = ('%+.1f%%' % (dv*100)) if dv is not None else '-'
    legtag = legname or '-'
    print('%-11s %-5s %-22s vs %-22s | 腿:%-9s 方向:%-8s %-7s | %-5s %s' % (
        ko, lg, (h or '')[:20], (a or '')[:20], legtag, (d or '-')[:8], evs, score or '----', tag))
from collections import Counter
print()
print(Counter(o[8] for o in out))
