# -*- coding: utf-8 -*-
import csv, io, collections, sys
sys.path.insert(0, r'src/models')
from poisson_lambda import dixon_coles_prob

# 大表 league 全集
fp = r'data/raw/football_data/matches_2015_2025.csv'
leagues = collections.Counter()
with io.open(fp, encoding='utf-8-sig') as f:
    r = csv.DictReader(f)
    for row in r:
        lg = (row.get('league') or '').strip()
        if lg: leagues[lg] += 1
print('大表league:', dict(sorted(leagues.items(), key=lambda x:-x[1])))
