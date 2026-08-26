# -*- coding: utf-8 -*-
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8')
# 1) 37场欧战复盘: 有方向=1X2/OU 实盘腿
d37 = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
n37_ou = sum(1 for m in d37 if any(k.startswith(('小球','大球')) for k in m))
n37_1x2 = sum(1 for m in d37 if '1X2主' in m or '1X2客' in m)
print('37场欧战: 1X2实盘方向 %d, OU实盘方向 %d' % (n37_1x2, n37_ou))
# 2) 08-21 4场(南美杯/解放者杯/J1x2) 方向文件
txt = open('analysis_records/scan_window_20260821_ah5_directions.txt', encoding='utf-8').read()
targets = ['Botafogo','Corinthians','Kashiwa','FC Tokyo']
n4=0
for t in targets:
    hit = [l for l in txt.split('\n') if t in l and '08-21' in l]
    for l in hit:
        # 实盘腿: OU/1X2 有赔率
        has_ou = 'OU:' in l
        has_1x2 = '1X2:' in l
        print(l[:100])
        if has_ou or has_1x2: n4+=1
print('08-21 4场中 有OU或1X2实盘方向:', n4)
