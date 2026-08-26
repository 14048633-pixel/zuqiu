# -*- coding: utf-8 -*-
import pandas as pd, io
back = pd.read_csv('data/raw/football_data/hf_2025_26_backfill.csv', low_memory=False)
e2 = back[back['Div']=='E2']
out = io.open('_e2.txt','w',encoding='utf-8')
out.write('E2 队数: %d\n' % len(set(e2['HomeTeam'])|set(e2['AwayTeam'])))
out.write(sorted(set(e2['HomeTeam'])|set(e2['AwayTeam'])).__str__())
out.close()
print('ok')
