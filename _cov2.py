# -*- coding: utf-8 -*-
import pandas as pd, io, collections
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
pool = []
for f in ['data/raw/football_data/matches_with_xg.csv','data/raw/football_data/hf_2025_26_backfill.csv',
          'data/raw/football_data/matches_2023_2024.csv','data/raw/football_data/football_data_recent.csv']:
    df = pd.read_csv(f, low_memory=False)
    need = ['Date','HomeTeam','AwayTeam','FTHG','FTAG','home_xG_for','away_xG_for','HS','HST']
    for c in need:
        if c not in df.columns: df[c] = None
    pool.append(df[need])
p = pd.concat(pool, ignore_index=True)
p['Date'] = pd.to_datetime(p['Date'], errors='coerce', dayfirst=True)
p = p.dropna(subset=['Date'])
hist = collections.defaultdict(list)
for _, r in p.iterrows():
    hist[r['HomeTeam']].append((r['Date'], r['home_xG_for']))
    hist[r['AwayTeam']].append((r['Date'], r['away_xG_for']))
lines=[]
bad=[]
for _, b in led.iterrows():
    for team, date in [(b['home'], pd.to_datetime(b['date'])), (b['away'], pd.to_datetime(b['date']))]:
        past = [m for m in hist.get(team, []) if m[0] < date]
        n = len(past); n_xg = sum(1 for m in past if pd.notna(m[1]))
        if n < 4:
            bad.append((team, b['league'], n, n_xg))
cov = {}
for t, lg, n, nx in bad:
    cov.setdefault((lg, n, nx), 0)
    cov[(lg, n, nx)] += 1
lines.append('历史<4场的球队次数: %d' % len(bad))
for k, v in sorted(cov.items(), key=lambda x: -x[1]):
    lines.append('  %s: %d场历史(含xG %d) -> %d次' % (k[0], k[1], k[2], v))
# 覆盖数
total_teams = len(set(led['home']) | set(led['away']))
ok_teams = set()
for t in set(led['home']) | set(led['away']):
    if sum(1 for m in hist.get(t, []) if m[0] < pd.Timestamp('2026-08-15')) >= 4:
        ok_teams.add(t)
lines.append('账本球队总数 %d, 有≥4场赛前历史 %d (%.0f%%)' % (total_teams, len(ok_teams), 100*len(ok_teams)/total_teams))
io.open('form_phase0/hf_backfill_cov2.txt','w',encoding='utf-8').write('\n'.join(lines))
print('saved')
