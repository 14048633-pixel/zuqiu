# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
f25 = fx[(fx['date_utc']>='2025-07-01') & fx['is_played']].copy()
lines=[]
# Machida 两id 2026 场次明细
for tid in [523, 4385]:
    sub = f25[(f25['home_team_id']==tid)|(f25['away_team_id']==tid)]
    sub = sub[sub['date_utc']>='2026-01-01']
    for _, r in sub.iterrows():
        h = tm.get(r['home_team_id'],'?'); a = tm.get(r['away_team_id'],'?')
        lines.append('id=%d %s  %s %s %s-%s  lid=%s' % (tid, r['date_utc'].date(), h, a, r['goals_home'], r['goals_away'], r['league_id']))
io.open('_machida.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved', len(lines))
