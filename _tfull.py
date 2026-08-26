import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
KEY = env['ODDS_API_KEY_6']
BASE = 'https://api.the-odds-api.com/v4'
u = '%s/sports/soccer_chile_campeonato/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % (BASE, KEY)
r = requests.get(u, headers={'Accept': 'application/json'}, timeout=40)
d = r.json()
for ev in d:
    if ev.get('home_team') in ('La Serena',):
        print(json.dumps(ev, ensure_ascii=False, indent=1)[:1500])
