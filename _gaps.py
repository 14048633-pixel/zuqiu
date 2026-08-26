# -*- coding: utf-8 -*-
import pandas as pd, io
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
f25 = fx[(fx['date_utc']>='2025-07-01') & fx['is_played']].copy()
lc = pd.read_parquet('data/xg/league_catalogue.parquet')
lc_id = dict(zip(lc['dataset_league_id'], lc['af_name']))
for name in ['Burnley','Exeter City','Port Vale','Rotherham United','Tenerife','AC Horsens','SC Cambuur','Willem II','ADO Den Haag','Bolton Wanderers','Lincoln City','West Ham United','1. FC Heidenheim','Celta Vigo','Racing Santander','Las Palmas','Kortrijk','Leuven','KV Kortrijk','Oud-Heverlee Leuven','Dalian Zhixing','Dalian Yingbo','AIK','Malmo FF','Djurgardens IF','GAIS']:
    ids = teams[teams['name']==name]['id'].tolist()
    if not ids:
        # 模糊找
        import difflib
        best=None;bs=0
        for t in teams['name']:
            r=difflib.SequenceMatcher(None,name.lower(),str(t).lower()).ratio()
            if r>bs: bs=r; best=t
        print('%-22s NOT EXACT (best %s %.2f)' % (name, best, bs))
        continue
    row=[]
    for tid in ids:
        s = f25[(f25['home_team_id']==tid)|(f25['away_team_id']==tid)]
        leagues = {l: lc_id.get(l, l) for l in sorted(s['league_id'].unique().tolist())}
        row.append('%s(id=%s,%d场,%s)' % (name, tid, len(s), leagues))
    print('%-22s' % name, ' | '.join(row))
