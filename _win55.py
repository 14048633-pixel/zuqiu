import json, io, sys, collections, re, unicodedata
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
scan = json.load(io.open(r'analysis_records/20260823_scan_upcoming.json', encoding='utf-8'))
CST = timezone(timedelta(hours=8))
w0 = datetime(2026,8,23,20,0,tzinfo=CST); w1 = datetime(2026,8,24,13,0,tzinfo=CST)
sel = [m for m in scan['matches'] if w0 <= datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(CST) <= w1]
print('昨晚窗口场次:', len(sel))
# 已结算的比分 (prematch_results)
res = { (o['lg'], o['h'], o['a']): o for o in json.load(io.open(r'analysis_records/20260824_prematch_results.json', encoding='utf-8')) }
nores = []
for m in sel:
    k = (m['league'], m['home'], m['away'])
    if k in res and res[k].get('hg') is not None: continue
    nores.append(m)
print('缺结果(未在已结算清单):', len(nores))
by = collections.Counter(m['league'] for m in nores)
print('按联赛:', dict(by.most_common(20)))
for m in sorted(nores, key=lambda x: x['ct']):
    ct = datetime.fromisoformat(m['ct'].replace('Z','+00:00')).astimezone(CST)
    print(' ', ct.strftime('%m-%d %H:%M'), m['league'], m['home'], 'vs', m['away'])
