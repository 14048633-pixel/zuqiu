# -*- coding: utf-8 -*-
import pandas as pd, io
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
led_names = sorted(set(led['home']) | set(led['away']))
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
# 账本涉及的联赛
lc = pd.read_parquet('data/xg/league_catalogue.parquet')
leagues = led['league'].value_counts()
lines = ['账本联赛分布:']
for k,v in leagues.items(): lines.append('  %s: %d' % (k, v))
lines.append('')
lines.append('账本队名 vs HF队名 (按联赛):')
for lg in sorted(leagues.index):
    teams_lg = sorted(set(led[led['league']==lg]['home']) | set(led[led['league']==lg]['away']))
    lines.append('== %s ==' % lg)
    for t in teams_lg:
        lines.append('  %s' % t)
io.open('_names2.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved')
