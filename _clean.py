# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
f25 = fx[(fx['date_utc']>='2025-07-01') & fx['is_played']].copy()
f25['home'] = f25['home_team_id'].map(tm); f25['away'] = f25['away_team_id'].map(tm)
L = {'J1':21.0,'中超':31.0,'丹超':30.0,'土超':16.0,'墨超':22.0,'巴甲':19.0,'德乙':12.0,'挪超':23.0,'智利甲':53.0,
 '比甲':15.0,'瑞超':29.0,'美职':20.0,'英乙':4.0,'英冠':2.0,'荷甲':13.0,'葡超':14.0,'西乙':6.0,'西甲':5.0,'阿甲':28.0}
lines=[]
for cn, lid in L.items():
    sub = f25[f25['league_id']==lid]
    # 双方都在本联赛主队集(>=10场主队次数)
    home_cnt = sub['home'].value_counts()
    members = set(home_cnt[home_cnt>=10].index)
    clean = sub[sub['home'].isin(members) & sub['away'].isin(members)]
    lines.append('%s(id=%s): 总%d, 双方均为主队集=%d, 剔除%d, 主队集%d队' % (cn, lid, len(sub), len(clean), len(sub)-len(clean), len(members)))
io.open('_clean.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved')
