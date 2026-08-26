import io, sys, csv, os, collections
sys.stdout.reconfigure(encoding='utf-8')
p='prediction_v2/output/odds_snapshots/snapshots.csv'
if not os.path.exists(p):
    print('快照文件不存在:', p); sys.exit()
with io.open(p, encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('总行:', len(rows), '列:', list(rows[0].keys())[:12])
lg = collections.Counter((r.get('league') or '?') for r in rows)
print('联赛分布:', dict(lg.most_common(20)))
