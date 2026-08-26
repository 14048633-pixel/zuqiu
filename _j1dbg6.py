import io, sys, csv
sys.stdout.reconfigure(encoding='utf-8')
# 检查 bsd_batch CSV 是否含 J1/JP1
p='data/raw/football_data/bsd_batch_20260821.csv'
import os
if os.path.exists(p):
    with io.open(p, encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    print('bsd_batch 行数:', len(rows), '列:', list(rows[0].keys()) if rows else None)
    import collections
    print('联赛分布:', collections.Counter(r.get('league') or r.get('Div') or '?' for r in rows).most_common(20))
else:
    print('bsd_batch_20260821.csv 不存在')
