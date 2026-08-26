# -*- coding: utf-8 -*-
import pandas as pd, io, difflib
mx = pd.read_csv('data/raw/football_data/matches_with_xg.csv', low_memory=False, usecols=['HomeTeam','AwayTeam'])
mx = mx.dropna(subset=['HomeTeam'])
teams_mx = sorted(set(mx['HomeTeam'].astype(str)) | set(mx['AwayTeam'].astype(str)))
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
led_teams = sorted(set(led['home']) | set(led['away']))
out = io.open('_mxnames.txt','w',encoding='utf-8')
tmx = set(teams_mx)
hit = [t for t in led_teams if t in tmx]
out.write('matches_with_xg 队数: %d\n' % len(tmx))
out.write('账本%d队, matches_with_xg同名命中 %d\n' % (len(led_teams), len(hit)))
out.write('未命中(账本 -> 最接近):\n')
for t in led_teams:
    if t not in tmx:
        best = None; bs = 0
        for x in tmx:
            r = difflib.SequenceMatcher(None, t.lower(), str(x).lower()).ratio()
            if r > bs: bs = r; best = x
        out.write('  %-32s -> %-32s (%.2f)\n' % (t, best, bs))
out.close()
print('ok')
