# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2'); sys.path.insert(0, '.')
import bsd_extra
def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())
needle = {norm(x) for x in ['FC Tokyo','Cerezo Osaka','Kashima Antlers','Urawa Red Diamonds','FC Anyang','Gangwon FC','Jubilo Iwata']}
for d in ('2026-08-25','2026-08-26','2026-08-27'):
    ev = bsd_extra.fetch_events(d, tries=2)
    if ev is None:
        print(d,'FAILED'); continue
    lg = Counter()
    hits = []
    for e in ev:
        le = e.get('league') or {}
        lg[le.get('name') if isinstance(le,dict) else le] += 1
        h = e.get('home_team'); a = e.get('away_team')
        if isinstance(h,dict): h=h.get('name')
        if isinstance(a,dict): a=a.get('name')
        if norm(h) in needle or norm(a) in needle:
            hits.append((h,a,e.get('status'),e.get('home_score'),e.get('away_score'),e.get('event_date','')[:19]))
    print('==',d,'total',len(ev),'| Emperor Cup:',lg.get('Emperor Cup'),'| K League:',lg.get('K League'))
    for x in hits[:20]:
        print('   ',x)
