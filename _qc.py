# -*- coding: utf-8 -*-
import pandas as pd
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
# 中超队(Shanghai Port等)出现在哪些league_id
cn_teams = ['Beijing Guoan','Shanghai Port','Shandong Taishan','Chengdu Rongcheng','Wuhan Three Towns']
for t in cn_teams:
    tid = teams[teams['name']==t]['id']
    if len(tid)==0: 
        print(t, 'not in teams'); continue
    tid = tid.iloc[0]
    sub = fx[(fx['home_team_id']==tid) | (fx['away_team_id']==tid)]
    sub = sub[(sub['date_utc']>='2025-07-01')]
    print(t, '-> league_ids 2025/26:', sub['league_id'].value_counts().to_dict())
# 智利甲id=53 里中国队的比赛数量
sub53 = fx[(fx['league_id']==53) & (fx['date_utc']>='2025-07-01') & fx['is_played']]
cn_in53 = sub53[(sub53['home_team_id'].map(tm).isin(cn_teams)) | (sub53['away_team_id'].map(tm).isin(cn_teams))]
print('league53 2025/26 played:', len(sub53), '其中含中超队:', len(cn_in53))
print(sub53['home_team_id'].map(tm).value_counts().head(8))
