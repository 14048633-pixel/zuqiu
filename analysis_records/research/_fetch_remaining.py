# -*- coding: utf-8 -*-
import json, sys, io, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
KEY = 'FOOTBALL_API_KEY_FROM_ENV'
def get(url):
    req = urllib.request.Request(url, headers={'x-apisports-key': KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))
# 目标场次: 按名字粗筛(不含已复盘的Rayo/Botafogo/Corinthians)
targets = {
 'Al-Fayha': ('Al-Fayha','Al-Hilal'),
 'Sheffield Wednesday': ('Sheffield Wednesday','Bradford City'),
 'Olimpia': ('Olimpia','Vasco da Gama'),
 'Macará': ('Macará','Santos'),
 'LDU': ('LDU','Mirassol'),
 'Athletic Club': ('Athletic Club','Regatas Brasil'),
 'Real Cundinamarca': ('Real Cundinamarca','Internacional de Bogotá'),
 'Atlético Nacional': ('Atlético Nacional','Deportivo Cali'),
 'Grêmio Novorizontino': ('Grêmio Novorizontino','América Mineiro'),
}
found = {}
for date in ['2026-08-20', '2026-08-21']:
    try:
        data = get('https://v3.football.api-sports.io/fixtures?date=%s' % date)
    except Exception as e:
        print('ERR', date, e); continue
    for f in data.get('response', []):
        ht = (f.get('teams',{}).get('home',{}) or {}).get('name','')
        at = (f.get('teams',{}).get('away',{}) or {}).get('name','')
        status = (f.get('fixture',{}).get('status',{}) or {}).get('short','')
        goals = f.get('goals',{}) or {}
        fid = f.get('fixture',{}).get('id')
        for key,(h,a) in targets.items():
            if key.lower() in (ht+at).lower() and h.lower() in ht.lower() and a.lower() in at.lower():
                found[key] = dict(id=fid, home=ht, away=at, hs=goals.get('home'), as_=goals.get('away'),
                                  status=status, date=date, score='%s-%s'%(goals.get('home'),goals.get('away')))
print('命中:', len(found), '/', len(targets))
for k in targets:
    if k in found:
        f = found[k]
        print('%-22s | %-30s %-1s %-30s | %s | %s' % (k, f['home'], f['score'], f['away'], f['status'], f['id']))
    else:
        print('%-22s | 未命中' % k)
json.dump(found, io.open('analysis_records/_remaining_results.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
