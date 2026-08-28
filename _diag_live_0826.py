# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2'); sys.path.insert(0, '.')
import bsd_extra
ROOT = r'D:\足球分析'
def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())
events = []
for d in ('2026-08-25','2026-08-26'):
    ev = bsd_extra.fetch_events(d, tries=3)
    if ev: events.extend(ev)
print('fetched total:', len(events))
# 目标: 天皇杯/K联赛 未终局场次
scan = json.load(io.open(os.path.join(ROOT,'analysis_records','scan_next24h_20260825_1644.json'), encoding='utf-8'))
targets = []
for m in scan:
    if m.get('league') in ('天皇杯','K联赛') and m.get('ko_bjt','').startswith('08-26 17:3'):
        targets.append((m['home'], m['away'], m.get('ko_bjt')))
    if m.get('league') in ('天皇杯','K联赛') and m.get('ko_bjt','').startswith('08-26 18:'):
        targets.append((m['home'], m['away'], m.get('ko_bjt')))
for h,a,ko in targets:
    nh,na = norm(h),norm(a)
    cands=[]
    for e in events:
        eh = e.get('home_team'); ea = e.get('away_team')
        if isinstance(eh,dict): eh=eh.get('name')
        if isinstance(ea,dict): ea=ea.get('name')
        if not eh or not ea: continue
        if norm(eh)==nh and norm(ea)==na:
            cands.append(e)
    for e in cands:
        print('%-22s vs %-22s | id=%-8s status=%-10s score=%s-%s min=%s per=%s date=%s' % (
            eh, ea, e.get('id'), e.get('status'), e.get('home_score'), e.get('away_score'),
            e.get('current_minute'), e.get('period'), (e.get('event_date') or '')[:19]))
    if not cands:
        print('%-22s vs %-22s | NO MATCH' % (h,a))
