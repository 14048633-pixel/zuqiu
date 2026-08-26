# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('analysis_records/scan48h_20260821_0048_clean.json', encoding='utf-8'))
ms = sorted(d['matches'], key=lambda x: x['kickoff'])
from collections import Counter
c = Counter(m['league'] for m in ms)
print('窗口:', d['window_start'], '->', d['window_end'])
print('场次:', len(ms), '| 联赛:', len(c))
for k,v in c.most_common(): print('  ', k, v)
print()
print('== 逐场 ==')
for m in ms:
    print('%-11s | %-14s | %s vs %s' % (m['kickoff'], m['league'], m['home'], m['away']))
