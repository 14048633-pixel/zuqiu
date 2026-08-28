# -*- coding: utf-8 -*-
import os
import json, sys, io, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
KEY = os.environ.get("FOOTBALL_API_KEY", "")
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
# 用日期拉 J1 联赛场次
d = get('https://v3.football.api-sports.io/fixtures?date=2026-08-21')
kws = ['Kashiwa','V-Varen','Nagasaki','FC Tokyo','JEF','Chiba']
cnt=0
for f in d.get('response', []):
    lg = (f.get('league',{}) or {}).get('name','')
    ht = (f.get('teams',{}).get('home',{}) or {}).get('name','')
    at = (f.get('teams',{}).get('away',{}) or {}).get('name','')
    if 'J1' in lg or any(k.lower() in (ht+at).lower() for k in kws):
        st = (f.get('fixture',{}).get('status',{}) or {}).get('short','')
        g = f.get('goals',{}) or {}
        fid = (f.get('fixture',{}) or {}).get('id')
        print('%s | %s vs %s | %s-%s | %s | fid=%s' % (lg, ht, at, g.get('home'), g.get('away'), st, fid))
        cnt+=1
print('匹配场次:', cnt)
