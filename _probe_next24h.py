# -*- coding: utf-8 -*-
import sys, io, os, json, requests
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2')
import bsd_extra
TOKEN = bsd_extra.TOKEN
BASE = 'https://sports.bzzoiro.com/api/v2'
H = {**bsd_extra.HEADERS, 'Authorization': 'Token %s' % TOKEN}
now = datetime.now(timezone.utc)
frm = now.strftime('%Y-%m-%dT%H:%M:%SZ')
to = (now + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
print('window:', frm, '->', to)
d=None
for i in range(3):
    try:
        r = requests.get(BASE+'/events/', params={'date_from':frm,'date_to':to,'limit':100,'full':'true'}, headers=H, timeout=60)
        if r.status_code==200:
            d=r.json(); break
        print('HTTP', r.status_code, r.text[:100])
    except Exception as e:
        print('ERR', repr(e)[:100])
if not d:
    print('FAILED'); sys.exit()
rows = d.get('results') or []
print('upcoming events:', len(rows))
BJT = timezone(timedelta(hours=8))
seen=set()
out=[]
for e in rows:
    h=e.get('home_team'); a=e.get('away_team')
    if isinstance(h,dict): h=h.get('name')
    if isinstance(a,dict): a=a.get('name')
    le=e.get('league') or {}
    lg = le.get('name') if isinstance(le,dict) else le
    ed=e.get('event_date') or ''
    try:
        ko=datetime.fromisoformat(ed.replace('Z','+00:00')).astimezone(BJT)
    except Exception:
        ko=None
    key=(h,a)
    if key in seen: continue
    seen.add(key)
    out.append((ko, lg, h, a, e.get('id'), e.get('status')))
out.sort(key=lambda x:(x[0] or datetime.max))
from collections import Counter
print('by league:', dict(Counter(x[1] for x in out)))
for ko,lg,h,a,eid,st in out:
    print('  %-16s %-18s %-22s vs %-22s | id=%s | %s' % (ko.strftime('%m-%d %H:%M') if ko else '?', lg, (h or '')[:20], (a or '')[:20], eid, st))
