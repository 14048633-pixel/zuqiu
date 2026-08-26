# -*- coding: utf-8 -*-
import sys, json, csv, io, os, collections
sys.stdout.reconfigure(encoding='utf-8')
# 验证 _csv_recent_league_avg 对 J1 的输出: 需要 j1_2026_results.csv 的 Div 是否匹配 ALL_DIVS
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
# 手动模拟 J1 csv 行
fp='data/raw/football_data/j1_2026_results.csv'
with io.open(fp,encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
print('J1 csv 行数:', len(rows))
print('首行:', rows[0])
print('Div:', rows[0].get('Div'), '| Season:', rows[0].get('Season'))
print('JP1 in ALL_DIVS?', 'JP1' in su.ALL_DIVS)
print('SEASON_WEIGHT 2026/2027 =', su.SEASON_WEIGHT.get('2026/2027'))
# 检查 _csv_recent_league_avg
out = su._csv_recent_league_avg()
print('recent avg J1:', out.get('J1'))
print('recent avg keys:', list(out.keys()))
