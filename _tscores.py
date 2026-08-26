import json, io, sys, requests, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1)
        v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
KEY = env['ODDS_API_KEY_6']
BASE = 'https://api.the-odds-api.com/v4'
# test scores for chile, serie b, finland
for sport in ('soccer_chile_campeonato', 'soccer_italy_serie_b', 'soccer_finland_veikkausliiga'):
    u = '%s/sports/%s/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % (BASE, sport, KEY)
    r = requests.get(u, headers={'Accept': 'application/json'}, timeout=40)
    print(sport, 'status:', r.status_code, 'remaining:', r.headers.get('x-requests-remaining'))
    if r.status_code == 200:
        d = r.json()
        print('  rows:', len(d) if isinstance(d, list) else d)
        for ev in (d if isinstance(d, list) else [])[:6]:
            sc = ev.get('scores') or []
            h = a = None
            for s in sc:
                if s.get('name') == 'Home': h = s.get('score')
                if s.get('name') == 'Away': a = s.get('score')
            print('   ', ev.get('home_team'), 'vs', ev.get('away_team'), '|', h, a, '|', ev.get('completed'))
