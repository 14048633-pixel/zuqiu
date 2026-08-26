import io, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
from datetime import datetime, timezone
import scan_upcoming as su

# 用真实 recent_league_avg（不 mock）
ts, lavg, index = su.load_team_stats()
print('lavg 含 JP1 吗:', 'JP1' in lavg, '| lavg.get(JP1)=', lavg.get('JP1'))
print('recent_league_avg J1:', su.recent_league_avg().get('J1'))

m = {"id": "t", "league": "J1", "home": "Yokohama F Marinos", "away": "Avispa Fukuoka",
     "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
     "snap": "2026-08-16T10:00:00Z",
     "h2h": {"home": 2.0, "away": 3.4, "draw": 3.6},
     "spread": {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
     "totals": {"line": 3.5, "over_price": 2.05, "under_price": 1.78}}
r = su.analyze_match(m, ts, lavg, index)
print('lambda:', r['lambda'])
print('notes:')
for n in r['notes']:
    print('  ', n)
print('risk_tags:', r['risk_tags'])
print('best:', r['best_bet'])
