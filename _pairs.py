# -*- coding: utf-8 -*-
import pandas as pd, io
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
L = {'J1':21.0,'中超':31.0,'丹超':30.0,'土超':16.0,'墨超':22.0,'巴甲':19.0,'德乙':12.0,'挪超':23.0,'智利甲':53.0,
 '比甲':15.0,'瑞超':29.0,'美职':20.0,'英乙':4.0,'英冠':2.0,'荷甲':13.0,'葡超':14.0,'西乙':6.0,'西甲':5.0,'阿甲':28.0}
lines=[]
for cn, lid in L.items():
    sub = fx[(fx['league_id']==lid) & (fx['date_utc']>='2025-07-01') & fx['is_played']]
    hf = sorted(set(sub['home_team_id'].map(tm).dropna()))
    lt = sorted(set(led[led['league']==cn]['home']) | set(led[led['league']==cn]['away']))
    lines.append('### %s (HF %d队 / 账本 %d队)' % (cn, len(hf), len(lt)))
    lines.append('HF: ' + ' | '.join(hf))
    lines.append('账本: ' + ' | '.join(lt))
    lines.append('')
io.open('_leagues_pairs.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved')
