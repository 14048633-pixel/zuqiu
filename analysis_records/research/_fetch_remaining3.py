# -*- coding: utf-8 -*-
import json, sys, io, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
KEY = 'FOOTBALL_API_KEY_FROM_ENV'
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
# 1) LDU 详情 (确认 PEN 是否点球大战 + 全场比分)
d = get('https://v3.football.api-sports.io/fixtures?id=1547771')
f = d.get('response',[{}])[0]
print('LDU vs Mirassol:')
print('  status:', f.get('fixture',{}).get('status'))
print('  goals:', f.get('goals'))
print('  score.ht:', f.get('score',{}).get('halftime'), 'ft:', f.get('score',{}).get('fulltime'))
print('  league:', f.get('league',{}).get('name'), f.get('league',{}).get('round'))
# 2) Sanluqueño 友谊赛 (date=08-20 全量里搜)
kws = ['Sanluqueno','Antoniano','Sanluque']
for date in ['2026-08-20']:
    data = get('https://v3.football.api-sports.io/fixtures?date=%s' % date)
    for x in data.get('response', []):
        ht = (x.get('teams',{}).get('home',{}) or {}).get('name','')
        at = (x.get('teams',{}).get('away',{}) or {}).get('name','')
        if any(k.lower() in (ht+at).lower() for k in kws):
            g = x.get('goals',{}) or {}
            st = (x.get('fixture',{}).get('status',{}) or {}).get('short','')
            print('Sanluque match:', ht, 'vs', at, '| %s-%s'%(g.get('home'),g.get('away')), '|', st, '| id', x.get('fixture',{}).get('id'))
