import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
KEY = env['ODDS_API_KEY_6']
u = 'https://api.the-odds-api.com/v4/sports/?apiKey=%s' % KEY
r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
print('status:', r.status_code, 'remaining:', r.headers.get('x-requests-remaining'))
if r.status_code == 200:
    for s in sorted(r.json(), key=lambda x: x.get('key','')):
        if s.get('group') == 'Soccer' and any(k in s.get('key','') for k in ('uefa','champ','europa','league_','superlig','russia','swiss','romania','bulgar','serie_b','bundesliga2','dfb','cup','soccer_england_efl')):
            print(' ', s.get('key'), '|', s.get('title'), '| active:', s.get('active'))
