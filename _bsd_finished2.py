# -*- coding: utf-8 -*-
import sys, io, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2')
import bsd_extra
TOKEN = bsd_extra.TOKEN
BASE = 'https://sports.bzzoiro.com/api/v2'
H = {**bsd_extra.HEADERS, 'Authorization': 'Token %s' % TOKEN}
def get(url, params=None):
    for i in range(3):
        try:
            r = requests.get(BASE + url, params=params, headers=H, timeout=60)
            if r.status_code == 200: return r.json()
        except Exception: pass
    return None

# K联赛1 finished 08-26
d = get('/events/', {'league_id': 50, 'status': 'finished', 'date_from': '2026-08-26T00:00:00Z', 'date_to': '2026-08-26T23:59:59Z', 'limit': 50})
rows = d.get('results') if isinstance(d, dict) else []
print('== K League 1 finished 08-26:', len(rows))
for e in rows:
    h=e.get('home_team'); a=e.get('away_team')
    if isinstance(h,dict): h=h.get('name')
    if isinstance(a,dict): a=a.get('name')
    print('  %-24s vs %-24s | FT %s-%s' % (h,a,e.get('home_score'),e.get('away_score')))

# Avispa Fukuoka 任意状态
d2 = get('/events/', {'league_id': 51, 'date_from': '2026-08-25T00:00:00Z', 'date_to': '2026-08-27T23:59:59Z', 'limit': 200})
if isinstance(d2, dict):
    for e in d2.get('results') or []:
        h=e.get('home_team'); a=e.get('away_team')
        if isinstance(h,dict): h=h.get('name')
        if isinstance(a,dict): a=a.get('name')
        if h=='Avispa Fukuoka' or a=='Avispa Fukuoka':
            print('Avispa:', h, 'vs', a, '| status', e.get('status'), '|', e.get('home_score'), e.get('away_score'), '|', (e.get('event_date') or '')[:19])
