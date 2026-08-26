# -*- coding: utf-8 -*-
import sys, os, csv, io
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
print('ALL_DIVS 含 JP1?', 'JP1' in su.ALL_DIVS)
print('DIV_BY_LEAGUE J1 =', su.DIV_BY_LEAGUE.get('J1'))
out, lavg, index = su.load_team_stats()
print('lavg keys:', list(lavg.keys()))
for t in ['Kashiwa Reysol','V-Varen Nagasaki','FC Tokyo','JEF United Chiba']:
    rec = out.get(t)
    print(t, '->', json_dumps(rec) if rec else '无数据')
