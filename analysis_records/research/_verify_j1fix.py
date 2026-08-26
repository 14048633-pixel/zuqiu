# -*- coding: utf-8 -*-
import sys, json, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
# 确认 J1 配置
print('scan_upcoming J1 league_avg:', su.CAL.get('J1',{}).get('league_avg'))
# 验证 j1_odds_zones 修改
z=json.load(open('strategy_data/j1_odds_zones.json',encoding='utf-8'))
print('j1_odds_zones baseline avg:', z['baseline']['avg_goals'], '| effective:', z['baseline'].get('effective_2026'))
print('zone1 rule_basis:', z['odds_zones']['zone1_1.30_1.50'].get('rule_basis_2026','无')[:40])
print('asian_hdp rule_basis:', z['asian_hdp'].get('rule_basis_2026','无')[:40])
print()
# 用今天 J1 场次验证 λ
from datetime import datetime, timezone
ts, lavg, index = su.load_team_stats()
for m in [
    {'league':'J1','home':'Kashiwa Reysol','away':'V-Varen Nagasaki','ct':datetime(2026,8,21,10,0,tzinfo=timezone.utc),'snap':'2026-08-21T09:30:00Z'},
    {'league':'J1','home':'FC Tokyo','away':'JEF United Chiba','ct':datetime(2026,8,21,10,30,tzinfo=timezone.utc),'snap':'2026-08-21T10:00:00Z'},
]:
    r = su.analyze_match(dict(m), ts, lavg, index)
    lam = r['lambda']
    print('%s vs %s -> λ %.2f/%.2f (sum %.2f) | data_src %s' % (
        m['home'], m['away'], lam['home'], lam['away'], lam['sum'], r.get('data_src')))
