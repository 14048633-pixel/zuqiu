import io, sys, csv, collections, os
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding='utf-8')
p='prediction_v2/output/odds_snapshots/snapshots.csv'
rows=list(csv.DictReader(io.open(p, encoding='utf-8-sig')))
lg = collections.Counter((r.get('league') or '?') for r in rows)
print('葡超:', lg.get('葡超'), '| 荷甲:', lg.get('荷甲'), '| 比甲:', lg.get('比甲'))
# 快照时间范围
ts = [r.get('snapshot_ts') for r in rows if r.get('snapshot_ts')]
print('快照时间: min=%s max=%s' % (min(ts), max(ts)))
# 未来比赛(commence_time > now)
now = datetime.now(timezone.utc)
def pt(s):
    try: return datetime.fromisoformat(s.replace('Z','+00:00'))
    except: return None
fut = collections.defaultdict(list)
for r in rows:
    ct = pt(r.get('commence_time') or '')
    if ct and ct > now:
        fut[(r.get('league'), r.get('home_team'), r.get('away_team'))].append(ct)
print('未来比赛(UTC now=%s):' % now.isoformat()[:16])
for (lgk, h, a), cts in sorted(fut.items(), key=lambda x: min(x[1])):
    print('  %s | %s vs %s | %s' % (lgk, h, a, min(cts).isoformat()[:16]))
