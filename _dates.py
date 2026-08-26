# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
for lid, label in [(21,'J1'), (31,'中超')]:
    sub = fx[(fx['league_id']==lid) & fx['is_played']]
    sub = sub.copy()
    print('%s HF played: %d, 日期 %s ~ %s' % (label, len(sub), sub['date_utc'].min(), sub['date_utc'].max()))
