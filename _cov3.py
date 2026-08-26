# -*- coding: utf-8 -*-
import pandas as pd, io, json, collections
ROOT = r'D:\足球分析'
canon = json.load(io.open(ROOT + r'\form_phase0\team_name_canon.json', encoding='utf-8'))
hf2c = canon['hf_to_canon']; mx2c = canon['mx_to_canon']
def norm(x):
    s = str(x).strip()
    return mx2c.get(s, hf2c.get(s, s))
led = pd.read_csv(ROOT + r'\analysis_records\bet_ledger.csv', encoding='utf-8-sig')
pool = []
for f, apply_norm in [('data/raw/football_data/matches_with_xg.csv', True),
                      ('data/raw/football_data/hf_2025_26_backfill.csv', False),
                      ('data/raw/football_data/matches_2023_2024.csv', True),
                      ('data/raw/football_data/football_data_recent.csv', True)]:
    df = pd.read_csv(ROOT + '/' + f, low_memory=False)
    need = ['Date','HomeTeam','AwayTeam','home_xG_for','away_xG_for']
    for c in need:
        if c not in df.columns: df[c] = None
    df = df[need]
    if apply_norm:
        df['HomeTeam'] = df['HomeTeam'].map(norm); df['AwayTeam'] = df['AwayTeam'].map(norm)
    pool.append(df)
p = pd.concat(pool, ignore_index=True)
p['Date'] = pd.to_datetime(p['Date'], errors='coerce', dayfirst=True)
p = p.dropna(subset=['Date'])
hist = collections.defaultdict(list)
for _, r in p.iterrows():
    hist[str(r['HomeTeam']).strip()].append((r['Date'], r['home_xG_for']))
    hist[str(r['AwayTeam']).strip()].append((r['Date'], r['away_xG_for']))
out = io.open('form_phase0/hf_backfill_cov3.txt','w',encoding='utf-8')
missing = collections.Counter()
for _, b in led.iterrows():
    for team, date in [(b['home'], pd.to_datetime(b['date'])), (b['away'], pd.to_datetime(b['date']))]:
        past = [m for m in hist.get(str(team).strip(), []) if m[0] < date]
        n = len(past); nx = sum(1 for m in past if pd.notna(m[1]))
        if n < 4:
            missing[(b['league'], n, nx)] += 1
out.write('合并池(规范化后) 历史<4场: %d 次\n' % sum(missing.values()))
for (lg, n, nx), v in sorted(missing.items(), key=lambda x: -x[1])[:25]:
    out.write('  %s: %d场历史(含xG %d) -> %d次\n' % (lg, n, nx, v))
teams_all = set(led['home']) | set(led['away'])
ok = 0
for t in teams_all:
    if sum(1 for m in hist.get(t, []) if m[0] < pd.Timestamp('2026-08-15')) >= 4:
        ok += 1
out.write('账本球队 %d, ≥4场赛前历史 %d (%.0f%%)\n' % (len(teams_all), ok, 100*ok/len(teams_all)))
# 有 xG 的场次数
withxg = sum(1 for lst in hist.values() for m in lst if pd.notna(m[1]))
out.write('合并池历史记录中 xG 覆盖: %d 条\n' % withxg)
out.close()
print('saved')
