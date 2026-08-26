# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
out, lavg, index = su.load_team_stats()
print('lavg keys:', list(lavg.keys()))
for t in ['Kashiwa Reysol','V-Varen Nagasaki','FC Tokyo','JEF United Chiba','浦和','Kashima']:
    rec = out.get(t)
    print(t, '->', json.dumps(rec, ensure_ascii=False) if rec else '无数据')
# 看 j1 csv 里队名原样
import csv, io
with io.open('data/raw/football_data/j1_2026_results.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
names = set()
for r in rows:
    names.add(r['HomeTeam']); names.add(r['AwayTeam'])
print('J1 CSV 队名样例:', sorted(names)[:8])
print('Kashiwa in index?', su._norm('Kashiwa Reysol') in index)
