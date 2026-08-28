# -*- coding: utf-8 -*-
import sys, io, os, json, requests
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2')
import bsd_extra
TOKEN = bsd_extra.TOKEN
BASE = 'https://sports.bzzoiro.com/api/v2'
H = {**bsd_extra.HEADERS, 'Authorization': 'Token %s' % TOKEN}
ROOT = r'D:\足球分析'

def get(url, params):
    for i in range(3):
        try:
            r = requests.get(BASE+url, params=params, headers=H, timeout=60)
            if r.status_code==200: return r.json()
        except Exception: pass
    return None

# 联赛表
leagues={}
off=0
while True:
    d=get('/leagues/', {'limit':100,'offset':off})
    if not d: break
    rows=d.get('results') or []
    for x in rows: leagues[x['id']]=x.get('name')
    if len(rows)<100 or not d.get('next'): break
    off+=100
print('leagues loaded:', len(leagues))

# 24h 窗口事件
now=datetime.now(timezone.utc)
frm=now.strftime('%Y-%m-%dT%H:%M:%SZ')
to=(now+timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
d=get('/events/', {'date_from':frm,'date_to':to,'limit':100,'full':'true'})
rows=d.get('results') or [] if d else []
print('events:', len(rows))

BJT=timezone(timedelta(hours=8))
ms=[]; seen=set()
for e in rows:
    h=e.get('home_team'); a=e.get('away_team')
    if isinstance(h,dict): h=h.get('name')
    if isinstance(a,dict): a=a.get('name')
    ed=e.get('event_date') or ''
    try:
        ko=datetime.fromisoformat(ed.replace('Z','+00:00'))
    except Exception:
        continue
    key=(h,a,ko.date().isoformat())
    if key in seen: continue
    seen.add(key)
    lid=e.get('league_id')
    lgn=leagues.get(lid, str(lid))
    ms.append({
        'id': e.get('id'), 'league': lgn, 'kickoff': ko.astimezone(BJT).strftime('%m-%d %H:%M'),
        'kickoff_iso': ko.isoformat(), 'ct': ko.isoformat(),
        'home': h, 'away': a, 'home_id': e.get('home_team_id'), 'away_id': e.get('away_team_id'),
        'status': e.get('status'),
    })
ms.sort(key=lambda x:x['ct'])
out={'window': '%s BJT -> %s BJT' % (now.astimezone(BJT).strftime('%m-%d %H:%M'), (now+timedelta(hours=24)).astimezone(BJT).strftime('%m-%d %H:%M')),
      'generated': now.isoformat(), 'matches': ms}
fp=os.path.join(ROOT,'analysis_records','scan24h_%s.json' % now.astimezone(BJT).strftime('%Y%m%d_%H%M'))
io.open(fp,'w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=1))
print('saved ->', fp)
from collections import Counter
print('by league:', dict(Counter(m['league'] for m in ms)))
print()
for m in ms:
    print('  %-16s %-24s %-22s vs %-22s | id=%s' % (m['kickoff'], m['league'], (m['home'] or '')[:20], (m['away'] or '')[:20], m['id']))
