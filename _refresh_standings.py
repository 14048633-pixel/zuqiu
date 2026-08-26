# -*- coding: utf-8 -*-
import io, sys, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import _batch_match_info as bmi
n = 0
for lg in bmi.BSD_LEAGUE_ID:
    try:
        d = bmi.bsd_standings(lg)
    except Exception as e:
        d = {}
        print('ERR', lg, repr(e)[:100])
    if d:
        n += 1
        print('OK  %-6s %d 队' % (lg, len(d)))
    else:
        print('--  %-6s (空/未覆盖)' % lg)
    time.sleep(0.3)
print('covered leagues:', n, '/', len(bmi.BSD_LEAGUE_ID))
