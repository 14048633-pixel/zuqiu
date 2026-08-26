import io, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
j1 = {t: ts[t].get('JP1') for t in ts if isinstance(ts[t], dict) and 'JP1' in ts[t]}
print('J1 球队数:', len(j1))
for t, r in sorted(j1.items(), key=lambda x: -(x[1].get('n_home') or 0)):
    print('%-24s n_home=%s n_away=%s best_season=%s gf/ga(h)=%s/%s gf/ga(a)=%s/%s' % (
        t, r.get('n_home'), r.get('n_away'), r.get('best_season'),
        r.get('home_gf'), r.get('home_ga'), r.get('away_gf'), r.get('away_ga')))
print()
print('lavg JP1:', lavg.get('JP1'))
