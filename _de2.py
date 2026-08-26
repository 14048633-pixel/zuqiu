# -*- coding: utf-8 -*-
import pandas as pd, io, re
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
lc = pd.read_parquet('data/xg/league_catalogue.parquet')
fx['date_utc'] = pd.to_datetime(fx['date_utc'], errors='coerce')
target_map = {'J1':('J1 League','Japan',21.0),'中超':('Super League','China',31.0),'丹超':('Superliga','Denmark',30.0),'土超':('Süper Lig','Turkey',16.0),
 '墨超':('Liga MX','Mexico',22.0),'巴甲':('Serie A','Brazil',19.0),'德乙':('2nd Bundesliga','Germany',None),'挪超':('Eliteserien','Norway',23.0),
 '智利甲':('Primera División','Chile',53.0),'比甲':('Jupiler Pro League','Belgium',15.0),'瑞超':('Allsvenskan','Sweden',29.0),
 '美职':('Major League Soccer','USA',20.0),'英乙':('League Two','England',4.0),'英冠':('Championship','England',2.0),
 '荷甲':('Eredivisie','Netherlands',13.0),'葡超':('Primeira Liga','Portugal',14.0),'西乙':('La Liga 2','Spain',None),
 '西甲':('La Liga','Spain',5.0),'阿甲':('Liga Profesional Argentina','Argentina',28.0)}
# 德乙/西乙查目录
for kw, country in [('Bundesliga','Germany'),('Segunda','Spain')]:
    m = lc[lc['af_name'].str.contains(kw, case=False, na=False) & (lc['af_country']==country) & lc['in_dataset']]
    print(kw, country, m[['af_name','dataset_league_id']].to_string())
