# -*- coding: utf-8 -*-
import pandas as pd, io
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
back = pd.read_csv('data/raw/football_data/hf_2025_26_backfill.csv', low_memory=False)
led_teams = set(led['home']) | set(led['away'])
bteams = set(back['HomeTeam']) | set(back['AwayTeam'])
miss = sorted(led_teams - bteams)
out = io.open('_miss.txt','w',encoding='utf-8')
out.write('回填未命中 %d 队:\n' % len(miss))
for t in miss:
    out.write('  %s\n' % t)
out.close()
print('ok', len(miss))
