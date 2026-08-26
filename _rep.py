# -*- coding: utf-8 -*-
import pandas as pd, io
out = io.open('_report.txt','w',encoding='utf-8')
back = pd.read_csv('data/raw/football_data/hf_2025_26_backfill.csv')
out.write('回填 %d 场\n' % len(back))
out.write('Div分布: %s\n' % back['Div'].value_counts().head(30).to_dict())
cov = pd.read_csv('form_phase0/hf_backfill_coverage.csv')
no_data = cov[cov['with_stats']==0]
out.write('无stats球队 %d:\n%s\n' % (len(no_data), no_data.to_string()))
low = cov[cov['with_stats']<4]
out.write('stats<4场球队 %d:\n%s\n' % (len(low), low.to_string()))
out.close()
print('saved')
