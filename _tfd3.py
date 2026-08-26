import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
# football-data
r = requests.get('https://api.football-data.org/v4/competitions/SB/matches?dateFrom=2026-08-23&dateTo=2026-08-25&status=FINISHED',
                 headers={'X-Auth-Token': env['FOOTBALL_DATA_KEY']}, timeout=30)
print('FD SB:', r.status_code, r.text[:120])
# API-Football
r2 = requests.get('https://v3.football.api-sports.io/status',
                  headers={'x-apisports-key': env['FOOTBALL_API_KEY']}, timeout=30)
print('APIFB status:', r2.status_code, r2.text[:200])
