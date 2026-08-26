# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
f25 = fx[(fx['date_utc']>='2025-07-01') & fx['is_played']].copy()
lines=[]
# 同俱乐部两id: 看日期是否有重叠(即同一场被两个team_id记录)
for a,b,name in [(446,2790,'Athletico-PR vs Atletico Paranaense'),(523,4385,'Machida vs Machida Zelvia'),(293,3389,'Dresden vs Dynamo Dresden'),(518,4384,'Verdy vs Tokyo Verdy')]:
    sa = f25[(f25['home_team_id']==a)|(f25['away_team_id']==a)][['date_utc','home_team_id','away_team_id']].set_index(['date_utc','home_team_id','away_team_id'])
    sb = f25[(f25['home_team_id']==b)|(f25['away_team_id']==b)][['date_utc','home_team_id','away_team_id']].set_index(['date_utc','home_team_id','away_team_id'])
    inter = sa.index.intersection(sb.index)
    lines.append('%s: A=%d B=%d 完全重复=%d' % (name, len(sa), len(sb), len(inter)))
# league 53 是什么
lc = pd.read_parquet('data/xg/league_catalogue.parquet')
m = lc[lc['dataset_league_id']==53.0]
lines.append('league53: ' + m[['af_name','af_country','af_type']].to_string())
# 账本球队中, HF 完全找不到的(通过模糊) — 先手工列关键缺口队
for t in ['Burnley','Exeter City','Port Vale','Rotherham United','Tenerife','AC Horsens','SC Cambuur','Willem II','ADO Den Haag','Bolton Wanderers','Lincoln City','West Ham United','1. FC Heidenheim','Celta Vigo','Real Racing Club de Santander','Las Palmas','Kortrijk','Leuven']:
    pass
io.open('_dup2.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved')
