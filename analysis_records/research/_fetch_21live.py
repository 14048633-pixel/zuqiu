# -*- coding: utf-8 -*-
import os
import json, sys, io, urllib.request, datetime
sys.stdout.reconfigure(encoding='utf-8')
KEY = os.environ.get("FOOTBALL_API_KEY", "")
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
print('当前时间(本地):', now.strftime('%Y-%m-%d %H:%M'))
ids = {'Botafogo vs Cienciano': 1607201, 'Corinthians vs Rosario Central': 1547767}
for name, fid in ids.items():
    try:
        d = get('https://v3.football.api-sports.io/fixtures?id=%d' % fid)
        f = d.get('response',[{}])[0]
        st = (f.get('fixture',{}).get('status',{}) or {})
        g = f.get('goals',{}) or {}
        print('%s | %s-%s | %s | %s\'' % (name, g.get('home'), g.get('away'), st.get('short'), st.get('elapsed')))
    except Exception as e:
        print(name, 'ERR', e)
