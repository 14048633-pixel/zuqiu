import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
KEY = ''
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if l.startswith('FOOTBALL_API_KEY='):
        KEY = l.split('=', 1)[1].strip().strip('"').strip("'")
print('fotmob/football-data key? key len:', len(KEY))
# try football-data.org
for base in ('https://api.football-data.org/v4',):
    try:
        r = requests.get(base + '/competitions/SA/matches?dateFrom=2026-08-23&dateTo=2026-08-24&status=FINISHED',
                         headers={'X-Auth-Token': KEY}, timeout=30)
        print('football-data SA status:', r.status_code, r.headers.get('X-Requests-Available-Minute'))
        if r.status_code == 200:
            d = r.json()
            for m in (d.get('matches') or [])[:5]:
                print('  ', m.get('homeTeam',{}).get('name'), 'vs', m.get('awayTeam',{}).get('name'), m.get('score',{}).get('fullTime'))
    except Exception as e:
        print('ERR', repr(e))
