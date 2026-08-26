# -*- coding: utf-8 -*-
import json, sys, io, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
KEY = 'FOOTBALL_API_KEY_FROM_ENV'
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
kws = ['Sheffield','Bradford','Macara','Santos','Athletic Club','Regatas','Cundinamarca','Bogota','Atletico Nacional','Deportivo Cali','Novorizontino','America Mineiro','America-MG']
seen = set()
for date in ['2026-08-20', '2026-08-21']:
    try:
        data = get('https://v3.football.api-sports.io/fixtures?date=%s' % date)
    except Exception as e:
        print('ERR', date, e); continue
    for f in data.get('response', []):
        ht = (f.get('teams',{}).get('home',{}) or {}).get('name','')
        at = (f.get('teams',{}).get('away',{}) or {}).get('name','')
        combo = ht + ' ' + at
        for k in kws:
            if k.lower() in combo.lower():
                status = (f.get('fixture',{}).get('status',{}) or {}).get('short','')
                goals = f.get('goals',{}) or {}
                fid = f.get('fixture',{}).get('id')
                key = (ht, at)
                if key in seen: break
                seen.add(key)
                print('%-4s | %-38s vs %-30s | %s-%s | %s | %s' % (date[-5:], ht, at, goals.get('home'), goals.get('away'), status, fid))
                break
