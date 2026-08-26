import io, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
ts, lavg, index = su.load_team_stats()
print('--- 直接看 agg 内 JP1 记录字段 ---')
for t in list(ts)[:0]: pass
j1 = {t: ts[t].get('JP1') for t in ts if isinstance(ts[t], dict) and 'JP1' in ts[t]}
k = list(j1.keys())[0]
print('示例', k, j1[k])
print()
print('--- match_stats 判定 ---')
for name in ['Yokohama F Marinos', 'Avispa Fukuoka', 'Kashiwa Reysol', 'Vissel Kobe']:
    r = su.match_stats(name, 'JP1', ts, index)
    print(name, '->', (r[0].get('src_tag'), r[0].get('src_season'), r[0].get('src_w'), 'n_home=', r[0].get('n_home'), 'n_away=', r[0].get('n_away')) if r[0] else None, '| h_fb=', r[2], 'xd=', r[4])
