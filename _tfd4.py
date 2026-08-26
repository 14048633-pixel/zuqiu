import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1)
        v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
r = requests.get('https://api.football-data.org/v4/competitions/SB/matches?dateFrom=2026-08-23&dateTo=2026-08-25&status=FINISHED',
                 headers={'X-Auth-Token': env['FOOTBALL_DATA_KEY']}, timeout=30)
print('FD SB:', r.status_code, r.text[:200])
