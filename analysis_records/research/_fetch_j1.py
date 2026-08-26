# -*- coding: utf-8 -*-
import json, sys, io, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
KEY = 'FOOTBALL_API_KEY_FROM_ENV'
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
ids = {'Kashiwa vs Nagasaki': 212205, 'FC Tokyo vs Chiba': 212204}
for name, fid in ids.items():
    try:
        d = get('https://v3.football.api-sports.io/fixtures?id=%d' % fid)
        f = d.get('response',[{}])[0]
        st = (f.get('fixture',{}).get('status',{}) or {}).get('short')
        g = f.get('goals',{}) or {}
        print('%s | %s-%s | %s' % (name, g.get('home'), g.get('away'), st))
    except Exception as e:
        print(name, 'ERR', e)
