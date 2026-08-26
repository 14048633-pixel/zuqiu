import io, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
from datetime import datetime, timezone
import scan_upcoming as su

ts, lavg, index = su.load_team_stats()
lg = 'J1'
div = su.DIV_BY_LEAGUE.get(lg)
print('div:', div)
cal0 = su._cal_for_league(lg) or su.CAL.get(lg)
print('cal0:', cal0)
# 复刻 analyze_match 的 cal fallback
cal = su._cal_for_league(lg) or su.CAL.get(lg, {'league_avg': lavg.get(div, 2.6), 'rho': 0.0, 'shrink': 1.0, 'home': 1.0, 'away': 1.0, 'fatigue': 1.0})
print('cal.league_avg:', cal['league_avg'])
print('lavg.get(div,2.6):', lavg.get(div, 2.6))
ri = su.recent_league_avg().get(lg)
print('recent_league_avg().get(J1):', ri)
if ri and abs(ri[0] - cal['league_avg']) > su.LEAGUE_AVG_DEV_TOL:
    old = cal['league_avg']
    dev = round(ri[0] - old, 3)
    shifted = round(old + dev * su.LEAGUE_AVG_SHIFT_W, 3)
    print('会平移:', old, '->', shifted, 'dev=', dev)
