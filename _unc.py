# -*- coding: utf-8 -*-
import pandas as pd, io, json, collections
ROOT = r'D:\足球分析'
def robust_date(s):
    s = str(s).strip()
    if not s: return pd.NaT
    try:
        if "/" in s:
            parts = s.split("/")
            if len(parts) == 3 and len(parts[0]) == 4:
                return pd.to_datetime(s, format="%Y/%m/%d", errors="coerce")
            return pd.to_datetime(s, dayfirst=True, format="mixed", errors="coerce")
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT
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
    df['Date'] = df['Date'].map(robust_date)
    pool.append(df)
p = pd.concat(pool, ignore_index=True).dropna(subset=['Date'])
hist = collections.defaultdict(list)
for _, r in p.iterrows():
    hist[str(r['HomeTeam']).strip()].append((r['Date'], r['home_xG_for']))
    hist[str(r['AwayTeam']).strip()].append((r['Date'], r['away_xG_for']))
out = io.open('_uncovered.txt','w',encoding='utf-8')
seen = set()
for _, b in led.iterrows():
    for team, date in [(b['home'], pd.to_datetime(b['date'])), (b['away'], pd.to_datetime(b['date']))]:
        key = (team, b['league'])
        past = [m for m in hist.get(str(team).strip(), []) if m[0] < date]
        if len(past) < 4 and key not in seen:
            seen.add(key)
            out.write('%s (%s): %d场赛前历史, xG %d\n' % (team, b['league'], len(past), sum(1 for m in past if pd.notna(m[1]))))
out.close()
print('saved')
