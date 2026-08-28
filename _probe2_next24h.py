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
to = (now + timedelta(hours=36)).strftime('%Y-%m-%dT%H:%M:%SZ')
r = requests.get(BASE+'/events/', params={'date_from':frm,'date_to':to,'limit':100,'full':'true'}, headers=H, timeout=60)
print('HTTP', r.status_code)
d = r.json()
rows = d.get('results') or []
print('events:', len(rows), '| next:', d.get('next'))
if rows:
    e=rows[0]
    print('keys:', list(e.keys()))
    print('league field:', json.dumps(e.get('league'), ensure_ascii=False)[:200])
    print('league_id:', e.get('league_id'))
