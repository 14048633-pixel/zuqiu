# -*- coding: utf-8 -*-
import os
import json, sys, io, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
KEY = os.environ.get("FOOTBALL_API_KEY", "")
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
d = get('https://v3.football.api-sports.io/fixtures?id=1547771')
f = d.get('response',[{}])[0]
sc = f.get('score',{}) or {}
print('penalty:', sc.get('penalty'))
print('fulltime:', sc.get('fulltime'))
print('teams:', f.get('teams',{}).get('home',{}).get('winner'), '|', f.get('teams',{}).get('away',{}).get('winner'))
# 写结果存档
out = {
 'LDU vs Mirassol': {'score':'0-0','penalty':sc.get('penalty'),'winner_home':f.get('teams',{}).get('home',{}).get('winner'),'status':'PEN(点球决出)'}
}
json.dump(out, io.open('analysis_records/_ldu_penalty.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
