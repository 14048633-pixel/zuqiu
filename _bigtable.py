# -*- coding: utf-8 -*-
import csv, io, collections

fp = r'data/raw/football_data/matches_2015_2025.csv'
agg = collections.defaultdict(lambda: {'n':0,'hw':0,'dr':0,'aw':0,'hg':0,'ag':0})
seasons = collections.defaultdict(collections.Counter)
with io.open(fp, encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    for row in r:
        lg = (row.get('league') or '').strip()
        if not lg: continue
        try:
            fh = float(row.get('FTHG') or 0); fa = float(row.get('FTAG') or 0)
        except: continue
        a = agg[lg]; a['n'] += 1; a['hg'] += fh; a['ag'] += fa
        if fh > fa: a['hw'] += 1
        elif fh == fa: a['dr'] += 1
        else: a['aw'] += 1
        seasons[lg][row.get('season','')] += 1

print('league   n     HW%   DR%   AW%   avg   HA   近3季')
for lg, a in sorted(agg.items(), key=lambda x: -x[1]['n']):
    if a['n'] < 500: continue
    n = a['n']
    hw, dr, aw, hg, ag = a['hw'], a['dr'], a['aw'], a['hg'], a['ag']
    ha = hg/ag if ag else 0
    # 近3季: 主胜/平局/客胜
    recent = collections.Counter()
    for row_season, cnt in seasons[lg].items():
        pass
    print('%-4s %6d %5.1f %5.1f %5.1f %5.2f %4.2f' % (lg, n, hw/n*100, dr/n*100, aw/n*100, (hg+ag)/n, ha))
