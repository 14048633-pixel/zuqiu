# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
f25 = fx[(fx['date_utc']>='2025-07-01') & fx['is_played'] & (fx['league_id']==120.0)].copy()
f25['home']=f25['home_team_id'].map(tm); f25['away']=f25['away_team_id'].map(tm)
out = io.open('_dk2r.txt','w',encoding='utf-8')
out.write('league120 total: %d\n' % len(f25))
out.write(f25['home'].value_counts().to_string())
out.close()
print('ok')
