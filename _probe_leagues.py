# -*- coding: utf-8 -*-
import sys, io, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2')
import bsd_extra
TOKEN = bsd_extra.TOKEN
BASE = 'https://sports.bzzoiro.com/api/v2'
H = {**bsd_extra.HEADERS, 'Authorization': 'Token %s' % TOKEN}
alll=[]
off=0
while True:
    r = requests.get(BASE+'/leagues/', params={'limit':100,'offset':off}, headers=H, timeout=60)
    if r.status_code!=200:
        print('HTTP',r.status_code); break
    d=r.json(); rows=d.get('results') or []
    alll.extend(rows)
    if len(rows)<100 or not d.get('next'): break
    off+=100
print('leagues total:', len(alll))
for x in alll:
    if x.get('country') in ('Japan','South Korea','England','Spain','Saudi Arabia','Brazil','China','Chile','USA','Germany','Italy','France','Netherlands','Portugal','Belgium','Greece','Turkey','Austria','Poland','Colombia','Mexico','Argentina','Russia') or 'Cup' in str(x.get('name')):
        print('  %-5s %-30s %s' % (x.get('id'), x.get('name'), x.get('country')))
