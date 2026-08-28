# -*- coding: utf-8 -*-
import sys, io, os, json, requests, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2')
import bsd_extra
TOKEN = bsd_extra.TOKEN
BASE = 'https://sports.bzzoiro.com/api/v2'
H = {**bsd_extra.HEADERS, 'Authorization': 'Token %s' % TOKEN}
print('token ok:', bool(TOKEN))

def get(url, params=None, tries=3):
    for i in range(tries):
        try:
            r = requests.get(BASE + url, params=params, headers=H, timeout=60)
            if r.status_code == 200: return r.json()
            print('HTTP', r.status_code, r.text[:120]); 
        except Exception as e:
            print('ERR', repr(e)[:100])
    return None

# 1) 天皇杯 finished
d = get('/events/', {'league_id': 51, 'status': 'finished', 'date_from': '2026-08-26T00:00:00Z', 'date_to': '2026-08-26T23:59:59Z', 'limit': 100})
rows = d.get('results') if isinstance(d, dict) else None
print('天皇杯 finished events:', len(rows) if rows is not None else 'none')
if rows:
    for e in rows:
        h=e.get('home_team'); a=e.get('away_team')
        if isinstance(h,dict): h=h.get('name')
        if isinstance(a,dict): a=a.get('name')
        et=e.get('extra_time_score'); pen=e.get('penalty_shootout')
        print('  %-24s vs %-24s | FT %s-%s | ET %s | PEN %s' % (h,a,e.get('home_score'),e.get('away_score'),et,pen))

# 2) 找 K League league_id
lg = get('/leagues/', {'country': 'South Korea', 'limit': 20})
if isinstance(lg, dict):
    for x in (lg.get('results') or []):
        print('Korea league:', x.get('id'), x.get('name'))
