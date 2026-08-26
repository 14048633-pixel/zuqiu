import io, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
r = su.recent_league_avg()
print('recent_league_avg J1:', r.get('J1'), '| 中超:', r.get('中超'))
print('全部:', {k: v for k, v in r.items()})
