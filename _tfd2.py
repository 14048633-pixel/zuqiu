import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
KEY = ''
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if l.startswith('FOOTBALL_API_KEY='):
        KEY = l.split('=', 1)[1].strip().strip('"').strip("'")
r = requests.get('https://api.football-data.org/v4/competitions/SB/matches?dateFrom=2026-08-23&dateTo=2026-08-25&status=FINISHED',
                 headers={'X-Auth-Token': KEY}, timeout=30)
print('SB status:', r.status_code, r.text[:200])
r2 = requests.get('https://api.football-data.org/v4/competitions/CLP/matches?dateFrom=2026-08-23&dateTo=2026-08-25&status=FINISHED',
                  headers={'X-Auth-Token': KEY}, timeout=30)
print('CLP status:', r2.status_code, r2.text[:200])
