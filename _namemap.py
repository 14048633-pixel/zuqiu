# -*- coding: utf-8 -*-
import pandas as pd, io, re, difflib, json
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
fx = pd.read_parquet('data/xg/fixtures.parquet', columns=['id','date_utc','league_id','home_team_id','away_team_id','goals_home','goals_away','is_played'])
teams = pd.read_parquet('data/xg/teams.parquet')
tm = dict(zip(teams['id'], teams['name']))
lc = pd.read_parquet('data/xg/league_catalogue.parquet')

def norm(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', str(s).lower())
    return re.sub(r'\s+', ' ', s).strip()

# 账本各联赛队名
league_led_teams = {}
for lg in led['league'].unique():
    league_led_teams[lg] = sorted(set(led[led['league']==lg]['home']) | set(led[led['league']==lg]['away']))

# HF 各联赛队名(2025/26)
hf_teams_by_league = {}
target_map = {'J1':('J1 League','Japan'),'中超':('Super League','China'),'丹超':('Superliga','Denmark'),'土超':('Süper Lig','Turkey'),
 '墨超':('Liga MX','Mexico'),'巴甲':('Serie A','Brazil'),'德乙':('2nd Bundesliga','Germany'),'挪超':('Eliteserien','Norway'),
 '智利甲':('Primera División','Chile'),'比甲':('Jupiler Pro League','Belgium'),'瑞超':('Allsvenskan','Sweden'),
 '美职':('Major League Soccer','USA'),'英乙':('League Two','England'),'英冠':('Championship','England'),
 '荷甲':('Eredivisie','Netherlands'),'葡超':('Primeira Liga','Portugal'),'西乙':('La Liga 2','Spain'),
 '西甲':('La Liga','Spain'),'阿甲':('Liga Profesional Argentina','Argentina')}
found = {}
for cn,(name,country) in target_map.items():
    m = lc[(lc['af_name']==name)&(lc['af_country']==country)]
    if len(m):
        found[cn] = m.iloc[0]['dataset_league_id']
    else:
        # 搜索 2. Bundesliga 或 Segunda
        if cn=='德乙':
            m = lc[lc['af_name'].str.contains('Bundesliga', case=False, na=False) & (lc['af_country']=='Germany')]
            found[cn] = None if not len(m) else m.iloc[0]['dataset_league_id']
        if cn=='西乙':
            m = lc[lc['af_name'].str.contains('Segunda|La Liga 2', case=False, na=False) & (lc['af_country']=='Spain')]
            found[cn] = None if not len(m) else m.iloc[0]['dataset_league_id']

lines = []
mapping = {}
for cn, lid in found.items():
    if lid is None:
        lines.append('== %s: HF联赛未找到 ==' % cn); continue
    sub = fx[(fx['league_id']==lid) & fx['is_played']]
    hf_names = sorted(set(sub['home_team_id'].map(tm).dropna()))
    led_names = league_led_teams.get(cn, [])
    lines.append('== %s (id=%s) HF %d队 / 账本 %d队 ==' % (cn, lid, len(hf_names), len(led_names)))
    led_norm = {norm(t): t for t in led_names}
    for h in hf_names:
        hn = norm(h)
        if hn in led_norm:
            mapping[h] = led_norm[hn]
        else:
            # 模糊匹配
            best, score = None, 0.0
            for t in led_names:
                r = difflib.SequenceMatcher(None, hn, norm(t)).ratio()
                if r > score: best, score = t, r
            if score >= 0.75:
                mapping[h] = best
                lines.append('  模糊: %s -> %s (%.2f)' % (h, best, score))
            else:
                lines.append('  未匹配: %s (最高%.2f -> %s)' % (h, score, best))
    for t in led_names:
        if t not in mapping.values():
            lines.append('  账本无对应: %s' % t)
io.open('_name_map.txt','w',encoding='utf-8').write('\n'.join(lines))
json.dump(mapping, io.open('_hf_name_map.json','w',encoding='utf-8'), ensure_ascii=False, indent=1)
print('mapped', len(mapping), '-> _name_map.txt')
