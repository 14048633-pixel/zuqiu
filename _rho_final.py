# -*- coding: utf-8 -*-
import csv, io, collections, sys, json
sys.path.insert(0, r'src/models')
from poisson_lambda import dixon_coles_prob

# 大表实际
fp = r'data/raw/football_data/matches_2015_2025.csv'
agg = collections.defaultdict(lambda: {'n':0,'hw':0,'dr':0,'aw':0,'hg':0,'ag':0})
with io.open(fp, encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        lg = (row.get('league') or '').strip()
        if not lg: continue
        try: fh = float(row.get('FTHG') or 0); fa = float(row.get('FTAG') or 0)
        except: continue
        a = agg[lg]; a['n'] += 1; a['hg'] += fh; a['ag'] += fa
        if fh > fa: a['hw'] += 1
        elif fh == fa: a['dr'] += 1
        else: a['aw'] += 1

cal = json.load(io.open(r'strategy_data/league_calib.json', encoding='utf-8'))['leagues']
print('league  n   实际H/D/A    模型H/D/A     ΔH    ΔD    ΔA')
for lg, a in sorted(agg.items(), key=lambda x: -x[1]['n']):
    n = a['n']; ah, ad, aa = a['hw']/n*100, a['dr']/n*100, a['aw']/n*100
    cfg = cal.get(lg)
    if not cfg: continue
    avg_atk = cfg['league_avg']/2.0
    sp, mp = dixon_coles_prob(avg_atk*cfg['home'], avg_atk*cfg['away'], cfg['rho'])
    mh, md, ma = mp['win']*100, mp['draw']*100, mp['lose']*100
    print('%-4s %5d %5.1f %5.1f %5.1f | %5.1f %5.1f %5.1f | %+5.1f %+5.1f %+5.1f' % (lg, n, ah, ad, aa, mh, md, ma, ah-mh, ad-md, aa-ma))
