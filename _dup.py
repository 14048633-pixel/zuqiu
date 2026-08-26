# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
f25 = fx[(fx['date_utc']>='2025-07-01') & fx['is_played']].copy()
f25['home']=f25['home_team_id'].map(tm); f25['away']=f25['away_team_id'].map(tm)
lines=[]
# 1) Beijing Guoan 31 vs 53 是否重复
bg = teams[teams['name']=='Beijing Guoan']['id'].iloc[0]
sub = f25[(f25['home_team_id']==bg)|(f25['away_team_id']==bg)]
lines.append('BeijingGuoan 2025/26: %d 场' % len(sub))
for lid, g in sub.groupby('league_id'):
    lines.append('  league %s: %d 场, 日期 %s~%s' % (lid, len(g), g['date_utc'].min().date(), g['date_utc'].max().date()))
# 2) 检查重复 (同一球队同一天两场)
for name in ['Beijing Guoan','Athletico-PR','Atletico Paranaense','Machida','Machida Zelvia','Verdy','Tokyo Verdy','Dresden','Dynamo Dresden']:
    ids = teams[teams['name']==name]['id'].tolist()
    for tid in ids:
        s = f25[(f25['home_team_id']==tid)|(f25['away_team_id']==tid)]
        lines.append('%s(id=%s): %d场, leagues=%s' % (name, tid, len(s), sorted(s['league_id'].unique().tolist())))
io.open('_dup.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved')
